"""Exercise builtin consumption against a supplied complete flow_config.py."""

import argparse
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
source_path = ROOT / "core-shared/scripts/flow_config.py"
unittest_args = sys.argv[1:]
if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--flow-config", type=Path, default=source_path)
    options, unittest_args = parser.parse_known_args()
    source_path = options.flow_config
flow = None
if source_path.is_file():
    spec = importlib.util.spec_from_file_location("flow_config", source_path)
    flow = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(flow)


@unittest.skipIf(flow is None, "Supply the runtime via --flow-config /path/to/flow_config.py")
class SkillConsumptionFlowTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.config = Path(directory.name) / "flow-config.json"
        path_patch = patch.object(flow, "get_config_path", return_value=self.config)
        path_patch.start()
        self.addCleanup(path_patch.stop)

    def initialize(self):
        blocks = []
        for skill in ("core-design", "core-apply"):
            block = flow._extract_skill_block_from_template(skill)
            self.assertIsNotNone(block)
            blocks.append(block.strip().rstrip(","))
        self.config.write_text("{\n" + ",\n".join(blocks) + "\n}\n", encoding="utf-8")

    def read_config(self):
        config, error = flow.load_config(self.config)
        self.assertIsNone(error)
        return config

    def plan(self, skill, namespace):
        self.assertEqual(flow.validate_namespace(namespace, skill), [])
        plan = flow.build_execution_plan(skill, namespace)
        self.assertEqual(flow.consistency_check(plan), [])
        return plan

    def entry(self, plan):
        builtin = next(b for b in flow.get_built_in_steps(plan["skill"]) if b["key"] == "skill_consumption")
        return next(e for e in plan["steps"] if e["key"] == builtin["at"])

    def test_template_and_namespace_extraction_use_false_switches(self):
        self.assertIs(flow.parse_jsonc(flow.TEMPLATE_JSONC)["core-apply"]["skill_consumption"], False)
        self.initialize()
        for skill in ("core-design", "core-apply"):
            self.assertIs(self.read_config()[skill]["skill_consumption"], False)
            self.assertFalse(any(e["key"] == "skill_consumption" for e in flow.list_commented_custom_steps(skill)))

    def test_missing_namespace_and_key_are_default_disabled(self):
        for skill in ("core-design", "core-apply"):
            for namespace in (None, {}):
                plan = flow.build_execution_plan(skill, namespace)
                self.assertEqual(flow.consistency_check(plan), [])
                self.assertTrue(flow.is_all_default_plan(plan))
                self.assertFalse(self.entry(plan)["enabled"])
                self.assertTrue(plan["disabled"]["skill_consumption"]["default_disabled"])

    def test_four_enable_combinations_are_builtins_outside_custom_slots(self):
        for design in (False, True):
            for apply in (False, True):
                for skill, enabled in (("core-design", design), ("core-apply", apply)):
                    with self.subTest(design=design, apply=apply, skill=skill):
                        plan = self.plan(skill, {"skill_consumption": enabled})
                        entry = self.entry(plan)
                        self.assertIs(entry["enabled"], enabled)
                        self.assertFalse(any(e["key"] == "skill_consumption" for items in plan["orchestration_points"].values() for e in items))
                        if enabled:
                            self.assertEqual(entry["type"], "built_in")
                            self.assertEqual(entry["config_key"], "skill_consumption")
                            self.assertNotIn("skill_consumption", plan["disabled"])
                            for mode in ("single", "multi"):
                                self.assertEqual(entry["ref_file"][mode], "references/skill-consumption.md")
                                self.assertTrue((ROOT / skill / entry["ref_file"][mode]).is_file())
                        else:
                            self.assertNotIn("config_key", entry)
                            self.assertNotIn("ref_file", entry)
                            self.assertIn("skill_consumption", plan["disabled"])

    def test_boolean_roundtrip_preserves_other_config_and_fingerprint(self):
        self.initialize()
        original = self.read_config()
        for skill in ("core-design", "core-apply"):
            before = flow.canonical_fingerprint(original[skill])
            for enabled in (True, False, True, False):
                ok, error = flow.update_config_value(skill, "skill_consumption", enabled)
                self.assertTrue(ok, error)
                config = self.read_config()
                self.assertIs(self.entry(self.plan(skill, config[skill]))["enabled"], enabled)
                self.assertEqual(flow.canonical_fingerprint(config[skill]) == before, not enabled)
                for name, value in original[skill].items():
                    if name != "skill_consumption":
                        self.assertEqual(config[skill][name], value)
        self.assertEqual(self.read_config(), original)

    def test_legacy_custom_objects_and_non_booleans_are_rejected(self):
        for skill, slot in (("core-design", "post-generate"), ("core-apply", "pre-codegen")):
            for value in ({"type": "reference", "file": "references/skill-consumption.md", "at": slot}, "true", 1, None):
                with self.subTest(skill=skill, value=value):
                    self.assertTrue(flow.validate_namespace({"skill_consumption": value}, skill))
            for value in (False, True):
                self.assertEqual(flow.validate_namespace({"skill_consumption": value}, skill), [])

    def test_expert_experience_and_apply_consumption_are_independent(self):
        plan = self.plan("core-design", {"expert_experience": False, "skill_consumption": True})
        self.assertIn("expert_experience", plan["disabled"])
        self.assertTrue(self.entry(plan)["enabled"])
        self.assertFalse(self.entry(self.plan("core-apply", {}))["enabled"])
        plan = self.plan("core-design", {"expert_experience": True, "skill_consumption": False})
        self.assertTrue(any(e.get("config_key") == "expert_experience" for e in plan["steps"]))
        self.assertFalse(self.entry(plan)["enabled"])

    def test_registration_and_positions_match_sequential_flow(self):
        for skill, count, position in (("core-design", 12, 8), ("core-apply", 16, 9)):
            plan = self.plan(skill, {"skill_consumption": True})
            self.assertEqual([e["key"] for e in plan["steps"]], [f"step-{i}" for i in range(count)])
            self.assertEqual(plan["steps"][position]["config_key"], "skill_consumption")
            label = "Phase" if skill == "core-design" else "Step"
            self.assertEqual(plan["steps"][position]["skill_md_step"], f"{label} 9")
            self.assertEqual(plan["steps"][position + 1]["skill_md_step"], f"{label} 10")
            registrations = flow.get_built_in_steps(skill)
            self.assertEqual(len({b["at"] for b in registrations}), len(registrations))
            for registered in registrations:
                enabled = self.plan(skill, {registered["key"]: True})
                entry = next(e for e in enabled["steps"] if e.get("config_key") == registered["key"])
                self.assertEqual(entry["key"], registered["at"])
                self.assertEqual(entry["skill_md_step"], registered["skill_md_step"])

    def test_custom_slots_continue_independently(self):
        other = {"type": "reference", "file": "references/judgment-ladder.md", "at": "pre-codegen", "order": 2}
        for enabled in (True, False):
            plan = self.plan("core-apply", {"skill_consumption": enabled, "judgment_ladder": other})
            entries = plan["orchestration_points"]["pre-codegen"]
            self.assertEqual([e["key"] for e in entries], ["judgment_ladder"])
            self.assertEqual(entries[0]["file"], other["file"])
            self.assertIs(self.entry(plan)["enabled"], enabled)


if __name__ == "__main__":
    if flow is None:
        raise SystemExit("Runtime source is absent. Use --flow-config /path/to/flow_config.py after applying the patch.")
    unittest.main(argv=[sys.argv[0], *unittest_args])
