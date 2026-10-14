# 初始化与 GitHub 使用

## 1. 选择目录，而不是把整个压缩包当成一个仓库

外层 `project-template/` 是分发包。`paper-main/` 是论文仓库；
`paper-code/` 和 `paper-experiments/` 是可选的另外两个独立仓库种子。
**不要在外层运行 `git init` 或把三个目录一次性提交成 monorepo。**
仅需要论文时，直接单独使用 `paper-main/` 即可。

## 2. 本地工具

维护工具需要 Python 3.10+ 与 Git 2.28+。所有随包 Python 工具只使用标准库。
编译需要 `.typst-version` 中的精确版本 **0.15.1**；没有自动安装或隐式升级脚本。

从 Typst 官方 releases 下载对应操作系统的编译器，解压并加入 PATH：
`https://github.com/typst/typst/releases/tag/v0.15.1`。
校验来源和平台后安装；模板不携带任何编译器或字体文件。

```bash
python3 --version
git --version
typst --version
```

Windows 可使用 WSL 运行 README 中的 Make 命令；也可直接在 PowerShell 中：

```powershell
py -3 scripts/manage.py init --name my-paper --title "My Paper" --author "Author Name"
git init -b main
git add .
py -3 scripts/manage.py check
py -3 -m unittest discover -s tests -v
py -3 scripts/manage.py compile
```

子模块示例使用 Bash；原生 PowerShell 用户应将环境变量写成 `$env:NAME = "..."`，
或逐行替换参数，不要直接照搬 Bash 的变量检查语法。若使用 `make` 且 Python 命令名为
`python`，可运行 `make PYTHON=python check`。

### 中文正文与字体

默认正文是英文，使用编译器内置字体，不依赖宿主机字体搜索。
中文排版时自行安装具有适当许可的中文字体，记录版本与可获取位置，并在
`src/main.typ` 选择字体、为编译命令增加明确的 `--font-path`。
不要把本机字体文件未经许可提交或发送给他人。CI 也必须以相同方式提供所需字体。

## 3. 初始化论文元数据

```bash
python3 scripts/manage.py init --name my-paper --title "My Research Paper" --author "Author One" --author "Author Two"
```

此命令只修改 `project.json`；重复执行会拒绝覆盖。
之后直接编辑 JSON 即可修改作者、摘要或仓库地址。不会替你改 Git 全局配置，
不会创建 GitHub 仓库或设置组织名称。

## 4. 推送到新建的空 GitHub 仓库

先在 GitHub 创建论文的**空仓库**。不要同时生成另一个 README 或 LICENSE，
以免与本地初始化历史冲突。根据项目要求配置用户身份和权限；然后在 `paper-main/` 中：

```bash
git init -b main
git add .
make check
make test
make compile
git commit -m "meta: initialize paper repository"
# PAPER_URL 设置为你批准的实际 GitHub 论文仓库地址，不要填访问令牌。
: "${PAPER_URL:?Set your approved paper repository URL}"
git remote add origin "$PAPER_URL"
git push -u origin main
```

命令必须逐项成功再继续。编译 BLOCKED 时先解决工具问题，不要描述为 CI 已通过。
如果仓库已存在并已有提交，不要重新初始化、强推或覆盖历史；在该仓库的新分支中有选择地迁移模板。

## 5. 标记为 GitHub 模板仓库

推送并验证后，由具有相应权限的维护者在仓库 Settings 中启用 “Template repository”。
随后使用 “Use this template” 生成新的论文仓库。这个开关不能由 ZIP 文件自行启用。
官方依据：`https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-template-repository`。

通用模板建议保留空 `.gitmodules`。真实代码／实验地址属于具体研究项目，
不要让新建论文无意沿用另一个项目的依赖指针。

## 6. 项目化前最后检查

修改 README 开头的项目介绍和各章节占位正文；确认参考文献；选择许可；
核对 main 分支名称；在实际仓库运行 CI；需要时在 GitHub 设置分支保护／规则集。
仓库规则、密钥、模板开关、组织权限均需真实账户配置，随包 YAML 不代表它们已经设置。
