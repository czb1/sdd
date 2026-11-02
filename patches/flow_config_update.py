"""Drop-in JSONC writer for flow_config.py; not a replacement for that module.

Copy the four _flow_jsonc_* helpers and update_config_value into the runtime,
or use apply_flow_config_fixes.py. get_config_path remains runtime-owned.
"""


def _flow_jsonc_mask_comments(raw):
    """Mask comments without moving offsets or interpreting // inside strings."""
    import re

    return re.sub(
        r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/',
        lambda match: match[0] if match[0].startswith('"') else re.sub(r"[^\r\n]", " ", match[0]),
        raw,
    )


def _flow_jsonc_decoder():
    """Use strict JSON values and reject ambiguous duplicate object keys."""
    import json

    def unique_object(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError(f"配置包含重复键：{name}")
            result[name] = value
        return result

    def reject_constant(value):
        raise ValueError(f"配置包含无效 JSON 值：{value}")

    return json.JSONDecoder(object_pairs_hook=unique_object, parse_constant=reject_constant)


def _flow_jsonc_object_members(masked, opening, decoder):
    """Return direct members' source spans and the closing brace of an object.

    The entire document must already have passed decoder.decode(). Nested
    values are consumed as a unit, so their keys cannot match a parent key.
    """
    position = opening + 1
    members = []
    while True:
        while masked[position] in " \t\r\n":
            position += 1
        if masked[position] == "}":
            return members, position
        key_start = position
        name, position = decoder.raw_decode(masked, position)
        while masked[position] in " \t\r\n":
            position += 1
        position += 1  # colon, already validated
        while masked[position] in " \t\r\n":
            position += 1
        value_start = position
        _, position = decoder.raw_decode(masked, position)
        members.append((name, key_start, value_start, position))
        while masked[position] in " \t\r\n":
            position += 1
        if masked[position] == ",":
            position += 1


def _flow_jsonc_set_value(raw, skill, key, value):
    """Edit one direct namespace member, preserving text outside its value."""
    import json
    import re

    if not isinstance(skill, str) or not isinstance(key, str):
        raise ValueError("命名空间和配置键必须是字符串")
    masked = _flow_jsonc_mask_comments(raw)
    decoder = _flow_jsonc_decoder()
    document = decoder.decode(masked)
    if not isinstance(document, dict):
        raise ValueError("配置顶层必须是对象")
    root_start = len(masked) - len(masked.lstrip())
    namespaces, _ = _flow_jsonc_object_members(masked, root_start, decoder)
    namespace = next((entry for entry in namespaces if entry[0] == skill), None)
    if namespace is None or not isinstance(document[skill], dict):
        raise ValueError(f"配置中不存在 '{skill}' 命名空间对象")
    members, closing = _flow_jsonc_object_members(masked, namespace[2], decoder)
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    normalized_value = decoder.decode(encoded)
    entry = next((entry for entry in members if entry[0] == key), None)
    if entry is not None:
        # Canonical JSON distinguishes true from 1, including nested values.
        current = json.dumps(document[skill][key], ensure_ascii=False, sort_keys=True)
        target = json.dumps(normalized_value, ensure_ascii=False, sort_keys=True)
        if current == target:
            return raw
        result = raw[:entry[2]] + encoded + raw[entry[3]:]
    else:
        pair = json.dumps(key, ensure_ascii=False) + ": " + encoded
        body = raw[namespace[2]:closing]
        if "\n" not in body and "\r" not in body:
            separator = " " if body[-1:] not in ("{", " ", "\t") else ""
            result = raw[:closing] + separator + pair + raw[closing:]
        else:
            newline = "\r\n" if "\r\n" in raw else ("\n" if "\n" in raw else "\r")

            def line_start(position):
                return max(raw.rfind("\n", 0, position), raw.rfind("\r", 0, position)) + 1

            base_indent = re.match(r"[ \t]*", raw[line_start(namespace[1]):]).group(0)
            indent = base_indent + "  "
            if members:
                prefix = raw[line_start(members[0][1]):members[0][1]]
                if not prefix.strip():
                    indent = prefix
            close_line = line_start(closing)
            if not raw[close_line:closing].strip():
                result = raw[:close_line] + indent + pair + newline + raw[close_line:]
            else:
                result = raw[:closing] + newline + indent + pair + newline + base_indent + raw[closing:]
        if members:
            # The comma belongs immediately after the last value, before any
            # inline comment. Empty objects have no preceding value/comma.
            last_end = members[-1][3]
            result = result[:last_end] + "," + result[last_end:]
    decoder.decode(_flow_jsonc_mask_comments(result))
    return result


def update_config_value(skill: str, key: str, value: "Any") -> "Tuple[bool, str]":
    """Persist a namespace value without rewriting unrelated JSONC content.

    Validate before writing; replace atomically so write failures preserve
    the original file. Return (ok, error_message), including idempotent success.
    """
    import os
    from pathlib import Path
    import stat
    import tempfile

    path = get_config_path()
    temporary = None
    try:
        if not path.exists():
            return False, f"配置文件不存在：{path}"
        path = path.resolve()  # Preserve a symlink used for the config location.
        original = path.read_bytes()
        raw = original.decode("utf-8")
        result = _flow_jsonc_set_value(raw, skill, key, value)
        if result == raw:
            return True, ""
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent,
            prefix=f".{path.name}.", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(result)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        if path.read_bytes() != original:
            return False, "配置文件已被其他操作修改，请重新读取后重试"
        os.replace(temporary, path)
        temporary = None
    except Exception as error:
        return False, f"配置更新失败：{error}"
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True, ""
