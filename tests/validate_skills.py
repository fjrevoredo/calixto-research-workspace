"""Validate that all shipped skills follow the Agent Skills specification."""
import re
import sys
from pathlib import Path

import yaml


SKILL_ROOTS = [
    Path("skills"),
    Path("runtime") / "workspace" / "skills",
]


errors = []
for skill_root in SKILL_ROOTS:
    if not skill_root.exists():
        continue
    for skill_dir in sorted(skill_root.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        label = str(skill_md).replace("\\", "/")
        if not skill_md.exists():
            errors.append(f"{label}: SKILL.md missing")
            continue
        text = skill_md.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not m:
            errors.append(f"{label}: no frontmatter")
            continue
        try:
            fm = yaml.safe_load(m.group(1))
        except yaml.YAMLError as e:
            errors.append(f"{label}: YAML error: {e}")
            continue
        if "name" not in fm:
            errors.append(f"{label}: missing name")
        else:
            name = fm["name"]
            if name != skill_dir.name:
                errors.append(
                    f"{label}: name {name!r} does not match directory {skill_dir.name!r}"
                )
            if not re.match(r"^[a-z0-9](-?[a-z0-9])*$", name):
                errors.append(f"{label}: invalid name format {name!r}")
            if "--" in name:
                errors.append(f"{label}: name contains consecutive hyphens")
            if len(name) > 64:
                errors.append(f"{label}: name too long ({len(name)})")
        if "description" not in fm:
            errors.append(f"{label}: missing description")
        else:
            desc = fm["description"]
            dlen = len(desc)
            if dlen < 1 or dlen > 1024:
                errors.append(
                    f"{label}: description length {dlen} out of range [1, 1024]"
                )
        if "compatibility" in fm and len(fm["compatibility"]) > 500:
            errors.append(f"{label}: compatibility too long")
        body = text[m.end() :]
        body_lines = body.count("\n")
        print(
            f"{label}: name={fm.get('name')!r}, desc_len={len(fm.get('description', ''))}, body_lines={body_lines}"
        )

if errors:
    print("\nERRORS:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("\nAll skills pass spec validation")
