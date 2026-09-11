"""Offline behavioral tests for registry contracts and failure-safe task enrichment."""
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import skill_registry as registry
import task_skill_matching as matching


TASKS = '''# tasks.md
<!-- product: old -->

## 代码生成任务

- [ ] 1.1 实现部署
  - **编程语言**: python
  - **关联需求**: REQ-001
  - **验收标准**: 成功部署
  - **设计锚点**: #3.1
  - **Skill**: old
  - **Skill路径**: .codeagent/skills/old
  - **Skill场景**: old
  - **Skill来源**: Agent自选

- [ ] 1.2 实现校验
  - **编程语言**: python
  - **设计锚点**: #3.2

- [ ] 1.3 实现接口
  - **编程语言**: java
  - **设计锚点**: #3.3

## Review
- [ ] 2.1 规范检查
  - **Skill**: codecheck-for-cleancode
'''


def package(content='new', path='SKILL.md'):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr(path, content)
    return stream.getvalue()


def skill(name):
    return {'skillName': name, 'versions': [
        {'version': '1.9', 'uploadDate': '2026-08-01 00:00:00', 'downloadUrl': 'https://example.test/old'},
        {'version': '1.10', 'uploadDate': '2026-09-01 00:00:00', 'downloadUrl': 'https://example.test/' + name},
    ]}


def choice(task, name, source='Agent自选'):
    return {'task': task, 'skill': skill(name), 'scene': '需求开发 / 部署', 'source': source}


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.tasks = self.repo / 'tasks.md'
        self.tasks.write_text(TASKS)

    def old(self, name, content='old'):
        directory = self.repo / '.codeagent/skills' / name
        directory.mkdir(parents=True)
        (directory / 'SKILL.md').write_text(content)
        (directory / 'old.txt').write_text('old asset')
        return directory

    def test_partial_failure_deduplicates_and_preserves_other_tasks(self):
        failed = self.old('broken')
        other = self.old('unrelated')
        def download(url):
            if url.endswith('broken'):
                raise TimeoutError('offline')
            return package()
        with patch.object(registry, 'request', side_effect=download) as request:
            result = matching.finalize(self.repo, self.tasks,
                [choice('1.1', 'good', '用户选择'), choice('1.2', 'good'), choice('1.3', 'broken')], 'CSP')
        self.assertEqual(request.call_count, 2)
        self.assertEqual(result['installed'], {'1.1': 'good', '1.2': 'good'})
        self.assertEqual(result['agent_selected'], ['1.2'])
        self.assertEqual(result['without_skill'], ['1.3'])
        self.assertEqual((failed / 'SKILL.md').read_text(), 'old')
        self.assertEqual((other / 'SKILL.md').read_text(), 'old')
        output = self.tasks.read_text()
        self.assertEqual(output.split('## Review')[1], TASKS.split('## Review')[1])
        self.assertIn('<!-- product: CSP -->', output)
        self.assertEqual(output.count('**Skill路径**'), 2)
        self.assertIn('  - **Skill来源**: 用户选择', output)
        self.assertIn('.codeagent/', (self.repo / '.gitignore').read_text())
        self.assertFalse(any(x.name.endswith('.install-lock') for x in failed.parent.iterdir()))

    def test_real_atomic_exchange_replaces_entire_directory(self):
        target = self.old('good')
        with patch.object(registry, 'request', return_value=package(path='wrapper/SKILL.md')):
            matching.install(self.repo, skill('good'))
        self.assertEqual((target / 'SKILL.md').read_text(), 'new')
        self.assertFalse((target / 'old.txt').exists())

    def test_unsupported_exchange_keeps_old_and_omits_fields(self):
        target = self.old('good')
        with patch.object(registry, 'request', return_value=package()), \
             patch.object(matching, 'exchange', side_effect=OSError('unsupported')):
            result = matching.finalize(self.repo, self.tasks, [choice('1.1', 'good')])
        self.assertEqual((target / 'SKILL.md').read_text(), 'old')
        self.assertTrue((target / 'old.txt').exists())
        self.assertFalse(result['installed'])
        self.assertNotIn('**Skill路径**', self.tasks.read_text())
        self.assertTrue(result['warnings'])

    def test_corrupt_and_traversal_archives_leave_old_intact(self):
        target = self.old('good')
        for body in (b'not a zip', package(path='../escape'), package(path='readme.txt')):
            with self.subTest(body=body), patch.object(registry, 'request', return_value=body):
                with self.assertRaises(Exception):
                    matching.install(self.repo, skill('good'))
                self.assertEqual((target / 'SKILL.md').read_text(), 'old')
        self.assertFalse((self.repo / '.codeagent/skills/escape').exists())

    def test_symlink_archive_rejected(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            item = zipfile.ZipInfo('SKILL.md')
            item.create_system = 3
            item.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(item, '/etc/passwd')
        with patch.object(registry, 'request', return_value=stream.getvalue()):
            with self.assertRaises(ValueError):
                matching.install(self.repo, skill('good'))

    def test_explicit_none_clears_old_metadata_without_download(self):
        old = self.old('old')
        with patch.object(registry, 'request') as request:
            matching.finalize(self.repo, self.tasks, [])
        request.assert_not_called()
        self.assertNotIn('**Skill路径**', self.tasks.read_text())
        self.assertTrue((old / 'SKILL.md').exists())
        self.assertIn('**Skill**: codecheck-for-cleancode', self.tasks.read_text())

    def test_fenced_examples_and_crlf_preserved(self):
        example = '\n```markdown\n- [ ] 1.9 示例\n  - **Skill**: example\n```\n'
        original = (TASKS + example).replace('\n', '\r\n')
        changed = matching.rewrite(original, {})
        self.assertTrue(changed.endswith(example.replace('\n', '\r\n')))
        self.assertEqual(len(matching.task_blocks(original)[1]), 3)
        self.assertNotIn('\n', changed.replace('\r\n', ''))

    def test_indented_example_metadata_is_not_removed(self):
        example = '  ```markdown\n  - **Skill**: example\n  ```\n'
        original = TASKS.replace('  - **设计锚点**: #3.2\n', '  - **设计锚点**: #3.2\n' + example)
        self.assertIn(example, matching.rewrite(original, {}))

    def test_repeated_finalize_is_idempotent_but_redownloads(self):
        with patch.object(registry, 'request', return_value=package()) as request:
            matching.finalize(self.repo, self.tasks, [choice('1.1', 'good')], 'CSP')
            first = self.tasks.read_bytes()
            matching.finalize(self.repo, self.tasks, [choice('1.1', 'good')], 'CSP')
        self.assertEqual(first, self.tasks.read_bytes())
        self.assertEqual(request.call_count, 2)

    def test_repo_isolation_for_same_skill_name(self):
        other = self.repo / 'another-repo'
        other.mkdir()
        with patch.object(registry, 'request', return_value=package('A')):
            matching.install(self.repo, skill('good'))
        with patch.object(registry, 'request', return_value=package('B')):
            matching.install(other, skill('good'))
        self.assertEqual((self.repo / '.codeagent/skills/good/SKILL.md').read_text(), 'A')
        self.assertEqual((other / '.codeagent/skills/good/SKILL.md').read_text(), 'B')

    def test_busy_install_does_not_remove_existing_lock(self):
        target = self.old('good')
        lock = target.parent / '.good.install-lock'
        lock.mkdir()
        with patch.object(registry, 'request') as request:
            with self.assertRaises(FileExistsError):
                matching.install(self.repo, skill('good'))
        request.assert_not_called()
        self.assertTrue(lock.exists())
        self.assertEqual((target / 'SKILL.md').read_text(), 'old')

    def test_tasks_write_failure_preserves_file(self):
        with patch.object(matching.os, 'replace', side_effect=OSError('write denied')):
            with self.assertRaises(OSError):
                matching.finalize(self.repo, self.tasks, [])
        self.assertEqual(self.tasks.read_text(), TASKS)

    def test_non_code_selection_rejected_before_side_effects(self):
        with self.assertRaises(ValueError):
            matching.finalize(self.repo, self.tasks, [choice('2.1', 'good')])
        self.assertEqual(self.tasks.read_text(), TASKS)
        self.assertFalse((self.repo / '.codeagent').exists())


class RegistryTests(unittest.TestCase):
    def test_api_contracts(self):
        with patch.object(registry, 'post_list', return_value=[]) as post, \
             patch.dict(os.environ, {'SKILL_SCENE_BASE_URL': 'https://scene.example/gateway'}):
            registry.offerings('https://codehub-y.huawei.com/CSP/CSPCertSDK_C')
            self.assertEqual(post.call_args.args[1], {'page': 1, 'pageSize': 20,
                'http_url': 'https://codehub-y.huawei.com/CSP/CSPCertSDK_C'})
            registry.scenes('22633567')
            self.assertEqual(post.call_args.args, ('https://scene.example/gateway/experience/harness/scenes',
                {'dimCode': '22633567'}))
            registry.skills('需求开发', 'MML开发', 'UNC USMF  ')
            self.assertEqual(post.call_args.args[1], {'firstScene': '需求开发', 'secondScene': 'MML开发',
                'dimType': '产品级', 'dimName': 'UNC USMF  '})

    def test_latest_version_not_array_or_lexical_order(self):
        data = skill('good')
        self.assertEqual(registry.latest_version(data)['version'], '1.10')
        data['versions'].reverse()
        self.assertEqual(registry.latest_version(data)['version'], '1.10')

    def test_remote_normalization_removes_credentials(self):
        for value in ('git@codehub-y.huawei.com:CSP/CSPCertSDK_C.git',
                      'https://user:secret@codehub-y.huawei.com/CSP/CSPCertSDK_C.git?token=secret'):
            with patch.object(registry.subprocess, 'run') as run:
                run.return_value.returncode = 0
                run.return_value.stdout = value
                self.assertEqual(registry.remote_url('.'), 'https://codehub-y.huawei.com/CSP/CSPCertSDK_C')

    def test_business_failure_not_empty_success(self):
        with patch.object(registry, 'request', return_value=json.dumps(
                {'success': False, 'code': 200, 'data': []}).encode()):
            with self.assertRaises(ValueError):
                registry.post_list('https://example.test', {})

    def test_default_scene_service_without_configuration(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(registry, 'post_list', return_value=[]) as post:
            registry.scenes('22633567')
            self.assertEqual(post.call_args.args[0],
                'https://coreinsight.rnd.huawei.com/experience/harness/scenes')
            registry.skills('需求开发', 'MML开发', 'UNC USMF  ')
            self.assertEqual(post.call_args.args[0],
                'https://coreinsight.rnd.huawei.com/experience/harness/scene/skills')

    def test_explicit_empty_scene_host_fails(self):
        with patch.dict(os.environ, {'SKILL_SCENE_BASE_URL': ''}):
            with self.assertRaisesRegex(ValueError, 'SKILL_SCENE_BASE_URL'):
                registry.scenes('123')


if __name__ == '__main__':
    unittest.main()
