#!/usr/bin/env python3
"""Check the bundle against a Horizon checkout, without building anything.

Checks, against the revision in compatibility.json:
  * the checkout is at that commit, or has it in its history;
  * every `hook` + `hook_version` the manifest names is in native-hooks.json;
  * every raw `target` resolves the way horizon-mixins resolves one: crate
    (`extern crate self as <name>;`), then module by module to its file, then
    the method inside the right `impl`;
  * the module file and the helper files the manifest names exist.

Usage: python3 tools/check_compat.py --horizon ../horizon
Exit status is nonzero with what is wrong otherwise. This is a source check
only: `horizon-mixins check --trust-native-mods` still compiles the stage.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    sys.exit("needs Python 3.11+ (tomllib)")

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "mixins" / "freelook"
COMPAT = json.loads((ROOT / "compatibility.json").read_text())

# `pub mod x {` / `mod x;` / `#[path = "..."] mod x;`
MOD_RE = re.compile(r"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+([A-Za-z_][A-Za-z0-9_]*)\s*(;|\{)")
PATH_ATTR_RE = re.compile(r'#\[path\s*=\s*"([^"]+)"\]\s*$')


def stripped(text):
    """Source without comments and string/char literals (for block scans)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r'r#*"(\\.|[^"\\])*"#*', '""', text, flags=re.S)
    text = re.sub(r'"(\\.|[^"\\\n])*"', '""', text)
    text = re.sub(r"'(\\.|[^'\\\n])'", "''", text)
    return text


def block_at(text, open_index):
    """The text between `open_index`'s `{` and its matching `}`."""
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_index + 1 : i]
    return ""


class Crate:
    def __init__(self, name, root_file):
        self.name = name
        self.root_file = root_file

    def file_of(self, modules):
        """The file holding `modules` below the crate root, or None."""
        path = self.root_file
        text = stripped(path.read_text(errors="replace"))
        for module in modules:
            found = None
            for match in MOD_RE.finditer(text):
                if match.group(1) != module:
                    continue
                found = match
                break
            if found is None:
                return None
            before = text[: found.start()].rstrip()
            attr = PATH_ATTR_RE.search(before.splitlines()[-1] if before else "")
            # A module's files are next to `lib.rs` and `game.rs`, or in its
            # own folder under a submodule's directory.
            base = path.parent / path.stem if path.stem not in ("lib", "mod") else path.parent
            candidate = None
            if attr:
                candidate = base / attr.group(1)
            elif found.group(2) == "{":
                # Inline: keep looking inside this block.
                offset = text.index("{", found.start())
                text = block_at(text, offset)
                continue
            else:
                flat = base / f"{found.group(1)}.rs"
                nested = base / found.group(1) / "mod.rs"
                for option in (flat, nested):
                    if option.is_file():
                        candidate = option
                        break
            if candidate is None or not candidate.is_file():
                return None
            path = candidate
            text = stripped(path.read_text(errors="replace"))
        return path


def crates(horizon):
    """Crate name (as `extern crate self as` spells it) → root file."""
    out = {}
    for manifest in sorted(horizon.glob("crates/*/Cargo.toml")):
        text = manifest.read_text(errors="replace")
        lib = re.search(r'(?m)^\[lib\]\s*$([\s\S]*?)(?=^\[|\Z)', text)
        if lib and re.search(r'(?m)^\s*path\s*=', lib.group(1)):
            rel = re.search(r'(?m)^\s*path\s*=\s*"([^"]+)"', lib.group(1)).group(1)
        elif (manifest.parent / "src" / "lib.rs").is_file():
            rel = "src/lib.rs"
        else:
            continue
        root = (manifest.parent / rel).resolve()
        if not root.is_file():
            continue
        names = set(re.findall(r"extern\s+crate\s+self\s+as\s+([A-Za-z_][A-Za-z0-9_]*)", root.read_text(errors="replace")))
        package = re.search(r'(?m)^name\s*=\s*"([^"]+)"', text)
        if not names and package:
            names.add(package.group(1).replace("-", "_"))
        for name in names:
            out.setdefault(name, Crate(name, root))
    return out


def resolve_target(target, modules):
    """(ok, explanation) for a horizon-mixins style target path."""
    parts = target.split("::")
    crate = modules.get(parts[0])
    if crate is None:
        return False, f"no crate named {parts[0]!r} in the checkout"
    rest = parts[1:]
    # Module segments are lowercase idents; the first type (`Game<'_>`, a
    # struct) ends them, and the last segment is the function or method.
    split = next(
        (i for i, part in enumerate(rest) if part[:1].isupper() or part.startswith("<")),
        len(rest),
    )
    module_path, tail = rest[:split], rest[split:]
    path = crate.file_of(module_path)
    if path is None:
        return False, f"no module {'::'.join(module_path)} under {crate.root_file}"
    if not tail:
        return False, "target names a module, not a function"
    function = tail[-1]
    text = stripped(path.read_text(errors="replace"))
    if len(tail) == 1:
        if re.search(rf"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?(?:const\s+)?(?:async\s+)?fn\s+{re.escape(function)}\b", text):
            return True, str(path)
        return False, f"no function {function} in {path}"
    owner = re.sub(r"<.*", "", tail[0])
    for match in re.finditer(rf"(?m)^\s*impl(?:<[^>]*>)?\s+{re.escape(owner)}\b[^{{]*\{{", text):
        open_index = text.index("{", match.start())
        if re.search(rf"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?(?:const\s+)?(?:async\s+)?fn\s+{re.escape(function)}\b", block_at(text, open_index)):
            return True, str(path)
    return False, f"no `{tail[0]}::{function}` in {path}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", required=True, type=Path)
    args = parser.parse_args()
    horizon = args.horizon.resolve()
    pin = COMPAT["horizon_revision"]
    errors = []

    head = subprocess.run(
        ["git", "-C", str(horizon), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if not head.startswith(pin):
        known = subprocess.run(
            ["git", "-C", str(horizon), "cat-file", "-e", f"{pin}^{{commit}}"],
            capture_output=True,
        ).returncode == 0
        if not known:
            errors.append(f"the checkout has no commit {pin} (HEAD {head})")
        else:
            print(f"note: HEAD is {head[:12]}; the pin is in the history and staging exports it")

    manifest = tomllib.loads((BUNDLE / "horizon-mixin.toml").read_text())
    stated = manifest.get("compatibility", {}).get("horizon_revision")
    if stated != pin:
        errors.append(f"horizon-mixin.toml pins {stated}, compatibility.json pins {pin}")

    catalog = {}
    catalog_file = horizon / "native-hooks.json"
    if catalog_file.is_file():
        for hook in json.loads(catalog_file.read_text())["hooks"]:
            catalog[(hook["name"], hook["version"])] = hook["target"]
    else:
        errors.append("the checkout has no native-hooks.json")

    modules = crates(horizon)
    for injection in manifest.get("injection", []):
        where = f"injection {injection['id']!r}"
        target = injection.get("target")
        if "hook" in injection:
            key = (injection["hook"], injection.get("hook_version"))
            resolved = catalog.get(key)
            if resolved is None:
                have = sorted(v for (n, v) in catalog if n == key[0])
                errors.append(f"{where}: hook {key[0]!r} v{key[1]} is not in native-hooks.json (has {have})")
                continue
            target = resolved
        if not target:
            errors.append(f"{where}: neither hook nor target")
        else:
            ok, why = resolve_target(target, modules)
            if not ok:
                errors.append(f"{where}: {why}")
        if not (BUNDLE / injection["helper"]).is_file():
            errors.append(f"{where}: helper {injection['helper']} is missing")

    for module in manifest.get("module", []):
        if not (BUNDLE / module["source"]).is_file():
            errors.append(f"module {module['id']!r}: {module['source']} is missing")
        if not (horizon / module["file"]).is_file():
            errors.append(f"module {module['id']!r}: the checkout has no {module['file']}")

    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"ok: bundle {manifest['mod']['id']} {manifest['mod']['version']} fits {pin[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
