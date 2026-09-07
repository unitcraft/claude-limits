"""Check the agent's full-valid.toml against the inventory it was built from.

Two directions, both required:
  * every inventory key appears in the TOML (active or commented) — nothing lost;
  * every TOML key appears in the inventory — nothing invented.
"""
import pathlib, re, tomllib

repo = pathlib.Path(r"<repos>\claude-limits")
inv = repo / "docs" / "reports" / "T1.2-config-inventory.md"
toml = repo / "fixtures" / "config" / "full-valid.toml"

# Inventory keys: first column, backticked.
inv_keys = []
for line in inv.read_text(encoding="utf-8").splitlines():
    if line.startswith("| `"):
        m = re.match(r"\| `([^`]+)`", line)
        if m:
            inv_keys.append(m.group(1))

text = toml.read_text(encoding="utf-8")

# Active keys, from the parsed document (flattened to dotted paths).
doc = tomllib.loads(text)
active = set()
def walk(node, prefix=""):
    for k, v in node.items():
        path = f"{prefix}{k}"
        if isinstance(v, dict):
            walk(v, path + ".")
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            for item in v:
                walk(item, f"[[{path}]].")
        else:
            active.add(path)
walk(doc)

# Commented-out keys: "# name = ..." lines, resolved against the section above them.
commented = set()
section = ""
for line in text.splitlines():
    s = line.strip()
    if s.startswith("[[") and s.endswith("]]"):
        section = f"[[{s[2:-2]}]]."
    elif s.startswith("[") and s.endswith("]"):
        section = s[1:-1] + "."
    m = re.match(r"#\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", s)
    if m:
        commented.add(section + m.group(1))

present = active | commented
inv_set = set(inv_keys)

lost = sorted(inv_set - present)
invented = sorted(present - inv_set)

print(f"inventory keys : {len(inv_set)}")
print(f"toml active    : {len(active)}")
print(f"toml commented : {len(commented)}")
print(f"toml total     : {len(present)}")
print()
print("LOST (in inventory, missing from toml):", lost if lost else "none")
print("INVENTED (in toml, absent from inventory):", invented if invented else "none")
raise SystemExit(1 if (lost or invented) else 0)
