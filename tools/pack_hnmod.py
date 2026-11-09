#!/usr/bin/env python3
"""Pack the bundle into the `.hnmod` the launcher installs.

The zip is the one `horizon_launcher::github_mods::pack` makes: a manifest
(`horizon-native.json`) with the pins taken from the bundle's own
`horizon-mixin.toml`, then the bundle's sources under `mixins/<id>/`, keeping
the files `horizon_mods::index::native::allowed` allows (`.rs`, `.toml`,
`data/`, and a crate's README/LICENSE/.gitignore). Same entries, same bytes,
fixed timestamps, so the same sources give the same file.

Usage:
  python3 tools/pack_hnmod.py                 # writes freelook-<version>.hnmod
  python3 tools/pack_hnmod.py --out dist/     # another folder (created)
  python3 tools/pack_hnmod.py --check FILE    # re-read FILE as Bundle::read does
"""
import argparse
import hashlib
import json
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "mixins" / "freelook"
COMPAT = json.loads((ROOT / "compatibility.json").read_text())
MANIFEST = "horizon-native.json"
CHECKED = ("README", "LICENSE", "LICENCE", "COPYING", "NOTICE")


def allowed(rest: str) -> bool:
    """Whether a bundle may carry `rest` (its path under `mixins/<id>/`)."""
    parts = rest.split("/")
    in_data = len(parts) >= 2 and (parts[0] == "data" or (len(parts) >= 3 and parts[1] == "data"))
    name = parts[-1]
    text = len(parts) <= 2 and (name.startswith(CHECKED) or name == ".gitignore")
    return rest.endswith(".rs") or rest.endswith(".toml") or in_data or text


def bundle_files():
    for path in sorted(BUNDLE.rglob("*")):
        if path.is_file():
            yield path.relative_to(BUNDLE).as_posix()


def manifest_for(text: str):
    mixin = tomllib.loads(text)
    revision = mixin.get("compatibility", {}).get("horizon_revision")
    if not (revision and len(revision) == 40 and all(c in "0123456789abcdef" for c in revision)):
        sys.exit(
            f"{BUNDLE}/horizon-mixin.toml has no [compatibility] horizon_revision "
            "(40 hex digits): add the Horizon commit it was made for."
        )
    return {
        "schema": 1,
        "id": mixin["mod"]["id"],
        "version": mixin["mod"]["version"],
        "game": COMPAT["game"],
        "horizon": revision,
        "mixins": COMPAT["horizon_mixins_revision"],
    }


def pack(out: Path):
    files = list(bundle_files())
    manifest = manifest_for((BUNDLE / "horizon-mixin.toml").read_text())
    entries = [(MANIFEST, json.dumps(manifest, indent=2).encode())]
    for name in files:
        if allowed(name):
            entries.append((f"mixins/{manifest['id']}/{name}", (BUNDLE / name).read_bytes()))
        else:
            print(f"leaving out {name} (not a native bundle file)", file=sys.stderr)
    # Deterministic: fixed time and mode, entries in name order.
    info = zipfile.ZipInfo("x", date_time=(1980, 1, 1, 0, 0, 0))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries):
            member = zipfile.ZipInfo(name, date_time=info.date_time)
            member.external_attr = 0o644 << 16
            member.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(member, data)
    return manifest, len(entries)


def check(path: Path):
    """Read `path` the way `horizon_mods::index::native::Bundle::read` does."""
    errors = []
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            errors.append("the zip is damaged")
        names = [i.filename for i in archive.infolist() if not i.is_dir()]
        if MANIFEST not in names:
            errors.append(f"missing {MANIFEST}")
            return errors, None
        manifest = json.loads(archive.read(MANIFEST))
        unknown = set(manifest) - {"schema", "id", "version", "game", "horizon", "mixins", "hooks"}
        if unknown:
            errors.append(f"{MANIFEST} has unknown fields: {sorted(unknown)}")
        if manifest.get("schema") != 1:
            errors.append("schema is not 1")
        if not manifest.get("version"):
            errors.append("version is empty")
        for key in ("horizon", "mixins"):
            value = manifest.get(key, "")
            if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
                errors.append(f"{key} is not 40 hex digits")
        prefix = f"mixins/{manifest.get('id')}/"
        for name in names:
            if name == MANIFEST:
                continue
            if not name.startswith(prefix) or not allowed(name[len(prefix):]):
                errors.append(f"unexpected native source: {name}")
        mixin_name = f"{prefix}horizon-mixin.toml"
        if mixin_name not in names:
            errors.append(f"missing {mixin_name}")
            return errors, manifest
        mixin = tomllib.loads(archive.read(mixin_name).decode())
        if (
            mixin.get("mod", {}).get("id") != manifest.get("id")
            or mixin.get("mod", {}).get("version") != manifest.get("version")
            or mixin.get("compatibility", {}).get("horizon_revision") != manifest.get("horizon")
        ):
            errors.append("native manifest and mixin identity/revision differ")
        if len(names) > 512:
            errors.append(f"{len(names)} files: the limit is 512")
        size = sum(i.file_size for i in archive.infolist())
        if size > 64 * 1024 * 1024:
            errors.append("more than 64 MiB unpacked")
    return errors, manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    if args.check:
        errors, manifest = check(args.check)
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        if errors:
            return 1
        print(f"ok: {args.check} is {manifest['id']} {manifest['version']} for {manifest['horizon'][:12]}")
        return 0
    args.out.mkdir(parents=True, exist_ok=True)
    version = tomllib.loads((BUNDLE / "horizon-mixin.toml").read_text())["mod"]["version"]
    target = args.out / f"freelook-{version}.hnmod"
    manifest, count = pack(target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    errors, _ = check(target)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    print(f"{target}  ({count} files, {target.stat().st_size} bytes)")
    print(f"sha256 {digest}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
