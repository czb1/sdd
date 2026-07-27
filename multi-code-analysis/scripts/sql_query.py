"""
SQL query executor for codegraph.db using Python's built-in sqlite3 module.

Provides a CLI for executing SQL queries against codegraph.db when the
sqlite3 CLI tool is not available. Also offers preset queries for common
analysis tasks defined in SKILL.md.

Usage:
    python sql_query.py <db_path> --sql "SELECT ..."
    python sql_query.py <db_path> --preset cross-repo
    python sql_query.py <db_path> --preset single-repo
    python sql_query.py <db_path> --preset repo-stats
    python sql_query.py <db_path> --preset ambiguous
    python sql_query.py <db_path> --preset file-deps --file "repo/path/to/file"
    python sql_query.py <db_path> --preset reverse-deps --file "repo/path/to/file"
    python sql_query.py <db_path> --preset cross-repo-chain --repo-src A --repo-tgt B
    python sql_query.py <db_path> --preset fuzzy-search --keyword "xxx"
    python sql_query.py <db_path> --preset unresolved --repo "repo_name"
    python sql_query.py <db_path> --preset unresolved-top
    python sql_query.py <db_path> --sql-file queries.sql
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import List, Optional, Tuple


# --- Preset SQL queries from SKILL.md ---

PRESET_QUERIES = {
    "cross-repo": """
SELECT
    SUBSTR(n1.file_path, 1, INSTR(n1.file_path, '/') - 1) AS src_repo,
    SUBSTR(n2.file_path, 1, INSTR(n2.file_path, '/') - 1) AS tgt_repo,
    e.kind,
    COUNT(*) AS cnt
FROM edges e
JOIN nodes n1 ON e.source = n1.id
JOIN nodes n2 ON e.target = n2.id
WHERE n1.file_path IS NOT NULL AND n2.file_path IS NOT NULL
  AND n1.file_path != '' AND n2.file_path != ''
  AND SUBSTR(n1.file_path, 1, INSTR(n1.file_path, '/') - 1) != SUBSTR(n2.file_path, 1, INSTR(n2.file_path, '/') - 1)
GROUP BY src_repo, tgt_repo, e.kind
ORDER BY cnt DESC
""",
    "single-repo": """
SELECT
    CASE
        WHEN INSTR(SUBSTR(n1.file_path, INSTR(n1.file_path, '/') + 1), '/') > 0
        THEN SUBSTR(n1.file_path, 1, INSTR(SUBSTR(n1.file_path, INSTR(n1.file_path, '/') + 1), '/') + INSTR(n1.file_path, '/') - 1)
        ELSE SUBSTR(n1.file_path, 1, INSTR(n1.file_path, '/') - 1)
    END AS src_dir,
    CASE
        WHEN INSTR(SUBSTR(n2.file_path, INSTR(n2.file_path, '/') + 1), '/') > 0
        THEN SUBSTR(n2.file_path, 1, INSTR(SUBSTR(n2.file_path, INSTR(n2.file_path, '/') + 1), '/') + INSTR(n2.file_path, '/') - 1)
        ELSE SUBSTR(n2.file_path, 1, INSTR(n2.file_path, '/') - 1)
    END AS tgt_dir,
    COUNT(*) AS cnt
FROM edges e
JOIN nodes n1 ON e.source = n1.id
JOIN nodes n2 ON e.target = n2.id
WHERE n1.file_path IS NOT NULL AND n2.file_path IS NOT NULL
  AND n1.file_path != '' AND n2.file_path != ''
  AND SUBSTR(n1.file_path, 1, INSTR(n1.file_path, '/') - 1) = SUBSTR(n2.file_path, 1, INSTR(n2.file_path, '/') - 1)
GROUP BY src_dir, tgt_dir
ORDER BY cnt DESC
""",
    "repo-stats": """
SELECT
    SUBSTR(n.file_path, 1, INSTR(n.file_path, '/') - 1) AS repo,
    COUNT(DISTINCT n.id) AS node_count,
    COUNT(DISTINCT n.file_path) AS file_count
FROM nodes n
WHERE n.file_path IS NOT NULL AND n.file_path != ''
GROUP BY repo
ORDER BY repo
""",
    "ambiguous": """
SELECT
    SUBSTR(n.file_path, INSTR(n.file_path, '/') + 1) AS relative_path,
    COUNT(DISTINCT SUBSTR(n.file_path, 1, INSTR(n.file_path, '/') - 1)) AS repo_count,
    GROUP_CONCAT(DISTINCT SUBSTR(n.file_path, 1, INSTR(n.file_path, '/') - 1)) AS repos
FROM nodes n
WHERE n.file_path IS NOT NULL AND n.file_path != '' AND n.kind = 'file'
GROUP BY relative_path
HAVING repo_count > 1
ORDER BY repo_count DESC
""",
    "file-deps": """
SELECT DISTINCT n2.file_path
FROM edges e
JOIN nodes n1 ON e.source = n1.id
JOIN nodes n2 ON e.target = n2.id
WHERE n1.file_path = ?
ORDER BY n2.file_path
""",
    "reverse-deps": """
SELECT DISTINCT n1.file_path
FROM edges e
JOIN nodes n1 ON e.source = n1.id
JOIN nodes n2 ON e.target = n2.id
WHERE n2.file_path = ?
ORDER BY n1.file_path
""",
    "cross-repo-chain": """
SELECT
    n1.file_path AS src_file,
    n1.name AS src_symbol,
    n1.kind AS src_kind,
    n2.file_path AS tgt_file,
    n2.name AS tgt_symbol,
    n2.kind AS tgt_kind,
    e.kind AS edge_kind,
    e.line,
    e.col
FROM edges e
JOIN nodes n1 ON e.source = n1.id
JOIN nodes n2 ON e.target = n2.id
WHERE SUBSTR(n1.file_path, 1, INSTR(n1.file_path, '/') - 1) = ?
  AND SUBSTR(n2.file_path, 1, INSTR(n2.file_path, '/') - 1) = ?
ORDER BY n1.file_path, n2.file_path
""",
    "fuzzy-search": """
SELECT id, name, kind, file_path, start_line
FROM nodes
WHERE name LIKE ?
ORDER BY kind, name
LIMIT 20
""",
    "unresolved": """
SELECT * FROM unresolved_refs
WHERE file_path LIKE ?
LIMIT 20
""",
    "unresolved-top": """
SELECT file_path, COUNT(*) AS cnt
FROM unresolved_refs
GROUP BY file_path
ORDER BY cnt DESC
LIMIT 10
""",
    "lang-stats": """
SELECT language, COUNT(*) AS cnt FROM files GROUP BY language ORDER BY cnt DESC
""",
    "node-kind-stats": """
SELECT kind, COUNT(*) AS cnt FROM nodes GROUP BY kind ORDER BY cnt DESC
""",
    "edge-kind-stats": """
SELECT kind, COUNT(*) AS cnt FROM edges GROUP BY kind ORDER BY cnt DESC
""",
}

PRESET_PARAMS = {
    "file-deps": ["file"],
    "reverse-deps": ["file"],
    "cross-repo-chain": ["repo-src", "repo-tgt"],
    "fuzzy-search": ["keyword"],
    "unresolved": ["repo"],
}


def execute_query(
    db_path: Path,
    sql: str,
    params: Optional[Tuple] = None
) -> Tuple[List[str], List[List]]:
    """Execute a SQL query and return (headers, rows)."""
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(sql, params or ())
        headers = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return headers, rows
    finally:
        conn.close()


def format_table(headers: List[str], rows: List[List]) -> str:
    """Format query results as a markdown table."""
    if not headers:
        return "(no results)"

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))

    sep = "|" + "|".join("-" * (w + 2) for w in col_widths) + "|"
    header_line = "|" + "|".join(f" {h:<{col_widths[i]}} " for i, h in enumerate(headers)) + "|"

    lines = [header_line, sep]
    for row in rows:
        line = "|" + "|".join(f" {str(val):<{col_widths[i]}} " for i, val in enumerate(row)) + "|"
        lines.append(line)

    return "\n".join(lines)


def find_db_path(db_path: str) -> Path:
    """Resolve codegraph.db path, auto-detecting if needed."""
    p = Path(db_path)
    if p.is_file():
        return p
    if p.is_dir():
        candidates = [p / "codegraph.db", p / ".codegraph" / "codegraph.db"]
        for c in candidates:
            if c.exists():
                return c
    raise FileNotFoundError(
        f"codegraph.db not found at {db_path}. "
        f"Searched: {p}, {p}/codegraph.db, {p}/.codegraph/codegraph.db"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Execute SQL queries against codegraph.db (Python sqlite3, no CLI dependency)"
    )
    parser.add_argument("db_path", nargs="?", help="Path to codegraph.db or its parent directory (not required for --list-presets)")
    parser.add_argument("--sql", help="Raw SQL query to execute")
    parser.add_argument("--sql-file", help="Path to a .sql file to execute")
    parser.add_argument("--preset", choices=list(PRESET_QUERIES.keys()), help="Preset query name")
    parser.add_argument("--file", help="File path parameter (for file-deps/reverse-deps presets)")
    parser.add_argument("--repo-src", help="Source repo parameter (for cross-repo-chain preset)")
    parser.add_argument("--repo-tgt", help="Target repo parameter (for cross-repo-chain preset)")
    parser.add_argument("--keyword", help="Keyword parameter (for fuzzy-search preset)")
    parser.add_argument("--repo", help="Repo name parameter (for unresolved preset)")
    parser.add_argument("--limit", type=int, default=0, help="Limit result rows (0=unlimited)")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of markdown table")
    parser.add_argument("--list-presets", action="store_true", help="List all preset queries and exit")

    args = parser.parse_args()

    if args.list_presets:
        print("Available preset queries:")
        for name, sql in PRESET_QUERIES.items():
            params = PRESET_PARAMS.get(name, [])
            param_str = ", ".join(f"--{p}" for p in params) if params else "no params"
            print(f"  {name:20s} ({param_str})")
        return

    # Resolve SQL source
    sql = None
    params = None

    if args.preset:
        sql = PRESET_QUERIES[args.preset]
        required_params = PRESET_PARAMS.get(args.preset, [])
        param_values = []
        for p in required_params:
            val = getattr(args, p.replace("-", "_"), None)
            if not val:
                print(f"Error: --{p} required for preset '{args.preset}'")
                sys.exit(1)
            if p in ("fuzzy-search",):
                param_values.append(f"%{val}%")
            elif p == "repo":
                param_values.append(f"{val}/%")
            else:
                param_values.append(val)
        params = tuple(param_values) if param_values else None
    elif args.sql:
        sql = args.sql
    elif args.sql_file:
        sql_path = Path(args.sql_file)
        if not sql_path.exists():
            print(f"Error: SQL file not found: {sql_path}")
            sys.exit(1)
        sql = sql_path.read_text(encoding="utf-8")
    else:
        print("Error: specify --sql, --sql-file, or --preset")
        parser.print_help()
        sys.exit(1)

    # Find database
    try:
        db = find_db_path(args.db_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Execute
    try:
        headers, rows = execute_query(db, sql, params)
    except sqlite3.OperationalError as e:
        print(f"SQL Error: {e}")
        sys.exit(1)

    if args.limit > 0 and len(rows) > args.limit:
        rows = rows[:args.limit]

    # Output
    if args.json:
        import json
        result = [dict(zip(headers, row)) for row in rows]
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if not rows:
            print("(no results)")
        else:
            print(format_table(headers, rows))
            print(f"\n({len(rows)} rows)")


if __name__ == "__main__":
    main()
