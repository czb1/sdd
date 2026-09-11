"""
Main entry point for corespec-apply skill.
Provides CLI-like interface for implementing tasks from a change.
"""

import sys
import os
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from cc_paths import setup_core_paths

# Use skill_bootstrap for path setup
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'core-shared' / 'scripts'))
from skill_bootstrap import skill_bootstrap
skill_bootstrap()

from list_changes import list_changes
from apply_tasks import get_apply_instructions, parse_tasks, update_task_status


def main():
    """Main entry point for skill execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description='CoreSpec Apply Skill')
    parser.add_argument('command', choices=['list', 'status', 'apply', 'instructions'],
                        help='Command to execute')
    parser.add_argument('--name', help='Change name')
    parser.add_argument('--change', help='Change name (alias for --name)')
    parser.add_argument('--artifact', help='Artifact ID for instructions')
    parser.add_argument('--schema', help='Schema name')
    parser.add_argument('--project-root', default=os.getcwd(), help='Project root directory')
    parser.add_argument('--json', action='store_true', help='JSON output')
    parser.add_argument('--task-index', type=int, help='Task index to mark complete')
    parser.add_argument('--done', action='store_true', help='Mark task as done')
    
    args = parser.parse_args()
    
    change_name = args.name or args.change
    
    if args.command == 'list':
        try:
            changes = list_changes(args.project_root, args.json)
            if args.json:
                import json
                print(json.dumps(changes, indent=2))
            else:
                if not changes:
                    print("No active changes found.")
                else:
                    print("Available changes:")
                    for c in changes:
                        status_str = f"{c.get('artifacts_done', 0)}/{c.get('artifacts_total', 0)} artifacts"
                        print(f"  - {c['name']} ({c.get('schema', 'spec-driven')}) - {status_str}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    elif args.command == 'status':
        if not change_name:
            print("Error: --name or --change required for 'status' command")
            sys.exit(1)
        
        try:
            result = get_apply_instructions(change_name, args.project_root, args.schema, args.json)
            if args.json:
                import json
                print(json.dumps(result, indent=2))
            else:
                print(f"Change: {result['changeName']}")
                print(f"State: {result['state']}")
                print(f"Progress: {result['complete']}/{result['total']} tasks")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    elif args.command == 'apply':
        if not change_name:
            print("Error: --name or --change required for 'apply' command")
            sys.exit(1)
        
        try:
            result = get_apply_instructions(change_name, args.project_root, args.schema, args.json)
            if args.json:
                import json
                print(json.dumps(result, indent=2))
            else:
                print(f"Change: {result['changeName']}")
                print(f"Schema: {result['schemaName']}")
                print(f"State: {result['state']}")
                print(f"Progress: {result['complete']}/{result['total']} tasks")
                if result.get('tasks'):
                    print("\nTasks:")
                    for i, task in enumerate(result['tasks']):
                        status = "[x]" if task['done'] else "[ ]"
                        print(f"  {status} {i+1}. {task['text']}")
                if result.get('instruction'):
                    print(f"\nInstruction: {result['instruction']}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
