"""JSONC persistence regressions; runnable without the complete CoreSpec CLI."""

import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
source_path = ROOT / "patches/flow_config_update.py"
unittest_args = sys.argv[1:]
if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--flow-config", type=Path, default=source_path)
    options, unittest_args = parser.parse_known_args()
    source_path = options.flow_config
spec = importlib.util.spec_from_file_location("flow_config_update", source_path)
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)


class ConfigUpdateTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "flow-config.json"
        patcher = patch.object(writer, "get_config_path", return_value=self.path, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, source):
        self.path.write_bytes(source.encode("utf-8"))

    def update(self, value=True, key="skill_consumption"):
        ok, error = writer.update_config_value("core-design", key, value)
        self.assertTrue(ok, error)
        raw = self.path.read_bytes().decode("utf-8")
        return raw, json.loads(writer._flow_jsonc_mask_comments(raw))

    def test_insert_into_empty_compact_multiline_and_comment_only_objects(self):
        for body in ("{}", "{ }", "{\n  }", "{\n    // keep this example\n  }", "{/* keep block comment */}"):
            with self.subTest(body=body):
                self.write('{"core-design": ' + body + ', "other": {"value": 7}}\n')
                raw, result = self.update()
                self.assertEqual(result, {"core-design": {"skill_consumption": True}, "other": {"value": 7}})
                if "keep" in body:
                    self.assertIn("keep", raw)
                self.assertNotIn("{,", raw)

    def test_insert_before_inline_line_comment(self):
        source = '{\n  "core-design": {\n    "cleanup": true // keep comment\n  },\n  "test_strategy": "tdd"\n}\n'
        self.write(source)
        raw, result = self.update()
        self.assertIn('"cleanup": true, // keep comment\n', raw)
        self.assertEqual(result["core-design"], {"cleanup": True, "skill_consumption": True})
        self.assertEqual(result["test_strategy"], "tdd")

    def test_insert_after_nested_multiline_object_and_trailing_comments(self):
        source = '''{
  "core-design": {
    "custom": {
      "type": "reference",
      "options": {"skill_consumption": false}
    } /* keep inline */
    // "skill_consumption": false
    /* keep trailing
       block comment */
  },
  "core-apply": {"skill_consumption": false}
}'''
        self.write(source)
        raw, result = self.update()
        self.assertIn('}, /* keep inline */', raw)
        self.assertIn('// "skill_consumption": false', raw)
        self.assertIn('/* keep trailing\n       block comment */', raw)
        self.assertIs(result["core-design"]["custom"]["options"]["skill_consumption"], False)
        self.assertIs(result["core-design"]["skill_consumption"], True)
        self.assertIs(result["core-apply"]["skill_consumption"], False)

    def test_existing_direct_key_is_the_only_replacement(self):
        source = '''{
  "core-design": {
    "nested": {"skill_consumption": false},
    // "skill_consumption": false
    "skill_consumption" /* keep */ : false // retained
  },
  "core-apply": {"skill_consumption": false}
}'''
        self.write(source)
        raw, _ = self.update()
        self.assertEqual(raw, source.replace(': false // retained', ': true // retained'))

    def test_single_line_namespace_and_escaped_string_values(self):
        source = json.dumps({"core-design": {"url": 'https://example.test/a//b?text="/* x */"\\', "cleanup": True}, "core-apply": {"cleanup": False}})
        self.write(source)
        raw, result = self.update()
        self.assertEqual(result["core-design"]["url"], json.loads(source)["core-design"]["url"])
        self.assertEqual(result["core-apply"], {"cleanup": False})
        self.assertIn('"cleanup": true, "skill_consumption": true', raw)

    def test_replace_string_containing_comment_markers(self):
        source = '{"core-design": {"url": "https://old.test/*q*/"}} // retained\n'
        self.write(source)
        raw, result = self.update('https://new.test/a//b"\\', "url")
        self.assertEqual(result["core-design"]["url"], 'https://new.test/a//b"\\')
        self.assertTrue(raw.endswith(" // retained\n"))

    def test_multiline_value_replacement_keeps_following_fields(self):
        source = '{"core-design": {"custom": {\n "a": [1, 2]\n}, "cleanup": false}}'
        self.write(source)
        _, result = self.update({"b": [True, None]}, "custom")
        self.assertEqual(result["core-design"], {"custom": {"b": [True, None]}, "cleanup": False})

    def test_repeated_update_is_byte_identical_and_does_not_write(self):
        for value in (True, False, None, {"nested": [True, 1]}, "中文"):
            with self.subTest(value=value):
                self.write(json.dumps({"core-design": {"skill_consumption": value}}, ensure_ascii=False) + " // keep\n")
                original = self.path.read_bytes()
                with patch("os.replace", side_effect=AssertionError("No write expected")):
                    self.update(value)
                self.assertEqual(self.path.read_bytes(), original)

    def test_boolean_is_not_integer_even_inside_objects(self):
        self.write('{"core-design": {"skill_consumption": 1, "custom": {"a": 1}}}')
        _, result = self.update()
        self.assertIs(result["core-design"]["skill_consumption"], True)
        _, result = self.update({"a": True}, "custom")
        self.assertIs(result["core-design"]["custom"]["a"], True)

    def test_crlf_and_permissions_are_preserved(self):
        self.write('{\r\n  "core-design": {\r\n    "cleanup": true // keep\r\n  }\r\n}\r\n')
        self.path.chmod(0o640)
        raw, _ = self.update()
        self.assertNotIn("\n", raw.replace("\r\n", ""))
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)

    def test_escaped_namespace_and_key_names(self):
        self.write('{"core-\\u0064esign": {"skill_\\u0063onsumption": false}}')
        raw, _ = self.update()
        self.assertEqual(raw, '{"core-\\u0064esign": {"skill_\\u0063onsumption": true}}')

    def test_invalid_ambiguous_or_missing_namespace_leaves_original_untouched(self):
        cases = (
            '{"core-design": {,}}',
            '{"core-design": {"cleanup": true,}}',
            '{"core-design": {"cleanup": true /* unfinished}}',
            '{"core-design": {"cleanup": NaN}}',
            '{"core-design": {"cleanup": true, "cleanup": false}}',
            '{"core-design": {}, "core-design": {}}',
            '{"other": {"core-design": {}}}',
            '{"core-design": false}',
            '[]',
        )
        for source in cases:
            with self.subTest(source=source):
                self.write(source)
                ok, error = writer.update_config_value("core-design", "skill_consumption", True)
                self.assertFalse(ok)
                self.assertTrue(error)
                self.assertEqual(self.path.read_bytes(), source.encode("utf-8"))

    def test_non_json_value_leaves_original_untouched(self):
        for value in (float("nan"), float("inf"), object()):
            with self.subTest(value=value):
                source = '{"core-design": {}}'
                self.write(source)
                self.assertFalse(writer.update_config_value("core-design", "skill_consumption", value)[0])
                self.assertEqual(self.path.read_bytes(), source.encode())

    def test_missing_file_does_not_create_config(self):
        self.assertFalse(writer.update_config_value("core-design", "skill_consumption", True)[0])
        self.assertFalse(self.path.exists())

    def test_atomic_replace_failure_leaves_original_and_removes_temporary(self):
        source = '{"core-design": {}}'
        self.write(source)
        with patch("os.replace", side_effect=OSError("simulated write failure")):
            self.assertFalse(writer.update_config_value("core-design", "skill_consumption", True)[0])
        self.assertEqual(self.path.read_bytes(), source.encode())
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_concurrent_edit_detected_before_replace_is_retained(self):
        self.write('{"core-design": {}}')
        edited = b'{"core-design": {"cleanup": false}}'
        with patch("os.chmod", side_effect=lambda *args: self.path.write_bytes(edited)):
            ok, error = writer.update_config_value("core-design", "skill_consumption", True)
        self.assertFalse(ok)
        self.assertIn("其他操作修改", error)
        self.assertEqual(self.path.read_bytes(), edited)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], *unittest_args])
