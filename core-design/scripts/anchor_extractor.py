"""
Design anchor extractor for CoreHarness-Spec.

This module provides functionality to extract design anchors from delta_design.md
based on task IDs, supporting the lightweight anchor reference scheme in tasks.md.
"""

import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path


def parse_anchor_metadata(content: str) -> Dict[str, Dict]:
    """
    Parse anchor metadata from delta_design.md content.
    
    Args:
        content: Content of delta_design.md
        
    Returns:
        Dict mapping anchor ID to metadata dict with keys:
        - anchor_id: str (e.g., '#3.1', '#1.1:约束')
        - tasks: List[str] of associated task IDs
        - keywords: List[str] of associated anchor keywords
        - line: int line number
    """
    metadata = {}
    
    # Match anchor comments: <!-- anchor: #X.X -->
    anchor_pattern = re.compile(r'<!--\s*anchor:\s*([^\s]+)\s*-->')
    # Match tasks metadata: <!-- tasks: [1.1, 2.1] -->
    tasks_pattern = re.compile(r'<!--\s*tasks:\s*\[([^\]]+)\]\s*-->')
    # Match anchors metadata: <!-- anchors: [关键词1, 关键词2] -->
    anchors_pattern = re.compile(r'<!--\s*anchors:\s*\[([^\]]+)\]\s*-->')
    
    lines = content.split('\n')
    current_chapter = None
    chapter_start_line = 0
    
    for line_num, line in enumerate(lines, start=1):
        # Detect chapter headers (### X.X)
        chapter_match = re.match(r'^###\s+(\d+\.\d+)', line)
        if chapter_match:
            current_chapter = chapter_match.group(1)
            chapter_start_line = line_num
        
        # Parse anchor comment
        anchor_match = anchor_pattern.search(line)
        if anchor_match and current_chapter:
            anchor_id = anchor_match.group(1)
            metadata[anchor_id] = {
                'anchor_id': anchor_id,
                'chapter': current_chapter,
                'tasks': [],
                'keywords': [],
                'line': line_num
            }
            
        # Parse tasks metadata (can follow anchor or be in same section)
        tasks_match = tasks_pattern.search(line)
        if tasks_match and current_chapter:
            tasks_str = tasks_match.group(1)
            tasks = [t.strip() for t in tasks_str.split(',')]
            # Associate with current chapter's anchor
            chapter_anchor = f'#{current_chapter}'
            if chapter_anchor in metadata:
                metadata[chapter_anchor]['tasks'].extend(tasks)
            # Also store globally indexed by task
            for task in tasks:
                if task not in metadata:
                    metadata[task] = {
                        'anchor_id': chapter_anchor,
                        'chapter': current_chapter,
                        'tasks': [task],
                        'keywords': [],
                        'line': line_num
                    }
                else:
                    metadata[task]['tasks'].append(task)
        
        # Parse anchors keywords metadata
        anchors_match = anchors_pattern.search(line)
        if anchors_match and current_chapter:
            anchors_str = anchors_match.group(1)
            keywords = [k.strip() for k in anchors_str.split(',')]
            chapter_anchor = f'#{current_chapter}'
            if chapter_anchor in metadata:
                metadata[chapter_anchor]['keywords'].extend(keywords)
    
    return metadata


def extract_anchors_by_task(
    delta_design_path: str,
    task_id: str
) -> List[str]:
    """
    Extract design anchors for a specific task from delta_design.md.
    
    Args:
        delta_design_path: Path to delta_design.md
        task_id: Task ID (e.g., '1.1', '2.3')
        
    Returns:
        List of anchor strings (e.g., ['#3.1', '#2.2', '#1.1:约束'])
    """
    with open(delta_design_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    metadata = parse_anchor_metadata(content)
    anchors = []
    
    # Find all anchors associated with this task
    for key, value in metadata.items():
        if task_id in value.get('tasks', []):
            anchors.append(value['anchor_id'])
            # Add keyword-based anchors
            for keyword in value.get('keywords', []):
                chapter = value['chapter']
                anchors.append(f'#{chapter}:{keyword}')
    
    # Always include architecture anchors (2.1, 2.2) if they exist
    # These are generally relevant to all tasks
    if '#2.1' in content and '#2.1' not in anchors:
        anchors.append('#2.1')
    if '#2.2' in content and '#2.2' not in anchors:
        anchors.append('#2.2')
    
    # Remove duplicates while preserving order
    seen = set()
    unique_anchors = []
    for a in anchors:
        if a not in seen:
            seen.add(a)
            unique_anchors.append(a)
    
    return unique_anchors


def expand_wildcard_anchors(anchors: List[str], content: str) -> List[str]:
    """
    Expand wildcard anchors (e.g., #4.x:*) to concrete anchors.
    
    Args:
        anchors: List of anchor strings (may contain wildcards)
        content: delta_design.md content for reference
        
    Returns:
        List of anchors with wildcards expanded
    """
    expanded = []
    
    for anchor in anchors:
        if '#x' in anchor.lower() or '.x' in anchor:
            # This is a wildcard anchor
            # Extract chapter number
            match = re.match(r'#(\d+)\.x', anchor)
            if match:
                chapter_prefix = match.group(1)
                # Find all subsections (3.1, 3.2, 3.3, etc.)
                pattern = re.compile(rf'^###\s+{chapter_prefix}\.\d+', re.MULTILINE)
                for sub_match in pattern.finditer(content):
                    sub_chapter = sub_match.group(0).replace('### ', '')
                    expanded.append(f'#{sub_chapter}')
        else:
            expanded.append(anchor)
    
    return expanded


def resolve_anchor_to_content(
    anchor: str,
    content: str
) -> Tuple[Optional[str], str]:
    """
    Resolve an anchor to its corresponding content in delta_design.md.
    
    Args:
        anchor: Anchor string (e.g., '#3.1', '#1.1:约束')
        content: delta_design.md content
        
    Returns:
        Tuple of (chapter_title, content_snippet)
        - chapter_title: The title of the chapter (e.g., '3.1 explore-doc-reviewer Skill 设计'), or None if not found
        - content_snippet: The content under this anchor, always a string (may be empty)
    """
    lines = content.split('\n')
    
    # Handle chapter anchor like #3.1
    if re.match(r'^#\d+\.\d+$', anchor):
        chapter_num = anchor.replace('#', '')
        # Find the chapter header
        for i, line in enumerate(lines):
            if re.match(rf'^###\s+{re.escape(chapter_num)}\s', line):
                chapter_title = line.replace('### ', '').strip()
                # Extract the anchor comment if present
                anchor_comment_match = re.search(r'<!--\s*anchor:\s*([^\s]+)\s*-->', line)
                if anchor_comment_match:
                    chapter_title = chapter_title.replace(anchor_comment_match.group(0), '').strip()
                
                # Collect content until next chapter or end
                snippet_lines = []
                for j in range(i + 1, len(lines)):
                    next_line = lines[j]
                    # Stop at next chapter header
                    if re.match(r'^##+\s+\d+\.\d+', next_line):
                        break
                    snippet_lines.append(next_line)
                
                return chapter_title, '\n'.join(snippet_lines).strip()
    
    # Handle keyword anchor like #1.1:约束
    elif ':' in anchor:
        match = re.match(r'^#(\d+\.\d+):(.+)$', anchor)
        if match:
            chapter_num = match.group(1)
            keyword = match.group(2)
            
            # Find the chapter first
            chapter_start = -1
            chapter_title = None
            for i, line in enumerate(lines):
                if re.match(rf'^###\s+{re.escape(chapter_num)}\s', line):
                    chapter_start = i
                    chapter_title = line.replace('### ', '').strip()
                    break
            
            if chapter_start == -1:
                return None, ""
            
            # Search for keyword within the chapter
            for i in range(chapter_start, len(lines)):
                line = lines[i]
                # Stop at next chapter
                if i > chapter_start and re.match(r'^##+\s+\d+\.\d+', line):
                    break
                if keyword in line:
                    # Found keyword, return context
                    snippet_lines = []
                    start = max(chapter_start, i - 2)
                    end = min(len(lines), i + 5)
                    for j in range(start, end):
                        snippet_lines.append(lines[j])
                    return f'{chapter_title} - {keyword}', '\n'.join(snippet_lines).strip()
    
    return None, ""


def get_priority(anchor: str) -> int:
    """
    Get the display priority for an anchor.
    
    Priority mapping:
    - P0: #X.X chapter anchors, #2.1, #2.2 architecture anchors
    - P1: #1.1:constraint, #1.2:principle anchors
    - P2: #4.x:flow anchors
    
    Args:
        anchor: Anchor string
        
    Returns:
        Priority level (0, 1, or 2)
    """
    if anchor in ['#2.1', '#2.2']:
        return 0
    
    match = re.match(r'^#(\d+)\.(\d+)(?::(.+))?$', anchor)
    if not match:
        return 2
    
    major = int(match.group(1))
    minor = int(match.group(2))
    keyword = match.group(3) or ''
    
    # Detailed design chapters (3.x)
    if major == 3:
        return 0
    
    # Design overview chapters (1.x)
    if major == 1:
        if '约束' in keyword or '非目标' in keyword:
            return 1
        if keyword:  # Has keyword, it's a principle
            return 1
        return 2
    
    # Architecture chapters (2.x)
    if major == 2:
        return 0
    
    # Core process chapters (4.x, 5.x, 6.x)
    if major in [4, 5, 6]:
        if keyword:
            return 2
        return 1
    
    return 2


def group_anchors_by_priority(anchors: List[str]) -> Dict[int, List[str]]:
    """
    Group anchors by their display priority.
    
    Args:
        anchors: List of anchor strings
        
    Returns:
        Dict mapping priority to list of anchors
    """
    grouped = {0: [], 1: [], 2: []}
    for anchor in anchors:
        priority = get_priority(anchor)
        grouped[priority].append(anchor)
    
    return grouped
