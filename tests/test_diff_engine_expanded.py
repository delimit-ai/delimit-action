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

    def test_details_survive_evidence_model(self):
        """LED-2294: old_required/new_required are bools at the producer; they
        MUST be coerced to str so the change survives the Dict[str, str]
        Evidence/Violation models (a bool used to crash validation ->
        execution_failure misclassification). Runs the real end-to-end diff."""
        changes = _diff(*self._specs(False, True))
        prc = [c for c in changes if c.type == ChangeType.PARAM_REQUIRED_CHANGED][0]
        self.assertTrue(
            all(isinstance(v, str) for v in prc.details.values()),
            f"non-str details value reaches Evidence: {prc.details}",
        )
        self.assertEqual(prc.details["old_required"], "false")
        self.assertEqual(prc.details["new_required"], "true")
        from schemas.evidence import Violation
        Violation(
            rule="param_required_changed", severity="high",
            message=prc.message, details=prc.details,
        )


# ===================================================================
# LED-2294: Change.details str-coercion choke point (full producer hardening)
# ===================================================================

class TestChangeDetailsCoercion(unittest.TestCase):
    """Change.__post_init__ coerces every details value to str so the downstream
    Dict[str, str] Evidence/Violation models never crash on a non-str — bool
    (PARAM_REQUIRED_CHANGED), int/None (maxLength/minLength constraint changes),
    or any-typed DEFAULT_CHANGED. One choke point, covering current + future
    producer sites."""

    def test_bool_to_lowercase_str(self):
        c = Change(type=ChangeType.PARAM_REQUIRED_CHANGED, path="/x", severity="high",
                   message="m", details={"old_required": False, "new_required": True})
        self.assertEqual(c.details, {"old_required": "false", "new_required": "true"})

    def test_int_and_none_coerced(self):
        c = Change(type=ChangeType.MAX_LENGTH_DECREASED, path="/x", severity="high",
                   message="m", details={"constraint": "maxLength", "old_value": None, "new_value": 5})
        self.assertEqual(c.details, {"constraint": "maxLength", "old_value": "", "new_value": "5"})
        self.assertTrue(all(isinstance(v, str) for v in c.details.values()))

    def test_any_typed_default_coerced(self):
        c = Change(type=ChangeType.DEFAULT_CHANGED, path="/x", severity="low",
                   message="m", details={"old_default": 10, "new_default": False})
        self.assertEqual(c.details, {"old_default": "10", "new_default": "false"})

    def test_str_values_passthrough(self):
        c = Change(type=ChangeType.FIELD_REMOVED, path="/x", severity="medium",
                   message="m", details={"schema": "User"})
        self.assertEqual(c.details, {"schema": "User"})

    def test_empty_details_ok(self):
        c = Change(type=ChangeType.FIELD_REMOVED, path="/x", severity="low",
                   message="m", details={})
        self.assertEqual(c.details, {})


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
        # LED-2294: details values are coerced to str (Dict[str, str] contract)
        # so they survive the downstream Evidence model. Previously raw ints.
        self.assertEqual(dc.details["old_default"], "1")
        self.assertEqual(dc.details["new_default"], "0")


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
        # LED-1600: required->optional. Breaking by default (no context) and in
        # a response context; non-breaking only in a request context.
        ChangeType.FIELD_REQUIREMENT_RELAXED,
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
        """Verify total ChangeType enum count.

        LED-1600 added ONE new type (FIELD_REQUIREMENT_RELAXED, required->
        optional) to close the silent under-classification of that change.
        Prior canon pinned 27; it is now 28. No existing value was renamed or
        removed.
        """
        self.assertEqual(len(ChangeType), 28)


class TestRefResolution(unittest.TestCase):
    """LED-1591: $ref-targeted schemas must be resolved so breaking changes
    *behind* a reference are not silently missed — while NOT double-counting
    changes already reported once at the component level, and NOT flagging a
    structurally-identical schema rename as breaking.

    Before the fix, _compare_schema_deep returned immediately whenever either
    side carried a $ref, so a field repointed to a structurally-different
    schema (or an inline->$ref refactor that dropped a field) produced zero
    changes at that path.
    """

    def _resp_spec(self, schemas, item_schema):
        """Spec whose GET /w 200 response is an object with one property
        `item` set to `item_schema`. `schemas` populates components."""
        return _base_spec(
            paths={
                "/w": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {"item": item_schema},
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            components={"schemas": schemas, "securitySchemes": {}},
        )

    def test_repoint_to_structurally_different_schema_is_detected(self):
        """item: $ref A -> $ref B where B drops a field A had. Detected."""
        schemas = {
            "A": {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"}}, "required": ["name"]},
            "B": {"type": "object", "properties": {"id": {"type": "string"}}},
        }
        old = self._resp_spec(schemas, {"$ref": "#/components/schemas/A"})
        new = self._resp_spec(schemas, {"$ref": "#/components/schemas/B"})
        changes = _diff(old, new)
        # A and B are unchanged components, so the ONLY signal is the repoint.
        breaking = [c for c in changes if c.is_breaking]
        self.assertTrue(breaking, "repoint to a field-dropping schema must be flagged")
        self.assertTrue(
            any(c.type == ChangeType.FIELD_REMOVED for c in breaking),
            f"expected FIELD_REMOVED behind the ref, got {_types(changes)}",
        )

    def test_identical_rename_is_not_breaking(self):
        """item: $ref A -> $ref ARenamed, identical structure. No false positive."""
        schemas = {
            "A": {"type": "object", "properties": {"id": {"type": "string"}}},
            "ARenamed": {"type": "object", "properties": {"id": {"type": "string"}}},
        }
        old = self._resp_spec(schemas, {"$ref": "#/components/schemas/A"})
        new = self._resp_spec(schemas, {"$ref": "#/components/schemas/ARenamed"})
        breaking = [c for c in _diff(old, new) if c.is_breaking]
        self.assertEqual(breaking, [], f"identical-structure rename must not be breaking, got {_types(breaking)}")

    def test_same_ref_target_is_not_double_counted(self):
        """Both sides $ref A; A.id type changes. Reported ONCE at the component,
        not again at the property path."""
        old = self._resp_spec(
            {"A": {"type": "object", "properties": {"id": {"type": "string"}}}},
            {"$ref": "#/components/schemas/A"},
        )
        new = self._resp_spec(
            {"A": {"type": "object", "properties": {"id": {"type": "integer"}}}},
            {"$ref": "#/components/schemas/A"},
        )
        type_changes = [c for c in _diff(old, new) if c.type == ChangeType.TYPE_CHANGED]
        self.assertEqual(len(type_changes), 1, f"shared component change must not double-count: {[c.path for c in type_changes]}")

    def test_external_ref_is_skipped_safely(self):
        """Non-local ($ref to a URL) is unresolvable — no crash, no false positive."""
        old = self._resp_spec({}, {"$ref": "https://ext.example/schemas/X"})
        new = self._resp_spec({}, {"$ref": "https://ext.example/schemas/Y"})
        try:
            breaking = [c for c in _diff(old, new) if c.is_breaking]
        except Exception as e:  # pragma: no cover
            self.fail(f"external ref must not crash the engine: {e}")
        self.assertEqual(breaking, [], "unresolvable external ref must not fabricate a breaking change")

    def test_inline_to_ref_structural_change_is_detected(self):
        """item: inline {id, name(required)} -> $ref A where A lacks `name`.

        The dropped field is *required* — the engine flags required-field
        removal as breaking regardless of how the schema is expressed, so an
        inline->$ref refactor that drops it must surface (previously the $ref
        side short-circuited and it was missed)."""
        schemas = {"A": {"type": "object", "properties": {"id": {"type": "string"}}}}
        old = self._resp_spec(
            schemas,
            {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"}}, "required": ["name"]},
        )
        new = self._resp_spec(schemas, {"$ref": "#/components/schemas/A"})
        breaking = [c for c in _diff(old, new) if c.is_breaking]
        self.assertTrue(
            any(c.type == ChangeType.FIELD_REMOVED for c in breaking),
            f"inline->$ref dropping a required field must be flagged, got {_types(_diff(old, new))}",
        )

    def test_recursive_schema_terminates(self):
        """A self-referential schema resolved via one-side ref must not loop."""
        schemas = {"Node": {"type": "object", "properties": {"val": {"type": "string"}, "child": {"$ref": "#/components/schemas/Node"}}}}
        # old child is inline (forcing one-side-ref resolution), new child is the $ref.
        old = self._resp_spec(schemas, {"type": "object", "properties": {"val": {"type": "string"}, "child": {"$ref": "#/components/schemas/Node"}}})
        new = self._resp_spec(schemas, {"$ref": "#/components/schemas/Node"})
        # Must return (not hang / RecursionError).
        changes = _diff(old, new)
        self.assertIsInstance(changes, list)


class TestMalformedSpecHardening(unittest.TestCase):
    """The engine must degrade gracefully on structurally-malformed specs
    rather than crashing the GitHub Action with an AttributeError. A spec is
    user-supplied input; a crash is a worse failure than a partial diff.

    Per OpenAPI, `paths`, the path-item method map, and `responses` are all
    objects (maps). Real-world specs (hand-edited, generated, truncated) put
    lists or scalars there. `.keys()` on a list raises AttributeError, which
    previously aborted the whole run.
    """

    def test_paths_as_list_does_not_crash(self):
        bad = _base_spec(paths=[{"/x": {}}])
        good = _base_spec(paths={"/x": {"get": {}}})
        # Both directions must be safe.
        self.assertIsInstance(_diff(bad, good), list)
        self.assertIsInstance(_diff(good, bad), list)

    def test_methods_as_list_does_not_crash(self):
        bad = _base_spec(paths={"/x": ["get", "post"]})
        good = _base_spec(paths={"/x": {"get": {}}})
        self.assertIsInstance(_diff(bad, good), list)
        self.assertIsInstance(_diff(good, bad), list)

    def test_responses_as_list_does_not_crash(self):
        bad = _base_spec(paths={"/x": {"get": {"responses": [200, 404]}}})
        good = _base_spec(paths={"/x": {"get": {"responses": {"200": {}}}}})
        self.assertIsInstance(_diff(bad, good), list)
        self.assertIsInstance(_diff(good, bad), list)

    def test_response_item_and_content_non_dict_does_not_crash(self):
        # A response code mapping to a non-dict, and a content node that's a list.
        bad = _base_spec(paths={"/x": {"get": {"responses": {"200": "OK"}}}})
        bad_content = _base_spec(paths={"/x": {"get": {"responses": {"200": {"content": ["application/json"]}}}}})
        good = _base_spec(paths={"/x": {"get": {"responses": {"200": {"content": {"application/json": {"schema": {"type": "object"}}}}}}}})
        self.assertIsInstance(_diff(bad, good), list)
        self.assertIsInstance(_diff(bad_content, good), list)

    def test_request_body_content_as_list_does_not_crash(self):
        bad = _base_spec(paths={"/x": {"post": {"requestBody": {"content": ["application/json"]}}}})
        good = _base_spec(paths={"/x": {"post": {"requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}}}}})
        self.assertIsInstance(_diff(bad, good), list)
        self.assertIsInstance(_diff(good, bad), list)

    def test_malformed_does_not_suppress_real_diff(self):
        """Guarding one malformed endpoint must not blind the engine to a real
        breaking change on a well-formed endpoint in the same spec."""
        old = _base_spec(paths={
            "/bad": [1, 2, 3],                       # malformed — ignored
            "/good": {"get": {}, "post": {}},        # well-formed
        })
        new = _base_spec(paths={
            "/bad": [1, 2, 3],
            "/good": {"get": {}},                    # post removed -> breaking
        })
        breaking = [c for c in _diff(old, new) if c.is_breaking]
        self.assertTrue(
            any(c.type == ChangeType.METHOD_REMOVED for c in breaking),
            f"real METHOD_REMOVED on /good must survive the malformed /bad guard, got {_types(_diff(old, new))}",
        )


if __name__ == "__main__":
    unittest.main()
