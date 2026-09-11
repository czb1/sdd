"""
Apply tasks - get instructions and manage task completion.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from cc_paths import setup_core_paths
setup_core_paths()

from change_context import load_change_context, format_change_status
from schema import get_schema


def resolve_generates_path(generates: str, change_dir: Path) -> Path:
    """Resolve artifact generates path."""
    return change_dir / generates


def get_apply_instructions(
    change_name: str,
    project_root: str,
    schema: Optional[str] = None,
    json_output: bool = False
) -> Dict[str, Any]:
    """
    Get instructions for applying tasks from a change.
    
    Args:
        change_name: Name of the change
        project_root: Project root directory
        schema: Optional schema name
        json_output: Whether to return JSON format
        
    Returns:
        Dict with apply instructions
    """
    context = load_change_context(project_root, change_name, schema)
    
    schema_data = get_schema(context.schema_name, project_root)
    apply_config = schema_data.get('apply', {})
    
    tasks_artifact_id = apply_config.get('tracks', 'tasks')
    tasks_file_pattern = apply_config.get('requires', [tasks_artifact_id])
    
    if not tasks_file_pattern:
        tasks_file_pattern = [tasks_artifact_id]
    
    tasks_path = None
    for artifact in context.graph.get_all_artifacts():
        if artifact['id'] == tasks_artifact_id:
            generates = artifact.get('generates', '')
            if generates:
                tasks_path = resolve_generates_path(generates, Path(context.change_dir))
                break
    
    if not tasks_path or not tasks_path.exists():
        return {
            'changeName': change_name,
            'schemaName': context.schema_name,
            'state': 'blocked',
            'message': f'No tasks file found at expected location',
            'complete': 0,
            'total': 0,
            'tasks': [],
            'contextFiles': [],
            'instruction': 'No tasks found. Use /core-design to create the tasks artifact first.',
        }
    
    tasks = parse_tasks(str(tasks_path))
    complete_count = sum(1 for t in tasks if t['done'])
    total_count = len(tasks)
    
    context_files = []
    for artifact in context.graph.get_all_artifacts():
        generates = artifact.get('generates', '')
        if generates and artifact['id'] in context.completed:
            resolved_path = resolve_generates_path(generates, Path(context.change_dir))
            context_files.append(str(resolved_path))
    
    is_complete = complete_count == total_count and total_count > 0
    
    state = 'all_done' if is_complete else ('ready' if total_count > 0 else 'blocked')
    
    return {
        'changeName': change_name,
        'schemaName': context.schema_name,
        'state': state,
        'complete': complete_count,
        'total': total_count,
        'tasks': tasks,
        'contextFiles': context_files,
        'instruction': apply_config.get('instruction', 'Implement the tasks listed above.'),
    }


def parse_tasks(tasks_file_path: str) -> List[Dict[str, Any]]:
    """
    Parse tasks from a tasks.md file.
    
    Args:
        tasks_file_path: Path to the tasks file
        
    Returns:
        List of task dicts with 'text' and 'done' keys
    """
    tasks_path = Path(tasks_file_path)
    if not tasks_path.exists():
        return []
    
    content = tasks_path.read_text(encoding='utf-8')
    
    tasks = []
    task_pattern = re.compile(r'^-\s*\[([ x])\]\s*(.+)$', re.MULTILINE)
    
    for match in task_pattern.finditer(content):
        done = match.group(1).lower() == 'x'
        text = match.group(2).strip()
        tasks.append({'text': text, 'done': done})
    
    return tasks


def update_task_status(
    tasks_file_path: str,
    task_index: int,
    done: bool = True
) -> Dict[str, Any]:
    """
    Update the status of a task in the tasks file.
    
    Args:
        tasks_file_path: Path to the tasks file
        task_index: Index of the task (0-based)
        done: Whether to mark as done
        
    Returns:
        Dict with updated task info
    """
    tasks_path = Path(tasks_file_path)
    if not tasks_path.exists():
        raise FileNotFoundError(f"Tasks file not found: {tasks_file_path}")
    
    content = tasks_path.read_text(encoding='utf-8')
    
    task_pattern = re.compile(r'^(- )\[([ x])\](.*)$', re.MULTILINE)
    
    matches = list(task_pattern.finditer(content))
    
    if task_index < 0 or task_index >= len(matches):
        raise IndexError(f"Task index {task_index} out of range")
    
    match = matches[task_index]
    prefix = match.group(1)
    old_status = match.group(2)
    task_text = match.group(3)
    
    new_status = 'x' if done else ' '
    
    new_line = f"{prefix}[{new_status}]{task_text}"
    new_content = content[:match.start()] + new_line + content[match.end():]
    
    tasks_path.write_text(new_content, encoding='utf-8')
    
    return {
        'task_index': task_index,
        'text': task_text.strip(),
        'done': done,
    }


def parse_tasks_multi(
    project_root: str,
    change_name: str,
    repos: List[str],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parse tasks from multiple repos for multi-repo mode.

    Reads tasks.md from each repo's change directory and returns
    a mapping of repo name to task list.

    Args:
        project_root: Project root directory
        change_name: Name of the change
        repos: List of repo names to parse

    Returns:
        {repo_name: [{"text": str, "done": bool}]}
    """
    root_path = Path(project_root)
    result: Dict[str, List[Dict[str, Any]]] = {}

    for repo in repos:
        tasks_file = root_path / repo / "docs" / "changes" / change_name / "tasks.md"
        if tasks_file.exists():
            result[repo] = parse_tasks(str(tasks_file))
        else:
            result[repo] = []

    return result


def update_task_status_multi(
    project_root: str,
    change_name: str,
    repo: str,
    task_index: int,
    done: bool = True,
) -> Dict[str, Any]:
    """
    Update task status in a specific repo's tasks.md.

    Args:
        project_root: Project root directory
        change_name: Name of the change
        repo: Repo name whose tasks.md to update
        task_index: Index of the task (0-based)
        done: Whether to mark as done

    Returns:
        Dict with updated task info

    Raises:
        FileNotFoundError: If the repo's tasks.md does not exist
        IndexError: If task_index is out of range
    """
    root_path = Path(project_root)
    tasks_file = root_path / repo / "docs" / "changes" / change_name / "tasks.md"
    return update_task_status(str(tasks_file), task_index, done)


def _add_dependency_edge(
    adj: Dict[str, List[str]],
    in_degree: Dict[str, int],
    repo_set: set,
    definition_repo: str,
    consumer: str,
) -> None:
    """Add a dependency edge from definition_repo to consumer if valid."""
    if consumer in repo_set and consumer != definition_repo:
        adj[definition_repo].append(consumer)
        in_degree[consumer] = in_degree.get(consumer, 0) + 1


def _build_dependency_graph(
    repos: List[str],
    contracts_data: Dict,
) -> Tuple[Dict[str, List[str]], Dict[str, int]]:
    """Build adjacency list and in-degree map from contracts data.

    Args:
        repos: List of repo names
        contracts_data: Parsed cross_repo_contracts.json data

    Returns:
        (adjacency_list, in_degree_map) tuple
    """
    repo_set = set(repos)
    adj: Dict[str, List[str]] = {repo: [] for repo in repos}
    in_degree: Dict[str, int] = {repo: 0 for repo in repos}

    for contract in contracts_data.get("contracts", []):
        definition_repo = contract.get("definition_repo", "")
        consumer_repos = contract.get("consumer_repos", [])
        if definition_repo and definition_repo in repo_set and consumer_repos:
            for consumer in consumer_repos:
                _add_dependency_edge(adj, in_degree, repo_set, definition_repo, consumer)

    return adj, in_degree


def topological_sort_repos(
    project_root: str,
    change_name: str,
    repos: List[str],
) -> Dict[str, Any]:
    """
    Topological sort repos based on cross_repo_contracts.json dependencies.

    Uses Kahn's algorithm. If a cycle is detected, returns cycle info
    so the caller can ask the user to resolve the order.

    Args:
        project_root: Project root directory
        change_name: Name of the change
        repos: List of involved repo names

    Returns:
        {
            "sorted_repos": list[str],  # Topologically sorted repo names
            "has_cycle": bool,          # Whether a cycle was detected
            "cycle_repos": list[str],   # Repos involved in the cycle (if any)
            "unresolved": list[str],    # Repos not in any dependency (if no cycle)
        }
    """
    root_path = Path(project_root)
    contracts_path = (
        root_path
        / "docs"
        / "changes"
        / change_name
        / "clarifications"
        / "cross_repo_contracts.json"
    )

    contracts_data = {"contracts": []}
    if contracts_path.exists():
        try:
            with open(contracts_path, encoding="utf-8") as f:
                contracts_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    adj, in_degree = _build_dependency_graph(repos, contracts_data)

    # Kahn's algorithm
    queue: List[str] = [r for r in repos if in_degree.get(r, 0) == 0]
    sorted_repos: List[str] = []

    while queue:
        # Sort queue for deterministic order among equal-priority repos
        queue.sort()
        current = queue.pop(0)
        sorted_repos.append(current)
        for neighbor in adj.get(current, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    has_cycle = len(sorted_repos) < len(repos)
    cycle_repos = [r for r in repos if r not in sorted_repos] if has_cycle else []

    return {
        "sorted_repos": sorted_repos,
        "has_cycle": has_cycle,
        "cycle_repos": cycle_repos,
        "unresolved": cycle_repos,
    }


def parse_cross_repo_dependencies(
    tasks_content: str,
) -> List[Dict[str, str]]:
    """
    Parse cross-repo dependency fields from tasks.md content.

    Extracts fields in the format:
        - **跨仓依赖**: repoB::TASK-003

    Args:
        tasks_content: Content of a tasks.md file

    Returns:
        List of {"task_text": str, "dep_repo": str, "dep_task": str}
    """
    deps: List[Dict[str, str]] = []
    dep_pattern = re.compile(
        r"-\s*\[([ x])\]\s*(.+?)\n(?:(?:\s+-\s+\*\*.*?\*\*:.*?\n)*?\s+-\s+\*\*跨仓依赖\*\*:\s*(\S+))",
        re.MULTILINE,
    )
    # Simpler two-pass approach
    task_pattern = re.compile(r"^-\s*\[([ x])\]\s*(.+)$", re.MULTILINE)
    cross_dep_pattern = re.compile(r"^\s+-\s+\*\*跨仓依赖\*\*:\s*(\S+)", re.MULTILINE)

    # Find all task lines and their following metadata
    lines = tasks_content.split("\n")
    current_task_text = None
    for line in lines:
        task_match = task_pattern.match(line)
        if task_match:
            current_task_text = task_match.group(2).strip()
            continue
        dep_match = cross_dep_pattern.match(line)
        if dep_match and current_task_text:
            dep_value = dep_match.group(1)
            if "::" in dep_value:
                parts = dep_value.split("::", 1)
                deps.append({
                    "task_text": current_task_text,
                    "dep_repo": parts[0],
                    "dep_task": parts[1],
                })
            current_task_text = None

    return deps
