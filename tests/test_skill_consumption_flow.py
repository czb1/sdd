"""Exercise the real flow-config parser, toggles and plan builder in isolation."""

import argparse
import sys
import importlib.util
import json
from pathlib import Path
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


@unittest.skipIf(flow is None, "Supply the complete runtime via --flow-config /path/to/flow_config.py")

class SkillConsumptionFlowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = Path(self.directory.name) / "flow-config.json"
        self.path_patch = patch.object(flow, "get_config_path", return_value=self.config)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)

    def initialize_both_namespaces(self):
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

    def plan(self, skill):
        namespace = flow.get_skill_namespace(self.read_config(), skill)
        self.assertEqual(flow.validate_namespace(namespace, skill), [])
        plan = flow.build_execution_plan(skill, namespace)
        self.assertEqual(flow.consistency_check(plan), [])
        return plan

    def toggle(self, skill, enabled):
        fn = flow.uncomment_config_key if enabled else flow.comment_out_config_key
        ok, error = fn(skill, "skill_consumption")
        self.assertTrue(ok, error)

    def test_default_template_and_namespace_extraction_keep_consumption_disabled(self):
        parsed = flow.parse_jsonc(flow.TEMPLATE_JSONC)
        self.assertNotIn("skill_consumption", parsed.get("core-apply", {}))
        self.initialize_both_namespaces()
        for skill in ("core-design", "core-apply"):
            self.assertNotIn("skill_consumption", self.read_config()[skill])
            declaration = next(entry for entry in flow.list_commented_custom_steps(skill)
                               if entry["key"] == "skill_consumption")
            self.assertEqual(declaration["declaration"]["type"], "reference")
            self.assertFalse(any(entry["key"] == "skill_consumption" for items in self.plan(skill)["orchestration_points"].values() for entry in items))

    def test_all_four_enable_combinations_use_only_their_slots(self):
        for design in (False, True):
            for apply in (False, True):
                with self.subTest(design=design, apply=apply):
                    self.initialize_both_namespaces()
                    for skill, enabled, slot in (("core-design", design, "post-generate"),
                                                 ("core-apply", apply, "pre-codegen")):
                        if enabled:
                            self.toggle(skill, True)
                        plan = self.plan(skill)
                        entries = [entry for entry in plan["orchestration_points"][slot]
                                   if entry["key"] == "skill_consumption"]
                        self.assertEqual(len(entries), int(enabled))
                        self.assertFalse(any(entry.get("config_key") == "skill_consumption"
                                             for entry in plan["steps"]))
                        if entries:
                            self.assertEqual(entries[0]["type"], "reference")
                            self.assertEqual(entries[0]["file"], "references/skill-consumption.md")
                            self.assertNotIn("run_mode", entries[0])
                        for other_slot, items in plan["orchestration_points"].items():
                            if other_slot != slot:
                                self.assertFalse(any(entry["key"] == "skill_consumption" for entry in items))

    def test_enable_disable_restore_updates_real_plans_and_fingerprints(self):
        self.initialize_both_namespaces()
        for skill in ("core-design", "core-apply"):
            before = flow.canonical_fingerprint(self.read_config()[skill])
            self.toggle(skill, True)
            enabled = flow.canonical_fingerprint(self.read_config()[skill])
            self.assertNotEqual(before, enabled)
            self.toggle(skill, False)
            self.assertEqual(flow.canonical_fingerprint(self.read_config()[skill]), before)
            self.assertFalse(any(entry["key"] == "skill_consumption" for items in self.plan(skill)["orchestration_points"].values() for entry in items))
            self.toggle(skill, True)
            self.assertEqual(flow.canonical_fingerprint(self.read_config()[skill]), enabled)

    def test_expert_experience_stays_independent_and_closed_refs_are_unloaded(self):
        self.initialize_both_namespaces()
        self.toggle("core-design", True)
        ok, error = flow.update_config_value("core-design", "expert_experience", False)
        self.assertTrue(ok, error)
        plan = self.plan("core-design")
        self.assertIn("expert_experience", plan["disabled"])
        self.assertFalse(any(entry.get("config_key") == "expert_experience" for entry in plan["steps"]))
        closed = next(entry for entry in plan["steps"] if entry["key"] == "step-6")
        self.assertFalse(closed["enabled"])
        self.assertNotIn("ref_file", closed)
        self.assertEqual(plan["orchestration_points"]["post-generate"][0]["key"], "skill_consumption")
        self.assertEqual([entry["key"] for entry in self.plan("core-apply")["orchestration_points"]["pre-codegen"]], ["judgment_ladder"])

    def test_reject_boolean_switch_and_wrong_slot_for_custom_consumption(self):
        for skill, wrong_slot in (("core-design", "pre-codegen"), ("core-apply", "post-generate")):
            self.assertTrue(flow.validate_namespace({"skill_consumption": True}, skill))
            self.assertTrue(flow.validate_namespace({"skill_consumption": {
                "type": "reference", "file": "references/skill-consumption.md", "at": wrong_slot}}, skill))

    def test_same_slot_custom_entries_remain_when_consumption_is_disabled(self):
        self.initialize_both_namespaces()
        self.toggle("core-apply", True)
        config = self.read_config()
        other = {"type": "reference", "file": "references/judgment-ladder.md", "at": "pre-codegen", "order": 2}
        config["core-apply"]["judgment_ladder"] = other
        self.config.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        self.toggle("core-apply", False)
        entries = self.plan("core-apply")["orchestration_points"]["pre-codegen"]
        self.assertEqual([entry["key"] for entry in entries], ["judgment_ladder"])
        self.assertEqual(self.read_config()["core-apply"]["judgment_ladder"], other)
        self.assertTrue(flow.is_all_default_plan(self.plan("core-design")))


if __name__ == "__main__":
    if flow is None:
        raise SystemExit("Runtime source is absent. Use --flow-config /path/to/flow_config.py after applying the patch.")
    unittest.main(argv=[sys.argv[0], *unittest_args])
