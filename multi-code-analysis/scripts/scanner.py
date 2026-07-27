"""
Code dependency scanner.

Single-pass directory scanning and dependency parsing.

Fixed in this version
---------------------
  - `_scan_single_repo` walked the tree with NO directory pruning at all. Since
    CODE_EXTENSIONS includes .js/.ts, a single front-end repo with installed
    dependencies fed hundreds of thousands of node_modules files into
    `_resolve_all_deps`. SKIP_DIRS now prunes in-place during os.walk.
  - Repo selection ignored `codegraph.json`. It now honours the same exclude
    patterns core-init writes, so a workspace scan stays inside the chosen
    repos.
  - No upper bound on work. Each repo now has a file budget
    (MAX_FILES_PER_REPO); hitting it warns loudly rather than hanging.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

from parsers import get_parser_for_file
from path_resolver import resolve_dependency_path

# Shared repo-scope filter (core-shared/scripts/repo_config.py).
try:
    from repo_scope import filter_repo_dirs, scope_available
except ImportError:  # degrade gracefully if core-shared is missing
    def filter_repo_dirs(root, dirs):
        return list(dirs), []

    def scope_available():
        return False


CODE_EXTENSIONS = {
    '.py', '.java', '.js', '.jsx', '.ts', '.tsx',
    '.cpp', '.cc', '.cxx', '.c', '.h', '.hpp',
    '.go', '.rs', '.rb', '.php', '.cs', '.swift', '.kt', '.scala',
}

# Directories never walked into. Kept in sync with core-shared/repo_config.py.
SKIP_DIRS = {
    'node_modules', 'vendor', 'third_party', 'thirdparty', 'external',
    'dist', 'build', 'out', 'target', '__pycache__', '.git', '.svn',
    '.hg', '.idea', '.vscode', '.cache', '.tox', '.mypy_cache',
    '.pytest_cache', '.gradle', '.mvn', 'venv', '.venv', 'env',
    '.env', 'Pods', 'bazel-bin', 'bazel-out', 'bazel-testlogs', '.bazel',
    '.codegraph', '.generation',
}

# Upper bound on code files inspected per repo.
MAX_FILES_PER_REPO = 30000


def is_code_file(file_path: Path) -> bool:
    return file_path.suffix.lower() in CODE_EXTENSIONS


def scan_multi_repo(
    root_path: Path,
    include_patterns: List[str] = None,
    max_files_per_repo: int = MAX_FILES_PER_REPO,
) -> Dict[str, Dict[str, Any]]:
    """
    Scan root_path, automatically detecting repos by .git presence.

    Repos excluded via `codegraph.json` are skipped, so this agrees with
    core-init and with what `codegraph index` put in the database.

    Args:
        root_path: Root directory containing multiple repos
        include_patterns: Patterns to include even without .git (for new projects)
        max_files_per_repo: Safety budget; scanning stops for a repo past this

    Returns:
        graph_data: {path: {path, repo, deps: [], rev_deps: []}}
    """
    if include_patterns is None:
        include_patterns = []

    graph_data: Dict[str, Dict[str, Any]] = {}
    all_files: Dict[str, Path] = {}

    def match_include(name: str) -> bool:
        for pattern in include_patterns:
            if pattern in name:
                return True
        return False

    candidates: List[Path] = []
    for entry in root_path.iterdir():
        if not entry.is_dir():
            continue
        if entry.name in SKIP_DIRS or entry.name.startswith('.'):
            continue

        is_repo = (entry / '.git').exists()
        should_include = match_include(entry.name)

        if not is_repo and not should_include:
            continue

        candidates.append(entry)

    candidates, skipped = filter_repo_dirs(root_path, candidates)
    if skipped:
        names = ', '.join(d.name for d in skipped)
        print(f"Skipping {len(skipped)} repo(s) excluded by codegraph.json: {names}")
    if not scope_available():
        print("WARNING: codegraph.json scope filter unavailable "
              "(core-shared/repo_config.py not found)")

    if not candidates:
        candidates = [root_path]

    for entry in candidates:
        repo_name = entry.name
        print(f"Scanning repo: {repo_name}")

        repo_files, repo_graph = _scan_single_repo(
            entry, repo_name, max_files=max_files_per_repo
        )
        all_files.update(repo_files)
        graph_data.update(repo_graph)

    print(f"Resolving dependencies across {len(graph_data)} files...")
    all_paths = list(graph_data.keys())
    _resolve_all_deps(graph_data, all_files, all_paths)

    return graph_data


def _scan_single_repo(
    root_path: Path,
    repo_name: str,
    max_files: int = MAX_FILES_PER_REPO,
) -> Tuple[Dict[str, Path], Dict[str, Dict[str, Any]]]:
    """Scan a single repo, pruning dependency/build directories."""
    all_files: Dict[str, Path] = {}
    graph_data: Dict[str, Dict[str, Any]] = {}
    truncated = False

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune in-place: os.walk will not descend into removed entries.
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith('.')
        ]

        for filename in filenames:
            file_path = Path(dirpath) / filename

            if not is_code_file(file_path):
                continue

            if len(all_files) >= max_files:
                truncated = True
                break

            try:
                rel_path = str(file_path.relative_to(root_path)).replace('\\', '/')
                full_path = f"{repo_name}/{rel_path}"

                all_files[full_path] = file_path
                graph_data[full_path] = {
                    'path': full_path,
                    'repo': repo_name,
                    'deps': [],
                    'rev_deps': []
                }
            except (IOError, OSError, ValueError):
                continue

        if truncated:
            break

    if truncated:
        print(f"  WARNING: {repo_name} hit the {max_files}-file budget; "
              f"the dependency graph for this repo is INCOMPLETE. "
              f"Exclude vendored directories in codegraph.json or raise the budget.")
    else:
        print(f"  {repo_name}: {len(all_files)} code files")

    return all_files, graph_data


def _resolve_all_deps(
    graph_data: Dict[str, Dict[str, Any]],
    all_files: Dict[str, Path],
    all_paths: List[str]
):
    """Resolve dependencies for all files using complete file list."""
    ambiguous_deps: Dict[str, List[Dict]] = {}

    for file_path, abs_path in all_files.items():
        current_repo = file_path.split('/')[0]
        parser = get_parser_for_file(abs_path)
        if not parser:
            continue

        try:
            raw_deps = parser.parse_dependencies(abs_path)

            for raw_dep in raw_deps:
                result = resolve_dependency_path(raw_dep, file_path, all_paths, current_repo)

                if result.is_ambiguous:
                    if file_path not in ambiguous_deps:
                        ambiguous_deps[file_path] = []
                    ambiguous_deps[file_path].append({
                        'raw_dep': raw_dep,
                        'candidates': result.candidates
                    })
                    continue

                if result.resolved and result.resolved in graph_data:
                    if result.resolved not in graph_data[file_path]['deps']:
                        graph_data[file_path]['deps'].append(result.resolved)
                    if file_path not in graph_data[result.resolved]['rev_deps']:
                        graph_data[result.resolved]['rev_deps'].append(file_path)
        except (IOError, OSError):
            continue

    for file_path, amb_list in ambiguous_deps.items():
        if 'ambiguous_deps' not in graph_data[file_path]:
            graph_data[file_path]['ambiguous_deps'] = []
        graph_data[file_path]['ambiguous_deps'].extend(amb_list)


def detect_cycles(graph_data: Dict[str, Dict[str, Any]]) -> List[List[str]]:
    cycles = []
    visited = set()
    rec_stack = set()

    def dfs(node: str, path: List[str]) -> bool:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph_data.get(node, {}).get('deps', []):
            if neighbor not in visited:
                if dfs(neighbor, path):
                    return True
            elif neighbor in rec_stack:
                try:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                except ValueError:
                    cycles.append([neighbor])
                return True

        path.pop()
        rec_stack.remove(node)
        return False

    for node in graph_data:
        if node not in visited:
            dfs(node, [])

    return cycles
