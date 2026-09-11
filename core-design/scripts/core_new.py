"""
Create a new change in CoreSpec.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from core_validate_name import validate_change_name, derive_name_from_description
from core_schema import get_schema, DEFAULT_SCHEMA


def get_project_config(project_root: str) -> Optional[Dict[str, Any]]:
    """
    Reads the CoreSpec project config.
    
    Args:
        project_root: Path to the project root
        
    Returns:
        Config dict or None if not found
    """
    config_path = Path(project_root) / 'docs' / 'config.yaml'
    if not config_path.exists():
        return None
    
    import yaml
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def write_change_metadata(change_dir: Path, metadata: Dict[str, Any], project_root: str) -> None:
    """
    Writes the change metadata file.
    
    Args:
        change_dir: Path to the change directory
        metadata: Metadata to write
        project_root: Project root path
    """
    metadata_file = change_dir / '.docs.yaml'
    
    with open(metadata_file, 'w', encoding='utf-8') as f:
        yaml.dump(metadata, f, default_flow_style=False)


def create_change(
    name: str,
    project_root: str,
    schema: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a new change directory with metadata file.
    
    Args:
        name: The change name (must be valid kebab-case)
        project_root: The root directory of the project
        schema: Optional schema name (default: spec-driven)
        description: Optional description for the change
        
    Returns:
        Dict with 'schema' and 'change_dir' keys
        
    Raises:
        ValueError: If name is invalid or change already exists
    """
    # Validate the name first
    valid, error = validate_change_name(name)
    if not valid:
        raise ValueError(f"Invalid change name '{name}': {error}")
    
    # Determine schema: explicit option → project config → hardcoded default
    if not schema:
        try:
            config = get_project_config(project_root)
            schema = config.get('schema', DEFAULT_SCHEMA) if config else DEFAULT_SCHEMA
        except Exception:
            schema = DEFAULT_SCHEMA
    
    # Build the change directory path
    change_dir = Path(project_root) / 'docs' / 'changes' / name
    
    # Check if change already exists
    if change_dir.exists():
        raise ValueError(f"Change '{name}' already exists at {change_dir}")
    
    # Create the directory (including parent directories if needed)
    change_dir.mkdir(parents=True, exist_ok=True)
    
    # Write metadata file with schema and creation date
    today = datetime.now().isoformat().split('T')[0]
    write_change_metadata(change_dir, {
        'schema': schema,
        'created': today,
    }, project_root)
    
    # If description provided, create README.md
    if description:
        readme_path = change_dir / 'README.md'
        readme_path.write_text(f"# {name}\n\n{description}\n", encoding='utf-8')
    
    return {
        'schema': schema,
        'change_dir': str(change_dir),
        'name': name,
    }


def handle_new_change(
    user_input: str,
    project_root: str,
    schema: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handles the full new change workflow.
    
    Args:
        user_input: The user's input (change name or description)
        project_root: Path to the project root
        schema: Optional schema name
        
    Returns:
        Result dict with change info and next steps
    """
    # If no input, we need to ask the user
    if not user_input or not user_input.strip():
        return {
            'needs_input': True,
            'prompt': 'What change do you want to work on? Describe what you want to build or fix.'
        }
    
    # Try to derive name from input if it looks like a description
    name = user_input.strip()
    
    # Check if it's already a valid name
    valid, error = validate_change_name(name)
    if not valid:
        # Try to derive a valid name from the description
        name = derive_name_from_description(name)
        valid, error = validate_change_name(name)
        if not valid:
            raise ValueError(f"Could not derive valid change name: {error}")
    
    # Create the change
    result = create_change(name, project_root, schema)
    
    # Get schema to find first artifact
    schema_data = get_schema(result['schema'], project_root)
    artifacts = schema_data.get('artifacts', [])
    first_artifact = artifacts[0] if artifacts else None
    
    return {
        'needs_input': False,
        'change_name': result['name'],
        'change_dir': result['change_dir'],
        'schema': result['schema'],
        'artifacts': [a['id'] for a in artifacts],
        'first_artifact': first_artifact['id'] if first_artifact else None,
        'first_artifact_instruction': first_artifact.get('instruction', '') if first_artifact else '',
    }
