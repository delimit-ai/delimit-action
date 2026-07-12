"""LED-1865: no ``actions/github-script`` step may interpolate ``${{ }}`` in its script.

Incident (LED-1865): the mute-surface fix enlarged the "Comment on PR"
``actions/github-script`` block to ~479 lines while it still contained one
inline expression — ``const mode = '${{ inputs.mode }}';``. GitHub treats ANY
``script:`` value that contains a ``${{ }}`` expression as a single template
expression and evaluates the WHOLE block before the step runs. Once the block
grew past GitHub's max expression length the action failed to parse with
``The template is not valid ... Exceeded max expression length`` — but only on
``pull_request`` events, because the step is guarded by
``github.event_name == 'pull_request'``. Push-to-main self-tests skipped the
step, so neither the self-test nor a plain ``yaml.safe_load`` caught it, and the
break shipped to ``@v1``.

The fix is to source runtime values from ``process.env`` (populated via the
step's ``env:`` block) instead of inline ``${{ }}`` interpolation. This test is
the deterministic guard for the whole class: it fails if ANY
``actions/github-script`` step's ``script`` contains a ``${{ }}`` expression.
``run:`` shell/python blocks are intentionally NOT checked — inline
interpolation there is safe; only ``github-script`` ``script`` inputs are the
template-evaluation hazard.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml


ACTION_YML = Path(__file__).resolve().parent.parent / "action.yml"

# Matches a GitHub Actions template expression: ${{ ... }}
INTERPOLATION_RE = re.compile(r"\$\{\{.*?\}\}", re.DOTALL)


def _github_script_steps():
    """Yield (index, name, script) for every actions/github-script step."""
    data = yaml.safe_load(ACTION_YML.read_text(encoding="utf-8"))
    steps = data["runs"]["steps"]
    for i, step in enumerate(steps):
        uses = step.get("uses", "") or ""
        if uses.startswith("actions/github-script@"):
            script = (step.get("with") or {}).get("script", "")
            yield i, step.get("name", f"<step {i}>"), script


class TestLed1865GithubScriptNoInterpolation:
    def test_at_least_one_github_script_step_exists(self):
        # Guard the guard: if github-script is ever removed this test should be
        # revisited rather than silently passing on zero steps.
        assert list(_github_script_steps()), (
            "expected at least one actions/github-script step in action.yml; "
            "if github-script was removed, update this LED-1865 lint"
        )

    def test_no_interpolation_in_any_github_script_block(self):
        offenders = []
        for _, name, script in _github_script_steps():
            for m in INTERPOLATION_RE.finditer(script):
                line = script[: m.start()].count("\n") + 1
                offenders.append((name, line, m.group(0)))
        assert not offenders, (
            "LED-1865: actions/github-script `script:` blocks must not contain "
            "`${{ }}` expressions (GitHub evaluates the whole block as one "
            "template; a large block exceeds max expression length and breaks "
            "the action on pull_request events). Move each value to the step's "
            "`env:` block and read it via process.env. Offenders "
            "(step, line-within-script, expr): " + repr(offenders)
        )

    def test_comment_on_pr_mode_sourced_from_env(self):
        # Regression pin for the exact incident line.
        data = yaml.safe_load(ACTION_YML.read_text(encoding="utf-8"))
        steps = data["runs"]["steps"]
        step = next(s for s in steps if s.get("name") == "Comment on PR")
        script = step["with"]["script"]
        env = step.get("env") or {}
        assert "DELIMIT_MODE" in env, "Comment on PR step must expose inputs.mode via env DELIMIT_MODE"
        assert "process.env.DELIMIT_MODE" in script, (
            "mode must be read from process.env.DELIMIT_MODE, not inline ${{ inputs.mode }}"
        )
