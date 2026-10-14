# 子模块接入与固定版本

## 前提

先在独立目录初始化、审阅并发布 `paper-code` 和 `paper-experiments`，
或使用现有的独立仓库。随包种子提供 `make test`，不包含真实研究算法。
仓库必须已有至少一条提交。保持上游软件独立可运行，不反向读取 paper-main。

审核远程 URL、许可、访问权限及目标上游分支／保留标签。记录你批准的**完整提交号**。
不要将访问令牌写进 URL。模板自动接入检查只允许绝对 HTTPS/SSH URL；
本地文件路径与相对 URL 不属于默认生产配置。

## 首次添加（在 paper-main 根目录，Bash）

先提交现有模板工作；确保子模块目标目录没有需要保留的文件。
`CODE_URL`、`EXPERIMENTS_URL` 和两个完整 SHA 都必须是你实际批准的值。

```bash
(
  set -eu
  : "${CODE_URL:?Set the approved code URL}"
  : "${EXPERIMENTS_URL:?Set the approved experiments URL}"
  : "${CODE_SHA:?Set the approved full code commit hash}"
  : "${EXPERIMENTS_SHA:?Set the approved full experiments commit hash}"
  git submodule add --name code "$CODE_URL" submodules/code
  git submodule add --name experiments "$EXPERIMENTS_URL" submodules/experiments
  test "$(git -C submodules/code rev-parse --verify --end-of-options "$CODE_SHA^{commit}")" = "$CODE_SHA"
  test "$(git -C submodules/experiments rev-parse --verify --end-of-options "$EXPERIMENTS_SHA^{commit}")" = "$EXPERIMENTS_SHA"
  git -C submodules/code checkout --detach "$CODE_SHA"
  git -C submodules/experiments checkout --detach "$EXPERIMENTS_SHA"
  git -C submodules/code submodule update --init --recursive --checkout
  git -C submodules/experiments submodule update --init --recursive --checkout
  git add -- .gitmodules submodules/code submodules/experiments
  python3 scripts/manage.py record-pins --reason "Initial approved code and experiment pins; no research results generated yet"
)
```

审核并补全 `docs/REPRODUCE.md` 中环境、来源和真实实验版本；
确认 `config/hooks.json` 是对应仓库的真实命令后：

```bash
git add -- docs/REPRODUCE.md config/hooks.json
make check-dependencies
make code-test
make compile
git diff --cached --submodule=log
git commit -m "submodule: attach reviewed code and experiment pins"
```

不要把未推送的本地子模块提交写入论文仓库。上述 clone/checkout 成功并不替代
“目标 SHA 已合入批准上游分支／保留标签”的人工审阅。

## 更新固定版本

先在子仓库完成 PR、合并并发布；然后按 `AGENTS.md` 第 4.3 节选择具体 SHA。
确认各级子模块无本地修改、无未发布工作。使用显式 fetch + detached checkout，
再暂存新的 gitlink，运行 `record-pins`，最后把 gitlink 和复现记录一起提交。
更新过程中不要先调用 `make submodules`，它恢复的是索引记录版本而不是你的目标新版本。

## 克隆与恢复

```bash
: "${PAPER_URL:?Set the approved paper repository URL}"
git clone --recurse-submodules "$PAPER_URL" paper-main
cd paper-main
make check-dependencies
```

已有干净 checkout 可运行 `make submodules`。
安全检查发现脏工作区、已初始化依赖版本偏离索引或目标目录有未跟踪文件时会停止，
不会 reset、stash、clean、force-checkout 或自动同步本地 URL 覆盖。

## CI 与私有仓库

默认依赖任务在全新托管 runner 中以索引固定版本执行递归拉取，不使用 `--remote`。
公开依赖不需要额外私密凭据；私有依赖可能无法由论文仓库默认 token 访问。
此时任务必须失败并显示访问问题，不应跳过后宣称成功。

私有仓库访问应由维护者按最小权限配置 GitHub App／只读凭据／适当密钥，
仅用于经过审核的代码和隔离任务。不要在来自 fork 的 PR 中注入这些凭据，
不要使用 `pull_request_target` 执行不可信提交。默认工作流没有预设秘密名称或授权。

## 移除

遵循 `AGENTS.md` 第 4.6 节：保留本地工作，确认上游提交已发布，deinit 后 git rm；
同时更新复现记录和相关命令。不要例行删除 `.git/modules/` 缓存。

技术依据：`https://git-scm.com/docs/git-submodule`，`https://git-scm.com/docs/gitsubmodules`。
