// The camera's distance while the key is held: the wheel's, in blocks, before
// the game pulls it in where a wall is in the way. Nothing changes the rest of
// the time.
fn freelook_distance(game: &crate::game::Game<'_>, distance: &mut f32) {
    use crate::game::freelook as m;
    if !game.native_on(m::ID) || !game.native_window() || !game.controls_camera() {
        return;
    }
    if let Some(wanted) = m::distance() {
        *distance = wanted;
    }
}
