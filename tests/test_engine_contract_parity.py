"""Shared behavioral contract for the OpenAPI diff engine (LED-1589 drift guard).

The diff engine is maintained as two copies — delimit-gateway/core (MCP
`delimit_diff`) and delimit-action/core (the GitHub Action). They have
repeatedly drifted, so a fix in one silently failed to land in the other
(see LED-1589). This file pins the COMMON behavioral contract: a battery of
spec pairs and the exact breaking-change signature the engine must produce.

>>> THIS FILE IS SYNCED across delimit-gateway and delimit-action. <<<
Any change here MUST be mirrored in the other repo. If the two copies of this
test diverge, or an engine stops matching a signature, that is the drift this
guard exists to catch — reconcile both engines before shipping.

The contract intentionally covers only behavior both engines agree on
(change detection + paths), NOT gateway-only features like the advisory
channel. Signatures are the sorted list of (change_type, path) for breaking
changes only.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.diff_engine_v2 import OpenAPIDiffEngine


def _v3(schemas, paths=None):
    return {"openapi": "3.0.3", "info": {"title": "t", "version": "1"},
            "paths": paths or {}, "components": {"schemas": schemas}}


def _v2(definitions, paths=None):
    return {"swagger": "2.0", "info": {"title": "t", "version": "1"},
            "paths": paths or {}, "definitions": definitions}


_REF_PATH = {"/u": {"get": {"responses": {"200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/U"}}}}}}}}
_V2_REF_PATH = {"/u": {"get": {"responses": {"200": {"schema": {"$ref": "#/definitions/U"}}}}}}


def _resp_obj(props, required=None):
    """An OpenAPI 3.x spec with a single GET whose 200 response is an inline
    object schema. Used for LED-1600 request/response-context contract cases."""
    schema = {"type": "object", "properties": props}
    if required is not None:
        schema["required"] = required
    return {"openapi": "3.0.3", "info": {"title": "t", "version": "1"},
            "paths": {"/u": {"get": {"responses": {"200": {"description": "ok",
                "content": {"application/json": {"schema": schema}}}}}}}}


def _req_obj(props, required=None):
    """An OpenAPI 3.x spec with a single POST whose requestBody is an inline
    object schema. Used for LED-1600 request-context contract cases."""
    schema = {"type": "object", "properties": props}
    if required is not None:
        schema["required"] = required
    return {"openapi": "3.0.3", "info": {"title": "t", "version": "1"},
            "paths": {"/u": {"post": {
                "requestBody": {"content": {"application/json": {"schema": schema}}},
                "responses": {"200": {"description": "ok"}}}}}}

# name -> (old_spec, new_spec, expected sorted breaking [(type, path), ...])
CONTRACT = {
    "endpoint_removed": (
        _v3({}, {"/a": {"get": {}}}), _v3({}, {}),
        [("endpoint_removed", "/a")],
    ),
    "method_removed": (
        _v3({}, {"/a": {"get": {}, "post": {}}}), _v3({}, {"/a": {"get": {}}}),
        [("method_removed", "/a:POST")],
    ),
    "component_required_field_removed": (
        _v3({"U": {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"}}, "required": ["name"]}}),
        _v3({"U": {"type": "object", "properties": {"id": {"type": "string"}}}}),
        [("field_removed", "#/components/schemas/U.name")],
    ),
    "breaking_change_behind_ref": (
        _v3({"U": {"type": "object", "properties": {"id": {"type": "string"}}}}, _REF_PATH),
        _v3({"U": {"type": "object", "properties": {"id": {"type": "integer"}}}}, _REF_PATH),
        [("type_changed", "#/components/schemas/U.id")],
    ),
    "swagger2_definition_required_field_removed": (
        _v2({"U": {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"}}, "required": ["name"]}}, _V2_REF_PATH),
        _v2({"U": {"type": "object", "properties": {"id": {"type": "string"}}}}, _V2_REF_PATH),
        [("field_removed", "#/definitions/U.name")],
    ),
    "non_breaking_endpoint_added": (
        _v3({}, {"/a": {"get": {}}}), _v3({}, {"/a": {"get": {}}, "/b": {"get": {}}}),
        [],
    ),
    "malformed_paths_no_crash_no_breaking": (
        {"openapi": "3.0.3", "info": {}, "paths": [1, 2]},
        _v3({}, {"/a": {"get": {}}}),
        [],
    ),

    # ── LED-1600: request/response-context-aware severity ──────────────
    # A response-field removal (optional) is breaking; both engines must
    # produce the same breaking signature.
    "led1600_response_optional_field_removed_is_breaking": (
        _resp_obj({"id": {"type": "string"}, "extra": {"type": "string"}}),
        _resp_obj({"id": {"type": "string"}}),
        [("field_removed", "/u:GET:200.extra")],
    ),
    # A request-field removal is NON-breaking — empty breaking signature.
    "led1600_request_field_removed_not_breaking": (
        _req_obj({"id": {"type": "string"}, "extra": {"type": "string"}}),
        _req_obj({"id": {"type": "string"}}),
        [],
    ),
    # Adding a new required REQUEST field is breaking.
    "led1600_request_required_field_added_is_breaking": (
        _req_obj({"id": {"type": "string"}}, ["id"]),
        _req_obj({"id": {"type": "string"}, "tok": {"type": "string"}}, ["id", "tok"]),
        [("required_field_added", "/u:POST:request.tok")],
    ),
    # Adding a new required RESPONSE field is NON-breaking.
    "led1600_response_required_field_added_not_breaking": (
        _resp_obj({"id": {"type": "string"}}, ["id"]),
        _resp_obj({"id": {"type": "string"}, "add": {"type": "string"}}, ["id", "add"]),
        [],
    ),
    # Making a required RESPONSE field optional is breaking (was undetected
    # before LED-1600).
    "led1600_response_required_to_optional_is_breaking": (
        _resp_obj({"id": {"type": "string"}}, ["id"]),
        _resp_obj({"id": {"type": "string"}}, []),
        [("field_requirement_relaxed", "/u:GET:200.id")],
    ),
}


@pytest.mark.parametrize("name", sorted(CONTRACT))
def test_engine_matches_shared_contract(name):
    old, new, expected = CONTRACT[name]
    # LED-1600 direction-aware severity is opt-in (default off). The led1600_*
    # contract cases document that feature's behavior, so exercise it enabled;
    # all other cases assert the conservative default-off baseline.
    changes = OpenAPIDiffEngine(context_aware=name.startswith("led1600")).compare(old, new)
    actual = sorted((c.type.value, c.path) for c in changes if c.is_breaking)
    assert actual == sorted(expected), (
        f"engine drifted from shared contract on '{name}':\n"
        f"  expected breaking: {sorted(expected)}\n"
        f"  actual breaking:   {actual}\n"
        f"If this is an intentional behavior change, update BOTH repos' copies "
        f"of this contract file (LED-1589)."
    )
