#!/usr/bin/env python3
"""Check GitHub CLI availability and guide or launch authentication."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check GitHub CLI readiness and guide or start authentication."
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Launch `gh auth login` when authentication is missing.",
    )
    parser.add_argument(
        "--git-protocol",
        choices=("https", "ssh"),
        default="https",
        help="Protocol to configure during GitHub CLI login. Default: https.",
    )
    parser.add_argument(
        "--setup-git",
        action="store_true",
        help="Run `gh auth setup-git` after authentication so HTTPS pushes use the GitHub CLI credential helper.",
    )
    parser.add_argument(
        "--ensure-scope",
        action="append",
        default=[],
        help="Ensure that the authenticated GitHub CLI token has the given scope. Repeat for multiple scopes.",
    )
    parser.add_argument(
        "--refresh-if-needed",
        action="store_true",
        help="When scopes are missing, prefer `gh auth refresh` instead of a full re-login.",
    )
    return parser


def parse_scopes(text: str) -> set[str]:
    match = re.search(r"Token scopes:\s*(.+)", text)
    if not match:
        return set()
    raw = match.group(1).strip().strip("'")
    return {part.strip().strip("'") for part in raw.split(",") if part.strip()}


def run_capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
    )


def ensure_scopes(
    *,
    gh_path: str,
    current_scopes: set[str],
    requested_scopes: list[str],
    refresh_if_needed: bool,
) -> int:
    missing = [scope for scope in requested_scopes if scope not in current_scopes]
    if not missing:
        if requested_scopes:
            print(f"Required scopes already present: {', '.join(requested_scopes)}")
        return 0

    print(f"Missing GitHub CLI scopes: {', '.join(missing)}")
    if not refresh_if_needed:
        print(
            "Run `gh auth refresh -h github.com -s "
            + ",".join(missing)
            + "` to add them."
        )
        return 1

    refresh = subprocess.run(
        [gh_path, "auth", "refresh", "-h", "github.com", "-s", ",".join(missing)]
    )
    return refresh.returncode


def main() -> int:
    args = build_parser().parse_args()

    gh_path = shutil.which("gh")
    if not gh_path:
        print("GitHub CLI (`gh`) is not installed.", file=sys.stderr)
        print("Install it with `brew install gh` or from https://cli.github.com/.", file=sys.stderr)
        print("Then run `gh auth login --git-protocol https` and verify with `gh auth status`.", file=sys.stderr)
        return 1

    version = run_capture([gh_path, "--version"])
    if version.stdout.strip():
        print(version.stdout.strip().splitlines()[0])

    status = run_capture([gh_path, "auth", "status"])
    if status.returncode == 0:
        details = status.stdout.strip() or status.stderr.strip()
        print("GitHub CLI is authenticated and ready.")
        if details:
            print(details)
        scope_result = ensure_scopes(
            gh_path=gh_path,
            current_scopes=parse_scopes(details),
            requested_scopes=args.ensure_scope,
            refresh_if_needed=args.refresh_if_needed,
        )
        if scope_result != 0:
            return scope_result
        if args.setup_git:
            setup = run_capture([gh_path, "auth", "setup-git"])
            if setup.returncode != 0:
                print("GitHub CLI git credential setup failed.", file=sys.stderr)
                print(setup.stderr.strip() or setup.stdout.strip(), file=sys.stderr)
                return 1
            print("Configured git to use GitHub CLI credentials.")
        return 0

    print("GitHub CLI is installed but not authenticated.")
    print(
        f"Run `gh auth login --git-protocol {args.git_protocol}` and verify with `gh auth status`."
    )

    if not args.login:
        return 1

    login_cmd = [gh_path, "auth", "login", "--git-protocol", args.git_protocol, "--web"]
    if args.git_protocol == "ssh":
        login_cmd.append("--skip-ssh-key")
    login = subprocess.run(login_cmd)
    if login.returncode != 0:
        return login.returncode

    refreshed_status = run_capture([gh_path, "auth", "status"])
    details = refreshed_status.stdout.strip() or refreshed_status.stderr.strip()
    scope_result = ensure_scopes(
        gh_path=gh_path,
        current_scopes=parse_scopes(details),
        requested_scopes=args.ensure_scope,
        refresh_if_needed=args.refresh_if_needed,
    )
    if scope_result != 0:
        return scope_result

    if args.setup_git:
        setup = subprocess.run([gh_path, "auth", "setup-git"])
        return setup.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
