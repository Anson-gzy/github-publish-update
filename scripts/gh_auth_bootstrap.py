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
    return parser


def main() -> int:
    args = build_parser().parse_args()

    gh_path = shutil.which("gh")
    if not gh_path:
        print("GitHub CLI (`gh`) is not installed.", file=sys.stderr)
        print("Install it with `brew install gh` or from https://cli.github.com/.", file=sys.stderr)
        print("Then run `gh auth login --git-protocol ssh` and verify with `gh auth status`.", file=sys.stderr)
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
        return 0

    print("GitHub CLI is installed but not authenticated.")
    print("Run `gh auth login --git-protocol ssh` and verify with `gh auth status`.")

    if not args.login:
        return 1

    login = subprocess.run([gh_path, "auth", "login", "--git-protocol", "ssh"])
    return login.returncode


if __name__ == "__main__":
    raise SystemExit(main())
