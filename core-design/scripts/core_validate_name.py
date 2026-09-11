"""
Change name validation logic.
"""

import re
from typing import Tuple


def validate_change_name(name: str) -> Tuple[bool, str]:
    """
    Validates that a change name follows kebab-case conventions.
    
    Valid names:
    - Start with a lowercase letter
    - Contain only lowercase letters, numbers, and hyphens
    - Do not start or end with a hyphen
    - Do not contain consecutive hyphens
    
    Args:
        name: The change name to validate
        
    Returns:
        Tuple of (valid: bool, error_message: str)
    """
    if not name:
        return False, "Change name cannot be empty"
    
    # Pattern: starts with lowercase letter, followed by lowercase letters/numbers,
    # optionally followed by hyphen + lowercase letters/numbers (repeatable)
    kebab_case_pattern = re.compile(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$')
    
    if not kebab_case_pattern.match(name):
        # Provide specific error messages for common mistakes
        if re.search(r'[A-Z]', name):
            return False, "Change name must be lowercase (use kebab-case)"
        if re.search(r'\s', name):
            return False, "Change name cannot contain spaces (use hyphens instead)"
        if '_' in name:
            return False, "Change name cannot contain underscores (use hyphens instead)"
        if name.startswith('-'):
            return False, "Change name cannot start with a hyphen"
        if name.endswith('-'):
            return False, "Change name cannot end with a hyphen"
        if '--' in name:
            return False, "Change name cannot contain consecutive hyphens"
        if re.search(r'[^a-z0-9-]', name):
            return False, "Change name can only contain lowercase letters, numbers, and hyphens"
        if re.match(r'^[0-9]', name):
            return False, "Change name must start with a letter"
        
        return False, "Change name must follow kebab-case convention (e.g., add-auth, refactor-db)"
    
    return True, ""


def derive_name_from_description(description: str) -> str:
    """
    Derives a kebab-case name from a natural language description.
    
    Args:
        description: Natural language description of what to build
        
    Returns:
        A valid kebab-case name derived from the description
    """
    # Convert to lowercase
    name = description.lower()
    
    # Replace spaces and underscores with hyphens
    name = re.sub(r'[\s_]+', '-', name)
    
    # Remove any characters that aren't letters, numbers, or hyphens
    name = re.sub(r'[^a-z0-9-]', '', name)
    
    # Remove consecutive hyphens
    name = re.sub(r'-+', '-', name)
    
    # Remove leading/trailing hyphens
    name = name.strip('-')
    
    # Ensure it starts with a letter (prefix with 'add-' if needed)
    if name and re.match(r'^[0-9]', name):
        name = 'task-' + name
    
    # If empty or too short, use a default
    if not name or len(name) < 2:
        name = 'new-change'
    
    return name
