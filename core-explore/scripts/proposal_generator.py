#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
proposal.md 生成器
按照 spec工程规范.md 1.5.1 要求生成 proposal.md
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


def generate_proposal(
    requirement_id: str,
    requirement_data: Dict[str, Any],
    output_dir: str = "."
) -> str:
    """
    生成 proposal.md 文件

    Args:
        requirement_id: 需求ID
        requirement_data: 需求信息字典
        output_dir: 输出目录

    Returns:
        生成的文件路径
    """
    output_path = Path(output_dir) / "proposal.md"

    content = _build_proposal_content(requirement_id, requirement_data)

    # 写入文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    return str(output_path)


def _build_proposal_content(requirement_id: str, requirement_data: Dict[str, Any]) -> str:
    """
    构建 proposal.md 内容

    按照 spec工程规范.md 1.5.1 要求:
    1. 背景与动机（现状痛点 + 业务驱动）
    2. 变更内容（功能清单 + 用户故事 + 不在范围内）
    3. 影响分析（受影响的规格 / 设计章节、破坏性变更、依赖关系）
    4. DFX约束（本次新增的非功能性约束）
    5. 里程碑
    """
    e2e_id = requirement_data.get("e2e_id", requirement_id)
    ir_id = requirement_data.get("ir_id", "")
    description = requirement_data.get("description", "")
    doc_info = requirement_data.get("doc_info", [])

    content_lines = [
        f"# Proposal: {e2e_id}",
        "",
        f"**创建日期**: {datetime.now().strftime('%Y-%m-%d')}",
        f"**需求ID**: {e2e_id}",
        f"**IR ID**: {ir_id}",
        "",
        "---",
        "",
        "## 1. 背景与动机",
        "",
        "### 1.1 现状痛点",
        "",
        _format_description(description, max_length=500),
        "",
        "### 1.2 业务驱动",
        "",
        "- 业务目标: (待填写)",
        "- 业务价值: (待填写)",
        "- 优先级: P0",
        "",
        "---",
        "",
        "## 2. 变更内容",
        "",
        "### 2.1 功能清单",
        "",
        "| 序号 | 功能点 | 优先级 | 备注 |",
        "|------|--------|--------|------|",
        "| 1 | (待填写) | P0 | |",
        "",
        "### 2.2 用户故事",
        "",
        "作为 (角色)，我希望 (功能)，以便 (价值)。",
        "",
        "### 2.3 不在范围内",
        "",
        "- (明确列出本次不包含的功能)",
        "",
        "---",
        "",
        "## 3. 影响分析",
        "",
        "### 3.1 受影响的规格/设计章节",
        "",
        "- SPEC.md 章节: (待填写)",
        "- DESIGN.md 章节: (待填写)",
        "",
        "### 3.2 破坏性变更",
        "",
        "- (如有破坏性变更，在此说明)",
        "",
        "### 3.3 依赖关系",
        "",
        "| 依赖项 | 类型 | 说明 |",
        "|--------|------|------|",
        "| (依赖项) | 内部/外部 | (说明) |",
        "",
        "---",
        "",
        "## 4. DFX约束",
        "",
        "| 约束项 | 要求 | 备注 |",
        "|--------|------|------|",
        "| 性能 | (待填写) | |",
        "| 可靠性 | (待填写) | |",
        "| 安全性 | (待填写) | |",
        "| 可维护性 | (待填写) | |",
        "| 兼容性 | (待填写) | |",
        "",
        "---",
        "",
        "## 5. 里程碑",
        "",
        "| 里程碑 | 计划日期 | 交付物 |",
        "|--------|----------|--------|",
        "| 需求评审 | (待填写) | proposal.md |",
        "| Spec评审 | (待填写) | delta_spec.md |",
        "| Design评审 | (待填写) | delta-design.md |",
        "| 开发完成 | (待填写) | 代码 |",
        "| 测试完成 | (待填写) | 测试报告 |",
        "",
        "---",
        "",
        "## 6. 多仓环境说明",
        "",
        "**【仅多仓环境填写】** 当检测到需求涉及多个仓库时，必须填写以下内容：",
        "",
        "### 6.1 依赖查找完整性",
        "",
        "**【必须确认】** 是否找到所有涉及的仓库依赖？",
        "| 检查项 | 结果 | 备注 |",
        "|----------|--------|------|",
        "| 需求涉及的仓库是否全部识别 | 是/否 | 不能遗漏 |",
        "| 调用链是否完整 | 是/否 | 跨仓库调用关系是否正确 |",
        "",
        "### 6.2 仓库范围完整性",
        "",
        "| 仓库 | 职责 | 是否涉及 |",
        "|------|------|---------|",
        "| (仓库名) | (职责描述) | 是/否 |",
        "",
        "### 6.2 实现顺序",
        "",
        "| 顺位 | 仓库 | 任务 |",
        "|------|------|------|",
        "| 1 | (仓库名) | (任务描述) |",
        "| 2 | (仓库名) | (任务描述) |",
        "",
        "### 6.3 接口契约（如有跨仓库接口变更）",
        "",
        "| 接口 | 定义位置 | 使用方 |",
        "|------|---------|-------|",
        "| (接口名) | (repo/path) | (使用方) |",
        "",
        "### 6.4 边界清晰",
        "",
        "| 功能 | 实现仓库 | 边界说明 |",
        "|------|---------|---------|",
        "| (功能名) | (仓库名) | (边界描述) |",
        "",
    ]

    # 如果有文档信息，添加到附录
    if doc_info:
        content_lines.extend([
            "---",
            "",
            "## 6. 附录",
            "",
            "### 6.1 参考文档",
            "",
        ])
        for i, doc in enumerate(doc_info, 1):
            doc_url = doc.get("doc_url", "")
            doc_id = doc.get("doc_id", "")
            content_lines.append(f"- [{doc_id}]({doc_url})")

    return "\n".join(content_lines)


def _format_description(text: str, max_length: int = 500) -> str:
    """
    格式化描述文本
    """
    if not text:
        return "(无描述)"

    # 移除多余的空白
    text = " ".join(text.split())

    if len(text) <= max_length:
        return text

    # 截断并添加省略号
    return text[:max_length] + "..."


def parse_proposal_for_delta_spec(proposal_path: str) -> Dict[str, Any]:
    """
    解析 proposal.md，为生成 delta_spec.md 准备数据

    Args:
        proposal_path: proposal.md 文件路径

    Returns:
        解析后的数据字典
    """
    content = Path(proposal_path).read_text(encoding="utf-8")

    result = {
        "requirement_id": "",
        "background": "",
        "changes": [],
        "impact": [],
        "dfx_constraints": [],
        "milestones": []
    }

    # 简单解析
    lines = content.split("\n")
    current_section = ""

    for line in lines:
        line = line.strip()

        # 检测章节
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue

        # 解析需求ID
        if "需求ID" in line:
            result["requirement_id"] = line.split(":")[-1].strip()

    return result


def main():
    """测试入口"""
    import argparse

    parser = argparse.ArgumentParser(description="proposal生成器")
    parser.add_argument("--id", "-i", required=True, help="需求ID")
    parser.add_argument("--output", "-o", default=".", help="输出目录")
    parser.add_argument("--desc", "-d", default="测试描述", help="需求描述")

    args = parser.parse_args()

    requirement_data = {
        "e2e_id": args.id,
        "ir_id": "IR" + args.id[2:],
        "description": args.desc,
        "doc_info": []
    }

    file_path = generate_proposal(args.id, requirement_data, args.output)
    print(f"已生成: {file_path}")


if __name__ == "__main__":
    main()
