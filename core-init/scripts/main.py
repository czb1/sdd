"""
Main entry point for core-init skill.
Provides CLI-like interface for project initialization.

New in this version (防爆 / repo scope):
  - `scan-repos`     : preview which repos /core-init would touch
  - `set-repo-scope` : write the user's decision into codegraph.json
  - `init`           : refuses to run when the launch directory holds more
                       repos than `maxRepos` (exit code 3), so a workspace
                       with dozens of clones can't blow up the pipeline
"""

import json
import locale
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from shutil import which
from typing import List, Optional

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from cc_paths import setup_core_paths
    setup_core_paths()
except Exception:  # noqa: BLE001 - never let path setup break the CLI
    pass

try:
    from repo_config import (  # noqa: E402
        CONFIG_FILENAME,
        DEFAULT_MAX_REPOS,
        apply_repo_selection,
        config_path,
        evaluate_scope,
        load_config,
        print_scope_report,
        suggest_config,
    )
except ImportError as _exc:  # pragma: no cover
    raise SystemExit(
        'core-init requires core-shared/scripts/repo_config.py. Install the '
        'core-shared skill next to core-init (<config_dir>/skills/core-shared/scripts/). '
        f'Import error: {_exc}'
    )


# Exit code used to tell the SKILL layer "stop and ask the user".
EXIT_NEEDS_REPO_SELECTION = 3


def _split_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


def ensure_docs_structure(project_root: str) -> dict:
    """
    Ensure docs directory structure exists (was corespec).

    Args:
        project_root: Project root directory

    Returns:
        Dict with created directories
    """
    root = Path(project_root)
    docs = root / 'docs'

    dirs = {
        'docs': docs,
        'specs': docs / 'specs',
        'changes': docs / 'changes',
        'archive': docs / 'archive',
    }

    for name, path in dirs.items():
        path.mkdir(parents=True, exist_ok=True)

    return {name: str(path) for name, path in dirs.items()}


def fetch_layered_specs(project_root: str, json_output: bool = False) -> dict:
    """
    Prepare for fetching layered specs from remote repositories.
    Returns skill invocation for code-rule-skills.
    """
    return {
        'success': True,
        'skill_invocation': {
            'skill': 'code-rule-skills',
            'action': 'sync',
        },
        'message': 'SKILL layer should invoke code-rule-skills skill to fetch and merge layered specs',
    }


def init_project(
    project_root: str,
    json_output: bool = False,
    max_repos: Optional[int] = None,
    force: bool = False,
    run_index: bool = True,
) -> dict:
    """
    Initialize a new CoreSpec project.

    Execution order:
    0. repo scope guard (防爆)      <- NEW: may stop here and ask the user
    1. ensure_docs_structure
    2. codegraph init (+ index, honouring codegraph.json)
    3. fetch_layered_specs (returns skill invocation)
    4. generate_module_designs (codewiki-sync invocation)
    """
    scope = evaluate_scope(project_root, max_repos=max_repos, force=force)

    if scope['needs_selection']:
        return {
            'success': False,
            'status': 'needs_repo_selection',
            'reason': 'too_many_repos' if scope['over_limit'] else 'scan_truncated',
            'scope': scope,
            'suggested_config': suggest_config(scope),
            'config_file': scope['config_file'],
            'message': (
                f"Found {len(scope['repos'])} repositories under {scope['root']} "
                f"(limit {scope['max_repos']}). Ask the user which repos to keep, then run "
                f"`set-repo-scope --repos <a,b>` or edit {CONFIG_FILENAME} directly."
            ),
        }

    dirs = ensure_docs_structure(project_root)
    codegraph_result = run_codegraph(project_root, run_index=run_index)
    layered_specs_result = fetch_layered_specs(project_root, json_output)
    modules_result = generate_module_designs(project_root, json_output)

    return {
        'success': True,
        'status': 'ok',
        'mode': 'init',
        'phase': 'complete',
        'directories': dirs,
        'repos': [r['name'] for r in scope['repos']],
        'excluded_repos': [r['name'] for r in scope['excluded_repos']],
        'is_multi_repo': scope['is_multi_repo'],
        'config_file': scope['config_file'],
        'codegraph': codegraph_result,
        'skill_invocation': layered_specs_result.get('skill_invocation'),
        'modules': modules_result.get('modules', []),
    }


def identify_modules(project_root: str) -> dict:
    """
    Identify modules in the project based on build files.

    Module identification strategy:
    - Maven/Gradle multi-module: each directory with pom.xml or build.gradle is a module
    - Single module project: the root project is the only module
    - Frontend projects: directories with package.json
    """
    project_path = Path(project_root)
    modules = {}

    BUILD_FILES = {
        'pom.xml': 'maven',
        'build.gradle': 'gradle',
        'build.gradle.kts': 'gradle',
        'package.json': 'npm',
        'go.mod': 'go',
        'Cargo.toml': 'rust',
        'pyproject.toml': 'python',
    }

    EXCLUDE_DIRS = {'node_modules', '.git', 'dist', 'build', '__pycache__', 'target', '.idea', '.vscode'}

    for root_dir, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        root_path = Path(root_dir)
        rel_path = root_path.relative_to(project_path)

        for build_file, build_type in BUILD_FILES.items():
            if build_file in files:
                module_name = rel_path.name if str(rel_path) != '.' else project_path.name
                if module_name not in modules:
                    modules[module_name] = {
                        'path': str(rel_path),
                        'build_type': build_type,
                        'build_file': build_file,
                    }
                break

    if not modules:
        modules[project_path.name] = {
            'path': '.',
            'build_type': 'unknown',
            'build_file': None,
        }

    return modules


def generate_module_designs(project_root: str, json_output: bool = False) -> dict:
    """
    Prepare for codewiki-sync skill invocation.
    Returns skill invocation info for SKILL layer to execute.
    """
    return {
        'success': True,
        'modules': [],
        'module_paths': {},
        'skill_invocation': {
            'skill': 'codewiki-sync',
            'action': 'sync',
            'command': f'python skills/codewiki-sync/scripts/main.py sync --path "{project_root}"',
        },
        'message': 'SKILL layer should invoke codewiki-sync skill',
    }


def update_project(
    project_root: str,
    json_output: bool = False,
    max_repos: Optional[int] = None,
    force: bool = False,
    run_index: bool = True,
) -> dict:
    """Update an existing CoreSpec project."""
    scope = evaluate_scope(project_root, max_repos=max_repos, force=force)
    if scope['needs_selection']:
        return {
            'success': False,
            'status': 'needs_repo_selection',
            'scope': scope,
            'suggested_config': suggest_config(scope),
            'config_file': scope['config_file'],
            'message': (
                f"Found {len(scope['repos'])} repositories (limit {scope['max_repos']}). "
                f"Narrow the scope in {CONFIG_FILENAME} before updating."
            ),
        }

    project_path = Path(project_root)
    docs = project_path / 'docs'
    backup_dir = docs / 'backup' / datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir.mkdir(parents=True, exist_ok=True)

    import shutil
    for f in ['rule.md', 'language.json', 'relationship.md', 'graph.json']:
        src = docs / f
        if src.exists():
            shutil.copy2(src, backup_dir / f)

    codegraph_result = run_codegraph(project_root, run_index=run_index)
    fetch_layered_specs(project_root, json_output)

    return {
        'success': True,
        'status': 'ok',
        'mode': 'update',
        'backup': str(backup_dir),
        'repos': [r['name'] for r in scope['repos']],
        'codegraph': codegraph_result,
    }


def find_codegraph():
    candidates = [
        Path.home() / ".config" / "opencode" / "node_modules" / ".bin" / "codegraph.cmd",
        Path.home() / ".config" / "opencode" / "node_modules" / ".bin" / "codegraph",
        Path.home() / ".cac" / "node_modules" / ".bin" / "codegraph.cmd",
        Path.home() / ".cac" / "node_modules" / ".bin" / "codegraph",
    ]

    for cmd in candidates:
        if cmd.exists():
            return str(cmd)

    found = which("codegraph")
    if found:
        return found

    raise RuntimeError("Cannot find codegraph executable")


def runcmd(args, cwd: Optional[str] = None, timeout: int = 120) -> bool:
    """Run the codegraph CLI. Never raises - returns False on failure."""
    try:
        codegraph = find_codegraph()
        print(f"Using codegraph: {codegraph}")

        # Console encoding differs per platform (gbk on zh-CN Windows, utf-8 elsewhere).
        encoding = os.environ.get("CORESPEC_CMD_ENCODING") or locale.getpreferredencoding(False) or "utf-8"

        ret = subprocess.run(
            [codegraph, *args],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding=encoding,
            errors="replace",
            timeout=timeout,
        )

        if ret.returncode != 0:
            print(ret.stderr)
            return False

        if ret.stdout:
            print(ret.stdout)

        return True

    except Exception as e:
        print(f"codegraph error: {e}")
        return False


def run_codegraph(project_root: str, run_index: bool = True) -> dict:
    """
    Run `codegraph init` and (optionally) `codegraph index`.

    The index step is what actually honours codegraph.json (exclude / include /
    includeIgnored / extensions), and the CodeGraph docs require a re-index
    after those keys change - so init always follows the config with an index.
    Failures are reported but never abort /core-init.
    """
    root = str(Path(project_root).resolve())
    result = {
        'init': runcmd(["init", root], timeout=120),
        'index': None,
        'config_file': str(config_path(root)),
        'config_exists': config_path(root).exists(),
    }
    if run_index:
        # `codegraph index` reads codegraph.json from the project root.
        result['index'] = runcmd(["index"], cwd=root, timeout=1800)
    return result


def has_substantial_content(file_path: Path) -> bool:
    """
    Check if file exists and has substantial content (not empty or placeholder).

    IMPORTANT: this must stay in sync with codewiki-sync's `is_placeholder_spec`
    (skills/codewiki-sync/scripts/main.py). codewiki-sync writes placeholder
    spec.md files that are long, Chinese, and do NOT start with '# TODO' - so
    the old length+prefix heuristic classified them as real content and made
    check-sync skip a repo whose spec.md was still a template.

    Args:
        file_path: Path to the file to check

    Returns:
        True if file exists and has content beyond placeholder text
    """
    if not file_path.exists():
        return False

    try:
        content = file_path.read_text(encoding='utf-8')
        stripped = content.strip()

        if len(stripped) < 100:
            return False

        prefix_patterns = [
            '# TODO',
            '# Placeholder',
            '# Generated',
            'Under construction',
            'Coming soon',
        ]
        for pattern in prefix_patterns:
            if stripped.startswith(pattern):
                return False

        # Markers emitted by codewiki-sync's placeholder templates.
        placeholder_markers = [
            '此文档为模板占位内容',
            '请补充核心职责描述',
            '实际内容需由 Agent',
        ]
        for marker in placeholder_markers:
            if marker in content:
                return False

        # A template table is mostly TODO cells.
        if sum(1 for line in content.splitlines() if 'TODO' in line) >= 3:
            return False

        return True
    except Exception:
        return False


def get_repo_list_from_language_json(project_root: Path):
    """
    Parse language.json to get repo list and determine single/multi repo.

    Returns:
        Tuple of (repo_names, is_multi_repo)
    """
    lang_file = project_root / 'docs' / 'language.json'
    if not lang_file.exists():
        return [project_root.name], False

    try:
        with open(lang_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return [project_root.name], False

    if not isinstance(data, dict) or not data:
        return [project_root.name], False

    repos = [k for k in data.keys() if not k.startswith('_')]
    if not repos:
        return [project_root.name], False

    # Single-repo language.json uses the root directory name as its only key.
    is_multi_repo = len(repos) > 1
    return repos, is_multi_repo


def check_specs_need_sync(project_root: str, json_output: bool = False) -> dict:
    """Check if spec documents need to be synced via codewiki-sync."""
    root = Path(project_root)
    repos, is_multi_repo = get_repo_list_from_language_json(root)

    repos_needing_sync = []
    repos_skipped = []

    for repo_name in repos:
        if is_multi_repo:
            repo_path = root / repo_name
            spec_file = repo_path / 'docs' / 'specs' / 'spec.md'
            design_file = repo_path / 'docs' / 'specs' / 'design.md'
        else:
            repo_path = root
            spec_file = root / 'docs' / 'specs' / 'spec.md'
            design_file = root / 'docs' / 'specs' / 'design.md'

        spec_ok = has_substantial_content(spec_file)
        design_ok = has_substantial_content(design_file)

        if not spec_ok or not design_ok:
            repos_needing_sync.append({
                'repo': repo_name,
                'path': str(repo_path),
                'spec_missing': not spec_ok,
                'design_missing': not design_ok,
            })
        else:
            repos_skipped.append({
                'repo': repo_name,
                'path': str(repo_path),
            })

    result = {
        'success': True,
        'is_multi_repo': is_multi_repo,
        'repos_needing_sync': repos_needing_sync,
        'repos_skipped': repos_skipped,
        'skip_codewiki_sync': len(repos_needing_sync) == 0,
    }

    if json_output:
        return result

    if result['skip_codewiki_sync']:
        print("All spec documents already exist with substantial content. Skipping codewiki-sync.")
        for r in repos_skipped:
            print(f"  ✓ {r['repo']}: spec.md and design.md OK")
    else:
        print(f"{len(repos_needing_sync)} repo(s) need codewiki-sync:")
        for r in repos_needing_sync:
            reasons = []
            if r['spec_missing']:
                reasons.append('spec.md missing/empty')
            if r['design_missing']:
                reasons.append('design.md missing/empty')
            print(f"  → {r['repo']}: {', '.join(reasons)}")
        if repos_skipped:
            print(f"\n{len(repos_skipped)} repo(s) already have substantial content:")
            for r in repos_skipped:
                print(f"  ✓ {r['repo']}: spec.md and design.md OK")

    return result


def main():
    """Main entry point for skill execution."""
    import argparse

    parser = argparse.ArgumentParser(description='CoreSpec Init Skill')
    parser.add_argument(
        'command',
        choices=['init', 'update', 'scan-repos', 'set-repo-scope', 'fetch-layered',
                 'generate-modules', 'merge', 'status', 'check-sync'],
        help='Command to execute')
    parser.add_argument('--project-root', default=os.getcwd(), help='Project root directory')
    parser.add_argument('--json', action='store_true', help='JSON output')

    # 防爆 / repo scope options
    parser.add_argument('--max-repos', type=int, default=None,
                        help=f'Max repos before asking the user (default {DEFAULT_MAX_REPOS})')
    parser.add_argument('--force', action='store_true',
                        help='Bypass the repo-count guard (only after the user confirmed)')
    parser.add_argument('--no-index', action='store_true',
                        help='Skip `codegraph index` after init/update')
    parser.add_argument('--repos', default=None,
                        help='set-repo-scope: comma-separated repo names to KEEP')
    parser.add_argument('--exclude', default=None,
                        help='set-repo-scope: comma-separated gitignore-style patterns to exclude')
    parser.add_argument('--include', default=None,
                        help='set-repo-scope: comma-separated patterns for gitignored first-party source')
    parser.add_argument('--reset', action='store_true',
                        help='set-repo-scope: clear the existing exclude list first')

    args = parser.parse_args()

    if args.command == 'init':
        try:
            result = init_project(
                args.project_root,
                args.json,
                max_repos=args.max_repos,
                force=args.force,
                run_index=not args.no_index,
            )
            if result.get('status') == 'needs_repo_selection':
                if args.json:
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                else:
                    print_scope_report(result['scope'])
                sys.exit(EXIT_NEEDS_REPO_SELECTION)

            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print("✓ Project initialized")
                print(f"  Root: {result['directories']['docs']}")
                print(f"  Repos in scope ({len(result['repos'])}): {', '.join(result['repos'])}")
                if result['excluded_repos']:
                    print(f"  Excluded by {CONFIG_FILENAME}: {', '.join(result['excluded_repos'])}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == 'update':
        try:
            result = update_project(
                args.project_root,
                args.json,
                max_repos=args.max_repos,
                force=args.force,
                run_index=not args.no_index,
            )
            if result.get('status') == 'needs_repo_selection':
                if args.json:
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                else:
                    print_scope_report(result['scope'])
                sys.exit(EXIT_NEEDS_REPO_SELECTION)

            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print("✓ Project updated")
                print(f"  Backup: {result['backup']}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == 'scan-repos':
        try:
            scope = evaluate_scope(args.project_root, max_repos=args.max_repos, force=args.force)
            payload = {
                'success': True,
                'status': 'needs_repo_selection' if scope['needs_selection'] else 'ok',
                'scope': scope,
                'suggested_config': suggest_config(scope),
            }
            if args.json:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                print_scope_report(scope)
            if scope['needs_selection']:
                sys.exit(EXIT_NEEDS_REPO_SELECTION)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == 'set-repo-scope':
        try:
            result = apply_repo_selection(
                args.project_root,
                keep=_split_list(args.repos),
                add_exclude=_split_list(args.exclude),
                add_include=_split_list(args.include),
                max_repos=args.max_repos,
                reset=args.reset,
            )
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(f"✓ Repo scope written to {result['config_file']}")
                print(f"  Active repos  : {', '.join(result['active_repos']) or '(none)'}")
                if result['excluded_repos']:
                    print(f"  Excluded repos: {', '.join(result['excluded_repos'])}")
                if result['unknown_repos']:
                    print(f"  ! Unknown repo names ignored: {', '.join(result['unknown_repos'])}")
                print(f"  {result['hint']}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == 'fetch-layered':
        try:
            result = fetch_layered_specs(args.project_root, args.json)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print("✓ Fetched layered specs")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == 'generate-modules':
        try:
            result = generate_module_designs(args.project_root, args.json)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                modules = result.get('modules', [])
                print(f"✓ Identified {len(modules)} modules")
                for m in modules:
                    print(f"  - {m}: {result.get('module_paths', {}).get(m, '')}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == 'merge':
        print("Error: `merge` is not implemented (merge_specs does not exist).")
        sys.exit(1)

    elif args.command == 'status':
        project_path = Path(args.project_root)
        docs = project_path / 'docs'

        files = {
            'rule.md': docs / 'rule.md',
            'language.json': docs / 'language.json',
            'relationship.md': docs / 'relationship.md',
            'graph.json': docs / 'graph.json',
            CONFIG_FILENAME: config_path(project_path),
        }

        status = {}
        for name, path in files.items():
            status[name] = 'exists' if path.exists() else 'missing'

        if args.json:
            print(json.dumps(status, indent=2, ensure_ascii=False))
        else:
            print("Docs Project Status:")
            for name, state in status.items():
                symbol = '✓' if state == 'exists' else '✗'
                print(f"  {symbol} {name}: {state}")

    elif args.command == 'check-sync':
        try:
            result = check_specs_need_sync(args.project_root, args.json)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()
