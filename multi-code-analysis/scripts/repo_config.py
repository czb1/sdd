"""
Repo scope configuration & guarded repo discovery for core-init.

Why this module exists
----------------------
`/core-init` used to scan every sub-directory of the launch directory for
`.git`, and every discovered repo was then fed to scan_language ->
multi-code-analysis -> codewiki-sync. When the user launches from a directory
that holds dozens of repos (a "workspace" / super-repo), that pipeline explodes:
huge language.json, minutes of file walking, and N x codewiki-sync loops.

This module adds two things:

1. 防爆 (blast guard): repo discovery is bounded (max dirs visited, max depth)
   and refuses to continue when more repos are found than `maxRepos`. The
   caller is expected to ask the user which repos to keep.

2. User-owned configuration, modelled on CodeGraph's own `codegraph.json`
   (https://colbymchenry.github.io/codegraph/getting-started/configuration/):

   {
     "exclude": ["static/", "**/vendor/**", "legacy-repo/"],
     "include": ["Tools/"],
     "includeIgnored": ["packages/"],
     "extensions": {".tpl": "php"},
     "corespec": { "maxRepos": 8 }
   }

   `exclude` / `include` are the CodeGraph keys, so the same file drives both
   CodeGraph indexing *and* core-init's repo scope - one file, one source of
   truth. `corespec` holds core-init-only settings; CodeGraph ignores unknown
   top-level keys.

Pattern syntax is a pragmatic subset of gitignore, matched against
project-root-relative paths:
  - "name"          -> matches any path segment called `name`
  - "dir/"          -> matches `dir` and everything under it
  - "a/b"           -> matches that path and everything under it
  - "**/vendor/**"  -> matches `vendor` at any depth
  - "!keep-me/"     -> negation, last matching pattern wins
An explicit `exclude` always wins over `include` (same rule as CodeGraph).
"""

import fnmatch
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

CONFIG_FILENAME = "codegraph.json"

# ---------------------------------------------------------------- 防爆 defaults
DEFAULT_MAX_REPOS = 5          # more repos than this -> ask the user
DEFAULT_MAX_SCAN_DIRS = 3000   # hard cap on directories visited while discovering
DEFAULT_MAX_DEPTH = 2          # how deep below project root we look for `.git`

# Directories never walked into and never treated as repos.
BUILTIN_SKIP_DIRS = {
    "node_modules", "vendor", "third_party", "thirdparty", "external",
    "dist", "build", "out", "target", "__pycache__", ".git", ".svn",
    ".hg", ".idea", ".vscode", ".cache", ".tox", ".mypy_cache",
    ".pytest_cache", ".gradle", ".mvn", "venv", ".venv", "env",
    ".env", "Pods", "bazel-bin", "bazel-out", "bazel-testlogs", ".bazel",
    ".codegraph", "docs",
}

# Cheap, no-walk language guess used only for the repo-selection preview.
MARKER_LANGUAGE = [
    ("pom.xml", "java"),
    ("build.gradle", "java"),
    ("build.gradle.kts", "kotlin"),
    ("go.mod", "go"),
    ("Cargo.toml", "rust"),
    ("pyproject.toml", "python"),
    ("requirements.txt", "python"),
    ("setup.py", "python"),
    ("tsconfig.json", "ts"),
    ("package.json", "js"),
    ("composer.json", "php"),
    ("Gemfile", "ruby"),
    ("pubspec.yaml", "dart"),
    ("CMakeLists.txt", "cpp"),
]


# --------------------------------------------------------------- path matching
def norm(path) -> str:
    """Normalize to a forward-slash, no-leading/trailing-slash relative path."""
    return str(path).replace("\\", "/").strip("/")


def _match_one(pattern: str, rel_path: str) -> bool:
    """Match a single (non-negated) gitignore-style pattern against rel_path."""
    pat = norm(pattern)
    path = norm(rel_path)
    if not pat or not path:
        return False

    if pat.endswith("/**"):
        pat = pat[:-3]
    pat = pat.strip("/")
    if not pat:
        return False

    segments = path.split("/")

    # Bare name with no separator: match any segment (gitignore behaviour).
    if "/" not in pat:
        return any(fnmatch.fnmatch(seg, pat) for seg in segments)

    variants = [pat]
    if pat.startswith("**/"):
        variants.append(pat[3:])

    # Match the path itself and every parent, so "a/b" also excludes "a/b/c".
    candidates = ["/".join(segments[:i]) for i in range(1, len(segments) + 1)]
    return any(fnmatch.fnmatch(c, v) for c in candidates for v in variants)


def is_excluded(rel_path: str, exclude_patterns: Optional[List[str]]) -> bool:
    """Gitignore semantics: last matching pattern wins, `!` negates."""
    excluded = False
    for raw in exclude_patterns or []:
        pat = str(raw).strip()
        if not pat or pat.startswith("#"):
            continue
        negated = pat.startswith("!")
        if negated:
            pat = pat[1:]
        if _match_one(pat, rel_path):
            excluded = not negated
    return excluded


# ---------------------------------------------------------------------- config
def config_path(project_root) -> Path:
    return Path(project_root) / CONFIG_FILENAME


def load_config(project_root) -> dict:
    """Load codegraph.json. A malformed file warns and is treated as empty."""
    path = config_path(project_root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # never break init on a bad config
        print(f"[core-init] WARNING: cannot parse {path}: {exc} (ignored)")
        return {}


def save_config(project_root, config: dict) -> Path:
    path = config_path(project_root)
    path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def get_exclude_patterns(config: dict) -> List[str]:
    value = config.get("exclude") or []
    return [str(v) for v in value] if isinstance(value, list) else []


def get_include_patterns(config: dict) -> List[str]:
    value = config.get("include") or []
    return [str(v) for v in value] if isinstance(value, list) else []


def get_max_repos(config: dict, cli_value: Optional[int] = None) -> int:
    if cli_value:
        return int(cli_value)
    env = os.environ.get("CORESPEC_MAX_REPOS")
    if env and env.isdigit():
        return int(env)
    corespec = config.get("corespec")
    if isinstance(corespec, dict) and str(corespec.get("maxRepos", "")).isdigit():
        return int(corespec["maxRepos"])
    return DEFAULT_MAX_REPOS


# ------------------------------------------------------------- repo discovery
def _guess_language(repo_path: Path) -> str:
    for marker, lang in MARKER_LANGUAGE:
        if (repo_path / marker).exists():
            return lang
    return "unknown"


def discover_repos(
    project_root,
    config: Optional[dict] = None,
    max_dirs: int = DEFAULT_MAX_SCAN_DIRS,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> dict:
    """
    Find git repos under project_root, bounded and honouring codegraph.json.

    Returns:
        {
          "root": str,
          "repos": [{"name", "path", "language_hint"}],
          "excluded_repos": [{"name", "path", "reason"}],
          "is_multi_repo": bool,
          "truncated": bool,      # scan budget hit -> result may be incomplete
          "dirs_scanned": int,
        }
    """
    root = Path(project_root).resolve()
    config = load_config(root) if config is None else config
    exclude = get_exclude_patterns(config)

    repos: List[dict] = []
    excluded: List[dict] = []
    visited = 0
    truncated = False

    stack = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            entries = sorted(p for p in current.iterdir() if p.is_dir())
        except (PermissionError, OSError):
            continue

        for entry in entries:
            visited += 1
            if visited > max_dirs:
                truncated = True
                stack = []
                break

            name = entry.name
            if name in BUILTIN_SKIP_DIRS or name.startswith("."):
                continue

            rel = norm(entry.relative_to(root))
            is_repo = (entry / ".git").exists()

            if is_excluded(rel, exclude):
                if is_repo:
                    excluded.append(
                        {"name": rel, "path": str(entry), "reason": f"excluded by {CONFIG_FILENAME}"}
                    )
                continue

            if is_repo:
                repos.append(
                    {"name": rel, "path": str(entry), "language_hint": _guess_language(entry)}
                )
                continue  # never descend into a repo

            if depth + 1 < max_depth:
                stack.append((entry, depth + 1))

    # No sub-repos -> the root itself is the (single) repo.
    if not repos:
        repos.append(
            {
                "name": root.name,
                "path": str(root),
                "language_hint": _guess_language(root),
                "is_root": True,
            }
        )

    repos.sort(key=lambda r: r["name"].lower())
    return {
        "root": str(root),
        "repos": repos,
        "excluded_repos": excluded,
        "is_multi_repo": len(repos) > 1,
        "truncated": truncated,
        "dirs_scanned": visited,
    }


def evaluate_scope(
    project_root,
    max_repos: Optional[int] = None,
    force: bool = False,
    config: Optional[dict] = None,
) -> dict:
    """
    Discover repos and decide whether the agent must stop and ask the user.

    `needs_selection` is True when more repos were found than allowed, or when
    the discovery budget was exhausted (meaning the directory is huge).
    """
    root = Path(project_root).resolve()
    config = load_config(root) if config is None else config
    limit = get_max_repos(config, max_repos)

    scope = discover_repos(root, config=config)
    over_limit = len(scope["repos"]) > limit
    scope.update(
        {
            "max_repos": limit,
            "config_file": str(config_path(root)),
            "config_exists": config_path(root).exists(),
            "over_limit": over_limit,
            "forced": bool(force),
            "needs_selection": bool((over_limit or scope["truncated"]) and not force),
        }
    )
    return scope


# -------------------------------------------------------------- config writing
def repo_exclude_pattern(repo_name: str) -> str:
    return norm(repo_name) + "/"


def suggest_config(scope: dict, keep: Optional[List[str]] = None) -> dict:
    """Build a codegraph.json skeleton the user can copy/edit by hand."""
    keep_set = {norm(k) for k in (keep or [])}
    exclude = [
        repo_exclude_pattern(r["name"])
        for r in scope.get("repos", [])
        if not keep_set or norm(r["name"]) not in keep_set
    ]
    return {
        "exclude": exclude,
        "corespec": {"maxRepos": scope.get("max_repos", DEFAULT_MAX_REPOS)},
    }


def apply_repo_selection(
    project_root,
    keep: Optional[List[str]] = None,
    add_exclude: Optional[List[str]] = None,
    add_include: Optional[List[str]] = None,
    max_repos: Optional[int] = None,
    reset: bool = False,
) -> dict:
    """
    Persist the user's repo scope decision into codegraph.json.

    keep:        repo names to KEEP; every other discovered repo gets an
                 `exclude` entry. Empty/None -> keep whatever is there.
    add_exclude: extra raw gitignore-style patterns (e.g. "static/").
    add_include: raw patterns for `include` (gitignored first-party source).
    reset:       drop the existing exclude list before applying.
    """
    root = Path(project_root).resolve()
    config = load_config(root)

    if reset:
        config["exclude"] = []

    exclude = get_exclude_patterns(config)
    include = get_include_patterns(config)

    # Discover with an *empty* exclude so already-excluded repos stay visible.
    raw_scope = discover_repos(root, config={})
    all_names = [r["name"] for r in raw_scope["repos"]]

    unknown = []
    if keep:
        keep_set = {norm(k) for k in keep}
        unknown = sorted(k for k in keep_set if k not in {norm(n) for n in all_names})
        for name in all_names:
            if norm(name) in keep_set:
                # un-exclude if it was excluded before
                exclude = [p for p in exclude if norm(p).rstrip("/") != norm(name)]
                continue
            pattern = repo_exclude_pattern(name)
            if pattern not in exclude:
                exclude.append(pattern)

    for pattern in add_exclude or []:
        pattern = str(pattern).strip()
        if pattern and pattern not in exclude:
            exclude.append(pattern)

    for pattern in add_include or []:
        pattern = str(pattern).strip()
        if pattern and pattern not in include:
            include.append(pattern)

    if exclude:
        config["exclude"] = exclude
    if include:
        config["include"] = include
    if max_repos:
        corespec = config.get("corespec")
        if not isinstance(corespec, dict):
            corespec = {}
        corespec["maxRepos"] = int(max_repos)
        config["corespec"] = corespec

    path = save_config(root, config)
    scope = evaluate_scope(root, max_repos=max_repos, config=config)

    return {
        "success": True,
        "config_file": str(path),
        "config": config,
        "unknown_repos": unknown,
        "active_repos": [r["name"] for r in scope["repos"]],
        "excluded_repos": [r["name"] for r in scope["excluded_repos"]],
        "needs_selection": scope["needs_selection"],
        "hint": "Re-index after changing exclude/include: `codegraph index`",
    }


# --------------------------------------------------------------- pretty output
def print_scope_report(scope: dict) -> None:
    root = scope.get("root", "")
    repos = scope.get("repos", [])
    print(f"Project root: {root}")
    print(f"Config file : {scope.get('config_file')}"
          f"{'' if scope.get('config_exists') else '  (not created yet)'}")
    print(f"Discovered  : {len(repos)} repo(s), limit = {scope.get('max_repos')}"
          f", dirs scanned = {scope.get('dirs_scanned')}")

    for repo in repos:
        print(f"  - {repo['name']}  [{repo.get('language_hint', 'unknown')}]")

    if scope.get("excluded_repos"):
        print(f"\nExcluded by {CONFIG_FILENAME} ({len(scope['excluded_repos'])}):")
        for repo in scope["excluded_repos"]:
            print(f"  x {repo['name']}")

    if scope.get("truncated"):
        print("\n!! Directory scan budget exhausted - this directory is very large.")
        print("   The repo list above is INCOMPLETE.")

    if scope.get("needs_selection"):
        print("\n!! Too many repositories for a safe /core-init run.")
        print("   Pick the repos to keep, then run:")
        print("     main.py set-repo-scope --project-root <root> --repos repo_a,repo_b")
        print(f"   ...or edit {CONFIG_FILENAME} by hand (gitignore-style patterns):")
        print(json.dumps(suggest_config(scope), indent=2, ensure_ascii=False))
