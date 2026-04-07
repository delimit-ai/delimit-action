"""Tests for core/generator_drift.py (LED-713).

Covers the end-to-end drift check, shell-injection guards, and
workspace restoration after drift detection.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.generator_drift import detect_drift, format_drift_report


@pytest.fixture
def repo_with_artifact():
    """Temporary repo with a committed JSON Schema artifact."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifact = root / "schema.json"
        artifact.write_text(json.dumps({"type": "object", "properties": {"a": {"type": "string"}}}))
        yield root, artifact


# ----------------------------------------------------------------------
# injection guards (LED-713 security fix)
# ----------------------------------------------------------------------

class TestInjectionGuards:
    def test_shell_chain_blocked(self, repo_with_artifact):
        root, _ = repo_with_artifact
        result = detect_drift(str(root), "schema.json", "echo hi && cat /etc/passwd")
        assert "shell metacharacters" in (result.error or "")
        assert not result.drifted

    def test_pipe_blocked(self, repo_with_artifact):
        root, _ = repo_with_artifact
        result = detect_drift(str(root), "schema.json", "cat schema.json | grep x")
        assert "shell metacharacters" in (result.error or "")

    def test_redirect_blocked(self, repo_with_artifact):
        root, _ = repo_with_artifact
        result = detect_drift(str(root), "schema.json", "echo x > out.txt")
        assert "shell metacharacters" in (result.error or "")

    def test_backtick_blocked(self, repo_with_artifact):
        root, _ = repo_with_artifact
        result = detect_drift(str(root), "schema.json", "echo `whoami`")
        assert "shell metacharacters" in (result.error or "")

    def test_dollar_substitution_blocked(self, repo_with_artifact):
        root, _ = repo_with_artifact
        result = detect_drift(str(root), "schema.json", "echo $(whoami)")
        assert "shell metacharacters" in (result.error or "")

    def test_semicolon_blocked(self, repo_with_artifact):
        root, _ = repo_with_artifact
        result = detect_drift(str(root), "schema.json", "cmd1 ; cmd2")
        assert "shell metacharacters" in (result.error or "")

    def test_empty_command_rejected(self, repo_with_artifact):
        root, _ = repo_with_artifact
        result = detect_drift(str(root), "schema.json", "")
        assert "empty" in (result.error or "").lower()

    def test_unparseable_command_rejected(self, repo_with_artifact):
        root, _ = repo_with_artifact
        # Unterminated quote breaks shlex
        result = detect_drift(str(root), "schema.json", "echo 'unterminated")
        assert "parse" in (result.error or "").lower()


# ----------------------------------------------------------------------
# happy path — valid commands that should run
# ----------------------------------------------------------------------

class TestHappyPath:
    def test_simple_command_no_drift(self, repo_with_artifact):
        """`true` exits 0 without modifying anything — no drift."""
        root, _ = repo_with_artifact
        result = detect_drift(str(root), "schema.json", "true")
        assert result.error is None
        assert not result.drifted

    def test_drift_detected_when_generator_modifies_artifact(self, repo_with_artifact):
        """Simulate a generator that writes a different schema."""
        root, artifact = repo_with_artifact
        script = root / "regen.py"
        script.write_text(
            f"import json\n"
            f"with open({str(artifact)!r}, 'w') as f:\n"
            f"    json.dump({{'type': 'object', 'properties': {{'a': {{'type': 'integer'}}}}}}, f)\n"
        )
        result = detect_drift(str(root), "schema.json", f"python3 {script.name}")
        assert result.error is None
        assert result.drifted
        assert len(result.changes) >= 1
        # Verify artifact was restored to its committed state
        restored = json.loads(artifact.read_text())
        assert restored["properties"]["a"]["type"] == "string"

    def test_workspace_restored_after_drift(self, repo_with_artifact):
        """The committed file must be restored even when drift is detected."""
        root, artifact = repo_with_artifact
        original_text = artifact.read_text()
        script = root / "regen.py"
        script.write_text(
            f"with open({str(artifact)!r}, 'w') as f: f.write('{{\"different\": true}}')\n"
        )
        detect_drift(str(root), "schema.json", f"python3 {script.name}")
        assert artifact.read_text() == original_text


# ----------------------------------------------------------------------
# error handling
# ----------------------------------------------------------------------

class TestErrorHandling:
    def test_missing_artifact(self, repo_with_artifact):
        root, _ = repo_with_artifact
        result = detect_drift(str(root), "nonexistent.json", "true")
        assert "not found" in (result.error or "").lower()

    def test_missing_executable(self, repo_with_artifact):
        root, _ = repo_with_artifact
        result = detect_drift(str(root), "schema.json", "nonexistent_binary_xyz_12345")
        assert "not found" in (result.error or "").lower()

    def test_generator_exit_code_propagated(self, repo_with_artifact):
        root, _ = repo_with_artifact
        result = detect_drift(str(root), "schema.json", "false")
        assert "exited" in (result.error or "").lower()

    def test_timeout(self, repo_with_artifact):
        root, _ = repo_with_artifact
        # sleep longer than the timeout
        result = detect_drift(str(root), "schema.json", "sleep 3", timeout_seconds=1)
        assert "timed out" in (result.error or "").lower()


# ----------------------------------------------------------------------
# report formatter
# ----------------------------------------------------------------------

class TestFormatter:
    def test_clean_report(self, repo_with_artifact):
        root, _ = repo_with_artifact
        result = detect_drift(str(root), "schema.json", "true")
        report = format_drift_report(result)
        assert "clean" in report.lower()
        assert "schema.json" in report

    def test_error_report(self, repo_with_artifact):
        root, _ = repo_with_artifact
        result = detect_drift(str(root), "schema.json", "echo foo && bar")
        report = format_drift_report(result)
        assert "error" in report.lower() or "metacharacter" in report.lower()
