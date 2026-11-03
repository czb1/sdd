"""Verify Skill consumption with the config-driven flow-config runtime."""

import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
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
        self.project = Path(directory.name) / "project"
        path_patch = patch.object(flow, "get_config_path", return_value=self.config)
        path_patch.start()
        self.addCleanup(path_patch.stop)
        guide_patch = patch.object(flow, "get_guide_path", return_value=Path(directory.name) / "guide.md")
        guide_patch.start()
        self.addCleanup(guide_patch.stop)
        # The full framework's template package is optional in this repository.
        template_patch = patch.dict(sys.modules, {"core_templates": None})
        template_patch.start()
        self.addCleanup(template_patch.stop)

    def command(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = flow.cmd_flow_config(["--json", "--project-root", str(self.project), *args])
        self.assertEqual(code, 0)
        return json.loads(output.getvalue())

    def rebuild(self, skill):
        result = self.command("--skill", skill)
        self.assertTrue(result["ok"], result)
        for removed in ("scenario", "confirm_required", "config_missing", "ns_missing"):
            self.assertNotIn(removed, result)
        self.assertEqual(json.loads(Path(result["plan_path"]).read_text()), result["plan"])
        self.assertEqual(json.loads(Path(result["skipped_path"]).read_text()), result["plan"]["disabled"])
        return result

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
                                suffix = "-multi" if skill == "core-apply" and mode == "multi" else ""
                                self.assertEqual(entry["ref_file"][mode], f"references/skill-consumption{suffix}.md")
                                self.assertTrue((ROOT / skill / entry["ref_file"][mode]).is_file())
                        else:
                            self.assertNotIn("config_key", entry)
                            self.assertNotIn("ref_file", entry)
                            self.assertIn("skill_consumption", plan["disabled"])

    def test_config_edits_rebuild_plan_without_confirmation_or_writeback(self):
        self.initialize()
        original = self.read_config()
        for skill in ("core-design", "core-apply"):
            before = flow.canonical_fingerprint(original[skill])
            for enabled in (True, False, True, False):
                config = self.read_config()
                config[skill]["skill_consumption"] = enabled
                self.config.write_text("// User-edited config\n" + json.dumps(config, ensure_ascii=False), encoding="utf-8")
                source = self.config.read_bytes()
                result = self.rebuild(skill)
                self.assertFalse(result["config_initialized"])
                self.assertIs(self.entry(result["plan"])["enabled"], enabled)
                self.assertEqual(result["plan"]["_fingerprint"] == before, not enabled)
                self.assertEqual(self.config.read_bytes(), source)
                for namespace, values in original.items():
                    for name, value in values.items():
                        if (namespace, name) != (skill, "skill_consumption"):
                            self.assertEqual(config[namespace][name], value)
        self.assertEqual(self.read_config(), original)

    def test_first_run_initializes_config_and_missing_namespace_silently(self):
        first = self.rebuild("core-apply")
        self.assertTrue(first["config_initialized"])
        self.assertFalse(self.entry(first["plan"])["enabled"])
        self.assertTrue(flow.get_guide_path().is_file())
        self.assertFalse(self.rebuild("core-apply")["config_initialized"])
        original = self.read_config()
        added = self.rebuild("core-design")
        self.assertTrue(added["config_initialized"])
        self.assertFalse(self.entry(added["plan"])["enabled"])
        self.assertIs(self.read_config()["core-design"]["skill_consumption"], False)
        for key, value in original.items():
            self.assertEqual(self.read_config()[key], value)
        self.assertFalse(self.rebuild("core-design")["config_initialized"])

    def test_invalid_config_preserves_last_plan_and_skipped_markers(self):
        self.initialize()
        results = {skill: self.rebuild(skill) for skill in ("core-design", "core-apply")}
        saved = {Path(result[key]): Path(result[key]).read_bytes()
                 for result in results.values() for key in ("plan_path", "skipped_path")}
        for content in ("{broken", json.dumps({skill: {"skill_consumption": {"type": "reference"}}
                                               for skill in results})):
            self.config.write_text(content, encoding="utf-8")
            for skill in results:
                self.assertFalse(self.command("--skill", skill)["ok"])
            for path, expected in saved.items():
                self.assertEqual(path.read_bytes(), expected)

    def test_multi_repo_fragment_is_sufficient_for_consumption_and_custom_slots(self):
        for enabled in (True, False):
            namespace = {"skill_consumption": enabled, "judgment_ladder": {
                "type": "reference", "file": "references/judgment-ladder.md", "at": "pre-codegen"}}
            self.config.write_text(json.dumps({"core-apply": namespace}), encoding="utf-8")
            result = self.rebuild("core-apply")
            repo_cwd = self.project / "service-a"
            fragment = self.command("--skill", "core-apply", "--fragment", "--repo", "service-a", "--repo-cwd", str(repo_cwd))
            self.assertEqual(fragment["repo_cwd"], str(repo_cwd))
            self.assertEqual(fragment["plan_path"], result["plan_path"])
            self.assertNotIn("steps", fragment)
            self.assertEqual(fragment["orchestration_points"], result["plan"]["orchestration_points"])
            # A codegen agent receives only its fragment; no single-repo steps
            # or root-plan read should be needed to decide what to load.
            Path(fragment["plan_path"]).unlink()
            saved = self.project / "docs/.flow_context/execution-plan-fragment-core-apply-service-a.json"
            self.assertEqual(json.loads(saved.read_text()), fragment)
            phase = json.loads(saved.read_text())["built_in_steps"]["skill_consumption"]
            self.assertEqual(phase["phase"], "M-1a")
            self.assertIs(phase["enabled"], enabled)
            self.assertNotIn("at", phase)
            self.assertNotIn("skill_md_step", phase)
            if enabled:
                self.assertEqual(phase["ref_file"], "references/skill-consumption-multi.md")
                self.assertTrue((ROOT / "core-apply" / phase["ref_file"]).is_file())
            else:
                self.assertNotIn("ref_file", phase)

    def test_fragment_uses_persisted_plan_until_next_rebuild(self):
        self.config.write_text(json.dumps({"core-apply": {"skill_consumption": True}}))
        result = self.rebuild("core-apply")
        self.config.write_text(json.dumps({"core-apply": {"skill_consumption": False}}))
        for repo in ("service-a", "service-b"):
            fragment = self.command("--skill", "core-apply", "--fragment", "--repo", repo,
                                    "--repo-cwd", str(self.project / repo))
            self.assertEqual(fragment["repo"], repo)
            self.assertEqual(fragment["repo_cwd"], str(self.project / repo))
            self.assertEqual(fragment["plan_path"], result["plan_path"])
            self.assertTrue(fragment["built_in_steps"]["skill_consumption"]["enabled"])
        self.rebuild("core-apply")
        fragment = self.command("--skill", "core-apply", "--fragment", "--repo", "service-a",
                                "--repo-cwd", str(self.project / "service-a"))
        self.assertFalse(fragment["built_in_steps"]["skill_consumption"]["enabled"])

    def test_default_disabled_fragment_is_written_without_json_output(self):
        self.rebuild("core-apply")
        with contextlib.redirect_stdout(io.StringIO()):
            code = flow.run_fragment("core-apply", "service-a", str(self.project / "service-a"),
                                     str(self.project), False)
        self.assertEqual(code, 0)
        saved = self.project / "docs/.flow_context/execution-plan-fragment-core-apply-service-a.json"
        self.assertEqual(json.loads(saved.read_text())["built_in_steps"], {
            "skill_consumption": {"phase": "M-1a", "enabled": False}})

    def test_other_skill_fragments_keep_their_existing_contract(self):
        for skill in ("core-design", "core-explore", "core-init", "core-archive"):
            self.rebuild(skill)
            fragment = self.command("--skill", skill, "--fragment", "--repo", "service-a",
                                    "--repo-cwd", str(self.project / "service-a"))
            self.assertEqual(set(fragment), {"repo", "repo_cwd", "plan_path", "orchestration_points"})

    def test_cli_describe_reports_both_default_disabled_switches(self):
        for skill in ("core-design", "core-apply"):
            schema = self.command("--skill", skill, "--describe")
            entry = next(b for b in schema["built_in_steps"] if b["key"] == "skill_consumption")
            self.assertIs(entry["default"], False)
            self.assertEqual(entry["depends_on"], [])

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


@unittest.skipIf(flow is None, "Supply the runtime via --flow-config /path/to/flow_config.py")
class FlowReferenceConsistencyTests(unittest.TestCase):
    def test_review_reference_headings_match_registry_and_steps(self):
        for skill in ("core-design", "core-apply"):
            skeleton = (ROOT / skill / "SKILL.md").read_text(encoding="utf-8")
            steps = (ROOT / skill / "steps.md").read_text(encoding="utf-8")
            for builtin in flow.get_built_in_steps(skill):
                if builtin["key"] not in {"design_traceability", "design_review", "l4_review", "l5_coverage"}:
                    continue
                label = builtin["skill_md_step"]
                marker = f"[可配置: {builtin['key']}]"
                rows = [line for line in steps.splitlines()
                        if line.startswith("|") and marker in line]
                self.assertTrue(rows, (skill, builtin["key"]))
                self.assertTrue(any(f"| {label} |" in row for row in rows))
                heading = label if skill == "core-design" else label.split()[1] + "."
                pattern = rf"(?m)^### {re.escape(heading)}.*{re.escape(marker)}"
                self.assertIsNotNone(re.search(pattern, skeleton), (skill, builtin["key"], label))
                for mode, reference in builtin["ref_file"].items():
                    with self.subTest(skill=skill, key=builtin["key"], mode=mode):
                        title = (ROOT / skill / reference).read_text(encoding="utf-8").splitlines()[0]
                        self.assertTrue(title.startswith(f"# {label}:"), title)

    def test_disabled_design_gates_do_not_bypass_skill_association(self):
        builtins = {b["key"]: b for b in flow.get_built_in_steps("core-design")}
        consumption_phase = builtins["skill_consumption"]["skill_md_step"]
        for key in ("design_traceability", "design_review"):
            for mode, reference in builtins[key]["ref_file"].items():
                with self.subTest(key=key, mode=mode):
                    text = (ROOT / "core-design" / reference).read_text(encoding="utf-8")
                    transitions = [line for line in text.splitlines()
                                   if "`design_traceability` 关闭" in line and "进入" in line]
                    self.assertTrue(transitions, reference)
                    for transition in transitions:
                        self.assertIn(f"{consumption_phase} 完成或跳过后", transition)
        reference = builtins["design_traceability"]["ref_file"]["multi"]
        text = (ROOT / "core-design" / reference).read_text(encoding="utf-8")
        self.assertIn(f"通用 `post-generate` 插槽执行完毕且 {consumption_phase} 完成或按计划跳过后", text)


if __name__ == "__main__":
    if flow is None:
        raise SystemExit("Runtime source is absent. Use --flow-config /path/to/flow_config.py after applying the patch.")
    unittest.main(argv=[sys.argv[0], *unittest_args])
