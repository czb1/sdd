"""
.gitignore parser and matcher.

Reads .gitignore files and provides matching functions.
"""

import os
import re
from pathlib import Path
from typing import List, Set, Pattern


class GitIgnore:
    """Represents a .gitignore file with its patterns."""
    
    def __init__(self):
        self.patterns: List[tuple] = []  # (pattern, is_negation, is_dir_pattern)
    
    def add_pattern(self, pattern: str):
        """Add a gitignore pattern."""
        if not pattern or pattern.strip().startswith('#'):
            return
        
        pattern = pattern.strip()
        is_negation = pattern.startswith('!')
        if is_negation:
            pattern = pattern[1:]
        
        # Determine if this is a directory-only pattern
        is_dir_pattern = pattern.endswith('/')
        if is_dir_pattern:
            pattern = pattern[:-1]
        
        # Convert gitignore pattern to regex
        regex_pattern = self._to_regex(pattern)
        if regex_pattern:
            try:
                compiled = re.compile(regex_pattern)
                self.patterns.append((compiled, is_negation, is_dir_pattern))
            except re.error:
                pass
    
    def _to_regex(self, pattern: str) -> str:
        """Convert a gitignore pattern to a regex pattern."""
        if not pattern:
            return None
        
        regex_parts = []
        i = 0
        n = len(pattern)
        
        while i < n:
            c = pattern[i]
            
            if c == '\\':
                # Escape special regex characters
                regex_parts.append(re.escape(pattern[i + 1]) if i + 1 < n else '')
                i += 2
            elif c == '*':
                # Single wildcard
                if i + 1 < n and pattern[i + 1] == '*':
                    # Double asterisk - match any number of directories
                    if i + 2 < n and pattern[i + 2] == '/':
                        # **/ means match anywhere
                        regex_parts.append('(.*/)?')
                        i += 3
                    else:
                        # ** means match everything
                        regex_parts.append('.*')
                        i += 2
                else:
                    # Single * means match anything except /
                    regex_parts.append('[^/]*')
                    i += 1
            elif c == '?':
                # Single character wildcard
                regex_parts.append('.')
                i += 1
            elif c == '[':
                # Character class
                regex_parts.append('[')
                i += 1
                while i < n and pattern[i] != ']':
                    regex_parts.append(re.escape(pattern[i]) if pattern[i] in '\\^$.|+(){}' else pattern[i])
                    i += 1
                if i < n:
                    regex_parts.append(']')
                    i += 1
            else:
                # Regular character
                regex_parts.append(re.escape(c))
                i += 1
        
        return ''.join(regex_parts) + ('(/.*)?' if regex_parts else '')
    
    def matches(self, path: str, is_dir: bool = False) -> bool:
        """
        Check if a path matches this .gitignore.
        
        Returns:
            True if path should be excluded, False if should be included
        """
        # Normalize path separators
        path = path.replace('\\', '/')
        
        # Try patterns in reverse order (last rule wins)
        result = False
        for compiled, is_negation, is_dir_pattern in reversed(self.patterns):
            if is_dir_pattern and not is_dir:
                continue
            
            if compiled.fullmatch(path) or compiled.search(path):
                result = not is_negation
        
        return result


def load_gitignore(repo_path: Path) -> GitIgnore:
    """
    Load .gitignore file from a repository path.
    
    Also loads from parent directories up to root.
    """
    gitignore = GitIgnore()
    
    # Load from subdirectories first (more specific)
    # then from parent directories (more general)
    current = repo_path
    patterns_from_parents = []
    
    while current != current.parent:
        gitignore_file = current / '.gitignore'
        if gitignore_file.exists():
            with open(gitignore_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.rstrip('\n\r')
                    if line and not line.startswith('#'):
                        if current != repo_path:
                            # Patterns from parent dirs only apply to subdirectories
                            patterns_from_parents.append(line)
                        else:
                            gitignore.add_pattern(line)
        
        current = current.parent
    
    # Add parent patterns with path prefix
    for pattern in patterns_from_parents:
        # Adjust pattern for relative path from where it was defined
        gitignore.add_pattern(pattern)
    
    return gitignore


def load_gitignore_simple(repo_path: Path) -> GitIgnore:
    """
    Simple version: load only the .gitignore in the repo root.
    """
    gitignore = GitIgnore()
    gitignore_file = repo_path / '.gitignore'
    
    if gitignore_file.exists():
        with open(gitignore_file, 'r', encoding='utf-8') as f:
            for line in f:
                gitignore.add_pattern(line.rstrip('\n\r'))
    
    return gitignore


def find_git_repos(root_path: Path) -> List[tuple]:
    """
    Find all git repositories under root_path.
    
    Returns:
        List of (repo_path, gitignore) tuples
    """
    repos = []
    
    for dirpath, dirnames, _ in os.walk(root_path):
        # Check if this directory is a git repo
        if '.git' in dirnames:
            repo_path = Path(dirpath)
            gitignore = load_gitignore_simple(repo_path)
            repos.append((repo_path, gitignore))
            # Don't descend into sub-repos
            dirnames[:] = [d for d in dirnames if d != '.git']
    
    return repos
