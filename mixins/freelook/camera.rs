// While the key is held the view is worked out from the camera's angles (the
// key put the game in third person): the player's own yaw and pitch are put
// back right after, so the body keeps facing, and aiming, the way it did while
// the camera looks elsewhere. The distance is the wheel's, through the
// `camera_distance` hook, which pulls the camera in where a wall is in the way.
// Cancels the original; the nested call runs it unchanged.
fn freelook_camera(
    game: &mut crate::game::Game<'_>,
    partial: f32,
) -> std::ops::ControlFlow<Option<(glam::DVec3, f32, f32)>> {
    use crate::game::freelook as m;
    if !game.native_on(m::ID)
        || !game.native_window()
        || !game.controls_camera()
        || game.camera_type.first_person()
        || !m::begin()
    {
        return std::ops::ControlFlow::Continue(());
    }
    let (yaw, pitch) = (game.yaw, game.pitch);
    let (look_yaw, look_pitch) = m::look(yaw, pitch);
    game.yaw = look_yaw;
    game.pitch = look_pitch;
    let view = game.camera_view(partial);
    game.yaw = yaw;
    game.pitch = pitch;
    m::end();
    std::ops::ControlFlow::Break(view)
}
