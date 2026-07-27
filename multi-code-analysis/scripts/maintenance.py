"""
Graph maintenance operations.

Provides add, delete, and update operations for the dependency graph.
"""

import json
from pathlib import Path
from typing import Dict, List, Any


def load_graph(graph_path: Path) -> Dict[str, Dict[str, Any]]:
    graph_path = Path(graph_path)
    if graph_path.is_file():
        graph_file = graph_path
    else:
        graph_file = graph_path / 'graph.json'

    if not graph_file.exists():
        return {}

    with open(graph_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_graph(graph_data: Dict[str, Dict[str, Any]], output_path: Path) -> None:
    output_path = Path(output_path)
    if output_path.is_file():
        graph_file = output_path
        output_path = output_path.parent
    else:
        graph_file = output_path / 'graph.json'
    output_path.mkdir(parents=True, exist_ok=True)
    with open(graph_file, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, indent=2, ensure_ascii=False)


def add_file(
    file_path: str,
    repo_name: str,
    graph_data: Dict[str, Dict[str, Any]],
    all_paths: List[str]
) -> Dict[str, Any]:
    if file_path in graph_data:
        raise ValueError(f"File already exists in graph: {file_path}")

    from parsers import get_parser_for_file
    from path_resolver import resolve_dependency_path

    abs_path = Path(file_path)
    parser = get_parser_for_file(abs_path)

    graph_data[file_path] = {
        'path': file_path,
        'repo': repo_name,
        'deps': [],
        'rev_deps': []
    }

    result = {'deps_added': [], 'rev_deps_updated': []}

    if parser:
        try:
            raw_deps = parser.parse_dependencies(abs_path)
            for raw_dep in raw_deps:
                resolved = resolve_dependency_path(raw_dep, file_path, all_paths)
                if resolved and resolved in graph_data:
                    graph_data[file_path]['deps'].append(resolved)
                    if file_path not in graph_data[resolved]['rev_deps']:
                        graph_data[resolved]['rev_deps'].append(file_path)
                        result['rev_deps_updated'].append(resolved)
                    result['deps_added'].append(resolved)
        except (IOError, OSError):
            pass

    return result


def delete_file(file_path: str, graph_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    if file_path not in graph_data:
        raise ValueError(f"File not found in graph: {file_path}")

    result = {'removed_deps': [], 'affected_files': []}

    deps = list(graph_data.get(file_path, {}).get('deps', []))
    rev_deps = list(graph_data.get(file_path, {}).get('rev_deps', []))

    for dep in deps:
        if dep in graph_data and file_path in graph_data[dep]['rev_deps']:
            graph_data[dep]['rev_deps'].remove(file_path)
            result['affected_files'].append(dep)

    for rev_dep in rev_deps:
        if rev_dep in graph_data and file_path in graph_data[rev_dep]['deps']:
            graph_data[rev_dep]['deps'].remove(file_path)
            result['affected_files'].append(rev_dep)

    del graph_data[file_path]

    return result


def update_file(
    file_path: str,
    graph_data: Dict[str, Dict[str, Any]],
    all_paths: List[str]
) -> Dict[str, Any]:
    if file_path not in graph_data:
        raise ValueError(f"File not found in graph: {file_path}")

    from parsers import get_parser_for_file
    from path_resolver import resolve_dependency_path

    abs_path = Path(file_path)
    parser = get_parser_for_file(abs_path)

    old_deps = set(graph_data[file_path]['deps'])
    new_deps = set()

    result = {'deps_added': [], 'deps_removed': [], 'affected_files': []}

    if parser:
        try:
            raw_deps = parser.parse_dependencies(abs_path)
            for raw_dep in raw_deps:
                resolved = resolve_dependency_path(raw_dep, file_path, all_paths)
                if resolved and resolved in graph_data:
                    new_deps.add(resolved)
        except (IOError, OSError):
            pass

    deps_added = new_deps - old_deps
    deps_removed = old_deps - new_deps

    for dep in deps_removed:
        if file_path in graph_data[dep]['rev_deps']:
            graph_data[dep]['rev_deps'].remove(file_path)
            result['affected_files'].append(dep)

    for dep in deps_added:
        if file_path not in graph_data[dep]['rev_deps']:
            graph_data[dep]['rev_deps'].append(file_path)
            result['affected_files'].append(dep)

    graph_data[file_path]['deps'] = list(new_deps)

    result['deps_added'] = list(deps_added)
    result['deps_removed'] = list(deps_removed)
    result['affected_files'] = list(set(result['affected_files']))

    return result
