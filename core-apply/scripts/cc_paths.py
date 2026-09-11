"""
Path utilities for core-apply skill.
Delegates to core-shared for shared path resolution.
"""

import os
import sys
from pathlib import Path
from typing import Optional


def get_project_root(project_root: Optional[str] = None) -> Path:
    """Get the project root directory."""
    if project_root:
        return Path(project_root)
    return Path(os.getcwd())


def get_docs_dir(project_root: Optional[str] = None) -> Path:
    """Get the docs directory path."""
    return get_project_root(project_root) / 'docs'


def get_changes_dir(project_root: Optional[str] = None) -> Path:
    """Get the changes directory path."""
    return get_docs_dir(project_root) / 'changes'


def get_schemas_dir(project_root: Optional[str] = None) -> Path:
    """Get the schemas directory path."""
    docs_dir = get_docs_dir(project_root)
    local_schemas = docs_dir / 'core-schemas'
    if local_schemas.exists():
        return local_schemas

    # Delegate to core-shared for global schemas resolution
    skills_dir = Path(__file__).parent.parent.parent
    shared_dir = skills_dir / 'core-shared' / 'scripts'
    if str(shared_dir) not in sys.path and shared_dir.exists():
        sys.path.insert(0, str(shared_dir))
    try:
        from core_paths import get_opencode_config_dir
        opencode_config = get_opencode_config_dir()
        if opencode_config:
            global_schemas = opencode_config / 'core-schemas'
            if global_schemas.exists():
                return global_schemas
    except ImportError:
        pass

    return Path(__file__).parent.parent.parent.parent / 'core-schemas'


def setup_core_paths():
    """Setup Python path to include core-shared modules."""
    skills_dir = Path(__file__).parent.parent.parent
    shared_dir = skills_dir / 'core-shared' / 'scripts'
    if str(shared_dir) not in sys.path and shared_dir.exists():
        sys.path.insert(0, str(shared_dir))
