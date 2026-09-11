"""
Design anchor resolver for CoreHarness-Spec.

This module provides functionality to resolve design anchors from tasks.md
and fetch corresponding content from delta_design.md, supporting the
three-phase display scheme (P0/P1/P2).
"""

import re
from typing import List, Dict, Tuple, Optional
from pathlib import Path


def parse_task_anchors(task_content: str) -> Dict[str, List[str]]:
    """
    Parse design anchors from a task's content.
    
    Args:
        task_content: Content of a single task block from tasks.md
        
    Returns:
        Dict with keys:
        - 'anchors': List of anchor strings
        - 'task_id': Task ID if found
        - 'language': Programming language if found
        - 'requirements': List of requirement IDs
    """
    result = {
        'anchors': [],
        'task_id': None,
        'language': None,
        'requirements': [],
        'acceptance_criteria': None
    }
    
    # Extract task ID from checkbox: - [ ] 1.1 <description>
    id_match = re.search(r'- \[.\] (\d+\.\d+)', task_content)
    if id_match:
        result['task_id'] = id_match.group(1)
    
    # Extract design anchors line: - **设计锚点**: #3.1 #2.2 #1.1:约束
    anchor_match = re.search(r'\*\*设计锚点\*\*:\s*(.+)', task_content)
    if anchor_match:
        anchors_str = anchor_match.group(1).strip()
        # Split by whitespace and filter empty
        anchors = [a.strip() for a in anchors_str.split() if a.strip()]
        result['anchors'] = anchors
    
    # Extract programming language: - **编程语言**: python
    lang_match = re.search(r'\*\*编程语言\*\*:\s*(.+)', task_content)
    if lang_match:
        result['language'] = lang_match.group(1).strip()
    
    # Extract requirements: - **关联需求**: R001, R002
    req_match = re.search(r'\*\*关联需求\*\*:\s*(.+)', task_content)
    if req_match:
        req_str = req_match.group(1).strip()
        requirements = [r.strip() for r in req_str.split(',') if r.strip()]
        result['requirements'] = requirements
    
    # Extract acceptance criteria
    accept_match = re.search(r'\*\*验收标准\*\*:\s*(.+)', task_content)
    if accept_match:
        result['acceptance_criteria'] = accept_match.group(1).strip()
    
    return result


def extract_tasks_from_tasks_md(tasks_content: str) -> List[Dict]:
    """
    Extract all tasks with their anchors from tasks.md content.
    
    Args:
        tasks_content: Content of tasks.md
        
    Returns:
        List of task dicts with parsed anchor information
    """
    tasks = []
    
    # Split by task checkbox pattern
    # Pattern: - [ ] TASK_ID DESCRIPTION
    task_pattern = re.compile(r'- \[.\] (\d+\.\d+)\s+(.+?)(?=\n- \[.\] \d+\.\d+|$)', re.DOTALL)
    
    for match in task_pattern.finditer(tasks_content):
        task_id = match.group(1)
        task_body = match.group(2)
        
        # Parse the task content
        task_info = parse_task_anchors(f"- [ ] {task_id} {task_body}")
        task_info['task_id'] = task_id
        task_info['description'] = task_body.split('\n')[0].strip()
        
        tasks.append(task_info)
    
    return tasks


def expand_wildcard_anchor(anchor: str, available_chapters: List[str]) -> List[str]:
    """
    Expand a wildcard anchor to concrete anchors.
    
    Args:
        anchor: Anchor string which may contain wildcards (e.g., '#4.x:*')
        available_chapters: List of available chapter identifiers
        
    Returns:
        List of expanded anchor strings
    """
    if '.x' not in anchor and 'X' not in anchor:
        return [anchor]
    
    # Pattern: #4.x:* or #4.X:keyword
    match = re.match(r'^#(\d+)\.x(?::(.+))?$', anchor, re.IGNORECASE)
    if not match:
        return [anchor]
    
    chapter_prefix = match.group(1)
    keyword = match.group(2)
    
    expanded = []
    for chapter in available_chapters:
        if chapter.startswith(f'{chapter_prefix}.'):
            if keyword:
                expanded.append(f'#{chapter}:{keyword}')
            else:
                expanded.append(f'#{chapter}')
    
    return expanded


def resolve_anchor(
    anchor: str,
    delta_design_content: str
) -> Tuple[Optional[str], Optional[str], int]:
    """
    Resolve an anchor to its display content.
    
    Args:
        anchor: Anchor string (e.g., '#3.1', '#1.1:约束')
        delta_design_content: Content of delta_design.md
        
    Returns:
        Tuple of (title, content, priority)
        - title: Display title for this anchor
        - content: Content snippet for this anchor
        - priority: Display priority (0, 1, or 2)
    """
    from anchor_extractor import get_priority, resolve_anchor_to_content
    
    lines = delta_design_content.split('\n')
    
    # Determine priority
    priority = get_priority(anchor)
    
    # Handle chapter-only anchor like #3.1
    if re.match(r'^#\d+\.\d+$', anchor):
        chapter_num = anchor.replace('#', '')
        
        # Find the chapter header
        for i, line in enumerate(lines):
            if re.match(rf'^###\s+{re.escape(chapter_num)}\s', line):
                title = line.replace('### ', '').strip()
                # Remove HTML comment if present
                title = re.sub(r'<!--.*?-->', '', title).strip()
                
                # Collect content until next chapter or end
                snippet_lines = []
                for j in range(i + 1, len(lines)):
                    next_line = lines[j]
                    if re.match(r'^##+\s+\d+\.\d+', next_line):
                        break
                    # Skip metadata comments
                    if '<!--' in next_line and '-->' in next_line:
                        continue
                    snippet_lines.append(next_line)
                
                content = '\n'.join(snippet_lines).strip()
                return title, content, priority
        
        return None, None, priority
    
    # Handle keyword anchor like #1.1:约束
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
                chapter_title = re.sub(r'<!--.*?-->', '', chapter_title).strip()
                break
        
        if chapter_start == -1:
            return None, None, priority
        
        # Search for keyword within the chapter
        for i in range(chapter_start, len(lines)):
            line = lines[i]
            # Stop at next chapter
            if i > chapter_start and re.match(r'^##+\s+\d+\.\d+', line):
                break
            if keyword in line and not line.strip().startswith('<!--'):
                # Found keyword, return context (lines before and after)
                snippet_lines = []
                start = max(chapter_start, i - 1)
                end = min(len(lines), i + 10)
                for j in range(start, end):
                    line_content = lines[j]
                    # Skip metadata comments
                    if '<!--' in line_content and '-->' in line_content:
                        continue
                    snippet_lines.append(line_content)
                content = '\n'.join(snippet_lines).strip()
                return f'{chapter_title} - {keyword}', content, priority
        
        # Fallback: if keyword not found, return chapter title with note
        return f'{chapter_title} - {keyword}', f'(关键词 "{keyword}" 未在章节中找到)', priority
    
    return None, None, priority


def format_anchor_display(
    anchor: str,
    title: str,
    content: Optional[str],
    priority: int
) -> str:
    """
    Format an anchor for display in the three-phase scheme.
    
    Args:
        anchor: The anchor string
        title: Resolved title
        content: Resolved content
        priority: Display priority (0, 1, or 2)
        
    Returns:
        Formatted string for display
    """
    priority_label = {0: 'P0', 1: 'P1', 2: 'P2'}.get(priority, 'P2')
    
    result = f'📌 {anchor} → {title}\n'
    if content:
        # Truncate content if too long (max 500 chars)
        if len(content) > 500:
            content = content[:500] + '...'
        result += f'   {content}'
    
    return result


def generate_anchor_display(
    task_info: Dict,
    delta_design_content: str,
    max_content_length: int = 2000
) -> str:
    """
    Generate the complete three-phase anchor display for a task.
    
    Args:
        task_info: Dict with task information from parse_task_anchors
        delta_design_content: Content of delta_design.md
        max_content_length: Maximum total content length (default 2000)
        
    Returns:
        Formatted multi-line string with P0/P1/P2 sections
    """
    from anchor_extractor import group_anchors_by_priority
    
    anchors = task_info.get('anchors', [])
    if not anchors:
        return ''
    
    task_id = task_info.get('task_id', 'unknown')
    description = task_info.get('description', '')
    
    # Group anchors by priority
    grouped = group_anchors_by_priority(anchors)
    
    # Collect all available chapters from delta_design
    chapter_pattern = re.compile(r'^###\s+(\d+\.\d+)', re.MULTILINE)
    available_chapters = chapter_pattern.findall(delta_design_content)
    
    # Expand wildcard anchors
    all_expanded = []
    for priority_level in [0, 1, 2]:
        for anchor in grouped[priority_level]:
            expanded = expand_wildcard_anchor(anchor, available_chapters)
            all_expanded.extend([(a, priority_level) for a in expanded])
    
    # Resolve each anchor
    resolved = []
    for anchor, priority in all_expanded:
        title, content, _ = resolve_anchor(anchor, delta_design_content)
        if title:
            resolved.append((anchor, title, content, priority))
    
    # Re-group by priority after expansion
    grouped_resolved = {0: [], 1: [], 2: []}
    for anchor, title, content, priority in resolved:
        grouped_resolved[priority].append((anchor, title, content))
    
    # Generate output
    lines = []
    lines.append(f'Working on task {task_id}: {description}\n')
    
    total_content_size = 0
    
    # P0 - Must Reference
    if grouped_resolved[0]:
        lines.append('【P0 必须参考 - 设计锚点解析结果】\n')
        for anchor, title, content in grouped_resolved[0]:
            lines.append(format_anchor_display(anchor, title, content, 0))
            if content:
                total_content_size += len(content)
        lines.append('')
    
    # P1 - Should Reference
    if grouped_resolved[1] and total_content_size < max_content_length:
        lines.append('【P1 应当参考 - 设计约束与原则】\n')
        for anchor, title, content in grouped_resolved[1]:
            lines.append(format_anchor_display(anchor, title, content, 1))
            if content:
                total_content_size += len(content)
        lines.append('')
    
    # P2 - Suggest Reference
    if grouped_resolved[2] and total_content_size < max_content_length:
        lines.append('【P2 建议参考 - 核心流程】\n')
        for anchor, title, content in grouped_resolved[2]:
            lines.append(format_anchor_display(anchor, title, content, 2))
            if content:
                total_content_size += len(content)
        lines.append('')
    
    lines.append('请基于以上设计信息实现当前任务。')
    
    return '\n'.join(lines)
