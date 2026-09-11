"""JSON stdin/stdout helper for Phase 8.6; tasks.md is the only selection record."""
import ctypes
import io
import json
import os
import re
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

import skill_registry as registry

FIELDS = ('Skill', 'Skill路径', 'Skill场景', 'Skill来源')
TASK = re.compile(r'^-\s*\[[ xX]\]\s+(\d+\.\d+)\s+(.+)')
FIELD = re.compile(r'^\s+-\s+\*\*(Skill|Skill路径|Skill场景|Skill来源)\*\*\s*[:：]')
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z')


def task_blocks(content):
    lines = content.splitlines(keepends=True)
    result, fence = [], None
    for index, line in enumerate(lines):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        match = TASK.match(line) if fence is None else None
        if not match or not match[1].startswith('1.'):
            continue
        end = index + 1
        while end < len(lines) and (not lines[end].strip() or lines[end][0].isspace()):
            end += 1
        result.append({'id': match[1], 'description': match[2].strip(),
                       'start': index, 'end': end,
                       'metadata': ''.join(lines[index + 1:end])})
    if len({item['id'] for item in result}) != len(result):
        raise ValueError('Duplicate 1.x task IDs')
    return lines, result


def atomic_text(path, content):
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            os.chmod(name, stat.S_IMODE(path.stat().st_mode))
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def exchange(left, right):
    """True atomic directory exchange; unsupported platforms retain the old version."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, 'renameat2', None)
    if rename is None:
        raise OSError('Atomic directory exchange unavailable on this platform')
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(left), -100, os.fsencode(right), 2):
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))


def extract_package(body, stage):
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        entries = archive.infolist()
        if len(entries) > 10000 or sum(x.file_size for x in entries) > 200 * 1024 * 1024:
            raise ValueError('Skill archive exceeds extraction limits')
        seen = set()
        for item in entries:
            path = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if (not item.filename or path.is_absolute() or '..' in path.parts
                    or '\\' in item.filename or ':' in item.filename
                    or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))
                    or str(path) in seen):
                raise ValueError('Unsafe or duplicate archive entry')
            seen.add(str(path))
        archive.extractall(stage)
    # Accept SKILL.md at root or under one wrapper directory; reject ambiguous roots.
    if (stage / 'SKILL.md').is_file():
        root = stage
    else:
        children = list(stage.iterdir())
        root = children[0] if len(children) == 1 and children[0].is_dir() else stage
    entry = root / 'SKILL.md'
    if not entry.is_file() or not entry.read_text(encoding='utf-8').strip():
        raise ValueError('Package must contain a nonempty UTF-8 SKILL.md')
    return root


def install(repo, skill):
    name = skill['skillName']
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError('Unsafe Skill name')
    parent = repo / '.codeagent/skills'
    if (repo / '.codeagent').is_symlink() or parent.is_symlink():
        raise ValueError('Skill storage must not be a symlink')
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / name
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise ValueError('Skill target is not a regular directory')
    lock = parent / ('.' + name + '.install-lock')
    lock.mkdir()  # Busy same-name installation degrades; never remove another writer's lock.
    try:
        version = registry.latest_version(skill)
        body = registry.request(version['downloadUrl'])
        with tempfile.TemporaryDirectory(prefix='.' + name + '-', dir=parent) as temp:
            stage = Path(temp) / 'unpacked'
            stage.mkdir()
            root = extract_package(body, stage)
            if target.exists():
                exchange(root, target)
            else:
                os.rename(root, target)
        return version['version']
    finally:
        lock.rmdir()


def ensure_ignored(repo):
    path = repo / '.gitignore'
    if path.is_symlink():
        raise ValueError('.gitignore must not be a symlink')
    content = path.read_text(encoding='utf-8') if path.exists() else ''
    rules = [line.strip() for line in content.splitlines() if line.strip()]
    if not rules or rules[-1] not in ('.codeagent/', '/.codeagent/'):
        atomic_text(path, content + ('' if not content or content.endswith('\n') else '\n') + '.codeagent/\n')


def without_skill_fields(lines):
    result, fence = [], None
    for line in lines:
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            result.append(line)
        elif fence is not None or not FIELD.match(line):
            result.append(line)
    return result


def rewrite(content, installed, product=None):
    lines, blocks = task_blocks(content)
    newline = '\r\n' if '\r\n' in content else '\n'
    for task in reversed(blocks):
        start, end = task['start'], task['end']
        section = without_skill_fields(lines[start:end])
        selected = installed.get(task['id'])
        if selected:
            position = len(section)
            while position > 1 and not section[position - 1].strip():
                position -= 1
            if not section[position - 1].endswith(('\n', '\r')):
                section[position - 1] += newline
            name = selected['skill']['skillName']
            values = (name, '.codeagent/skills/' + name, selected['scene'], selected['source'])
            section[position:position] = [f'  - **{key}**: {value}{newline}' for key, value in zip(FIELDS, values)]
        lines[start:end] = section
    content = ''.join(lines)
    if product is not None:
        if not isinstance(product, str) or not product.strip() or any(x in product for x in ('\n', '\r', '<', '>')):
            raise ValueError('Product must be a single-line name')
        content = re.sub(r'^<!-- product:.*?-->\r?\n?', '', content, flags=re.MULTILINE)
        header = re.match(r'^# [^\r\n]*(?:\r?\n|$)', content)
        pos = header.end() if header else 0
        prefix = '' if pos == 0 or content[:pos].endswith('\n') else newline
        content = content[:pos] + prefix + f'<!-- product: {product} -->{newline}' + content[pos:]
    return content


def finalize(repo, tasks, selections, product=None):
    with tasks.open(encoding='utf-8', newline='') as stream:
        original = stream.read()
    _, blocks = task_blocks(original)
    ids = {task['id'] for task in blocks}
    warnings, installed, downloads, used = [], {}, {}, set()
    # Validate all choices before side effects. A task can choose at most one Skill.
    for choice in selections:
        if choice['task'] not in ids or choice['task'] in used:
            raise ValueError('Selection must identify one unique existing 1.x task')
        used.add(choice['task'])
        if choice['source'] not in ('用户选择', 'Agent自选'):
            raise ValueError('Invalid Skill source')
        if not isinstance(choice['scene'], str) or not choice['scene'].strip() or any(c in choice['scene'] for c in '\r\n<>'):
            raise ValueError('Invalid Skill scene')
    rewrite(original, {}, product)  # Validate product before downloads.
    for choice in selections:
        name = choice['skill']['skillName']
        if name not in downloads:
            try:
                ensure_ignored(repo)
                downloads[name] = install(repo, choice['skill'])
            except Exception as error:
                downloads[name] = None
                warnings.append(f'{name}: {type(error).__name__}: {error}')
        if downloads[name] is not None:
            installed[choice['task']] = choice
    updated = rewrite(original, installed, product)
    with tasks.open(encoding='utf-8', newline='') as stream:
        if stream.read() != original:
            raise ValueError('tasks.md changed concurrently; re-read before retrying')
    atomic_text(tasks, updated)
    return {'installed': {key: value['skill']['skillName'] for key, value in installed.items()},
            'agent_selected': [key for key, value in installed.items() if value['source'] == 'Agent自选'],
            'without_skill': sorted(ids - installed.keys()), 'warnings': warnings}


def main():
    try:
        payload = json.load(sys.stdin)
        action = payload['action']
        repo = Path(payload.get('repo', '.')).resolve()
        if action in ('tasks', 'finalize'):
            tasks = Path(payload['tasks']).resolve()
            tasks.relative_to(repo)
            if tasks.name != 'tasks.md':
                raise ValueError('Expected tasks.md in the selected repo')
        if action == 'tasks':
            result = task_blocks(tasks.read_text(encoding='utf-8'))[1]
        elif action == 'product':
            result = registry.product_hints(repo)
            try:
                result['offerings'] = registry.offerings(result['http_url'])
            except Exception as error:
                result['offerings'] = []
                result['warnings'] = [f'Offering lookup failed: {type(error).__name__}: {error}']
        elif action == 'scenes':
            result = registry.scenes(payload['offering_id'])
        elif action == 'skills':
            result = registry.skills(payload['firstScene'], payload['secondScene'], payload['product_name'])
        elif action == 'finalize':
            result = finalize(repo, tasks, payload.get('selections', []), payload.get('product'))
        else:
            raise ValueError('Unknown action')
        output = {'status': 'ok', 'data': result}
    except Exception as error:
        # Enhancement failure never blocks the design workflow. Callers MUST inspect status.
        output = {'status': 'warning', 'warning': f'{type(error).__name__}: {error}'}
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
