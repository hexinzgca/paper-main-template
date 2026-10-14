# Typst 论文项目模板

论文正文、代码和实验分开维护；论文以 Git submodule 的固定提交记录依赖版本。
这是**起步模板**，没有预置研究结论、实验数据、子模块地址或虚假的复现结果。
项目标题、作者和仓库地址写在 `project.json`，论文入口会自动读取它。

## 快速开始

需要 Python 3.10+、Git 2.28+；编译另需 `.typst-version` 指定的 Typst。
GNU Make 是快捷入口，不是必需依赖。具体安装和 Windows 用法见 [SETUP](docs/SETUP.md)。

```bash
# 在解压后的 paper-main 目录运行，不要在三仓库外层目录 git init。
python3 scripts/manage.py init --name my-paper --title "My Research Paper" --author "Author Name"

git init -b main
git add .
make check
make test
make compile

# 核对正文、元数据、许可选择和检查结果后，再自行创建第一条提交。
git commit -m "meta: initialize paper repository"
```

`make compile` 输出 `build/main.pdf`，不拉取子模块、不运行训练，也不需要真实实验。
模板使用英文占位正文和编译器内置字体；中文正文需要按 SETUP 明确配置字体。
没有安装 Make 时，将 `make check` 换成 `python3 scripts/manage.py check`，
`make compile` 换成 `python3 scripts/manage.py compile`。

## 目录

```text
paper-main/
├── AGENTS.md                  # 唯一的 Agent 维护规范
├── README.md                  # 人类使用入口
├── project.json               # 标题、作者、摘要、仓库元数据
├── .typst-version             # 精确编译器版本
├── src/                       # Typst 正文、章节、参考文献
│   ├── main.typ
│   ├── sections/
│   ├── figs/
│   └── refs.bib
├── assets/                    # 最终图件，不放绘图程序或原始数据
├── docs/                      # 初始化、复现、发布、同步及检查说明
├── config/hooks.json          # 子仓库测试／绘图命令契约
├── scripts/                   # 轻量维护工具，仅依赖 Python 标准库
├── tests/                     # 使用临时 Git 仓库的回归测试
├── submodules/                # 接入后创建 code/、experiments/ 两个 gitlink
├── .github/                   # CI、Issue/PR 模板、Dependabot
├── .gitmodules                # 初始只有注释；没有虚构依赖
├── .gitignore
└── Makefile
```

## 统一命令

| 命令 | 做什么 |
| --- | --- |
| `make compile` | 用固定版本编译正文到 `build/main.pdf`。 |
| `make check` | 检查已暂存／已跟踪文件、gitlink、复现记录、文件大小；不联网。 |
| `make test` | 运行模板维护工具的回归测试，不运行真实研究实验。 |
| `make check-history` | 在 check 之外检查提交历史中的超大 blob；`BASE_REV=<完整SHA>` 可限定范围。 |
| `make submodules` | 检查安全前提后初始化／恢复索引里记录的固定版本。 |
| `make check-dependencies` | 要求已有子模块已初始化并与固定版本一致。 |
| `make code-test` | 执行 `config/hooks.json` 中代码仓库已声明的轻量测试。 |
| `make figures` | 执行实验仓库已声明的绘图命令；输出至 `build/figures/`，不自动覆盖 `assets/`。 |
| `make record-pins REASON="说明"` | 从已暂存的 gitlink 更新复现记录中的 JSON 区块，不自动暂存／提交。 |
| `make manifest` | 提交后生成含真实论文提交号的 `build/provenance.json`。 |
| `make release-manifest` | 额外要求干净工作区和已初始化的依赖；不是发布审批或科学复现证明。 |

`make check` 以**索引**为对象；先审阅并 `git add` 本次修改。它会拒绝未暂存的已跟踪修改，
避免“检查了 A、提交了 B”。未跟踪文件不在普通 check 的内容审查范围内；正式发布要求干净工作区。
不要为通过检查而丢弃他人修改。

## 连接真实代码与实验仓库

随压缩包附带的 `paper-code/`、`paper-experiments/` 是两个**独立仓库的种子**，
不是本目录下的普通代码文件夹。分别初始化、提交并推送后，再按
[SUBMODULES](docs/SUBMODULES.md) 接入。不要复制它们的源码进 `submodules/`。

新增／更新的完整 SHA 必须与 `docs/REPRODUCE.md` 同一提交记录；
不要运行 `git submodule update --remote` 作为更新方式。已生成的旧结果不因更新代码 pin 而自动成为新结果。

## GitHub 使用

把**本目录内容**提交到论文仓库根目录。首次推送后检查 Actions 中的 `Paper CI`。
验证报告不会自动提交回仓库。实际 GitHub 运行结果取决于仓库权限、网络和工具可用性。

希望长期复用时，在 GitHub 仓库设置中将论文仓库标记为模板仓库，之后通过
“Use this template”创建新的论文仓库。此设置不是 ZIP 或 YAML 能自动代替的；详见
[SETUP](docs/SETUP.md)。代码、实验仓库仍独立创建和接入。

普通 PR 只运行无特权论文检查和模板测试。`Dependency checks` 在 main 推送／手动触发时运行；
手动 `Render figures` 工作流仅允许 main，并在未配置真实绘图流程时明确失败为 BLOCKED。
没有配置自动发布、自动提交、自动合并或写权限令牌。

## 复现、协作与许可

复现记录入口：[REPRODUCE](docs/REPRODUCE.md)；图件来源：[ASSETS](docs/ASSETS.md)；
提交和 PR 约定：[CONTRIBUTING](CONTRIBUTING.md)；发布：[RELEASE](docs/RELEASE.md)；
本地同步：[SYNC](docs/SYNC.md)；自动检查边界：[TEMPLATE_STATUS](docs/TEMPLATE_STATUS.md)。

本模板**没有代替作者选择开源许可证**。公开前按 [LICENSING](docs/LICENSING.md) 明确论文、
程序和图件的许可，并添加真实 LICENSE。也没有自动设置仓库所有者、DOI 或引用作者信息。
