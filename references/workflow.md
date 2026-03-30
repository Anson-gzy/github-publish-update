# GitHub Publish Workflow

## Decision Tree

1. Check the local repository state first.
   - Run `git status --short --branch`.
   - Run `git remote -v`.
   - Inspect `.gitignore`.
2. Decide whether this is a first publish or a later update.
   - First publish: create or confirm the GitHub repository, then set `origin`.
   - Later update: reuse `origin` unless the user wants a different repo.
3. Decide how to resolve the remote repository.
   - Prefer GitHub MCP when it is available and authenticated.
   - Otherwise use `scripts/git_publish_update.py --create-github-repo ...` or `--fork-github-repo ...`.
   - The headless API path accepts `GITHUB_PAT`, `GITHUB_TOKEN`, `GH_TOKEN`, `GH_PAT`, or `gh auth token`.
   - Fall back to a user-provided GitHub URL only when the API path is unavailable.
4. Decide how much to stage.
   - Use `--path` when the repo contains unrelated user changes.
   - Use the default full-repo stage only after checking ignored files and build artifacts.
5. If the existing remote is not writable.
   - Prefer a headless fork workflow over browser automation.
   - Create the fork with `scripts/github_prepare_remote.py --fork owner/repo --json`.
   - Push to the fork and tell the user what happened.

## Recommended Commands

### Publish a new folder

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --init-if-needed \
  --create-github-repo repo-name \
  --message "Initial publish"
```

### Fork an existing GitHub repo without a browser

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --fork-github-repo owner/repo \
  --change-remote \
  --message "Push to fork"
```

### Push later updates

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --message "Update project"
```

### Stage only selected paths

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --path src \
  --path README.md \
  --message "Update docs and source"
```

### Move to a new remote

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --remote-url git@github.com:user/new-repo.git \
  --change-remote \
  --message "Move to new remote"
```

## Guardrails

- Do not overwrite `origin` silently.
- Prefer SSH URLs to avoid interactive HTTPS credential prompts.
- Call out suspicious files before staging:
  - `.env`
  - tokens or credentials
  - model checkpoints
  - generated outputs
  - app bundles
  - build directories
- If git author identity looks auto-generated, tell the user before pushing publicly.
- If there is no headless GitHub auth path, stop and ask for a token or remote URL. Do not default to browser automation.
- If the user already supplied a remote URL, skip GitHub API creation and push directly.

## Failure Recovery

- `No origin remote configured`: provide `--remote-url` or create the GitHub repo first.
- `Current branch is ...`: rerun with `--checkout-branch` if the user wants to switch branches.
- Push auth failure over HTTPS: switch to SSH or confirm GitHub credentials.
- Host key verification failure over SSH: perform a one-time SSH handshake and retry.
- Original repo is read-only: create a fork headlessly and push there instead.
- No GitHub API auth available: ask for `GITHUB_PAT`, `GITHUB_TOKEN`, `GH_TOKEN`, `gh auth login`, or a repository URL.
