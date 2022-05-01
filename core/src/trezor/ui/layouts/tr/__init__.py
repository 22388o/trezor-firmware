from typing import TYPE_CHECKING, Sequence

from trezor import io, log, loop, ui, wire, workflow
from trezor.enums import ButtonRequestType

import trezorui2

from ..common import button_request, interact

if TYPE_CHECKING:
    from typing import Any, NoReturn, Type

    ExceptionType = BaseException | Type[BaseException]


class DoublePressHandler:
    """Monitoring when to send double press events"""

    def __init__(self) -> None:
        self.left_pressed = False
        self.right_pressed = False
        self.wait_for_double_press_release = False
        self.send_double_press_pressed = False
        self.send_double_press_released = False
        self.skip_rest = False

        # Signal of double press, connected with the middle option on R screen
        self.button_num = 2

    def handle_double_press(self, event: int, button_num: int) -> None:
        if event == io.BUTTON_PRESSED:
            if button_num == io.BUTTON_LEFT:
                self.left_pressed = True
                if self.right_pressed:
                    self.send_double_press_pressed = True
            elif button_num == io.BUTTON_RIGHT:
                self.right_pressed = True
                if self.left_pressed:
                    self.send_double_press_pressed = True
        elif event == io.BUTTON_RELEASED:
            if self.left_pressed and button_num == io.BUTTON_LEFT:
                self.left_pressed = False
                if self.right_pressed:
                    # not send release event for the button itself
                    self.skip_rest = True
                else:
                    self.send_double_press_released = True
                    self.skip_rest = False
            elif self.right_pressed and button_num == io.BUTTON_RIGHT:
                self.right_pressed = False
                if self.left_pressed:
                    # not send release event for the button itself
                    self.skip_rest = True
                else:
                    self.send_double_press_released = True
                    self.skip_rest = False

    def should_skip_rest(self) -> bool:
        """In some situations we do not want to send individual events.

        For example when releasing the first button from double press,
        we do not want to send the release event for the button itself,
        as that could trigger a click on the single button.
        (Considering that first-to-release button was first-to-press.)
        """
        return self.skip_rest

    def should_send_double_press_pressed(self) -> bool:
        return self.send_double_press_pressed

    def should_send_double_press_released(self) -> bool:
        return self.wait_for_double_press_release and self.send_double_press_released

    def account_for_double_press_pressed(self) -> None:
        self.wait_for_double_press_release = True
        self.send_double_press_pressed = False

    def account_for_double_press_released(self) -> None:
        self.send_double_press_released = False
        self.wait_for_double_press_release = False


class _RustLayout(ui.Layout):
    # pylint: disable=super-init-not-called
    def __init__(self, layout: Any) -> None:
        self.layout = layout
        self.timer = loop.Timer()
        self.layout.set_timer_fn(self.set_timer)
        self.d_p = DoublePressHandler()

    def set_timer(self, token: int, deadline: int) -> None:
        self.timer.schedule(deadline, token)

    def create_tasks(self) -> tuple[loop.Task, ...]:
        return self.handle_input_and_rendering(), self.handle_timers()

    def handle_input_and_rendering(self) -> loop.Task:  # type: ignore [awaitable-is-generator]
        button = loop.wait(io.BUTTON)
        ui.display.clear()
        self.layout.paint()
        while True:
            # Using `yield` instead of `await` to avoid allocations.
            event, button_num = yield button

            # TODO: could have some timing mechanism to wait for double press
            # (so that we do not send the "single" event first)

            self.d_p.handle_double_press(event, button_num)
            if self.d_p.should_skip_rest():
                continue

            workflow.idle_timer.touch()
            msg = None
            if event in (io.BUTTON_PRESSED, io.BUTTON_RELEASED):
                if self.d_p.should_send_double_press_pressed():
                    msg = self.layout.button_event(
                        io.BUTTON_PRESSED, self.d_p.button_num
                    )
                    self.d_p.account_for_double_press_pressed()
                elif self.d_p.should_send_double_press_released():
                    msg = self.layout.button_event(
                        io.BUTTON_RELEASED, self.d_p.button_num
                    )
                    self.d_p.account_for_double_press_released()
                else:
                    msg = self.layout.button_event(event, button_num)
            self.layout.paint()
            if msg is not None:
                raise ui.Result(msg)

    def handle_timers(self) -> loop.Task:  # type: ignore [awaitable-is-generator]
        while True:
            # Using `yield` instead of `await` to avoid allocations.
            token = yield self.timer
            msg = self.layout.timer(token)
            self.layout.paint()
            if msg is not None:
                raise ui.Result(msg)


async def confirm_action(
    ctx: wire.GenericContext,
    br_type: str,
    title: str,
    action: str | None = None,
    description: str | None = None,
    description_param: str | None = None,
    description_param_font: int = ui.BOLD,
    verb: str | bytes | None = "OK",
    verb_cancel: str | bytes | None = "cancel",
    hold: bool = False,
    hold_danger: bool = False,
    icon: str | None = None,
    icon_color: int | None = None,
    reverse: bool = False,
    larger_vspace: bool = False,
    exc: ExceptionType = wire.ActionCancelled,
    br_code: ButtonRequestType = ButtonRequestType.Other,
) -> None:
    if isinstance(verb, bytes) or isinstance(verb_cancel, bytes):
        raise NotImplementedError

    if description is not None and description_param is not None:
        if description_param_font != ui.BOLD:
            log.error(__name__, "confirm_action description_param_font not implemented")
        description = description.format(description_param)

    if hold:
        log.error(__name__, "confirm_action hold not implemented")

    result = await interact(
        ctx,
        _RustLayout(
            trezorui2.confirm_action(
                title=title.upper(),
                action=action,
                description=description,
                verb=verb,
                verb_cancel=verb_cancel,
                hold=hold,
                reverse=reverse,
            )
        ),
        br_type,
        br_code,
    )
    if result is not trezorui2.CONFIRMED:
        raise exc


async def confirm_text(
    ctx: wire.GenericContext,
    br_type: str,
    title: str,
    data: str,
    description: str | None = None,
    br_code: ButtonRequestType = ButtonRequestType.Other,
    icon: str = ui.ICON_SEND,  # TODO cleanup @ redesign
    icon_color: int = ui.GREEN,  # TODO cleanup @ redesign
) -> None:
    result = await interact(
        ctx,
        _RustLayout(
            trezorui2.confirm_text(
                title=title.upper(),
                data=data,
                description=description,
            )
        ),
        br_type,
        br_code,
    )
    if result is not trezorui2.CONFIRMED:
        raise wire.ActionCancelled


async def show_success(
    ctx: wire.GenericContext,
    br_type: str,
    content: str,
) -> None:
    result = await interact(
        ctx,
        _RustLayout(
            trezorui2.confirm_text(
                title="Success",
                data=content,
                description="",
            )
        ),
        br_type,
        br_code=ButtonRequestType.Other,
    )
    if result is not trezorui2.CONFIRMED:
        raise wire.ActionCancelled


async def show_address(
    ctx: wire.GenericContext,
    address: str,
    *,
    case_sensitive: bool = True,
    address_qr: str | None = None,
    title: str = "Confirm address",
    network: str | None = None,
    multisig_index: int | None = None,
    xpubs: Sequence[str] = (),
    address_extra: str | None = None,
    title_qr: str | None = None,
) -> None:
    result = await interact(
        ctx,
        _RustLayout(
            trezorui2.confirm_text(
                title="ADDRESS",
                data=address,
                description="Confirm address",
            )
        ),
        "show_address",
        ButtonRequestType.Address,
    )
    if result is not trezorui2.CONFIRMED:
        raise wire.ActionCancelled


async def confirm_output(
    ctx: wire.GenericContext,
    address: str,
    amount: str,
    font_amount: int = ui.NORMAL,  # TODO cleanup @ redesign
    title: str = "Confirm sending",
    icon: str = ui.ICON_SEND,
) -> None:
    result = await interact(
        ctx,
        _RustLayout(
            trezorui2.confirm_text(
                title=title,
                data=f"Send {amount} to {address}?",
                description="Confirm Output",
            )
        ),
        "confirm_output",
        ButtonRequestType.Other,
    )
    if result is not trezorui2.CONFIRMED:
        raise wire.ActionCancelled


async def confirm_total(
    ctx: wire.GenericContext,
    total_amount: str,
    fee_amount: str,
    title: str = "Confirm transaction",
    total_label: str = "Total amount:\n",
    fee_label: str = "\nincluding fee:\n",
    icon_color: int = ui.GREEN,
    br_type: str = "confirm_total",
    br_code: ButtonRequestType = ButtonRequestType.SignTx,
) -> None:
    result = await interact(
        ctx,
        _RustLayout(
            trezorui2.confirm_text(
                title=title,
                data=f"{total_label}{total_amount}\n{fee_label}{fee_amount}",
                description="Confirm Output",
            )
        ),
        br_type,
        br_code,
    )
    if result is not trezorui2.CONFIRMED:
        raise wire.ActionCancelled


async def confirm_blob(
    ctx: wire.GenericContext,
    br_type: str,
    title: str,
    data: bytes | str,
    description: str | None = None,
    hold: bool = False,
    br_code: ButtonRequestType = ButtonRequestType.Other,
    icon: str = ui.ICON_SEND,  # TODO cleanup @ redesign
    icon_color: int = ui.GREEN,  # TODO cleanup @ redesign
    ask_pagination: bool = False,
) -> None:
    result = await interact(
        ctx,
        _RustLayout(
            trezorui2.confirm_text(
                title=title,
                data=str(data),
                description=description,
            )
        ),
        br_type,
        br_code,
    )
    if result is not trezorui2.CONFIRMED:
        raise wire.ActionCancelled


def draw_simple_text(title: str, description: str = "") -> None:
    log.error(__name__, "draw_simple_text not implemented")


async def request_pin_on_device(
    ctx: wire.GenericContext,
    prompt: str,
    attempts_remaining: int | None,
    allow_cancel: bool,
) -> str:
    await button_request(ctx, "pin_device", code=ButtonRequestType.PinEntry)

    # TODO: implement attempts_remaining and allow_cancel parameters

    while True:
        result = await ctx.wait(_RustLayout(trezorui2.request_pin(prompt=prompt)))
        if result is trezorui2.CANCELLED:
            raise wire.PinCancelled
        assert isinstance(result, str)
        return result


async def show_error_and_raise(
    ctx: wire.GenericContext,
    br_type: str,
    content: str,
    header: str = "Error",
    subheader: str | None = None,
    button: str = "Close",
    red: bool = False,
    exc: ExceptionType = wire.ActionCancelled,
) -> NoReturn:
    await interact(
        ctx,
        _RustLayout(
            trezorui2.confirm_text(
                title=header, data=content, description="Error happened"
            )
        ),
        br_type,
        br_code=ButtonRequestType.Warning,
    )
    raise exc


async def show_popup(
    title: str,
    description: str,
    subtitle: str | None = None,
    description_param: str = "",
    timeout_ms: int = 3000,
) -> None:
    raise NotImplementedError