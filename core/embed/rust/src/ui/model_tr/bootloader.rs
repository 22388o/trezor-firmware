use super::{
    component::{ButtonPage, Frame},
    theme, constant,
};
use crate::{ui::component::text::paragraphs::Paragraphs, trezorhal::display};
use crate::ui::component::Component;
use cstr_core::CStr;

#[no_mangle]
extern "C" fn hello_world(text: *const cty::c_char) {
    let text = unsafe { CStr::from_ptr(text).to_str().unwrap() };
    let mut frame = Frame::new(
        "Hello World",
        ButtonPage::new(
            Paragraphs::new()
                .add::<theme::TRDefaultText>(theme::FONT_NORMAL, text)
                .add::<theme::TRDefaultText>(theme::FONT_BOLD, "bold"),
            theme::BG,
        ),
    );
    frame.place(constant::screen());
    frame.paint();
}
