use super::{
    theme, constant,
    component::Dialog,
    component::Button,
};
use crate::{ui::component::text::formatted::FormattedText, trezorhal::display};
use crate::ui::component::Component;
use cstr_core::CStr;

#[no_mangle]
extern "C" fn hello_world(text: *const cty::c_char) {
    let text = unsafe { CStr::from_ptr(text).to_str().unwrap() };
    let mut frame = Dialog::new(
        FormattedText::new::<theme::TTDefaultText>(
            "Testing text layout, with some text, and some more text. And {param}",
        )
            .with("param", text),
        Button::with_text("Left"),
        Button::with_text("Right"),
    );
    frame.place(constant::screen());
    frame.paint();
}
