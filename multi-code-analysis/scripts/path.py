"""
Path utilities for multi-code-analysis skill.
Provides path resolution for project root detection.

Fixed in this version
---------------------
`get_multi_repo_root()` had two independent defects that together could point
the whole analysis at a user's home directory:

  1. It iterated `cwd.parents` and **never looked at `cwd` itself**, so running
     from the actual project root skipped it and climbed upwards.
  2. `'docs'` is far too weak a marker. An unrelated `~/work/docs` made `~/work`
     the "multi-repo root" for anything under `~/work/*/`, and a `~/docs` made
     it the home directory - after which scan-deps / tree-all would walk every
     repo the user owns.

Now:
  - `cwd` is checked first, then ancestors, nearest-first
  - strong markers (written by core-init / codegraph) win over weak ones
  - the search never returns `$HOME` or a filesystem root
  - ascent is capped (MAX_ASCEND)
  - `CORESPEC_PROJECT_ROOT` overrides everything (explicit escape hatch)
"""

import os
import sys
from pathlib import Path
from typing import List, Optional

# How many levels above cwd we are willing to look.
MAX_ASCEND = 6

# Unambiguous "this is a CoreSpec / CodeGraph project root" markers.
STRONG_MARKERS = [
    'docs/language.json',    # written by core-init scan_language.py
    'codegraph.json',        # repo scope config
    '.codegraph',            # codegraph.db lives here
    'docs/graph.json',
    'docs/codeCapInfo',
]

# Weaker hints, only used when no strong marker exists anywhere in range.
WEAK_MARKERS = [
    'docs/specs',
    'docs/changes',
    'directory_trees',
    'dep_graph',
    '.multi_code_source',
]


def _boundaries() -> List[Path]:
    """Directories we must never return or ascend past."""
    stops = []
    try:
        stops.append(Path.home().resolve())
    except (RuntimeError, OSError):
        pass
    return stops


def _search_roots(start: Optional[Path] = None) -> List[Path]:
    """
    Candidate roots, nearest first: cwd itself, then ancestors.

    Stops before $HOME and before the filesystem root, and never ascends more
    than MAX_ASCEND levels.
    """
    current = (start or Path(os.getcwd())).resolve()
    stops = _boundaries()
    candidates: List[Path] = []

    for _ in range(MAX_ASCEND + 1):
        candidates.append(current)
        parent = current.parent
        if parent == current:          # filesystem root reached
            break
        if current in stops:           # don't ascend past $HOME
            break
        if parent in stops:            # ...and don't return $HOME itself
            break
        if parent.parent == parent:    # parent is the filesystem root
            break
        current = parent

    return candidates


def _has_marker(path: Path, markers: List[str]) -> Optional[str]:
    for marker in markers:
        if (path / marker).exists():
            return marker
    return None


def get_project_root(project_root: Optional[str] = None) -> Path:
    """
    Get the project root directory.

    Auto-detects by looking for a CoreSpec `docs/` directory if not explicitly
    provided. (The legacy `corespec/` directory name is still accepted.)

    Args:
        project_root: Explicit project root, or None to auto-detect

    Returns:
        Path to project root
    """
    if project_root:
        return Path(project_root)

    env = os.environ.get('CORESPEC_PROJECT_ROOT')
    if env:
        return Path(env)

    for candidate in _search_roots():
        if _has_marker(candidate, STRONG_MARKERS):
            return candidate

    for candidate in _search_roots():
        if (candidate / 'docs').is_dir() or (candidate / 'corespec').is_dir():
            return candidate

    return Path(os.getcwd())


def get_multi_repo_root(multi_repo_path: Optional[str] = None, explain: bool = False) -> Path:
    """
    Get the multi-repo root directory.

    Resolution order:
      1. explicit argument
      2. CORESPEC_PROJECT_ROOT environment variable
      3. nearest ancestor (cwd first) carrying a STRONG marker
      4. nearest ancestor carrying a WEAK marker
      5. nearest enclosing git repository
      6. cwd

    Never returns $HOME or a filesystem root.

    Args:
        multi_repo_path: Explicit path, or None to auto-detect
        explain: Print how the root was resolved

    Returns:
        Path to multi-repo root
    """
    if multi_repo_path:
        return Path(multi_repo_path)

    env = os.environ.get('CORESPEC_PROJECT_ROOT')
    if env:
        if explain:
            print(f"  multi-repo root from CORESPEC_PROJECT_ROOT: {env}")
        return Path(env)

    candidates = _search_roots()

    for candidate in candidates:
        marker = _has_marker(candidate, STRONG_MARKERS)
        if marker:
            if explain:
                print(f"  multi-repo root: {candidate}  (marker: {marker})")
            return candidate

    for candidate in candidates:
        marker = _has_marker(candidate, WEAK_MARKERS)
        if marker:
            if explain:
                print(f"  multi-repo root: {candidate}  (weak marker: {marker})")
            return candidate

    for candidate in candidates:
        if (candidate / '.git').exists():
            if explain:
                print(f"  multi-repo root: {candidate}  (git repository)")
            return candidate

    cwd = Path(os.getcwd()).resolve()
    if explain:
        print(f"  multi-repo root: {cwd}  (no marker found, using cwd)")
    return cwd


def get_script_dir() -> Path:
    """Get the scripts directory."""
    return Path(__file__).parent


def get_output_dir(name: str = 'dep_graph', project_root: Optional[str] = None) -> Path:
    """
    Get output directory for given name.

    Args:
        name: Output directory name (e.g. 'dep_graph', 'directory_trees')
        project_root: Explicit project root, or None to auto-detect

    Returns:
        Path to output directory
    """
    root = get_project_root(project_root)
    output_dir = root / name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
