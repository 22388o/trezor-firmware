use super::{event::TouchEvent, theme};
use crate::ui::{
    component::{Component, Event, EventCtx},
    display::{self, Color, Font},
    geometry::{Grid, Insets, Offset, Rect},
};

pub enum ButtonMsg {
    Pressed,
    Released,
    Clicked,
}

pub struct Button<T> {
    area: Rect,
    content: ButtonContent<T>,
    styles: ButtonStyleSheet,
    state: State,
}

impl<T> Button<T> {
    pub const HEIGHT: i32 = 38;
    pub const BASELINE_OFFSET: i32 = -4;

    pub fn new(area: Rect, content: ButtonContent<T>) -> Self {
        Self {
            area,
            content,
            styles: theme::button_default(),
            state: State::Initial,
        }
    }

    pub fn with_text(area: Rect, text: T) -> Self {
        Self::new(area, ButtonContent::Text(text))
    }

    pub fn with_icon(area: Rect, image: &'static [u8]) -> Self {
        Self::new(area, ButtonContent::Icon(image))
    }

    pub fn styled(mut self, styles: ButtonStyleSheet) -> Self {
        self.styles = styles;
        self
    }

    pub fn enable(&mut self, ctx: &mut EventCtx) {
        self.set(ctx, State::Initial)
    }

    pub fn disable(&mut self, ctx: &mut EventCtx) {
        self.set(ctx, State::Disabled)
    }

    pub fn enabled(&mut self, ctx: &mut EventCtx, enabled: bool) {
        if enabled {
            self.enable(ctx);
        } else {
            self.disable(ctx);
        }
    }

    pub fn is_enabled(&self) -> bool {
        matches!(
            self.state,
            State::Initial | State::Pressed | State::Released
        )
    }

    pub fn is_disabled(&self) -> bool {
        matches!(self.state, State::Disabled)
    }

    pub fn content(&self) -> &ButtonContent<T> {
        &self.content
    }

    fn style(&self) -> &ButtonStyle {
        match self.state {
            State::Initial | State::Released => self.styles.normal,
            State::Pressed => self.styles.active,
            State::Disabled => self.styles.disabled,
        }
    }

    fn set(&mut self, ctx: &mut EventCtx, state: State) {
        if self.state != state {
            self.state = state;
            ctx.request_paint();
        }
    }
}

impl<T> Component for Button<T>
where
    T: AsRef<[u8]>,
{
    type Msg = ButtonMsg;

    fn event(&mut self, ctx: &mut EventCtx, event: Event) -> Option<Self::Msg> {
        match event {
            Event::Touch(TouchEvent::TouchStart(pos)) => {
                match self.state {
                    State::Disabled => {
                        // Do nothing.
                    }
                    _ => {
                        // Touch started in our area, transform to `Pressed` state.
                        if self.area.contains(pos) {
                            self.set(ctx, State::Pressed);
                            return Some(ButtonMsg::Pressed);
                        }
                    }
                }
            }
            Event::Touch(TouchEvent::TouchMove(pos)) => {
                match self.state {
                    State::Released if self.area.contains(pos) => {
                        // Touch entered our area, transform to `Pressed` state.
                        self.set(ctx, State::Pressed);
                        return Some(ButtonMsg::Pressed);
                    }
                    State::Pressed if !self.area.contains(pos) => {
                        // Touch is leaving our area, transform to `Released` state.
                        self.set(ctx, State::Released);
                        return Some(ButtonMsg::Released);
                    }
                    _ => {
                        // Do nothing.
                    }
                }
            }
            Event::Touch(TouchEvent::TouchEnd(pos)) => {
                match self.state {
                    State::Initial | State::Disabled => {
                        // Do nothing.
                    }
                    State::Pressed if self.area.contains(pos) => {
                        // Touch finished in our area, we got clicked.
                        self.set(ctx, State::Initial);
                        return Some(ButtonMsg::Clicked);
                    }
                    _ => {
                        // Touch finished outside our area.
                        self.set(ctx, State::Initial);
                    }
                }
            }
            _ => {}
        };
        None
    }

    fn paint(&mut self) {
        let style = self.style();

        if style.border_width > 0 {
            // Paint the border and a smaller background on top of it.
            display::rect_fill_rounded(
                self.area,
                style.border_color,
                style.background_color,
                style.border_radius,
            );
            display::rect_fill_rounded(
                self.area.inset(Insets::uniform(style.border_width)),
                style.button_color,
                style.border_color,
                style.border_radius,
            );
        } else {
            // We do not need to draw an explicit border in this case, just a
            // bigger background.
            display::rect_fill_rounded(
                self.area,
                style.button_color,
                style.background_color,
                style.border_radius,
            );
        }

        match &self.content {
            ButtonContent::Text(text) => {
                let text = text.as_ref();
                let width = style.font.text_width(text);
                let height = style.font.text_height() + Self::BASELINE_OFFSET;
                let start_of_baseline = self.area.center() + Offset::new(-width / 2, height / 2);
                display::text(
                    start_of_baseline,
                    text,
                    style.font,
                    style.text_color,
                    style.button_color,
                );
            }
            ButtonContent::Icon(icon) => {
                display::icon(
                    self.area.center(),
                    icon,
                    style.text_color,
                    style.button_color,
                );
            }
        }
    }
}

#[cfg(feature = "ui_debug")]
impl<T> crate::trace::Trace for Button<T>
where
    T: AsRef<[u8]> + crate::trace::Trace,
{
    fn trace(&self, t: &mut dyn crate::trace::Tracer) {
        t.open("Button");
        match &self.content {
            ButtonContent::Text(text) => t.field("text", text),
            ButtonContent::Icon(_) => t.symbol("icon"),
        }
        t.close();
    }

    fn bounds(&self, sink: &dyn Fn(Rect)) {
        sink(self.area)
    }
}

#[derive(PartialEq, Eq)]
enum State {
    Initial,
    Pressed,
    Released,
    Disabled,
}

pub enum ButtonContent<T> {
    Text(T),
    Icon(&'static [u8]),
}

pub struct ButtonStyleSheet {
    pub normal: &'static ButtonStyle,
    pub active: &'static ButtonStyle,
    pub disabled: &'static ButtonStyle,
}

pub struct ButtonStyle {
    pub font: Font,
    pub text_color: Color,
    pub button_color: Color,
    pub background_color: Color,
    pub border_color: Color,
    pub border_radius: u8,
    pub border_width: i32,
}

pub struct ButtonArray<T> {
    pub left: Button<T>,
    pub right: Button<T>,
}

impl<T> ButtonArray<T> {
    const BUTTON_SPACING: i32 = 6;

    pub fn new(
        area: Rect,
        left: impl FnOnce(Rect) -> Button<T>,
        right: impl FnOnce(Rect) -> Button<T>,
    ) -> Self {
        let grid = Grid::new(area, 1, 4).with_spacing(Self::BUTTON_SPACING);
        let left = left(grid.row_col(0, 0));
        let right = right(Rect::new(
            grid.row_col(0, 1).top_left(),
            grid.row_col(0, 3).bottom_right(),
        ));

        Self { left, right }
    }
}

impl<T> Component for ButtonArray<T>
where
    T: AsRef<[u8]>,
{
    type Msg = bool;

    fn event(&mut self, ctx: &mut EventCtx, event: Event) -> Option<Self::Msg> {
        if let Some(ButtonMsg::Clicked) = self.left.event(ctx, event) {
            return Some(false);
        }
        if let Some(ButtonMsg::Clicked) = self.right.event(ctx, event) {
            return Some(true);
        }
        None
    }

    fn paint(&mut self) {
        self.left.paint();
        self.right.paint();
    }
}

#[cfg(feature = "ui_debug")]
impl<T> crate::trace::Trace for ButtonArray<T>
where
    T: AsRef<[u8]> + crate::trace::Trace,
{
    fn trace(&self, t: &mut dyn crate::trace::Tracer) {
        self.left.trace(t);
        self.right.trace(t);
    }

    fn bounds(&self, sink: &dyn Fn(Rect)) {
        self.left.bounds(sink);
        self.right.bounds(sink);
    }
}
