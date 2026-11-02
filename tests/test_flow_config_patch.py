"""Verify safe application of the runtime fixes, independent of source order."""

import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("apply_flow_config_fixes", ROOT / "patches/apply_flow_config_fixes.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

ORIGINAL_FUNCTION = '''def update_config_value(skill: str, key: str, value):
    return False, "old writer"
'''
UNRELATED = '''def unrelated():
    # Keep this function byte-for-byte.
    return {"core-design": {"skill_consumption": False}}
'''


class PatchApplicationTests(unittest.TestCase):
    def test_function_order_does_not_matter_and_other_code_is_preserved(self):
        for source in (ORIGINAL_FUNCTION + "\n" + UNRELATED, UNRELATED + "\n" + ORIGINAL_FUNCTION):
            with self.subTest(source=source):
                result = installer.transform(source)
                self.assertIn(UNRELATED, result)
                self.assertNotIn("old writer", result)
                names = [node.name for node in ast.parse(result).body if isinstance(node, ast.FunctionDef)]
                self.assertEqual(names.count("update_config_value"), 1)
                self.assertEqual(len([name for name in names if name.startswith("_flow_jsonc_")]), 4)

    def test_metadata_fixes_are_idempotent(self):
        metadata = 'METADATA = """\n' + '\n'.join(old for old, _ in installer.REPLACEMENTS) + '\n"""\n'
        result = installer.transform(metadata + ORIGINAL_FUNCTION)
        self.assertEqual(installer.transform(result), result)
        for _, new in installer.REPLACEMENTS:
            self.assertIn(new, result)

    def test_crlf_source_keeps_line_endings(self):
        result = installer.transform(ORIGINAL_FUNCTION.replace("\n", "\r\n"))
        self.assertNotIn("\n", result.replace("\r\n", ""))
        self.assertEqual(installer.transform(result), result)

    def test_missing_duplicate_or_incompatible_function_is_rejected(self):
        for source in (UNRELATED, ORIGINAL_FUNCTION * 2, 'def update_config_value(other):\n    pass\n', '@decorator\n' + ORIGINAL_FUNCTION):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    installer.transform(source)

    def test_apply_keeps_backup_and_second_apply_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flow_config.py"
            path.write_text(ORIGINAL_FUNCTION, encoding="utf-8")
            backup = installer.apply_to(path)
            self.assertEqual(backup.read_text(), ORIGINAL_FUNCTION)
            patched = path.read_bytes()
            self.assertIsNone(installer.apply_to(path))
            self.assertEqual(path.read_bytes(), patched)
            self.assertEqual(backup.read_text(), ORIGINAL_FUNCTION)

    def test_existing_backup_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flow_config.py"
            path.write_text(ORIGINAL_FUNCTION, encoding="utf-8")
            backup = path.with_name(path.name + ".before-flow-config-fixes.bak")
            backup.write_bytes(b"earlier backup")
            with self.assertRaises(FileExistsError):
                installer.apply_to(path)
            self.assertEqual(path.read_text(), ORIGINAL_FUNCTION)
            self.assertEqual(backup.read_bytes(), b"earlier backup")

    def test_apply_failure_retains_source_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flow_config.py"
            path.write_text(ORIGINAL_FUNCTION, encoding="utf-8")
            with patch("os.replace", side_effect=OSError("simulated failure")):
                with self.assertRaises(OSError):
                    installer.apply_to(path)
            self.assertEqual(path.read_text(), ORIGINAL_FUNCTION)
            backup = path.with_name(path.name + ".before-flow-config-fixes.bak")
            self.assertEqual(backup.read_text(), ORIGINAL_FUNCTION)
            self.assertEqual(set(path.parent.iterdir()), {path, backup})


if __name__ == "__main__":
    unittest.main()
