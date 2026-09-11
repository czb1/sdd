"""
Path utilities for core-design skill.
Provides path resolution by delegating to core-shared.
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
    
    opencode_config = os.environ.get('OPENCODE_CONFIG')
    if opencode_config:
        global_schemas = Path(opencode_config) / 'core-schemas'
        if global_schemas.exists():
            return global_schemas
    
    return Path(__file__).parent.parent.parent.parent / 'core-schemas'


def setup_core_paths():
    """Setup Python path to include core-shared modules."""
    # __file__ is at <skills>/core-design/scripts/cc_paths.py
    # Need to go up to <skills>/ then down to core-shared/scripts
    skills_dir = Path(__file__).parent.parent.parent
    shared_dir = skills_dir / 'core-shared' / 'scripts'
    if str(shared_dir) not in sys.path and shared_dir.exists():
        sys.path.insert(0, str(shared_dir))
