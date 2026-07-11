"""Mute-surface fix: fork-PR comment-403 falls back to $GITHUB_STEP_SUMMARY.

Background (Fable outreach review doc 27): delimit-action is installed and
green on goharbor/harbor (24k stars) and container-registry/harbor-next, but
harbor PRs come from forks. GitHub issues fork PRs a READ-ONLY GITHUB_TOKEN,
so github.rest.issues.createComment 403s regardless of the workflow's
`permissions:` block. The old handler misdiagnosed this (told users to add a
permissions block that cannot fix a fork-token downgrade) and had no fallback,
so the working install produced ZERO contributor-visible output.

The fix:
  1. On comment-post 403, write the same report to $GITHUB_STEP_SUMMARY
     (always writable, even on fork PRs).
  2. Correct the warning text to explain the fork read-only-token cause and
     point at pull_request_target (with its security caveat), not a
     permissions block.

Two layers of assertion:
  * TestForkSummaryStatic — parses action.yml and asserts the fallback + the
    corrected message are wired into the script source.
  * TestForkSummaryExecuted — actually EXECUTES the embedded github-script JS
    under Node with a mock `github` that throws a 403, proving the summary
    fallback fires and the fork warning is emitted. Skipped if node is absent.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
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


class TestForkSummaryStatic:
    def test_summary_fallback_helper_present(self, comment_step_script):
        # The fallback must target the always-writable job summary.
        assert "GITHUB_STEP_SUMMARY" in comment_step_script
        assert "core.summary" in comment_step_script

    def test_both_paths_use_the_fallback(self, comment_step_script):
        # JSON Schema renderer + OpenAPI renderer both route their 403 to the
        # shared warnCommentBlocked helper.
        assert comment_step_script.count("warnCommentBlocked(body") >= 2

    def test_fork_detection_present(self, comment_step_script):
        assert "detectForkPR" in comment_step_script
        assert "head.repo" in comment_step_script
        assert "base.repo" in comment_step_script

    def test_corrected_message_names_fork_readonly_cause(self, comment_step_script):
        low = comment_step_script.lower()
        assert "read-only" in low
        assert "fork" in low
        # Must point at pull_request_target as the (caveated) path to comments.
        assert "pull_request_target" in comment_step_script
        # Must not blindly recommend it — security caveat required.
        assert "security" in low

    def test_still_keeps_permissions_hint_for_nonfork(self, comment_step_script):
        # Same-repo 403s are still genuinely a missing-permissions problem.
        assert "pull-requests: write" in comment_step_script

    def test_deprecated_pins_refreshed(self):
        text = ACTION_YML.read_text(encoding="utf-8")
        assert "actions/setup-python@v4" not in text
        assert "actions/github-script@v6" not in text
        assert "actions/setup-python@v5" in text
        assert "actions/github-script@v7" in text


# ---------------------------------------------------------------------------
# Execution test: run the embedded github-script JS under Node with a mock
# `github` client that throws a 403, and assert the summary fallback fires.
# ---------------------------------------------------------------------------

NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs');

const script = process.argv[2];
const reportPath = process.argv[3];
const summaryPath = process.argv[4];
const scenario = process.argv[5]; // "fork" | "samerepo"

// Mock github: any REST issues call throws a 403 (fork read-only token).
const forbidden = () => { const e = new Error('Resource not accessible by integration'); e.status = 403; throw e; };
const github = {
  rest: {
    issues: {
      listComments: async () => forbidden(),
      createComment: async () => forbidden(),
      updateComment: async () => forbidden(),
    },
  },
};

// Mock @actions/core summary + warning capture.
const warnings = [];
let summaryBuf = '';
const core = {
  warning: (m) => { warnings.push(String(m)); },
  summary: {
    addRaw: function (s) { summaryBuf += s; return this; },
    write: async function () { fs.appendFileSync(summaryPath, summaryBuf); summaryBuf = ''; return this; },
  },
};

const base = { repo: { full_name: 'goharbor/harbor' } };
const head = scenario === 'fork'
  ? { repo: { full_name: 'contributor/harbor', fork: true } }
  : { repo: { full_name: 'goharbor/harbor', fork: false } };

const context = {
  repo: { owner: 'goharbor', repo: 'harbor' },
  issue: { number: 42 },
  payload: { pull_request: { number: 42, head, base } },
};

process.env.GITHUB_STEP_SUMMARY = summaryPath;

const src = fs.readFileSync(script, 'utf8');
const runner = new Function('github', 'core', 'context', 'require', 'process',
  'return (async () => {\n' + src + '\n})();');

runner(github, core, context, require, process)
  .then(() => {
    console.log(JSON.stringify({ ok: true, warnings, summary: fs.existsSync(summaryPath) ? fs.readFileSync(summaryPath, 'utf8') : '' }));
  })
  .catch((e) => {
    console.log(JSON.stringify({ ok: false, error: String(e && e.stack || e), warnings }));
    process.exit(3);
  });
"""


def _extract_openapi_script() -> str:
    data = yaml.safe_load(ACTION_YML.read_text(encoding="utf-8"))
    steps = data["runs"]["steps"]
    return next(s for s in steps if s.get("name") == "Comment on PR")["with"]["script"]


def _run_scenario(tmp: Path, scenario: str, report: dict) -> dict:
    script_js = tmp / "script.js"
    script_js.write_text(_extract_openapi_script(), encoding="utf-8")

    harness_js = tmp / "harness.js"
    harness_js.write_text(HARNESS, encoding="utf-8")

    report_path = Path("/tmp/delimit_report.json")
    report_path.write_text(json.dumps(report), encoding="utf-8")

    summary_path = tmp / "step_summary.md"
    summary_path.write_text("", encoding="utf-8")

    proc = subprocess.run(
        [NODE, str(harness_js), str(script_js), str(report_path), str(summary_path), scenario],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"harness failed: {proc.stdout}\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(NODE is None, reason="node not available to execute github-script JS")
class TestForkSummaryExecuted:
    REPORT = {
        "spec_type": "openapi",
        "semver": {"bump": "major", "next_version": "2.0.0"},
        "summary": {"breaking_changes": 1, "total_changes": 2},
        "decision": "fail",
        "violations": [],
        "all_changes": [
            {"path": "/pets", "message": "endpoint removed", "type": "endpoint_removed", "is_breaking": True},
            {"path": "/pets", "message": "field added", "type": "field_added", "is_breaking": False},
        ],
        "migration": "",
        "drift": None,
    }

    def test_fork_403_writes_summary_and_warns_about_fork(self, tmp_path):
        res = _run_scenario(tmp_path, "fork", self.REPORT)
        assert res["ok"], res
        # Report body landed in the job summary despite the 403.
        assert "Breaking API Changes Detected" in res["summary"]
        assert "endpoint removed" in res["summary"]
        # The warning correctly diagnoses the fork read-only token.
        joined = " ".join(res["warnings"]).lower()
        assert "fork" in joined
        assert "read-only" in joined
        assert "pull_request_target" in joined
        # And it must NOT claim a permissions block would fix a fork 403.
        assert "cannot override the fork-token downgrade" in " ".join(res["warnings"])

    def test_samerepo_403_still_gives_permissions_hint(self, tmp_path):
        res = _run_scenario(tmp_path, "samerepo", self.REPORT)
        assert res["ok"], res
        assert "Breaking API Changes Detected" in res["summary"]
        joined = " ".join(res["warnings"])
        assert "pull-requests: write" in joined
