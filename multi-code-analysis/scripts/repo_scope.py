"""
Repo scope guard for multi-code-analysis.

Why this exists
---------------
multi-code-analysis v5.0 reads `codegraph.db`, and `codegraph index` already
honours `codegraph.json` - so the SQL-based flow is scope-safe for free.

But two code paths in `main.py` still enumerate the filesystem themselves and
bypass that config entirely:

  - `tree-all`  : walks `root.iterdir()` looking for `.git` -> writes one
                  `docs/codeCapInfo/<repo>/` per repo found
  - `scan` /
    `scan-deps` : legacy scanner.py path, walks every repo under root

On a workspace directory holding dozens of clones, both explode. This module
reuses core-shared/scripts/repo_config.py (the same filter core-init writes)
so every entry point agrees on which repos are in scope.
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple

EXIT_NEEDS_REPO_SELECTION = 3


def _bootstrap_shared() -> Optional[Path]:
    """Put core-shared/scripts on sys.path (OpenCode + ClaudeCode layouts)."""
    here = Path(__file__).resolve()
    candidates = []
    for parent in here.parents:
        if parent.name == 'skills':
            candidates.append(parent / 'core-shared' / 'scripts')
            break
    candidates += [
        Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts',
        Path.home() / '.cac' / 'skills' / 'core-shared' / 'scripts',
    ]
    for candidate in candidates:
        if (candidate / 'repo_config.py').exists():
            if str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
            return candidate
    return None


_bootstrap_shared()

try:
    from repo_config import (  # noqa: E402
        CONFIG_FILENAME,
        evaluate_scope,
        get_exclude_patterns,
        is_excluded,
        load_config,
        norm,
        print_scope_report,
    )
    _AVAILABLE = True
except ImportError:  # core-shared not installed -> degrade, never break
    _AVAILABLE = False
    CONFIG_FILENAME = 'codegraph.json'


def scope_available() -> bool:
    return _AVAILABLE


def guard_scope(root, max_repos: Optional[int] = None, force: bool = False) -> Optional[dict]:
    """
    Stop the command when the directory holds more repos than allowed.

    Exits with code 3 (needs_repo_selection) so the SKILL layer treats it as
    "ask the user", not as a failure. Returns the scope dict when OK.
    """
    if not _AVAILABLE:
        print(f"[multi-code-analysis] WARNING: core-shared/repo_config.py not found; "
              f"{CONFIG_FILENAME} scope filter is INACTIVE")
        return None

    scope = evaluate_scope(root, max_repos=max_repos, force=force)
    if scope['needs_selection']:
        print_scope_report(scope)
        print("\nRun `/core-init` first to confirm the repo scope, "
              f"or edit {CONFIG_FILENAME} by hand.")
        sys.exit(EXIT_NEEDS_REPO_SELECTION)

    if scope['excluded_repos']:
        names = ', '.join(r['name'] for r in scope['excluded_repos'])
        print(f"[multi-code-analysis] excluded by {CONFIG_FILENAME}: {names}")
    return scope


def filter_repo_dirs(root, dirs: List[Path]) -> Tuple[List[Path], List[Path]]:
    """
    Split a list of candidate repo directories into (kept, skipped) according
    to `codegraph.json`'s exclude patterns.
    """
    if not _AVAILABLE:
        return list(dirs), []

    root_path = Path(root).resolve()
    exclude = get_exclude_patterns(load_config(root_path))
    if not exclude:
        return list(dirs), []

    kept, skipped = [], []
    for directory in dirs:
        try:
            rel = norm(Path(directory).resolve().relative_to(root_path))
        except ValueError:
            kept.append(directory)
            continue
        (skipped if (rel and is_excluded(rel, exclude)) else kept).append(directory)
    return kept, skipped


def scoped_repo_paths(root, scope: Optional[dict] = None) -> List[Path]:
    """Absolute paths of the repos that are in scope."""
    if not _AVAILABLE:
        return [Path(root).resolve()]
    scope = scope or evaluate_scope(root, force=True)
    return [Path(r['path']) for r in scope['repos']]
