"""
Change context loading and management.
"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

from core_schema import get_schema


METADATA_FILENAME = '.docs.yaml'
DOCS_DIR = 'docs'
RULE_PATTERN = '*-rule.md'


def read_all_language_rules(project_root: str) -> Dict[str, str]:
    """
    Read all language-specific rule files from docs directory.
    
    Reads files matching docs/*-rule.md pattern, e.g.:
    - docs/cpp-rule.md
    - docs/js-rule.md
    - docs/python-rule.md
    
    Returns:
        Dict mapping language to content, e.g.:
        {"cpp": "...", "js": "...", "python": "..."}
        Returns empty dict if no rule files found.
    """
    docs_path = Path(project_root) / DOCS_DIR
    if not docs_path.exists():
        return {}
    
    rules = {}
    for rule_file in docs_path.glob(RULE_PATTERN):
        language = rule_file.stem.replace('-rule', '')  # cpp-rule.md -> cpp
        with open(rule_file, 'r', encoding='utf-8') as f:
            rules[language] = f.read()
    
    return rules


def extract_skill_instructions_from_rule(rule_content: str) -> List[str]:
    """
    Extract skill usage instructions from rule.md content.
    
    Looks for patterns like:
    - "Use /huawei-cleancode-java"
    - "Use generate-java-ut"
    - "Skill:" or "Use Skill:" sections
    
    Args:
        rule_content: Content of rule.md
        
    Returns:
        List of skill usage instructions found
    """
    skill_instructions = []
    
    if not rule_content:
        return skill_instructions
    
    lines = rule_content.split('\n')
    for line in lines:
        line = line.strip()
        # Look for skill usage patterns
        if 'Use /' in line or 'Use skill' in line.lower():
            skill_instructions.append(line)
        elif 'huawei-cleancode' in line.lower():
            skill_instructions.append(line)
        elif 'generate-java-ut' in line or 'generate-' in line:
            skill_instructions.append(line)
    
    return skill_instructions


def extract_skill_instructions_from_all_rules(all_rules: Dict[str, str]) -> Dict[str, List[str]]:
    """
    Extract skill usage instructions from all language rule files.
    
    Args:
        all_rules: Dict mapping language to rule content
        
    Returns:
        Dict mapping language to list of skill instructions
    """
    result = {}
    for language, content in all_rules.items():
        result[language] = extract_skill_instructions_from_rule(content)
    return result


class ChangeContext:
    """Change context containing graph, completion state, and metadata."""
    
    def __init__(
        self,
        graph: 'ArtifactGraph',
        completed: Set[str],
        schema_name: str,
        change_name: str,
        change_dir: str,
        project_root: str,
        rule_content: Optional[str] = None,
        skill_instructions: Optional[List[str]] = None,
        all_rules: Optional[Dict[str, str]] = None,
        all_skill_instructions: Optional[Dict[str, List[str]]] = None
    ):
        self.graph = graph
        self.completed = completed
        self.schema_name = schema_name
        self.change_name = change_name
        self.change_dir = change_dir
        self.project_root = project_root
        self.rule_content = rule_content
        self.skill_instructions = skill_instructions or []
        self.all_rules = all_rules or {}
        self.all_skill_instructions = all_skill_instructions or {}


class ArtifactGraph:
    """Simple artifact graph implementation."""
    
    def __init__(self, artifacts: List[Dict[str, Any]]):
        self.artifacts = artifacts
        self._by_id = {a['id']: a for a in artifacts}
    
    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        return self._by_id.get(artifact_id)
    
    def get_all_artifacts(self) -> List[Dict[str, Any]]:
        return self.artifacts
    
    def get_next_artifacts(self, completed: Set[str]) -> List[str]:
        """Get artifacts that are ready to be created."""
        ready = []
        for artifact in self.artifacts:
            artifact_id = artifact['id']
            if artifact_id in completed:
                continue
            
            requires = artifact.get('requires', [])
            if all(req in completed for req in requires):
                ready.append(artifact_id)
        
        return ready
    
    def get_blocked(self, completed: Set[str]) -> Dict[str, List[str]]:
        """Get blocked artifacts and their missing dependencies."""
        blocked = {}
        for artifact in self.artifacts:
            artifact_id = artifact['id']
            if artifact_id in completed:
                continue
            
            requires = artifact.get('requires', [])
            missing = [req for req in requires if req not in completed]
            
            if missing:
                blocked[artifact_id] = missing
        
        return blocked
    
    def is_complete(self, completed: Set[str]) -> bool:
        """Check if all artifacts are complete."""
        return all(a['id'] in completed for a in self.artifacts)
    
    def get_build_order(self) -> List[str]:
        """Get artifacts in build order."""
        return [a['id'] for a in self.artifacts]


def read_change_metadata(change_dir: str) -> Optional[Dict[str, Any]]:
    """
    Reads change metadata from .docs.yaml in the change directory.
    
    Args:
        change_dir: Path to the change directory
        
    Returns:
        Metadata dict or None if not found
    """
    metadata_path = Path(change_dir) / METADATA_FILENAME
    if not metadata_path.exists():
        return None
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def resolve_schema_for_change(change_dir: str, schema_name: Optional[str] = None) -> str:
    """
    Resolves schema for a change.
    
    Resolution order:
    1. Explicit schemaName parameter
    2. Schema from .docs.yaml metadata
    3. Default 'spec-driven'
    
    Args:
        change_dir: Path to the change directory
        schema_name: Optional schema name override
        
    Returns:
        Resolved schema name
    """
    if schema_name:
        return schema_name
    
    metadata = read_change_metadata(change_dir)
    if metadata and 'schema' in metadata:
        return metadata['schema']
    
    return 'spec-driven'


def detect_completed(graph: ArtifactGraph, change_dir: str) -> Set[str]:
    """
    Detects which artifacts are completed by checking file existence.
    
    Args:
        graph: Artifact graph
        change_dir: Change directory path
        
    Returns:
        Set of completed artifact IDs
    """
    completed = set()
    
    change_path = Path(change_dir)
    if not change_path.exists():
        return completed
    
    for artifact in graph.get_all_artifacts():
        generates = artifact.get('generates', '')
        if not generates:
            continue
        
        full_pattern = change_path / generates
        
        if '*' in generates or '?' in generates or '[' in generates:
            matches = list(change_path.glob(generates))
            if matches:
                completed.add(artifact['id'])
        else:
            if full_pattern.exists():
                completed.add(artifact['id'])
    
    return completed


def load_change_context(
    project_root: str,
    change_name: str,
    schema_name: Optional[str] = None,
    design_rules_json: Optional[Dict[str, Any]] = None
) -> ChangeContext:
    """
    Loads change context combining graph and completion state.
    Also loads rule.md for design constraints and skill instructions.
    
    Args:
        project_root: Project root directory
        change_name: Change name
        schema_name: Optional schema name override
        design_rules_json: Optional JSON string of all language rules
        
    Returns:
        Change context with rule.md content loaded
    """
    change_dir = Path(project_root) / 'docs' / 'changes' / change_name
    
    resolved_schema = resolve_schema_for_change(str(change_dir), schema_name)
    schema_data = get_schema(resolved_schema, project_root)
    
    graph = ArtifactGraph(schema_data.get('artifacts', []))
    completed = detect_completed(graph, str(change_dir))
    
    all_rules = {}
    all_skill_instructions = {}
    rule_content = ''
    skill_instructions = []
    
    if design_rules_json:
        try:
            all_rules = design_rules_json
            all_skill_instructions = extract_skill_instructions_from_all_rules(design_rules_json)
            rule_content = all_rules.get(None) or all_rules.get('default') or ''
            skill_instructions = all_skill_instructions.get(None) or all_skill_instructions.get('default') or []
        except json.JSONDecodeError:
            pass
    
    return ChangeContext(
        graph=graph,
        completed=completed,
        schema_name=resolved_schema,
        change_name=change_name,
        change_dir=str(change_dir),
        project_root=project_root,
        rule_content=rule_content,
        skill_instructions=skill_instructions,
        all_rules=all_rules,
        all_skill_instructions=all_skill_instructions
    )


def format_change_status(context: ChangeContext) -> Dict[str, Any]:
    """
    Formats the status of all artifacts in a change.
    
    Args:
        context: Change context
        
    Returns:
        Formatted status dict
    """
    schema_data = get_schema(context.schema_name, context.project_root)
    apply_requires = schema_data.get('apply', {}).get('requires', 
        [a['id'] for a in schema_data.get('artifacts', [])])
    
    artifacts = context.graph.get_all_artifacts()
    ready_ids = set(context.graph.get_next_artifacts(context.completed))
    blocked = context.graph.get_blocked(context.completed)
    
    artifact_statuses = []
    for artifact in artifacts:
        artifact_id = artifact['id']
        
        if artifact_id in context.completed:
            status = 'done'
        elif artifact_id in ready_ids:
            status = 'ready'
        else:
            status = 'blocked'
        
        artifact_info = {
            'id': artifact_id,
            'outputPath': artifact.get('generates', ''),
            'status': status,
        }
        
        if status == 'blocked' and artifact_id in blocked:
            artifact_info['missingDeps'] = blocked[artifact_id]
        
        artifact_statuses.append(artifact_info)
    
    build_order = context.graph.get_build_order()
    order_map = {aid: idx for idx, aid in enumerate(build_order)}
    artifact_statuses.sort(key=lambda a: order_map.get(a['id'], 0))
    
    return {
        'changeName': context.change_name,
        'schemaName': context.schema_name,
        'isComplete': context.graph.is_complete(context.completed),
        'applyRequires': apply_requires,
        'artifacts': artifact_statuses,
    }
