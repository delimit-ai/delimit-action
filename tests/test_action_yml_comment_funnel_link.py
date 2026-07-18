"""Conversion-funnel wiring: the PR comment (the only touch a third-party dev
sees) must route to the public worked-example reports, and the attestation
permalink must carry an ``src=action-comment`` attribution tag.

Background: the attestation permalink previously carried repo/pr/commit/rekor
but no ``src`` param, so the delimit.ai footer's ``inbound_src='action-comment'``
attribution path had no producer. Likewise the PR-comment body linked nowhere
public. This test locks in both fixes so the measured leak does not regress.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


ACTION_YML = Path(__file__).resolve().parent.parent / "action.yml"


@pytest.fixture(scope="module")
def steps() -> list:
    data = yaml.safe_load(ACTION_YML.read_text(encoding="utf-8"))
    return data["runs"]["steps"]


@pytest.fixture(scope="module")
def comment_step_script(steps) -> str:
    comment_step = next(s for s in steps if s.get("name") == "Comment on PR")
    return comment_step["with"]["script"]


@pytest.fixture(scope="module")
def sign_step_run(steps) -> str:
    sign_step = next(s for s in steps if s.get("name", "").startswith("Sign attestation"))
    return sign_step["run"]


class TestAttestationPermalinkAttribution:
    def test_permalink_carries_src_action_comment(self, sign_step_run):
        # Without this the footer's inbound_src='action-comment' path has no producer.
        assert "src=action-comment" in sign_step_run

    def test_permalink_still_carries_thread_context(self, sign_step_run):
        # Attribution must be additive, not a replacement of existing context.
        for key in ("rekor=", "repo=", "commit=", "att/"):
            assert key in sign_step_run


class TestCommentBodyReportsLink:
    def test_reports_link_present(self, comment_step_script):
        assert "https://delimit.ai/reports" in comment_step_script

    def test_reports_link_tagged_for_attribution(self, comment_step_script):
        assert "src=action-comment" in comment_step_script

    def test_reports_link_in_both_renderers(self, comment_step_script):
        # One for the JSON Schema comment path, one for the OpenAPI path.
        assert comment_step_script.count("delimit.ai/reports?src=action-comment") >= 2
