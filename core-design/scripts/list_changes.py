"""
List active changes in the project.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from cc_paths import setup_core_paths
setup_core_paths()

from core_schema import get_schema, DEFAULT_SCHEMA

METADATA_FILENAME = '.docs.yaml'


def get_change_metadata(change_dir: Path) -> Optional[Dict[str, Any]]:
    """Read change metadata."""
    metadata_path = change_dir / METADATA_FILENAME
    if not metadata_path.exists():
        return None
    
    import yaml
    with open(metadata_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_change_status(change_dir: Path, schema_name: str, project_root: str) -> Dict[str, Any]:
    """Get status of a single change."""
    try:
        schema_data = get_schema(schema_name, project_root)
        artifacts = schema_data.get('artifacts', [])
        
        completed = set()
        for artifact in artifacts:
            generates = artifact.get('generates', '')
            if not generates:
                continue
            
            full_pattern = change_dir / generates
            
            if '*' in generates or '?' in generates or '[' in generates:
                matches = list(change_dir.glob(generates))
                if matches:
                    completed.add(artifact['id'])
            else:
                if full_pattern.exists():
                    completed.add(artifact['id'])
        
        return {
            'completed': list(completed),
            'total': len(artifacts),
            'done_count': len(completed),
        }
    except Exception:
        return {'completed': [], 'total': 0, 'done_count': 0}


def list_changes(project_root: str, json_output: bool = False) -> List[Dict[str, Any]]:
    """
    List all active changes in the project.
    
    Args:
        project_root: Path to project root
        json_output: Whether to return JSON format
        
    Returns:
        List of change info dicts
    """
    changes_dir = Path(project_root) / 'docs' / 'changes'
    
    if not changes_dir.exists():
        return []
    
    changes = []
    
    for item in changes_dir.iterdir():
        if not item.is_dir():
            continue
        
        if item.name == 'archive':
            continue
        
        metadata = get_change_metadata(item)
        schema_name = metadata.get('schema', DEFAULT_SCHEMA) if metadata else DEFAULT_SCHEMA
        
        status = get_change_status(item, schema_name, project_root)
        
        last_modified = None
        if item.exists():
            mtime = item.stat().st_mtime
            last_modified = datetime.fromtimestamp(mtime).isoformat()
        
        change_info = {
            'name': item.name,
            'schema': schema_name,
            'change_dir': str(item),
            'artifacts_done': status.get('done_count', 0),
            'artifacts_total': status.get('total', 0),
            'lastModified': last_modified,
        }
        
        changes.append(change_info)
    
    changes.sort(key=lambda x: x.get('lastModified', ''), reverse=True)
    
    return changes
