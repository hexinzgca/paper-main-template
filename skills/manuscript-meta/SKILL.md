---
name: manuscript-meta
description: 为任意 Typst/LaTeX 手稿建立并维护 `.manuscript_meta/` 规范层：术语与缩写、章节组织与意图、学术同义变体、公式符号唯一性、实体到 bib 引用映射、图表与数值主张，以及 grey/green/red/blue/yellow 颜色协作协议。用于手稿写作、改写、审稿回复、术语统一、符号冲突排查、引用审计与颜色审阅。自动生成的条目保持未打勾；只有用户可以把条目改为 `[x]` 固定规范，agent 只能遵从，不能修改或勾选。
---

# Manuscript Meta

## 目的

把手稿中**隐式、易漂移的写作约定**变成可审查的显式清单：

- 名词对象与缩写到底用哪个写法；
- 每一节承担什么论证任务；
- 哪些学术动词/副词是同义变体，哪些应排除；
- 一个公式符号是否被复用于多个含义；
- 一个正文实体短语对应哪些 `@key`；
- 图、表、数值在正文中的唯一写法。

清单位于项目根目录的 `.manuscript_meta/`，按手稿分子目录保存。它不是正文、不是实验记录、不是引用管理器，也不替用户做科学判断。

## 硬契约（不可协商）

1. **只有用户能打勾。** `[x]` 表示用户已固定规范。工具与 agent 不得把 `[ ]` 改为 `[x]`，不得把 `[x]` 改为 `[ ]`。
2. **`[x]` 行只读。** 工具同步、agent 整理、批量替换都不得改写、移动、删除 `[x]` 行。用户手动编辑 `[x]` 行是允许的；下一次 `sync` 仍不会碰它。
3. **自动条目保持 `[ ]`。** 自动生成或自动更新的条目一律未打勾；它们只是候选。
4. **用户改写的条目不能被覆盖。** 用户直接编辑过的 `[ ]` 行会转为 user-owned；`sync` 保留原文，`apply` 拒绝覆盖，除非用户明确要求。
5. **冲突时改正文或报告，不改规范。** 若 `audit` 报“固定规范与正文冲突”，agent 必须修改正文、或向用户报告；不得通过改 `[x]` 行让检查通过。
6. **不伪造事实。** 不在清单里编造引用、数值、公式含义或实验结论；未知就写“待补”并保持 `[ ]`。

## 颜色协作契约（与 `[x]` 同级）

正文颜色是审阅状态机，不是装饰。agent 必须先读颜色，再决定能否改字。

| 颜色 | 状态 | agent 行为 |
|---|---|---|
| grey | 人类未核实 | 可以编辑、移动、重写；编辑后的直接改动标记为 blue |
| green | 人类已核实 | 只读；不得改字、移动、删除或去掉绿色 |
| red | 人类已核实，但含标注/修改意见 | 下一轮必须修改；修改完成后标记为 blue，不能继续留在 red |
| blue | agent 返回的直接修改，人类待审核 | agent 不得再次修改；等待人类接受为 green 或退回 red |
| yellow | agent 的建议/评注 | 直接以 yellow 新增在正文相应位置；不能替换/删改既有原文；人类审核；可以多轮修改 |

### 状态流转

```text
grey --agent直接修改--> blue
red  --agent必须修改--> blue
blue --人类接受------> green
blue --人类要求修改--> red
yellow --人类接受----> green
yellow --人类要求修改--> yellow（可多轮）
green --禁止改动
```

- red 是**人类发出的修改指令**，不是 agent 的待审核标记；agent 下一轮必须处理。
- blue 是**一次性快照**：agent 返回直接修改后，人类审核前不得二次修改。
- yellow 只允许新增建议/评注；必须直接插入正文，不能只写在 `.manuscript_meta`。不能覆盖、替换或删除既有文本。yellow 可以多轮修改，直到人类接受或退回。
- green 表示人类已核实并冻结；不得改字、移动或去色。
- grey 是默认可编辑状态；对既有 grey 文本的直接改写应转为 blue，纯新增建议可用 yellow。

### 颜色实现

- green 使用墨绿色：Typst `rgb("#1B5E20")`，LaTeX `darkgreen`；不要使用亮绿。
- grey 默认使用 `luma(105)`；red/blue/yellow 保留用户已有颜色。
- 颜色作用域可能是 `#set text(fill: ...)` 直到下一次 set，也可能是局部 `#text(fill: ...)[...]`。移动文本时连同颜色包装一起移动；不得重新着色。
- 现有颜色标记是权威状态。agent 不得新增、删除或改色，除非用户明确要求或按上述状态流转执行。
- 若 grey 文本紧邻 green/red/blue/yellow，编辑只限 grey 范围，不重排其他颜色块。
- yellow 建议/评注必须直接增加在正文相应位置；不得把 yellow 当作既有文本的修改标记。

### Yellow 建议直接写入正文

yellow 是正文中的可见建议/评注，不是只存在于 `.meta` 的备注。

- 在需要评注的段落之后直接新增 `#text(fill: rgb("#B8860B"))[...]`；
- 只增加内容，不替换、删除或重写既有文本；
- 可以多轮修改 yellow 内容，等待人类接受或继续修订；

### Red/blue 处理记录（可选）

red 的修改计划、blue 的审核理由可以记录在：

```text
.manuscript_meta/docs/<document>/07-color-review.md
```

该文件只是审阅日志，不是 yellow 建议的替代品。

## 目录

```text
.manuscript_meta/
├── README.md                     # 本目录契约（工具生成）
├── config.json                   # 手稿注册表：路径、格式、活动文档
├── .state/<document>.json        # 行所有权、哈希、排序键
└── docs/<document>/
    ├── 00-terminology.md         # 学术专业词与缩写
    ├── 01-structure.md           # 章节组织与意图
    ├── 02-lexicon.md             # 用词多变性与替换
    ├── 03-symbols.md             # 公式符号唯一性
    ├── 04-citations.md           # 实体短语 → @key
    ├── 05-figures.md             # 图、表、标签
    └── 06-numbers.md             # 数值主张与位置
```

`config.json` 可注册多份手稿；每份手稿有独立的 `docs/<document>/` 与 state。活动文档默认是最近初始化/选择的那一份。

## 行语法

所有列表共用 Markdown checkbox：

```markdown
- [ ] 候选或自动条目 <!-- id:stable-id -->
- [x] 用户已固定的规范 <!-- id:stable-id -->
```

行尾 `<!-- id:... -->` 是稳定标识。用户可以改行内文字；保留 ID 才能继续接收自动更新。删除 ID 等于把该行转为用户私有行，工具不会再覆盖或删除它。

`(x)` 后缀表示**禁用变体**，只作用于术语/用词/符号列表：

```markdown
- [ ] MLIP;LAM: 原子间势/原子基础模型的缩写候选。
- [x] MLIP;LAM(x): 已固定：只用 MLIP，禁止 LAM。
```

函数式记号不是禁用标记：`bold(x)`、`bold(R)`、`cal(F)` 会按原样解析，不会把 `(x)` 当成 ban。禁用写法请写成 `` `Z_j`(x) `` 或 `LAM(x)`。

### 1. 学术专业词（`00-terminology.md`）

```markdown
- [ ] 规范词;可接受变体;禁用变体(x): 中文释义
```

- 第一项是规范词；分号分隔变体；`(x)` 为禁用。
- 顺序是“专业性从高到低”的启发式建议；用户可重排、合并、拆分。
- 一个条目可以列举多项，例如 `MLIP;machine-learned interatomic potential;MLIPs`。
- 自动条目只给出现次数与首次行号；释义与禁用决策由用户固定。
- 自动扫描偏好高置信候选（缩写、标题式短语、技术名词短语），不追求召回全部普通名词。
- **green 优先级**：摘要与 §1–§3 的 green 文本是人类已核实用法；grey 出现的新写法不能反向覆盖 green。两者冲突时改 grey 或报告。

### 2. 章节组织与意图（`01-structure.md`）

```markdown
- [ ] §2.3 标题 | 意图: 这一节在论证链中完成什么 | 标签: section-label
```

- 一行压缩一个标题层级；顺序即正文顺序。
- 意图写“功能/证据/边界”，不要复述整段；目标是一眼能看出该节为何存在。
- 打勾表示该节的组织与意图冻结；新增内容应放进未固定小节，或先报告。
- 自动扫描从标题与首段生成候选；agent 可以把候选压缩成真正的一句话意图（通过工具），但不得改已打勾的行。

### 3. 学术用词多变性（`02-lexicon.md`）

```markdown
- [ ] show;demonstrate;exhibit;reveal: 展示/表明类；同段只选一种。
- [x] significantly;substantially(x): 未做统计检验，禁止用 significantly。
```

- 第一项为首选；`(x)` 为排除项。
- 用于审查动词、副词、连接词的措辞漂移，不是禁止一切同义表达。
- 计数仅作提示；不要为了“看起来一致”而机械替换所有词。
- 自动条目来自内置学术语义族与正文计数；领域特有词由 agent/用户补充。
- **green 优先级**：优先采用摘要与 §1–§3 的实际用法；grey 结果段不能反向改写 green 的用词习惯。

### 4. 公式符号唯一性（`03-symbols.md`）

```markdown
- [ ] `Z;Z_i;Z_j`: 节点核电荷 | 正实数 | 首次 L94
- [x] `M;M_b`: 总偶极矩 | D | 首次 L586
- [x] `cal(M);cal(M)_b`: 自旋多重度 | 无量纲 | 首次 L272
```

- 一个含义一个主写法；同义/冲突写法放同一行或用 `(x)` 标记禁用。
- 必须写出含义；建议写域/单位与首次位置。
- 同一字母承担多个含义时，用两行明确区分，例如 `M`（偶极）与 `cal(M)`（自旋多重度）；不要合并。
- 自动扫描给出规范化符号、变体、次数与首次行号；语义、单位、禁用决策由用户固定。
- 符号写法使用 Typst 规范化形式（`E_tot`、`bold(R)`、`kappa_w`），不要直接粘贴整段数学源码。

### 5. 实体与引用（`04-citations.md`）

```markdown
- [ ] 近5年 MLIP 与等变势基础: @behler2007; @bartok2010; @gilmer2017
```

- 左侧是正文中的名词性实体/主张，右侧是该主张允许的 bib key 集合。
- 同一个 key 可以服务多个实体；一个实体也可以有多个 key。
- 打勾的实体行表示“该主张只能引用这些 key”；`audit` 检查 key 是否存在、是否真的被正文引用。
- 自动扫描按正文引用簇生成候选；实体措辞由 agent/用户压缩。

### 6. 图、表与标签（`05-figures.md`）

```markdown
- [ ] fig:concept — 概念图：电荷测度、有限能量与响应；a/b/c/d 各自承担什么。
```

- 记录 `fig:` / `tab:` 标签与图注意图；无标签图会提示补标签。
- 打勾表示标签、图注意图与引用方式冻结。

### 7. 数值主张（`06-numbers.md`）

```markdown
- [ ] 1.6 meV — T2c1 能量 MAE，600 子集，per atom。
```

- 记录带单位数值及其上下文；用于跨摘要、结果、图注的一致性审查。
- 打勾表示正文必须保留该数值写法；`audit` 会做子串存在性检查。
- 自动条目只摘录，不判断实验来源是否充分。

## 所有权状态

| 状态 | 含义 | `sync` 行为 | `apply` 行为 |
|---|---|---|---|
| `pinned` | `[x]` 用户固定 | 永不改写/移动/删除 | 拒绝修改 |
| `auto` | 工具生成的候选 | 可更新；事实消失时可删除 | 可改写为 curated |
| `curated` | agent 通过工具写的候选 | 保留；不覆盖 | 可更新 |
| `manual` | 用户直接编辑过的行 | 永远保留 | 拒绝覆盖 |

用户直接编辑 `auto` 或 `curated` 行后，下一次 `sync` 会把该行识别为 `manual`。这是保护机制，不是错误。

## 快速开始

在项目根目录运行（脚本随 skill 分发）：

```bash
python3 skills/manuscript-meta/scripts/mmeta.py init
```

`init` 会：

1. 发现候选手稿（`manuscript*.typ`、`paper*.typ`、`src/main.typ`、`main.tex` 等，排除 build/submodules/figures）；
2. 默认选择最近修改的一份，也可用 `--manuscript PATH` 指定；
3. 创建 `.manuscript_meta/`、注册表、七份列表与 state；
4. 立即扫描一次，写入 `[ ]` 自动候选。

常用命令：

```bash
# 刷新自动条目；保留所有 [x]、manual、curated 行
python3 skills/manuscript-meta/scripts/mmeta.py sync

# 只预览
python3 skills/manuscript-meta/scripts/mmeta.py sync --dry-run

# 查看统计
python3 skills/manuscript-meta/scripts/mmeta.py status

# 只打印用户已固定的规范（agent 修改前必读）
python3 skills/manuscript-meta/scripts/mmeta.py norms

# 查看抽取到的事实（标题、引用、图、数值、术语、符号）
python3 skills/manuscript-meta/scripts/mmeta.py scan
python3 skills/manuscript-meta/scripts/mmeta.py scan --json

# 规范审计；有 error 时退出码 1
python3 skills/manuscript-meta/scripts/mmeta.py audit
python3 skills/manuscript-meta/scripts/mmeta.py audit --strict   # warning 也视为失败

# 合并 agent 的语义整理（不碰 [x]/manual）
python3 skills/manuscript-meta/scripts/mmeta.py apply --file overlay.json

# 改单行
python3 skills/manuscript-meta/scripts/mmeta.py set-text \
  --kind terminology --id term-mlip \
  --text "MLIP;machine-learned interatomic potential: 机器学习原子间势。"
```

选择文档：

```bash
--document my-paper             # config.json 中的 id
--document path/to/paper.typ   # 或相对路径
--all                          # sync/audit/status 对全部文档
```

根目录可用 `--root PATH` 覆盖；默认从当前目录向上寻找 `.manuscript_meta`、`.git` 或 `project.json`。

## Agent 修订工作流

### 修改前

1. 运行 `status`，确认活动文档。
2. 运行 `norms`，读所有 `[x]` 行；它们是唯一规范。
3. 检查正文颜色：`grep -n '#text(fill:\|#set text(fill:' <manuscript>`；先按状态机确定 grey/green/red/blue/yellow 边界。
4. 特别检查：
   - 术语：第一项是否规范，哪些变体带 `(x)`；
   - 结构：目标章节是否已固定；意图是否禁止改变论证功能；
   - 用词：目标语义族是否已排除某些变体；
   - 符号：目标符号是否已有唯一含义与写法；
   - 引用：目标实体是否已映射到固定 key 集合。
5. 若用户要求修改已固定章节的组织/意图，先报告冲突；只有用户能改 `[x]`。

### 修改中

- 只直接改 grey；red 下一轮必须修改并转 blue；blue/green 只读；yellow 直接以新增评注写入正文。
- 直接修改 grey 或 red 后标为 blue；不要编辑已有 blue，也不要给 green 改字或挪位。
- 不要直接编辑 `.manuscript_meta` 的 `[x]` 行。
- 新术语/新符号/新引用先按现有规范写；没有规范时，选择与正文最一致的形式，并在修改后用 `sync` 生成候选。
- 不引入 `(x)` 变体；不新增同义符号承担同一含义；不把一个实体的引用扩到未映射 key。
- 不为了通过 `audit` 而修改清单；`audit` 失败时改正文或报告。

### 修改后

```bash
python3 skills/manuscript-meta/scripts/mmeta.py sync
python3 skills/manuscript-meta/scripts/mmeta.py audit
typst compile --root . <manuscript>.typ <output>.pdf
```

并检查颜色块未被误改：

```bash
grep -n '#text(fill:\|#set text(fill:' <manuscript>
```


- `sync` 只更新/新增 `[ ]` 候选；不会碰 `[x]`、manual、curated。
- `audit` 只检查已固定（`[x]`）条目；未固定条目不会阻塞。
- 若有 error：修正文或报告，不要改 `[x]`。
- 若出现新的重要概念，agent 可通过 `apply`/`set-text` 把它整理成 `curated` 候选；仍保持 `[ ]`，等待用户固定。

## `apply` overlay

`apply` 用于 agent 批量整理语义，而不是让 agent 直接改文件。示例：

```json
{
  "terminology": {
    "_clear_auto": true,
    "rows": [
      {"id": "term-mlip", "text": "MLIP;machine-learned interatomic potential: 机器学习原子间势。"}
    ]
  },
  "symbols": {
    "rows": [
      {"id": "sym-e-tot", "text": "`E_tot;E_tot^kappa`: 物理总能量与有限总能量 | 能量 | 首次 L96"}
    ]
  }
}
```

规则：

- `id` 必填且同一列表内唯一；重复 id 会整体拒绝，避免静默覆盖。
- 已存在且为 `auto`/`curated` 的行：更新文字并转为 `curated`。
- 已存在且为 `manual` 或 `[x]`：拒绝。
- 不存在：追加为 `curated`。
- `_clear_auto: true`：只删除 `auto` 行；`manual`、`curated`、`[x]` 全部保留。用于 agent 把自己的自动候选重写为干净的语义组。
- `{"id": "...", "delete": true}`：删除 `auto`/`curated` 行；拒绝删除 `manual`/`[x]`。

整理时优先“合并”而不是“堆叠”：把同一概念的缩写、全称、复数形式放进同一行；把同一字母的不同含义拆成两行并标明冲突。

## `audit` 规则

只对 `[x]` 行报错/警告：

| 检查 | 级别 | 含义 |
|---|---|---|
| `banned-variant` | error | 术语/用词中 `(x)` 变体仍出现在正文 |
| `canonical-missing` | warning | 固定规范词在正文中未出现（可能已改名） |
| `banned-symbol` | error | 固定禁用符号仍出现在公式 |
| `symbol-missing` | warning | 固定符号在公式中未出现（可能已换记号） |
| `cite-missing-bib` | error | 正文或实体映射的 `@key` 不在 bib |
| `cite-mapped-not-used` | error | 已固定实体映射到未在正文引用的 key |
| `outline-missing-section` | error | 已固定章节在正文中不存在 |
| `outline-title-drift` | error | 已固定章节标题被改 |
| `outline-order-drift` | warning | 已固定章节相对顺序变化 |
| `figure-missing` | error | 已固定 `fig:`/`tab:` 标签不存在 |
| `number-missing` | warning | 已固定数值写法在正文中未找到 |
| `cite-unmapped` | warning | 正文有引用但没有任何实体行覆盖 |
| `outline-unmapped` | warning | 正文有标题但组织列表未覆盖 |

`audit` 是**词法检查**，不是语义证明：它不能判断引用是否恰当、符号含义是否正确、数值实验是否可靠。

## 多手稿与多格式

- 一个项目可注册多份手稿；`sync --all` / `audit --all` 批量处理。
- Typst 为首要支持：标题、`#figure`、`#cites`、`@key`、`$...$`、标签。
- LaTeX 提供基础支持：`\section`、`\label`、`\cite`、`$...$`、`figure` 环境；复杂宏包需要人工补充候选。
- 手稿发现排除 `build/`、`submodules/`、`figures*/`、`assets/`、`tests/`、PDF 与辅助文件；不会扫描 skill 自身。
- 多份手稿共享术语库目前不做自动合并；需要时由用户复制条目或后续扩展。

## 自定义列表

新增列表需要同时改脚本与文档：

1. 在 `LIST_SPECS` 增加 `kind/file/title/grammar`；
2. 在 `FILE_HEADERS` 增加表头；
3. 在 `build_desired` 增加事实生成；
4. 在 `primary_key`/`coverage_keys` 增加语义键；
5. 在 `audit_document` 增加检查；
6. 在 `selftest` 增加一条覆盖“新增、更新、保留、审计”的断言。

不要只改 Markdown 文件：下次 `sync` 不认识新列表，会把它当普通文本保留，但不会维护它。

## 自检与故障排查

```bash
python3 skills/manuscript-meta/scripts/mmeta.py selftest
```

自检覆盖：

- `[x]` 行在同步后保持不变；
- 用户改写的 `[ ]` 行不被覆盖；
- 新事实会追加为 `auto`；
- 过时 `auto` 行会删除；
- `sync` 幂等；
- `(x)` 禁用词/符号/引用/章节缺失能被 `audit` 捕获；
- agent 不能改 `[x]` 行。

常见问题：

- **“refusing to overwrite user-owned row”**：该行被用户直接编辑过。不要强改；让用户决定，或用新的 `id` 追加候选。
- **“duplicate ids in overlay”**：overlay 内 id 重复；同一概念请合并成一行，或给不同行不同 id。
- **自动候选太多**：用 `apply` 的 `_clear_auto` 清掉自己的自动候选，再写精简语义行；不要删除 `manual`/`[x]`。
- **`audit` 无 error 但规范仍不对**：`audit` 只检查已固定行；先让用户打勾，或把语义写进 `curated` 行。
- **手稿改名/换版本**：`init --manuscript NEW_PATH` 注册新文档；旧文档保留，避免历史规范丢失。

## 严禁

- 禁止把 `[ ]` 自动改为 `[x]`，或把 `[x]` 改为 `[ ]`。
- 禁止在 `sync`/批量替换中改写、移动、删除 `[x]` 行。
- 禁止覆盖用户直接编辑过的 `[ ]` 行。
- 禁止用修改清单的方式让 `audit` 通过。
- 禁止编造 bib key、数值、符号含义、章节意图或实验结论。
- 禁止把清单内容当作新的科学主张；它只记录写作约定。
- 禁止在未授权时提交、推送或改变仓库历史。
- 禁止改 green 文本的颜色、内容、位置或删除 green 包装。
- 禁止在人类审核前二次修改 blue 文本；blue 只能等待人类接受或退回 red。
- 禁止把 red 当作普通待审核标记；red 表示 agent 下一轮必须修改。
- 禁止用 yellow 替换、删改既有文本；yellow 只能新增正文建议/评注。
- 禁止只把 yellow 建议写在 `.manuscript_meta` 而不进入正文。
