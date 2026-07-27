"""
Path resolution for dependency imports.

Converts import/module paths to actual file paths.
"""

from pathlib import Path
from typing import List, Optional, Union, Dict, Any
from dataclasses import dataclass


@dataclass
class ResolutionResult:
    """解析结果，包含歧义信息"""
    resolved: Optional[str]  # 明确解析的路径，None 表示未找到
    candidates: List[str]    # 所有候选文件（用于歧义时给 agent 参考）
    is_ambiguous: bool       # 是否有歧义（多个候选）
    
    def __bool__(self):
        return self.resolved is not None


def extract_name(path: str) -> str:
    """提取文件名（去掉路径和扩展名）"""
    basename = path.split('/')[-1]
    return basename.rsplit('.', 1)[0] if '.' in basename else basename


def create_result(resolved: str, candidates: List[str] = None) -> ResolutionResult:
    """创建解析结果"""
    if candidates is None:
        candidates = [resolved] if resolved else []
    is_ambiguous = len(candidates) > 1
    return ResolutionResult(resolved=resolved, candidates=candidates, is_ambiguous=is_ambiguous)


def create_ambiguous_result(candidates: List[str]) -> ResolutionResult:
    """创建歧义结果（未找到唯一匹配）"""
    return ResolutionResult(resolved=None, candidates=candidates, is_ambiguous=True)


def create_not_found_result() -> ResolutionResult:
    """创建未找到结果"""
    return ResolutionResult(resolved=None, candidates=[], is_ambiguous=False)


def resolve_dependency_path(
    raw_dep: str,
    current_rel_path: str,
    all_files: List[str],
    current_repo: str = None
) -> ResolutionResult:
    """
    Resolve a raw dependency import to an actual file path.
    
    Resolution order:
    1. Cross-repo direct lookup (e.g., "common/source/xxx.h")
    2. Relative imports (. or ..)
    3. Same directory then parent directories (Python-style path walk)
    4. Global ambiguous match (collect all candidates)
    
    Returns ResolutionResult with:
    - resolved: the best match, or None if ambiguous/not found
    - candidates: all possible matches for agent to review
    - is_ambiguous: True if multiple candidates exist
    """
    dep = raw_dep.strip()

    if not dep:
        return create_not_found_result()

    current_rel_path = current_rel_path.replace('\\', '/')
    current_parts = current_rel_path.split('/')
    
    if current_repo is None and len(current_rel_path.split('/')) > 0:
        current_repo = current_rel_path.split('/')[0]

    result = try_resolve_cross_repo(dep, all_files, current_repo)
    if result.resolved:
        return result
        
    if dep.startswith('.'):
        resolved = try_resolve_relative(dep, current_rel_path, all_files)
        if resolved:
            return create_result(resolved)

    for i in range(len(current_parts), 0, -1):
        search_dir = '/'.join(current_parts[:i]) if i > 0 else ''
        search_path = (search_dir + '/' + dep) if search_dir else dep
        
        resolved = try_resolve_with_extensions(search_path, all_files)
        if resolved:
            return create_result(resolved)

    return create_not_found_result()


def try_resolve_with_extensions(
    dep: str,
    all_files: List[str]
) -> Optional[str]:
    """Try resolving by appending common code extensions."""
    extensions = ['.py', '.js', '.ts', '.go', '.java', '.cpp', '.h', '.rs']

    if dep in all_files:
        return dep

    for ext in extensions:
        if dep + ext in all_files:
            return dep + ext

    return None


def try_resolve_cross_repo(
    dep: str,
    all_files: List[str],
    current_repo: str = None
) -> ResolutionResult:
    """
    Try to resolve a cross-repo dependency with same-repo priority.
    
    Resolution strategy:
    1. Direct lookup (e.g., "common/source/xxx.h") - exact match
    2. With extension appended
    3. Same-repo same-name match (compile-priority: local first)
    4. Global unique match (must be unique across all repos)
    5. All candidates collected (ambiguous case, no unique match)
    
    Args:
        dep: raw dependency string from source code
        all_files: list of all known file paths (format: "repo/path/file.ext")
        current_repo: current file's repository name (for same-repo priority)
    
    Returns:
        ResolutionResult with resolved path and/or candidates for ambiguous cases
    """
    if dep in all_files:
        return create_result(dep)
    
    extensions = ['.py', '.js', '.ts', '.go', '.java', '.cpp', '.h', '.rs']
    for ext in extensions:
        if dep + ext in all_files:
            return create_result(dep + ext)
    
    dep_basename = dep.split('/')[-1] if '/' in dep else dep
    dep_name = dep_basename.split('.')[0] if '.' in dep_basename else dep_basename
    
    all_candidates = []
    for f in all_files:
        f_basename = f.split('/')[-1]
        f_name = f_basename.rsplit('.', 1)[0] if '.' in f_basename else f_basename
        if f_name == dep_name:
            all_candidates.append(f)
    
    if len(all_candidates) == 0:
        return create_not_found_result()
    
    if len(all_candidates) == 1:
        return create_result(all_candidates[0])
    
    same_repo_candidates = [f for f in all_candidates if f.split('/')[0] == current_repo]
    if len(same_repo_candidates) == 1:
        return create_result(same_repo_candidates[0], all_candidates)
    
    if len(same_repo_candidates) > 1:
        return create_ambiguous_result(same_repo_candidates)
    
    return create_ambiguous_result(all_candidates)


def try_resolve_unique(
    dep: str,
    all_files: List[str]
) -> Optional[str]:
    """
    Try to find the dependency anywhere in the project.
    ONLY returns result if UNIQUE match is found.
    Otherwise returns None (ambiguous or not found).
    """
    dep_normalized = dep.replace('\\', '/')
    candidates = []
    
    for f in all_files:
        f_normalized = f.replace('\\', '/')
        f_basename = f_normalized.split('/')[-1]
        f_name_without_ext = f_basename.rsplit('.', 1)[0] if '.' in f_basename else f_basename
        
        # Match if filename (without extension) matches the dependency
        if f_name_without_ext == dep:
            candidates.append(f)
    
    # Only return if UNIQUE match
    if len(candidates) == 1:
        return candidates[0]
    
    # Multiple matches or no match - uncertain, let caller decide
    return None


def try_resolve_relative(
    dep: str,
    current_rel_path: str,
    all_files: List[str]
) -> Optional[str]:
    """Try resolving relative to current file's directory."""
    # Handle relative imports
    if not dep.startswith('.'):
        return None

    current_rel_path = current_rel_path.replace('\\', '/')
    parts = current_rel_path.split('/')
    current_dir = '/'.join(parts[:-1]) if len(parts) > 1 else ''

    # Build target path based on current directory
    if dep == '.':
        return current_dir if current_dir else parts[-1]  # Return dir or filename without extension

    elif dep.startswith('./'):
        target = (current_dir + '/' + dep[2:]) if current_dir else dep[2:]
    elif dep.startswith('../'):
        # Go up directories
        up_count = dep.count('..')
        dir_parts = current_dir.split('/') if current_dir else []
        target_parts = dir_parts[:-up_count] if up_count <= len(dir_parts) else []
        remaining = dep.split('../')[-1] if '../' in dep else ''
        target = '/'.join(target_parts) + ('/' + remaining if remaining else '')
    else:
        # Just a dot start like '.module'
        target = (current_dir + '/' + dep[1:]) if current_dir else dep[1:]

    # Normalize and try with extensions
    normalized = target.replace('\\', '/').strip('/')
    return try_resolve_with_extensions(normalized, all_files)


def try_resolve_scoped_package(
    dep: str,
    all_files: List[str]
) -> Optional[str]:
    """Handle scoped packages like @org/package or @org/package/sub."""
    if not dep.startswith('@'):
        return None

    # Convert @org/package to org/package
    parts = dep.split('/')
    if len(parts) < 2:
        return None

    # @org/package -> org/package
    scope_part = parts[0][1:]  # Remove @
    package_part = '/'.join(parts[1:])

    # Try package/path
    combined = f"{scope_part}/{package_part}"
    result = try_resolve_with_extensions(combined, all_files)
    if result:
        return result

    # Try as index file
    combined_index = f"{scope_part}/{package_part}/index.js"
    if combined_index in all_files:
        return combined_index

    return None


def normalize_path(path_str: str) -> str:
    """Normalize path separators to forward slash."""
    return path_str.replace('\\', '/')
