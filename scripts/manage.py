#!/usr/bin/env python3
"""Portable command interface for the paper template (Python 3.10+)."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from repo import (Blocked, Violation, PIN_START, PIN_END, assert_no_unstaged,
                  blob, check_content, check_dependencies, check_history, entries,
                  git, index_text, pin_block, pins, require_repo, valid_url, verify_record)

ROOT = Path(__file__).resolve().parents[1]

def output_dir(root: Path) -> Path:
    path = root / 'build'
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise Violation('build must be a local directory, not a symlink or file.')
    path.mkdir(exist_ok=True)
    return path

def write_output(path: Path, text: str) -> None:
    if path.is_symlink():
        raise Violation(f'Refusing to overwrite an output symlink: {path.name}')
    path.write_text(text, encoding='utf-8', newline='\n')

def inspect(root: Path) -> tuple[dict, list[dict]]:
    require_repo(root)
    index = entries(root)
    if not index:
        raise Blocked('The Git index is empty. Review the template, then git add .')
    return index, pins(root, index)

def check(root: Path, args: argparse.Namespace) -> None:
    index, inventory = inspect(root)
    assert_no_unstaged(root)
    for path in ('AGENTS.md', 'README.md', 'src/main.typ', 'project.json', '.typst-version'):
        index_text(root, index, path)
    verify_record(index_text(root, index, 'docs/REPRODUCE.md'), inventory)
    check_content(root, index)
    check_dependencies(root, inventory, args.require_submodules)
    if args.history:
        check_history(root, args.base)
    print('PASS: index topology, recorded pins, tracked file policy and size limits.')
    print('NOT RUN: scientific result validation, remote-ref approval and local sync settings (manual gates).')

def record_pins(root: Path, reason: str) -> None:
    if not reason.strip():
        raise Blocked('Provide --reason or REASON explaining this inventory update.')
    _, inventory = inspect(root)
    path = root / 'docs/REPRODUCE.md'
    if path.is_symlink():
        raise Violation('REPRODUCE.md must not be a symlink.')
    prefix, _, suffix = pin_block(path.read_text(encoding='utf-8'))
    reason = ' '.join(reason.split())
    text = prefix + PIN_START + json.dumps(inventory, indent=2, ensure_ascii=False) + PIN_END + suffix
    text += f'\nPin inventory note: {reason}\n'
    write_output(path, text)
    print('PASS: updated only the pin block and appended its reason in docs/REPRODUCE.md.')
    print('Review the full record, then stage it together with .gitmodules and the gitlinks; nothing was committed.')

def restore(root: Path) -> None:
    index, inventory = inspect(root)
    assert_no_unstaged(root)
    # Do not restore over dirty dependencies or an intentional unstaged pin upgrade.
    check_dependencies(root, inventory, required=False)
    for item in inventory:
        path = root / item['path']
        if path.is_symlink():
            raise Violation('Refusing a symlinked submodule destination.')
        if path.exists() and not (path / '.git').exists() and any(path.iterdir()):
            raise Violation(f'Uninitialized destination contains files; preserve them: {item["path"]}')
    if not inventory:
        print('NOT RUN: no submodules to initialize.')
        return
    try:
        git(root, 'submodule', 'update', '--init', '--recursive', '--checkout')
    except Violation as exc:
        raise Blocked('Submodule checkout failed. Inspect access/network/state; no forced cleanup was attempted.') from exc
    check_dependencies(root, inventory, required=True)

def compile_paper(root: Path) -> None:
    version = (root / '.typst-version').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise Violation('.typst-version must contain an exact stable version.')
    exe = shutil.which('typst')
    if not exe:
        raise Blocked(f'Install Typst {version} and add it to PATH; see docs/SETUP.md.')
    installed = subprocess.run([exe, '--version'], text=True, capture_output=True, check=True).stdout
    match = re.search(r'typst (\d+\.\d+\.\d+)\b', installed)
    if not match or match.group(1) != version:
        raise Blocked(f'Typst version mismatch. Required {version}; installed {installed.strip()}')
    out = output_dir(root) / 'main.pdf'
    if out.is_symlink():
        raise Violation('Refusing to overwrite a symlinked PDF output.')
    subprocess.run([exe, 'compile', '--root', str(root), '--ignore-system-fonts',
                    '--creation-timestamp', '0', str(root / 'src/main.typ'), str(out)], check=True)
    if not out.is_file() or out.stat().st_size == 0:
        raise Violation('Compilation did not produce a nonempty PDF.')
    print(f'PASS: manuscript compiled with Typst {version} -> build/main.pdf')

def run_hook(root: Path, name: str) -> None:
    _, inventory = inspect(root)
    target = 'submodules/code' if name == 'code-test' else 'submodules/experiments'
    if target not in {x['path'] for x in inventory}:
        raise Blocked(f'{target} is not configured; no {name} command was executed.')
    assert_no_unstaged(root)
    check_dependencies(root, inventory, required=True)
    config = json.loads((root / 'config/hooks.json').read_text(encoding='utf-8'))
    command = config.get(name)
    if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
        raise Blocked(f'Document an argv array for {name} in config/hooks.json.')
    command = [sys.executable if i == 0 and value == '{python}' else value
               for i, value in enumerate(command)]
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    if name == 'figures':
        destination = output_dir(root) / 'figures'
        if destination.is_symlink():
            raise Violation('build/figures must not be a symlink.')
        destination.mkdir(exist_ok=True)
        env['FIGURE_OUTPUT_DIR'] = str(destination)
    try:
        r = subprocess.run(command, cwd=root / target, env=env, check=False)
    except FileNotFoundError as exc:
        raise Blocked(f'Hook executable not installed: {command[0]}') from exc
    if r.returncode == 2 and name == 'figures':
        raise Blocked(f'{name} is not configured or its prerequisites are missing. Inspect the owning repository output.')
    if r.returncode:
        raise Violation(f'{name} failed with exit code {r.returncode}.')
    print(f'PASS: documented {name} hook exited successfully (not a scientific correctness proof).')

def initialize(root: Path, args: argparse.Namespace) -> None:
    path = root / 'project.json'
    if path.is_symlink():
        raise Violation('project.json must not be a symlink.')
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('initialized'):
        raise Violation('Metadata is already initialized. Edit project.json explicitly; no overwrite was made.')
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]*', args.name):
        raise Violation('--name must be a lowercase repository slug.')
    if not args.title.strip() or any(not x.strip() for x in args.author):
        raise Violation('Title and author names must be nonempty.')
    if args.repository_url and not valid_url(args.repository_url):
        raise Violation('Repository URL must be HTTPS/SSH without embedded secrets.')
    data.update(name=args.name, title=args.title, authors=args.author,
                repository_url=args.repository_url, initialized=True)
    write_output(path, json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print('PASS: project.json initialized. No Git repository, remote, commit or GitHub resource was created.')

def manifest(root: Path, release: bool) -> None:
    index, inventory = inspect(root)
    head = git(root, 'rev-parse', '--verify', 'HEAD', allowed=(0, 128)).decode().strip()
    if not head:
        raise Blocked('Commit the reviewed source before generating a commit-based manifest.')
    dirty = bool(git(root, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=none'))
    if release and dirty:
        raise Violation('Release manifest requires a clean committed checkout, including untracked files and submodules.')
    verify_record(index_text(root, index, 'docs/REPRODUCE.md'), inventory)
    if release:
        check_dependencies(root, inventory, required=True)
    files = {}
    for path, (mode, oid) in index.items():
        if path.startswith('assets/') and mode in ('100644', '100755'):
            files[path] = hashlib.sha256(blob(root, oid)).hexdigest()
    pdf = root / 'build/main.pdf'
    pdf_digest = hashlib.sha256(pdf.read_bytes()).hexdigest() if pdf.is_file() and not pdf.is_symlink() else None
    result = {
        'schema_version': 1, 'paper_commit': head, 'dirty': dirty,
        'pin_source': 'Git index (equals committed revision only in a clean checkout)',
        'pins': inventory, 'recursive_submodule_status': git(root, 'submodule', 'status', '--recursive').decode(),
        'typst_required': (root / '.typst-version').read_text().strip(),
        'python': sys.version.split()[0], 'git': git(root, '--version').decode().strip(),
        'tracked_asset_sha256': files, 'pdf_sha256': pdf_digest,
        'validation': 'Manifest only. Run compile, checks, tests and manual release gates separately.',
    }
    dest = output_dir(root) / 'provenance.json'
    write_output(dest, json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print('PASS: build/provenance.json records the actual commit and current index; no files were staged or committed.')

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='paper repository root')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('check', help='validate staged/index state without rewriting it')
    p.add_argument('--history', action='store_true', help='also scan committed blobs, including later-deleted ones')
    p.add_argument('--base', default=os.environ.get('BASE_REV') or None, help='full base commit for history scan')
    p.add_argument('--require-submodules', action='store_true')
    p = sub.add_parser('record-pins', help='write the staged pin inventory into REPRODUCE.md')
    p.add_argument('--reason', default=os.environ.get('REASON', ''))
    for cmd in ('submodules', 'compile', 'code-test', 'figures'):
        sub.add_parser(cmd)
    p = sub.add_parser('manifest')
    p.add_argument('--release', action='store_true', help='require clean checkout and initialized pins')
    p = sub.add_parser('init', help='one-time metadata initialization; never creates/pushes repositories')
    p.add_argument('--name', required=True)
    p.add_argument('--title', required=True)
    p.add_argument('--author', action='append', required=True)
    p.add_argument('--repository-url', default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command == 'check':
            check(root, args)
        elif args.command == 'record-pins':
            record_pins(root, args.reason)
        elif args.command == 'submodules':
            restore(root)
        elif args.command == 'compile':
            compile_paper(root)
        elif args.command in ('code-test', 'figures'):
            run_hook(root, args.command)
        elif args.command == 'manifest':
            manifest(root, args.release)
        elif args.command == 'init':
            initialize(root, args)
        return 0
    except Blocked as exc:
        print(f'BLOCKED: {exc}', file=sys.stderr)
        return 2
    except (Violation, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
