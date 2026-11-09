// While the key is held, the mouse (and a pad, the arrow keys or an agent's
// turn) turns the camera's angles, not the player's: the turn is worked out on
// them and the player's angles are left where they were, so the body keeps
// facing, and the game keeps aiming, the way it did. Extras and screens move
// the player's angles themselves, so nothing else follows when we turn ours.
// Cancels the original.
fn freelook_turn(
    game: &mut crate::game::Game<'_>,
    xo: f64,
    yo: f64,
) -> std::ops::ControlFlow<()> {
    use crate::game::freelook as m;
    if !game.native_on(m::ID)
        || !game.native_window()
        || !game.controls_camera()
        || game.camera_type.first_person()
        || !m::begin()
    {
        return std::ops::ControlFlow::Continue(());
    }
    // `Entity.turn` on the camera's own angles, with the deltas the game
    // passes (the mouse's are already scaled by the zoom and the pad turns
    // write the player's angles directly, so this keeps both as they are).
    let (yaw, pitch) = m::look(game.yaw, game.pitch);
    let mut rotation = crate::mouse::Rotation {
        x_rot: pitch,
        y_rot: yaw,
        x_rot_o: pitch,
        y_rot_o: yaw,
    };
    rotation.turn(xo, yo);
    m::set_look(rotation.y_rot, rotation.x_rot);
    m::end();
    std::ops::ControlFlow::Break(())
}
