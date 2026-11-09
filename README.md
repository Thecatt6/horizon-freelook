# horizon-freelook

Freelook mod for [Horizon](https://github.com/horizon-rust/horizon): hold a key
(X by default) for a third person camera you can look around in, scroll to
change the distance. Your character keeps facing (and aiming) where it did;
on release the camera goes back to what it was.

It is a native mixin bundle, applied by
[horizon-mixins](https://github.com/horizon-rust/horizon-mixins).

## Compatibility

| | |
|---|---|
| Horizon | `fdc87aecdbd116bf1e08adcd062fcbaea8c2e2ca` (Nightly 2026-11-08, game 26.3) |
| horizon-mixins | `5a64af938ec86b00d53d16a408aabc0038fb3e57` (0.6.0, plan schema 6) |
| Rust | 1.95 |

`compatibility.json` holds the same pins. The bundle pins
`[compatibility] horizon_revision`, so a build on another commit is refused by
the launcher (`native-build --allow-version-mismatch` builds anyway).

## What it hooks

| Injection | Kind | Target | Does |
|---|---|---|---|
| `key` | HEAD | hook `key` (`native_key`) | starts/stops freelook, remembers the camera to return to |
| `turn` | HEAD, cancellable | `game::perspective::Game<'_>::turn_player` | the mouse (and pad, arrow keys) turns the camera's angles, not the player's |
| `distance` | HEAD | hook `camera_distance` (`native_camera_distance`) | the wheel's distance, before a wall pulls the camera in |
| `camera` | HEAD, cancellable | `game::perspective::Game<'_>::camera_view` | renders from the camera's angles while the key is held |
| `wheel` | HEAD | hook `wheel` (`native_wheel`) | the wheel moves the camera, not the hotbar |
| `list` | HEAD | hook `mods` (`native_mods`) | the Options > Mods row and its key setting |

The four named hooks are resolved from the game's `native-hooks.json`, so they
survive a move of those functions in the source. `turn` and `camera` are
private methods of `game/perspective.rs` (both used to live in `game.rs`), so
they are exact paths, which is why the bundle pins the commit.

`runtime.rs` is both the bundle's injected module (`crate::game::freelook`) and
the crate's library, so `cargo test` runs its unit tests without a Horizon
checkout.

## Build

Clone Horizon and horizon-mixins beside this repository at the pinned
revisions, then plan and stage:

```sh
cargo build --locked -p horizon-mixins-cli
./target/debug/horizon-mixins apply \
  --workspace ../horizon --mods mixins --out ../freelook-game
```

Or, with the launcher (`FOLDER` is this repository's `mixins` directory):

```sh
horizon-launcher native-build mixins --instance NAME --trust-native-code
```

`horizon-mixins check ... --trust-native-mods` compiles the staged workspace
and runs its tests. Nothing here downloads Minecraft assets: preparing
resources and signing in stay the launcher's job.

## Limits

- The look is the camera's angles only: the player's body, arms and held item
  keep pointing where they did (that is the point), and so does the player's
  model head — it does not turn with the look.
- Freelook stays off while a server puts the view on another entity
  (`camera` attachment, spectator mob) and in first person: pressing F5 during
  freelook switches the camera as usual.
- The wheel's distance starts at the game's own 4 blocks each time the key goes
  down, and a wall behind the player still pulls the camera in.

## Checking a bundle

`tools/check_compat.py` resolves the manifest against a Horizon checkout
without building: the pinned revision, the named hooks in `native-hooks.json`,
every raw `target` (crate → modules → file → `impl`), the module file and the
helpers.

```sh
python3 tools/check_compat.py --horizon ../horizon
```

## Making the `.hnmod`

A `.hnmod` is the zip the launcher installs: `horizon-native.json` at the root
(schema 1, the mod id and version, the game version, the exact Horizon and
horizon-mixins commits) and the bundle's sources under `mixins/<id>/` — only
`.rs`, `.toml`, `data/` files and a crate's README/LICENSE. It is the same zip
`horizon_launcher::github_mods::pack` writes from a folder, built here without
compiling the launcher:

```sh
python3 tools/pack_hnmod.py              # ./freelook-0.4.0.hnmod + its SHA-256
python3 tools/pack_hnmod.py --out dist   # somewhere else
python3 tools/pack_hnmod.py --check dist/freelook-0.4.0.hnmod   # read it as the launcher does
```

The manifest is made from the bundle itself, so bumping `[mod] version` in
`horizon-mixin.toml` is enough; the packer refuses a bundle without
`[compatibility] horizon_revision`.

### Installing it

- **In the launcher**, the file installs a mod the launcher then builds: the
  Mods page (**Open folder** opens `<instance>/horizon-native-mods/`) is where
  a `.hnmod` goes, then build with `horizon-launcher native-build --instance
  NAME --trust-native-code` (or `native-build` with no folder, which builds the
  installed native mods that are turned on).
- **By hand**, drop it in `<instance>/horizon-native-mods/freelook.hnmod` and
  add `mod.freelook:true` to `<instance>/horizon-mods.txt` (or turn it on in
  Options > Mods): that is what the launcher does when it installs one.
- **Building a folder directly** works too and skips the file entirely:
  `horizon-launcher native-build mixins --instance NAME --trust-native-code`.

The mod is built on the Horizon commit it pins (`fdc87ae`), so the instance
needs a version whose source that commit is, or the launcher asks before
building on the newest pinned commit anyway (`--allow-version-mismatch`).
