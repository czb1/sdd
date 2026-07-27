"""
Graph builder and persistence.

Builds the dependency graph and saves to JSON files.
"""

import json
from pathlib import Path
from typing import Dict, Any, List


def save_graph(
    graph_data: Dict[str, Dict[str, Any]],
    output_path: Path
) -> None:
    """
    Save the dependency graph to a single JSON file.

    Args:
        graph_data: {path: {path, repo, deps: [], rev_deps: []}}
        output_path: Directory to save files (dep_graph/)
    """
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    graph_file = output_path / 'graph.json'
    with open(graph_file, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, indent=2, ensure_ascii=False)


def load_graph(graph_path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Load dependency graph from JSON file.

    Args:
        graph_path: Directory containing graph.json (dep_graph/) or path to graph.json file

    Returns:
        graph_data: {path: {path, repo, deps: [], rev_deps: []}}
    """
    graph_path = Path(graph_path)
    if graph_path.is_file():
        graph_file = graph_path
    else:
        graph_file = graph_path / 'graph.json'

    if not graph_file.exists():
        raise FileNotFoundError(f"Graph file not found: {graph_file}")

    with open(graph_file, 'r', encoding='utf-8') as f:
        graph_data = json.load(f)

    return graph_data
