"""LED-1600: request/response-context-aware severity classification.

The merge gate's worst failure mode is silently under-classifying a breaking
change as non-breaking. Before LED-1600 the engine treated field add/remove
uniformly regardless of whether the field lived in a REQUEST schema
(requestBody / in:body) or a RESPONSE schema (responses[].content). The
breaking direction flips:

  REQUEST  : adding a NEW REQUIRED field is breaking (clients must send it);
             making an optional field required is breaking; removing a field
             is non-breaking (server stops requiring it).
  RESPONSE : removing a field is breaking (consumers lose it); making a
             required field optional is breaking (consumers can no longer rely
             on it); adding a field is non-breaking.

Each test here would have been mis-ranked before LED-1600.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.diff_engine_v2 import OpenAPIDiffEngine, ChangeType
from core.semver_classifier import classify, SemverBump


# ── spec builders ────────────────────────────────────────────────────

def _resp_spec(props, required=None):
    return {
        "openapi": "3.0.3",
        "info": {"title": "t", "version": "1"},
        "paths": {
            "/items": {"get": {
                "responses": {"200": {
                    "description": "ok",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": props,
                        **({"required": required} if required is not None else {}),
                    }}},
                }},
            }},
        },
    }


def _req_spec(props, required=None):
    return {
        "openapi": "3.0.3",
        "info": {"title": "t", "version": "1"},
        "paths": {
            "/items": {"post": {
                "requestBody": {"content": {"application/json": {"schema": {
                    "type": "object",
                    "properties": props,
                    **({"required": required} if required is not None else {}),
                }}}},
                "responses": {"200": {"description": "ok"}},
            }},
        },
    }


def _diff(old, new):
    return OpenAPIDiffEngine().compare(old, new)


def _find(changes, ct, name):
    return [c for c in changes if c.type == ct and c.path.endswith(f".{name}")]


# ── RESPONSE: removing an OPTIONAL field is breaking ─────────────────
# This is the headline silent-leak case (the TED NoticeResponse.sme-part
# class): an optional response field disappearing IS breaking for consumers,
# but a context-blind engine could bucket it low/non-breaking.

class TestResponseOptionalFieldRemoval:
    def test_optional_response_field_removal_is_breaking(self):
        old = _resp_spec({"id": {"type": "string"}, "extra": {"type": "string"}})
        new = _resp_spec({"id": {"type": "string"}})
        changes = _diff(old, new)
        removed = _find(changes, ChangeType.FIELD_REMOVED, "extra")
        assert len(removed) == 1
        c = removed[0]
        assert c.context == "response"
        assert c.is_breaking is True
        assert c.severity == "high"
        assert classify(changes) == SemverBump.MAJOR

    def test_required_response_field_removal_is_breaking(self):
        old = _resp_spec({"id": {"type": "string"}}, required=["id"])
        new = _resp_spec({})
        changes = _diff(old, new)
        removed = _find(changes, ChangeType.FIELD_REMOVED, "id")
        assert removed and removed[0].is_breaking is True
        assert removed[0].severity == "high"


# ── REQUEST: removing a field is NON-breaking ────────────────────────

class TestRequestFieldRemoval:
    def test_request_field_removal_is_not_breaking(self):
        old = _req_spec({"id": {"type": "string"}, "extra": {"type": "string"}})
        new = _req_spec({"id": {"type": "string"}})
        changes = _diff(old, new)
        removed = _find(changes, ChangeType.FIELD_REMOVED, "extra")
        assert len(removed) == 1
        c = removed[0]
        assert c.context == "request"
        assert c.is_breaking is False
        assert c.severity == "low"
        # No breaking change in the whole diff.
        assert classify(changes) != SemverBump.MAJOR


# ── REQUEST: adding a NEW REQUIRED field is breaking ─────────────────

class TestRequestRequiredFieldAdd:
    def test_request_required_field_add_is_breaking(self):
        old = _req_spec({"id": {"type": "string"}}, required=["id"])
        new = _req_spec(
            {"id": {"type": "string"}, "token": {"type": "string"}},
            required=["id", "token"],
        )
        changes = _diff(old, new)
        added = _find(changes, ChangeType.REQUIRED_FIELD_ADDED, "token")
        assert len(added) == 1
        c = added[0]
        assert c.context == "request"
        assert c.is_breaking is True
        assert c.severity == "high"
        assert classify(changes) == SemverBump.MAJOR


# ── RESPONSE: adding a NEW REQUIRED field is NON-breaking ────────────

class TestResponseRequiredFieldAdd:
    def test_response_required_field_add_is_not_breaking(self):
        old = _resp_spec({"id": {"type": "string"}}, required=["id"])
        new = _resp_spec(
            {"id": {"type": "string"}, "added": {"type": "string"}},
            required=["id", "added"],
        )
        changes = _diff(old, new)
        added = _find(changes, ChangeType.REQUIRED_FIELD_ADDED, "added")
        assert len(added) == 1
        c = added[0]
        assert c.context == "response"
        assert c.is_breaking is False
        assert c.severity == "low"
        assert classify(changes) != SemverBump.MAJOR


# ── RESPONSE: making a REQUIRED field OPTIONAL is breaking ───────────
# Before LED-1600 this was NOT DETECTED AT ALL (no code path looked at
# old_required - new_required). The purest silent leak.

class TestResponseRequirementRelaxed:
    def test_required_to_optional_in_response_is_breaking(self):
        old = _resp_spec({"id": {"type": "string"}}, required=["id"])
        new = _resp_spec({"id": {"type": "string"}}, required=[])
        changes = _diff(old, new)
        relaxed = _find(changes, ChangeType.FIELD_REQUIREMENT_RELAXED, "id")
        assert len(relaxed) == 1, "required->optional in response must be detected"
        c = relaxed[0]
        assert c.context == "response"
        assert c.is_breaking is True
        assert c.severity == "high"
        assert classify(changes) == SemverBump.MAJOR

    def test_required_to_optional_in_request_is_not_breaking(self):
        old = _req_spec({"id": {"type": "string"}}, required=["id"])
        new = _req_spec({"id": {"type": "string"}}, required=[])
        changes = _diff(old, new)
        relaxed = _find(changes, ChangeType.FIELD_REQUIREMENT_RELAXED, "id")
        assert len(relaxed) == 1
        c = relaxed[0]
        assert c.context == "request"
        assert c.is_breaking is False
        assert c.severity == "low"


# ── REQUEST: making an OPTIONAL field REQUIRED is breaking ───────────

class TestRequestRequirementTightened:
    def test_optional_to_required_in_request_is_breaking(self):
        old = _req_spec({"id": {"type": "string"}}, required=[])
        new = _req_spec({"id": {"type": "string"}}, required=["id"])
        changes = _diff(old, new)
        tightened = [
            c for c in changes
            if c.type == ChangeType.REQUIRED_FIELD_ADDED
            and c.path.endswith(".id")
            and c.details.get("was_optional")
        ]
        assert len(tightened) == 1, "optional->required on existing request field must be flagged"
        c = tightened[0]
        assert c.context == "request"
        assert c.is_breaking is True
        assert c.severity == "high"
        assert classify(changes) == SemverBump.MAJOR

    def test_optional_to_required_in_response_is_not_breaking(self):
        old = _resp_spec({"id": {"type": "string"}}, required=[])
        new = _resp_spec({"id": {"type": "string"}}, required=["id"])
        changes = _diff(old, new)
        tightened = [
            c for c in changes
            if c.type == ChangeType.REQUIRED_FIELD_ADDED
            and c.path.endswith(".id")
            and c.details.get("was_optional")
        ]
        assert len(tightened) == 1
        assert tightened[0].is_breaking is False


# ── Context-unknown (component schema) stays conservatively breaking ─

class TestComponentSchemaConservative:
    def test_component_field_removal_is_breaking_without_context(self):
        old = {
            "openapi": "3.0.3", "info": {"title": "t", "version": "1"}, "paths": {},
            "components": {"schemas": {"U": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "extra": {"type": "string"}},
            }}},
        }
        new = {
            "openapi": "3.0.3", "info": {"title": "t", "version": "1"}, "paths": {},
            "components": {"schemas": {"U": {
                "type": "object", "properties": {"id": {"type": "string"}},
            }}},
        }
        changes = _diff(old, new)
        removed = _find(changes, ChangeType.FIELD_REMOVED, "extra")
        assert removed and removed[0].context is None
        assert removed[0].is_breaking is True  # conservative
        assert classify(changes) == SemverBump.MAJOR
