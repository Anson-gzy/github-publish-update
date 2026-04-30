# github-publish-update

[English](./README.md) | [简体中文](./README.zh-CN.md)

`github-publish-update` is a Codex skill for publishing local projects to GitHub without relying on a browser-first workflow, and for reusing the same flow for future updates.

It prefers GitHub MCP for creating or verifying the remote repository. If MCP is unavailable, it prefers authenticated GitHub CLI with HTTPS remotes and `gh auth setup-git`. If that still is not available, it falls back to the bundled Python scripts using the GitHub API, environment tokens, or `gh auth token`.

## Highlights

- Publish a local folder to GitHub for the first time
- Update an existing GitHub repository
- Run `git init` automatically when needed
- Inspect `git status`, `git remote -v`, and `.gitignore` before publishing
- Stage only selected paths to avoid unrelated changes
- Create repositories or forks headlessly via the GitHub API
- Offer a one-command `--simple` fast path
- Prefer HTTPS remotes plus the GitHub CLI credential helper by default
- Warn about `.env` files, large binaries, build outputs, model files, and other risky content before publishing
- Create bilingual README docs as two separate files: `README.md` for English and `README.zh-CN.md` for Simplified Chinese

## Layout

```text
github-publish-update/
├── SKILL.md
├── README.md
├── README.zh-CN.md
├── agents/
│   └── openai.yaml
├── references/
│   └── workflow.md
└── scripts/
    ├── gh_auth_bootstrap.py
    ├── git_publish_update.py
    └── github_prepare_remote.py
```

## Good Fits

- "Upload this project to GitHub"
- "Sync my current code to a remote repo"
- "Create a new GitHub repository and push it"
- "If I cannot push to the original repo, fork it and push there"
- "Only commit `src` and `README.md`; leave everything else alone"

## Requirements

- `git`
- `python3`
- `gh` (GitHub CLI) is strongly recommended
- At least one authentication path:
- GitHub MCP
- `GITHUB_PAT` / `GITHUB_TOKEN` / `GH_TOKEN` / `GH_PAT`
- Authenticated GitHub CLI (`gh auth login`, with `gh auth token` available)

## Installation

### Option 1: Clone into your Codex skills directory

```bash
git clone <your-repo-url> "$CODEX_HOME/skills/github-publish-update"
```

If `CODEX_HOME` is not set, a common location is:

```bash
git clone <your-repo-url> ~/.codex/skills/github-publish-update
```

### Option 2: Download and copy manually

1. Download this repository.
2. Copy the entire `github-publish-update` folder into `~/.codex/skills/`.
3. Confirm the final path is:

```text
~/.codex/skills/github-publish-update/SKILL.md
```

### Option 3: Use a local symlink while developing

```bash
ln -s /path/to/github-publish-update ~/.codex/skills/github-publish-update
```

That lets Codex pick up the latest local changes directly.

## Usage

### 0. Fastest path: one command

The recommended fast path is:

```bash
python3 scripts/git_publish_update.py /path/to/repo --simple
```

This will automatically:

- infer the GitHub repository name from the folder name
- check whether GitHub CLI is already authenticated
- guide login when needed
- run `gh auth setup-git`
- prefer HTTPS remotes
- reuse an existing repo with the same name when possible
- initialize a git repository if needed
- commit and push current changes

In a healthy setup, you should not need to enter a device code every time. A normal flow is:

1. `gh auth login` once
2. `gh auth setup-git` once
3. Reuse the saved keychain token for later operations

You should only see another device code when:

- the GitHub CLI token has become invalid
- you logged out of `gh`
- you need an additional scope, such as `delete_repo`

### 1. Set up GitHub CLI first

```bash
brew install gh
```

```bash
python3 scripts/gh_auth_bootstrap.py
```

If it reports that you are not logged in:

```bash
python3 scripts/gh_auth_bootstrap.py --login --setup-git
```

If you only need to add an extra scope later, prefer refresh over full login:

```bash
python3 scripts/gh_auth_bootstrap.py \
  --ensure-scope delete_repo \
  --refresh-if-needed
```

Then verify:

```bash
gh auth status
```

You can also run the GitHub CLI commands directly:

```bash
gh auth login --git-protocol https
gh auth setup-git
```

### 2. Invoke the skill in Codex

Examples:

```text
Use $github-publish-update to publish this repo to GitHub.
```

```text
Use $github-publish-update to create a repo and push my latest changes.
```

### 3. Default skill flow

The skill generally does this:

1. Check `git status --short --branch`
2. Check `git remote -v`
3. Inspect `.gitignore`
4. Decide whether this is a first publish or a later update
5. Prefer GitHub MCP to create or confirm the remote
6. Otherwise prefer authenticated GitHub CLI
7. Otherwise fall back to the bundled GitHub API flow
8. Stage changes, create a commit, and push
9. Print the resulting status, remote, and latest commit

### 4. Bilingual README convention

When a project needs Chinese and English documentation, use two separate README files instead of one mixed-language file:

- `README.md`: English
- `README.zh-CN.md`: Simplified Chinese

Both files should put this language switcher directly under the H1 title:

```markdown
[English](./README.md) | [简体中文](./README.zh-CN.md)
```

Keep the two files parallel: same major sections, same commands, same project-specific claims, and same links where applicable. Avoid mixed headings like `Features / 功能`; use English headings in `README.md` and Chinese headings in `README.zh-CN.md`.

### 5. Run the scripts directly

#### Publish a local folder for the first time

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --init-if-needed \
  --simple
```

#### Push updates to an existing repo

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --message "Update project"
```

#### Stage only selected paths

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --path src \
  --path README.md \
  --message "Update docs and source"
```

#### Move to a different remote

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --remote-url https://github.com/user/new-repo.git \
  --change-remote \
  --message "Move to new remote"
```

#### Fork and push when the original repo is not writable

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --prefer-gh-cli \
  --gh-login-if-needed \
  --gh-setup-git \
  --gh-remote-protocol https \
  --fork-github-repo owner/repo \
  --change-remote \
  --message "Push to fork"
```

## Authentication

If you want a no-browser GitHub API path, you can also set a token manually:

```bash
export GITHUB_TOKEN=your_token_here
```

Or:

```bash
export GITHUB_PAT=your_token_here
```

The scripts can use:

- `GITHUB_PAT`
- `GITHUB_TOKEN`
- `GH_TOKEN`
- `GH_PAT`
- `gh auth token`

If you use `--simple` or `--prefer-gh-cli`, repository creation and fork flows will prefer GitHub CLI first.

If you need extra permissions later, use `gh auth refresh` instead of a full re-login whenever possible.

## Suggested Prompts

- "Upload this project to GitHub"
- "Create a GitHub repo and push it"
- "Only commit `src` and `README.md`"
- "If the original repo is read-only, fork it first"
- "Check whether this repo is safe to publish publicly"

## Safety Rules

This skill is designed to publish safely, not just quickly:

- It will not silently replace `origin`
- It prefers HTTPS remotes with `gh auth setup-git` by default
- It only suggests SSH when the user explicitly wants SSH
- It checks for large files, build artifacts, `.env` files, and sensitive data first
- It should stage only requested paths when the working tree contains unrelated changes
- If no headless GitHub auth path is available, it stops and asks for a token or repository URL instead of silently switching to browser automation

## FAQ

### `No GitHub API token available`

Run:

```bash
gh auth login --git-protocol https
gh auth setup-git
```

If `gh` is not installed yet:

```bash
brew install gh
```

### Why am I seeing device codes again?

Usually you should not need them repeatedly.

Check your current GitHub CLI health first:

```bash
python3 scripts/gh_auth_bootstrap.py --setup-git
```

If you only need an extra scope:

```bash
python3 scripts/gh_auth_bootstrap.py \
  --ensure-scope delete_repo \
  --refresh-if-needed
```

That path is faster than doing a full `gh auth login` again.

### `origin already exists and points to a different URL`

The local repository already has an `origin` pointing somewhere else. If you really want to replace it, add:

```bash
--change-remote
```

### I want to force SSH

If your environment explicitly requires SSH:

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --prefer-gh-cli \
  --gh-login-if-needed \
  --gh-login-protocol ssh \
  --gh-remote-protocol ssh \
  --create-github-repo repo-name
```

## References

- Skill definition: [SKILL.md](./SKILL.md)
- Workflow reference: [references/workflow.md](./references/workflow.md)
- GitHub CLI bootstrap helper: [scripts/gh_auth_bootstrap.py](./scripts/gh_auth_bootstrap.py)
- Main publish script: [scripts/git_publish_update.py](./scripts/git_publish_update.py)
- Remote preparation script: [scripts/github_prepare_remote.py](./scripts/github_prepare_remote.py)
