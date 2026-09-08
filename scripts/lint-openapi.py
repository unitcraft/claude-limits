# -*- coding: utf-8 -*-
"""Lint the API contract against the rules 01.5 T2.18 lists.

    python scripts/lint-openapi.py <spec.json>

WHAT THIS IS NOT. There is no `openapi_spec_validator` on this machine (checked:
ImportError), so "valid against the OpenAPI 3.x schema" is NOT what happens here.
What happens is a STRUCTURAL check of the parts the other rules depend on --
`openapi`, `info`, `paths`, an operation object per method, `responses` on each. A
linter that claimed schema validation it does not perform would be worse than one
that checks less and says so, because the claim is what the next reader would trust.

WHERE THE ROUTE LIST COMES FROM. Not from a copy kept here: the table in
`docs/plans/01.3-api.md` section 2 is parsed, so a route added to the contract
without being added to the spec -- or the reverse -- is what the check is FOR, and a
second list in this file would just drift away from the first.

The phase-6 routes are excluded by name, because the table does not mark them. The
exclusion is checked against the table too: if one of these ever disappears or is
renamed, the exclusion goes stale silently, and a stale exclusion hides a missing
route rather than reporting one.
"""
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
API_PLAN = REPO / "docs" / "plans" / "01.3-api.md"

# Phase 6 is LAN access over TLS with browser sessions (plan 01, "Ф.6"): deliberately
# out of the contract until that phase lands.
PHASE_6 = {
    "GET /login",
    "POST /api/session",
    "POST /api/session/token",
    "DELETE /api/session",
}

# Parameters that must never appear in a URL: a personal e-mail, a filesystem path, a
# secret, or an account identity. 01.3 forbids them in query and path -- URLs are
# logged, cached by proxies and pasted into chats, so PII in one leaks in every copy.
FORBIDDEN_PARAM_NAMES = ("email", "path", "token", "account_id")

MAX_SCHEMA_DEPTH = 3

PII_HINTS = ("email", "mail", "path", "dir", "folder")
ID_HINTS = ("id", "uuid", "etag", "request_id")


def routes_from_plan():
    """Every `| `METHOD /path` |` row of the section-2 table."""
    rows = set()
    for line in API_PLAN.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*`(GET|POST|PUT|DELETE|PATCH|HEAD) ([^`]+)`\s*\|", line)
        if m:
            rows.add(f"{m.group(1)} {m.group(2)}")
    return rows


def resolve(node, spec, depth=0):
    """Follow a local `$ref` so a check reads the thing, not the pointer to it.

    A contract that spells its error body out eighteen times is a contract nobody
    keeps consistent, so `$ref: #/components/responses/Error` is the NORMAL shape --
    and a checker that cannot see through it reports every error response as broken.
    """
    if not isinstance(node, dict) or depth > 8:
        return node
    ref = node.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return node
    target = spec
    for part in ref[2:].split("/"):
        if not isinstance(target, dict) or part not in target:
            return node                      # a dangling ref: leave it as it is
        target = target[part]
    return resolve(target, spec, depth + 1)


def norm(path):
    """`/api/history` and `/assets/{*path}` compare by shape, not by parameter name."""
    return re.sub(r"\{[^}]*\}", "{}", path.rstrip("/") or "/")


def schema_depth(node, seen=None):
    """Nesting of an inline schema. A $ref is depth 1: it is a name, not a nest."""
    if not isinstance(node, dict):
        return 0
    if "$ref" in node:
        return 1
    seen = seen or set()
    if id(node) in seen:
        return 1                      # a cycle is not infinitely deep for our purpose
    seen = seen | {id(node)}
    inner = 0
    for key in ("properties", "patternProperties"):
        for sub in (node.get(key) or {}).values():
            inner = max(inner, schema_depth(sub, seen))
    for key in ("items", "additionalProperties"):
        sub = node.get(key)
        if isinstance(sub, dict):
            inner = max(inner, schema_depth(sub, seen))
    for key in ("allOf", "anyOf", "oneOf"):
        for sub in node.get(key) or []:
            inner = max(inner, schema_depth(sub, seen))
    return 1 + inner


def walk_properties(node, trail=()):
    """Every named property in a schema, with the trail that reached it."""
    if not isinstance(node, dict):
        return
    for name, sub in (node.get("properties") or {}).items():
        yield trail + (name,), sub
        yield from walk_properties(sub, trail + (name,))
    for key in ("items", "additionalProperties"):
        sub = node.get(key)
        if isinstance(sub, dict):
            yield from walk_properties(sub, trail)
    for key in ("allOf", "anyOf", "oneOf"):
        for sub in node.get(key) or []:
            yield from walk_properties(sub, trail)


def main(argv):
    if len(argv) != 2:
        print("usage: lint-openapi.py <spec.json>")
        return 2
    spec_path = pathlib.Path(argv[1])
    if not spec_path.exists():
        print(f"FAILED: {spec_path} does not exist")
        return 1

    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FAILED: {spec_path} is not JSON: {e}")
        return 1

    bad = []

    # --- 1. structural (NOT schema validation -- see the header) ----------------
    if not re.match(r"^3\.", str(spec.get("openapi", ""))):
        bad.append(f'openapi: expected a 3.x version, got {spec.get("openapi")!r}')
    info = spec.get("info") or {}
    for field in ("title", "version"):
        if not info.get(field):
            bad.append(f"info.{field}: missing")
    paths = spec.get("paths")
    if not isinstance(paths, dict) or not paths:
        print("FAILED: paths is missing or empty -- nothing to lint")
        return 1

    methods = ("get", "post", "put", "delete", "patch", "head")
    described = set()
    for path, item in paths.items():
        if not isinstance(item, dict):
            bad.append(f"paths.{path}: not an object")
            continue
        for method in methods:
            op = item.get(method)
            if op is None:
                continue
            if not isinstance(op, dict):
                bad.append(f"{method.upper()} {path}: not an operation object")
                continue
            described.add(f"{method.upper()} {norm(path)}")
            responses = op.get("responses")
            if not isinstance(responses, dict) or not responses:
                bad.append(f"{method.upper()} {path}: no responses")
                continue

            # --- 3. every error answers with a Problem ----------------------
            for code, body in responses.items():
                if not re.match(r"^[45]\d\d$", str(code)):
                    continue
                # Read through the reference: see resolve().
                blob = json.dumps(resolve(body, spec)) + json.dumps(body)
                if "Problem" not in blob:
                    bad.append(f"{method.upper()} {path} {code}: does not reference Problem "
                               f"(RFC 9457 is the only error shape this API has)")

            # --- 4. no PII or secrets in the URL ----------------------------
            for param in (op.get("parameters") or []) + (item.get("parameters") or []):
                if not isinstance(param, dict):
                    continue
                where, name = param.get("in"), str(param.get("name", ""))
                if where in ("query", "path") and name.lower() in FORBIDDEN_PARAM_NAMES:
                    bad.append(f"{method.upper()} {path}: parameter `{name}` in {where} "
                               f"-- URLs are logged, cached and pasted")

            # --- 5. response schemas stay shallow ---------------------------
            for code, body in responses.items():
                for ctype, media in ((body or {}).get("content") or {}).items():
                    depth = schema_depth((media or {}).get("schema") or {})
                    if depth > MAX_SCHEMA_DEPTH:
                        bad.append(f"{method.upper()} {path} {code} ({ctype}): schema nests "
                                   f"{depth} deep, limit is {MAX_SCHEMA_DEPTH}")

    # --- 2. every route of the contract is described ---------------------------
    planned = routes_from_plan()
    if not planned:
        bad.append("could not parse the route table out of 01.3 section 2 -- the check "
                   "that every route is described did NOT run")
    missing_exclusions = PHASE_6 - planned
    if missing_exclusions:
        bad.append("phase-6 exclusions no longer in the plan's table (stale exclusion "
                   f"hides a real gap): {sorted(missing_exclusions)}")
    for route in sorted(planned - PHASE_6):
        method, path = route.split(" ", 1)
        if f"{method} {norm(path)}" not in described:
            bad.append(f"{route}: in 01.3 section 2, absent from the contract")

    # --- 6. personal data is labelled ------------------------------------------
    for name, schema in ((spec.get("components") or {}).get("schemas") or {}).items():
        for trail, sub in walk_properties(schema):
            leaf = trail[-1].lower()
            # A container is not the datum: `dirs` is an array of objects, and the
            # label belongs on the leaf inside it that actually holds a path.
            scalar = (sub or {}).get("type") in ("string", "integer", "number", "boolean")
            if scalar and any(h in leaf for h in PII_HINTS) and not any(h == leaf for h in ID_HINTS):
                if (sub or {}).get("x-data-class") != "pii":
                    bad.append(f"components.schemas.{name}.{'.'.join(trail)}: looks like "
                               f"personal data and carries no x-data-class: pii")

    print(f"routes in 01.3 section 2: {len(planned)} "
          f"({len(PHASE_6)} deferred to phase 6), described: {len(described)}")
    print("OPENAPI LINT:", "clean" if not bad else "FAILED")
    for b in bad:
        print("  ", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
