"""
Main entry point for multi-code-analysis skill.

Provides CLI-like interface for code dependency analysis.
"""

import sys
import os
from pathlib import Path
from typing import List

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from repo_scope import guard_scope, filter_repo_dirs


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Multi-Code-Analysis: 多仓库代码依赖关系分析工具'
    )
    parser.add_argument(
        'command',
        choices=['scan', 'scan-deps', 'query', 'impact', 'trace', 'stats', 'tree', 'tree-all', 'add', 'delete', 'update', 'dep-report'],
        help='Command to execute'
    )
    parser.add_argument('--root', help='Code root directory')
    parser.add_argument('--output', help='Output directory for dependency graph (dep_graph/)')
    parser.add_argument('--file', help='File path (e.g. repo_name/path/to/file.py)')
    parser.add_argument('--graph', help='Dependency graph directory (dep_graph/)')
    parser.add_argument('--depth', type=int, default=0, help='Max recursion depth (0=unlimited)')
    parser.add_argument('--include', action='append', default=[], help='Include patterns (for new repos without .git)')
    parser.add_argument('--json', action='store_true', help='JSON output')
    parser.add_argument('--max-repos', type=int, default=None,
                        help='仓库数阈值，超过则退出码 3 要求先跑 /core-init 确认范围')
    parser.add_argument('--force', action='store_true',
                        help='跳过仓库数守卫（仅在用户明确确认后使用）')

    args = parser.parse_args()

    if args.command == 'scan':
        if not args.root:
            print("Error: --root required for 'scan' command")
            sys.exit(1)

        from scanner import scan_multi_repo
        from graph_builder import save_graph

        root_path = Path(args.root).resolve()
        if not root_path.exists():
            print(f"Error: Root directory does not exist: {root_path}")
            sys.exit(1)

        output_path = Path(args.output) if args.output else root_path.parent / 'dep_graph'

        guard_scope(root_path, args.max_repos, args.force)

        print(f"Scanning directory: {root_path}")

        graph_data = scan_multi_repo(root_path, args.include)

        print(f"Found {len(graph_data)} files")
        print(f"Building dependency graph...")

        save_graph(graph_data, output_path)

        total_deps = sum(len(g.get('deps', [])) for g in graph_data.values())
        max_depth = calculate_max_depth(graph_data)

        repos = set(g.get('repo', 'unknown') for g in graph_data.values())

        print(f"\n## Dependency Graph Built")
        print(f"\n**Root:** {root_path}")
        print(f"**Output:** {output_path}")
        print(f"\n### Statistics:")
        print(f"- Total files: {len(graph_data)}")
        print(f"- Total dependencies: {total_deps}")
        print(f"- Max depth: {max_depth}")
        print(f"\n### Output Files:")
        print(f"- graph.json: Dependency graph")

    elif args.command == 'scan-deps':
        from scanner import scan_multi_repo
        from graph_builder import save_graph
        from path import get_multi_repo_root

        if args.root:
            root_path = Path(args.root).resolve()
        else:
            root_path = get_multi_repo_root()
            print(f"Auto-detected multi-repo root: {root_path}")
        
        if not root_path.exists():
            print(f"Error: Root directory does not exist: {root_path}")
            sys.exit(1)

        output_path = Path(args.output) if args.output else root_path / 'docs'

        guard_scope(root_path, args.max_repos, args.force)

        print(f"Scanning dependencies: {root_path}")
        print(f"Include patterns: {args.include}")

        result = scan_multi_repo(root_path, args.include)
        if isinstance(result, tuple):
            graph_data, _ = result
        else:
            graph_data = result

        print(f"Found {len(graph_data)} files across all repos")
        print(f"Building dependency graph...")

        save_graph(graph_data, output_path)

        total_deps = sum(len(g.get('deps', [])) for g in graph_data.values())
        max_depth = calculate_max_depth(graph_data)

        repos = set(g.get('repo', 'unknown') for g in graph_data.values())

        print(f"\n## Dependency Graph Built")
        print(f"\n**Root:** {root_path}")
        print(f"**Output:** {output_path}")
        print(f"\n### Statistics:")
        print(f"- Total repos: {len(repos)}")
        print(f"- Total files: {len(graph_data)}")
        print(f"- Total dependencies: {total_deps}")
        print(f"- Max depth: {max_depth}")
        print(f"\n### Output Files:")
        print(f"- docs/graph.json: Dependency graph")

    elif args.command == 'query':
        from graph_builder import load_graph

        if not args.graph:
            print("Error: --graph required for 'query' command")
            sys.exit(1)

        graph_path = Path(args.graph)
        if graph_path.is_file():
            graph_file = graph_path
        else:
            graph_file = graph_path / 'graph.json'
        if not graph_file.exists():
            print(f"Error: Graph file not found: {graph_file}")
            sys.exit(1)

        graph_data = load_graph(graph_path)

        if not args.file:
            print("Error: --file required for 'query' command")
            sys.exit(1)

        result = graph_data.get(args.file.replace('\\', '/'))

        if result:
            print(f"\n## File Info")
            print(f"\n**Path:** {result['path']}")
            print(f"**Repo:** {result.get('repo', 'unknown')}")
            print(f"**Deps:** {len(result.get('deps', []))}")
            print(f"**RevDeps:** {len(result.get('rev_deps', []))}")
            
            ambiguous_deps = result.get('ambiguous_deps', [])
            if ambiguous_deps:
                print(f"\n## ⚠️ 歧义依赖提醒")
                print(f"\n此文件有 {len(ambiguous_deps)} 个歧义依赖（同名文件存在于多个仓库）：")
                for amb in ambiguous_deps:
                    candidates_str = ", ".join(amb['candidates'])
                    print(f"  - {amb['raw_dep']} → 候选: {candidates_str}")
                print(f"\n**注意**：请根据实际调用链判断实际依赖了哪个同名文件")
        else:
            print("File not found in graph")
            sys.exit(1)

    elif args.command == 'impact':
        from graph_builder import load_graph
        from query_engine import analyze_impact_files

        if not args.graph or not args.file:
            print("Error: --graph and --file required for 'impact' command")
            sys.exit(1)

        graph_path = Path(args.graph)
        graph_data = load_graph(graph_path)

        target_path = args.file.replace('\\', '/')
        if target_path not in graph_data:
            print(f"File not found: {args.file}")
            sys.exit(1)

        affected = analyze_impact_files(target_path, graph_data, args.depth)

        print(f"\n## Impact Analysis")
        print(f"\n**Target:** {target_path}")
        print(f"\n### Affected Files:")

        if affected:
            ambiguous_files = []
            for item in affected[:20]:
                file_path = item['path']
                has_ambiguous = bool(graph_data.get(file_path, {}).get('ambiguous_deps'))
                marker = " ⚠️" if has_ambiguous else ""
                print(f"  - {file_path} (depth: {item['depth']}){marker}")
                if has_ambiguous:
                    ambiguous_files.append(file_path)
            if len(affected) > 20:
                print(f"  ... and {len(affected) - 20} more")
            
            if ambiguous_files:
                print(f"\n### ⚠️ 歧义依赖详情")
                for file_path in ambiguous_files:
                    amb_deps = graph_data[file_path].get('ambiguous_deps', [])
                    print(f"\n**{file_path}:**")
                    for amb in amb_deps:
                        candidates_str = ", ".join(amb['candidates'])
                        print(f"  - {amb['raw_dep']} → 候选: {candidates_str}")
                print(f"\n**注意**：请根据实际调用链判断这些文件实际依赖了哪个同名文件")
        else:
            print("  (no files depend on this file)")

        print(f"\n**Total affected:** {len(affected)} files")

    elif args.command == 'trace':
        from graph_builder import load_graph
        from query_engine import trace_dependency_files

        if not args.graph or not args.file:
            print("Error: --graph and --file required for 'trace' command")
            sys.exit(1)

        graph_path = Path(args.graph)
        graph_data = load_graph(graph_path)

        target_path = args.file.replace('\\', '/')
        if target_path not in graph_data:
            print(f"File not found: {args.file}")
            sys.exit(1)

        traced = trace_dependency_files(target_path, graph_data, args.depth)

        print(f"\n## Trace Analysis")
        print(f"\n**Target:** {target_path}")
        print(f"\n### Dependencies:")

        if traced:
            ambiguous_files = []
            for item in traced[:20]:
                file_path = item['path']
                has_ambiguous = bool(graph_data.get(file_path, {}).get('ambiguous_deps'))
                marker = " ⚠️" if has_ambiguous else ""
                print(f"  - {file_path} (depth: {item['depth']}){marker}")
                if has_ambiguous:
                    ambiguous_files.append(file_path)
            if len(traced) > 20:
                print(f"  ... and {len(traced) - 20} more")
            
            if ambiguous_files:
                print(f"\n### ⚠️ 歧义依赖详情")
                for file_path in ambiguous_files:
                    amb_deps = graph_data[file_path].get('ambiguous_deps', [])
                    print(f"\n**{file_path}:**")
                    for amb in amb_deps:
                        candidates_str = ", ".join(amb['candidates'])
                        print(f"  - {amb['raw_dep']} → 候选: {candidates_str}")
                print(f"\n**注意**：请根据实际调用链判断这些文件实际依赖了哪个同名文件")
        else:
            print("  (no dependencies)")

        print(f"\n**Total dependencies:** {len(traced)} files")

    elif args.command == 'stats':
        from graph_builder import load_graph
        from query_engine import get_graph_stats

        if not args.graph:
            print("Error: --graph required for 'stats' command")
            sys.exit(1)

        graph_path = Path(args.graph)
        graph_data = load_graph(graph_path)

        stats = get_graph_stats(graph_data)

        print(f"\n## Dependency Graph Statistics")
        print(f"\n**Graph Directory:** {graph_path}")
        print(f"\n### Overview:")
        print(f"- Total files: {stats['total_files']}")
        print(f"- Total dependency links: {stats['total_deps']}")
        print(f"- Files with dependencies: {stats['files_with_deps']}")
        print(f"- Files depended upon: {stats['files_with_rev_deps']}")
        print(f"- Isolated files: {stats['isolated_files']}")
        print(f"\n### Depth Analysis:")
        print(f"- Max dependency depth: {stats['max_depth']}")
        print(f"- Average dependencies per file: {stats['avg_deps_per_file']:.2f}")
        print(f"\n### Top Depended Files (most referenced):")
        for item in stats['top_rev_deps'][:5]:
            print(f"  - {item['path']}: {item['count']} references")
        print(f"\n### Top Dependencies (most imports):")
        for item in stats['top_deps'][:5]:
            print(f"  - {item['path']}: {item['count']} imports")

    elif args.command == 'dep-report':
        from graph_builder import load_graph
        from tree import generate_dependency_report
        from path import get_output_dir

        if args.graph:
            graph_path = Path(args.graph)
        else:
            graph_path = get_output_dir('dep_graph')
            print(f"Auto-detected graph directory: {graph_path}")
        
        if graph_path.is_file():
            graph_file = graph_path
        else:
            graph_file = graph_path / 'graph.json'
        if not graph_file.exists():
            print(f"Error: Graph file not found: {graph_file}")
            print("Please run 'scan-multi' first to generate the dependency graph.")
            sys.exit(1)
        
        graph_data = load_graph(graph_path)

        if not graph_data:
            print("Error: Graph is empty")
            sys.exit(1)

        root_name = args.root if args.root else graph_path.parent.name
        report = generate_dependency_report(graph_data, root_name)
        print(report)

    elif args.command == 'tree':
        from tree import build_tree, format_tree, get_directory_structure

        if not args.root:
            print("Error: --root required for 'tree' command")
            sys.exit(1)

        root_path = Path(args.root).resolve()
        if not root_path.exists():
            print(f"Error: Root directory does not exist: {root_path}")
            sys.exit(1)

        max_depth = args.depth if args.depth > 0 else 4

        if args.json:
            import json
            from tree import generate_tree_summary
            summary = generate_tree_summary(root_path, max_depth)
            print(json.dumps(summary, indent=2))
        else:
            print(f"# {root_path.name}")
            print(f"\n**Root:** `{root_path}`")
            print(f"\n## Directory Structure\n")
            print("```")
            tree = build_tree(root_path, max_depth=max_depth, include_files=True)
            lines = format_tree(tree, max_depth=max_depth)
            for line in lines:
                print(line)
            print("```")
            print(f"\n## Statistics")
            print(f"\n- Total files: {tree.file_count}")
            print(f"- Total directories: {tree.dir_count}")

    elif args.command == 'add':
        from maintenance import load_graph, save_graph, add_file

        if not args.graph or not args.file:
            print("Error: --graph and --file required for 'add' command")
            sys.exit(1)

        graph_path = Path(args.graph)
        graph_data = load_graph(graph_path)

        repo_name = args.file.split('/')[0] if '/' in args.file else 'unknown'
        abs_file_path = Path(args.root) / args.file if args.root else Path(args.file)

        print(f"Adding file: {args.file}")
        result = add_file(args.file, repo_name, graph_data, list(graph_data.keys()))

        save_graph(graph_data, graph_path)

        print(f"\n## File Added")
        print(f"\n**File:** {args.file}")
        print(f"**Deps added:** {len(result['deps_added'])}")
        print(f"**Files with updated rev_deps:** {len(result['rev_deps_updated'])}")

    elif args.command == 'delete':
        from maintenance import load_graph, save_graph, delete_file

        if not args.graph or not args.file:
            print("Error: --graph and --file required for 'delete' command")
            sys.exit(1)

        graph_path = Path(args.graph)
        graph_data = load_graph(graph_path)

        print(f"Deleting file: {args.file}")
        result = delete_file(args.file, graph_data)

        save_graph(graph_data, graph_path)

        print(f"\n## File Deleted")
        print(f"\n**File:** {args.file}")
        print(f"**Affected files:** {len(result['affected_files'])}")

    elif args.command == 'update':
        from maintenance import load_graph, save_graph, update_file

        if not args.graph or not args.file:
            print("Error: --graph and --file required for 'update' command")
            sys.exit(1)

        graph_path = Path(args.graph)
        graph_data = load_graph(graph_path)

        print(f"Updating file: {args.file}")
        result = update_file(args.file, graph_data, list(graph_data.keys()))

        save_graph(graph_data, graph_path)

        print(f"\n## File Updated")
        print(f"\n**File:** {args.file}")
        print(f"**Deps added:** {len(result['deps_added'])}")
        print(f"**Deps removed:** {len(result['deps_removed'])}")
        print(f"**Affected files:** {len(result['affected_files'])}")

    elif args.command == 'tree-all':
        from tree import generate_project_intel
        from path import get_multi_repo_root

        if args.root:
            root_path = Path(args.root).resolve()
        else:
            root_path = get_multi_repo_root()
            print(f"Auto-detected multi-repo root: {root_path}")
        
        if not root_path.exists():
            print(f"Error: Root directory does not exist: {root_path}")
            sys.exit(1)

        output_dir = Path(args.output) if args.output else root_path / 'docs' / 'codeCapInfo'
        output_dir.mkdir(parents=True, exist_ok=True)

        max_depth = args.depth if args.depth > 0 else 4

        guard_scope(root_path, args.max_repos, args.force)

        subdirs = []
        for entry in root_path.iterdir():
            if entry.is_dir() and not entry.name.startswith('.'):
                is_repo = (entry / '.git').exists()
                if is_repo:
                    subdirs.append(entry)

        subdirs, skipped = filter_repo_dirs(root_path, subdirs)
        if skipped:
            print(f"  (skipped {len(skipped)} repo(s) excluded by codegraph.json)")

        if not subdirs:
            subdirs = [root_path]

        print(f"\n## Generating Project Intelligence (Markdown)")
        print(f"**Root:** {root_path}")
        print(f"**Output:** {output_dir}")
        print(f"**Repositories found:** {len(subdirs)}")
        print()

        for repo in sorted(subdirs, key=lambda x: x.name):
            repo_name = repo.name if repo != root_path else root_path.name
            repo_output_dir = output_dir / repo_name
            repo_output_dir.mkdir(parents=True, exist_ok=True)

            intel_files = generate_project_intel(repo, repo_name, max_depth)

            for filename, content in intel_files.items():
                output_file = repo_output_dir / filename
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(content)

            print(f"  {repo_name}/ ({len(intel_files)} files)")


def calculate_max_depth(graph_data):
    max_depth = 0
    for path_key in graph_data:
        visited = set()
        queue = [(path_key, 0)]
        while queue:
            current, depth = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            max_depth = max(max_depth, depth)
            for dep in graph_data[current].get('deps', []):
                if dep not in visited:
                    queue.append((dep, depth + 1))
    return max_depth


if __name__ == '__main__':
    main()
