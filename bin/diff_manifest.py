#!/usr/bin/env python3
"""
Diff two DB manifest YAMLs and list entry keys whose version/checksum changed.

Usage: diff_manifest.py <old_manifest.yaml> <new_manifest.yaml> <changed_entries.txt>

If <old_manifest.yaml> does not exist (no prior setup run), every entry in the
new manifest is considered changed.
"""
import sys
import os

from build_setup_report import parse_manifest


def entries_of(path):
    if not path or not os.path.isfile(path):
        return {}
    data = parse_manifest(path)
    if not data:
        return {}
    genome = list(data.keys())[0]
    return data[genome]


def changed_keys(old_entries, new_entries):
    changed = []
    for key, new_e in new_entries.items():
        old_e = old_entries.get(key)
        if old_e is None:
            changed.append(key)
            continue
        if new_e.get("version", "") != old_e.get("version", ""):
            changed.append(key)
            continue
        if new_e.get("expected_sha256", "") != old_e.get("expected_sha256", ""):
            changed.append(key)
    return changed


def main():
    if len(sys.argv) != 4:
        sys.exit(f"Usage: {sys.argv[0]} <old_manifest.yaml> <new_manifest.yaml> <changed_entries.txt>")

    old_path, new_path, out_path = sys.argv[1:4]

    old_entries = entries_of(old_path)
    new_entries = entries_of(new_path)

    changed = changed_keys(old_entries, new_entries)

    with open(out_path, "w") as f:
        for key in changed:
            f.write(key + "\n")

    print(f"[diff_manifest] {len(changed)}/{len(new_entries)} entries changed.")


if __name__ == "__main__":
    main()
