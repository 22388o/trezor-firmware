use crate::{
    ui::{
        component::{Component, Event, EventCtx, Pad},
        display,
        geometry::{Point, Rect},
    },
};
use core::ops::Deref;

use super::{theme, BothButtonPressHandler, Button, ButtonMsg, ButtonPos};
use heapless::String;
use heapless::Vec;

pub enum ConfirmWordPageMsg {
    Confirmed,
}

const LEFT_COL: i32 = 5;
const MIDDLE_COL: i32 = 50;
const RIGHT_COL: i32 = 90;

const PIN_ROW: i32 = 40;
const MIDDLE_ROW: i32 = 72;

pub struct ConfirmWordPage<T> {
    prompt: T,
    words: Vec<String<50>, 24>,
    both_button_press: BothButtonPressHandler,
    pad: Pad,
    prev: Button<&'static str>,
    next: Button<&'static str>,
    ok: Button<&'static str>,
    page_counter: u8,
}

impl<T> ConfirmWordPage<T>
where
    T: Deref<Target = str>,
{
    pub fn new(prompt: T, words: Vec<String<50>, 24>) -> Self {
        Self {
            prompt,
            words,
            both_button_press: BothButtonPressHandler::new(),
            pad: Pad::with_background(theme::BG),
            prev: Button::with_text(ButtonPos::Left, "BACK", theme::button_default()),
            next: Button::with_text(ButtonPos::Right, "NEXT", theme::button_default()),
            ok: Button::with_text(ButtonPos::Middle, "OK", theme::button_default()),
            page_counter: 0,
        }
    }

    fn render_header(&self) {
        self.display_text(Point::new(0, 10), &self.prompt);
        display::dotted_line(Point::new(0, 15), 128, theme::FG);
    }

    fn update_situation(&mut self) {
        // So that only relevant buttons are visible
        self.pad.clear();

        // MIDDLE section above buttons
        if self.page_counter == 0 {
            self.show_current_word();
            self.show_next_word();
        } else if self.page_counter < self.last_page_index() {
            self.show_previous_word();
            self.show_current_word();
            self.show_next_word();
        } else if self.page_counter == self.last_page_index() {
            self.show_previous_word();
            self.show_current_word();
        }
    }

    fn last_page_index(&self) -> u8 {
        self.words.len() as u8 - 1
    }

    pub fn get_current_word(&self) -> &str {
        &self.words[self.page_counter as usize]
    }

    fn show_current_word(&self) {
        let current = self.get_current_word();
        self.display_text(Point::new(62, MIDDLE_ROW), &current);
    }

    fn show_previous_word(&self) {
        if self.page_counter > 0 {
            let previous = &self.words[(self.page_counter - 1) as usize];
            self.display_text(Point::new(5, MIDDLE_ROW), &previous);
        }
    }

    fn show_next_word(&self) {
        if self.page_counter < 9 {
            let next = &self.words[(self.page_counter + 1) as usize];
            self.display_text(Point::new(115, MIDDLE_ROW), &next);
        }
    }

    /// Display bold white text on black background
    fn display_text(&self, baseline: Point, text: &str) {
        display::text(baseline, text, theme::FONT_BOLD, theme::FG, theme::BG);
    }

    /// Changing all non-middle button's visual state to "released" state
    /// (one of the buttons has a "pressed" state from
    /// the first press of the both-button-press)
    /// NOTE: does not cause any event to the button, it just repaints it
    fn set_right_and_left_buttons_as_released(&mut self, ctx: &mut EventCtx) {
        self.prev.set_released(ctx);
        self.next.set_released(ctx);
    }
}

impl<T> Component for ConfirmWordPage<T>
where
    T: Deref<Target = str>,
{
    type Msg = ConfirmWordPageMsg;

    fn place(&mut self, bounds: Rect) -> Rect {
        let button_height = theme::FONT_BOLD.line_height() + 2;
        let (_content_area, button_area) = bounds.split_bottom(button_height);
        self.pad.place(bounds);
        self.prev.place(button_area);
        self.next.place(button_area);
        self.ok.place(button_area);
        bounds
    }

    fn event(&mut self, ctx: &mut EventCtx, event: Event) -> Option<Self::Msg> {
        // Possibly replacing or skipping an event because of both-button-press
        // aggregation
        let event = self.both_button_press.possibly_replace_event(event)?;

        // In case of both-button-press, changing all other buttons to released
        // state
        if self.both_button_press.are_both_buttons_pressed(event) {
            self.set_right_and_left_buttons_as_released(ctx);
        }

        // LEFT button clicks
        if self.page_counter > 0 {
            if let Some(ButtonMsg::Clicked) = self.prev.event(ctx, event) {
                // Clicked BACK. Decrease the page counter.
                self.page_counter = self.page_counter - 1;
                self.update_situation();
                return None;
            }
        }

        // RIGHT button clicks
        if self.page_counter < self.last_page_index() {
            if let Some(ButtonMsg::Clicked) = self.next.event(ctx, event) {
                // Clicked NEXT. Increase the page counter.
                self.page_counter = self.page_counter + 1;
                self.update_situation();
                return None;
            }
        }

        // MIDDLE button clicks
        if let Some(ButtonMsg::Clicked) = self.ok.event(ctx, event) {
            // Clicked OK. Send current word to the client.
            return Some(ConfirmWordPageMsg::Confirmed);
        }

        None
    }

    fn paint(&mut self) {
        self.pad.paint();

        // TOP header
        self.render_header();

        // MIDDLE panel
        self.update_situation();

        // BOTTOM LEFT button
        if self.page_counter > 0 {
            self.prev.paint();
        }

        // BOTTOM RIGHT button
        if self.page_counter < self.last_page_index() {
            self.next.paint();
        }

        // BOTTOM MIDDLE button
        self.ok.paint();
    }
}

#[cfg(feature = "ui_debug")]
impl<T> crate::trace::Trace for ConfirmWordPage<T>
where
    T: Deref<Target = str>,
{
    fn trace(&self, t: &mut dyn crate::trace::Tracer) {
        t.open("ConfirmWordPage");
        t.close();
    }
}
