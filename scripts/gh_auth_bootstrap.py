#!/usr/bin/env python3
"""Check GitHub CLI availability and guide or launch authentication."""

from __future__ import annotations

import argparse
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
        help="Launch `gh auth login --git-protocol ssh` when authentication is missing.",
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
    return parser


def main() -> int:
    args = build_parser().parse_args()

    gh_path = shutil.which("gh")
    if not gh_path:
        print("GitHub CLI (`gh`) is not installed.", file=sys.stderr)
        print("Install it with `brew install gh` or from https://cli.github.com/.", file=sys.stderr)
        print("Then run `gh auth login --git-protocol https` and verify with `gh auth status`.", file=sys.stderr)
        return 1

    version = subprocess.run(
        [gh_path, "--version"],
        text=True,
        capture_output=True,
    )
    if version.stdout.strip():
        print(version.stdout.strip().splitlines()[0])

    status = subprocess.run(
        [gh_path, "auth", "status"],
        text=True,
        capture_output=True,
    )
    if status.returncode == 0:
        details = status.stdout.strip() or status.stderr.strip()
        print("GitHub CLI is authenticated and ready.")
        if details:
            print(details)
        if args.setup_git:
            setup = subprocess.run(
                [gh_path, "auth", "setup-git"],
                text=True,
                capture_output=True,
            )
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

    if args.setup_git:
        setup = subprocess.run([gh_path, "auth", "setup-git"])
        return setup.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
