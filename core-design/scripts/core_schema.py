"""
Schema management for CoreSpec.

Handles loading, validating, and resolving schemas.
"""

import os
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any, Union


# Default schema name
DEFAULT_SCHEMA = 'spec-driven'


def get_opencode_global_dir() -> Optional[Path]:
    """
    Gets the OpenCode global config directory.
    
    Returns:
        Path to OpenCode global config directory, or None if not found
    """
    # Standard OpenCode global config location on Windows
    opencode_config = Path(os.environ.get('OPENCODE_CONFIG', str(Path.home() / '.config' / 'opencode')))
    if opencode_config.exists():
        return opencode_config
    return None


def get_package_schemas_dir() -> Path:
    """
    Gets the package's built-in core-schemas directory path.
    
    Resolution order:
    1. OpenCode global config: <OPENCODE_CONFIG>/core-schemas
    2. Package local: <skillDir>/../../core-schemas (与skills同级)
    
    Returns:
        Path to the core-schemas directory
    """
    # 1. Check OpenCode global config first (与skills同级)
    global_dir = get_opencode_global_dir()
    if global_dir:
        global_schemas = global_dir / 'core-schemas'
        if global_schemas.exists():
            return global_schemas
    
    # 2. Fallback to package local (core-schemas 与 skills 同级)
    skill_dir = Path(__file__).parent.parent.parent  # scripts/ → core-design/ → skills/
    return skill_dir.parent / 'core-schemas'


def get_schema_dir(schema_name: str, project_root: Optional[str] = None) -> Optional[str]:
    """
    Resolves a schema name to its directory path.
    
    Resolution order:
    1. Project-local: <projectRoot>/core-schemas/<name>/schema.yaml
    2. OpenCode global: <OPENCODE_CONFIG>/core-schemas/<name>/schema.yaml (与skills同级)
    3. User override: ${XDG_DATA_HOME}/core-schemas/<name>/schema.yaml
    4. Package built-in: <package>/core-schemas/<name>/schema.yaml
    
    Args:
        schema_name: Schema name (e.g., "spec-driven")
        project_root: Optional project root directory
        
    Returns:
        Path to the schema directory, or None if not found
    """
    # 1. Check project-local core-schemas directory
    if project_root:
        project_dir = Path(project_root) / 'core-schemas' / schema_name
        if project_dir.exists():
            return str(project_dir)
    
    # 2. Check OpenCode global config (与skills同级)
    global_dir = get_opencode_global_dir()
    if global_dir:
        global_schemas = global_dir / 'core-schemas' / schema_name
        if global_schemas.exists():
            return str(global_schemas)
    
    # 3. Check user override directory
    xdg_data = os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))
    user_dir = Path(xdg_data) / 'core-schemas' / schema_name
    if user_dir.exists():
        return str(user_dir)
    
    # 4. Check package built-in
    package_dir = get_package_schemas_dir() / schema_name
    if package_dir.exists():
        return str(package_dir)
    
    return None


def load_schema(schema_name: str, project_root: Optional[str] = None) -> Dict[str, Any]:
    """
    Loads a schema by name.
    
    Args:
        schema_name: Name of the schema to load
        project_root: Optional project root for local schema resolution
        
    Returns:
        Schema dictionary
        
    Raises:
        FileNotFoundError: If schema not found
        yaml.YAMLError: If schema is invalid YAML
    """
    schema_dir = get_schema_dir(schema_name, project_root)
    if not schema_dir:
        raise FileNotFoundError(f"Schema '{schema_name}' not found")
    
    schema_path = Path(schema_dir) / 'schema.yaml'
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def list_schemas(project_root: Optional[str] = None) -> List[str]:
    """
    Lists all available schemas.
    
    Args:
        project_root: Optional project root for local schema resolution
        
    Returns:
        List of schema names
    """
    schemas = set()
    
    # 1. Check project-local core-schemas
    if project_root:
        project_schemas_dir = Path(project_root) / 'core-schemas'
        if project_schemas_dir.exists():
            for item in project_schemas_dir.iterdir():
                if item.is_dir() and (item / 'schema.yaml').exists():
                    schemas.add(item.name)
    
    # 2. Check OpenCode global config (与skills同级)
    global_dir = get_opencode_global_dir()
    if global_dir:
        global_schemas_dir = global_dir / 'core-schemas'
        if global_schemas_dir.exists():
            for item in global_schemas_dir.iterdir():
                if item.is_dir() and (item / 'schema.yaml').exists():
                    schemas.add(item.name)
    
    # 3. Check user override schemas
    xdg_data = os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))
    user_schemas_dir = Path(xdg_data) / 'core-schemas'
    if user_schemas_dir.exists():
        for item in user_schemas_dir.iterdir():
            if item.is_dir() and (item / 'schema.yaml').exists():
                schemas.add(item.name)
    
    # 4. Check package built-in schemas
    package_schemas_dir = get_package_schemas_dir()
    if package_schemas_dir.exists():
        for item in package_schemas_dir.iterdir():
            if item.is_dir() and (item / 'schema.yaml').exists():
                schemas.add(item.name)
    
    return sorted(schemas)


def get_schema(schema_name: str, project_root: Optional[str] = None) -> Dict[str, Any]:
    """
    Gets a schema by name with default fallback.
    
    Args:
        schema_name: Name of the schema (or empty for default)
        project_root: Optional project root
        
    Returns:
        Schema dictionary
    """
    if not schema_name:
        schema_name = DEFAULT_SCHEMA
    
    return load_schema(schema_name, project_root)


def get_artifacts(schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extracts artifact definitions from a schema.
    
    Args:
        schema: Schema dictionary
        
    Returns:
        List of artifact definitions
    """
    return schema.get('artifacts', [])


def get_first_ready_artifact(artifacts: List[Dict[str, Any]], completed: List[str]) -> Optional[Dict[str, Any]]:
    """
    Gets the first artifact that is ready to be created.
    
    An artifact is ready if:
    1. It hasn't been completed
    2. All its required artifacts are completed
    
    Args:
        artifacts: List of artifact definitions
        completed: List of completed artifact IDs
        
    Returns:
        First ready artifact, or None if all complete
    """
    for artifact in artifacts:
        artifact_id = artifact.get('id')
        if artifact_id in completed:
            continue
        
        # Check if all requirements are met
        requires = artifact.get('requires', [])
        if all(req in completed for req in requires):
            return artifact
    
    return None
