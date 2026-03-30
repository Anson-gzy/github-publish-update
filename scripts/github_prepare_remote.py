#!/usr/bin/env python3
"""Create or resolve GitHub repositories and forks without a browser."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


API_BASE = "https://api.github.com"
TOKEN_ENV_VARS = ("GITHUB_PAT", "GITHUB_TOKEN", "GH_TOKEN", "GH_PAT")


class GitHubApiError(RuntimeError):
    """Raised when the GitHub API cannot complete the requested operation."""


@dataclass
class AuthContext:
    token: str
    source: str


@dataclass
class GhCliContext:
    gh_path: str


def quote_cmd(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def gh_login_guidance() -> str:
    return (
        "GitHub CLI is not ready. Install it with `brew install gh` (or from "
        "https://cli.github.com/), then run `gh auth login --git-protocol ssh` "
        "and verify with `gh auth status`."
    )


def load_gh_cli(*, require_auth: bool) -> GhCliContext:
    gh_path = shutil.which("gh")
    if not gh_path:
        raise GitHubApiError(gh_login_guidance())

    if require_auth:
        result = subprocess.run(
            [gh_path, "auth", "status"],
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise GitHubApiError(
                "GitHub CLI is installed but not authenticated. "
                "Run `gh auth login --git-protocol ssh`, verify with "
                "`gh auth status`, then retry."
            )

    return GhCliContext(gh_path=gh_path)


def gh_status(gh: GhCliContext) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [gh.gh_path, "auth", "status"],
        text=True,
        capture_output=True,
    )


def ensure_gh_cli_ready(
    *,
    login_if_needed: bool,
    git_protocol: str,
    setup_git: bool,
) -> GhCliContext:
    gh = load_gh_cli(require_auth=False)
    status = gh_status(gh)
    if status.returncode != 0:
        if not login_if_needed:
            raise GitHubApiError(
                "GitHub CLI is installed but not authenticated. "
                "Run `gh auth login --git-protocol https`, verify with "
                "`gh auth status`, then retry."
            )
        login_cmd = [
            gh.gh_path,
            "auth",
            "login",
            "--git-protocol",
            git_protocol,
            "--web",
        ]
        if git_protocol == "ssh":
            login_cmd.append("--skip-ssh-key")
        login = subprocess.run(login_cmd, text=True)
        if login.returncode != 0:
            raise GitHubApiError(
                f"GitHub CLI login failed ({login.returncode}): {quote_cmd(login_cmd)}"
            )
        status = gh_status(gh)
        if status.returncode != 0:
            raise GitHubApiError(
                "GitHub CLI login completed, but `gh auth status` is still not ready."
            )

    if setup_git:
        setup = subprocess.run(
            [gh.gh_path, "auth", "setup-git"],
            text=True,
            capture_output=True,
        )
        if setup.returncode != 0:
            detail = setup.stderr.strip() or setup.stdout.strip()
            raise GitHubApiError(
                f"GitHub CLI git credential setup failed ({setup.returncode}).\n{detail}"
            )

    return gh


def gh_api_request(
    gh: GhCliContext,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cmd = [
        gh.gh_path,
        "api",
        path.lstrip("/"),
        "--method",
        method,
        "--header",
        "Accept: application/vnd.github+json",
    ]
    input_text = None
    if payload is not None:
        cmd.extend(["--input", "-"])
        input_text = json.dumps(payload)

    result = subprocess.run(
        cmd,
        text=True,
        input=input_text,
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise GitHubApiError(
            f"GitHub CLI command failed ({result.returncode}): {quote_cmd(cmd)}\n"
            f"{stderr}"
        )

    body = result.stdout.strip()
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise GitHubApiError(
            f"GitHub CLI command returned non-JSON content: {quote_cmd(cmd)}"
        ) from exc


def load_token() -> AuthContext:
    for env_name in TOKEN_ENV_VARS:
        value = os.environ.get(env_name, "").strip()
        if value:
            return AuthContext(token=value, source=f"env:{env_name}")

    gh_path = shutil.which("gh")
    if gh_path:
        result = subprocess.run(
            [gh_path, "auth", "token"],
            text=True,
            capture_output=True,
        )
        token = result.stdout.strip()
        if result.returncode == 0 and token:
            return AuthContext(token=token, source="gh auth token")

    raise GitHubApiError(
        "No GitHub API token available. Set GITHUB_PAT, GITHUB_TOKEN, GH_TOKEN, or "
        "GH_PAT, or install/authenticate GitHub CLI first. "
        + gh_login_guidance()
    )


def parse_owner_repo(value: str) -> tuple[str, str]:
    owner, sep, repo = value.strip().partition("/")
    if not sep or not owner or not repo:
        raise GitHubApiError(f"Expected owner/repo, got: {value!r}")
    return owner, repo


def api_request(
    auth: AuthContext,
    method: str,
    path: str,
    *,
    api_base: str = API_BASE,
    payload: dict[str, Any] | None = None,
    expected: tuple[int, ...] = (200,),
) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}{path}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {auth.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "codex-github-publish-update",
            **({"Content-Type": "application/json"} if payload is not None else {}),
        },
    )

    try:
        with urllib.request.urlopen(request) as response:
            status = response.getcode()
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body)
        except json.JSONDecodeError:
            detail = {"message": body or exc.reason}
        message = detail.get("message") or exc.reason
        errors = detail.get("errors")
        if errors:
            message = f"{message} | errors={errors}"
        raise GitHubApiError(f"GitHub API {method} {path} failed: {message}") from exc
    except urllib.error.URLError as exc:
        raise GitHubApiError(f"GitHub API {method} {path} failed: {exc.reason}") from exc

    if status not in expected:
        raise GitHubApiError(f"GitHub API {method} {path} returned unexpected status {status}")
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise GitHubApiError(f"GitHub API {method} {path} returned non-JSON content") from exc


def get_viewer(auth: AuthContext, *, api_base: str = API_BASE) -> dict[str, Any]:
    return api_request(auth, "GET", "/user", api_base=api_base)


def get_repo(
    auth: AuthContext,
    owner: str,
    repo: str,
    *,
    api_base: str = API_BASE,
) -> dict[str, Any]:
    return api_request(auth, "GET", f"/repos/{owner}/{repo}", api_base=api_base)


def repo_exists(
    auth: AuthContext,
    owner: str,
    repo: str,
    *,
    api_base: str = API_BASE,
) -> dict[str, Any] | None:
    try:
        return get_repo(auth, owner, repo, api_base=api_base)
    except GitHubApiError as exc:
        if "Not Found" in str(exc):
            return None
        raise


def gh_get_viewer(gh: GhCliContext) -> dict[str, Any]:
    return gh_api_request(gh, "GET", "/user")


def gh_get_repo(gh: GhCliContext, owner: str, repo: str) -> dict[str, Any]:
    return gh_api_request(gh, "GET", f"/repos/{owner}/{repo}")


def gh_repo_exists(gh: GhCliContext, owner: str, repo: str) -> dict[str, Any] | None:
    try:
        return gh_get_repo(gh, owner, repo)
    except GitHubApiError as exc:
        message = str(exc).lower()
        if "404" in message or "not found" in message:
            return None
        raise


def create_repo(
    auth: AuthContext,
    *,
    owner: str,
    name: str,
    private: bool,
    description: str | None,
    homepage: str | None,
    api_base: str = API_BASE,
) -> dict[str, Any]:
    viewer = get_viewer(auth, api_base=api_base)
    payload: dict[str, Any] = {
        "name": name,
        "private": private,
    }
    if description:
        payload["description"] = description
    if homepage:
        payload["homepage"] = homepage

    if owner == viewer["login"]:
        return api_request(
            auth,
            "POST",
            "/user/repos",
            api_base=api_base,
            payload=payload,
            expected=(201,),
        )
    return api_request(
        auth,
        "POST",
        f"/orgs/{owner}/repos",
        api_base=api_base,
        payload=payload,
        expected=(201,),
    )


def gh_create_repo(
    gh: GhCliContext,
    *,
    owner: str,
    name: str,
    private: bool,
    description: str | None,
    homepage: str | None,
) -> dict[str, Any]:
    viewer = gh_get_viewer(gh)
    payload: dict[str, Any] = {
        "name": name,
        "private": private,
    }
    if description:
        payload["description"] = description
    if homepage:
        payload["homepage"] = homepage

    if owner == viewer["login"]:
        return gh_api_request(gh, "POST", "/user/repos", payload=payload)
    return gh_api_request(gh, "POST", f"/orgs/{owner}/repos", payload=payload)


def fork_repo(
    auth: AuthContext,
    *,
    source_owner: str,
    source_repo: str,
    target_owner: str | None,
    wait_seconds: int,
    api_base: str = API_BASE,
) -> dict[str, Any]:
    viewer = get_viewer(auth, api_base=api_base)
    destination_owner = target_owner or viewer["login"]

    existing = repo_exists(auth, destination_owner, source_repo, api_base=api_base)
    if existing:
        return existing

    payload: dict[str, Any] = {}
    if target_owner and target_owner != viewer["login"]:
        payload["organization"] = target_owner

    api_request(
        auth,
        "POST",
        f"/repos/{source_owner}/{source_repo}/forks",
        api_base=api_base,
        payload=payload or None,
        expected=(202,),
    )

    deadline = time.time() + max(wait_seconds, 5)
    while time.time() < deadline:
        found = repo_exists(auth, destination_owner, source_repo, api_base=api_base)
        if found:
            return found
        time.sleep(2)

    raise GitHubApiError(
        f"Fork creation started but {destination_owner}/{source_repo} was not ready within {wait_seconds} seconds."
    )


def gh_fork_repo(
    gh: GhCliContext,
    *,
    source_owner: str,
    source_repo: str,
    target_owner: str | None,
    wait_seconds: int,
) -> dict[str, Any]:
    viewer = gh_get_viewer(gh)
    destination_owner = target_owner or viewer["login"]

    existing = gh_repo_exists(gh, destination_owner, source_repo)
    if existing:
        return existing

    payload: dict[str, Any] = {}
    if target_owner and target_owner != viewer["login"]:
        payload["organization"] = target_owner

    gh_api_request(
        gh,
        "POST",
        f"/repos/{source_owner}/{source_repo}/forks",
        payload=payload or None,
    )

    deadline = time.time() + max(wait_seconds, 5)
    while time.time() < deadline:
        found = gh_repo_exists(gh, destination_owner, source_repo)
        if found:
            return found
        time.sleep(2)

    raise GitHubApiError(
        f"Fork creation started but {destination_owner}/{source_repo} was not ready within {wait_seconds} seconds."
    )


def create_or_reuse_repo(
    auth: AuthContext,
    *,
    owner: str | None,
    name: str,
    private: bool,
    description: str | None,
    homepage: str | None,
    reuse_existing: bool,
    api_base: str = API_BASE,
) -> dict[str, Any]:
    viewer = get_viewer(auth, api_base=api_base)
    target_owner = owner or viewer["login"]
    if reuse_existing:
        existing = repo_exists(auth, target_owner, name, api_base=api_base)
        if existing:
            return existing
    return create_repo(
        auth,
        owner=target_owner,
        name=name,
        private=private,
        description=description,
        homepage=homepage,
        api_base=api_base,
    )


def gh_create_or_reuse_repo(
    gh: GhCliContext,
    *,
    owner: str | None,
    name: str,
    private: bool,
    description: str | None,
    homepage: str | None,
    reuse_existing: bool,
) -> dict[str, Any]:
    viewer = gh_get_viewer(gh)
    target_owner = owner or viewer["login"]
    if reuse_existing:
        existing = gh_repo_exists(gh, target_owner, name)
        if existing:
            return existing
    return gh_create_repo(
        gh,
        owner=target_owner,
        name=name,
        private=private,
        description=description,
        homepage=homepage,
    )


def summarize_repo_data(
    *,
    repo: dict[str, Any],
    viewer_login: str | None,
    auth_source: str,
) -> dict[str, Any]:
    owner = repo.get("owner") or {}
    default_branch = repo.get("default_branch")
    if not default_branch:
        default_branch_ref = repo.get("defaultBranchRef") or {}
        default_branch = default_branch_ref.get("name")

    return {
        "full_name": repo.get("full_name"),
        "owner": owner.get("login"),
        "name": repo.get("name"),
        "html_url": repo.get("html_url"),
        "ssh_url": repo.get("ssh_url"),
        "clone_url": repo.get("clone_url"),
        "default_branch": default_branch,
        "private": repo.get("private"),
        "viewer_login": viewer_login,
        "auth_source": auth_source,
    }


def apply_preferred_remote_url(summary: dict[str, Any], remote_protocol: str) -> dict[str, Any]:
    if remote_protocol == "ssh":
        summary["preferred_remote_url"] = summary.get("ssh_url") or summary.get("clone_url")
    else:
        summary["preferred_remote_url"] = summary.get("clone_url") or summary.get("ssh_url")
    return summary


def summarize_repo(
    auth: AuthContext,
    repo: dict[str, Any],
    *,
    api_base: str = API_BASE,
) -> dict[str, Any]:
    viewer = get_viewer(auth, api_base=api_base)
    return summarize_repo_data(
        repo=repo,
        viewer_login=viewer.get("login"),
        auth_source=auth.source,
    )


def prepare_remote(
    *,
    create: str | None,
    fork: str | None,
    owner: str | None,
    private: bool,
    description: str | None,
    homepage: str | None,
    wait_seconds: int,
    reuse_existing: bool,
    prefer_gh_cli: bool,
    remote_protocol: str,
    api_base: str = API_BASE,
) -> dict[str, Any]:
    if prefer_gh_cli:
        gh = load_gh_cli(require_auth=True)
        if fork:
            source_owner, source_repo = parse_owner_repo(fork)
            repo = gh_fork_repo(
                gh,
                source_owner=source_owner,
                source_repo=source_repo,
                target_owner=owner,
                wait_seconds=wait_seconds,
            )
        elif create:
            repo = gh_create_or_reuse_repo(
                gh,
                owner=owner,
                name=create,
                private=private,
                description=description,
                homepage=homepage,
                reuse_existing=reuse_existing,
            )
        else:
            raise GitHubApiError("One of create or fork must be provided.")
        viewer = gh_get_viewer(gh)
        summary = summarize_repo_data(
            repo=repo,
            viewer_login=viewer.get("login"),
            auth_source="gh cli",
        )
        return apply_preferred_remote_url(summary, remote_protocol)

    auth = load_token()
    if fork:
        source_owner, source_repo = parse_owner_repo(fork)
        repo = fork_repo(
            auth,
            source_owner=source_owner,
            source_repo=source_repo,
            target_owner=owner,
            wait_seconds=wait_seconds,
            api_base=api_base,
        )
    elif create:
        repo = create_or_reuse_repo(
            auth,
            owner=owner,
            name=create,
            private=private,
            description=description,
            homepage=homepage,
            reuse_existing=reuse_existing,
            api_base=api_base,
        )
    else:
        raise GitHubApiError("One of create or fork must be provided.")
    summary = summarize_repo(auth, repo, api_base=api_base)
    return apply_preferred_remote_url(summary, remote_protocol)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or resolve a GitHub repository or fork without using a browser."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--fork", help="Fork the given owner/repo into the authenticated account or target owner.")
    group.add_argument("--create", help="Create a new repository with this name.")
    parser.add_argument(
        "--owner",
        help="Target owner for --create, or destination owner/org for --fork. Defaults to the authenticated user.",
    )
    parser.add_argument("--private", action="store_true", help="Create the repository as private.")
    parser.add_argument("--description", help="Repository description for --create.")
    parser.add_argument("--homepage", help="Repository homepage URL for --create.")
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Return the existing repository when --create targets a repo that already exists under the same owner.",
    )
    parser.add_argument(
        "--prefer-gh-cli",
        action="store_true",
        help="Use authenticated GitHub CLI commands before falling back to raw token-based API calls.",
    )
    parser.add_argument(
        "--remote-protocol",
        choices=("https", "ssh"),
        default="https",
        help="Preferred remote URL type to return. Default: https.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=30,
        help="How long to wait for a new fork to become available. Default: 30.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")
    parser.add_argument(
        "--api-base-url",
        default=API_BASE,
        help=argparse.SUPPRESS,
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        summary = prepare_remote(
            create=args.create,
            fork=args.fork,
            owner=args.owner,
            private=args.private,
            description=args.description,
            homepage=args.homepage,
            wait_seconds=args.wait_seconds,
            reuse_existing=args.reuse_existing,
            prefer_gh_cli=args.prefer_gh_cli,
            remote_protocol=args.remote_protocol,
            api_base=args.api_base_url,
        )
        if args.json:
            print(json.dumps(summary, ensure_ascii=True, indent=2))
        else:
            print(f"Resolved repository: {summary['full_name']}")
            print(f"Preferred remote URL: {summary.get('preferred_remote_url')}")
            print(f"HTML URL: {summary['html_url']}")
            print(f"Viewer: {summary['viewer_login']}")
            print(f"Auth source: {summary['auth_source']}")
        return 0
    except GitHubApiError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
