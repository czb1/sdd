"""
Query engine for dependency graph analysis.

Provides functions to query dependencies, impacts, and statistics.
"""

from typing import Dict, List, Any, Optional, Set


def query_file_info(file_path: str, graph_data: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    normalized = file_path.replace('\\', '/')
    return graph_data.get(normalized)


def analyze_impact_files(
    target_path: str,
    graph_data: Dict[str, Dict[str, Any]],
    max_depth: int = 0
) -> List[Dict[str, Any]]:
    if target_path not in graph_data:
        return []

    visited: Set[str] = set()
    result: List[Dict[str, Any]] = []
    queue: List[tuple] = [(target_path, 0)]

    while queue:
        current, depth = queue.pop(0)

        if current in visited:
            continue
        if max_depth > 0 and depth > max_depth:
            continue

        visited.add(current)

        rev_deps = graph_data.get(current, {}).get('rev_deps', [])
        for rev_dep in rev_deps:
            if rev_dep not in visited:
                result.append({
                    'path': rev_dep,
                    'depth': depth + 1
                })
                queue.append((rev_dep, depth + 1))

    return result


def trace_dependency_files(
    target_path: str,
    graph_data: Dict[str, Dict[str, Any]],
    max_depth: int = 0
) -> List[Dict[str, Any]]:
    if target_path not in graph_data:
        return []

    visited: Set[str] = set()
    result: List[Dict[str, Any]] = []
    queue: List[tuple] = [(target_path, 0)]

    while queue:
        current, depth = queue.pop(0)

        if current in visited:
            continue
        if max_depth > 0 and depth > max_depth:
            continue

        visited.add(current)

        deps = graph_data.get(current, {}).get('deps', [])
        for dep in deps:
            if dep not in visited:
                result.append({
                    'path': dep,
                    'depth': depth + 1
                })
                queue.append((dep, depth + 1))

    return result


def get_graph_stats(graph_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    total_files = len(graph_data)
    total_deps = sum(len(g.get('deps', [])) for g in graph_data.values())

    files_with_deps = sum(1 for g in graph_data.values() if len(g.get('deps', [])) > 0)
    files_with_rev_deps = sum(1 for g in graph_data.values() if len(g.get('rev_deps', [])) > 0)
    isolated_files = sum(
        1 for g in graph_data.values()
        if len(g.get('deps', [])) == 0 and len(g.get('rev_deps', [])) == 0
    )

    max_depth = 0
    for path_key in graph_data:
        depth = calculate_node_depth(path_key, graph_data)
        max_depth = max(max_depth, depth)

    avg_deps = total_deps / total_files if total_files > 0 else 0

    top_rev_deps = []
    for path_key, data in graph_data.items():
        top_rev_deps.append({
            'path': path_key,
            'count': len(data.get('rev_deps', []))
        })
    top_rev_deps.sort(key=lambda x: x['count'], reverse=True)

    top_deps = []
    for path_key, data in graph_data.items():
        top_deps.append({
            'path': path_key,
            'count': len(data.get('deps', []))
        })
    top_deps.sort(key=lambda x: x['count'], reverse=True)

    return {
        'total_files': total_files,
        'total_deps': total_deps,
        'files_with_deps': files_with_deps,
        'files_with_rev_deps': files_with_rev_deps,
        'isolated_files': isolated_files,
        'max_depth': max_depth,
        'avg_deps_per_file': avg_deps,
        'top_rev_deps': top_rev_deps,
        'top_deps': top_deps,
    }


def calculate_node_depth(
    node_path: str,
    graph_data: Dict[str, Dict[str, Any]]
) -> int:
    visited: Set[str] = set()
    max_depth = 0
    queue: List[tuple] = [(node_path, 0)]

    while queue:
        current, depth = queue.pop(0)

        if current in visited:
            continue

        visited.add(current)
        max_depth = max(max_depth, depth)

        deps = graph_data.get(current, {}).get('deps', [])
        for dep in deps:
            if dep not in visited:
                queue.append((dep, depth + 1))

    return max_depth
