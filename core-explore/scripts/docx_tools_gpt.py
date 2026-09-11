#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Word 文档处理工具集 v4
支持：
1. tree    - 输出文档标题目录树
2. content - 根据标题提取内容并转 Markdown

改进点：
- 使用文档顺序遍历 paragraph/table，避免表格错位
- 图片从 paragraph/run 中按出现位置提取
- 标题层级严格映射到 Markdown #
- 不依赖 Word 自动编号，避免序号混乱与重复
- 多行 block 状态机识别：json / yaml / http / filetree / code-like
"""

import sys
import argparse
import re
import shutil
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

try:
    from docx import Document
    from docx.document import Document as _Document
    from docx.table import Table, _Cell
    from docx.text.paragraph import Paragraph
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
except ImportError:
    print("请先安装 python-docx 库: pip install python-docx")
    sys.exit(1)

# =========================================================
# 解析XML编号
# =========================================================

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _get_numpr_from_paragraph(para: Paragraph):
    """
    读取段落上的 numPr，返回 (numId, ilvl)；若没有则返回 (None, None)
    """
    p = para._p
    pPr = getattr(p, "pPr", None)
    if pPr is None:
        return None, None

    numPr = pPr.find(f"{{{W_NS}}}numPr")
    if numPr is None:
        return None, None

    numId_elm = numPr.find(f"{{{W_NS}}}numId")
    ilvl_elm = numPr.find(f"{{{W_NS}}}ilvl")

    num_id = numId_elm.get(f"{{{W_NS}}}val") if numId_elm is not None else None
    ilvl = ilvl_elm.get(f"{{{W_NS}}}val") if ilvl_elm is not None else None

    return num_id, ilvl


def _build_numbering_maps(doc):
    """
    从 numbering.xml 构建:
      numId -> abstractNumId
      abstractNumId -> {ilvl: lvlText}
    """
    numbering_part = getattr(doc.part, "numbering_part", None)
    if numbering_part is None:
        return {}, {}

    numbering_elm = numbering_part.element

    num_to_abstract: Dict[str, str] = {}
    abstract_to_levels: Dict[str, Dict[int, str]] = {}

    # <w:num w:numId="X"><w:abstractNumId w:val="Y"/></w:num>
    for num in numbering_elm.findall(f".//{{{W_NS}}}num"):
        num_id = num.get(f"{{{W_NS}}}numId")
        abstract = num.find(f"{{{W_NS}}}abstractNumId")
        if num_id and abstract is not None:
            abstract_id = abstract.get(f"{{{W_NS}}}val")
            if abstract_id:
                num_to_abstract[num_id] = abstract_id

    # <w:abstractNum w:abstractNumId="Y"><w:lvl w:ilvl="0"><w:lvlText w:val="%1.%2"/></w:lvl>
    for abs_num in numbering_elm.findall(f".//{{{W_NS}}}abstractNum"):
        abs_id = abs_num.get(f"{{{W_NS}}}abstractNumId")
        if not abs_id:
            continue

        level_map: Dict[int, str] = {}
        for lvl in abs_num.findall(f"{{{W_NS}}}lvl"):
            ilvl = lvl.get(f"{{{W_NS}}}ilvl")
            lvlText = lvl.find(f"{{{W_NS}}}lvlText")
            if ilvl is None or lvlText is None:
                continue
            val = lvlText.get(f"{{{W_NS}}}val")
            if val is not None:
                level_map[int(ilvl)] = val

        abstract_to_levels[abs_id] = level_map

    return num_to_abstract, abstract_to_levels


def build_heading_number_map(doc) -> Dict[int, str]:
    """
    返回 {id(para): '10.1.1'} 这样的映射。
    仅对 Heading 段落生成编号。
    """
    num_to_abstract, abstract_to_levels = _build_numbering_maps(doc)

    # 每个 numId 一套层级计数器
    counters: Dict[str, List[int]] = {}
    result: Dict[int, str] = {}

    for para in doc.paragraphs:
        style_name = ""
        try:
            style_name = para.style.name or ""
        except Exception:
            pass

        if not style_name.startswith("Heading"):
            continue

        num_id, ilvl = _get_numpr_from_paragraph(para)
        if num_id is None or ilvl is None:
            continue

        ilvl_int = int(ilvl)

        if num_id not in counters:
            counters[num_id] = [0] * 9

        counters[num_id][ilvl_int] += 1

        # 清零更深层
        for j in range(ilvl_int + 1, len(counters[num_id])):
            counters[num_id][j] = 0

        # 优先按实际层级计数拼接
        nums = [str(x) for x in counters[num_id][: ilvl_int + 1] if x > 0]
        number_str = ".".join(nums)

        # 如果 numbering.xml 里有 lvlText，可进一步按模板渲染
        abstract_id = num_to_abstract.get(num_id)
        if abstract_id:
            lvl_map = abstract_to_levels.get(abstract_id, {})
            lvl_text = lvl_map.get(ilvl_int)
            if lvl_text:
                rendered = lvl_text
                for idx in range(1, 10):
                    token = f"%{idx}"
                    if token in rendered:
                        value = counters[num_id][idx - 1]
                        rendered = rendered.replace(token, str(value))
                # 清理末尾句点
                rendered = rendered.rstrip(".")
                if rendered:
                    number_str = rendered

        result[id(para)] = number_str

    return result


# =========================================================
# 通用工具
# =========================================================

def parse_heading_level(style_name: str) -> int:
    """
    从 style name 中提取 Heading 级别。
    兼容 "Heading 1" / "Heading1" 等形式。
    """
    if not style_name:
        return 0
    match = re.search(r'Heading\s*(\d+)', style_name, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def normalize_text(text: str) -> str:
    return text.replace("\r", "").strip()


def heading_to_md(level: int, base_level: int) -> str:
    """
    target 标题固定输出为 ##，
    其子级按相对层级递增：
      base_level      -> ##
      base_level + 1  -> ###
      base_level + 2  -> ####
    """
    md_level = max(2, level - base_level + 2)
    return "#" * md_level


def is_heading_paragraph(para: Paragraph) -> bool:
    try:
        return para.style is not None and para.style.name.startswith("Heading")
    except Exception:
        return False


def safe_style_name(para: Paragraph) -> str:
    try:
        return para.style.name or ""
    except Exception:
        return ""


# =========================================================
# 文档顺序遍历
# =========================================================

def iter_block_items(parent) -> Iterator[Tuple[str, object]]:
    """
    按文档顺序遍历 Paragraph / Table
    """
    if hasattr(parent, "iter_inner_content"):
        for item in parent.iter_inner_content():
            if isinstance(item, Paragraph):
                yield "paragraph", item
            elif isinstance(item, Table):
                yield "table", item
        return

    if isinstance(parent, _Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise TypeError(f"Unsupported parent type: {type(parent)}")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield "paragraph", Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield "table", Table(child, parent)


# =========================================================
# 图片处理
# =========================================================

NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def extract_images_from_docx(doc, doc_path: str) -> Tuple[Dict[str, str], str]:
    """
    导出文档内所有图片，返回:
      {rId: filename}, image_dir_name
    """
    image_map: Dict[str, str] = {}
    image_dir_name = f"{Path(doc_path).stem}_media"
    media_dir = Path(doc_path).parent / image_dir_name
    media_dir.mkdir(parents=True, exist_ok=True)

    for rel_id, rel in doc.part.rels.items():
        target_ref = getattr(rel, "target_ref", "") or ""
        if "image" not in target_ref.lower():
            continue

        try:
            image_part = doc.part.related_parts[rel_id]
            ext = Path(target_ref).suffix.lower() or ".png"
            filename = f"image_{rel_id}{ext}"
            with open(media_dir / filename, "wb") as f:
                f.write(image_part.blob)
            image_map[rel_id] = filename
        except Exception:
            continue

    return image_map, image_dir_name


def find_images_in_paragraph(para, image_map: Dict[str, str]) -> List[str]:
    """
    从段落内提取 inline 图片。
    直接查 run._element 下面的 a:blip / r:embed。
    """
    images: List[str] = []

    for run in para.runs:
        try:
            # 直接拿 embed 属性，避免先找 drawing 再找 blip 的多层误差
            embed_ids = run._element.xpath(".//a:blip/@r:embed")
            for rid in embed_ids:
                if rid in image_map:
                    images.append(image_map[rid])
        except Exception:
            # 有些环境 xpath 命名空间支持不稳定，退回通用遍历
            try:
                for node in run._element.iter():
                    tag = str(getattr(node, "tag", ""))
                    if tag.endswith("}blip"):
                        rid = node.get(f"{{{NS_R}}}embed")
                        if rid and rid in image_map:
                            images.append(image_map[rid])
            except Exception:
                continue

    return images


# =========================================================
# 表格处理
# =========================================================

def paragraph_text_with_images(para, image_map: Dict[str, str], image_dir_name: str) -> str:
    parts = []
    text = para.text.strip()
    if text:
        parts.append(text)

    images = find_images_in_paragraph(para, image_map)
    for img in images:
        img_path = f"{image_dir_name}/{img}"
        # 按你要求的格式输出
        parts.append(f"({img})[{img_path}]")

    return "<br>".join(parts).strip()


def convert_table_to_markdown(table, image_map: Dict[str, str], image_dir_name: str) -> str:
    if not table.rows:
        return ""

    rows = []
    for row in table.rows:
        row_cells = []
        for cell in row.cells:
            cell_parts = []

            # 保持单元格内部段落顺序
            for para in cell.paragraphs:
                value = paragraph_text_with_images(para, image_map, image_dir_name)
                if value:
                    cell_parts.append(value)

            row_cells.append("<br>".join(cell_parts).strip())
        rows.append(row_cells)

    if not rows:
        return ""

    max_cols = max(len(r) for r in rows)
    normalized = [r + [""] * (max_cols - len(r)) for r in rows]

    md = []
    md.append("|" + "|".join(normalized[0]) + "|")
    md.append("|" + "|".join(["---"] * max_cols) + "|")
    for r in normalized[1:]:
        md.append("|" + "|".join(r) + "|")

    return "\n".join(md)


# =========================================================
# block 识别
# =========================================================

def is_http_start(text: str) -> bool:
    text = text.strip()
    patterns = [
        r"^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+\S+",
        r"^HTTP/\d\.\d",
        r"^Host:",
        r"^Content-Type:",
        r"^Accept:",
        r"^Authorization:",
        r"^Method[:：]",
        r"^request[:：]",
        r"^response[:：]",
        r"^Body[:：]",
        r"^Status[:：]?",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def is_yaml_like_start(text: str) -> bool:
    text = text.strip()
    if not text:
        return False

    indicators = [
        "swagger:",
        "openapi:",
        "info:",
        "paths:",
        "definitions:",
        "components:",
        "responses:",
        "parameters:",
        "schema:",
        "properties:",
        "requestBody:",
        "content:",
        "type:",
    ]
    if any(text.startswith(ind) for ind in indicators):
        return True

    # 形如 key: value，但排除明显普通句子
    if re.match(r"^[A-Za-z0-9_\-./]+:\s*.*$", text):
        return True

    return False


def is_file_structure_start(text: str) -> bool:
    text = text.strip()
    if not text:
        return False

    if text.startswith("|") and ("--" in text or "|-" in text or "|==" in text):
        return True
    if re.search(r"\.(zip|tar|tar\.gz|tgz|rar)\b", text, re.IGNORECASE):
        return True
    if text.startswith(("├", "└", "│", "──", "--", "+--")):
        return True
    return False


def is_json_start(text: str) -> bool:
    text = text.strip()
    return text.startswith("{") or text.startswith("[")


def is_xml_like_start(text: str) -> bool:
    text = text.strip()
    return text.startswith("<") and text.endswith(">") and len(text) > 2


def is_sql_like_start(text: str) -> bool:
    text = text.strip().upper()
    return text.startswith((
        "SELECT ", "INSERT ", "UPDATE ", "DELETE ", "CREATE ",
        "ALTER ", "DROP ", "WITH "
    ))


def detect_block_type(text: str) -> Optional[str]:
    t = text.strip()
    if not t:
        return None

    if t.startswith("{") or t.startswith("["):
        return "json"

    if re.match(r"^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+\S+", t, re.I):
        return "http"
    if re.match(r"^(HTTP/\d\.\d|Host:|Content-Type:|Authorization:|Accept:|Method[:：]|request[:：]|response[:：]|Body[:：]|Status[:：])", t, re.I):
        return "http"

    if re.match(r"^[A-Za-z0-9_.\-/]+:\s*.*$", t):
        return "yaml"
    if t.startswith(("swagger:", "openapi:", "info:", "paths:", "components:", "schema:", "properties:", "type:")):
        return "yaml"

    if t.startswith(("├", "└", "│", "+--", "|--", "--")) or re.search(r"\.(zip|tar|tar\.gz|tgz|rar)\b", t, re.I):
        return "text"

    if t.startswith("<") and t.endswith(">"):
        return "xml"

    if re.match(r"^(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|WITH)\s+", t, re.I):
        return "sql"

    return None


def collect_json_block(lines: List[str], start: int) -> Tuple[List[str], int]:
    buf = []
    i = start
    balance = 0
    started = False

    while i < len(lines):
        t = lines[i].rstrip()

        if not t.strip():
            if started:
                buf.append("")
            i += 1
            continue

        if not started and not (t.lstrip().startswith("{") or t.lstrip().startswith("[")):
            break

        started = True
        buf.append(t)

        balance += t.count("{") + t.count("[")
        balance -= t.count("}") + t.count("]")

        if balance <= 0 and started:
            i += 1
            break

        i += 1

    return buf, i


def collect_yaml_block(lines: List[str], start: int) -> Tuple[List[str], int]:
    buf = []
    i = start
    indent = None

    while i < len(lines):
        t = lines[i]

        if not t.strip():
            buf.append("")
            i += 1
            continue

        # 确定基准缩进
        if indent is None:
            indent = len(t) - len(t.lstrip())
            if indent == len(t):
                indent = 0

        current_indent = len(t) - len(t.lstrip())

        # 如果缩进减少到基准以下，认为 yaml 块结束
        if indent > 0 and current_indent < indent:
            break

        # 检测新 block 开始
        if current_indent == indent and detect_block_type(t):
            break

        buf.append(t.rstrip())
        i += 1

    return buf, i


def collect_http_block(lines: List[str], start: int) -> Tuple[List[str], int]:
    buf = []
    i = start

    while i < len(lines):
        t = lines[i].rstrip()

        # 空行分隔
        if not t.strip():
            if buf:
                # 继续读，下一个非空决定是否继续
                i += 1
                continue
            else:
                i += 1
                continue

        # HTTP 块需要以特定关键字开头
        if not buf and not is_http_start(t):
            break

        # 如果已经开始，遇到非 http 行且不是缩进的继续
        if buf:
            # 检查是否是 http 继续行 (空格/tab 开头)
            if t and (t[0] == ' ' or t[0] == '\t'):
                buf.append(t)
                i += 1
                continue
            # 检查是否是新的 http 开始
            if is_http_start(t):
                buf.append(t)
                i += 1
                continue
            # 否则结束
            break
        else:
            buf.append(t)
            i += 1

    return buf, i


def collect_text_block(lines: List[str], start: int) -> Tuple[List[str], int]:
    buf = []
    i = start

    while i < len(lines):
        t = lines[i].rstrip()

        if not t.strip():
            # 连续空行结束
            if buf:
                # 允许一个空行
                if len(buf) > 0 and buf[-1] != "":
                    buf.append("")
                    i += 1
                    continue
                else:
                    break
            else:
                i += 1
                continue

        # 检测是否是新的 block 开始
        if detect_block_type(t):
            break

        buf.append(t)
        i += 1

    return buf, i


# =========================================================
# 主转换逻辑
# =========================================================

def convert_docx_to_markdown(doc_path: str, heading_keyword: str = None) -> str:
    """
    将 docx 转换为 markdown。

    :param doc_path: docx 文件路径
    :param heading_keyword: 如果指定，只返回包含该关键词的标题下的内容
    :return: markdown 文本
    """
    doc = Document(doc_path)

    # 导出图片
    image_map, image_dir_name = extract_images_from_docx(doc, doc_path)

    # 构建标题编号映射
    heading_number_map = build_heading_number_map(doc)

    # 找到目标标题的层级
    target_level = None
    if heading_keyword:
        for para in doc.paragraphs:
            style_name = safe_style_name(para)
            if is_heading_paragraph(para):
                text = normalize_text(para.text)
                if heading_keyword in text:
                    target_level = parse_heading_level(style_name)
                    break

    # 收集所有标题
    headings = []
    for para in doc.paragraphs:
        style_name = safe_style_name(para)
        if is_heading_paragraph(para):
            level = parse_heading_level(style_name)
            text = normalize_text(para.text)
            number = heading_number_map.get(id(para), "")
            headings.append({
                "level": level,
                "text": text,
                "number": number,
                "para": para
            })

    # 如果指定了关键词，找到目标标题的起始和结束位置
    start_idx = None
    end_idx = None
    if heading_keyword:
        for i, h in enumerate(headings):
            if heading_keyword in h["text"]:
                start_idx = i
                # 找到下一个同级或更高层级的标题
                for j in range(i + 1, len(headings)):
                    if headings[j]["level"] <= h["level"]:
                        end_idx = j
                        break
                if end_idx is None:
                    end_idx = len(headings)
                break

    # 按文档顺序遍历
    md_lines = []
    in_target_section = target_level is None  # 如果没有指定关键词，则全部输出

    for block_type, block in iter_block_items(doc):
        if block_type == "paragraph":
            para = block
            style_name = safe_style_name(para)

            # 处理标题
            if is_heading_paragraph(para):
                level = parse_heading_level(style_name)
                text = normalize_text(para.text)
                number = heading_number_map.get(id(para), "")

                # 检查是否在目标章节内
                if target_level is not None:
                    if start_idx is not None:
                        # 找到当前标题在 headings 中的位置
                        # 注意：由于 iter_block_items 创建新的 Paragraph 对象，
                        # 不能使用 is 比较，只能通过文本内容匹配
                        current_idx = None
                        for i, h in enumerate(headings):
                            if h["text"] == text and h["level"] == level:
                                current_idx = i
                                break

                        if current_idx is not None:
                            if current_idx == start_idx:
                                in_target_section = True
                            elif current_idx >= end_idx:
                                in_target_section = False

                if not in_target_section:
                    continue

                prefix = f"{number} " if number else ""
                md_lines.append(f"{heading_to_md(level, 2)} {prefix}{text}")
                continue

            # 非标题段落
            if not in_target_section:
                continue

            text = paragraph_text_with_images(para, image_map, image_dir_name)
            if not text:
                continue

            # 检测 block 类型
            block_type = detect_block_type(text)
            if block_type:
                # 收集多行 block
                pass  # 简化处理，单行输出

            md_lines.append(text)

        elif block_type == "table":
            if not in_target_section:
                continue

            table_md = convert_table_to_markdown(block, image_map, image_dir_name)
            if table_md:
                md_lines.append("")
                md_lines.append(table_md)
                md_lines.append("")

    return "\n".join(md_lines)


def get_document_toc(doc_path: str) -> List[Dict]:
    """
    获取文档的目录结构（标题树）
    """
    doc = Document(doc_path)
    heading_number_map = build_heading_number_map(doc)

    toc = []
    for para in doc.paragraphs:
        style_name = safe_style_name(para)
        if is_heading_paragraph(para):
            level = parse_heading_level(style_name)
            text = normalize_text(para.text)
            number = heading_number_map.get(id(para), "")

            if text:
                toc.append({
                    "level": level,
                    "number": number,
                    "text": text
                })

    return toc


def find_heading_by_keyword(doc_path: str, keyword: str) -> Optional[Dict]:
    """
    查找包含关键词的标题
    """
    toc = get_document_toc(doc_path)

    for item in toc:
        if keyword in item["text"]:
            return item

    return None


def extract_section_content(doc_path: str, keyword: str) -> str:
    """
    提取包含关键词的章节内容
    """
    return convert_docx_to_markdown(doc_path, heading_keyword=keyword)


# =========================================================
# CLI 入口
# =========================================================

def main():
    parser = argparse.ArgumentParser(description="Word 文档处理工具")
    parser.add_argument("command", choices=["tree", "content"], help="命令: tree=目录树, content=内容")
    parser.add_argument("file", help="docx 文件路径")
    parser.add_argument("--keyword", "-k", help="查找的关键词（仅 content 命令有效）")
    parser.add_argument("--output", "-o", help="输出文件路径")

    args = parser.parse_args()

    if args.command == "tree":
        toc = get_document_toc(args.file)
        for item in toc:
            indent = "  " * (item["level"] - 1)
            number = f"{item['number']} " if item["number"] else ""
            print(f"{indent}{number}{item['text']}")

    elif args.command == "content":
        if not args.keyword:
            print("错误: content 命令需要 --keyword 参数")
            sys.exit(1)

        content = extract_section_content(args.file, args.keyword)

        if args.output:
            Path(args.output).write_text(content, encoding="utf-8")
            print(f"内容已保存到: {args.output}")
        else:
            print(content)


if __name__ == "__main__":
    main()
