"""
Directory tree generator.

Generates a tree view of the project structure for logical analysis.
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Set, Any


# Directories to exclude from tree
EXCLUDE_DIRS = {
    'node_modules', '__pycache__', '.git', '.svn', '.hg',
    'target', 'build', 'dist', 'out', 'bin', 'obj',
    'coverage', '.nyc_output', '.pytest_cache',
    '.idea', '.vscode', '.vs', 'cmake-build-*',
    '.venv', 'venv', 'env', '.env', 'virtualenv',
    '.tox', '.eggs', '*.egg-info',
    'vendor', 'third_party', 'thirdparties',
}

# Files to exclude from tree
EXCLUDE_FILES = {
    '.DS_Store', 'Thumbs.db', 'desktop.ini',
    '*.pyc', '*.pyo', '*.so', '*.dll', '*.dylib',
    '*.class', '*.jar', '*.war',
    '*.o', '*.a', '*.lib',
}


class TreeNode:
    """Represents a node in the directory tree."""
    
    def __init__(self, name: str, is_dir: bool, path: str):
        self.name = name
        self.is_dir = is_dir
        self.path = path
        self.children: List['TreeNode'] = []
        self.file_count: int = 0
        self.dir_count: int = 0
    
    def add_child(self, child: 'TreeNode'):
        self.children.append(child)
        if child.is_dir:
            self.dir_count += 1
            self.file_count += child.file_count
            self.dir_count += child.dir_count
        else:
            self.file_count += 1
    
    def sort_children(self):
        """Sort children: directories first, then files, alphabetically."""
        self.children.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        for child in self.children:
            child.sort_children()


def should_exclude_dir(name: str) -> bool:
    """Check if directory should be excluded."""
    return name in EXCLUDE_DIRS or name.startswith('.')


def should_exclude_file(name: str) -> bool:
    """Check if file should be excluded."""
    if name in EXCLUDE_FILES:
        return True
    for pattern in EXCLUDE_FILES:
        if pattern.startswith('*') and name.endswith(pattern[1:]):
            return True
    return False


def build_tree(root_path: Path, max_depth: int = 0, include_files: bool = True) -> TreeNode:
    """
    Build directory tree from root path.
    
    Args:
        root_path: Root directory to scan
        max_depth: Maximum depth to traverse (0 = unlimited)
        include_files: Whether to include files in tree
        
    Returns:
        Root TreeNode
    """
    root_name = root_path.name if root_path.name else str(root_path)
    root = TreeNode(root_name, True, str(root_path))
    
    _build_tree_recursive(root, root_path, 1, max_depth, include_files)
    root.sort_children()
    
    return root


def _build_tree_recursive(
    node: TreeNode,
    path: Path,
    current_depth: int,
    max_depth: int,
    include_files: bool
):
    """Recursively build tree."""
    if max_depth > 0 and current_depth > max_depth:
        return
    
    try:
        entries = list(path.iterdir())
    except (PermissionError, OSError):
        return
    
    for entry in sorted(entries, key=lambda x: x.name.lower()):
        name = entry.name
        
        if entry.is_dir():
            if should_exclude_dir(name):
                continue
            child = TreeNode(name, True, str(entry))
            _build_tree_recursive(child, entry, current_depth + 1, max_depth, include_files)
            child.sort_children()
            node.add_child(child)
        elif include_files:
            if should_exclude_file(name):
                continue
            child = TreeNode(name, False, str(entry))
            node.add_child(child)


def format_tree(node: TreeNode, prefix: str = "", is_last: bool = True, max_depth: int = 0, current_depth: int = 0) -> List[str]:
    """
    Format tree as list of strings for display.
    
    Compression rules:
    - If directory has subdirs: expand and show children
    - If directory has only files (no subdirs): merge as "dir/ (N files)", do NOT expand
    - Mixed directories: expand with file names shown
    
    Args:
        node: TreeNode to format
        prefix: Prefix for current line
        is_last: Whether this is the last sibling
        max_depth: Maximum depth to display (0 = unlimited)
        current_depth: Current recursion depth
        
    Returns:
        List of formatted lines
    """
    lines = []
    
    if max_depth > 0 and current_depth > max_depth:
        return lines
    
    connector = "`-- " if is_last else "|-- "
    extension = "[DIR] " if node.is_dir else "[FILE] "
    
    info = ""
    if node.is_dir and (node.file_count > 0 or node.dir_count > 0):
        info = f" ({node.file_count} files, {node.dir_count} dirs)"
    
    lines.append(f"{prefix}{connector}{extension}{node.name}{info}")
    
    child_prefix = prefix + ("    " if is_last else "|   ")
    
    if node.is_dir and node.dir_count == 0 and node.file_count > 0:
        return lines
    
    for i, child in enumerate(node.children):
        is_last_child = (i == len(node.children) - 1)
        lines.extend(format_tree(child, child_prefix, is_last_child, max_depth, current_depth + 1))
    
    return lines


def format_tree_markdown(node: TreeNode, max_depth: int = 0, current_depth: int = 0) -> List[str]:
    """
    Format tree as Markdown list with hierarchical indentation.
    
    Args:
        node: TreeNode to format
        max_depth: Maximum depth to display (0 = unlimited)
        current_depth: Current recursion depth
        
    Returns:
        List of Markdown formatted lines
    """
    lines = []
    
    if max_depth > 0 and current_depth > max_depth:
        return lines
    
    indent = "  "
    if node.is_dir:
        lines.append(f"{indent * current_depth}- **{node.name}/** ({node.file_count} files, {node.dir_count} dirs)")
    else:
        lines.append(f"{indent * current_depth}- {node.name}")
    
    for child in node.children:
        lines.extend(format_tree_markdown(child, max_depth, current_depth + 1))
    
    return lines


def generate_tree_summary(root_path: Path, max_depth: int = 2) -> Dict:
    """
    Generate a summary of the directory tree structure.
    
    Returns:
        Dictionary with tree statistics and structure
    """
    tree = build_tree(root_path, max_depth=max_depth, include_files=True)
    
    def count_nodes(node: TreeNode) -> Dict:
        return {
            'name': node.name,
            'is_dir': node.is_dir,
            'path': node.path,
            'file_count': node.file_count,
            'dir_count': node.dir_count,
            'children': [count_nodes(c) for c in node.children if c.is_dir][:10]  # Limit children in summary
        }
    
    return count_nodes(tree)


def get_directory_structure(root_path: Path) -> List[str]:
    """
    Get a flat list of all directories under root_path.
    
    Returns:
        List of directory paths relative to root
    """
    dirs = []
    try:
        for dirpath, dirnames, _ in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if not should_exclude_dir(d)]
            rel_path = str(Path(dirpath).relative_to(root_path))
            dirs.append(rel_path if rel_path != '.' else '/')
    except (PermissionError, OSError):
        pass
    
    return sorted(dirs)


def generate_markdown_tree(root_path: Path, repo_name: str = None, max_depth: int = 0) -> str:
    """
    Generate a complete Markdown file with ASCII tree format.
    
    Args:
        root_path: Root directory to scan
        repo_name: Name of the repository (for header)
        max_depth: Maximum depth (0 = unlimited)
        
    Returns:
        Markdown formatted string
    """
    if repo_name is None:
        repo_name = root_path.name
    
    tree = build_tree(root_path, max_depth=max_depth, include_files=True)
    
    lines = []
    lines.append(f"# {repo_name}")
    lines.append("")
    lines.append(f"**Root:** `{root_path}`")
    lines.append("")
    lines.append("## Directory Structure")
    lines.append("")
    lines.append("```")
    lines.extend(format_tree(tree, max_depth=max_depth))
    lines.append("```")
    lines.append("")
    lines.append("## Statistics")
    lines.append("")
    lines.append(f"- Total files: {tree.file_count}")
    lines.append(f"- Total directories: {tree.dir_count}")
    
    return '\n'.join(lines)


BUILD_CONFIG_FILES = [
    'pom.xml', 'build.gradle', 'build.gradle.kts',
    'go.mod',
    'package.json',
    'pyproject.toml', 'setup.py', 'setup.cfg',
    'CMakeLists.txt',
    'Makefile', 'makefile',
    'Cargo.toml',
    'build.sh', 'build.bat',
]

README_FILES = ['README.md', 'README.txt', 'README.rst', 'README']


def grab_file_content(file_path: Path, max_lines: int = 100) -> str:
    """Grab file content with line limit."""
    if not file_path.exists():
        return None
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [f.readline() for _ in range(max_lines)]
            content = ''.join(lines)
            if f.readline():
                content += f'\n... (truncated, showing first {max_lines} lines)'
            return content
    except (IOError, OSError):
        return None


def generate_project_intel(root_path: Path, repo_name: str = None, max_depth: int = 0) -> Dict[str, str]:
    """
    Generate project intelligence files for a repository.
    
    Args:
        root_path: Root directory of the repository
        repo_name: Name of the repository
        max_depth: Maximum depth for tree
        
    Returns:
        Dict mapping filename to content
    """
    if repo_name is None:
        repo_name = root_path.name
    
    result = {}
    
    tree = build_tree(root_path, max_depth=max_depth, include_files=True)
    
    result['_tree.md'] = f"# {repo_name} - Directory Tree\n\n**Root:** `{root_path}`\n\n```\n"
    result['_tree.md'] += '\n'.join(format_tree(tree, max_depth=max_depth))
    result['_tree.md'] += '\n```\n\n'
    result['_tree.md'] += f"## Statistics\n\n- Total files: {tree.file_count}\n- Total directories: {tree.dir_count}\n"
    
    for readme in README_FILES:
        readme_path = root_path / readme
        if readme_path.exists():
            content = grab_file_content(readme_path, 100)
            if content:
                result['README.md'] = f"# {readme}\n\n{content}"
                break
    
    for build_file in BUILD_CONFIG_FILES:
        build_path = root_path / build_file
        if build_path.exists():
            max_lines = 80 if build_file in ['CMakeLists.txt'] else 50
            content = grab_file_content(build_path, max_lines)
            if content:
                output_name = f'{build_file}.md'
                result[output_name] = f"# {build_file}\n\n{content}"
                break
    
    result['_meta.md'] = f"""# {repo_name} - Metadata

**Root:** `{root_path}`

## Statistics
- Total files: {tree.file_count}
- Total directories: {tree.dir_count}

## Build Config Files Found
"""
    for build_file in BUILD_CONFIG_FILES:
        if (root_path / build_file).exists():
            result['_meta.md'] += f"- {build_file}\n"
    
    result['_meta.md'] += "\n## README Found\n"
    for readme in README_FILES:
        if (root_path / readme).exists():
            result['_meta.md'] += f"- {readme}\n"
            break
    
    return result


def analyze_cross_repo_dependencies(graph_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze dependencies between repos and modules from graph data.
    
    Returns:
        Dict with repo_deps, module_deps, repo_stats, and ambiguous_deps
    """
    repo_deps = {}      # {repo: {depended_repo: count}}
    module_deps = {}    # {module: {depended_module: count}}
    repo_stats = {}     # {repo: {files, deps_count, rev_deps_count}}
    ambiguous_deps = [] # List of {file, raw_dep, candidates}

    for path, data in graph_data.items():
        parts = path.split('/')
        if len(parts) < 2:
            continue
        
        repo = parts[0]
        module = '/'.join(parts[:2])  # e.g., "am/source"
        
        if repo not in repo_stats:
            repo_stats[repo] = {'files': 0, 'deps': set(), 'rev_deps': set()}
        
        repo_stats[repo]['files'] += 1
        
        for dep in data.get('deps', []):
            dep_parts = dep.split('/')
            if len(dep_parts) < 2:
                continue
            dep_repo = dep_parts[0]
            dep_module = '/'.join(dep_parts[:2])
            
            if dep_repo != repo:
                if repo not in repo_deps:
                    repo_deps[repo] = {}
                if dep_repo not in repo_deps[repo]:
                    repo_deps[repo][dep_repo] = 0
                repo_deps[repo][dep_repo] += 1
                
                if module not in module_deps:
                    module_deps[module] = {}
                if dep_module not in module_deps[module]:
                    module_deps[module][dep_module] = 0
                module_deps[module][dep_module] += 1
            
            repo_stats[repo]['deps'].add(dep)
        
        for rev_dep in data.get('rev_deps', []):
            rev_parts = rev_dep.split('/')
            if len(rev_parts) < 2:
                continue
            rev_repo = rev_parts[0]
            if rev_repo != repo:
                if rev_repo not in repo_stats:
                    repo_stats[rev_repo] = {'files': 0, 'deps': set(), 'rev_deps': set()}
                repo_stats[rev_repo]['rev_deps'].add(path)
        
        for amb_dep in data.get('ambiguous_deps', []):
            ambiguous_deps.append({
                'file': path,
                'repo': repo,
                'raw_dep': amb_dep['raw_dep'],
                'candidates': amb_dep['candidates']
            })

    return {
        'repo_deps': repo_deps,
        'module_deps': module_deps,
        'repo_stats': repo_stats,
        'ambiguous_deps': ambiguous_deps
    }


def generate_dependency_report(graph_data: Dict[str, Dict[str, Any]], root_name: str = "Multi-Repo") -> str:
    """
    Generate a markdown report of cross-repo and cross-module dependencies.
    """
    analysis = analyze_cross_repo_dependencies(graph_data)
    repo_deps = analysis['repo_deps']
    module_deps = analysis['module_deps']
    repo_stats = analysis['repo_stats']
    ambiguous_deps = analysis['ambiguous_deps']

    lines = []
    lines.append(f"# {root_name} - 依赖关系分析")
    lines.append("")
    
    repos = sorted(repo_stats.keys())
    
    lines.append("## 仓库统计")
    lines.append("")
    lines.append("| 仓库 | 文件数 | 对外依赖数 | 被依赖数 |")
    lines.append("|------|--------|-----------|---------|")
    for repo in repos:
        stats = repo_stats[repo]
        deps_count = len(repo_deps.get(repo, {}))
        rev_deps_count = sum(1 for r, deps in repo_deps.items() if repo in deps)
        lines.append(f"| {repo} | {stats['files']} | {deps_count} | {rev_deps_count} |")
    
    lines.append("")
    lines.append("## 仓库间依赖关系")
    lines.append("")
    lines.append("```")
    lines.append("方向: A → B 表示 A 依赖 B")
    lines.append("")
    
    for repo in repos:
        deps = repo_deps.get(repo, {})
        if deps:
            dep_str = ", ".join([f"{r}({c})" for r, c in sorted(deps.items(), key=lambda x: -x[1])])
            lines.append(f"{repo} → {dep_str}")
    
    lines.append("```")
    
    lines.append("")
    lines.append("## 模块间依赖关系 (按一级目录聚合)")
    lines.append("")
    lines.append("```")
    
    sorted_modules = sorted(module_deps.items(), key=lambda x: x[0])
    for module, deps in sorted_modules:
        if deps:
            dep_str = ", ".join([f"{m}({c})" for m, c in sorted(deps.items(), key=lambda x: -x[1])])
            lines.append(f"{module} → {dep_str}")
    
    lines.append("```")
    
    lines.append("")
    lines.append("## 详细依赖矩阵")
    lines.append("")
    lines.append("| 被依赖 \\ 依赖 | " + " | ".join(repos) + " |")
    lines.append("|" + "---|" * (len(repos) + 1))
    for repo in repos:
        row = [repo]
        for dep_repo in repos:
            if dep_repo == repo:
                row.append("-")
            elif dep_repo in repo_deps.get(repo, {}):
                row.append(str(repo_deps[repo][dep_repo]))
            else:
                row.append("")
        lines.append("| " + " | ".join(row) + " |")
    
    if ambiguous_deps:
        lines.append("")
        lines.append("## ⚠️ 歧义依赖提醒")
        lines.append("")
        lines.append(f"发现 {len(ambiguous_deps)} 个歧义依赖（同名文件存在于多个仓库）：")
        lines.append("")
        
        module_ambiguous: Dict[str, Dict[str, Dict[str, int]]] = {}
        for amb in ambiguous_deps:
            file_path = amb['file']
            raw_dep = amb['raw_dep']
            candidates = amb['candidates']
            
            parts = file_path.split('/')
            module = '/'.join(parts[:2]) if len(parts) >= 2 else parts[0]
            candidate_repos = sorted(set(c.split('/')[0] for c in candidates))
            
            if module not in module_ambiguous:
                module_ambiguous[module] = {}
            if raw_dep not in module_ambiguous[module]:
                module_ambiguous[module][raw_dep] = {'count': 0, 'candidate_repos': candidate_repos}
            module_ambiguous[module][raw_dep]['count'] += 1
        
        lines.append("### 按模块聚合")
        lines.append("")
        lines.append("| 模块 | 歧义依赖数 | 同名文件分布 |")
        lines.append("|------|-----------|-------------|")
        for module in sorted(module_ambiguous.keys()):
            deps = module_ambiguous[module]
            dep_count = len(deps)
            total_occurrences = sum(d['count'] for d in deps.values())
            all_repos = set()
            for d in deps.values():
                all_repos.update(d['candidate_repos'])
            repos_str = "[" + ", ".join(sorted(all_repos)) + "]"
            lines.append(f"| {module} | {dep_count} 个 ({total_occurrences} 次引用) | {repos_str} |")
        
        lines.append("")
        lines.append("### 详细（按模块+依赖名聚合）")
        lines.append("")
        lines.append("| 模块 | 依赖名 | 出现次数 | 候选仓库 |")
        lines.append("|------|--------|---------|---------|")
        for module in sorted(module_ambiguous.keys()):
            deps = module_ambiguous[module]
            for dep_name in sorted(deps.keys()):
                info = deps[dep_name]
                repos_str = ", ".join(info['candidate_repos'])
                lines.append(f"| {module} | {dep_name} | {info['count']} | {repos_str} |")
        
        lines.append("")
        lines.append("**注意**：请根据实际调用链判断这些模块实际依赖了哪个同名文件")
    
    lines.append("")
    lines.append("---")
    lines.append(f"* 分析基于 {len(graph_data)} 个文件的依赖关系 *")
    
    return '\n'.join(lines)
