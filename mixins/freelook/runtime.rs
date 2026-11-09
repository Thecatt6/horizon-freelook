// Freelook: hold a key (X by default) for a third person view (like F5) you
// can look around in: the mouse turns only the camera, the wheel changes its
// distance, and the player keeps walking and aiming where they faced. On
// release the camera goes back to what it was. This file is both the mod's
// Cargo library (its tests run with `cargo test`) and the module the bundle
// adds to the game as crate::game::freelook.
use std::cell::Cell;

pub const ID: &str = "freelook";
pub const VERSION: &str = "0.4.0";
pub const DESCRIPTION: &str = "Hold a key for a third person view you can look around in while your character keeps facing the same way; the wheel changes the camera distance.";
/// The key's name, and its default.
pub const KEY: &str = "freelook";
pub const DEFAULT_KEY: &str = "key.keyboard.x";
/// The distance the camera starts at (the game's own), and the farthest and
/// the closest the wheel moves it, in blocks.
pub const DEFAULT_OUT: f32 = 4.0;
pub const MAX_OUT: f32 = 24.0;
pub const MIN_OUT: f32 = 1.0;

#[derive(Clone, Copy)]
struct State {
    /// The key is down.
    held: bool,
    /// The camera's (yaw, pitch) while held; None until first used.
    look: Option<(f32, f32)>,
    /// One of our hooks is calling the game's own function again.
    busy: bool,
    /// Camera distance in blocks, set with the wheel (the game's own is 4);
    /// each time freelook starts it starts from there again.
    out: f32,
    /// The camera type before the key went down: 0 first person, 1 third
    /// person behind, 2 in front.
    before: u8,
}

thread_local! {
    static STATE: Cell<State> = const {
        Cell::new(State { held: false, look: None, busy: false, out: DEFAULT_OUT, before: 0 })
    };
}

fn update(f: impl FnOnce(&mut State)) {
    STATE.with(|s| {
        let mut v = s.get();
        f(&mut v);
        s.set(v);
    });
}

/// The freelook key went down (only while playing) or up: Some(true) when
/// freelook starts, Some(false) when it ends, None when nothing changed
/// (key repeat, or a press over a screen).
pub fn key(playing: bool, pressed: bool) -> Option<bool> {
    let mut change = None;
    update(|s| {
        if (pressed && (!playing || s.held)) || (!pressed && !s.held) {
            return;
        }
        s.held = pressed;
        s.look = None;
        s.out = DEFAULT_OUT;
        change = Some(pressed);
    });
    change
}

/// Remembers the camera type to go back to (see `State::before`).
pub fn set_before(kind: u8) {
    update(|s| s.before = kind);
}

pub fn before() -> u8 {
    STATE.with(|s| s.get().before)
}

pub fn held() -> bool {
    STATE.with(|s| s.get().held)
}

/// Wheel steps (up is positive): true when the key is held and they move
/// the camera closer (up) or away (down) instead of the hotbar.
pub fn wheel(steps: f32) -> bool {
    let mut held = false;
    update(|s| {
        held = s.held;
        if held && steps.is_finite() {
            s.out = (s.out - steps).clamp(MIN_OUT, MAX_OUT);
        }
    });
    held
}

/// The camera's distance in blocks while freelook is on: what the game's
/// third person camera is told to use, before it is pulled in by a wall.
pub fn distance() -> Option<f32> {
    let s = STATE.with(|s| s.get());
    s.held.then_some(s.out)
}

/// Starts a hooked call; false when one is already running (the game's own
/// function, called again by our hook, must run unchanged).
pub fn begin() -> bool {
    let s = STATE.with(|s| s.get());
    if !s.held || s.busy {
        return false;
    }
    update(|s| s.busy = true);
    true
}

pub fn end() {
    update(|s| s.busy = false);
}

/// The camera's (yaw, pitch): the stored one, or the player's own
/// (`yaw`, `pitch`) the first time after the key went down.
pub fn look(yaw: f32, pitch: f32) -> (f32, f32) {
    let mut out = (yaw, pitch);
    update(|s| out = *s.look.get_or_insert((yaw, pitch)));
    out
}

pub fn set_look(yaw: f32, pitch: f32) {
    update(|s| s.look = Some((yaw, pitch.clamp(-90.0, 90.0))));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn holds_and_lets_go() {
        assert_eq!(key(false, true), None, "not while a screen is open");
        assert!(!held());
        assert_eq!(key(true, true), Some(true));
        assert_eq!(key(true, true), None, "key repeat");
        assert!(held());
        assert_eq!(look(10.0, 5.0), (10.0, 5.0));
        set_look(40.0, 120.0);
        assert_eq!(look(10.0, 5.0), (40.0, 90.0));
        assert_eq!(key(false, false), Some(false));
        assert_eq!(key(false, false), None);
        assert!(!held());
        assert_eq!(key(true, true), Some(true));
        assert_eq!(look(1.0, 2.0), (1.0, 2.0), "starts from the player again");
        key(true, false);
    }

    #[test]
    fn the_wheel_moves_the_camera_while_held() {
        assert!(!wheel(1.0));
        assert_eq!(distance(), None);
        key(true, true);
        assert_eq!(distance(), Some(4.0));
        assert!(wheel(-6.0));
        assert_eq!(distance(), Some(10.0));
        assert!(wheel(100.0));
        assert_eq!(distance(), Some(MIN_OUT));
        assert!(wheel(-100.0));
        assert_eq!(distance(), Some(MAX_OUT));
        assert!(wheel(f32::NAN));
        assert_eq!(distance(), Some(MAX_OUT), "a broken step changes nothing");
        key(true, false);
        assert_eq!(distance(), None);
        key(true, true);
        assert_eq!(distance(), Some(DEFAULT_OUT), "the next hold starts over");
    }

    #[test]
    fn remembers_the_camera_to_return_to() {
        set_before(2);
        assert_eq!(before(), 2);
    }

    #[test]
    fn a_hooked_call_is_not_hooked_twice() {
        key(true, true);
        assert!(begin());
        assert!(!begin());
        end();
        assert!(begin());
        end();
        key(true, false);
        assert!(!begin());
    }
}
