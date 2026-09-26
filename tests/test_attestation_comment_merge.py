"""Exercise the JavaScript helper used by both PR comment renderers."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


NODE = shutil.which("node")
HELPER = Path(__file__).resolve().parents[1] / "scripts/merge_attestation_footer.js"
ACTION = Path(__file__).resolve().parents[1] / "action.yml"
RUN = "https://github.com/example/private/actions/runs/123"
BLOCK = (
    "### 🔏 Signed attestation\n\n"
    "- **ID:** `abc123`\n"
    f"- **Workflow run:** [runs/123]({RUN})\n\n"
)


def merge(new, previous):
    script = (
        "const {mergeUnsignedAttestation} = require(process.argv[1]);"
        "const [newBody, oldBody] = JSON.parse(process.argv[2]);"
        "process.stdout.write(mergeUnsignedAttestation(newBody, oldBody));"
    )
    return subprocess.check_output(
        [NODE, "-e", script, str(HELPER), json.dumps([new, previous])], text=True
    )


@pytest.mark.skipif(NODE is None, reason="node is required for the comment helper")
def test_unsigned_update_preserves_prior_signed_block_and_run():
    old = "Old verdict\n\n" + BLOCK + "---\nPowered by Delimit"
    new = "New verdict\n\n---\nPowered by Delimit"
    result = merge(new, old)
    assert result.startswith("New verdict")
    assert BLOCK in result
    assert f"This run was not signed (see notice); the attestation above belongs to run {RUN}" in result
    assert result.count("### 🔏 Signed attestation") == 1
    assert result.index("### 🔏 Signed attestation") < result.index("---")


@pytest.mark.skipif(NODE is None, reason="node is required for the comment helper")
def test_repeated_unsigned_update_does_not_accumulate_notes():
    old = "Old verdict\n\n" + BLOCK + "---\nPowered by Delimit"
    current = merge("First unsigned\n\n---\nPowered by Delimit", old)
    result = merge("Second unsigned\n\n---\nPowered by Delimit", current)
    assert result.count("This run was not signed") == 1
    assert result.count(BLOCK) == 1


@pytest.mark.skipif(NODE is None, reason="node is required for the comment helper")
def test_no_prior_signature_and_new_signature_are_unchanged():
    unsigned = "New verdict\n\n---\nPowered by Delimit"
    signed = "New verdict\n\n" + BLOCK + "---\nPowered by Delimit"
    assert merge(unsigned, "Old unsigned") == unsigned
    assert merge(signed, "Old verdict\n\n" + BLOCK) == signed


def test_both_comment_renderers_use_merge_on_existing_comments():
    action = ACTION.read_text()
    assert action.count("body: attId ? body : mergeUnsignedAttestation(body, existing.body)") == 2
