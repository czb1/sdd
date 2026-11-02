"""Apply the reviewed writer/metadata fixes to a complete local flow_config.py.

Default: preview a diff. --apply writes atomically and keeps a .bak copy.
Function locations come from AST, independent of the order of pasted snippets.
This script does not install or re-register any built-in steps.
"""

import argparse
import ast
import difflib
import os
from pathlib import Path
import stat
import tempfile

REPLACEMENTS = (
    ('# SKILL.md 采用 "Phase 1~11" 连续编号', '# SKILL.md 采用 "Phase 1~12" 连续编号'),
    ('# 内容型 3 键（version_check / read_similar / expert_experience）单多仓共用', '# 内容型 4 键（version_check / read_similar / expert_experience / skill_consumption）单多仓共用'),
    ('"description": "获取专家经验（paradigm-exp-use）",', '"description": "准备已有项目经验及任务能力查找上下文",'),
    ('（内置步骤全开，无自定义步骤）', '（内置步骤按各自默认值启停，无自定义步骤）'),
    ('    // ---- 自定义步骤示例（取消注释即启用；注意：最后一个有效键不可带尾逗号）----', '    // ---- 自定义步骤（未注释即启用；最后一个有效键不可带尾逗号）----\n    // judgment_ladder 是默认启用的模板示例；整块注释可关闭。\n    // 下方 compile / codebase_scan 示例默认关闭，取消整块注释可启用。'),
    ("  // 启用时在上方 core-apply 对象闭合 '}' 后补逗号，例如：", '  // 启用命名空间时只去掉一层注释，并在其闭合 } 后加逗号以连接后续顶层键。\n  // 保留内部自定义声明的注释；需要启用某声明时再取消其整块注释。'),
    ('// Phase 7 获取专家经验（paradigm-exp-use，纯增益）', '// Phase 7 准备已有项目经验及任务能力查找上下文（不独立拉取经验，纯增益）'),
    ('every orchestration slot is present (all 5 slots always exist)', 'every orchestration slot registered for the current skill is present'),
    ('（五个插槽必须齐全）', '（当前 skill 注册的所有插槽必须齐全）'),
)


def transform(source):
    source_tree = ast.parse(source)
    functions = [node for node in source_tree.body if isinstance(node, ast.FunctionDef)]
    updates = [node for node in functions if node.name == "update_config_value"]
    if len(updates) != 1 or [arg.arg for arg in updates[0].args.args] != ["skill", "key", "value"]:
        raise ValueError("需要唯一的 update_config_value(skill, key, value) 函数")
    writer = Path(__file__).with_name("flow_config_update.py").read_text(encoding="utf-8")
    replacements = {
        node.name: ast.get_source_segment(writer, node)
        for node in ast.parse(writer).body if isinstance(node, ast.FunctionDef)
    }
    names = [node.name for node in functions if node.name in replacements]
    if len(names) != len(set(names)):
        raise ValueError("目标文件含重复的修复函数，请先消除歧义")
    newline = "\r\n" if "\r\n" in source else "\n"
    missing = [code for name, code in replacements.items() if name not in names]
    lines = source.splitlines(keepends=True)
    for node in sorted(functions, key=lambda node: node.lineno, reverse=True):
        if node.name not in replacements:
            continue
        if node.decorator_list:
            raise ValueError(f"{node.name} 含额外装饰器，请人工合入")
        code = replacements[node.name]
        if node.name == "update_config_value" and missing:
            code = "\n\n\n".join([*missing, code])
        ending = newline if lines[node.end_lineno - 1].endswith(("\r", "\n")) else ""
        lines[node.lineno - 1:node.end_lineno] = [code.replace("\n", newline) + ending]
    result = "".join(lines)
    for old, new in REPLACEMENTS:
        result = result.replace(old.replace("\n", newline), new.replace("\n", newline))
    compile(result, "flow_config.py", "exec")
    return result


def apply_to(path):
    path = path.resolve(strict=True)
    original = path.read_bytes()
    result = transform(original.decode("utf-8")).encode("utf-8")
    if result == original:
        return None
    backup = path.with_name(path.name + ".before-flow-config-fixes.bak")
    # Exclusive creation prevents overwriting an earlier backup.
    with backup.open("xb") as stream:
        stream.write(original)
    mode = stat.S_IMODE(path.stat().st_mode)
    os.chmod(backup, mode)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(result)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        if path.read_bytes() != original:
            raise ValueError("源文件已被其他操作修改，请重新检查")
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="完整 flow_config.py 的路径")
    parser.add_argument("--apply", action="store_true", help="写入修复并保留原文件备份；默认仅显示 diff")
    args = parser.parse_args()
    if args.apply:
        backup = apply_to(args.source)
        print(f"已修复 {args.source}；原文件备份：{backup}" if backup else "内容已是修复后的版本，无需写入。")
    else:
        before = args.source.read_bytes().decode("utf-8")
        after = transform(before)
        print("".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=str(args.source), tofile=str(args.source))), end="")


if __name__ == "__main__":
    main()
