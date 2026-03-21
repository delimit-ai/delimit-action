"""
Tests for expanded diff engine change types (v2.1).

Covers 10 new ChangeType values:
  Breaking:  PARAM_TYPE_CHANGED, PARAM_REQUIRED_CHANGED, RESPONSE_TYPE_CHANGED,
             SECURITY_REMOVED, SECURITY_SCOPE_REMOVED, MAX_LENGTH_DECREASED,
             MIN_LENGTH_INCREASED
  Non-breaking: SECURITY_ADDED, DEPRECATED_ADDED, DEFAULT_CHANGED

Run with:
    python3 -m pytest tests/test_diff_engine_expanded.py -xvs
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.diff_engine_v2 import OpenAPIDiffEngine, Change, ChangeType


# ---------------------------------------------------------------------------
# Helper: build minimal specs
# ---------------------------------------------------------------------------

def _base_spec(**overrides):
    """Return a minimal valid OpenAPI 3 spec dict. Override any top-level key."""
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {},
        "components": {"schemas": {}, "securitySchemes": {}},
    }
    spec.update(overrides)
    return spec


def _diff(old_spec, new_spec):
    engine = OpenAPIDiffEngine()
    return engine.compare(old_spec, new_spec)


def _types(changes):
    return [c.type for c in changes]


# ===================================================================
# 1. PARAM_TYPE_CHANGED
# ===================================================================

class TestParamTypeChanged(unittest.TestCase):
    """Detect when a parameter's schema type changes."""

    def _specs(self, old_type="string", new_type="integer"):
        old = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "filter", "in": "query", "schema": {"type": old_type}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        new = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "filter", "in": "query", "schema": {"type": new_type}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        return old, new

    def test_detected(self):
        changes = _diff(*self._specs("string", "integer"))
        self.assertIn(ChangeType.PARAM_TYPE_CHANGED, _types(changes))

    def test_is_breaking(self):
        changes = _diff(*self._specs())
        ptc = [c for c in changes if c.type == ChangeType.PARAM_TYPE_CHANGED]
        self.assertTrue(all(c.is_breaking for c in ptc))

    def test_details_contain_types(self):
        changes = _diff(*self._specs("string", "boolean"))
        ptc = [c for c in changes if c.type == ChangeType.PARAM_TYPE_CHANGED][0]
        self.assertEqual(ptc.details["old_type"], "string")
        self.assertEqual(ptc.details["new_type"], "boolean")
        self.assertIn("filter", ptc.details["parameter"])

    def test_no_false_positive_same_type(self):
        changes = _diff(*self._specs("string", "string"))
        self.assertNotIn(ChangeType.PARAM_TYPE_CHANGED, _types(changes))


# ===================================================================
# 2. PARAM_REQUIRED_CHANGED
# ===================================================================

class TestParamRequiredChanged(unittest.TestCase):
    """Detect when an existing parameter goes from optional to required."""

    def _specs(self, old_required=False, new_required=True):
        old = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "page", "in": "query", "required": old_required, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        new = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "page", "in": "query", "required": new_required, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        return old, new

    def test_optional_to_required(self):
        changes = _diff(*self._specs(False, True))
        self.assertIn(ChangeType.PARAM_REQUIRED_CHANGED, _types(changes))

    def test_is_breaking(self):
        changes = _diff(*self._specs(False, True))
        prc = [c for c in changes if c.type == ChangeType.PARAM_REQUIRED_CHANGED]
        self.assertTrue(all(c.is_breaking for c in prc))

    def test_required_to_optional_not_flagged(self):
        """Going from required to optional is not flagged as PARAM_REQUIRED_CHANGED."""
        changes = _diff(*self._specs(True, False))
        self.assertNotIn(ChangeType.PARAM_REQUIRED_CHANGED, _types(changes))

    def test_same_required_no_change(self):
        changes = _diff(*self._specs(True, True))
        self.assertNotIn(ChangeType.PARAM_REQUIRED_CHANGED, _types(changes))


# ===================================================================
# 3. RESPONSE_TYPE_CHANGED
# ===================================================================

class TestResponseTypeChanged(unittest.TestCase):
    """Detect type change in response body fields."""

    def _specs(self, old_type="string", new_type="integer"):
        old = _base_spec(paths={
            "/items": {"get": {
                "responses": {"200": {
                    "description": "ok",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"count": {"type": old_type}},
                    }}},
                }},
            }}
        })
        new = _base_spec(paths={
            "/items": {"get": {
                "responses": {"200": {
                    "description": "ok",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"count": {"type": new_type}},
                    }}},
                }},
            }}
        })
        return old, new

    def test_detected(self):
        changes = _diff(*self._specs("string", "integer"))
        self.assertIn(ChangeType.RESPONSE_TYPE_CHANGED, _types(changes))

    def test_is_breaking(self):
        changes = _diff(*self._specs("string", "array"))
        rtc = [c for c in changes if c.type == ChangeType.RESPONSE_TYPE_CHANGED]
        self.assertTrue(len(rtc) >= 1)
        self.assertTrue(all(c.is_breaking for c in rtc))

    def test_no_false_positive_same_type(self):
        changes = _diff(*self._specs("string", "string"))
        self.assertNotIn(ChangeType.RESPONSE_TYPE_CHANGED, _types(changes))


# ===================================================================
# 4. SECURITY_REMOVED (operation level)
# ===================================================================

class TestSecurityRemovedOperation(unittest.TestCase):
    """Detect when security scheme is removed from an operation."""

    def _specs(self):
        old = _base_spec(paths={
            "/secret": {"get": {
                "security": [{"bearerAuth": []}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        new = _base_spec(paths={
            "/secret": {"get": {
                "security": [],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        return old, new

    def test_detected(self):
        changes = _diff(*self._specs())
        self.assertIn(ChangeType.SECURITY_REMOVED, _types(changes))

    def test_is_breaking(self):
        changes = _diff(*self._specs())
        sr = [c for c in changes if c.type == ChangeType.SECURITY_REMOVED]
        self.assertTrue(all(c.is_breaking for c in sr))

    def test_details_contain_scheme(self):
        changes = _diff(*self._specs())
        sr = [c for c in changes if c.type == ChangeType.SECURITY_REMOVED][0]
        self.assertEqual(sr.details["scheme"], "bearerAuth")


class TestSecurityRemovedComponent(unittest.TestCase):
    """Detect when security scheme is removed from components."""

    def _specs(self):
        old = _base_spec()
        old["components"]["securitySchemes"] = {"apiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}}
        new = _base_spec()
        new["components"]["securitySchemes"] = {}
        return old, new

    def test_detected(self):
        changes = _diff(*self._specs())
        sr = [c for c in changes if c.type == ChangeType.SECURITY_REMOVED]
        self.assertTrue(len(sr) >= 1)

    def test_is_breaking(self):
        changes = _diff(*self._specs())
        sr = [c for c in changes if c.type == ChangeType.SECURITY_REMOVED]
        self.assertTrue(all(c.is_breaking for c in sr))


# ===================================================================
# 5. SECURITY_SCOPE_REMOVED
# ===================================================================

class TestSecurityScopeRemoved(unittest.TestCase):
    """Detect when an OAuth scope is removed from an operation's security."""

    def _specs(self):
        old = _base_spec(paths={
            "/data": {"get": {
                "security": [{"oauth2": ["read", "write"]}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        new = _base_spec(paths={
            "/data": {"get": {
                "security": [{"oauth2": ["read"]}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        return old, new

    def test_detected(self):
        changes = _diff(*self._specs())
        self.assertIn(ChangeType.SECURITY_SCOPE_REMOVED, _types(changes))

    def test_is_breaking(self):
        changes = _diff(*self._specs())
        ssr = [c for c in changes if c.type == ChangeType.SECURITY_SCOPE_REMOVED]
        self.assertTrue(all(c.is_breaking for c in ssr))

    def test_details_contain_scope(self):
        changes = _diff(*self._specs())
        ssr = [c for c in changes if c.type == ChangeType.SECURITY_SCOPE_REMOVED][0]
        self.assertEqual(ssr.details["scope"], "write")
        self.assertEqual(ssr.details["scheme"], "oauth2")

    def test_no_false_positive_same_scopes(self):
        old = _base_spec(paths={
            "/data": {"get": {
                "security": [{"oauth2": ["read", "write"]}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        changes = _diff(old, old)
        self.assertNotIn(ChangeType.SECURITY_SCOPE_REMOVED, _types(changes))


# ===================================================================
# 6. MAX_LENGTH_DECREASED
# ===================================================================

class TestMaxLengthDecreased(unittest.TestCase):
    """Detect when maxLength/maxItems constraint is made stricter."""

    def _specs_param(self, old_max=100, new_max=50):
        old = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "q", "in": "query", "schema": {"type": "string", "maxLength": old_max}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        new = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "q", "in": "query", "schema": {"type": "string", "maxLength": new_max}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        return old, new

    def test_detected_on_param(self):
        changes = _diff(*self._specs_param(100, 50))
        self.assertIn(ChangeType.MAX_LENGTH_DECREASED, _types(changes))

    def test_is_breaking(self):
        changes = _diff(*self._specs_param(100, 50))
        mld = [c for c in changes if c.type == ChangeType.MAX_LENGTH_DECREASED]
        self.assertTrue(all(c.is_breaking for c in mld))

    def test_increased_not_flagged(self):
        changes = _diff(*self._specs_param(50, 100))
        self.assertNotIn(ChangeType.MAX_LENGTH_DECREASED, _types(changes))

    def test_same_value_not_flagged(self):
        changes = _diff(*self._specs_param(100, 100))
        self.assertNotIn(ChangeType.MAX_LENGTH_DECREASED, _types(changes))

    def test_added_where_none_existed(self):
        """Adding maxLength where there was none is stricter."""
        old = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "q", "in": "query", "schema": {"type": "string"}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        new = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "q", "in": "query", "schema": {"type": "string", "maxLength": 50}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        changes = _diff(old, new)
        self.assertIn(ChangeType.MAX_LENGTH_DECREASED, _types(changes))

    def test_max_items_on_schema_field(self):
        """maxItems decreased on a response schema field."""
        old = _base_spec(paths={
            "/items": {"get": {
                "responses": {"200": {
                    "description": "ok",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"tags": {"type": "array", "maxItems": 20}},
                    }}},
                }},
            }}
        })
        new = _base_spec(paths={
            "/items": {"get": {
                "responses": {"200": {
                    "description": "ok",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"tags": {"type": "array", "maxItems": 10}},
                    }}},
                }},
            }}
        })
        changes = _diff(old, new)
        self.assertIn(ChangeType.MAX_LENGTH_DECREASED, _types(changes))


# ===================================================================
# 7. MIN_LENGTH_INCREASED
# ===================================================================

class TestMinLengthIncreased(unittest.TestCase):
    """Detect when minLength/minItems constraint is made stricter."""

    def _specs_param(self, old_min=1, new_min=5):
        old = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "q", "in": "query", "schema": {"type": "string", "minLength": old_min}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        new = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "q", "in": "query", "schema": {"type": "string", "minLength": new_min}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        return old, new

    def test_detected_on_param(self):
        changes = _diff(*self._specs_param(1, 5))
        self.assertIn(ChangeType.MIN_LENGTH_INCREASED, _types(changes))

    def test_is_breaking(self):
        changes = _diff(*self._specs_param(1, 5))
        mli = [c for c in changes if c.type == ChangeType.MIN_LENGTH_INCREASED]
        self.assertTrue(all(c.is_breaking for c in mli))

    def test_decreased_not_flagged(self):
        changes = _diff(*self._specs_param(5, 1))
        self.assertNotIn(ChangeType.MIN_LENGTH_INCREASED, _types(changes))

    def test_same_value_not_flagged(self):
        changes = _diff(*self._specs_param(3, 3))
        self.assertNotIn(ChangeType.MIN_LENGTH_INCREASED, _types(changes))

    def test_added_where_none_existed(self):
        """Adding minLength > 0 where there was none is stricter."""
        old = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "q", "in": "query", "schema": {"type": "string"}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        new = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "q", "in": "query", "schema": {"type": "string", "minLength": 3}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        changes = _diff(old, new)
        self.assertIn(ChangeType.MIN_LENGTH_INCREASED, _types(changes))

    def test_min_items_on_schema_field(self):
        """minItems increased on a response schema field."""
        old = _base_spec(paths={
            "/items": {"get": {
                "responses": {"200": {
                    "description": "ok",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"tags": {"type": "array", "minItems": 0}},
                    }}},
                }},
            }}
        })
        new = _base_spec(paths={
            "/items": {"get": {
                "responses": {"200": {
                    "description": "ok",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"tags": {"type": "array", "minItems": 2}},
                    }}},
                }},
            }}
        })
        changes = _diff(old, new)
        self.assertIn(ChangeType.MIN_LENGTH_INCREASED, _types(changes))


# ===================================================================
# 8. SECURITY_ADDED (non-breaking)
# ===================================================================

class TestSecurityAdded(unittest.TestCase):
    """Detect when a new security scheme is added."""

    def test_operation_level(self):
        old = _base_spec(paths={
            "/open": {"get": {
                "responses": {"200": {"description": "ok"}},
            }}
        })
        new = _base_spec(paths={
            "/open": {"get": {
                "security": [{"apiKey": []}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        changes = _diff(old, new)
        self.assertIn(ChangeType.SECURITY_ADDED, _types(changes))

    def test_component_level(self):
        old = _base_spec()
        old["components"]["securitySchemes"] = {}
        new = _base_spec()
        new["components"]["securitySchemes"] = {"bearerAuth": {"type": "http", "scheme": "bearer"}}
        changes = _diff(old, new)
        sa = [c for c in changes if c.type == ChangeType.SECURITY_ADDED]
        self.assertTrue(len(sa) >= 1)

    def test_not_breaking(self):
        old = _base_spec()
        old["components"]["securitySchemes"] = {}
        new = _base_spec()
        new["components"]["securitySchemes"] = {"bearerAuth": {"type": "http", "scheme": "bearer"}}
        changes = _diff(old, new)
        sa = [c for c in changes if c.type == ChangeType.SECURITY_ADDED]
        self.assertTrue(all(not c.is_breaking for c in sa))


# ===================================================================
# 9. DEPRECATED_ADDED (non-breaking)
# ===================================================================

class TestDeprecatedAdded(unittest.TestCase):
    """Detect when an operation or field is marked as deprecated."""

    def test_operation_deprecated(self):
        old = _base_spec(paths={
            "/legacy": {"get": {
                "responses": {"200": {"description": "ok"}},
            }}
        })
        new = _base_spec(paths={
            "/legacy": {"get": {
                "deprecated": True,
                "responses": {"200": {"description": "ok"}},
            }}
        })
        changes = _diff(old, new)
        self.assertIn(ChangeType.DEPRECATED_ADDED, _types(changes))

    def test_field_deprecated(self):
        old = _base_spec(paths={
            "/items": {"get": {
                "responses": {"200": {
                    "description": "ok",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"old_field": {"type": "string"}},
                    }}},
                }},
            }}
        })
        new = _base_spec(paths={
            "/items": {"get": {
                "responses": {"200": {
                    "description": "ok",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"old_field": {"type": "string", "deprecated": True}},
                    }}},
                }},
            }}
        })
        changes = _diff(old, new)
        self.assertIn(ChangeType.DEPRECATED_ADDED, _types(changes))

    def test_not_breaking(self):
        old = _base_spec(paths={
            "/legacy": {"get": {
                "responses": {"200": {"description": "ok"}},
            }}
        })
        new = _base_spec(paths={
            "/legacy": {"get": {
                "deprecated": True,
                "responses": {"200": {"description": "ok"}},
            }}
        })
        changes = _diff(old, new)
        dep = [c for c in changes if c.type == ChangeType.DEPRECATED_ADDED]
        self.assertTrue(all(not c.is_breaking for c in dep))

    def test_already_deprecated_no_change(self):
        old = _base_spec(paths={
            "/legacy": {"get": {
                "deprecated": True,
                "responses": {"200": {"description": "ok"}},
            }}
        })
        changes = _diff(old, old)
        self.assertNotIn(ChangeType.DEPRECATED_ADDED, _types(changes))


# ===================================================================
# 10. DEFAULT_CHANGED (non-breaking)
# ===================================================================

class TestDefaultChanged(unittest.TestCase):
    """Detect when a default value changes on a parameter or field."""

    def test_param_default_changed(self):
        old = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        new = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "page", "in": "query", "schema": {"type": "integer", "default": 0}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        changes = _diff(old, new)
        self.assertIn(ChangeType.DEFAULT_CHANGED, _types(changes))

    def test_field_default_changed(self):
        old = _base_spec(paths={
            "/items": {"get": {
                "responses": {"200": {
                    "description": "ok",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"active": {"type": "boolean", "default": True}},
                    }}},
                }},
            }}
        })
        new = _base_spec(paths={
            "/items": {"get": {
                "responses": {"200": {
                    "description": "ok",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"active": {"type": "boolean", "default": False}},
                    }}},
                }},
            }}
        })
        changes = _diff(old, new)
        self.assertIn(ChangeType.DEFAULT_CHANGED, _types(changes))

    def test_not_breaking(self):
        old = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        new = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "page", "in": "query", "schema": {"type": "integer", "default": 0}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        changes = _diff(old, new)
        dc = [c for c in changes if c.type == ChangeType.DEFAULT_CHANGED]
        self.assertTrue(all(not c.is_breaking for c in dc))

    def test_same_default_no_change(self):
        old = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        changes = _diff(old, old)
        self.assertNotIn(ChangeType.DEFAULT_CHANGED, _types(changes))

    def test_details_contain_values(self):
        old = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        new = _base_spec(paths={
            "/items": {"get": {
                "parameters": [{"name": "page", "in": "query", "schema": {"type": "integer", "default": 0}}],
                "responses": {"200": {"description": "ok"}},
            }}
        })
        changes = _diff(old, new)
        dc = [c for c in changes if c.type == ChangeType.DEFAULT_CHANGED][0]
        self.assertEqual(dc.details["old_default"], 1)
        self.assertEqual(dc.details["new_default"], 0)


# ===================================================================
# Enum completeness: all 17 breaking types in is_breaking
# ===================================================================

class TestBreakingTypeCompleteness(unittest.TestCase):
    """Verify all 17 breaking change types are classified as breaking."""

    EXPECTED_BREAKING = {
        ChangeType.ENDPOINT_REMOVED,
        ChangeType.METHOD_REMOVED,
        ChangeType.REQUIRED_PARAM_ADDED,
        ChangeType.PARAM_REMOVED,
        ChangeType.RESPONSE_REMOVED,
        ChangeType.REQUIRED_FIELD_ADDED,
        ChangeType.FIELD_REMOVED,
        ChangeType.TYPE_CHANGED,
        ChangeType.FORMAT_CHANGED,
        ChangeType.ENUM_VALUE_REMOVED,
        ChangeType.PARAM_TYPE_CHANGED,
        ChangeType.PARAM_REQUIRED_CHANGED,
        ChangeType.RESPONSE_TYPE_CHANGED,
        ChangeType.SECURITY_REMOVED,
        ChangeType.SECURITY_SCOPE_REMOVED,
        ChangeType.MAX_LENGTH_DECREASED,
        ChangeType.MIN_LENGTH_INCREASED,
    }

    EXPECTED_NON_BREAKING = {
        ChangeType.ENDPOINT_ADDED,
        ChangeType.METHOD_ADDED,
        ChangeType.OPTIONAL_PARAM_ADDED,
        ChangeType.RESPONSE_ADDED,
        ChangeType.OPTIONAL_FIELD_ADDED,
        ChangeType.ENUM_VALUE_ADDED,
        ChangeType.DESCRIPTION_CHANGED,
        ChangeType.SECURITY_ADDED,
        ChangeType.DEPRECATED_ADDED,
        ChangeType.DEFAULT_CHANGED,
    }

    def test_all_breaking_classified(self):
        for ct in self.EXPECTED_BREAKING:
            change = Change(type=ct, path="/test", details={}, severity="high", message="test")
            self.assertTrue(change.is_breaking, f"{ct.value} should be breaking")

    def test_all_non_breaking_classified(self):
        for ct in self.EXPECTED_NON_BREAKING:
            change = Change(type=ct, path="/test", details={}, severity="low", message="test")
            self.assertFalse(change.is_breaking, f"{ct.value} should NOT be breaking")

    def test_total_enum_count(self):
        """Verify total ChangeType enum has exactly 27 values (17 breaking + 10 non-breaking)."""
        self.assertEqual(len(ChangeType), 27)


if __name__ == "__main__":
    unittest.main()
