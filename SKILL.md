---
name: github-publish-update
description: Publish a local project to GitHub and push follow-up updates with a repeatable workflow. Use when Codex needs to create or connect a GitHub remote, inspect git status before publishing, stage and commit selected changes, push a first release, or sync later updates to an existing GitHub repository. Trigger phrases include "upload to GitHub", "push this project", "publish this repo", "update the GitHub repo", "sync my code", and Chinese requests such as "发到 GitHub", "上传项目", and "更新仓库".
---

# GitHub Publish Update

## Overview

Publish a local folder or git repository to GitHub, then reuse the same workflow for future updates. Prefer GitHub MCP for creating or verifying the remote repository, and use the bundled scripts for deterministic local git operations. This skill should complete headlessly whenever possible and should not rely on manually opening a browser.

## Quick Start

1. Inspect `git status --short --branch`, `git remote -v`, and `.gitignore` before pushing.
2. Reuse the current `origin` unless the user clearly wants a different remote.
3. Create or confirm the GitHub repository:
   - Prefer GitHub MCP when it is available.
   - Otherwise use the integrated headless GitHub API flow in `scripts/git_publish_update.py`.
   - The API helper uses `GITHUB_PAT`, `GITHUB_TOKEN`, `GH_TOKEN`, `GH_PAT`, or `gh auth token`.
   - Fall back to a user-provided repository URL when API-based creation is unavailable.
4. Run `scripts/git_publish_update.py` to initialize the repo if needed, create or fork the remote when requested, stage changes, create a commit, and push.
5. Verify with `git status --short --branch`, `git remote -v`, and `git log --oneline --decorate -1`.

## Safety Checks

- Review large binaries, build artifacts, model checkpoints, output directories, `.env` files, secrets, and credentials before staging.
- Refuse to replace an existing `origin` unless the user explicitly wants to move the repo or you use `--change-remote`.
- Prefer SSH remote URLs for push operations.
- Mention when git author identity is auto-derived and may need cleanup before a public push.
- If the working tree contains unrelated user changes, preserve them and stage only the intended paths.
- Do not use a browser as a default fallback. If GitHub MCP, `gh`, API tokens, and a user-provided remote are all unavailable, stop and ask for a GitHub token or repository URL instead.

## Workflows

### Publish a new local folder

1. If the folder is not a git repo, use `--init-if-needed`.
2. Create or identify the GitHub repo with GitHub MCP when available.
3. Otherwise create it headlessly with `scripts/git_publish_update.py --create-github-repo ...`.
4. Use the SSH clone URL when possible.
5. Run the script with `--remote-url` and an explicit commit message such as `Initial publish`.

### Update an existing GitHub repo

1. Reuse `origin` if it already points to the correct repo.
2. Stage either all changes or only the requested paths.
3. Let the script skip the commit when nothing changed.
4. Push the current branch or an explicit branch after confirming the target.

### Fork and push when the original repo is not writable

1. Detect the push failure or confirm that `origin` is read-only for the current identity.
2. Prefer GitHub MCP to create the fork when available.
3. Otherwise run `scripts/git_publish_update.py --fork-github-repo owner/repo ...`.
4. Push to the fork SSH URL instead of opening a browser.
5. Tell the user clearly when you pushed to a fork rather than the original repo.

## Script

Use the bundled script for the local git workflow:

```bash
python3 scripts/git_publish_update.py /path/to/repo --init-if-needed --remote-url git@github.com:user/repo.git --message "Initial publish"
```

```bash
python3 scripts/git_publish_update.py /path/to/repo --message "Update project"
```

```bash
python3 scripts/git_publish_update.py /path/to/repo --path src --path README.md --message "Update source and docs"
```

```bash
python3 scripts/git_publish_update.py /path/to/repo --remote-url git@github.com:user/new-repo.git --change-remote --message "Move to new remote"
```

Use the integrated no-browser publish flow when you want a single command:

```bash
python3 scripts/git_publish_update.py /path/to/repo --init-if-needed --create-github-repo repo-name --message "Initial publish"
```

```bash
python3 scripts/git_publish_update.py /path/to/repo --fork-github-repo owner/repo --change-remote --message "Push to fork"
```

## GitHub MCP Usage

- Use GitHub MCP to create repositories, inspect repository metadata, or confirm the correct SSH URL before pushing.
- Do not block on MCP when the user already supplied a remote URL and the local git workflow can proceed safely.
- If GitHub MCP is unavailable in the current session, use the built-in GitHub API path in `scripts/git_publish_update.py` before falling back to a user-provided remote URL.
- If no headless authentication path exists, say that explicitly and ask for `GITHUB_PAT`, `GITHUB_TOKEN`, `GH_TOKEN`, `gh auth login`, or a repository URL. Do not silently switch to browser automation.

## References

- Read `references/workflow.md` when you need the decision tree for new repo vs existing repo, remote replacement, authentication fallback, or branch handling.
