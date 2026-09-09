# -*- coding: utf-8 -*-
"""The contract linter's blacklist of PII parameter names is a hand-kept copy,
and it is already shorter than the list the convention names.

Two specs, both built from the project's own fixtures/openapi/sample.json (which
the linter calls clean today):

  control.json : ?email=...      -- a name the copy carries      -> expect FAILED
  gap.json     : ?user_id=..., ?person_id=..., ?phone=...,
                 and /{user_id} in a path                        -> expect clean

Everything is written into this directory; nothing in the repository is touched.

Run:  python probe.py
"""
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
SAMPLE = REPO / "fixtures" / "openapi" / "sample.json"
LINTER = REPO / "scripts" / "lint-openapi.py"


def param(name, where="query"):
    return {"name": name, "in": where, "required": False, "schema": {"type": "string"}}


def build(name, params, extra_path=None):
    spec = json.loads(SAMPLE.read_text(encoding="utf-8"))
    op = spec["paths"]["/api/snapshot"]["get"]
    op["parameters"] = (op.get("parameters") or []) + params
    if extra_path:
        # the same operation object under a path templated by a subject id
        spec["paths"][extra_path] = json.loads(json.dumps(spec["paths"]["/api/snapshot"]))
        spec["paths"][extra_path]["get"]["parameters"] = [param("user_id", "path")]
    out = HERE / name
    out.write_text(json.dumps(spec, indent=1), encoding="utf-8")
    return out


def run(path):
    p = subprocess.run([sys.executable, str(LINTER), str(path)],
                       capture_output=True, text=True, cwd=str(REPO))
    return p.returncode, p.stdout.strip()


control = build("control.json", [param("email")])
gap = build("gap.json",
            [param("user_id"), param("person_id"), param("phone"), param("inn"),
             param("last_name"), param("api_key")],
            extra_path="/api/people/{user_id}")

print("convention api.md section 2.3 names, verbatim:")
print("  `email`, `phone`, `inn`, `passport`, `*_name`, `person_id`, `user_id`, `token`, `key`")
print("the linter's copy, scripts/lint-openapi.py:43:")
print('  FORBIDDEN_PARAM_NAMES = ("email", "path", "token", "account_id")')
print()

for title, spec in (("CONTROL  ?email=", control), ("GAP      ?user_id= &person_id= &phone= &inn= &last_name= &api_key= and /{user_id}", gap)):
    code, out = run(spec)
    verdict = [l for l in out.splitlines() if l.startswith("OPENAPI LINT")]
    named = [l.strip() for l in out.splitlines() if "parameter `" in l]
    print(f"{title}")
    print(f"   exit={code}   {verdict[0] if verdict else out.splitlines()[-1]}")
    for l in named:
        print(f"   {l}")
    if not named:
        print("   (no parameter reported)")
    print()
