"""Skill Registry transport. Semantic matching and confirmation belong to the Agent."""
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

OFFERING_URL = 'http://coreharness.spec.rnd.huawei.com/core-harness/api/v1/offering/list'
SCENE_BASE_URL = 'https://coreinsight.rnd.huawei.com'
MAX_DOWNLOAD = 50 * 1024 * 1024


def request(url, payload=None, limit=MAX_DOWNLOAD):
    if urllib.parse.urlsplit(url).scheme not in ('http', 'https'):
        raise ValueError('Only HTTP(S) registry URLs are supported')
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    headers = {} if data is None else {'Content-Type': 'application/json'}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError('Registry response exceeds size limit')
    return body


def post_list(url, payload):
    result = json.loads(request(url, payload, limit=4 * 1024 * 1024))
    if result.get('code') != 200 or result.get('success') is False:
        raise ValueError('Registry returned an unsuccessful response')
    data = result.get('data')
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ValueError('Registry data must be an array of objects')
    return data


def remote_url(repo):
    result = subprocess.run(['git', '-C', str(repo), 'remote', 'get-url', 'origin'],
                            capture_output=True, text=True, timeout=10)
    if result.returncode:
        return ''
    value = result.stdout.strip()
    if '://' not in value:
        match = re.fullmatch(r'(?:[^@/]+@)?([^:/]+):(.+)', value)
        if not match:
            return ''
        value = 'https://' + match[1] + '/' + match[2]
    parsed = urllib.parse.urlsplit(value)
    if not parsed.hostname or parsed.scheme not in ('http', 'https', 'ssh'):
        return ''
    # Never send credentials, query strings, or fragments to offering lookup.
    host = parsed.hostname
    if parsed.port and parsed.scheme != 'ssh':
        host += ':' + str(parsed.port)
    scheme = parsed.scheme if parsed.scheme in ('http', 'https') else 'https'
    return urllib.parse.urlunsplit((scheme, host, parsed.path.removesuffix('.git'), '', ''))


def product_hints(repo):
    repo = Path(repo).resolve()
    config = repo / '.codeagent/product.json'
    local = json.loads(config.read_text(encoding='utf-8')) if config.is_file() else {}
    return {'http_url': remote_url(repo), 'repo_name': repo.name, 'local_product': local}


def offerings(http_url):
    if not http_url:
        return []
    found = []
    for page in range(1, 101):
        rows = post_list(os.environ.get('SKILL_OFFERING_URL', OFFERING_URL),
                         {'page': page, 'pageSize': 20, 'http_url': http_url})
        found.extend(rows)
        if len(rows) < 20:
            return found
    raise ValueError('Offering pagination limit reached; do not select from incomplete results')


def scene_endpoint(path):
    base = os.environ.get('SKILL_SCENE_BASE_URL', SCENE_BASE_URL).rstrip('/')
    if not base:
        raise ValueError('SKILL_SCENE_BASE_URL must not be empty')
    return base + path


def scenes(offering_id):
    return post_list(scene_endpoint('/experience/harness/scenes'), {'dimCode': str(offering_id)})


def skills(first_scene, second_scene, product_name):
    return post_list(scene_endpoint('/experience/harness/scene/skills'),
                     {'firstScene': first_scene, 'secondScene': second_scene,
                      'dimType': '产品级', 'dimName': product_name})


def latest_version(skill):
    versions = skill.get('versions', [])
    if not versions:
        raise ValueError('Skill has no downloadable versions')
    # Latest release is uploadDate, not response order or lexical version ordering.
    def key(version):
        return datetime.strptime(version['uploadDate'], '%Y-%m-%d %H:%M:%S')
    chosen = max(versions, key=key)
    if not chosen.get('downloadUrl') or not chosen.get('version'):
        raise ValueError('Latest Skill version is incomplete')
    return chosen
