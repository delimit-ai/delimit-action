"""LED-807: action.yml github-script comment-post must catch 403 cleanly.

Background: external maintainers running delimit-action without
`permissions: pull-requests: write` would see the whole job fail RED on a
green analysis because the github-script step propagated the 403 from
createComment/updateComment.

This test asserts that action.yml wraps both comment-post code paths
(JSON Schema and OpenAPI) in try/catch with an explicit 403 branch that
logs a permissions warning and does not rethrow.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


ACTION_YML = Path(__file__).resolve().parent.parent / "action.yml"


@pytest.fixture(scope="module")
def comment_step_script() -> str:
    data = yaml.safe_load(ACTION_YML.read_text(encoding="utf-8"))
    steps = data["runs"]["steps"]
    comment_step = next(s for s in steps if s.get("name") == "Comment on PR")
    return comment_step["with"]["script"]


class TestLed807Comment403Catch:
    def test_marker_present(self, comment_step_script):
        assert "LED-807" in comment_step_script

    def test_two_try_blocks(self, comment_step_script):
        # One for JSON Schema renderer, one for OpenAPI renderer
        assert comment_step_script.count("try {") >= 2

    def test_403_branch_present_in_both_paths(self, comment_step_script):
        assert comment_step_script.count("err.status === 403") >= 2

    def test_permission_warning_message(self, comment_step_script):
        # Hard requirement: the warning must name the missing permission
        # so external users get an actionable fix.
        assert "pull-requests: write" in comment_step_script
        assert "permissions" in comment_step_script.lower()

    def test_uses_core_warning_not_throw(self, comment_step_script):
        assert comment_step_script.count("core.warning") >= 2

    def test_non_403_errors_still_rethrow(self, comment_step_script):
        # Each try/catch must preserve the original throw for non-403 errors
        assert comment_step_script.count("throw err") >= 2

    def test_does_not_call_process_exit_in_catch(self, comment_step_script):
        # Final pass/fail is owned by the "Fail on breaking changes" step.
        # Comment posting should never call process.exit / core.setFailed.
        assert "process.exit(1)" not in comment_step_script
        assert "core.setFailed" not in comment_step_script

    def test_comment_step_runs_with_always_guard(self):
        data = yaml.safe_load(ACTION_YML.read_text(encoding="utf-8"))
        steps = data["runs"]["steps"]
        comment_step = next(s for s in steps if s.get("name") == "Comment on PR")
        # always() guard ensures the comment posts even when an earlier step
        # marks failure — the catch protects this from cascading.
        assert "always()" in comment_step["if"]


class TestLed807FailOnBreakingStepUnchanged:
    """The dedicated 'Fail on breaking changes' step is the only place that
    should fail the job. The 403 fix must not have altered its semantics."""

    def test_fail_step_still_present_with_correct_guard(self):
        data = yaml.safe_load(ACTION_YML.read_text(encoding="utf-8"))
        steps = data["runs"]["steps"]
        fail_step = next(
            (
                s
                for s in steps
                if "breaking" in (s.get("name") or "").lower()
                and "enforce" in (s.get("name") or "").lower()
            ),
            None,
        )
        assert fail_step is not None
        guard = fail_step["if"]
        # Must guard on (mode=enforce OR fail_on_breaking=true) AND breaking_changes=true
        assert "enforce" in guard
        assert "fail_on_breaking" in guard
        assert "breaking_changes" in guard
        # Must still actually exit 1
        assert "exit 1" in fail_step["run"]
