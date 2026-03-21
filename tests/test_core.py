"""
Tests for Delimit core engines: diff, policy, semver, explainer, ci_formatter.

Run with:
    python -m pytest tests/ -v
    python -m unittest tests.test_core
"""

import os
import sys
import unittest
from pathlib import Path

import yaml

# Ensure the repo root is on sys.path so `core` package resolves.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.diff_engine_v2 import OpenAPIDiffEngine, Change, ChangeType
from core.policy_engine import PolicyEngine, evaluate_with_policy
from core.semver_classifier import (
    SemverBump,
    classify,
    classify_detailed,
    bump_version,
)
from core.explainer import TEMPLATES, explain, explain_all
from core.ci_formatter import CIFormatter, OutputFormat, format_for_ci

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> dict:
    with open(FIXTURES / name) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Fixtures loaded once per module
# ---------------------------------------------------------------------------

V1 = _load("api_v1.yaml")
V2_BREAKING = _load("api_v2_breaking.yaml")
V2_SAFE = _load("api_v2_safe.yaml")


# ===================================================================
# Diff Engine Tests
# ===================================================================

class TestDiffEngineBreaking(unittest.TestCase):
    """Diff engine correctly detects breaking changes between v1 and v2_breaking."""

    def setUp(self):
        self.engine = OpenAPIDiffEngine()
        self.changes = self.engine.compare(V1, V2_BREAKING)
        self.breaking = [c for c in self.changes if c.is_breaking]

    def test_has_breaking_changes(self):
        self.assertTrue(len(self.breaking) > 0, "Should detect breaking changes")

    def test_endpoint_removed(self):
        removed = [c for c in self.changes if c.type == ChangeType.ENDPOINT_REMOVED]
        paths = [c.path for c in removed]
        self.assertIn("/users/{id}/profile", paths)

    def test_required_param_added(self):
        added = [c for c in self.changes if c.type == ChangeType.REQUIRED_PARAM_ADDED]
        self.assertTrue(len(added) >= 1, "Should detect added required param (org_id)")
        messages = " ".join(c.message for c in added)
        self.assertIn("org_id", messages)

    def test_type_changed(self):
        changed = [c for c in self.changes if c.type == ChangeType.TYPE_CHANGED]
        self.assertTrue(len(changed) >= 1, "Should detect type change on id param")

    def test_enum_value_removed(self):
        removed = [c for c in self.changes if c.type == ChangeType.ENUM_VALUE_REMOVED]
        values = [c.details.get("value") for c in removed]
        self.assertIn("guest", values)

    def test_breaking_count_at_least_four(self):
        # endpoint_removed, required_param_added, type_changed, enum_value_removed
        self.assertGreaterEqual(len(self.breaking), 4)


class TestDiffEngineSafe(unittest.TestCase):
    """Diff engine correctly reports only non-breaking changes for v2_safe."""

    def setUp(self):
        self.engine = OpenAPIDiffEngine()
        self.changes = self.engine.compare(V1, V2_SAFE)
        self.breaking = [c for c in self.changes if c.is_breaking]

    def test_no_breaking_changes(self):
        self.assertEqual(len(self.breaking), 0, f"Expected 0 breaking, got: {self.breaking}")

    def test_endpoint_added(self):
        added = [c for c in self.changes if c.type == ChangeType.ENDPOINT_ADDED]
        paths = [c.path for c in added]
        self.assertIn("/users/{id}/settings", paths)

    def test_enum_value_added(self):
        added = [c for c in self.changes if c.type == ChangeType.ENUM_VALUE_ADDED]
        values = [c.details.get("value") for c in added]
        self.assertIn("moderator", values)

    def test_has_additive_changes(self):
        self.assertTrue(len(self.changes) > 0, "Should detect at least some changes")


class TestDiffEngineNoChanges(unittest.TestCase):
    """Diff engine returns empty list when specs are identical."""

    def test_identical_specs(self):
        engine = OpenAPIDiffEngine()
        changes = engine.compare(V1, V1)
        self.assertEqual(len(changes), 0)


# ===================================================================
# Policy Engine Tests
# ===================================================================

class TestPolicyEngineBreaking(unittest.TestCase):
    """Policy engine returns fail for breaking changes."""

    def test_decision_fail(self):
        result = evaluate_with_policy(V1, V2_BREAKING)
        self.assertEqual(result["decision"], "fail")

    def test_has_violations(self):
        result = evaluate_with_policy(V1, V2_BREAKING)
        self.assertGreater(result["summary"]["violations"], 0)

    def test_has_error_severity(self):
        result = evaluate_with_policy(V1, V2_BREAKING)
        self.assertGreater(result["summary"]["errors"], 0)

    def test_exit_code_nonzero(self):
        result = evaluate_with_policy(V1, V2_BREAKING)
        self.assertEqual(result["exit_code"], 1)


class TestPolicyEngineSafe(unittest.TestCase):
    """Policy engine returns pass for safe/additive changes."""

    def test_decision_pass(self):
        result = evaluate_with_policy(V1, V2_SAFE)
        self.assertEqual(result["decision"], "pass")

    def test_no_error_violations(self):
        result = evaluate_with_policy(V1, V2_SAFE)
        self.assertEqual(result["summary"]["errors"], 0)

    def test_exit_code_zero(self):
        result = evaluate_with_policy(V1, V2_SAFE)
        self.assertEqual(result["exit_code"], 0)


class TestPolicyEngineDefaultRules(unittest.TestCase):
    """PolicyEngine loads default rules automatically."""

    def test_default_rules_loaded(self):
        engine = PolicyEngine()
        self.assertEqual(len(engine.rules), len(PolicyEngine.DEFAULT_RULES))


class TestPolicyEngineSemver(unittest.TestCase):
    """Policy evaluation returns semver metadata for action outputs."""

    def test_breaking_changes_get_major_bump_and_next_version(self):
        result = evaluate_with_policy(
            V1,
            V2_BREAKING,
            include_semver=True,
            current_version=V1["info"]["version"],
            api_name=V1["info"]["title"],
        )
        self.assertEqual(result["semver"]["bump"], "major")
        self.assertEqual(result["semver"]["next_version"], "2.0.0")

    def test_safe_changes_get_minor_bump_and_next_version(self):
        result = evaluate_with_policy(
            V1,
            V2_SAFE,
            include_semver=True,
            current_version=V1["info"]["version"],
            api_name=V1["info"]["title"],
        )
        self.assertEqual(result["semver"]["bump"], "minor")
        self.assertEqual(result["semver"]["next_version"], "1.1.0")


# ===================================================================
# Semver Classifier Tests
# ===================================================================

class TestSemverClassifierBreaking(unittest.TestCase):
    """Semver classifier returns MAJOR for breaking changes."""

    def setUp(self):
        engine = OpenAPIDiffEngine()
        self.changes = engine.compare(V1, V2_BREAKING)

    def test_classify_major(self):
        bump = classify(self.changes)
        self.assertEqual(bump, SemverBump.MAJOR)

    def test_detailed_is_breaking(self):
        detail = classify_detailed(self.changes)
        self.assertTrue(detail["is_breaking"])
        self.assertEqual(detail["bump"], "major")

    def test_bump_version_major(self):
        result = bump_version("1.0.0", SemverBump.MAJOR)
        self.assertEqual(result, "2.0.0")

    def test_bump_version_major_with_prefix(self):
        result = bump_version("v1.0.0", SemverBump.MAJOR)
        self.assertEqual(result, "v2.0.0")


class TestSemverClassifierSafe(unittest.TestCase):
    """Semver classifier returns MINOR for additive-only changes."""

    def setUp(self):
        engine = OpenAPIDiffEngine()
        self.changes = engine.compare(V1, V2_SAFE)

    def test_classify_minor(self):
        bump = classify(self.changes)
        self.assertEqual(bump, SemverBump.MINOR)

    def test_detailed_not_breaking(self):
        detail = classify_detailed(self.changes)
        self.assertFalse(detail["is_breaking"])
        self.assertEqual(detail["bump"], "minor")

    def test_bump_version_minor(self):
        result = bump_version("1.0.0", SemverBump.MINOR)
        self.assertEqual(result, "1.1.0")


class TestSemverClassifierNone(unittest.TestCase):
    """Semver classifier returns NONE for empty change list."""

    def test_no_changes(self):
        self.assertEqual(classify([]), SemverBump.NONE)

    def test_bump_version_none(self):
        self.assertEqual(bump_version("1.2.3", SemverBump.NONE), "1.2.3")


# ===================================================================
# Explainer Tests
# ===================================================================

class TestExplainerTemplates(unittest.TestCase):
    """All 7 explainer templates produce non-empty output."""

    def setUp(self):
        engine = OpenAPIDiffEngine()
        self.breaking_changes = engine.compare(V1, V2_BREAKING)
        self.safe_changes = engine.compare(V1, V2_SAFE)

    def test_all_templates_exist(self):
        self.assertEqual(len(TEMPLATES), 7)

    def test_all_templates_nonempty_breaking(self):
        for template in TEMPLATES:
            output = explain(
                self.breaking_changes,
                template=template,
                old_version="1.0.0",
                new_version="2.0.0",
                api_name="User Service",
            )
            self.assertTrue(
                len(output.strip()) > 0,
                f"Template '{template}' produced empty output for breaking changes",
            )

    def test_all_templates_nonempty_safe(self):
        for template in TEMPLATES:
            output = explain(
                self.safe_changes,
                template=template,
                old_version="1.0.0",
                new_version="1.1.0",
                api_name="User Service",
            )
            self.assertTrue(
                len(output.strip()) > 0,
                f"Template '{template}' produced empty output for safe changes",
            )

    def test_explain_all_returns_seven(self):
        result = explain_all(self.breaking_changes)
        self.assertEqual(len(result), 7)
        for name, text in result.items():
            self.assertIn(name, TEMPLATES)
            self.assertTrue(len(text.strip()) > 0)

    def test_developer_template_has_breaking_section(self):
        output = explain(self.breaking_changes, template="developer")
        self.assertIn("Breaking Changes", output)

    def test_migration_template_has_steps(self):
        output = explain(self.breaking_changes, template="migration")
        self.assertIn("Step 1", output)
        self.assertIn("Migration Guide", output)

    def test_pr_comment_has_table(self):
        output = explain(self.breaking_changes, template="pr_comment")
        self.assertIn("| Change | Location | Severity |", output)
        self.assertIn("MAJOR", output)
        self.assertIn("Migration guide", output)

    def test_slack_has_icon(self):
        output = explain(self.breaking_changes, template="slack")
        self.assertIn(":red_circle:", output)

    def test_unknown_template_message(self):
        output = explain(self.breaking_changes, template="nonexistent")
        self.assertIn("Unknown template", output)


# ===================================================================
# CI Formatter Tests
# ===================================================================

class TestCIFormatterMarkdown(unittest.TestCase):
    """CIFormatter markdown output contains expected sections."""

    def setUp(self):
        self.result_breaking = evaluate_with_policy(V1, V2_BREAKING)
        self.result_safe = evaluate_with_policy(V1, V2_SAFE)

    def test_markdown_breaking_has_header(self):
        formatter = CIFormatter(OutputFormat.MARKDOWN)
        output = formatter.format_result(self.result_breaking)
        self.assertIn("Delimit", output)
        self.assertIn("Breaking", output)

    def test_markdown_breaking_has_table(self):
        formatter = CIFormatter(OutputFormat.MARKDOWN)
        output = formatter.format_result(self.result_breaking)
        self.assertIn("| Metric | Value |", output)
        self.assertIn("Total changes", output)

    def test_markdown_breaking_has_violations(self):
        formatter = CIFormatter(OutputFormat.MARKDOWN)
        output = formatter.format_result(self.result_breaking)
        self.assertIn("Violations", output)

    def test_markdown_breaking_has_footer(self):
        formatter = CIFormatter(OutputFormat.MARKDOWN)
        output = formatter.format_result(self.result_breaking)
        self.assertIn("ESLint for API contracts", output)

    def test_markdown_safe_has_good_header(self):
        formatter = CIFormatter(OutputFormat.MARKDOWN)
        output = formatter.format_result(self.result_safe)
        self.assertIn("Look Good", output)

    def test_text_format(self):
        formatter = CIFormatter(OutputFormat.TEXT)
        output = formatter.format_result(self.result_breaking)
        self.assertIn("Failed", output)
        self.assertIn("Breaking Changes", output)

    def test_json_format(self):
        formatter = CIFormatter(OutputFormat.JSON)
        output = formatter.format_result(self.result_breaking)
        import json
        parsed = json.loads(output)
        self.assertIn("decision", parsed)

    def test_github_annotations(self):
        formatter = CIFormatter(OutputFormat.GITHUB_ANNOTATION)
        output = formatter.format_result(self.result_breaking)
        self.assertIn("::", output)

    def test_format_for_ci_github(self):
        output = format_for_ci(self.result_breaking, ci_environment="github")
        self.assertTrue(len(output) > 0)

    def test_format_for_ci_pr_comment(self):
        output = format_for_ci(self.result_breaking, ci_environment="pr_comment")
        self.assertIn("Delimit", output)


# ===================================================================
# Integration: full pipeline
# ===================================================================

class TestFullPipeline(unittest.TestCase):
    """End-to-end: diff -> policy -> semver -> explainer -> formatter."""

    def test_breaking_pipeline(self):
        # Diff
        engine = OpenAPIDiffEngine()
        changes = engine.compare(V1, V2_BREAKING)
        self.assertGreater(len(changes), 0)

        # Policy
        result = evaluate_with_policy(V1, V2_BREAKING)
        self.assertEqual(result["decision"], "fail")

        # Semver
        bump = classify(changes)
        self.assertEqual(bump, SemverBump.MAJOR)
        next_ver = bump_version("1.0.0", bump)
        self.assertEqual(next_ver, "2.0.0")

        # Explainer
        for t in TEMPLATES:
            self.assertTrue(len(explain(changes, template=t)) > 0)

        # Formatter
        formatter = CIFormatter(OutputFormat.MARKDOWN)
        md = formatter.format_result(result)
        self.assertIn("Breaking", md)

    def test_safe_pipeline(self):
        engine = OpenAPIDiffEngine()
        changes = engine.compare(V1, V2_SAFE)
        breaking = [c for c in changes if c.is_breaking]
        self.assertEqual(len(breaking), 0)

        result = evaluate_with_policy(V1, V2_SAFE)
        self.assertEqual(result["decision"], "pass")

        bump = classify(changes)
        self.assertEqual(bump, SemverBump.MINOR)


if __name__ == "__main__":
    unittest.main()
