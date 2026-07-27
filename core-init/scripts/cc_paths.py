"""
Path utilities for core-* skills.
Provides path resolution for both local and global modes.

Fixed in this version:
  - `setup_core_paths()` pointed at `<skill>/core-shared/scripts` instead of
    `<skills_root>/core-shared/scripts`, so shared modules were never importable.
    It now probes a list of candidates and returns the one it found.
  - Added `get_opencode_config_dir()` / `get_skills_dir()`, which every SKILL.md
    bootstrap snippet (`from core_paths import get_opencode_config_dir`) needs
    but which did not exist.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional


# --------------------------------------------------------------- config dirs
def _config_dir_candidates() -> List[Path]:
    """Candidate agent config dirs, most specific first."""
    candidates: List[Path] = []

    env = os.environ.get('OPENCODE_CONFIG') or os.environ.get('CAC_CONFIG')
    if env:
        candidates.append(Path(env))

    # Walk up from this file: .../<config_dir>/skills/core-shared/scripts/core_paths.py
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == 'skills':
            candidates.append(parent.parent)
            break

    candidates.append(Path.home() / '.config' / 'opencode')   # OpenCode
    candidates.append(Path.home() / '.cac')                   # ClaudeCode
    return candidates


def get_opencode_config_dir() -> Path:
    """
    Resolve the agent config directory (the one containing `skills/`).

    Supports both OpenCode (~/.config/opencode) and ClaudeCode (~/.cac), plus
    the OPENCODE_CONFIG / CAC_CONFIG environment variables.
    """
    for candidate in _config_dir_candidates():
        if (candidate / 'skills').is_dir():
            return candidate

    # Nothing found: fall back to the conventional location rather than raising,
    # so callers fail with a clear "file not found" instead of an import error.
    return Path.home() / '.config' / 'opencode'


def get_skills_dir() -> Path:
    """Directory containing all core-* skills."""
    return get_opencode_config_dir() / 'skills'


def get_skill_script(skill_name: str, script: str = 'main.py') -> Path:
    """Absolute path to a script inside a sibling skill."""
    return get_skills_dir() / skill_name / 'scripts' / script


def get_project_root(project_root: Optional[str] = None) -> Path:
    """
    Get the project root directory.

    Args:
        project_root: Explicit project root, or None to use cwd

    Returns:
        Path to project root
    """
    if project_root:
        return Path(project_root)
    return Path(os.getcwd())


def get_docs_dir(project_root: Optional[str] = None) -> Path:
    """
    Get the docs directory path (was corespec).

    Args:
        project_root: Explicit project root, or None to use cwd

    Returns:
        Path to docs directory
    """
    return get_project_root(project_root) / 'docs'


def get_changes_dir(project_root: Optional[str] = None) -> Path:
    """
    Get the changes directory path.

    Args:
        project_root: Explicit project root, or None to use cwd

    Returns:
        Path to changes directory
    """
    return get_docs_dir(project_root) / 'changes'


def get_change_dir(change_name: str, project_root: Optional[str] = None) -> Path:
    """
    Get a specific change directory path.

    Args:
        change_name: Name of the change
        project_root: Explicit project root, or None to use cwd

    Returns:
        Path to change directory
    """
    return get_changes_dir(project_root) / change_name


def get_specs_dir(project_root: Optional[str] = None) -> Path:
    """
    Get the main specs directory path.

    Args:
        project_root: Explicit project root, or None to use cwd

    Returns:
        Path to specs directory
    """
    return get_docs_dir(project_root) / 'specs'


def get_module_spec_dir(module_name: str, project_root: Optional[str] = None) -> Path:
    """
    Get a specific module's spec directory path.

    Args:
        module_name: Name of the module
        project_root: Explicit project root, or None to use cwd

    Returns:
        Path to module spec directory
    """
    return get_specs_dir(project_root) / module_name


def get_archive_dir(project_root: Optional[str] = None) -> Path:
    """
    Get the archive directory path.

    Args:
        project_root: Explicit project root, or None to use cwd

    Returns:
        Path to archive directory
    """
    return get_docs_dir(project_root) / 'archive'


def get_schemas_dir(project_root: Optional[str] = None) -> Path:
    """
    Get the schemas directory path.

    Args:
        project_root: Explicit project root, or None to use cwd

    Returns:
        Path to schemas directory
    """
    docs_dir = get_docs_dir(project_root)
    local_schemas = docs_dir / 'core-schemas'
    if local_schemas.exists():
        return local_schemas

    opencode_config = os.environ.get('OPENCODE_CONFIG')
    if opencode_config:
        global_schemas = Path(opencode_config) / 'core-schemas'
        if global_schemas.exists():
            return global_schemas

    return Path(__file__).parent.parent.parent / 'core-schemas'


def get_codegraph_config(project_root: Optional[str] = None) -> Path:
    """Path to the (optional) codegraph.json that defines repo scope."""
    return get_project_root(project_root) / 'codegraph.json'


def _shared_scripts_candidates() -> List[Path]:
    here = Path(__file__).resolve()
    candidates = [here.parent]  # we may already be core-shared/scripts

    # <skills_root>/<skill>/scripts/x.py -> <skills_root>/core-shared/scripts
    for parent in here.parents:
        if parent.name == 'skills':
            candidates.append(parent / 'core-shared' / 'scripts')
            break

    for config_dir in _config_dir_candidates():
        candidates.append(config_dir / 'skills' / 'core-shared' / 'scripts')

    return candidates


def setup_core_paths() -> Optional[Path]:
    """
    Setup Python path to include shared modules.
    This allows other skills to use core-shared modules.

    Returns the shared scripts directory that was added, or None if no
    candidate exists on disk.
    """
    for shared_dir in _shared_scripts_candidates():
        if shared_dir.is_dir():
            if str(shared_dir) not in sys.path:
                sys.path.insert(0, str(shared_dir))
            return shared_dir
    return None
