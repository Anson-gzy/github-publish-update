#!/usr/bin/env python3
"""Initialize, commit, and push a local repository to GitHub."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

from github_prepare_remote import GitHubApiError, ensure_gh_cli_ready, prepare_remote


class GitCommandError(RuntimeError):
    """Raised when a git command fails."""


def quote_cmd(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def run_git(
    repo: Path,
    args: list[str],
    *,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    cmd = ["git", *args]
    print(f"+ {quote_cmd(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=repo,
        text=True,
        capture_output=capture_output,
    )
    if check and result.returncode != 0:
        raise GitCommandError(
            f"Command failed ({result.returncode}): {quote_cmd(cmd)}\n"
            f"{result.stderr.strip()}"
        )
    return result


def is_git_repo(repo: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def has_head(repo: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def current_branch(repo: Path) -> str:
    result = run_git(repo, ["branch", "--show-current"])
    return result.stdout.strip()


def ensure_repo(repo: Path, branch: str, init_if_needed: bool) -> None:
    if is_git_repo(repo):
        return
    if not init_if_needed:
        raise GitCommandError(
            f"{repo} is not a git repository. Re-run with --init-if-needed."
        )
    run_git(repo, ["init", "-b", branch], capture_output=True)


def ensure_branch(
    repo: Path,
    requested_branch: str | None,
    checkout_branch: bool,
) -> str:
    branch = current_branch(repo)
    target = requested_branch or branch or "main"
    if branch == target:
        return target
    if branch and requested_branch and not checkout_branch:
        raise GitCommandError(
            f"Current branch is '{branch}', target branch is '{target}'. "
            "Use --checkout-branch to switch/create the requested branch."
        )
    run_git(repo, ["checkout", "-B", target], capture_output=True)
    return target


def origin_url(repo: Path) -> str | None:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def ensure_remote(repo: Path, remote_url: str | None, change_remote: bool) -> None:
    if not remote_url:
        return
    current = origin_url(repo)
    if current is None:
        run_git(repo, ["remote", "add", "origin", remote_url], capture_output=True)
        return
    if current == remote_url:
        return
    if not change_remote:
        raise GitCommandError(
            "origin already exists and points to a different URL. "
            "Use --change-remote to replace it."
        )
    run_git(repo, ["remote", "set-url", "origin", remote_url], capture_output=True)


def resolve_remote_url(args: argparse.Namespace) -> str | None:
    create = args.create_github_repo
    fork = args.fork_github_repo
    if args.remote_url and (create or fork):
        raise GitCommandError(
            "Choose either --remote-url or a GitHub API workflow flag "
            "(--create-github-repo / --fork-github-repo), not both."
        )
    if create and fork:
        raise GitCommandError(
            "Choose either --create-github-repo or --fork-github-repo, not both."
        )
    if not create and not fork:
        return args.remote_url

    try:
        summary = prepare_remote(
            create=create,
            fork=fork,
            owner=args.github_owner,
            private=args.private,
            description=args.repo_description,
            homepage=args.repo_homepage,
            wait_seconds=args.wait_seconds,
            reuse_existing=args.reuse_existing_repo,
            prefer_gh_cli=args.prefer_gh_cli,
            remote_protocol=args.gh_remote_protocol,
            api_base=args.api_base_url,
        )
    except GitHubApiError as exc:
        raise GitCommandError(str(exc)) from exc

    remote_url = (
        summary.get("preferred_remote_url")
        or summary.get("clone_url")
        or summary.get("ssh_url")
    )
    if not remote_url:
        raise GitCommandError("GitHub remote preparation did not return a usable remote URL.")
    print(f"Prepared GitHub remote: {summary['full_name']}")
    print(f"Remote URL: {remote_url}")
    return remote_url


def ensure_cli_auth_ready(args: argparse.Namespace) -> None:
    if not args.prefer_gh_cli:
        return
    if not (
        args.create_github_repo
        or args.fork_github_repo
        or args.gh_login_if_needed
        or args.gh_setup_git
    ):
        return
    ensure_gh_cli_ready(
        login_if_needed=args.gh_login_if_needed,
        git_protocol=args.gh_login_protocol,
        setup_git=args.gh_setup_git,
    )


def normalize_args(args: argparse.Namespace, repo: Path) -> argparse.Namespace:
    if not args.simple:
        return args

    args.prefer_gh_cli = True
    args.gh_login_if_needed = True
    args.gh_setup_git = True
    args.gh_login_protocol = "https"
    args.gh_remote_protocol = "https"
    args.init_if_needed = True
    args.reuse_existing_repo = True

    if not args.create_github_repo and not args.fork_github_repo and not args.remote_url:
        if origin_url(repo) is None:
            args.create_github_repo = repo.name

    if not args.message:
        args.message = "Publish project"

    return args


def stage_changes(repo: Path, paths: list[str]) -> None:
    if paths:
        run_git(repo, ["add", "--", *paths], capture_output=True)
        return
    run_git(repo, ["add", "-A"], capture_output=True)


def has_staged_changes(repo: Path) -> bool:
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    return result.returncode == 1


def default_commit_message(repo: Path, message: str | None) -> str:
    if message:
        return message
    if has_head(repo):
        return "Update project"
    return "Initial publish"


def commit_if_needed(repo: Path, message: str | None) -> bool:
    if not has_staged_changes(repo):
        print("No staged changes. Skipping commit.")
        return False
    run_git(repo, ["commit", "-m", default_commit_message(repo, message)], capture_output=True)
    return True


def push(repo: Path, branch: str) -> None:
    remote = origin_url(repo)
    if remote is None:
        raise GitCommandError(
            "No origin remote configured. Provide --remote-url or add origin first."
        )
    run_git(repo, ["push", "-u", "origin", branch], capture_output=False)


def show_summary(repo: Path) -> None:
    print("\nStatus:")
    print(run_git(repo, ["status", "--short", "--branch"]).stdout.strip())
    print("\nRemote:")
    print(run_git(repo, ["remote", "-v"]).stdout.strip())
    print("\nLatest commit:")
    print(run_git(repo, ["log", "--oneline", "--decorate", "-1"]).stdout.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize, commit, and push a local project to GitHub."
    )
    parser.add_argument("repo", help="Path to the local repository")
    parser.add_argument(
        "--remote-url",
        help="SSH or HTTPS remote URL to add or update as origin",
    )
    parser.add_argument(
        "--create-github-repo",
        help="Create a GitHub repository headlessly and use its remote URL as origin.",
    )
    parser.add_argument(
        "--fork-github-repo",
        help="Fork owner/repo headlessly and use the fork's remote URL as origin.",
    )
    parser.add_argument(
        "--github-owner",
        help="GitHub user or org for repo creation, or destination owner for forks.",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Create the GitHub repository as private when using --create-github-repo.",
    )
    parser.add_argument(
        "--repo-description",
        help="Repository description for --create-github-repo.",
    )
    parser.add_argument(
        "--repo-homepage",
        help="Repository homepage URL for --create-github-repo.",
    )
    parser.add_argument(
        "--reuse-existing-repo",
        action="store_true",
        help="Reuse an existing GitHub repository with the same owner/name when auto-creating a remote.",
    )
    parser.add_argument(
        "--prefer-gh-cli",
        action="store_true",
        help="Use authenticated GitHub CLI commands first when creating or forking a remote.",
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help=(
            "Fast path: infer the repo name from the folder, enable GitHub CLI, "
            "log in if needed, configure git credentials, reuse existing repos, "
            "and prefer HTTPS remotes."
        ),
    )
    parser.add_argument(
        "--gh-login-if-needed",
        action="store_true",
        help="When GitHub CLI is preferred, launch `gh auth login` automatically if needed.",
    )
    parser.add_argument(
        "--gh-setup-git",
        action="store_true",
        help="Run `gh auth setup-git` before publishing when GitHub CLI is preferred.",
    )
    parser.add_argument(
        "--gh-login-protocol",
        choices=("https", "ssh"),
        default="https",
        help="Protocol to configure during `gh auth login`. Default: https.",
    )
    parser.add_argument(
        "--gh-remote-protocol",
        choices=("https", "ssh"),
        default="https",
        help="Remote URL type to prefer when creating or resolving a GitHub repo. Default: https.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=30,
        help="How long to wait for a new fork to become available. Default: 30.",
    )
    parser.add_argument(
        "--api-base-url",
        default="https://api.github.com",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--branch",
        help="Target branch. Defaults to the current branch or 'main' when unset.",
    )
    parser.add_argument(
        "--checkout-branch",
        action="store_true",
        help="Switch/create the requested branch before committing and pushing.",
    )
    parser.add_argument(
        "--message",
        help="Commit message. Defaults to 'Initial publish' or 'Update project'.",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Stage only the given path. Repeat to include multiple paths.",
    )
    parser.add_argument(
        "--init-if-needed",
        action="store_true",
        help="Run git init when the target folder is not yet a git repository.",
    )
    parser.add_argument(
        "--change-remote",
        action="store_true",
        help="Replace the existing origin when it points to a different URL.",
    )
    parser.add_argument(
        "--skip-push",
        action="store_true",
        help="Stop after staging and committing without pushing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).expanduser().resolve()
    if not repo.exists() or not repo.is_dir():
        print(f"Repository path does not exist or is not a directory: {repo}", file=sys.stderr)
        return 1
    args = normalize_args(args, repo)

    try:
        ensure_cli_auth_ready(args)
        ensure_repo(repo, args.branch or "main", args.init_if_needed)
        branch = ensure_branch(repo, args.branch, args.checkout_branch)
        remote_url = resolve_remote_url(args)
        ensure_remote(repo, remote_url, args.change_remote)
        stage_changes(repo, args.path)
        commit_if_needed(repo, args.message)
        if not args.skip_push:
            push(repo, branch)
        show_summary(repo)
    except (GitCommandError, GitHubApiError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
