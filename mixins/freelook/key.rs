// The freelook key went down or up: third person while it is held (the same
// camera F5 gives, which the camera hook then looks around from), then back to
// the camera the player had.
fn freelook_key(game: &mut crate::game::Game<'_>, key: &str, pressed: bool) {
    use crate::game::freelook as m;
    use crate::game::perspective::CameraType;
    if !game.native_on(m::ID) || !game.native_window() {
        return;
    }
    let bound = game.native_mod_key(m::ID, m::KEY, m::DEFAULT_KEY);
    if key != bound {
        return;
    }
    let playing = game.native_playing();
    match m::key(playing, pressed) {
        Some(true) => {
            m::set_before(match game.camera_type {
                CameraType::FirstPerson => 0,
                CameraType::ThirdPersonBack => 1,
                CameraType::ThirdPersonFront => 2,
            });
            game.camera_type = CameraType::ThirdPersonBack;
        }
        Some(false) => {
            game.camera_type = match m::before() {
                1 => CameraType::ThirdPersonBack,
                2 => CameraType::ThirdPersonFront,
                _ => CameraType::FirstPerson,
            };
        }
        None => {}
    }
}
