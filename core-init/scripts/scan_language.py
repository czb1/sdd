"""
Scan project environment and generate language.json.

Detects multi-repo/sub-repo structure and programming languages using file
extension statistics.

防爆 (blast guard) changes:
  - repo discovery is delegated to repo_config.discover_repos (bounded depth,
    bounded number of directories, honours codegraph.json `exclude`)
  - if more repos are found than `maxRepos`, NOTHING is written; the script
    returns status="needs_repo_selection" so the SKILL layer can ask the user
  - per-repo file walking is capped (MAX_FILES_PER_REPO) and skips excluded
    directories, so a single huge repo can't stall init either
"""

import sys
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from cc_paths import setup_core_paths
    setup_core_paths()
except Exception:  # noqa: BLE001 - never let path setup break the CLI
    pass

try:
    from repo_config import (  # noqa: E402
        CONFIG_FILENAME,
        evaluate_scope,
        get_exclude_patterns,
        is_excluded,
        load_config,
        norm,
        print_scope_report,
        suggest_config,
    )
except ImportError as _exc:  # pragma: no cover
    raise SystemExit(
        'core-init requires core-shared/scripts/repo_config.py. Install the '
        'core-shared skill next to core-init (<config_dir>/skills/core-shared/scripts/). '
        f'Import error: {_exc}'
    )


EXIT_NEEDS_REPO_SELECTION = 3

# Extension -> language mapping
EXTENSION_MAP: Dict[str, str] = {
    # Python
    ".py": "python", ".pyi": "python", ".pyx": "python", ".pxd": "python",
    # Java
    ".java": "java",
    # JavaScript
    ".js": "js", ".mjs": "js", ".cjs": "js",
    # TypeScript
    ".ts": "ts", ".tsx": "ts", ".mts": "ts", ".cts": "ts",
    # Go
    ".go": "go",
    # Rust
    ".rs": "rust",
    # C
    ".c": "c", ".h": "c",
    # C++
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".hxx": "cpp", ".hh": "cpp", ".hcc": "cpp",
    # Shell
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    # SQL
    ".sql": "sql",
    # Kotlin
    ".kt": "kotlin", ".kts": "kotlin",
    # Swift
    ".swift": "swift",
    # Ruby
    ".rb": "ruby",
    # PHP
    ".php": "php",
    # Scala
    ".scala": "scala",
    # C#
    ".cs": "csharp",
    # Dart
    ".dart": "dart",
    # Lua
    ".lua": "lua",
    # R
    ".r": "r", ".R": "r",
    # Perl
    ".pl": "perl", ".pm": "perl",
    # Vue
    ".vue": "js",
    # Svelte
    ".svelte": "js",
}

# Directories to skip during scanning
SKIP_DIRS = {
    "node_modules", "vendor", "third_party", "thirdparty", "external",
    "dist", "build", "out", "target", "__pycache__", ".git", ".svn",
    ".hg", ".idea", ".vscode", ".cache", ".tox", ".mypy_cache",
    ".pytest_cache", ".gradle", ".mvn", "venv", ".venv", "env",
    ".env", "Pods", ".flutter-plugins-dependencies",
    "bazel-bin", "bazel-out", "bazel-testlogs", ".bazel",
}

# Minimum percentage threshold for reporting a language
MIN_PERCENTAGE = 1.0

# 防爆: hard cap on files inspected per repo
MAX_FILES_PER_REPO = 30000

# Marker files that boost confidence for a language
LANGUAGE_MARKERS = {
    "python": ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile", "setup.cfg"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "js": ["package.json"],
    "ts": ["tsconfig.json"],
    "go": ["go.mod"],
    "rust": ["Cargo.toml"],
    "cpp": ["CMakeLists.txt", "Makefile"],
    "kotlin": ["build.gradle.kts"],
    "csharp": [".csproj", ".sln"],
    "ruby": ["Gemfile"],
    "php": ["composer.json"],
    "dart": ["pubspec.yaml"],
}


def _count_files_by_language(
    repo_path: Path,
    root: Optional[Path] = None,
    exclude: Optional[List[str]] = None,
    max_files: int = MAX_FILES_PER_REPO,
) -> Tuple[Dict[str, int], bool]:
    """
    Walk directory tree and count source files per language by extension.

    Returns (counts, truncated). `truncated` is True when the file budget was
    hit - the counts are then a (representative) sample, not a full census.
    """
    counts: Dict[str, int] = defaultdict(int)
    scanned = 0
    truncated = False

    for current, dirs, files in os.walk(str(repo_path)):
        current_path = Path(current)

        # Prune skipped directories in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        # Prune directories excluded via codegraph.json
        if exclude and root is not None:
            kept = []
            for d in dirs:
                try:
                    rel = norm((current_path / d).relative_to(root))
                except ValueError:
                    rel = None
                if rel and is_excluded(rel, exclude):
                    continue
                kept.append(d)
            dirs[:] = kept

        for fname in files:
            scanned += 1
            if scanned > max_files:
                truncated = True
                return counts, truncated
            ext = os.path.splitext(fname)[1].lower()
            lang = EXTENSION_MAP.get(ext)
            if lang:
                counts[lang] += 1

    return counts, truncated


def _has_marker(repo_path: Path, language: str) -> bool:
    """Check if any marker file exists for the given language."""
    markers = LANGUAGE_MARKERS.get(language, [])
    return any((repo_path / m).exists() for m in markers)


def detect_project_languages(
    repo_path: Path,
    root: Optional[Path] = None,
    exclude: Optional[List[str]] = None,
    max_files: int = MAX_FILES_PER_REPO,
) -> List[Dict]:
    """
    Detect programming languages in a repo based on file extension statistics.
    Returns a list of {name, percentage, role} sorted by percentage descending.
    """
    counts, _truncated = _count_files_by_language(
        repo_path, root=root, exclude=exclude, max_files=max_files
    )
    total = sum(counts.values())

    if total == 0:
        # Fallback: try marker-based detection
        for lang in LANGUAGE_MARKERS:
            if _has_marker(repo_path, lang):
                return [{"name": lang, "percentage": 100, "role": "primary"}]
        return [{"name": "python", "percentage": 100, "role": "primary"}]

    # Calculate percentages
    results = []
    for lang, count in counts.items():
        pct = round(count / total * 100, 1)

        # Marker boost: if a language has marker files but low file count,
        # ensure it reaches at least the minimum threshold
        if pct < MIN_PERCENTAGE and _has_marker(repo_path, lang):
            pct = MIN_PERCENTAGE

        if pct >= MIN_PERCENTAGE:
            results.append({"name": lang, "percentage": pct, "role": ""})

    if not results:
        # All languages below threshold, pick the top one
        top_lang = max(counts, key=counts.get)
        results.append({"name": top_lang, "percentage": round(counts[top_lang] / total * 100, 1), "role": ""})

    # Sort by percentage descending
    results.sort(key=lambda x: x["percentage"], reverse=True)

    # Re-normalize percentages after filtering
    reported_total = sum(r["percentage"] for r in results)
    for r in results:
        r["percentage"] = round(r["percentage"] / reported_total * 100, 1)

    # Assign roles
    for i, r in enumerate(results):
        if i == 0:
            r["role"] = "primary"
        elif r["percentage"] >= 20:
            r["role"] = "secondary"
        else:
            r["role"] = "auxiliary"

    return results


def detect_project_language(repo_path: Optional[Path] = None) -> str:
    """Legacy API: return the primary language name as a string."""
    root = repo_path or Path.cwd()
    languages = detect_project_languages(root)
    return languages[0]["name"]


def get_git_remote_url(repo_path: Path) -> str:
    """Get git remote URL for a repository."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def find_git_repos(root: Path) -> Dict[str, Path]:
    """
    Legacy API kept for callers outside this file.
    Now honours codegraph.json and the discovery budget.
    """
    from repo_config import discover_repos
    scope = discover_repos(root)
    return {r["name"]: Path(r["path"]) for r in scope["repos"]}


def scan_environment(
    project_root: str,
    max_repos: Optional[int] = None,
    force: bool = False,
) -> dict:
    """
    Scan project environment and generate language.json.

    Stops *before* doing any expensive work (and writes nothing) when the
    directory holds more repos than allowed - the SKILL layer must then ask the
    user to narrow the scope via codegraph.json.
    """
    root = Path(project_root).resolve()
    config = load_config(root)
    exclude = get_exclude_patterns(config)

    scope = evaluate_scope(root, max_repos=max_repos, force=force, config=config)

    if scope["needs_selection"]:
        return {
            "success": False,
            "status": "needs_repo_selection",
            "reason": "too_many_repos" if scope["over_limit"] else "scan_truncated",
            "scope": scope,
            "suggested_config": suggest_config(scope),
            "config_file": scope["config_file"],
            "message": (
                f"Found {len(scope['repos'])} repositories (limit {scope['max_repos']}). "
                f"Ask the user which repos to keep, then narrow the scope in {CONFIG_FILENAME}."
            ),
        }

    language_json = {}
    for repo in scope["repos"]:
        repo_path = Path(repo["path"])
        languages = detect_project_languages(repo_path, root=root, exclude=exclude)
        language_json[repo["name"]] = {
            "languages": languages,
            "repo_url": get_git_remote_url(repo_path),
        }

    if not language_json:
        language_json[root.name] = {
            "languages": [{"name": "python", "percentage": 100, "role": "primary"}],
            "repo_url": "",
        }

    output_path = root / 'docs' / 'language.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(language_json, f, indent=2, ensure_ascii=False)

    return {
        'success': True,
        'status': 'ok',
        'repos': len(language_json),
        'language_json': str(output_path),
        'languages': language_json,
        'is_multi_repo': len(language_json) > 1,
        'excluded_repos': [r["name"] for r in scope["excluded_repos"]],
        'config_file': scope["config_file"],
    }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Scan project environment and generate language.json')
    parser.add_argument('--root', default=os.getcwd(), help='Project root directory')
    parser.add_argument('--max-repos', type=int, default=None,
                        help='Max repos before asking the user to narrow the scope')
    parser.add_argument('--force', action='store_true',
                        help='Skip the repo-count guard (use only after the user confirmed)')
    parser.add_argument('--json', action='store_true', help='JSON output')

    args = parser.parse_args()

    try:
        result = scan_environment(args.root, max_repos=args.max_repos, force=args.force)

        if result.get('status') == 'needs_repo_selection':
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print_scope_report(result['scope'])
            sys.exit(EXIT_NEEDS_REPO_SELECTION)

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Scanned {result['repos']} repository(ies)")
            print(f"  Language JSON: {result['language_json']}")
            for repo, info in result['languages'].items():
                langs = ", ".join(
                    f"{l['name']}({l['percentage']}%/{l['role']})"
                    for l in info['languages']
                )
                print(f"  - {repo}: {langs} ({info['repo_url'] or 'no remote'})")

            if result['excluded_repos']:
                print(f"  Excluded by {CONFIG_FILENAME}: {', '.join(result['excluded_repos'])}")

            if result['is_multi_repo']:
                print("  (Multi-repo detected)")
            else:
                print("  (Single-repo detected)")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
