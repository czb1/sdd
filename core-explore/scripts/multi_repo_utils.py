"""
多仓工具函数模块。

提供多仓检测、涉及仓分析、共享上下文一致性校验、
contracts生命周期管理等基础机制。

三级降级链：graph.json(P0) -> language.json(P1) -> 目录扫描(P2)
"""

import hashlib
import json
import logging
import os
import tempfile
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "detect_multi_repo",
    "aggregate_repo_edges",
    "expand_involved_repos",
    "extract_section",
    "verify_shared_context_consistency",
    "refresh_contracts_copies",
    "write_contracts_atomic",
    "write_repo_assignments",
]


def detect_multi_repo(project_root: Path) -> Dict[str, Any]:
    """
    检测多仓环境，三级降级链：
    P0: graph.json（脚本生成，最可靠）
    P1: language.json（脚本生成，次可靠）
    P2: 目录扫描（兜底）

    Args:
        project_root: 项目根目录路径

    Returns:
        {
            "is_multi_repo": bool,
            "repos": list[str],       # 仓列表
            "source": str,            # "graph.json" | "language.json" | "directory_scan" | "none"
            "cross_repo_edges": list  # 跨仓依赖边（仅graph.json源）
        }
    """
    # P0: graph.json
    graph_json_path = project_root / "docs" / "graph.json"
    if graph_json_path.exists():
        try:
            with open(graph_json_path, encoding="utf-8") as f:
                graph_data = json.load(f)
            mode = graph_data.get("mode", "")
            if mode == "multi-repo":
                return {
                    "is_multi_repo": True,
                    "repos": graph_data.get("repos", []),
                    "source": "graph.json",
                    "cross_repo_edges": graph_data.get("cross_repo_edges", []),
                }
            if mode == "single-repo":
                return {
                    "is_multi_repo": False,
                    "repos": [],
                    "source": "graph.json",
                    "cross_repo_edges": [],
                }
            # mode字段值未知，降级到P1
            logger.warning(
                "graph.json mode '%s' unrecognized, degrading to P1", mode
            )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to parse graph.json, degrading to P1: %s", exc
            )
    else:
        logger.info("graph.json not found, degrading to P1")

    # P1: language.json
    language_json_path = project_root / "docs" / "language.json"
    if language_json_path.exists():
        try:
            with open(language_json_path, encoding="utf-8") as f:
                language_data = json.load(f)
            keys = list(language_data.keys())
            if len(keys) > 1:
                return {
                    "is_multi_repo": True,
                    "repos": keys,
                    "source": "language.json",
                    "cross_repo_edges": [],
                }
            return {
                "is_multi_repo": False,
                "repos": keys if keys else [],
                "source": "language.json",
                "cross_repo_edges": [],
            }
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to parse language.json, degrading to P2: %s", exc
            )
    else:
        logger.info("language.json not found, degrading to P2")

    # P2: 目录扫描
    git_dirs = []
    try:
        for entry in project_root.iterdir():
            if entry.is_dir() and (entry / ".git").exists():
                git_dirs.append(entry.name)
    except OSError as exc:
        logger.warning("Failed to scan directories for .git: %s", exc)
        return {
            "is_multi_repo": False,
            "repos": [],
            "source": "none",
            "cross_repo_edges": [],
        }

    if len(git_dirs) >= 2:
        return {
            "is_multi_repo": True,
            "repos": git_dirs,
            "source": "directory_scan",
            "cross_repo_edges": [],
        }

    return {
        "is_multi_repo": False,
        "repos": git_dirs,
        "source": "directory_scan" if git_dirs else "none",
        "cross_repo_edges": [],
    }


def aggregate_repo_edges(edges: List[Dict]) -> Dict[Tuple[str, str], int]:
    """
    按(src_repo, tgt_repo)聚合所有kind的边权重。

    同一对仓之间可能有多条边（calls/imports/extends等），
    聚合后判断总权重，避免低频依赖被分散后遗漏。

    Args:
        edges: graph.json中的cross_repo_edges数组，每条边含
               src_repo, tgt_repo, kind, count字段

    Returns:
        {(src_repo, tgt_repo): total_count} 聚合后的边权重映射
    """
    aggregated: Dict[Tuple[str, str], int] = {}
    for edge in edges:
        src = edge.get("src_repo", "")
        tgt = edge.get("tgt_repo", "")
        count = edge.get("count", 0)
        if not src or not tgt:
            continue
        key = (src, tgt)
        aggregated[key] = aggregated.get(key, 0) + count
    return aggregated


def expand_involved_repos(
    project_root: Path,
    anchor_repos: List[str],
    depth: int = 1,
    min_edge_weight: int = 10,
) -> Dict[str, Any]:
    """
    从锚定仓沿cross_repo_edges扩展，发现隐含关联仓。

    Args:
        project_root: 项目根目录
        anchor_repos: Agent语义初判确定的锚定仓
        depth: 扩展深度（默认1层）
        min_edge_weight: 聚合权重阈值，>=threshold才纳入扩展仓

    Returns:
        {
            "anchor_repos": list[str],
            "expanded_repos": list[str],
            "expansion_reason": dict  # {repo: reason}
        }
    """
    graph_json_path = project_root / "docs" / "graph.json"
    if not graph_json_path.exists():
        return {
            "anchor_repos": anchor_repos,
            "expanded_repos": [],
            "expansion_reason": {},
        }

    try:
        with open(graph_json_path, encoding="utf-8") as f:
            graph_data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read graph.json for expansion: %s", exc)
        return {
            "anchor_repos": anchor_repos,
            "expanded_repos": [],
            "expansion_reason": {},
        }

    cross_repo_edges = graph_data.get("cross_repo_edges", [])
    if not cross_repo_edges:
        return {
            "anchor_repos": anchor_repos,
            "expanded_repos": [],
            "expansion_reason": {},
        }

    weighted_edges = aggregate_repo_edges(cross_repo_edges)

    # BFS from anchor_repos
    visited = set(anchor_repos)
    queue: deque[Tuple[str, int]] = deque()
    for repo in anchor_repos:
        queue.append((repo, 0))

    expanded_repos: List[str] = []
    expansion_reason: Dict[str, str] = {}

    while queue:
        current_repo, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        for (src, tgt), weight in weighted_edges.items():
            neighbor = None
            direction = ""
            if src == current_repo and tgt not in visited:
                neighbor = tgt
                direction = f"outgoing to {tgt} (weight={weight})"
            elif tgt == current_repo and src not in visited:
                neighbor = src
                direction = f"incoming from {src} (weight={weight})"

            if neighbor is not None and weight >= min_edge_weight:
                visited.add(neighbor)
                expanded_repos.append(neighbor)
                expansion_reason[neighbor] = (
                    f"Expanded from {current_repo} via {direction}"
                )
                queue.append((neighbor, current_depth + 1))

    return {
        "anchor_repos": anchor_repos,
        "expanded_repos": expanded_repos,
        "expansion_reason": expansion_reason,
    }


def extract_section(content: str, heading: str) -> str:
    """
    提取Markdown章节内容，标题匹配失败时降级为逐行搜索。

    Priority: exact heading match (## {heading})
    Fallback: line-by-line search for heading keyword

    Args:
        content: Markdown全文内容
        heading: 要提取的章节标题（不含#前缀）

    Returns:
        提取的章节内容（不含标题行），未匹配时返回空字符串
    """
    lines = content.split("\n")
    section_lines: List[str] = []
    in_section = False
    heading_level = 0

    # Priority: exact heading match
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            current_level = len(stripped) - len(stripped.lstrip("#"))
            current_heading = stripped.lstrip("#").strip()
            if not in_section and current_heading == heading:
                in_section = True
                heading_level = current_level
                continue
            if in_section and current_level <= heading_level:
                break
        if in_section:
            section_lines.append(line)

    if section_lines:
        return "\n".join(section_lines).strip()

    # Fallback: line-by-line keyword search
    keyword = heading.split()[0] if heading.split() else heading
    in_section = False
    heading_level = 0
    section_lines = []

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            current_level = len(stripped) - len(stripped.lstrip("#"))
            current_heading = stripped.lstrip("#").strip()
            if not in_section and keyword in current_heading:
                in_section = True
                heading_level = current_level
                continue
            if in_section and current_level <= heading_level:
                break
        if in_section:
            section_lines.append(line)

    return "\n".join(section_lines).strip()


def verify_shared_context_consistency(
    shared_context_path: Path,
    change_name: str,
    repos: List[str],
    project_root: Path,
) -> Dict[str, Any]:
    """
    严格hash比对各仓proposal共享章节与shared_context.md的一致性。

    Args:
        shared_context_path: shared_context.md文件路径
        change_name: 变更名
        repos: 涉及仓列表
        project_root: 项目根目录

    Returns:
        {"consistent": bool, "inconsistencies": [{"repo": str, "mismatched_sections": [str]}]}
    """
    if not shared_context_path.exists():
        return {
            "consistent": False,
            "inconsistencies": [
                {
                    "repo": "shared_context",
                    "mismatched_sections": [
                        f"shared_context.md not found at {shared_context_path}"
                    ],
                }
            ],
        }

    try:
        shared_content = shared_context_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to read shared_context.md: %s", exc)
        return {
            "consistent": False,
            "inconsistencies": [
                {
                    "repo": "shared_context",
                    "mismatched_sections": [f"Read error: {exc}"],
                }
            ],
        }

    # Extract shared sections from shared_context.md
    shared_sections = _extract_shared_sections(shared_content)

    inconsistencies: List[Dict[str, Any]] = []

    for repo in repos:
        proposal_path = (
            project_root
            / repo
            / "docs"
            / "changes"
            / change_name
            / "proposal.md"
        )
        if not proposal_path.exists():
            logger.info(
                "Proposal not found for repo %s: %s", repo, proposal_path
            )
            continue

        try:
            proposal_content = proposal_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to read proposal for %s: %s", repo, exc)
            continue

        mismatched: List[str] = []
        for section_name, shared_text in shared_sections.items():
            proposal_section = extract_section(proposal_content, section_name)
            if not proposal_section:
                continue
            shared_hash = hashlib.sha256(
                shared_text.encode("utf-8")
            ).hexdigest()
            proposal_hash = hashlib.sha256(
                proposal_section.encode("utf-8")
            ).hexdigest()
            if shared_hash != proposal_hash:
                # shared_context.md is authoritative, record the mismatch
                mismatched.append(section_name)
                logger.info(
                    "Section '%s' mismatch in repo %s, "
                    "shared_context.md is authoritative",
                    section_name,
                    repo,
                )

        if mismatched:
            inconsistencies.append(
                {"repo": repo, "mismatched_sections": mismatched}
            )

    return {
        "consistent": len(inconsistencies) == 0,
        "inconsistencies": inconsistencies,
    }


def _extract_shared_sections(content: str) -> Dict[str, str]:
    """
    从shared_context.md内容提取各章节。

    仅提取二级标题(##)作为共享章节。

    Args:
        content: shared_context.md全文

    Returns:
        {section_heading: section_content} 映射
    """
    sections: Dict[str, str] = {}
    lines = content.split("\n")
    current_heading = None
    current_lines: List[str] = []

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            if current_heading is not None:
                sections[current_heading] = "\n".join(
                    current_lines
                ).strip()
            current_heading = stripped[3:].strip()
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


def refresh_contracts_copies(
    project_root: Path,
    change_name: str,
    involved_repos: List[str] = None,
) -> None:
    """
    将根级主副本刷新到各涉及仓副本。

    根级主副本: docs/changes/<change>/clarifications/cross_repo_contracts.json
    各仓副本: {repo}/docs/changes/<change>/cross_repo_contracts.json

    Args:
        project_root: 项目根目录
        change_name: 变更名
        involved_repos: 涉及仓列表，None时自动从contracts中提取所有涉及仓
    """
    master_path = (
        project_root
        / "docs"
        / "changes"
        / change_name
        / "clarifications"
        / "cross_repo_contracts.json"
    )

    if not master_path.exists():
        logger.warning("Contracts master copy not found: %s", master_path)
        return

    try:
        with open(master_path, encoding="utf-8") as f:
            contracts_data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read contracts master copy: %s", exc)
        return

    # Auto-extract repos if not provided
    if involved_repos is None:
        involved_repos = _extract_involved_repos_from_contracts(
            contracts_data
        )

    for repo in involved_repos:
        repo_copy_path = (
            project_root
            / repo
            / "docs"
            / "changes"
            / change_name
            / "cross_repo_contracts.json"
        )
        write_contracts_atomic(repo_copy_path, contracts_data)
        logger.info("Refreshed contracts copy for repo %s", repo)


def _extract_involved_repos_from_contracts(
    contracts_data: Dict,
) -> List[str]:
    """
    从contracts数据中提取所有涉及仓。

    Args:
        contracts_data: cross_repo_contracts.json的内容

    Returns:
        去重后的涉及仓列表
    """
    repos = set()
    contracts = contracts_data.get("contracts", [])
    for contract in contracts:
        definition_repo = contract.get("definition_repo", "")
        consumer_repos = contract.get("consumer_repos", [])
        if definition_repo:
            repos.add(definition_repo)
        for repo in consumer_repos:
            repos.add(repo)
    return sorted(repos)


def write_contracts_atomic(path: Path, data: Dict) -> None:
    """
    原子性写入：先写入临时文件，再rename替换目标文件。

    Args:
        path: 目标文件路径
        data: 要写入的数据
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, indent=2)

    # Write to temp file first, then rename for atomicity
    try:
        fd, tmp_path = tempfile.mkstemp(
            suffix=".tmp",
            dir=str(path.parent),
            prefix=".contracts_",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                tmp_file.write(content)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_path, str(path))
        except BaseException:
            # Clean up temp file on any error
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError as exc:
        logger.warning(
            "Atomic write failed for %s: %s", path, exc
        )
        # Fallback: direct write (non-atomic but better than nothing)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as fallback_exc:
            logger.error(
                "Fallback write also failed for %s: %s", path, fallback_exc
            )
            raise


def write_repo_assignments(
    project_root: Path,
    change_name: str,
    anchor_repos: List[str],
    expanded_repos: List[str],
    expansion_reason: Dict[str, str],
) -> Path:
    """
    写入repo_assignments.json到docs/changes/<change>/目录。

    Args:
        project_root: 项目根目录
        change_name: 变更名
        anchor_repos: 锚定仓列表
        expanded_repos: 扩展仓列表
        expansion_reason: 扩展理由映射

    Returns:
        repo_assignments.json的路径
    """
    assignments_path = (
        project_root
        / "docs"
        / "changes"
        / change_name
        / "repo_assignments.json"
    )

    involved_repos = sorted(set(anchor_repos + expanded_repos))

    data = {
        "change_name": change_name,
        "involved_repos": involved_repos,
        "confirmed_at": datetime.now().isoformat(),
        "anchor_repos": anchor_repos,
        "expanded_repos": expanded_repos,
        "expansion_reason": expansion_reason,
    }

    write_contracts_atomic(assignments_path, data)
    return assignments_path
