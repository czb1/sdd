"""
Create artifact file from content.
"""

import sys
import re
from pathlib import Path
from typing import Optional, List , Dict, Any

from cc_paths import setup_core_paths
setup_core_paths()

from core_change_context import load_change_context, ChangeContext
from anchor_extractor import extract_anchors_by_task


def resolve_generates_path(generates: str, change_dir: Path) -> Path:
    """
    Resolve artifact generates path.
    
    Now that delta_spec and delta_design are in the change root directory,
    this function simply returns the direct path without glob handling.
    
    Args:
        generates: The generates path from schema
        change_dir: The change directory path
        
    Returns:
        Resolved actual path
    """
    return change_dir / generates


def extract_spec_sections(rule_content: str) -> List[str]:
    """
    Extract specification sections from rule content.
    
    Args:
        rule_content: Content of a rule file
        
    Returns:
        List of specification section strings
    """
    spec_sections = []
    current_section = []
    in_spec_section = False
    
    for line in rule_content.split('\n'):
        if line.startswith('#'):
            if in_spec_section and current_section:
                spec_sections.append('\n'.join(current_section))
                current_section = []
            in_spec_section = 'Requirement' in line or 'ADDED' in line or 'MODIFIED' in line or 'REMOVED' in line
            current_section.append(line)
        elif in_spec_section:
            current_section.append(line)
    
    if current_section:
        spec_sections.append('\n'.join(current_section))
    
    return spec_sections


def inject_all_rules_into_template(content: str, context: ChangeContext) -> str:
    """
    Inject ALL language rule.md content and skill instructions into artifact template.

    This function adds ALL available rule.md constraints (for all languages) to the
    generated artifacts (delta_design.md, tasks.md, etc.)

    Args:
        content: Original template content
        context: Change context containing all_rules and all_skill_instructions

    Returns:
        Modified content with all rule.md information injected
    """
    if not context.all_rules and not context.rule_content:
        return content

    rule_section = """

---

## 规范约束 (Specifications from relevant language)

"""
    # 直接遍历所有语言，原样插入规则内容
    for language, rule_content in context.all_rules.items():
        rule_section += f"""
### {language.upper()} 规范约束 ({language}-rule)

{rule_content}

"""
        # 如果有 skill 指引，也加上
        skill_instrs = context.all_skill_instructions.get(language, [])
        if skill_instrs:
            rule_section += """
**Skill 使用指引：**
"""
            for instr in skill_instrs:
                rule_section += f"- {instr}\n"

        rule_section += "\n"

    # 插入到合适位置
    if content.find('## 设计决策') != -1:
        content = content.replace('## 设计决策', rule_section + '\n\n## 设计决策')
    elif content.find('## 任务列表') != -1:
        content = content.replace('## 任务列表', rule_section + '\n\n## 任务列表')
    else:
        content += rule_section

    return content

def inject_design_anchors(content: str, delta_design_path: Path) -> str:
    """
    Inject design anchors into tasks.md content.
    
    For each code generation task in tasks.md, this function:
    1. Extracts the task ID (e.g., 1.1, 2.3)
    2. Looks up the associated design anchors from delta_design.md
    3. Fills in the design_anchors field
    
    Args:
        content: Original tasks.md content
        delta_design_path: Path to delta_design.md
        
    Returns:
        Modified content with design anchors filled in
    """
    if not delta_design_path.exists():
        return content
    
    # Read delta_design.md to get anchor metadata
    try:
        with open(delta_design_path, 'r', encoding='utf-8') as f:
            delta_design_content = f.read()
    except Exception:
        return content
    
    # Pattern to match code generation tasks
    # Matches: - [ ] 1.1 <description>\n  - **编程语言**: ...
    task_pattern = re.compile(
        r'(- \[.\] (\d+\.\d+).*?\n(?:  - \*\*[^*]+ \*\*:.*?\n)*)',
        re.MULTILINE | re.DOTALL
    )
    
    def replace_task_anchors(match):
        full_task = match.group(1)
        task_id = match.group(2)
        
        # Skip if already has design_anchors field
        if '**设计锚点**' in full_task:
            return full_task
        
        # Extract anchors for this task
        try:
            anchors = extract_anchors_by_task(str(delta_design_path), task_id)
            anchors_str = ' '.join(anchors)
        except Exception:
            anchors_str = ''
        
        if anchors_str:
            # Find the position after the last field and insert design_anchors
            last_field_match = re.search(r'(\n  - \*\*[^*]+ \*\*:.*?)$', full_task)
            if last_field_match:
                return full_task + f"  - **设计锚点**: {anchors_str}\n"
        
        return full_task
    
    return task_pattern.sub(replace_task_anchors, content)


def create_artifact_file(
    change_name: str,
    artifact_id: str,
    content: str,
    project_root: str,
    schema: Optional[str] = None,
    inject_rule: bool = True,
    design_rules: Optional[Dict[str, Any]] = None
) -> dict:
    """
    Create an artifact file with given content.
    
    Args:
        change_name: Name of the change
        artifact_id: ID of the artifact to create
        content: Content to write
        project_root: Project root directory
        schema: Optional schema name
        inject_rule: Whether to inject all rule.md content into the artifact
        
    Returns:
        Dict with artifactId and outputPath
    """
    context = load_change_context(project_root, change_name, schema, design_rules)
    
    artifact = context.graph.get_artifact(artifact_id)
    if not artifact:
        raise ValueError(f"Artifact '{artifact_id}' not found in schema")
    
    output_path = artifact.get('generates', '')
    if not output_path:
        raise ValueError(f"Artifact '{artifact_id}' has no generates path")
    
    if inject_rule and artifact_id in ['delta_design', 'tasks', 'delta_test_design']:
        content = inject_all_rules_into_template(content, context)
    
    change_dir = Path(context.change_dir)
    target_path = resolve_generates_path(output_path, change_dir)
    
    # For tasks.md, inject design anchors automatically
    if artifact_id == 'tasks':
        delta_design_path = change_dir / 'delta_design.md'
        if delta_design_path.exists():
            content = inject_design_anchors(content, delta_design_path)
    
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    all_instrs = []
    for instrs in context.all_skill_instructions.values():
        all_instrs.extend(instrs)
    
    return {
        'artifactId': artifact_id,
        'outputPath': str(target_path),
        'ruleInjected': bool(context.all_rules),
        'allLanguages': list(context.all_rules.keys()),
        'skillInstructions': all_instrs[:5],
        'anchorsInjected': artifact_id == 'tasks'
    }
