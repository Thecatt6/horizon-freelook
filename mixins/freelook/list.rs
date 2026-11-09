// Freelook's row in Options > Mods, with its key. The title carries the
// version, as the page shows a native mod's: `Name 1.0`.
fn freelook_listed(mods: &mut Vec<crate::mod_api::NativeMod>) {
    use crate::game::freelook as m;
    mods.push(crate::mod_api::NativeMod {
        id: m::ID.into(),
        title: format!("Freelook {}", m::VERSION),
        description: m::DESCRIPTION.into(),
        keys: vec![[m::KEY.into(), "Freelook key".into(), m::DEFAULT_KEY.into()]],
    });
}
