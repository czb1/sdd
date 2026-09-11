"""
Get status of a change - shows artifact completion status.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from core_schema import get_schema
from core_change_context import load_change_context, format_change_status


def get_status(
    change_name: str,
    project_root: str,
    schema: Optional[str] = None,
    json_output: bool = False
) -> Dict[str, Any]:
    """
    Gets the status of a change.
    
    Args:
        change_name: Name of the change
        project_root: Project root directory
        schema: Optional schema name
        json_output: Whether to return JSON format
        
    Returns:
        Status dict with artifact statuses
    """
    context = load_change_context(project_root, change_name, schema)
    status = format_change_status(context)
    
    if json_output:
        return status
    
    return status


def print_status(status: Dict[str, Any]) -> str:
    """
    Formats status for text output.
    
    Args:
        status: Status dict from get_status
        
    Returns:
        Formatted text output
    """
    lines = []
    lines.append(f"Change: {status['changeName']}")
    lines.append(f"Schema: {status['schemaName']}")
    
    done_count = sum(1 for a in status['artifacts'] if a['status'] == 'done')
    total = len(status['artifacts'])
    lines.append(f"Progress: {done_count}/{total} artifacts complete")
    lines.append("")
    
    for artifact in status['artifacts']:
        status_str = artifact['status']
        if status_str == 'done':
            indicator = "[x]"
        elif status_str == 'ready':
            indicator = "[ ]"
        else:
            indicator = "[-]"
        
        line = f"{indicator} {artifact['id']}"
        if status_str == 'blocked' and artifact.get('missingDeps'):
            line += f" (blocked by: {', '.join(artifact['missingDeps'])})"
        
        lines.append(line)
    
    if status.get('isComplete'):
        lines.append("")
        lines.append("All artifacts complete!")
    
    return "\n".join(lines)
