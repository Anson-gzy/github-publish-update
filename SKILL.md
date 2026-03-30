---
name: github-publish-update
description: Publish a local project to GitHub and push follow-up updates with a repeatable workflow. Use when Codex needs to create or connect a GitHub remote, inspect git status before publishing, stage and commit selected changes, push a first release, or sync later updates to an existing GitHub repository. Trigger phrases include "upload to GitHub", "push this project", "publish this repo", "update the GitHub repo", "sync my code", and Chinese requests such as "发到 GitHub", "上传项目", and "更新仓库".
---

# GitHub Publish Update

## Overview

Publish a local folder or git repository to GitHub, then reuse the same workflow for future updates. Prefer GitHub MCP for creating or verifying the remote repository, then authenticated GitHub CLI over HTTPS with `gh auth setup-git`, and finally the bundled token-based scripts for deterministic local git operations. On first use, guide the user through GitHub CLI login so later uploads can complete directly.

## Quick Start

1. Prefer the fast path first:
   - Run `python3 scripts/git_publish_update.py /path/to/repo --simple`.
   - This infers the repo name from the folder, checks GitHub CLI login, runs `gh auth setup-git`, reuses an existing GitHub repo when possible, and prefers HTTPS remotes.
2. If GitHub CLI is not ready:
   - Run `python3 scripts/gh_auth_bootstrap.py --login --setup-git`.
   - If `gh` is not installed, guide the user to install it with `brew install gh`.
3. If GitHub CLI is already logged in but needs an extra scope:
   - Prefer `python3 scripts/gh_auth_bootstrap.py --ensure-scope <scope> --refresh-if-needed`.
   - Do not default to a full `gh auth login` when `gh auth refresh` is sufficient.
4. Inspect `git status --short --branch`, `git remote -v`, and `.gitignore` before pushing.
5. Reuse the current `origin` unless the user clearly wants a different remote.
6. Create or confirm the GitHub repository:
   - Prefer GitHub MCP when it is available.
   - Otherwise prefer authenticated GitHub CLI with `--simple` or `--prefer-gh-cli`.
   - If CLI is unavailable, use the integrated headless GitHub API flow in `scripts/git_publish_update.py`.
   - The API helper uses `GITHUB_PAT`, `GITHUB_TOKEN`, `GH_TOKEN`, `GH_PAT`, or `gh auth token`.
   - Fall back to a user-provided repository URL when API-based creation is unavailable.
7. Verify with `git status --short --branch`, `git remote -v`, and `git log --oneline --decorate -1`.

## Safety Checks

- Review large binaries, build artifacts, model checkpoints, output directories, `.env` files, secrets, and credentials before staging.
- Refuse to replace an existing `origin` unless the user explicitly wants to move the repo or you use `--change-remote`.
- Prefer HTTPS remotes with `gh auth setup-git` for the default fast path.
- Use SSH only when the user explicitly wants SSH or their environment requires it.
- If GitHub CLI is missing or unauthenticated, guide the user through installation and `python3 scripts/gh_auth_bootstrap.py --login --setup-git` before the first publish attempt.
- If a later task only needs extra scopes, prefer `gh auth refresh` instead of a full re-login.
- Mention when git author identity is auto-derived and may need cleanup before a public push.
- If the working tree contains unrelated user changes, preserve them and stage only the intended paths.
- Do not use a browser as a default fallback. If GitHub MCP, `gh`, API tokens, and a user-provided remote are all unavailable, stop and ask for a GitHub token or repository URL instead.

## Workflows

### Publish a new local folder

1. If the folder is not a git repo, use `--init-if-needed`.
2. Start with `python3 scripts/git_publish_update.py /path/to/repo --simple` when the user wants the quickest path.
3. Create or identify the GitHub repo with GitHub MCP when available.
4. Otherwise create it through GitHub CLI with `scripts/git_publish_update.py --simple` or `--prefer-gh-cli --gh-login-if-needed --gh-setup-git --gh-remote-protocol https --create-github-repo ...`.
5. If CLI is unavailable, create it headlessly with the token-based API path.
6. Prefer HTTPS remotes by default so pushes can reuse the GitHub CLI credential helper.
7. Use the SSH remote only when the user explicitly requests it.

### Update an existing GitHub repo

1. Reuse `origin` if it already points to the correct repo.
2. Stage either all changes or only the requested paths.
3. Let the script skip the commit when nothing changed.
4. If GitHub CLI is available, keep it authenticated so later pushes can proceed directly.
5. Push the current branch or an explicit branch after confirming the target.

### Fork and push when the original repo is not writable

1. Detect the push failure or confirm that `origin` is read-only for the current identity.
2. Prefer GitHub MCP to create the fork when available.
3. Otherwise prefer `scripts/git_publish_update.py --prefer-gh-cli --gh-login-if-needed --gh-setup-git --fork-github-repo owner/repo ...`.
4. Fall back to the token-based API path only when CLI is unavailable.
5. Prefer HTTPS remotes for the fork so the GitHub CLI credential helper can push without extra SSH setup.
6. Tell the user clearly when you pushed to a fork rather than the original repo.

## Script

Use the bundled script for the local git workflow:

```bash
python3 scripts/git_publish_update.py /path/to/repo --simple
```

```bash
python3 scripts/git_publish_update.py /path/to/repo --message "Update project"
```

```bash
python3 scripts/git_publish_update.py /path/to/repo --path src --path README.md --message "Update source and docs"
```

```bash
python3 scripts/git_publish_update.py /path/to/repo --remote-url https://github.com/user/new-repo.git --change-remote --message "Move to new remote"
```

Use the integrated no-browser publish flow when you want a single command:

```bash
python3 scripts/gh_auth_bootstrap.py --login --setup-git
```

```bash
python3 scripts/git_publish_update.py /path/to/repo --init-if-needed --prefer-gh-cli --gh-login-if-needed --gh-setup-git --gh-remote-protocol https --create-github-repo repo-name --message "Initial publish"
```

```bash
python3 scripts/git_publish_update.py /path/to/repo --prefer-gh-cli --gh-login-if-needed --gh-setup-git --gh-remote-protocol https --fork-github-repo owner/repo --change-remote --message "Push to fork"
```

## GitHub MCP and CLI Usage

- Use GitHub MCP to create repositories, inspect repository metadata, or confirm the correct remote URL before pushing.
- On the first publish request, prefer `python3 scripts/git_publish_update.py /path/to/repo --simple`.
- If GitHub CLI is not ready, guide the user through `python3 scripts/gh_auth_bootstrap.py --login --setup-git`.
- Use `scripts/gh_auth_bootstrap.py` when you want a quick install/auth readiness check.
- Use `--prefer-gh-cli` when you want repository creation and fork management to run through authenticated GitHub CLI commands.
- Use `--gh-remote-protocol ssh` only when the user explicitly wants SSH.
- Do not block on MCP when the user already supplied a remote URL and the local git workflow can proceed safely.
- If GitHub MCP is unavailable in the current session, prefer authenticated GitHub CLI before the built-in token-based API path.
- If no headless authentication path exists, say that explicitly and ask for `GITHUB_PAT`, `GITHUB_TOKEN`, `GH_TOKEN`, `gh auth login`, or a repository URL. Do not silently switch to browser automation.

## References

- Read `references/workflow.md` when you need the decision tree for new repo vs existing repo, remote replacement, authentication fallback, or branch handling.
- Use `scripts/gh_auth_bootstrap.py` for first-run GitHub CLI guidance.
