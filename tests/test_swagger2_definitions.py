"""Swagger 2.0 `definitions` comparison in the Action's diff engine.

detect routes v2 specs to OpenAPIDiffEngine, but compare() previously only
diffed components/schemas — so a breaking change inside a v2 definition (and
behind a #/definitions/X ref) was missed entirely in Action runs. Parity with
the gateway engine fix (delimit-gateway#212). The Action has no advisory
channel, so this port covers the definitions comparison only.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.diff_engine_v2 import OpenAPIDiffEngine, ChangeType


def _v2(definitions, paths=None):
    return {"swagger": "2.0", "info": {"title": "t", "version": "1.0.0"},
            "paths": paths or {}, "definitions": definitions}


def _diff(old, new):
    return OpenAPIDiffEngine().compare(old, new)


def test_required_field_removed_from_v2_definition_is_detected():
    old = _v2({"User": {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"}}, "required": ["id", "name"]}})
    new = _v2({"User": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}})
    breaking = [c for c in _diff(old, new) if c.is_breaking]
    assert any(c.type == ChangeType.FIELD_REMOVED and c.path == "#/definitions/User.name" for c in breaking), \
        [(c.type.value, c.path) for c in breaking]


def test_v2_definition_removed_is_flagged():
    old = _v2({"User": {"type": "object"}, "Account": {"type": "object"}})
    new = _v2({"User": {"type": "object"}})
    changes = _diff(old, new)
    assert any(c.type == ChangeType.FIELD_REMOVED and c.path == "#/definitions/Account" for c in changes), \
        [(c.type.value, c.path) for c in changes]


def test_v2_type_change_detected_once_behind_ref():
    paths = {"/u": {"get": {"responses": {"200": {"schema": {"$ref": "#/definitions/User"}}}}}}
    old = _v2({"User": {"type": "object", "properties": {"id": {"type": "string"}}}}, paths)
    new = _v2({"User": {"type": "object", "properties": {"id": {"type": "integer"}}}}, paths)
    type_changes = [c for c in _diff(old, new) if c.type == ChangeType.TYPE_CHANGED]
    assert len(type_changes) == 1, [(c.type.value, c.path) for c in type_changes]
    assert type_changes[0].path == "#/definitions/User.id"


def test_v3_uses_components_prefix_unaffected():
    def v3(props):
        return {"openapi": "3.0.3", "info": {"title": "t", "version": "1"}, "paths": {},
                "components": {"schemas": {"User": {"type": "object", "properties": props, "required": ["name"]}}}}
    changes = _diff(v3({"id": {"type": "string"}, "name": {"type": "string"}}), v3({"id": {"type": "string"}}))
    assert any(c.path == "#/components/schemas/User.name" for c in changes), [(c.type.value, c.path) for c in changes]


def test_malformed_v2_definitions_does_not_crash():
    old = _v2(["not", "a", "dict"])
    new = _v2({"User": {"type": "object"}})
    assert isinstance(_diff(old, new), list)
    assert isinstance(_diff(new, old), list)
