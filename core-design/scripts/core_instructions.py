"""
Load instructions for creating an artifact.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from core_change_context import load_change_context
from core_schema import get_schema


def get_template_path(schema_name: str, template_name: str, project_root: Optional[str] = None) -> Optional[str]:
    """
    Gets the full path to a template file.
    
    Args:
        schema_name: Schema name (e.g., "spec-driven")
        template_name: Template filename (e.g., "proposal.md")
        project_root: Optional project root
        
    Returns:
        Full path to template, or None if not found
    """
    schema_dir = get_schema_dir(schema_name, project_root)
    if not schema_dir:
        return None
    
    template_path = Path(schema_dir) / 'templates' / template_name
    if template_path.exists():
        return str(template_path)
    
    return None


def get_schema_dir(schema_name: str, project_root: Optional[str] = None) -> Optional[str]:
    """
    Resolves a schema name to its directory path.
    
    Args:
        schema_name: Schema name
        project_root: Optional project root
        
    Returns:
        Path to schema directory, or None if not found
    """
    from core_schema import get_schema_dir as schema_get_dir
    return schema_get_dir(schema_name, project_root)


def load_template_content(schema_name: str, template_name: str, project_root: Optional[str] = None) -> str:
    """
    Loads template content.
    
    Args:
        schema_name: Schema name
        template_name: Template filename
        project_root: Optional project root
        
    Returns:
        Template content
        
    Raises:
        FileNotFoundError: If template not found
    """
    template_path = get_template_path(schema_name, template_name, project_root)
    if not template_path:
        raise FileNotFoundError(f"Template '{template_name}' not found in schema '{schema_name}'")
    
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def get_instructions(
    change_name: str,
    artifact_id: str,
    project_root: str,
    schema: Optional[str] = None,
    design_rules: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Gets instructions for creating an artifact.
    
    Args:
        change_name: Change name
        artifact_id: Artifact ID to get instructions for
        project_root: Project root directory
        schema: Optional schema name
        
    Returns:
        Instructions dict with template, dependencies, etc.
    """
    context = load_change_context(project_root, change_name, schema,design_rules)
    
    artifact = context.graph.get_artifact(artifact_id)
    if not artifact:
        raise ValueError(f"Artifact '{artifact_id}' not found in schema '{context.schema_name}'")
    
    template_content = load_template_content(
        context.schema_name,
        artifact.get('template', ''),
        project_root
    )
    
    dependencies = []
    for dep_id in artifact.get('requires', []):
        dep_artifact = context.graph.get_artifact(dep_id)
        dependencies.append({
            'id': dep_id,
            'done': dep_id in context.completed,
            'path': dep_artifact.get('generates', '') if dep_artifact else '',
            'description': dep_artifact.get('description', '') if dep_artifact else '',
        })
    
    unlocks = []
    for a in context.graph.get_all_artifacts():
        if artifact_id in a.get('requires', []):
            unlocks.append(a['id'])
    unlocks.sort()
    
    return {
        'changeName': context.change_name,
        'artifactId': artifact_id,
        'schemaName': context.schema_name,
        'changeDir': context.change_dir,
        'outputPath': artifact.get('generates', ''),
        'description': artifact.get('description', ''),
        'instruction': artifact.get('instruction', ''),
        'template': template_content,
        'dependencies': dependencies,
        'unlocks': unlocks,
    }
