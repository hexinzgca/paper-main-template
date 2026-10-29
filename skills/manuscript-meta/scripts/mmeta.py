#!/usr/bin/env python3
"""mmeta.py -- manuscript metadata ledger for a Typst/LaTeX paper repository.

The tool scans an active manuscript and maintains a set of reviewer-facing
lists under ``.manuscript_meta/``:

  00-terminology.md   technical nouns, acronyms and fixed variants
  01-structure.md     section order and one-line intent
  02-lexicon.md       interchangeable academic verbs / adverbs / connectives
  03-symbols.md       mathematical symbols and their meanings
  04-citations.md     entity phrase -> bibliography key(s)
  05-figures.md       figures / tables / labels
  06-numbers.md       numeric claims and their locations

Only the user may mark a row ``[x]`` (fixed norm).  The tool never changes a
checked row, never checks or unchecks a row, and never overwrites a row that was
edited by hand.  Agent-side curation goes through ``apply`` / ``set-text`` so
that auto-update state stays coherent.

Standard library only.  Python 3.9+.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1
META_NAME = ".manuscript_meta"

LIST_SPECS = [
    {
        "kind": "terminology",
        "file": "00-terminology.md",
        "title": "学术专业词与缩写",
        "grammar": "`规范词;可接受变体;禁用变体(x): 中文释义`；第一项为规范词，`(x)` 为禁用变体；按专业性从高到低排列。",
    },
    {
        "kind": "structure",
        "file": "01-structure.md",
        "title": "文章组织段落与意图",
        "grammar": "`§1.2 标题 | 意图: ... | 标签: ...`；顺序即文章顺序；打勾即冻结该节的组织与意图。",
    },
    {
        "kind": "lexicon",
        "file": "02-lexicon.md",
        "title": "学术用词多变性替换",
        "grammar": "`首选词;变体;禁用变体(x): 语义族说明`；用于审查并排除不合适的同义变体。",
    },
    {
        "kind": "symbols",
        "file": "03-symbols.md",
        "title": "公式符号唯一性",
        "grammar": "`符号;冲突写法(x): 含义 | 域/单位 | 首次位置`；`(x)` 表示禁止再用该写法。",
    },
    {
        "kind": "citations",
        "file": "04-citations.md",
        "title": "对象实体及其引用",
        "grammar": "`实体短语：@key1; @key2`；实体是正文中的名词性主张或对象，右侧是其唯一引用集合。",
    },
    {
        "kind": "figures",
        "file": "05-figures.md",
        "title": "图、表与标签实体",
        "grammar": "`fig:label — 图注主张`；打勾即固定该图/表的标签与叙述意图。",
    },
    {
        "kind": "numbers",
        "file": "06-numbers.md",
        "title": "数值主张与来源",
        "grammar": "`数值 单位 — 主张与位置`；打勾即固定正文采用的数值写法。",
    },
]

FILE_HEADERS = {
    "terminology": """
# 学术专业词与缩写

<!-- managed by manuscript-meta. 只读约定：本工具不会改动 [x] 行，也不会自动打勾。 -->

- 每一行是第一列为规范词的名词对象；`;` 分隔变体，`(x)` 标记禁用变体。
- 自动生成或自动更新的行保持 `[ ]`；用户修改后仍为 `[ ]`，只有用户可改为 `[x]`。
- 行尾 `<!-- id:... -->` 是稳定标识；删除它会让该行变成用户私有行（不再自动更新）。
- 行序为专业性从高到低的建议；打勾的行不因自动同步而移动。
- 优先级：green 模块（摘要 + §1–§3）是人类已核实用法；grey 模块不得反向覆盖 green。
""",
    "structure": """
# 文章组织段落与意图

<!-- managed by manuscript-meta. 只读约定：本工具不会改动 [x] 行，也不会自动打勾。 -->

- 每行压缩一个标题层级：章节编号、标题、写作意图、锚点标签。
- 顺序即正文顺序；打勾表示组织与意图已冻结，后续修改必须遵守。
- 新增章节会以 `[ ]` 候选行出现，等待用户确认。
""",
    "lexicon": """
# 学术用词多变性替换

<!-- managed by manuscript-meta. 只读约定：本工具不会改动 [x] 行，也不会自动打勾。 -->

- 每行一个语义族；第一项为首选词，`(x)` 为明确排除的变体。
- 用于审查“show / exhibit / demonstrate”一类不必要的措辞漂移，而不是禁止所有同义表达。
- 行尾计数仅作审计提示，不作为固定规范。
- 优先级：green 模块（摘要 + §1–§3）是人类已核实用法；grey 模块不得反向覆盖 green。
""",
    "symbols": """
# 公式符号唯一性

<!-- managed by manuscript-meta. 只读约定：本工具不会改动 [x] 行，也不会自动打勾。 -->

- 每行一个符号对象；同一含义只允许一个主写法，`(x)` 标记禁用写法。
- 自动扫描给出出现次数、首次位置与变体；语义和单位由用户固定。
- 符号冲突（同一字母承担多个含义）会以候选行或 `audit` 警告出现。
""",
    "citations": """
# 对象实体及其引用

<!-- managed by manuscript-meta. 只读约定：本工具不会改动 [x] 行，也不会自动打勾。 -->

- 每行从“正文实体短语”映射到一组 `@key`，而不是反过来罗列参考文献。
- 打勾的实体行表示：该主张只能引用这些 key；`audit` 会检查缺失与未引用。
- 同一 key 可服务多个实体；新出现的 key 会自动追加为候选行。
""",
    "figures": """
# 图、表与标签实体

<!-- managed by manuscript-meta. 只读约定：本工具不会改动 [x] 行，也不会自动打勾。 -->

- 每行记录一个 `fig:` / `tab:` 标签及其图注主张。
- 打勾表示标签、图注意图和引用方式已冻结。
- 无标签的图/表也会列出，提示补标签。
""",
    "numbers": """
# 数值主张与来源

<!-- managed by manuscript-meta. 只读约定：本工具不会改动 [x] 行，也不会自动打勾。 -->

- 每行记录一个带单位的数值主张及上下文；用于跨摘要、结果、图注的一致性审查。
- 打勾表示正文必须使用该写法/数值；`audit` 会检查它是否仍出现。
- 自动行只做摘录，不判断实验来源是否充分。
""",
}

STOP_MATH = {
    "lr", "abs", "norm", "frac", "sqrt", "root", "sum", "product", "integral",
    "partial", "nabla", "inf", "lim", "sup", "max", "min", "exp", "log", "ln",
    "sin", "cos", "tan", "erf", "erfc", "det", "dim", "ker", "span", "rank",
    "diag", "median", "mean", "var", "std", "quad", "comma", "dot", "thin",
    "semi", "slash", "times", "plus", "minus", "eq", "gt", "lt", "geq", "leq",
    "neq", "approx", "arrow", "med", "op", "basic", "and", "or", "not", "in",
    "subset", "union", "mapsto", "upright", "italic", "sans", "frak", "hat",
    "tilde", "bar", "overline", "underline", "vec", "mat", "cases", "display",
    "inline", "block", "h", "v", "text", "strong", "emph", "square", "stroked",
    "tiny", "limits", "prime", "compose", "circle", "ast", "star", "checkmark",
    "forall", "exists", "emptyset", "angle", "parallel", "perp", "sim", "propto",
    "left", "right", "big", "Big", "bigl", "bigr", "displaystyle", "operatorname",
    "bb", "em", "arrow", "chevron", "med", "alt", "compose", "circle", "ast",
}

MATH_FUNCS = {
    "bold", "cal", "upright", "italic", "sans", "frak", "hat", "tilde", "bar",
    "overline", "underline", "vec", "sqrt", "abs", "norm", "lr", "text",
}

STOP_ACRONYMS = {
    "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "SI", "ES",
    "AND", "THE", "ALL", "NOT", "FOR", "DOI", "URL", "PDF", "HTML", "CSS",
    "JSON", "YAML", "API", "TODO", "AUTHOR", "COMPLETION", "INSERTION",
    "RESULT", "STATUS", "PENDING", "NOTE", "WARNING", "ERROR", "E3",
}

ACADEMIC_FAMILIES = [
    ("show", ["show", "demonstrate", "exhibit", "reveal", "display", "indicate"], "展示 / 表明"),
    ("propose", ["propose", "present", "introduce", "develop", "formulate", "devise"], "提出 / 构建"),
    ("use", ["use", "employ", "utilize", "adopt", "apply", "leverage"], "使用 / 采用"),
    ("verify", ["verify", "validate", "confirm", "establish", "test", "check"], "验证 / 检验"),
    ("evaluate", ["evaluate", "assess", "measure", "quantify", "estimate"], "评估 / 度量"),
    ("report", ["report", "record", "document", "state", "describe"], "报告 / 记录"),
    ("observe", ["observe", "find", "see", "note", "detect"], "观察 / 发现"),
    ("require", ["require", "need", "demand", "necessitate"], "需要 / 要求"),
    ("allow", ["allow", "enable", "permit", "support", "facilitate"], "允许 / 支持"),
    ("preserve", ["preserve", "maintain", "retain", "keep", "conserve"], "保持 / 守恒"),
    ("generate", ["generate", "produce", "yield", "give", "return"], "产生 / 给出"),
    ("improve", ["improve", "enhance", "increase", "boost", "strengthen"], "改进 / 提升"),
    ("reduce", ["reduce", "decrease", "lower", "diminish", "mitigate"], "降低 / 缓解"),
    ("compare", ["compare", "contrast", "benchmark"], "比较 / 对照"),
    ("ensure", ["ensure", "guarantee", "secure"], "保证 / 确保"),
    ("significantly", ["significantly", "substantially", "markedly", "considerably", "notably"], "显著地"),
    ("consistently", ["consistently", "systematically", "reproducibly", "robustly"], "一致地 / 稳健地"),
    ("accurately", ["accurately", "precisely", "exactly", "quantitatively"], "精确地"),
    ("effectively", ["effectively", "efficiently", "successfully"], "有效地"),
    ("however", ["however", "nevertheless", "nonetheless", "yet", "still"], "转折"),
    ("therefore", ["therefore", "thus", "hence", "consequently", "accordingly"], "因此"),
    ("additionally", ["additionally", "moreover", "furthermore", "besides", "also"], "补充"),
    ("in contrast", ["in contrast", "by contrast", "conversely", "on the contrary"], "对比"),
    ("approximately", ["approximately", "about", "around", "roughly", "nearly"], "约 / 近似"),
]

ROW_RE = re.compile(r"^(\s*)[-*]\s+\[([ xX])\]\s+(.*)$")
ID_RE = re.compile(r"\s*<!--\s*id:([A-Za-z0-9_.:+-]+)\s*-->\s*$")
CITE_CALL_RE = re.compile(r"#cites\s*\(\((.*?)\)\)", re.S)
CITE_LABEL_RE = re.compile(r"#?cite\s*\(\s*label\s*\(\s*\"([^\"]+)\"\s*\)\s*\)")
CITE_ANGLE_RE = re.compile(r"#?cite\s*\(\s*<([^<>]+)>\s*\)")
AT_CITE_RE = re.compile(r"(?<![A-Za-z0-9_@])@([A-Za-z][A-Za-z0-9:_-]*)")
BIB_KEY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")


# ---------------------------------------------------------------------------
# small utilities


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def slugify(value: str, limit: int = 64) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return (value[:limit].strip("-") or "item")


def norm_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def text_hash(value: str) -> str:
    return hashlib.sha256(norm_space(value).encode("utf-8")).hexdigest()[:20]


def blank_match(match: re.Match) -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def mask_regex(text: str, pattern: str, flags: int = 0) -> str:
    return re.sub(pattern, blank_match, text, flags=flags)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, data) -> None:
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def resolve_root(value: str | None) -> Path:
    path = Path(value or os.getcwd()).expanduser().resolve()
    if path.name == META_NAME:
        return path.parent
    for ancestor in [path, *path.parents]:
        if (ancestor / META_NAME).is_dir():
            return ancestor
        if (ancestor / ".git").exists() or (ancestor / "project.json").is_file():
            return ancestor
    return path


def rel_to_root(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        raise SystemExit(f"error: manuscript must live inside the project root: {path}")


# ---------------------------------------------------------------------------
# document discovery / config


def excluded_path(path: Path, root: Path) -> bool:
    parts = set(path.relative_to(root).parts)
    bad = {
        ".git", "build", "dist", "submodules", "node_modules", ".venv", "venv",
        "__pycache__", "tests", "test", "skills", META_NAME, "assets",
    }
    if parts & bad:
        return True
    joined = "/".join(parts).lower()
    if joined.startswith("figures") or "/figures" in joined:
        return True
    if path.suffix.lower() in {".pdf", ".aux", ".log", ".out", ".toc", ".bbl", ".blg"}:
        return True
    return False


def discover_manuscripts(root: Path) -> list[Path]:
    patterns = [
        "manuscript*.typ", "paper*.typ", "main.typ", "src/main.typ",
        "manuscript/*.typ", "manuscripts/*.typ", "paper/*.typ",
        "manuscript*.tex", "paper*.tex", "main.tex", "src/main.tex",
        "manuscript/*.tex", "manuscripts/*.tex", "paper/*.tex",
    ]
    found: dict[Path, None] = {}
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file() and not excluded_path(path, root):
                found[path.resolve()] = None
    if not found:
        # Fallback for projects that do not use conventional manuscript names.
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".typ", ".tex"}:
                continue
            try:
                depth = len(path.relative_to(root).parts) - 1
            except ValueError:
                continue
            if depth > 3 or excluded_path(path, root):
                continue
            found[path.resolve()] = None
    ranked = sorted(
        found,
        key=lambda p: (
            -p.stat().st_mtime,
            len(p.relative_to(root).parts),
            p.name,
        ),
    )
    return ranked


def unique_document_id(path: Path, existing: dict) -> str:
    base = slugify(path.stem)
    candidate = base
    index = 2
    while candidate in existing:
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def load_config(root: Path) -> dict | None:
    return load_json(root / META_NAME / "config.json")


def save_config(root: Path, config: dict) -> None:
    save_json(root / META_NAME / "config.json", config)


def get_document(root: Path, config: dict, selector: str | None, required: bool = True):
    documents = config.get("documents", {})
    if not documents:
        if required:
            raise SystemExit("error: no manuscript registered; run `mmeta.py init` first")
        return None
    if selector:
        if selector in documents:
            return selector, documents[selector]
        normalized = selector.replace("\\", "/")
        for doc_id, doc in documents.items():
            if doc.get("path") == normalized:
                return doc_id, doc
        raise SystemExit(f"error: unknown document: {selector}")
    active = config.get("active")
    if active in documents:
        return active, documents[active]
    doc_id = next(iter(documents))
    return doc_id, documents[doc_id]


def doc_abs_path(root: Path, doc: dict) -> Path:
    return (root / doc["path"]).resolve()


def list_path(root: Path, doc: dict, spec: dict) -> Path:
    return root / META_NAME / doc["list_dir"] / spec["file"]


def state_path(root: Path, doc_id: str) -> Path:
    return root / META_NAME / ".state" / f"{doc_id}.json"


def load_state(root: Path, doc_id: str) -> dict:
    data = load_json(state_path(root, doc_id), None)
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        return {"schema_version": SCHEMA_VERSION, "items": {}, "updated_at": None}
    data.setdefault("items", {})
    return data


def save_state(root: Path, doc_id: str, state: dict) -> None:
    state["schema_version"] = SCHEMA_VERSION
    state["updated_at"] = now_iso()
    save_json(state_path(root, doc_id), state)


def discover_bib_files(root: Path, doc: dict) -> list[Path]:
    recorded = doc.get("bib") or []
    paths: list[Path] = []
    for item in recorded:
        path = (root / item).resolve()
        if path.is_file():
            paths.append(path)
    if not paths:
        for pattern in ["refs.bib", "references.bib", "src/refs.bib", "src/references.bib", "*.bib", "src/*.bib"]:
            for path in root.glob(pattern):
                if path.is_file() and not excluded_path(path, root):
                    paths.append(path.resolve())
    unique = []
    seen = set()
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


# ---------------------------------------------------------------------------
# parsers


def strip_comments(text: str, fmt: str) -> str:
    out = list(text)
    i = 0
    n = len(text)
    in_string = False
    in_block = False
    while i < n:
        c = text[i]
        if in_block:
            if c == "*" and i + 1 < n and text[i + 1] == "/":
                out[i] = out[i + 1] = " "
                i += 2
                in_block = False
            else:
                if c != "\n":
                    out[i] = " "
                i += 1
            continue
        if in_string:
            if c == "\\" and i + 1 < n:
                i += 2
            elif c == '"':
                in_string = False
                i += 1
            else:
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/" and fmt == "typst":
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            out[i] = out[i + 1] = " "
            i += 2
            in_block = True
        elif c == "%" and fmt == "latex":
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif c == '"' and fmt == "typst":
            in_string = True
            i += 1
        else:
            i += 1
    return "".join(out)


def math_spans(text: str, fmt: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    if fmt == "typst":
        i = 0
        while True:
            start = text.find("$", i)
            if start < 0:
                break
            if start > 0 and text[start - 1] == "\\":
                i = start + 1
                continue
            end = text.find("$", start + 1)
            if end < 0:
                break
            spans.append((start, end + 1))
            i = end + 1
        return spans
    patterns = [
        r"\$\$.*?\$\$",
        r"(?<!\\)\$[^$\n]*\$",
        r"\\\[.*?\\\]",
        r"\\\(.*?\\\)",
        r"\\begin\{(equation|align|gather|multline|eqnarray)\*?\}.*?\\end\{\1\*?\}",
    ]
    occupied: list[tuple[int, int]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.S):
            start, end = match.span()
            if any(a <= start < b or a < end <= b for a, b in occupied):
                continue
            occupied.append((start, end))
    return sorted(occupied)


def mask_ranges(text: str, spans: list[tuple[int, int]]) -> str:
    if not spans:
        return text
    chars = list(text)
    for start, end in spans:
        for index in range(start, min(end, len(chars))):
            if chars[index] != "\n":
                chars[index] = " "
    return "".join(chars)


def read_document(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def build_search_text(raw: str, fmt: str) -> str:
    text = strip_comments(raw, fmt)
    text = mask_ranges(text, math_spans(text, fmt))
    text = mask_regex(text, r"<[A-Za-z][A-Za-z0-9:_.-]*>")
    text = mask_regex(text, r"`[^`\n]*`")
    text = mask_regex(text, CITE_CALL_RE.pattern, re.S)
    text = mask_regex(text, CITE_LABEL_RE.pattern)
    text = mask_regex(text, CITE_ANGLE_RE.pattern)
    text = mask_regex(text, r"(?<![A-Za-z0-9_@])@[A-Za-z][A-Za-z0-9:_-]*")
    text = mask_regex(text, r"https?://\S+")
    text = mask_regex(text, r"#(?:import|include|bibliography|show|set|let)\b[^\n]*")
    return text


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def truncate_words(value: str, limit: int) -> str:
    value = norm_space(value)
    if len(value) <= limit:
        return value
    cut = value[:limit]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:") + "…"


def plain_inline(value: str, fmt: str = "typst") -> str:
    value = strip_comments(value, fmt)
    value = re.sub(r"#(?:emph|strong|italic|bold|upright)\s*\[([^\]]*)\]", r"\1", value)
    value = re.sub(r"#(?:xref|ref|cite|eqref)\s*\([^)]*\)", " ", value)
    value = mask_regex(value, CITE_CALL_RE.pattern, re.S)
    value = re.sub(r"<[A-Za-z][A-Za-z0-9:_.-]*>", " ", value)
    value = re.sub(r"\\(emph|textbf|textit|mathrm|text)\{([^{}]*)\}", r"\2", value)
    value = mask_ranges(value, math_spans(value, fmt))
    value = re.sub(r"[*_#]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def extract_headings(raw: str, fmt: str) -> list[dict]:
    text = mask_ranges(strip_comments(raw, fmt), math_spans(raw, fmt))
    headings: list[dict] = []
    if fmt == "typst":
        in_fence = False
        for index, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            match = re.match(r"^(=+)\s+(.*?)\s*$", line)
            if not match:
                continue
            level = len(match.group(1))
            title = re.sub(r"<[^<>]+>\s*$", "", match.group(2)).strip()
            title = plain_inline(title, fmt) or title
            headings.append({"level": level, "title": title, "line": index})
    else:
        levels = {
            "part": 1, "chapter": 1, "section": 1, "subsection": 2,
            "subsubsection": 3, "paragraph": 4,
        }
        for match in re.finditer(
            r"\\(part|chapter|section|subsection|subsubsection|paragraph)\*?\s*\{([^{}]*)\}",
            text,
        ):
            headings.append({
                "level": levels.get(match.group(1), 1),
                "title": plain_inline(match.group(2), fmt),
                "line": line_of(text, match.start()),
            })
    counters = [0] * 8
    for heading in headings:
        level = max(1, min(7, heading["level"]))
        counters[level - 1] += 1
        for deeper in range(level, 8):
            counters[deeper] = 0
        heading["number"] = ".".join(str(counters[i]) for i in range(level))
    return headings


def extract_labels(text: str, fmt: str) -> list[dict]:
    masked = mask_ranges(strip_comments(text, fmt), math_spans(text, fmt))
    labels = []
    if fmt == "typst":
        pattern = r"(?<![A-Za-z0-9_<])<([A-Za-z][A-Za-z0-9:_.-]*)>(?=\s|$|[.,;)\]])"
    else:
        pattern = r"\\label\{([^}]+)\}"
    for match in re.finditer(pattern, masked):
        labels.append({"label": match.group(1), "line": line_of(masked, match.start())})
    return labels


def extract_citations(raw: str, fmt: str, bib_keys: set[str]) -> list[dict]:
    text = strip_comments(raw, fmt)
    citations: list[dict] = []
    seen_calls: set[tuple[str, int]] = set()

    def context_before(pos: int, limit: int = 110) -> str:
        chunk = text[max(0, pos - 700):pos]
        chunk = re.sub(CITE_CALL_RE.pattern, " ", chunk, flags=re.S)
        chunk = re.sub(r"#(?:xref|ref|eqref)\s*\([^)]*\)", " ", chunk)
        chunk = re.sub(r"<[A-Za-z][A-Za-z0-9:_.-]*>", " ", chunk)
        parts = re.split(r"(?<=[.!?])\s+|\n+", chunk)
        sentence = parts[-1] if parts else ""
        sentence = plain_inline(sentence, fmt)
        if len(sentence) > limit:
            sentence = sentence[-limit:]
            if " " in sentence:
                sentence = sentence.split(" ", 1)[1]
        return sentence.strip(" ,;:")

    if fmt == "typst":
        for match in CITE_CALL_RE.finditer(text):
            keys = re.findall(r"\"([^\"]+)\"", match.group(1))
            if not keys:
                continue
            key = (",".join(keys), match.start())
            if key in seen_calls:
                continue
            seen_calls.add(key)
            citations.append({
                "keys": keys,
                "line": line_of(text, match.start()),
                "context": context_before(match.start()),
                "pos": match.start(),
            })
        for match in CITE_LABEL_RE.finditer(text):
            citations.append({
                "keys": [match.group(1)],
                "line": line_of(text, match.start()),
                "context": context_before(match.start()),
                "pos": match.start(),
            })
        for match in CITE_ANGLE_RE.finditer(text):
            citations.append({
                "keys": [match.group(1)],
                "line": line_of(text, match.start()),
                "context": context_before(match.start()),
                "pos": match.start(),
            })
        # Bare @key citations; mask strings first so imports/e-mails are ignored.
        strings_masked = mask_regex(text, r'"(?:\\.|[^"\\])*"')
        for match in AT_CITE_RE.finditer(strings_masked):
            key = match.group(1)
            if key in {"preview"}:
                continue
            if key not in bib_keys and not re.search(r"\d", key):
                continue
            citations.append({
                "keys": [key],
                "line": line_of(strings_masked, match.start()),
                "context": context_before(match.start()),
                "pos": match.start(),
            })
    else:
        for match in re.finditer(r"\\cite[a-zA-Z]*\*?\s*\{([^{}]+)\}", text):
            keys = [part.strip() for part in match.group(1).split(",") if part.strip()]
            citations.append({
                "keys": keys,
                "line": line_of(text, match.start()),
                "context": context_before(match.start()),
                "pos": match.start(),
            })
        for match in AT_CITE_RE.finditer(text):
            citations.append({
                "keys": [match.group(1)],
                "line": line_of(text, match.start()),
                "context": context_before(match.start()),
                "pos": match.start(),
            })
    citations.sort(key=lambda item: item["pos"])
    return citations


def balanced_group(text: str, start: int, opener: str = "(", closer: str = ")") -> int:
    depth = 0
    index = start
    in_string = False
    while index < len(text):
        char = text[index]
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return len(text) - 1


def extract_figures(raw: str, fmt: str) -> list[dict]:
    text = strip_comments(raw, fmt)
    figures: list[dict] = []
    if fmt == "typst":
        for match in re.finditer(r"#(figure|table)\s*\(", text):
            open_index = text.find("(", match.start())
            end = balanced_group(text, open_index)
            block_end = end + 1
            tail_match = re.match(
                r"\s*<([A-Za-z][A-Za-z0-9:_.-]*)>", text[end + 1:end + 160]
            )
            if tail_match:
                block_end = end + 1 + tail_match.end()
            block = text[match.start():block_end]
            caption = ""
            caption_match = re.search(r"caption\s*:\s*\[", block)
            if caption_match:
                bracket = block.find("[", caption_match.start())
                close = balanced_group(block, bracket, "[", "]")
                caption = plain_inline(block[bracket + 1:close], fmt)
            label = ""
            labels = re.findall(r"<([A-Za-z][A-Za-z0-9:_.-]*)>", block)
            if labels:
                label = labels[-1]
            images = re.findall(r'image\s*\(\s*"([^"]+)"', block)
            figures.append({
                "kind": match.group(1),
                "label": label,
                "caption": caption,
                "image": images[0] if images else "",
                "line": line_of(text, match.start()),
            })
    else:
        for match in re.finditer(r"\\begin\{(figure|table)\*?\}(.*?)\\end\{\1\*?\}", text, re.S):
            block = match.group(2)
            caption_match = re.search(r"\\caption\{([^{}]*)\}", block)
            label_match = re.search(r"\\label\{([^}]+)\}", block)
            figures.append({
                "kind": match.group(1),
                "label": label_match.group(1) if label_match else "",
                "caption": plain_inline(caption_match.group(1), fmt) if caption_match else "",
                "image": "",
                "line": line_of(text, match.start()),
            })
    return figures


def extract_bib_keys(paths: list[Path]) -> set[str]:
    keys: set[str] = set()
    for path in paths:
        text = read_document(path)
        keys.update(BIB_KEY_RE.findall(text))
    return keys


def extract_numbers(raw: str, fmt: str) -> list[dict]:
    search = build_search_text(raw, fmt)
    pattern = re.compile(
        r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*"
        r"(meV|eV|mV|kV|V|Å|nm|fs|ps|ns|K|bar|GPa|kcal/mol|D|%|million|g\s*cm|e)"
        r"(?![A-Za-z])"
    )
    results = []
    seen = set()
    for match in pattern.finditer(search):
        line_start = search.rfind("\n", 0, match.start()) + 1
        line_end = search.find("\n", match.end())
        line_end = len(search) if line_end < 0 else line_end
        line_text = search[line_start:line_end]
        if re.search(r"#(?:show|set|let)|par\(|width:|size:|align:|stroke:|inset:|radius:", line_text):
            continue
        value = match.group(1)
        unit = norm_space(match.group(2))
        key = f"{value} {unit}"
        if key in seen:
            continue
        seen.add(key)
        prefix = search[max(0, match.start() - 420):match.start()]
        suffix = search[match.end():match.end() + 100]
        prefix = re.split(r"(?<=[.!?])\s+", prefix)[-1]
        if len(prefix) > 120:
            prefix = prefix[-120:]
            if " " in prefix:
                prefix = prefix.split(" ", 1)[1]
        context = plain_inline((prefix + match.group(0) + suffix), fmt)
        context = truncate_words(context, 140)
        results.append({
            "value": value,
            "unit": unit,
            "key": key,
            "line": line_of(search, match.start()),
            "context": context,
        })
    return results


LEAD_STOP = {
    "the", "a", "an", "this", "these", "those", "that", "which", "whose",
    "of", "on", "in", "with", "from", "to", "for", "and", "or", "by", "as",
    "at", "into", "onto", "over", "under", "between", "among", "within",
    "most", "modern", "such", "only", "also", "both", "each", "every", "some",
    "we", "our", "their", "its", "it", "they", "here", "there", "then",
    "using", "employ", "employs", "furnish", "furnishes", "include", "includes",
    "provide", "provides", "give", "gives", "show", "shows", "remain", "remains",
    "become", "becomes", "make", "makes", "allow", "allows", "require",
    "requires", "need", "needs", "is", "are", "was", "were", "be", "been",
    "can", "may", "might", "must", "should", "will", "would", "has", "have",
    "had", "do", "does", "did", "not", "no", "all", "any", "more", "less",
    "same", "such", "other", "another", "own",
}

VERB_START = {
    "employ", "furnish", "include", "provide", "give", "show", "remain",
    "become", "make", "allow", "require", "need", "use", "using", "adopt",
    "introduce", "propose", "present", "develop", "observe", "report",
    "evaluate", "verify", "validate", "compare", "improve", "reduce",
}


def clean_phrase(surface: str) -> str:
    words = norm_space(surface).split()
    while words and re.sub(r"[^A-Za-z0-9-]", "", words[0]).lower() in LEAD_STOP:
        words.pop(0)
    if not words:
        return ""
    first = re.sub(r"[^A-Za-z0-9-]", "", words[0])
    if not first or len(first) == 1 or first.lower() in VERB_START:
        return ""
    if any(word.lower() in {"we", "our", "their", "its", "it", "they"} for word in words):
        return ""
    if len(words) > 6:
        return ""
    return " ".join(words)


def extract_terms(raw: str, fmt: str) -> list[dict]:
    search = build_search_text(raw, fmt)
    counts: dict[str, dict] = {}

    def add(surface: str, pos: int, score_bonus: float = 0.0, expansion: str = ""):
        line_start = search.rfind("\n", 0, pos) + 1
        line_end = search.find("\n", pos)
        line_end = len(search) if line_end < 0 else line_end
        line_text = search[line_start:line_end]
        if re.search(r"\b(names?|emails?|affiliations?|institutions?|authors?|keywords?|title)\s*:", line_text, re.I):
            return
        display = clean_phrase(surface)
        if not display:
            return
        if not display or len(display) < 2:
            return
        key = display.lower()
        item = counts.get(key)
        if item is None:
            counts[key] = {
                "display": display,
                "count": 1,
                "first": pos,
                "expansion": expansion,
                "bonus": score_bonus,
            }
        else:
            item["count"] += 1
            if expansion and not item["expansion"]:
                item["expansion"] = expansion
            item["bonus"] = max(item["bonus"], score_bonus)

    expansions: dict[str, str] = {}
    for match in re.finditer(
        r"\b([A-Z][A-Za-z0-9-]+(?:[ \t]+(?:[A-Z][A-Za-z0-9-]+|of|for|and|the)){0,6})[ \t]*"
        r"\(([A-Z][A-Z0-9]{1,7})s?\)",
        search,
    ):
        acronym = match.group(2)
        expansion = clean_phrase(match.group(1))
        if expansion and 2 <= len(expansion.split()) <= 9:
            expansions.setdefault(acronym, expansion)

    for match in re.finditer(r"\b([A-Z][A-Z0-9]{1,7})s?\b", search):
        acronym = match.group(1)
        if acronym in STOP_ACRONYMS:
            continue
        expansion = expansions.get(acronym, "")
        surface = f"{acronym};{expansion}" if expansion else acronym
        add(surface, match.start(), score_bonus=4.0, expansion=expansion)

    for match in re.finditer(
        r"\b([A-Z][a-z]+(?:[- ][A-Z][a-z]+){1,4})\b", search
    ):
        add(match.group(1), match.start(), score_bonus=2.5)

    technical_heads = (
        r"potential|model|network|descriptor|representation|symmetry|kernel|"
        r"energy|density|functional|framework|approximation|field|charge|"
        r"manifold|measure|operator|estimator|benchmark|ensemble|trajectory"
    )
    for match in re.finditer(
        rf"\b((?:[a-z][a-z-]*[ \t]+){{0,3}}(?:{technical_heads})s?)\b", search, re.I
    ):
        phrase = match.group(1)
        if len(phrase.split()) >= 2:
            add(phrase, match.start(), score_bonus=1.0)

    items = []
    for key, item in counts.items():
        display = item["display"]
        if re.search(r"\b(academy|university|institute|laborator(y|ies)|college|department|school)\b", display, re.I):
            continue
        if item["count"] < 2 and item["bonus"] < 1.0:
            continue
        if len(item["display"].split()) == 1 and item["display"][0].islower():
            continue
        if item["bonus"] <= 1.0 and item["count"] < 2:
            continue
        if re.search(
            r"\b(and|or|of|in|on|with|from|to|for|by|as|into|over|under|"
            r"between|among|within|separating|versus|via)\b",
            item["display"], re.I,
        ):
            continue
        if re.search(
            r"\b(fig|figure|table|eq|equation|section|appendix|supporting|information|"
            r"author|completion|leaves?|appears?|remains?|becomes?|gives?|shows?|"
            r"includes?|provides?|makes?)\b",
            item["display"], re.I,
        ):
            continue
        if item["count"] == 1 and re.fullmatch(r"[A-Z][a-z]+(?:[ ][A-Z][a-z]+)+", item["display"]):
            continue
        words = display.replace(";", " ").split()
        score = (
            item["bonus"]
            + 1.2 * len(words)
            + (2.0 if any(ch.isdigit() for ch in display) else 0.0)
            + (1.0 if "-" in display else 0.0)
            + 0.4 * min(item["count"], 10)
        )
        if re.search(r"\b(potential|model|network|energy|method|framework)\b", display, re.I):
            score -= 1.2
        items.append({
            "canonical": display,
            "count": item["count"],
            "line": line_of(search, item["first"]),
            "score": score,
            "expansion": item["expansion"],
        })
    items.sort(key=lambda row: (-row["score"], -row["count"], row["canonical"].lower()))
    return items[:70]


def normalize_script(content: str) -> str:
    content = content.strip()
    if content.startswith("(") and content.endswith(")"):
        content = content[1:-1]
    content = re.sub(r"\b(upright|italic|bold|cal|sans)\s*\(([^()]*)\)", r"\2", content)
    content = content.replace('"', "")
    content = re.sub(r"\bcomma\b", ",", content)
    content = re.sub(r"\bplus\b", "+", content)
    content = re.sub(r"\bminus\b", "-", content)
    content = re.sub(r"\s*,\s*", ",", content)
    content = re.sub(r"\s+", "", content)
    return content


INDEX_SUBS = {
    "i", "j", "k", "l", "a", "b", "s", "p", "t", "m", "n", "x", "y", "z",
    "i,j", "i,j,k", "s,i,a", "i,alpha", "i,m", "n,n", "b,i", "s,p",
}


def extract_symbols(raw: str, fmt: str) -> list[dict]:
    text = strip_comments(raw, fmt)
    spans = math_spans(text, fmt)
    clusters: dict[str, dict] = {}

    def read_identifier(source: str, index: int) -> tuple[str, int]:
        match = re.match(r"[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z]+)*", source[index:])
        if not match:
            return "", index
        return match.group(0), index + len(match.group(0))

    def read_script(source: str, index: int) -> tuple[str, int]:
        while index < len(source) and source[index] in "_^":
            marker = source[index]
            index += 1
            while index < len(source) and source[index].isspace():
                index += 1
            if index >= len(source):
                return marker, index
            char = source[index]
            if char in "({[":
                close_char = {"(": ")", "{": "}", "[": "]"}[char]
                end = balanced_group(source, index, char, close_char)
                content = source[index + 1:end]
                index = end + 1
            elif char == '"':
                end = source.find('"', index + 1)
                if end < 0:
                    end = len(source) - 1
                content = source[index + 1:end]
                index = end + 1
            else:
                ident, new_index = read_identifier(source, index)
                if ident:
                    content = ident
                    index = new_index
                else:
                    content = char
                    index += 1
            return marker + normalize_script(content), index
        return "", index

    for start, end in spans:
        body = text[start + 1:end - 1]
        index = 0
        while index < len(body):
            char = body[index]
            if char == '"':
                index += 1
                while index < len(body) and body[index] != '"':
                    index += 2 if body[index] == "\\" else 1
                index += 1
                continue
            if char.isalpha():
                ident, new_index = read_identifier(body, index)
                index = new_index
                if ident in STOP_MATH or ident.split(".")[0] in STOP_MATH:
                    continue
                head = ident
                if ident in MATH_FUNCS and index < len(body):
                    probe = index
                    while probe < len(body) and body[probe].isspace():
                        probe += 1
                    if probe < len(body) and body[probe] == "(":
                        close = balanced_group(body, probe)
                        head = f"{ident}({body[probe + 1:close]})"
                        index = close + 1
                scripts = ""
                while index < len(body) and body[index] in "_^":
                    script, index = read_script(body, index)
                    scripts += script
                canonical = head + scripts
                base = head
                sub = ""
                sub_match = re.match(r"_([^^]+)", scripts)
                if sub_match:
                    sub = sub_match.group(1)
                    if not (sub in INDEX_SUBS or re.fullmatch(r"[a-z][a-z,]*", sub) and sub in INDEX_SUBS):
                        base = head + "_" + sub
                key = base
                item = clusters.get(key)
                if item is None:
                    clusters[key] = {
                        "canonical": base,
                        "display": canonical,
                        "count": 1,
                        "first": start,
                        "variants": {canonical},
                        "variant_counts": {canonical: 1},
                    }
                else:
                    item["count"] += 1
                    item["variants"].add(canonical)
                    item["variant_counts"][canonical] = item["variant_counts"].get(canonical, 0) + 1
                continue
            index += 1

    items = []
    for key, item in clusters.items():
        if item["canonical"] in {"i", "j", "k", "l", "a", "b", "s", "p", "n", "m", "t"}:
            continue
        variants = sorted(item["variants"])
        items.append({
            "canonical": item["canonical"],
            "count": item["count"],
            "line": line_of(text, item["first"]),
            "variants": variants,
            "variant_counts": item["variant_counts"],
            "display": item["display"],
        })
    items.sort(key=lambda row: (row["line"], row["canonical"]))
    return items


def extract_lexicon(raw: str, fmt: str) -> list[dict]:
    search = build_search_text(raw, fmt)
    rows = []
    for canonical, variants, gloss in ACADEMIC_FAMILIES:
        counts = {}
        for variant in variants:
            pattern = r"(?<![A-Za-z])" + re.escape(variant) + r"(?:s|es|ed|ing)?(?![A-Za-z])"
            count = len(re.findall(pattern, search, re.I))
            if count:
                counts[variant] = count
        if not counts or sum(counts.values()) < 2:
            continue
        parts = [canonical] + [v for v in variants if v != canonical]
        rows.append({
            "canonical": canonical,
            "variants": parts,
            "counts": counts,
            "total": sum(counts.values()),
            "gloss": gloss,
        })
    rows.sort(key=lambda row: -row["total"])
    return rows


# ---------------------------------------------------------------------------
# facts / desired rows


@dataclass
class Facts:
    headings: list[dict]
    labels: list[dict]
    citations: list[dict]
    figures: list[dict]
    numbers: list[dict]
    terms: list[dict]
    symbols: list[dict]
    lexicon: list[dict]
    bib_keys: set[str]
    search_text: str
    raw: str
    fmt: str


def gather_facts(root: Path, doc: dict) -> Facts:
    path = doc_abs_path(root, doc)
    raw = read_document(path)
    fmt = doc.get("format", "typst")
    bib_keys = extract_bib_keys(discover_bib_files(root, doc))
    return Facts(
        headings=extract_headings(raw, fmt),
        labels=extract_labels(raw, fmt),
        citations=extract_citations(raw, fmt, bib_keys),
        figures=extract_figures(raw, fmt),
        numbers=extract_numbers(raw, fmt),
        terms=extract_terms(raw, fmt),
        symbols=extract_symbols(raw, fmt),
        lexicon=extract_lexicon(raw, fmt),
        bib_keys=bib_keys,
        search_text=build_search_text(raw, fmt),
        raw=raw,
        fmt=fmt,
    )


@dataclass
class Desired:
    id: str
    text: str
    key: tuple = field(default_factory=tuple)


def make_id(prefix: str, value: str, used: set[str]) -> str:
    base = f"{prefix}-{slugify(value)}"
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}-{index}"
        index += 1
    used.add(candidate)
    return candidate


def build_desired(facts: Facts) -> dict[str, list[Desired]]:
    used: dict[str, set[str]] = {spec["kind"]: set() for spec in LIST_SPECS}
    desired: dict[str, list[Desired]] = {}

    terms = []
    for item in facts.terms[:45]:
        parts = item["canonical"].split(";")
        first = parts[0].strip()
        detail = f"自动候选，出现 {item['count']} 次（首次 L{item['line']}）；待补释义并固定变体。"
        terms.append(Desired(
            id=make_id("term", first, used["terminology"]),
            text=f"{item['canonical']}: {detail}",
            key=(first.lower(),),
        ))
    desired["terminology"] = terms

    structure = []
    for heading in facts.headings:
        body = heading["title"]
        intent = ""
        # Seed the intent from the first prose sentence after the heading.
        raw_lines = facts.raw.splitlines()
        if heading["line"] < len(raw_lines):
            for line in raw_lines[heading["line"]:heading["line"] + 8]:
                if re.match(r"^\s*=+", line):
                    continue
                cleaned = plain_inline(line, facts.fmt)
                if len(cleaned) > 40:
                    intent = truncate_words(cleaned, 150)
                    break
        if not intent:
            intent = "待补写本节意图。"
        label = ""
        nearby = [
            candidate for candidate in facts.labels
            if heading["line"] <= candidate["line"] <= heading["line"] + 3
        ]
        nearby.sort(key=lambda candidate: (
            0 if candidate["label"].startswith(("eq:", "fig:", "tab:")) else 1,
            candidate["line"],
        ))
        if nearby:
            label = nearby[0]["label"]
        structure.append(Desired(
            id=make_id("sec", heading["number"], used["structure"]),
            text=f"§{heading['number']} {body} | 意图: {intent} | 标签: {label or '-'}",
            key=tuple(int(part) for part in heading["number"].split(".")),
        ))
    desired["structure"] = structure

    lexicon = []
    for row in facts.lexicon:
        counts = "，".join(f"{key}×{value}" for key, value in row["counts"].items())
        text = f"{';'.join(row['variants'])}: {row['gloss']}（{counts}）"
        lexicon.append(Desired(
            id=make_id("lex", row["canonical"], used["lexicon"]),
            text=text,
            key=(row["canonical"].lower(),),
        ))
    desired["lexicon"] = lexicon

    symbols = []
    frequent_symbols = [item for item in facts.symbols if item["count"] >= 3]
    frequent_symbols.sort(key=lambda item: (-item["count"], item["line"]))
    for item in frequent_symbols[:40]:
        variants = [v for v in item["variants"] if v != item["canonical"]]
        variant_text = f"；变体：{', '.join('`' + v + '`' for v in variants[:8])}" if variants else ""
        text = (
            f"`{item['canonical']}`: 自动候选，出现 {item['count']} 次"
            f"（首次 L{item['line']}）{variant_text}；待补语义、域与单位。"
        )
        symbols.append(Desired(
            id=make_id("sym", item["canonical"], used["symbols"]),
            text=text,
            key=(item["canonical"].lower(),),
        ))
    desired["symbols"] = symbols

    citations = []
    for call in facts.citations:
        keys = [key for key in call["keys"] if key]
        if not keys:
            continue
        context = call["context"] or f"L{call['line']} 引用"
        text = f"{context}: " + "; ".join(f"@{key}" for key in keys)
        citations.append(Desired(
            id=make_id("cite", context[:50] + "-" + keys[0], used["citations"]),
            text=text,
            key=tuple(keys),
        ))
    desired["citations"] = citations

    figures = []
    for index, item in enumerate(facts.figures, start=1):
        label = item["label"] or f"(unlabelled-{index})"
        caption = item["caption"] or "待补图注主张。"
        figures.append(Desired(
            id=make_id("fig", label, used["figures"]),
            text=f"{label} — {caption[:150]}",
            key=(label,),
        ))
    desired["figures"] = figures

    numbers = []
    for item in facts.numbers:
        numbers.append(Desired(
            id=make_id("num", f"{item['value']}-{item['unit']}-{item['line']}", used["numbers"]),
            text=f"{item['value']} {item['unit']} — {item['context'][:120]}",
            key=(item["key"],),
        ))
    desired["numbers"] = numbers

    return desired


# ---------------------------------------------------------------------------
# row parsing / coverage


def parse_row(line: str) -> dict | None:
    match = ROW_RE.match(line)
    if not match:
        return None
    text = match.group(3).strip()
    item_id = ""
    id_match = ID_RE.search(text)
    if id_match:
        item_id = id_match.group(1)
        text = text[:id_match.start()].rstrip()
    return {
        "indent": match.group(1),
        "checked": match.group(2).lower() == "x",
        "text": text,
        "id": item_id,
    }


def format_row(text: str, checked: bool = False, indent: str = "", item_id: str = "") -> str:
    box = "x" if checked else " "
    suffix = f" <!-- id:{item_id} -->" if item_id else ""
    return f"{indent}- [{box}] {text}{suffix}"


def marker_strip(value: str) -> tuple[str, bool]:
    value = value.strip().replace("`", "").strip()
    # Function-style notation such as bold(x), bold(R), cal(F) is not a
    # banned-variant marker; only a bare term followed by (x) is.
    if re.fullmatch(
        r"(?:bold|cal|italic|sans|frak|hat|tilde|bar|vec|upright|lr)\(.+\)",
        value,
    ):
        return value, False
    match = re.search(r"\s*[（(]\s*[xX×]\s*[)）]\s*$", value)
    if match:
        return value[:match.start()].strip(), True
    return value, False


def split_variants(text: str) -> list[str]:
    head = text.split(":", 1)[0]
    return [part for part in (piece.strip() for piece in head.split(";")) if part]


def coverage_keys(kind: str, text: str) -> set:
    keys: set = set()
    if kind in {"terminology", "lexicon", "symbols"}:
        for variant in split_variants(text):
            value, _ = marker_strip(variant)
            value = value.strip().strip("`").lower()
            if value:
                keys.add((value,))
        return keys
    return {primary_key(kind, text)}


def primary_key(kind: str, text: str) -> tuple:
    if kind in {"terminology", "lexicon"}:
        variants = split_variants(text)
        if variants:
            return (marker_strip(variants[0])[0].lower(),)
    elif kind == "symbols":
        variants = split_variants(text)
        if variants:
            return (marker_strip(variants[0])[0].lower(),)
    elif kind == "citations":
        return tuple(re.findall(r"@([A-Za-z][A-Za-z0-9:_-]*)", text))
    elif kind == "structure":
        match = re.match(r"§\s*([0-9]+(?:\.[0-9]+)*)", text)
        if match:
            return tuple(int(part) for part in match.group(1).split("."))
    elif kind == "figures":
        match = re.match(r"\s*(?:`)?((?:fig|tab|eq):[A-Za-z0-9:_.-]+)", text)
        if match:
            return (match.group(1),)
        match = re.search(r"\((unlabelled-\d+)\)", text)
        if match:
            return (match.group(1),)
    elif kind == "numbers":
        match = re.match(
            r"\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*"
            r"([A-Za-z%Å]+(?:\s+[A-Za-z%Å]+)*)", text,
        )
        if match:
            return (norm_space(match.group(1) + " " + match.group(2)),)
    return (norm_space(text.split(":", 1)[0]).lower(),)


# ---------------------------------------------------------------------------
# sync


def sync_list(
    path: Path,
    kind: str,
    desired: list[Desired],
    state_items: dict,
    dry_run: bool = False,
    prune: bool = True,
) -> dict:
    if path.exists():
        original = path.read_text(encoding="utf-8")
    else:
        original = ""

    # Existing rows (line indices) and semantic coverage from every row.
    rows_by_line: dict[int, dict] = {}
    covered_keys: set = set()
    covered_cite_keys: set[str] = set()
    auto_ids: set[str] = set()
    for index, line in enumerate(original.splitlines()):
        parsed = parse_row(line)
        if not parsed:
            continue
        parsed["line"] = index
        row_id = parsed["id"]
        state = state_items.get(row_id) if row_id else None
        if parsed["checked"]:
            ownership = "pinned"
        elif state:
            ownership = state.get("owned", "auto")
            if ownership in {"auto", "curated"} and state.get("hash") != text_hash(parsed["text"]):
                ownership = "manual"
        else:
            ownership = "manual"
        parsed["owned"] = ownership
        rows_by_line[index] = parsed

        # A manual/curated/pinned row owns its semantic key: suppress a
        # duplicate auto row.  Auto rows do not suppress the desired fact,
        # otherwise they could never be refreshed.
        if ownership != "auto":
            if kind == "citations":
                covered_cite_keys.update(primary_key(kind, parsed["text"]))
            else:
                covered_keys.update(coverage_keys(kind, parsed["text"]))

    # Filter desired facts already covered by manual/curated/pinned rows (or by
    # any semantically equivalent row), so curated content is not duplicated.
    filtered: list[Desired] = []
    for item in desired:
        if kind == "citations":
            remaining = [key for key in item.key if key not in covered_cite_keys]
            if not remaining:
                continue
            if len(remaining) != len(item.key):
                keys = remaining
                item = Desired(
                    id=item.id,
                    text=item.text.split(":", 1)[0] + ": " + "; ".join(f"@{key}" for key in keys),
                    key=tuple(keys),
                )
            filtered.append(item)
        else:
            if item.key in covered_keys:
                continue
            filtered.append(item)
    desired = filtered

    desired_by_id = {item.id: item for item in desired}
    actions = {"added": 0, "updated": 0, "removed": 0, "preserved": 0}
    output: list[tuple[int | None, int, str]] = []  # (insert-before line index or None, order, text)

    # Order output: preserve non-row lines and mutate rows in place.
    updates: dict[int, str] = {}
    removals: set[int] = set()
    consumed: set[str] = set()

    for index, parsed in rows_by_line.items():
        row_id = parsed["id"]
        if parsed["owned"] == "pinned":
            actions["preserved"] += 1
            continue
        if parsed["owned"] in {"manual", "curated"}:
            if row_id:
                consumed.add(row_id)
            actions["preserved"] += 1
            continue
        # owned == auto
        if row_id and row_id in desired_by_id:
            item = desired_by_id[row_id]
            consumed.add(row_id)
            auto_ids.add(row_id)
            if norm_space(item.text) != norm_space(parsed["text"]):
                updates[index] = format_row(item.text, False, parsed["indent"], row_id)
                actions["updated"] += 1
            else:
                actions["preserved"] += 1
        elif prune:
            removals.add(index)
            actions["removed"] += 1
        else:
            actions["preserved"] += 1

    new_rows: list[tuple[int | None, Desired]] = []
    for item in desired:
        if item.id in consumed:
            continue
        insert_at = None
        if kind == "structure":
            for index in sorted(rows_by_line):
                parsed = rows_by_line[index]
                if parsed["checked"]:
                    continue
                existing_key = primary_key(kind, parsed["text"])
                if existing_key and existing_key > item.key:
                    insert_at = index
                    break
        new_rows.append((insert_at, item))
        auto_ids.add(item.id)
        actions["added"] += 1

    # Build final text.
    lines = original.splitlines()
    if not lines:
        lines = []
    result: list[str] = []
    insert_map: dict[int, list[str]] = {}
    for insert_at, item in new_rows:
        row_text = format_row(item.text, False, "", item.id)
        if insert_at is None:
            insert_map.setdefault(len(lines), []).append(row_text)
        else:
            insert_map.setdefault(insert_at, []).append(row_text)

    for index, line in enumerate(lines):
        for row_text in insert_map.get(index, []):
            result.append(row_text)
        if index in removals:
            continue
        result.append(updates.get(index, line))
    for row_text in insert_map.get(len(lines), []):
        result.append(row_text)

    new_text = "\n".join(result)
    if original.endswith("\n") or not original:
        new_text += "\n"

    if not dry_run and new_text != original:
        atomic_write(path, new_text)

    # Update state for all known rows.
    if not dry_run:
        # Remove stale ids that no longer occur.
        live_ids = set()
        for line in result:
            parsed = parse_row(line)
            if parsed and parsed["id"]:
                live_ids.add(parsed["id"])
        for old_id in list(state_items):
            if old_id not in live_ids:
                state_items.pop(old_id, None)
        for line in result:
            parsed = parse_row(line)
            if not parsed or not parsed["id"]:
                continue
            row_id = parsed["id"]
            if parsed["checked"]:
                owned = "pinned"
            elif row_id in auto_ids:
                owned = "auto"
            else:
                previous = state_items.get(row_id, {})
                owned = previous.get("owned", "manual")
                if owned in {"pinned", "auto"}:
                    owned = "manual"
            state_items[row_id] = {
                "hash": text_hash(parsed["text"]),
                "owned": owned,
                "key": list(primary_key(kind, parsed["text"])),
            }

    return actions


def run_sync(root: Path, doc_id: str, doc: dict, dry_run: bool = False, prune: bool = True, quiet: bool = False) -> dict:
    facts = gather_facts(root, doc)
    desired = build_desired(facts)
    state = load_state(root, doc_id)
    state_items_all = state.setdefault("items", {})
    totals = {kind: {"added": 0, "updated": 0, "removed": 0, "preserved": 0} for kind in desired}

    for spec in LIST_SPECS:
        kind = spec["kind"]
        path = list_path(root, doc, spec)
        if not path.exists():
            header = FILE_HEADERS[kind].strip() + "\n\n"
            if not dry_run:
                atomic_write(path, header)
        kind_state = state_items_all.setdefault(kind, {})
        actions = sync_list(path, kind, desired[kind], kind_state, dry_run=dry_run, prune=prune)
        totals[kind] = actions

    if not dry_run:
        doc["updated_at"] = now_iso()
        save_state(root, doc_id, state)
    if not quiet:
        print(f"sync {doc_id} ({doc['path']}){' [dry-run]' if dry_run else ''}")
        for spec in LIST_SPECS:
            actions = totals[spec["kind"]]
            print(
                f"  {spec['file']:<20} +{actions['added']:<3} "
                f"~{actions['updated']:<3} -{actions['removed']:<3} "
                f"={actions['preserved']:<3}"
            )
    return totals


# ---------------------------------------------------------------------------
# apply / set-text


def find_row_by_id(path: Path, row_id: str) -> tuple[int, dict] | None:
    if not path.exists():
        return None
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        parsed = parse_row(line)
        if parsed and parsed["id"] == row_id:
            return index, parsed
    return None


def overlay_entries(payload):
    if not payload:
        return []
    entries = payload.get("rows", []) if isinstance(payload, dict) else payload
    if isinstance(entries, dict):
        entries = [{"id": key, "text": value} for key, value in entries.items()]
    return entries


def apply_overlay(root: Path, doc_id: str, doc: dict, overlay: dict) -> int:
    # Validate every payload before touching any file.
    failures = 0
    for spec in LIST_SPECS:
        payload = overlay.get(spec["kind"])
        if not payload:
            continue
        entries = overlay_entries(payload)
        ids = [str(entry.get("id", "")).strip() for entry in entries if isinstance(entry, dict)]
        ids = [item for item in ids if item]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            print(f"error: duplicate ids in overlay for {spec['kind']}: {', '.join(duplicates)}", file=sys.stderr)
            failures += len(duplicates)
    if failures:
        return failures

    state = load_state(root, doc_id)
    state_items_all = state.setdefault("items", {})

    for spec in LIST_SPECS:
        kind = spec["kind"]
        payload = overlay.get(kind)
        if not payload:
            continue

        # Backwards-compatible forms: {"id": "text"} or {"rows": [...], "_clear_auto": true}
        clear_auto = bool(payload.get("_clear_auto")) if isinstance(payload, dict) else False
        entries = overlay_entries(payload)

        path = list_path(root, doc, spec)
        if not path.exists():
            atomic_write(path, FILE_HEADERS[kind].strip() + "\n\n")
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        rows = {index: parse_row(line) for index, line in enumerate(lines)}
        rows = {index: row for index, row in rows.items() if row}
        state_kind = state_items_all.setdefault(kind, {})

        if clear_auto:
            keep = []
            for index, line in enumerate(lines):
                row = rows.get(index)
                if row:
                    st = state_kind.get(row["id"], {})
                    if row["checked"] or st.get("owned") in {"manual", "curated", "pinned"}:
                        keep.append((index, line))
                    else:
                        state_kind.pop(row["id"], None)
            # Remove auto rows by rebuilding; keep insert positions unchanged otherwise.
            new_lines = []
            for index, line in enumerate(lines):
                row = rows.get(index)
                if row and (index, line) not in keep:
                    continue
                new_lines.append(line)
            lines = new_lines
            rows = {index: parse_row(line) for index, line in enumerate(lines)}
            rows = {index: row for index, row in rows.items() if row}

        for entry in entries:
            if isinstance(entry, str):
                continue
            row_id = str(entry.get("id", "")).strip()
            if not row_id:
                print(f"error: apply entry without id in {kind}", file=sys.stderr)
                failures += 1
                continue
            if entry.get("delete"):
                found = next(((i, r) for i, r in rows.items() if r["id"] == row_id), None)
                if not found:
                    continue
                index, row = found
                st = state_kind.get(row_id, {})
                if row["checked"] or st.get("owned") in {"manual", "pinned"}:
                    print(f"error: refusing to delete user-owned row {row_id}", file=sys.stderr)
                    failures += 1
                    continue
                lines.pop(index)
                state_kind.pop(row_id, None)
                rows = {i: parse_row(line) for i, line in enumerate(lines)}
                rows = {i: row for i, row in rows.items() if row}
                continue

            new_text = str(entry.get("text", "")).strip()
            if not new_text:
                continue
            found = next(((i, r) for i, r in rows.items() if r["id"] == row_id), None)
            if found:
                index, row = found
                if row["checked"]:
                    print(f"error: refusing to modify checked row {row_id}", file=sys.stderr)
                    failures += 1
                    continue
                st = state_kind.get(row_id, {})
                if st.get("owned") == "manual" or (
                    st.get("owned") in {"auto", "curated"}
                    and st.get("hash") != text_hash(row["text"])
                ):
                    print(f"error: refusing to overwrite user-owned row {row_id}", file=sys.stderr)
                    failures += 1
                    continue
                lines[index] = format_row(new_text, False, row["indent"], row_id)
                rows[index] = parse_row(lines[index])
                state_kind[row_id] = {
                    "hash": text_hash(new_text),
                    "owned": "curated",
                    "key": list(primary_key(kind, new_text)),
                }
            else:
                # Insert a new curated row. Outline rows go in numbered order.
                new_line = format_row(new_text, False, "", row_id)
                insert_at = len(lines)
                if kind == "structure":
                    key = primary_key(kind, new_text)
                    for index in sorted(rows):
                        if rows[index]["checked"]:
                            continue
                        if primary_key(kind, rows[index]["text"]) > key:
                            insert_at = index
                            break
                lines.insert(insert_at, new_line)
                state_kind[row_id] = {
                    "hash": text_hash(new_text),
                    "owned": "curated",
                    "key": list(primary_key(kind, new_text)),
                }
                rows = {i: parse_row(line) for i, line in enumerate(lines)}
                rows = {i: row for i, row in rows.items() if row}

        atomic_write(path, "\n".join(lines) + "\n")

    if failures:
        return failures
    doc["updated_at"] = now_iso()
    save_state(root, doc_id, state)
    return 0


def set_text(root: Path, doc_id: str, doc: dict, kind: str, row_id: str, text: str) -> int:
    return apply_overlay(root, doc_id, doc, {kind: {"rows": [{"id": row_id, "text": text}]}})


# ---------------------------------------------------------------------------
# audit


@dataclass
class Finding:
    level: str  # error / warning / info
    code: str
    message: str


def variant_pattern(term: str) -> str:
    escaped = re.escape(term.strip().strip("`"))
    escaped = escaped.replace(r"\ ", r"\s+")
    return r"(?<![A-Za-z0-9])" + escaped + r"(?:s|es)?(?![A-Za-z0-9])"


def count_pattern(search_text: str, term: str, case_sensitive: bool = False) -> int:
    term = term.strip().strip("`")
    if not term:
        return 0
    flags = 0 if case_sensitive else re.I
    return len(re.findall(variant_pattern(term), search_text, flags))


def count_unembedded(search_text: str, value: str, longer_variants: list[str]) -> int:
    """Count a banned variant except where it is part of a longer allowed variant.

    Example: banning "sample efficiency" must not flag the canonical
    "structural sample efficiency".
    """
    total = count_pattern(search_text, value)
    if total == 0:
        return 0
    body = variant_pattern(value)
    for other in longer_variants:
        other = other.strip().strip("`")
        if not other or other.lower() == value.lower():
            continue
        if other.lower().endswith(value.lower()):
            prefix = other[:len(other) - len(value)]
            if prefix:
                pattern = r"(?<!" + re.escape(prefix) + r")" + body
                total = min(total, len(re.findall(pattern, search_text, re.I)))
        elif other.lower().startswith(value.lower()):
            suffix = other[len(value):]
            if suffix:
                pattern = body + r"(?!" + re.escape(suffix) + r")"
                total = min(total, len(re.findall(pattern, search_text, re.I)))
    return max(0, total)


def audit_document(root: Path, doc_id: str, doc: dict, strict: bool = False) -> list[Finding]:
    facts = gather_facts(root, doc)
    findings: list[Finding] = []
    symbol_counts: dict[str, int] = {}
    for symbol_item in facts.symbols:
        for variant, count in symbol_item.get("variant_counts", {}).items():
            symbol_counts[variant] = symbol_counts.get(variant, 0) + count
    cited_keys = {key for call in facts.citations for key in call["keys"]}
    heading_by_number = {heading["number"]: heading for heading in facts.headings}
    heading_order = {heading["number"]: index for index, heading in enumerate(facts.headings)}
    label_names = {item["label"] for item in facts.labels}
    figure_labels = {item["label"] for item in facts.figures if item["label"]}

    for missing in sorted(cited_keys - facts.bib_keys):
        findings.append(Finding("error", "cite-missing-bib", f"正文引用 @{missing} 在 refs.bib 中不存在"))

    covered_cite_keys: set[str] = set()
    previous_outline_index = -1

    for spec in LIST_SPECS:
        kind = spec["kind"]
        path = list_path(root, doc, spec)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            row = parse_row(line)
            if not row:
                continue
            if kind == "citations":
                covered_cite_keys.update(primary_key(kind, row["text"]))
            if not row["checked"]:
                continue
            text = row["text"]

            if kind in {"terminology", "lexicon"}:
                variants = split_variants(text)
                parsed_variants = [marker_strip(variant) for variant in variants]
                allowed_values = [value for value, banned in parsed_variants if value and not banned]
                for position, (value, banned) in enumerate(parsed_variants):
                    if not value:
                        continue
                    count = count_pattern(facts.search_text, value)
                    if banned:
                        count = count_unembedded(facts.search_text, value, allowed_values)
                        if count:
                            findings.append(Finding(
                                "error", "banned-variant",
                                f"{spec['file']}: 禁用变体 `{value}` 仍出现 {count} 次",
                            ))
                    elif position == 0 and count == 0:
                        findings.append(Finding(
                            "warning", "canonical-missing",
                            f"{spec['file']}: 规范词 `{value}` 在正文中未出现",
                        ))

            elif kind == "symbols":
                variants = split_variants(text)
                for position, variant in enumerate(variants):
                    value, banned = marker_strip(variant)
                    if not value:
                        continue
                    count = symbol_counts.get(value.strip().strip("`"), 0)
                    if banned and count:
                        findings.append(Finding(
                            "error", "banned-symbol",
                            f"{spec['file']}: 禁用符号 `{value}` 仍出现 {count} 次",
                        ))
                    elif position == 0 and count == 0:
                        findings.append(Finding(
                            "warning", "symbol-missing",
                            f"{spec['file']}: 规范符号 `{value}` 在公式中未出现",
                        ))

            elif kind == "citations":
                keys = re.findall(r"@([A-Za-z][A-Za-z0-9:_-]*)", text)
                if not keys:
                    findings.append(Finding("warning", "citation-row-empty", f"{spec['file']}: 实体行没有 @key"))
                for key in keys:
                    if key not in facts.bib_keys:
                        findings.append(Finding(
                            "error", "cite-missing-bib",
                            f"{spec['file']}: 实体映射的 @{key} 不在 bib 中",
                        ))
                    elif key not in cited_keys:
                        findings.append(Finding(
                            "error", "cite-mapped-not-used",
                            f"{spec['file']}: 实体映射的 @{key} 未在正文引用",
                        ))

            elif kind == "structure":
                match = re.match(r"§\s*([0-9]+(?:\.[0-9]+)*)\s+(.*?)(?:\s*\||$)", text)
                if not match:
                    findings.append(Finding("warning", "outline-unparsed", f"{spec['file']}: 无法解析章节行: {text[:60]}"))
                    continue
                number = match.group(1)
                title = norm_space(match.group(2))
                heading = heading_by_number.get(number)
                if not heading:
                    findings.append(Finding(
                        "error", "outline-missing-section",
                        f"{spec['file']}: 已固定章节 §{number} 在正文中不存在",
                    ))
                    continue
                if title and norm_space(heading["title"]).lower() != title.lower():
                    findings.append(Finding(
                        "error", "outline-title-drift",
                        f"{spec['file']}: §{number} 标题已偏离固定值 `{title}` → `{heading['title']}`",
                    ))
                index = heading_order.get(number, -1)
                if index < previous_outline_index:
                    findings.append(Finding(
                        "warning", "outline-order-drift",
                        f"{spec['file']}: §{number} 在正文中的顺序早于上一固定章节",
                    ))
                previous_outline_index = max(previous_outline_index, index)

            elif kind == "figures":
                key = primary_key(kind, text)
                label = key[0] if key else ""
                if label.startswith("fig:") and label not in label_names:
                    findings.append(Finding(
                        "error", "figure-missing",
                        f"{spec['file']}: 已固定图标签 `{label}` 不存在",
                    ))

            elif kind == "numbers":
                match = re.match(
                    r"\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*"
                    r"([A-Za-z%Å]+(?:\s+[A-Za-z%Å]+)*)", text,
                )
                if match:
                    needle = match.group(1)
                    unit = match.group(2)
                    pattern = re.escape(needle) + r"\s*" + re.escape(unit)
                    if not re.search(pattern, facts.raw):
                        findings.append(Finding(
                            "warning", "number-missing",
                            f"{spec['file']}: 已固定数值 `{needle} {unit}` 未在正文出现",
                        ))

    for key in sorted(cited_keys - covered_cite_keys):
        findings.append(Finding("warning", "cite-unmapped", f"正文引用 @{key} 未出现在任何实体行"))

    outline_numbers = set()
    for spec in LIST_SPECS:
        if spec["kind"] != "structure":
            continue
        path = list_path(root, doc, spec)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                row = parse_row(line)
                if row:
                    key = primary_key("structure", row["text"])
                    if key:
                        outline_numbers.add(".".join(str(part) for part in key))
    for heading in facts.headings:
        if heading["number"] not in outline_numbers:
            findings.append(Finding(
                "warning", "outline-unmapped",
                f"章节 §{heading['number']} {heading['title']} 未出现在组织列表",
            ))

    if strict:
        findings = [
            Finding("error", item.code, item.message) if item.level == "warning" else item
            for item in findings
        ]
    return findings


# ---------------------------------------------------------------------------
# status / scan / selftest


def print_status(root: Path, config: dict, selector: str | None) -> int:
    doc_id, doc = get_document(root, config, selector)
    state = load_state(root, doc_id)
    print(f"document: {doc_id}  path: {doc['path']}  format: {doc.get('format', 'typst')}")
    print(f"{'list':<22} {'total':>6} {'pinned':>7} {'auto':>6} {'curated':>8} {'manual':>7}")
    for spec in LIST_SPECS:
        path = list_path(root, doc, spec)
        counts = {"total": 0, "pinned": 0, "auto": 0, "curated": 0, "manual": 0}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                row = parse_row(line)
                if not row:
                    continue
                counts["total"] += 1
                if row["checked"]:
                    counts["pinned"] += 1
                    continue
                owned = state.get("items", {}).get(spec["kind"], {}).get(row["id"], {}).get("owned", "manual")
                if owned not in counts:
                    owned = "manual"
                counts[owned] += 1
        print(
            f"{spec['file']:<22} {counts['total']:>6} {counts['pinned']:>7} "
            f"{counts['auto']:>6} {counts['curated']:>8} {counts['manual']:>7}"
        )
    return 0


def print_scan(root: Path, config: dict, selector: str | None, as_json: bool) -> int:
    doc_id, doc = get_document(root, config, selector)
    facts = gather_facts(root, doc)
    payload = {
        "document": doc_id,
        "path": doc["path"],
        "headings": facts.headings,
        "citations": [{"keys": c["keys"], "line": c["line"], "context": c["context"]} for c in facts.citations],
        "figures": facts.figures,
        "numbers": facts.numbers,
        "terms": facts.terms,
        "symbols": facts.symbols,
        "lexicon": facts.lexicon,
        "bib_keys": sorted(facts.bib_keys),
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"document: {doc_id} ({doc['path']})")
    print(f"headings: {len(facts.headings)}  citations: {len(facts.citations)}  "
          f"figures: {len(facts.figures)}  numbers: {len(facts.numbers)}")
    print("\nTop terms:")
    for item in facts.terms[:12]:
        print(f"  {item['count']:>3}  {item['canonical']}  (L{item['line']})")
    print("\nTop symbols:")
    for item in facts.symbols[:12]:
        print(f"  {item['count']:>3}  {item['canonical']}  (L{item['line']})")
    return 0


def selftest() -> int:
    checks = 0
    with tempfile.TemporaryDirectory(prefix="mmeta-selftest-") as tmp:
        root = Path(tmp)
        (root / "paper.typ").write_text(
            "= Introduction\n<introduction>\n"
            "Machine-learned interatomic potentials (MLIPs) show good accuracy.\n"
            "A second sentence about machine-learned interatomic potentials.\n"
            "#cites((\"key1\", \"key2\",))\n"
            "$ E_(\"tot\") = Z_i + Z_j $ <eq:energy>\n"
            "#figure(image(\"f.svg\"), caption: [Test figure.]) <fig:test>\n"
            "The value 12 meV is reported.\n"
            "= Methods\n<methods>\nWe evaluate the MLIP and demonstrate the result.\n",
            encoding="utf-8",
        )
        (root / "refs.bib").write_text(
            "@article{key1, title={A}}\n@article{key2, title={B}}\n", encoding="utf-8"
        )
        config = {
            "schema_version": SCHEMA_VERSION,
            "active": "paper",
            "documents": {
                "paper": {
                    "path": "paper.typ",
                    "format": "typst",
                    "list_dir": "docs/paper",
                    "bib": ["refs.bib"],
                }
            },
        }
        (root / META_NAME).mkdir()
        save_config(root, config)
        (root / META_NAME / "docs/paper").mkdir(parents=True)
        for spec in LIST_SPECS:
            atomic_write(root / META_NAME / "docs/paper" / spec["file"], FILE_HEADERS[spec["kind"]].strip() + "\n\n")
        save_state(root, "paper", {"schema_version": SCHEMA_VERSION, "items": {}})

        doc = config["documents"]["paper"]
        run_sync(root, "paper", doc, quiet=True)
        checks += 1

        term_path = list_path(root, doc, LIST_SPECS[0])
        lines = term_path.read_text(encoding="utf-8").splitlines()
        mlip_line = next(line for line in lines if "MLIP" in line and "<!-- id:" in line)
        mlip_id = re.search(r"id:([A-Za-z0-9_.:+-]+)", mlip_line).group(1)

        # Agent curation uses the tool, keeping the row auto/curated.
        assert apply_overlay(root, "paper", doc, {"terminology": {"rows": [{"id": mlip_id, "text": "MLIP;machine-learned interatomic potential: 测试规范词。"}]}}) == 0
        checks += 1

        # User edits a curated row and checks another row.
        cur = term_path.read_text(encoding="utf-8")
        cur = cur.replace("MLIP;machine-learned interatomic potential: 测试规范词。", "MLIP;QMLIP: 用户改写的规范。")
        other_id = re.search(r"- \[ \] .*?id:([A-Za-z0-9_.:+-]+)", cur).group(1)
        cur = cur.replace(f"- [ ] ", "- [x] ", 1)
        term_path.write_text(cur, encoding="utf-8")
        checks += 1

        # Manuscript changes: add a new term/citation so sync has work to do.
        (root / "paper.typ").write_text(
            (root / "paper.typ").read_text(encoding="utf-8")
            + "\n= Results\nA new descriptor appears. A new descriptor is measured. #cites((\"key2\",))\n",
            encoding="utf-8",
        )
        run_sync(root, "paper", doc, quiet=True)

        after = term_path.read_text(encoding="utf-8")
        assert "- [x] " in after, "checked row was lost"
        assert "MLIP;QMLIP: 用户改写的规范。" in after, "manual edit was overwritten"
        assert "new descriptor" in after.lower(), "new term was not added"
        checks += 1

        findings = audit_document(root, "paper", doc)
        assert not any(f.level == "error" for f in findings), findings
        checks += 1

        # Idempotent sync.
        before = {spec["file"]: list_path(root, doc, spec).read_text(encoding="utf-8") for spec in LIST_SPECS}
        run_sync(root, "paper", doc, quiet=True)
        after_files = {spec["file"]: list_path(root, doc, spec).read_text(encoding="utf-8") for spec in LIST_SPECS}
        assert before == after_files, "sync is not idempotent"
        checks += 1

        # Checked rows are normative: audit must catch forbidden variants,
        # symbols, citations and missing sections, and agents cannot edit them.
        assert marker_strip("LAM(x)") == ("LAM", True)
        assert marker_strip("bold(x)") == ("bold(x)", False)
        checks += 1

        specs = {spec["kind"]: spec for spec in LIST_SPECS}
        term_path = list_path(root, doc, specs["terminology"])
        sym_path = list_path(root, doc, specs["symbols"])
        cite_path = list_path(root, doc, specs["citations"])
        struct_path = list_path(root, doc, specs["structure"])
        term_path.write_text(
            term_path.read_text(encoding="utf-8")
            + "- [x] Other;MLIP(x): 测试禁用词。 <!-- id:term-checked -->\n",
            encoding="utf-8",
        )
        sym_path.write_text(
            sym_path.read_text(encoding="utf-8")
            + "- [x] `Z_i`;`Z_j`(x): 测试禁用符号。 <!-- id:sym-checked -->\n",
            encoding="utf-8",
        )
        cite_path.write_text(
            cite_path.read_text(encoding="utf-8")
            + "- [x] Missing entity: @definitely_missing <!-- id:cite-checked -->\n",
            encoding="utf-8",
        )
        struct_path.write_text(
            struct_path.read_text(encoding="utf-8")
            + "- [x] §99 Missing section | 意图: test | 标签: - <!-- id:sec-checked -->\n",
            encoding="utf-8",
        )
        findings = audit_document(root, "paper", doc)
        codes = {finding.code for finding in findings if finding.level == "error"}
        assert {"banned-variant", "banned-symbol", "cite-missing-bib", "outline-missing-section"} <= codes, codes
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()):
            assert set_text(root, "paper", doc, "terminology", "term-checked", "changed") != 0
        checks += 1

    print(f"selftest: {checks} checks passed")
    return 0


# ---------------------------------------------------------------------------
# CLI


def cmd_init(args) -> int:
    root = resolve_root(args.root)
    meta = root / META_NAME
    config = load_config(root) if meta.exists() else None
    if config:
        if args.manuscript:
            path = Path(args.manuscript).expanduser()
            path = path if path.is_absolute() else (root / path)
            path = path.resolve()
            rel = rel_to_root(path, root)
            for doc_id, doc in config.get("documents", {}).items():
                if doc["path"] == rel:
                    print(f"already registered: {doc_id} ({rel})")
                    return 0
            doc_id = unique_document_id(path, config["documents"])
            config["documents"][doc_id] = {
                "path": rel,
                "format": "latex" if path.suffix.lower() == ".tex" else "typst",
                "list_dir": f"docs/{doc_id}",
                "bib": [],
                "created_at": now_iso(),
            }
            new_doc = config["documents"][doc_id]
            new_doc["bib"] = [rel_to_root(bib, root) for bib in discover_bib_files(root, new_doc)]
            config["active"] = doc_id
            save_config(root, config)
            bootstrap_lists(root, new_doc)
            save_state(root, doc_id, {"schema_version": SCHEMA_VERSION, "items": {}})
            print(f"registered {doc_id}: {rel}")
            run_sync(root, doc_id, new_doc)
        else:
            print(f"meta exists; active document: {config.get('active')}")
        return 0

    candidates = discover_manuscripts(root)
    if args.manuscript:
        path = Path(args.manuscript).expanduser()
        path = path if path.is_absolute() else (root / path)
        path = path.resolve()
    elif candidates:
        path = candidates[0]
        print("discovered manuscript candidates:")
        for candidate in candidates[:8]:
            print(f"  {candidate.relative_to(root)}")
        print(f"selected: {path.relative_to(root)}")
    else:
        raise SystemExit("error: no manuscript found; pass --manuscript PATH")

    rel = rel_to_root(path, root)
    doc_id = unique_document_id(path, {})
    doc = {
        "path": rel,
        "format": "latex" if path.suffix.lower() == ".tex" else "typst",
        "list_dir": f"docs/{doc_id}",
        "bib": [],
        "created_at": now_iso(),
    }
    doc["bib"] = [rel_to_root(bib, root) for bib in discover_bib_files(root, doc)]
    config = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_iso(),
        "active": doc_id,
        "documents": {doc_id: doc},
        "discovery": [str(candidate.relative_to(root)) for candidate in candidates[:12]],
    }
    meta.mkdir(parents=True, exist_ok=True)
    save_config(root, config)
    bootstrap_lists(root, doc)
    save_state(root, doc_id, {"schema_version": SCHEMA_VERSION, "items": {}})
    atomic_write(meta / "README.md", META_README)
    print(f"initialized {meta.relative_to(root)} for {rel}")
    run_sync(root, doc_id, doc)
    save_config(root, config)
    return 0


def bootstrap_lists(root: Path, doc: dict) -> None:
    folder = root / META_NAME / doc["list_dir"]
    folder.mkdir(parents=True, exist_ok=True)
    for spec in LIST_SPECS:
        path = folder / spec["file"]
        if not path.exists():
            atomic_write(path, FILE_HEADERS[spec["kind"]].strip() + "\n\n")


def cmd_sync(args) -> int:
    root = resolve_root(args.root)
    config = load_config(root)
    if not config:
        raise SystemExit("error: no .manuscript_meta/config.json; run `init` first")
    if args.all:
        docs = list(config["documents"].items())
    else:
        docs = [get_document(root, config, args.document)]
    for doc_id, doc in docs:
        run_sync(root, doc_id, doc, dry_run=args.dry_run, prune=not args.no_prune)
    if not args.dry_run:
        save_config(root, config)
    return 0


def cmd_apply(args) -> int:
    root = resolve_root(args.root)
    config = load_config(root)
    if not config:
        raise SystemExit("error: no .manuscript_meta/config.json; run `init` first")
    doc_id, doc = get_document(root, config, args.document)
    try:
        overlay = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: cannot read overlay: {exc}")
    failures = apply_overlay(root, doc_id, doc, overlay)
    if not failures:
        save_config(root, config)
        print(f"applied overlay to {doc_id}")
    return 1 if failures else 0


def cmd_set_text(args) -> int:
    root = resolve_root(args.root)
    config = load_config(root)
    if not config:
        raise SystemExit("error: no .manuscript_meta/config.json; run `init` first")
    doc_id, doc = get_document(root, config, args.document)
    failures = set_text(root, doc_id, doc, args.kind, args.id, args.text)
    if not failures:
        save_config(root, config)
        print(f"updated {args.kind}/{args.id}")
    return 1 if failures else 0


def cmd_adopt(args) -> int:
    root = resolve_root(args.root)
    config = load_config(root)
    if not config:
        raise SystemExit("error: no .manuscript_meta/config.json; run `init` first")
    doc_id, doc = get_document(root, config, args.document)
    state = load_state(root, doc_id)
    changed = 0
    for spec in LIST_SPECS:
        items = state.setdefault("items", {}).setdefault(spec["kind"], {})
        path = list_path(root, doc, spec)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            row = parse_row(line)
            if not row or not row["id"]:
                continue
            if row["id"] in items:
                continue
            items[row["id"]] = {
                "hash": text_hash(row["text"]),
                "owned": "manual",
                "key": list(primary_key(spec["kind"], row["text"])),
            }
            changed += 1
    save_state(root, doc_id, state)
    print(f"adopted {changed} existing rows as user-owned (unchecked)")
    return 0



def cmd_norms(args) -> int:
    root = resolve_root(args.root)
    config = load_config(root)
    if not config:
        raise SystemExit("error: no .manuscript_meta/config.json; run `init` first")
    doc_id, doc = get_document(root, config, args.document)
    total = 0
    print(f"document: {doc_id} ({doc['path']})")
    for spec in LIST_SPECS:
        path = list_path(root, doc, spec)
        if not path.exists():
            continue
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            row = parse_row(line)
            if row and row["checked"]:
                rows.append(row["text"])
        if not rows:
            continue
        total += len(rows)
        print(f"\n## {spec['title']}")
        for text in rows:
            print(f"- {text}")
    if total == 0:
        print("\nno pinned rows yet; all listed norms are still candidates ([ ]).")
    return 0

def cmd_audit(args) -> int:
    root = resolve_root(args.root)
    config = load_config(root)
    if not config:
        raise SystemExit("error: no .manuscript_meta/config.json; run `init` first")
    docs = list(config["documents"].items()) if args.all else [get_document(root, config, args.document)]
    findings_all = []
    for doc_id, doc in docs:
        findings = audit_document(root, doc_id, doc, strict=args.strict)
        findings_all.extend((doc_id, item) for item in findings)
    if args.json:
        print(json.dumps([{"document": doc, "level": f.level, "code": f.code, "message": f.message}
                          for doc, f in findings_all], ensure_ascii=False, indent=2))
    else:
        for doc_id, finding in findings_all:
            print(f"[{finding.level.upper():<7}] {doc_id}: {finding.code}: {finding.message}")
        errors = sum(1 for _, f in findings_all if f.level == "error")
        warnings = sum(1 for _, f in findings_all if f.level == "warning")
        print(f"\n{errors} error(s), {warnings} warning(s)")
    return 1 if any(f.level == "error" for _, f in findings_all) else 0


def cmd_status(args) -> int:
    root = resolve_root(args.root)
    config = load_config(root)
    if not config:
        raise SystemExit("error: no .manuscript_meta/config.json; run `init` first")
    if args.all:
        for doc_id in config["documents"]:
            print_status(root, config, doc_id)
            print()
        return 0
    return print_status(root, config, args.document)


def cmd_scan(args) -> int:
    root = resolve_root(args.root)
    config = load_config(root)
    if not config:
        raise SystemExit("error: no .manuscript_meta/config.json; run `init` first")
    return print_scan(root, config, args.document, args.json)


META_README = """# `.manuscript_meta` 契约

本目录由 `skills/manuscript-meta/scripts/mmeta.py` 维护。它是手稿修改的**规范层**，
不是正文、不是实验记录，也不是自动写作器的输出缓存。

## 所有权

| 标记 | 含义 | 谁可以改 |
|---|---|---|
| `[ ]` + 工具自动维护 | 自动候选；`sync` 可更新/删除 | 工具与 agent |
| `[ ]` + agent 策划 | `apply` 写入的语义候选 | agent 通过工具 |
| `[ ]` + 用户编辑 | 用户已改写；`sync` 永不覆盖 | 用户 |
| `[x]` | **用户已固定规范** | 只有用户可改；工具/agent 只读 |

工具在 `sync` 时不会修改 `[x]` 行，不会把 `[ ]` 改成 `[x]`，也不会把 `[x]` 改成 `[ ]`。
如果 `[x]` 与当前手稿冲突，`audit` 报错；agent 必须修改手稿或报告，**不得改规范行**。

## 行 ID

每行末尾的 `<!-- id:... -->` 是稳定标识，用于把自动事实与用户规范对应起来。
用户可自由改行内文字；保留 ID 才能继续接收自动更新。删除 ID = 该行转为用户私有行。

## 列表语法

- 专业词/用词：`规范词;变体;禁用(x): 释义`。第一项为规范；`(x)` 为禁用。
- 结构：`§1.2 标题 | 意图: ... | 标签: ...`。顺序即正文顺序。
- 符号：`` `符号`;`禁用写法`(x): 含义 | 域/单位 | 位置 ``。
- 引用：`实体短语：@key1; @key2`。
- 图/表：`fig:label — 图注主张`。
- 数值：`12 meV — 主张与位置`。

- 符号列表中的 `bold(x)`、`cal(F)` 是函数记号，不是 `(x)` 禁用标记；禁用写法写成 `` `sym`(x) ``。
- 若要把规范同步到其他机器/协作者，提交 `.manuscript_meta/` 时一并提交 `.state/`；否则未知行会退化为用户私有行（仍不会被覆盖）。

## 颜色协作

正文颜色表示审阅状态，与 `[x]` 规范同时生效：

| 颜色 | 含义 | agent 行为 |
|---|---|---|
| grey | 人类未核实 | 可编辑/移动；直接改动转 blue |
| green | 人类已核实 | 只读；不得改字、移动或去色 |
| red | 人类已核实但含修改意见 | 下一轮必须修改；修改后转 blue |
| blue | agent 直接修改，人类待审核 | 不得二次修改；等待人类接受或退回 red |
| yellow | agent 建议/评注 | 直接以 yellow 新增在正文；只能新增；可多轮修改 |

- 流转：`grey→blue`、`red→blue`、`blue→green|red`、`yellow→green|yellow`。
- green 用墨绿色 `rgb("#1B5E20")`（Typst）或 `darkgreen`（LaTeX）；grey 默认 `luma(105)`。
- yellow 使用 `rgb("#B8860B")`，必须直接插入正文，不能只写在 `.manuscript_meta`。
- 现有颜色标记是权威状态；agent 不得新增、删除或改色，除非按上述流转执行。

## 命令

```bash
python3 skills/manuscript-meta/scripts/mmeta.py init [--manuscript PATH]
python3 skills/manuscript-meta/scripts/mmeta.py sync [--dry-run] [--all]
python3 skills/manuscript-meta/scripts/mmeta.py norms
python3 skills/manuscript-meta/scripts/mmeta.py audit [--strict] [--json]
python3 skills/manuscript-meta/scripts/mmeta.py status
python3 skills/manuscript-meta/scripts/mmeta.py scan --json
python3 skills/manuscript-meta/scripts/mmeta.py apply --file overlay.json
python3 skills/manuscript-meta/scripts/mmeta.py set-text --kind terminology --id term-mlip --text "..."
python3 skills/manuscript-meta/scripts/mmeta.py adopt
python3 skills/manuscript-meta/scripts/mmeta.py selftest
```

## 修改手稿时的硬规则

1. 先读所有 `[x]` 行；它们是唯一规范。
2. 规范词第一项优先；`(x)` 变体不得再出现。
3. 不新增未在符号表固定的同义符号；符号含义冲突先停下报告。
4. 引用实体必须落在已映射的 `@key` 集合内；新增主张先补映射或报告。
5. 已固定的章节顺序与意图不得改动；新增内容放进未固定的小节或报告。
6. 修改完成后运行 `audit`，不得把 `[x]` 行改成“让检查通过”。
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mmeta.py", description="Manuscript metadata ledger")
    parser.add_argument("--root", default=None, help="project root (default: cwd / nearest .git)")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--root", default=argparse.SUPPRESS,
        help="project root (accepted before or after the subcommand)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", parents=[common], help="create .manuscript_meta and register a manuscript")
    init_parser.add_argument("--manuscript", default=None)
    init_parser.set_defaults(func=cmd_init)

    sync_parser = sub.add_parser("sync", parents=[common], help="refresh auto rows from the manuscript")
    sync_parser.add_argument("--document", default=None)
    sync_parser.add_argument("--all", action="store_true")
    sync_parser.add_argument("--dry-run", action="store_true")
    sync_parser.add_argument("--no-prune", action="store_true")
    sync_parser.set_defaults(func=cmd_sync)

    apply_parser = sub.add_parser("apply", parents=[common], help="apply an agent curation overlay")
    apply_parser.add_argument("--document", default=None)
    apply_parser.add_argument("--file", required=True)
    apply_parser.set_defaults(func=cmd_apply)

    set_parser = sub.add_parser("set-text", parents=[common], help="update one unchecked row")
    set_parser.add_argument("--document", default=None)
    set_parser.add_argument("--kind", required=True, choices=[spec["kind"] for spec in LIST_SPECS])
    set_parser.add_argument("--id", required=True)
    set_parser.add_argument("--text", required=True)
    set_parser.set_defaults(func=cmd_set_text)

    adopt_parser = sub.add_parser("adopt", parents=[common], help="mark existing rows as user-owned")
    adopt_parser.add_argument("--document", default=None)
    adopt_parser.set_defaults(func=cmd_adopt)

    norms_parser = sub.add_parser("norms", parents=[common], help="print only the fixed ([x]) norms")
    norms_parser.add_argument("--document", default=None)
    norms_parser.set_defaults(func=cmd_norms)

    audit_parser = sub.add_parser("audit", parents=[common], help="check manuscript against fixed rows")
    audit_parser.add_argument("--document", default=None)
    audit_parser.add_argument("--all", action="store_true")
    audit_parser.add_argument("--strict", action="store_true")
    audit_parser.add_argument("--json", action="store_true")
    audit_parser.set_defaults(func=cmd_audit)

    status_parser = sub.add_parser("status", parents=[common], help="row counts by ownership")
    status_parser.add_argument("--document", default=None)
    status_parser.add_argument("--all", action="store_true")
    status_parser.set_defaults(func=cmd_status)

    scan_parser = sub.add_parser("scan", parents=[common], help="dump extracted facts")
    scan_parser.add_argument("--document", default=None)
    scan_parser.add_argument("--json", action="store_true")
    scan_parser.set_defaults(func=cmd_scan)

    selftest_parser = sub.add_parser("selftest", parents=[common], help="run merge-preservation self-tests")
    selftest_parser.set_defaults(func=lambda args: selftest())

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
