"""Tests for core/json_schema_diff.py (LED-713).

Covers every v1 change type, $ref resolution, dispatcher routing,
and the agentspec rename as a real-world fixture.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.json_schema_diff import (
    JSONSchemaChangeType,
    JSONSchemaDiffEngine,
    is_json_schema,
)
from core.spec_detector import detect_spec_type, get_diff_engine


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _diff(old, new):
    return JSONSchemaDiffEngine().compare(old, new)


def _types(changes):
    return [c.type for c in changes]


# ----------------------------------------------------------------------
# detection
# ----------------------------------------------------------------------

class TestDetection:
    def test_is_json_schema_with_definitions(self):
        assert is_json_schema({"definitions": {"Foo": {}}})

    def test_is_json_schema_with_schema_url(self):
        assert is_json_schema({"$schema": "https://json-schema.org/draft/2020-12/schema"})

    def test_is_json_schema_with_ref_shim(self):
        assert is_json_schema({"$ref": "#/definitions/Foo", "definitions": {"Foo": {}}})

    def test_not_json_schema_openapi(self):
        assert not is_json_schema({"openapi": "3.0.0", "paths": {}})

    def test_not_json_schema_swagger(self):
        assert not is_json_schema({"swagger": "2.0", "paths": {}})

    def test_not_json_schema_non_dict(self):
        assert not is_json_schema("string")
        assert not is_json_schema([])
        assert not is_json_schema(None)

    def test_dispatcher_openapi(self):
        assert detect_spec_type({"openapi": "3.0.0"}) == "openapi"
        assert type(get_diff_engine({"openapi": "3.0.0"})).__name__ == "OpenAPIDiffEngine"

    def test_dispatcher_json_schema(self):
        assert detect_spec_type({"definitions": {"Foo": {}}}) == "json_schema"
        assert type(get_diff_engine({"definitions": {"Foo": {}}})).__name__ == "JSONSchemaDiffEngine"

    def test_dispatcher_ambiguous_defaults_to_openapi(self):
        assert detect_spec_type({}) == "unknown"
        # get_diff_engine falls back to OpenAPI for back-compat
        assert type(get_diff_engine({})).__name__ == "OpenAPIDiffEngine"


# ----------------------------------------------------------------------
# property add / remove
# ----------------------------------------------------------------------

class TestProperties:
    def test_property_added_is_non_breaking(self):
        old = {"properties": {"a": {"type": "string"}}}
        new = {"properties": {"a": {"type": "string"}, "b": {"type": "integer"}}}
        changes = _diff(old, new)
        assert len(changes) == 1
        assert changes[0].type == JSONSchemaChangeType.PROPERTY_ADDED
        assert not changes[0].is_breaking

    def test_property_removed_is_breaking(self):
        old = {"properties": {"a": {"type": "string"}, "b": {"type": "integer"}}}
        new = {"properties": {"a": {"type": "string"}}}
        changes = _diff(old, new)
        assert len(changes) == 1
        assert changes[0].type == JSONSchemaChangeType.PROPERTY_REMOVED
        assert changes[0].is_breaking


# ----------------------------------------------------------------------
# required add / remove
# ----------------------------------------------------------------------

class TestRequired:
    def test_required_added_is_breaking(self):
        old = {"properties": {"a": {}}}
        new = {"properties": {"a": {}}, "required": ["a"]}
        changes = _diff(old, new)
        assert JSONSchemaChangeType.REQUIRED_ADDED in _types(changes)
        assert any(c.is_breaking for c in changes)

    def test_required_removed_is_non_breaking(self):
        old = {"required": ["a"]}
        new = {}
        changes = _diff(old, new)
        assert changes[0].type == JSONSchemaChangeType.REQUIRED_REMOVED
        assert not changes[0].is_breaking


# ----------------------------------------------------------------------
# type widen / narrow
# ----------------------------------------------------------------------

class TestType:
    def test_integer_to_number_is_widening(self):
        changes = _diff({"type": "integer"}, {"type": "number"})
        assert changes[0].type == JSONSchemaChangeType.TYPE_WIDENED
        assert not changes[0].is_breaking

    def test_number_to_integer_is_narrowing(self):
        changes = _diff({"type": "number"}, {"type": "integer"})
        assert changes[0].type == JSONSchemaChangeType.TYPE_NARROWED
        assert changes[0].is_breaking

    def test_unrelated_type_change_is_breaking(self):
        changes = _diff({"type": "string"}, {"type": "integer"})
        assert changes[0].type == JSONSchemaChangeType.TYPE_NARROWED
        assert changes[0].is_breaking


# ----------------------------------------------------------------------
# enum add / remove
# ----------------------------------------------------------------------

class TestEnum:
    def test_enum_value_removed_is_breaking(self):
        changes = _diff({"enum": ["a", "b", "c"]}, {"enum": ["a", "b"]})
        assert JSONSchemaChangeType.ENUM_VALUE_REMOVED in _types(changes)
        assert any(c.is_breaking for c in changes)

    def test_enum_value_added_is_non_breaking(self):
        changes = _diff({"enum": ["a"]}, {"enum": ["a", "b"]})
        assert changes[0].type == JSONSchemaChangeType.ENUM_VALUE_ADDED
        assert not changes[0].is_breaking


# ----------------------------------------------------------------------
# const
# ----------------------------------------------------------------------

class TestConst:
    def test_const_changed_is_breaking(self):
        changes = _diff({"const": "v1"}, {"const": "v1alpha1"})
        assert changes[0].type == JSONSchemaChangeType.CONST_CHANGED
        assert changes[0].is_breaking


# ----------------------------------------------------------------------
# additionalProperties
# ----------------------------------------------------------------------

class TestAdditionalProperties:
    def test_true_to_false_is_breaking(self):
        changes = _diff({"additionalProperties": True}, {"additionalProperties": False})
        assert changes[0].type == JSONSchemaChangeType.ADDITIONAL_PROPERTIES_TIGHTENED
        assert changes[0].is_breaking

    def test_false_to_true_is_non_breaking(self):
        changes = _diff({"additionalProperties": False}, {"additionalProperties": True})
        assert changes[0].type == JSONSchemaChangeType.ADDITIONAL_PROPERTIES_LOOSENED
        assert not changes[0].is_breaking


# ----------------------------------------------------------------------
# pattern
# ----------------------------------------------------------------------

class TestPattern:
    def test_pattern_added_is_breaking(self):
        changes = _diff({}, {"pattern": "^[a-z]+$"})
        assert changes[0].type == JSONSchemaChangeType.PATTERN_TIGHTENED
        assert changes[0].is_breaking

    def test_pattern_removed_is_non_breaking(self):
        changes = _diff({"pattern": "^[a-z]+$"}, {})
        assert changes[0].type == JSONSchemaChangeType.PATTERN_LOOSENED
        assert not changes[0].is_breaking

    def test_pattern_changed_is_breaking(self):
        changes = _diff({"pattern": "^[a-z]+$"}, {"pattern": "^[A-Z]+$"})
        assert changes[0].type == JSONSchemaChangeType.PATTERN_TIGHTENED
        assert changes[0].is_breaking


# ----------------------------------------------------------------------
# string length bounds
# ----------------------------------------------------------------------

class TestStringLength:
    def test_min_length_increased_is_breaking(self):
        changes = _diff({"minLength": 1}, {"minLength": 5})
        assert changes[0].type == JSONSchemaChangeType.MIN_LENGTH_INCREASED
        assert changes[0].is_breaking

    def test_min_length_decreased_is_non_breaking(self):
        changes = _diff({"minLength": 5}, {"minLength": 1})
        assert changes[0].type == JSONSchemaChangeType.MIN_LENGTH_DECREASED
        assert not changes[0].is_breaking

    def test_max_length_decreased_is_breaking(self):
        changes = _diff({"maxLength": 100}, {"maxLength": 10})
        assert changes[0].type == JSONSchemaChangeType.MAX_LENGTH_DECREASED
        assert changes[0].is_breaking

    def test_max_length_increased_is_non_breaking(self):
        changes = _diff({"maxLength": 10}, {"maxLength": 100})
        assert changes[0].type == JSONSchemaChangeType.MAX_LENGTH_INCREASED
        assert not changes[0].is_breaking


# ----------------------------------------------------------------------
# numeric bounds
# ----------------------------------------------------------------------

class TestNumericBounds:
    def test_minimum_increased_is_breaking(self):
        changes = _diff({"minimum": 0}, {"minimum": 10})
        assert changes[0].type == JSONSchemaChangeType.MINIMUM_INCREASED
        assert changes[0].is_breaking

    def test_maximum_decreased_is_breaking(self):
        changes = _diff({"maximum": 100}, {"maximum": 50})
        assert changes[0].type == JSONSchemaChangeType.MAXIMUM_DECREASED
        assert changes[0].is_breaking

    def test_minimum_decreased_is_non_breaking(self):
        changes = _diff({"minimum": 10}, {"minimum": 0})
        assert changes[0].type == JSONSchemaChangeType.MINIMUM_DECREASED
        assert not changes[0].is_breaking


# ----------------------------------------------------------------------
# array items
# ----------------------------------------------------------------------

class TestItems:
    def test_items_type_narrowed_is_breaking(self):
        old = {"type": "array", "items": {"type": "number"}}
        new = {"type": "array", "items": {"type": "integer"}}
        changes = _diff(old, new)
        assert any(c.type == JSONSchemaChangeType.TYPE_NARROWED for c in changes)
        assert any(c.is_breaking for c in changes)

    def test_items_type_widened_is_non_breaking(self):
        old = {"type": "array", "items": {"type": "integer"}}
        new = {"type": "array", "items": {"type": "number"}}
        changes = _diff(old, new)
        assert any(c.type == JSONSchemaChangeType.TYPE_WIDENED for c in changes)
        assert not any(c.is_breaking for c in changes)


# ----------------------------------------------------------------------
# $ref resolution
# ----------------------------------------------------------------------

class TestRefResolution:
    def test_ref_shim_at_root(self):
        """Agentspec pattern: root is {"$ref": "#/definitions/X", "definitions": {...}}"""
        old = {
            "$ref": "#/definitions/Thing",
            "definitions": {"Thing": {"type": "object", "properties": {"a": {"type": "string"}}}},
        }
        new = {
            "$ref": "#/definitions/Thing",
            "definitions": {"Thing": {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "integer"}}}},
        }
        changes = _diff(old, new)
        assert len(changes) == 1
        assert changes[0].type == JSONSchemaChangeType.PROPERTY_ADDED

    def test_ref_in_nested_property(self):
        old = {
            "properties": {"child": {"$ref": "#/definitions/Child"}},
            "definitions": {"Child": {"type": "object", "required": ["a"]}},
        }
        new = {
            "properties": {"child": {"$ref": "#/definitions/Child"}},
            "definitions": {"Child": {"type": "object", "required": ["a", "b"]}},
        }
        changes = _diff(old, new)
        assert JSONSchemaChangeType.REQUIRED_ADDED in _types(changes)


# ----------------------------------------------------------------------
# agentspec fixture — real-world
# ----------------------------------------------------------------------

AGENTSPEC_FIXTURE = Path("/tmp/agentspec-v1.json")
AGENTSPEC_RENAMED = Path("/tmp/agentspec-v1alpha1.json")


@pytest.mark.skipif(not AGENTSPEC_FIXTURE.exists(), reason="agentspec fixture not available")
class TestAgentspecFixture:
    def test_detects_as_json_schema(self):
        doc = json.loads(AGENTSPEC_FIXTURE.read_text())
        assert detect_spec_type(doc) == "json_schema"

    def test_rename_classified_as_const_change(self):
        old = json.loads(AGENTSPEC_FIXTURE.read_text())
        new = json.loads(AGENTSPEC_RENAMED.read_text())
        changes = _diff(old, new)
        assert len(changes) == 1
        assert changes[0].type == JSONSchemaChangeType.CONST_CHANGED
        assert changes[0].is_breaking  # pre-1.0 breaking is expected; action stays advisory
        assert "apiVersion" in changes[0].path


# ----------------------------------------------------------------------
# edge cases
# ----------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_schemas(self):
        assert _diff({}, {}) == []

    def test_identical_schemas(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        assert _diff(schema, schema) == []

    def test_none_inputs(self):
        assert _diff(None, None) == []
        assert _diff(None, {}) == []

    def test_change_severity_matches_is_breaking(self):
        changes = _diff({"const": "a"}, {"const": "b"})
        assert changes[0].severity == "high"
        changes = _diff({}, {"properties": {"a": {}}})
        assert changes[0].severity == "low"
