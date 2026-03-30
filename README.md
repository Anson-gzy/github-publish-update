# github-publish-update

`github-publish-update` 是一个面向 Codex 的技能（skill），用于把本地项目无浏览器发布到 GitHub，并在后续继续用同一套流程推送更新。

它优先使用 GitHub MCP 创建或确认远程仓库；如果 MCP 不可用，则优先走已登录的 GitHub CLI，并默认配合 HTTPS 远程和 `gh auth setup-git`；再不行才回退到内置的 Python 脚本，通过 GitHub API、环境变量令牌或 `gh auth token` 完成仓库创建、fork、提交和推送。

## 功能亮点

- 首次发布本地文件夹到 GitHub
- 更新已经存在的 GitHub 仓库
- 在需要时自动 `git init`
- 检查 `git status`、`git remote -v` 和 `.gitignore`
- 只暂存指定路径，避免误提交无关改动
- 通过 GitHub API 无浏览器创建仓库或 fork 仓库
- 提供 `--simple` 一键发布模式
- 默认优先使用 HTTPS 远程和 GitHub CLI 凭证助手，减少 SSH 配置问题
- 对 `.env`、大文件、产物目录、模型文件等风险内容做发布前提示

## 目录结构

```text
github-publish-update/
├── SKILL.md
├── README.md
├── agents/
│   └── openai.yaml
├── references/
│   └── workflow.md
└── scripts/
    ├── gh_auth_bootstrap.py
    ├── git_publish_update.py
    └── github_prepare_remote.py
```

## 适用场景

- “把这个项目上传到 GitHub”
- “帮我把当前代码同步到远程仓库”
- “创建一个新的 GitHub 仓库并推送”
- “这个仓库没权限，帮我 fork 后推上去”
- “只提交 `src` 和 `README.md`，别动别的文件”

## 环境要求

- `git`
- `python3`
- 建议安装 `gh`（GitHub CLI）
- 以下认证方式至少一种：
- GitHub MCP
- `GITHUB_PAT` / `GITHUB_TOKEN` / `GH_TOKEN` / `GH_PAT`
- 已登录的 GitHub CLI（`gh auth login`，并能使用 `gh auth token`）

## 安装教程

### 方式一：直接克隆到 Codex skills 目录

把仓库克隆到你的 Codex skills 目录即可：

```bash
git clone <your-repo-url> "$CODEX_HOME/skills/github-publish-update"
```

如果你的环境没有设置 `CODEX_HOME`，常见位置是：

```bash
git clone <your-repo-url> ~/.codex/skills/github-publish-update
```

### 方式二：下载后手动复制

1. 下载这个仓库
2. 把整个 `github-publish-update` 文件夹放到 `~/.codex/skills/`
3. 确认最终路径为：

```text
~/.codex/skills/github-publish-update/SKILL.md
```

### 方式三：开发者本地软链接

如果你希望在本地持续迭代这个 skill，推荐用软链接：

```bash
ln -s /path/to/github-publish-update ~/.codex/skills/github-publish-update
```

这样修改仓库内容后，Codex 侧会直接读取最新版本。

## 使用教程

### 0. 最快方式：一条命令发布

现在推荐的最快用法是：

```bash
python3 scripts/git_publish_update.py /path/to/repo --simple
```

它会自动做这些事：

- 从文件夹名推导 GitHub 仓库名
- 检查 GitHub CLI 是否已登录
- 必要时引导登录
- 运行 `gh auth setup-git`
- 优先使用 HTTPS 远程
- 复用同名远程仓库
- 初始化本地 git 仓库（如果还没有）
- 提交并推送当前改动

### 1. 首次使用先登录 GitHub CLI

推荐先做这一步，后面上传会顺很多：

```bash
brew install gh
```

```bash
python3 scripts/gh_auth_bootstrap.py
```

如果提示还没登录，就执行：

```bash
python3 scripts/gh_auth_bootstrap.py --login --setup-git
```

登录完成后，建议验证一次：

```bash
gh auth status
```

或者直接执行：

```bash
gh auth login --git-protocol https
gh auth setup-git
```

### 2. 在对话中调用 skill

你可以直接对 Codex 说：

```text
用 $github-publish-update 把这个项目发到 GitHub
```

或者：

```text
Use $github-publish-update to publish this repo to GitHub.
```

### 3. skill 的默认工作流程

这个 skill 会优先执行下面的步骤：

1. 检查 `git status --short --branch`
2. 检查 `git remote -v`
3. 检查 `.gitignore`
4. 判断这是首次发布还是后续更新
5. 优先用 GitHub MCP 创建或确认远程仓库
6. 如果 MCP 不可用，则优先走已登录的 GitHub CLI
7. 如果 CLI 不可用，再使用内置脚本走 GitHub API
8. 暂存改动、创建提交、推送到远程
9. 最后输出状态、远程地址和最新提交

### 4. 直接运行脚本

如果你不通过 Codex 调用，也可以直接运行仓库自带脚本。

#### 首次发布一个本地目录

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --init-if-needed \
  --simple
```

#### 推送现有仓库的最新改动

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --message "Update project"
```

#### 只提交指定路径

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --path src \
  --path README.md \
  --message "Update docs and source"
```

#### 把远程切换到新的 GitHub 仓库

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --remote-url https://github.com/user/new-repo.git \
  --change-remote \
  --message "Move to new remote"
```

#### 没有原仓库权限时 fork 后推送

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

## GitHub 认证说明

如果你想用无浏览器方式创建 GitHub 仓库，先设置一个令牌：

```bash
export GITHUB_TOKEN=your_token_here
```

也可以用：

```bash
export GITHUB_PAT=your_token_here
```

脚本会优先尝试以下 GitHub 认证来源：

- `GITHUB_PAT`
- `GITHUB_TOKEN`
- `GH_TOKEN`
- `GH_PAT`
- `gh auth token`

如果你使用 `--simple` 或 `--prefer-gh-cli`，远程仓库的创建和 fork 会优先通过 `gh` CLI 完成。

## 推荐提问方式

下面这些提示词最适合这个 skill：

- “把这个项目上传到 GitHub”
- “帮我创建远程仓库并推送”
- “只提交 `src` 和 `README.md`”
- “如果原仓库没权限，就 fork 一份再推”
- “检查一下这个仓库能不能安全公开发布”

## 安全守则

这个 skill 的设计重点不是“尽快推上去”，而是“安全地推上去”：

- 不会默默覆盖已有 `origin`
- 默认优先推荐 HTTPS 远程和 `gh auth setup-git`
- 只有在你明确需要时才建议改用 SSH
- 会先检查大文件、构建产物、`.env` 和敏感信息
- 如果工作区里有无关改动，应该只暂存你明确指定的路径
- 如果没有可用的 GitHub 认证，不会偷偷切到浏览器自动化，而是明确停下来提示你补令牌或仓库 URL

## 常见问题

### `No GitHub API token available`

说明当前没有可用的 GitHub 认证。优先建议先执行：

```bash
gh auth login --git-protocol https
gh auth setup-git
```

如果你还没有安装 `gh`，先执行：

```bash
brew install gh
```

### `origin already exists and points to a different URL`

说明当前仓库已有 `origin`，而且和你这次要推送的仓库不一致。确认要替换时加上：

```bash
--change-remote
```

### 想强制使用 SSH

如果你的环境明确要求 SSH，可以显式传入：

```bash
python3 scripts/git_publish_update.py /path/to/repo \
  --prefer-gh-cli \
  --gh-login-if-needed \
  --gh-login-protocol ssh \
  --gh-remote-protocol ssh \
  --create-github-repo repo-name
```

## 参考资料

- 技能定义：[SKILL.md](./SKILL.md)
- 决策流程：[references/workflow.md](./references/workflow.md)
- GitHub CLI 登录引导脚本：[scripts/gh_auth_bootstrap.py](./scripts/gh_auth_bootstrap.py)
- 主发布脚本：[scripts/git_publish_update.py](./scripts/git_publish_update.py)
- GitHub 远程准备脚本：[scripts/github_prepare_remote.py](./scripts/github_prepare_remote.py)
