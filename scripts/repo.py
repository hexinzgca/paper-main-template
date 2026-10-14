"""Small, read-only Git inspection helpers used by the template CLI.

Checks describe the index, not arbitrary unstaged files. Network access is kept
out of this module. All subprocesses use argument arrays, never shell=True.
"""
from __future__ import annotations
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import urlsplit

MAX_BYTES = 10_000_000
ASSET_BYTES = 2_000_000
PIN_START = '<!-- pins:start -->\n```json\n'
PIN_END = '\n```\n<!-- pins:end -->'

class Violation(RuntimeError):
    """A definite repository-policy violation (exit code 1)."""

class Blocked(RuntimeError):
    """A required tool, dependency, or precondition is missing (exit code 2)."""

def git(root: Path, *args: str, allowed: tuple[int, ...] = (0,)) -> bytes:
    try:
        r = subprocess.run(['git', '-C', str(root), *args], capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise Blocked('Git is not installed or not on PATH.') from exc
    if r.returncode not in allowed:
        message = r.stderr.decode('utf-8', errors='replace').strip()
        raise Violation(f'Git command failed ({args[0]}): {message}')
    return r.stdout

def require_repo(root: Path) -> None:
    if not (root / '.git').exists():
        raise Blocked('Initialize this directory with git init -b main, then git add .')
    actual = git(root, 'rev-parse', '--show-toplevel').decode().strip()
    if Path(actual).resolve() != root.resolve():
        raise Violation('Run this tool at the paper repository root, not the bundle root.')

def entries(root: Path) -> dict[str, tuple[str, str]]:
    result = {}
    for row in git(root, 'ls-files', '--stage', '-z').split(b'\0'):
        if not row:
            continue
        header, name = row.split(b'\t', 1)
        mode, oid, stage = header.decode('ascii').split()
        path = name.decode('utf-8')
        if stage != '0':
            raise Violation(f'Unmerged index entry: {path}')
        result[path] = (mode, oid)
    return result

def blob(root: Path, oid: str) -> bytes:
    return git(root, 'cat-file', 'blob', oid)

def index_text(root: Path, index: dict, path: str) -> str:
    if path not in index:
        raise Violation(f'Required file is not staged/tracked: {path}')
    if index[path][0] not in ('100644', '100755'):
        raise Violation(f'Expected an ordinary file: {path}')
    return blob(root, index[path][1]).decode('utf-8').replace('\r\n', '\n')

def valid_url(url: str) -> bool:
    if any(c.isspace() for c in url):
        return False
    if re.fullmatch(r'git@[A-Za-z0-9.-]+:[A-Za-z0-9._/-]+', url):
        return '..' not in url.split(':', 1)[1].split('/')
    p = urlsplit(url)
    if p.scheme not in ('https', 'ssh') or not p.hostname or not p.path or p.path == '/':
        return False
    if p.password or p.query or p.fragment:
        return False
    if p.scheme == 'https' and p.username:
        return False
    return '..' not in p.path.split('/')

def pins(root: Path, index: dict) -> list[dict[str, str]]:
    index_text(root, index, '.gitmodules')
    # Git parses its own configuration syntax; do not approximate it with INI.
    raw = git(root, 'config', '--null', '--blob', index['.gitmodules'][1], '--list')
    groups: dict[str, dict[str, str]] = {}
    for item in raw.split(b'\0'):
        if not item:
            continue
        key, sep, value = item.decode('utf-8').partition('\n')
        match = re.fullmatch(r'submodule\.(.+)\.(path|url|branch|update|ignore|shallow)', key)
        if not match or not sep:
            raise Violation('Unsupported .gitmodules setting; review it explicitly.')
        name, field = match.groups()
        values = groups.setdefault(name, {})
        if field in values:
            raise Violation(f'Duplicate .gitmodules key: {key}')
        values[field] = value
    modules = {}
    for name, values in groups.items():
        path, url = values.get('path', ''), values.get('url', '')
        if not re.fullmatch(r'submodules/[A-Za-z0-9][A-Za-z0-9._-]*', path):
            raise Violation(f'Submodule path must be submodules/<name>: {path}')
        if path in modules:
            raise Violation(f'Duplicate submodule path: {path}')
        if not valid_url(url):
            raise Violation('Submodule URLs must be approved absolute HTTPS/SSH URLs without credentials or query tokens.')
        if values.get('update', 'checkout') != 'checkout':
            raise Violation('This template requires checkout as the submodule update strategy.')
        if values.get('ignore', 'none') != 'none':
            raise Violation('Do not hide submodule changes through .gitmodules ignore settings.')
        modules[path] = url
    links = {p: oid for p, (mode, oid) in index.items() if mode == '160000'}
    if set(modules) != set(links):
        raise Violation('.gitmodules paths do not exactly match the staged gitlinks.')
    return [{'path': p, 'url': modules[p], 'commit': links[p]} for p in sorted(links)]

def pin_block(text: str) -> tuple[str, str, str]:
    if text.count(PIN_START) != 1 or text.count(PIN_END) != 1:
        raise Violation('REPRODUCE.md needs exactly one intact pins:start / pins:end JSON block.')
    prefix, rest = text.split(PIN_START, 1)
    encoded, suffix = rest.split(PIN_END, 1)
    return prefix, encoded, suffix

def verify_record(text: str, expected: list[dict]) -> None:
    _, encoded, _ = pin_block(text)
    try:
        recorded = json.loads(encoded)
    except json.JSONDecodeError as exc:
        raise Violation('The pin inventory in REPRODUCE.md is invalid JSON.') from exc
    if recorded != expected:
        raise Violation('REPRODUCE.md pins differ from the index. Run record-pins, then stage the record with the gitlinks.')

def assert_no_unstaged(root: Path) -> None:
    changed = git(root, 'diff', '--name-only', '-z', '--ignore-submodules=all')
    if changed:
        raise Violation('There are unstaged tracked changes. Review and stage the intended files before check; nothing was overwritten.')

def check_content(root: Path, index: dict) -> None:
    denied = {'.pt', '.pth', '.ckpt', '.safetensors', '.npy', '.npz', '.parquet', '.h5', '.hdf5'}
    asset_notes = index_text(root, index, 'docs/ASSETS.md') if 'docs/ASSETS.md' in index else ''
    for path, (mode, oid) in index.items():
        p = PurePosixPath(path)
        if mode == '160000':
            continue
        if p.parts[0] == 'submodules' and path not in ('submodules/README.md', 'submodules/.gitkeep'):
            raise Violation(f'Copied submodule content is forbidden in the parent index: {path}')
        if p.suffix.lower() in denied or p.parts[0].lower() in {'data', 'datasets', 'weights', 'checkpoints', 'logs', 'build', '.venv'}:
            raise Violation(f'Prohibited raw data, model, or generated path: {path}')
        if mode == '120000' and p.parts[0] in {'src', 'assets', 'submodules'}:
            raise Violation(f'Symlinks in manuscript/dependency inputs require a separate reviewed design: {path}')
        size = int(git(root, 'cat-file', '-s', oid))
        if size > MAX_BYTES:
            raise Violation(f'Git blob exceeds {MAX_BYTES:,} bytes: {path} ({size:,})')
        if p.parts[0] == 'assets' and size >= ASSET_BYTES and path not in asset_notes:
            raise Violation(f'Asset at or above 2 MB needs a path-specific justification in docs/ASSETS.md: {path}')

def check_history(root: Path, base: str | None) -> None:
    head = git(root, 'rev-parse', '--verify', 'HEAD', allowed=(0, 128)).strip()
    if not head:
        print('NOT RUN: history scan (no commit yet); staged blobs were checked.')
        return
    args = ['rev-list', '--objects', 'HEAD']
    if base:
        if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', base):
            raise Violation('BASE_REV must be a full commit hash, not a branch, option, or range.')
        git(root, 'rev-parse', '--verify', f'{base}^{{commit}}')
        args += ['--not', base]
    oids = sorted({line.split(b' ', 1)[0] for line in git(root, *args).splitlines()})
    r = subprocess.run(['git', '-C', str(root), 'cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)'],
                       input=b'\n'.join(oids) + b'\n', capture_output=True, check=True)
    for row in r.stdout.splitlines():
        fields = row.split()
        if len(fields) == 3 and fields[1] == b'blob' and int(fields[2]) > MAX_BYTES:
            raise Violation(f'Oversized historical blob, even if later deleted: {fields[0].decode()} ({fields[2].decode()} bytes)')
    print('PASS: reachable commit-range Git blob sizes.')

def check_dependencies(root: Path, inventory: list[dict], required: bool = False) -> None:
    if not inventory:
        print('NOT RUN: dependency checkout/tests (no submodules configured).')
        return
    missing = []
    for item in inventory:
        path = root / item['path']
        if not (path / '.git').exists():
            missing.append(item['path'])
            continue
        if git(path, 'rev-parse', 'HEAD').decode().strip() != item['commit']:
            raise Violation(f'Submodule HEAD differs from index; preserve intentional pin changes: {item["path"]}')
        dirty = git(path, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=none')
        if dirty:
            raise Violation(f'Dirty submodule worktree; no automatic reset/stash: {item["path"]}')
    state = git(root, 'submodule', 'status', '--recursive').decode('utf-8')
    for line in state.splitlines():
        if line.startswith(('+', 'U')):
            raise Violation('Nested or direct submodule pin mismatch/conflict: ' + line)
        if line.startswith('-'):
            missing.append(line)
    if missing:
        if required:
            raise Blocked('Dependencies are not initialized at recorded pins. Review URLs/state, then run make submodules.')
        print('NOT RUN: full dependency validation (uninitialized pins; use make submodules).')
    else:
        print('PASS: initialized direct/nested dependency pins and direct worktree state.')
