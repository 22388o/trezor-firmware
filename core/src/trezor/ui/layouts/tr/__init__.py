from typing import TYPE_CHECKING, Sequence

from trezor import io, log, loop, ui, wire, workflow
from trezor.enums import ButtonRequestType

import trezorui2

from ..common import button_request, interact

if TYPE_CHECKING:
    from typing import Any, NoReturn, Type, Awaitable, Iterable, TypeVar

    from ..common import PropertyType

    T = TypeVar("T")

    ExceptionType = BaseException | Type[BaseException]


class _RustLayout(ui.Layout):
    # pylint: disable=super-init-not-called
    def __init__(self, layout: Any) -> None:
        self.layout = layout
        self.timer = loop.Timer()

    def set_timer(self, token: int, deadline: int) -> None:
        self.timer.schedule(deadline, token)

    if __debug__:

        def create_tasks(self) -> tuple[loop.AwaitableTask, ...]:
            from apps.debug import confirm_signal, input_signal

            return (
                self.handle_input_and_rendering(),
                self.handle_timers(),
                confirm_signal(),
                input_signal(),
            )

        def read_content(self) -> list[str]:
            result = []

            def callback(*args):
                for arg in args:
                    result.append(str(arg))

            self.layout.trace(callback)
            result = " ".join(result).split("\n")
            return result

    else:

        def create_tasks(self) -> tuple[loop.Task, ...]:
            return self.handle_timers(), self.handle_input_and_rendering()

    def _before_render(self) -> None:
        if __debug__ and self.should_notify_layout_change:
            from apps.debug import notify_layout_change

            # notify about change and do not notify again until next await.
            # (handle_rendering might be called multiple times in a single await,
            # because of the endless loop in __iter__)
            self.should_notify_layout_change = False
            notify_layout_change(self)

    def handle_input_and_rendering(self) -> loop.Task:  # type: ignore [awaitable-is-generator]
        button = loop.wait(io.BUTTON)
        self._before_render()
        ui.display.clear()
        self.layout.attach_timer_fn(self.set_timer)
        self.layout.paint()
        while True:
            # Using `yield` instead of `await` to avoid allocations.
            event, button_num = yield button

            workflow.idle_timer.touch()
            msg = None
            if event in (io.BUTTON_PRESSED, io.BUTTON_RELEASED):
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


async def raise_if_cancelled(a: Awaitable[T], exc: Any = wire.ActionCancelled) -> T:
    result = await a
    if result is trezorui2.CANCELLED:
        raise exc
    return result


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

    await raise_if_cancelled(
        interact(
            ctx,
            _RustLayout(
                trezorui2.confirm_action(
                    title=title,
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
        ),
        exc,
    )


async def confirm_text(
    ctx: wire.GenericContext,
    br_type: str,
    title: str,
    data: str,
    description: str | None = None,
    br_code: ButtonRequestType = ButtonRequestType.Other,
    icon: str = ui.ICON_SEND,  # TODO cleanup @ redesign
    icon_color: int = ui.GREEN,  # TODO cleanup @ redesign
) -> Any:
    result = await interact(
        ctx,
        _RustLayout(
            trezorui2.confirm_text(
                title=title,
                data=data,
                description=description,
            )
        ),
        br_type,
        br_code,
    )
    return result


async def confirm(
    ctx: wire.GenericContext,
    br_type: str,
    title: str,
    data: str,
    description: str | None = None,
    br_code: ButtonRequestType = ButtonRequestType.Other,
) -> Awaitable[Any]:
    return await confirm_text(
        ctx=ctx,
        br_type=br_type,
        title=title,
        data=data,
        description=description,
        br_code=br_code,
    )


async def get_bool(
    ctx: wire.GenericContext,
    br_type: str,
    title: str,
    data: str,
    description: str | None = None,
    br_code: ButtonRequestType = ButtonRequestType.Other,
) -> bool:
    result = await interact(
        ctx,
        _RustLayout(
            trezorui2.confirm_text(
                title=title,
                data=data,
                description=description,
            )
        ),
        br_type=br_type,
        br_code=br_code,
    )

    return result is trezorui2.CONFIRMED


async def show_success(
    ctx: wire.GenericContext,
    br_type: str,
    content: str,
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type=br_type,
        title="Success",
        data=content,
        description="",
        br_code=ButtonRequestType.Success,
    )


async def confirm_reset_device(
    ctx: wire.GenericContext, prompt: str, recovery: bool = False
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type="recover_device" if recovery else "setup_device",
        title="Recovery mode" if recovery else "Create new wallet",
        data=f"{prompt}\n\nBy continuing you agree to\nhttps://trezor.io/tos",
        description="",
        br_code=ButtonRequestType.ProtectCall
        if recovery
        else ButtonRequestType.ResetDevice,
    )


async def show_warning(
    ctx: wire.GenericContext,
    br_type: str,
    content: str,
    header: str = "Warning",
    br_code: ButtonRequestType = ButtonRequestType.Warning,
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type=br_type,
        title=header,
        data=content,
        description="",
        br_code=br_code,
    )


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
) -> Awaitable[None]:
    text = ""
    if network:
        text += f"{network} network\n"
    if address_extra:
        text += f"{address_extra}\n"
    text += address
    return await confirm(
        ctx=ctx,
        br_type="show_address",
        title=title,
        data=text,
        description="",
        br_code=ButtonRequestType.Address,
    )


async def confirm_output(
    ctx: wire.GenericContext,
    address: str,
    amount: str,
    subtitle: str = "",
    font_amount: int = ui.NORMAL,  # TODO cleanup @ redesign
    title: str = "Confirm sending",
    width_paginated: int = 0,
    width: int = 0,
    icon: str = ui.ICON_SEND,
    to_str: str = "\nto\n",
    to_paginated: bool = True,
    color_to: str = "",
    br_code: ButtonRequestType = ButtonRequestType.ConfirmOutput,
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type="confirm_output",
        title=title,
        data=f"{amount} to\n{address}",
        description=subtitle,
        br_code=br_code,
    )


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
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type=br_type,
        title=title,
        data=f"{total_label}{total_amount}{fee_label}{fee_amount}",
        description="",
        br_code=br_code,
    )


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
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type=br_type,
        title=title,
        data=str(data),
        description=description,
        br_code=br_code,
    )


async def confirm_address(
    ctx: wire.GenericContext,
    title: str,
    address: str,
    description: str | None = "Address:",
    br_type: str = "confirm_address",
    br_code: ButtonRequestType = ButtonRequestType.Other,
    icon: str = ui.ICON_SEND,  # TODO cleanup @ redesign
    icon_color: int = ui.GREEN,  # TODO cleanup @ redesign
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type=br_type,
        title=title,
        data=address,
        description=description,
        br_code=br_code,
    )


def draw_simple_text(title: str, description: str = "") -> None:
    log.error(__name__, "draw_simple_text not implemented")


async def request_pin_on_device(
    ctx: wire.GenericContext,
    prompt: str,
    attempts_remaining: int | None,
    allow_cancel: bool,
    shuffle: bool = False,
) -> str:
    await button_request(ctx, "pin_device", code=ButtonRequestType.PinEntry)

    if attempts_remaining is None:
        subprompt = ""
    elif attempts_remaining == 1:
        subprompt = "Last attempt"
    else:
        subprompt = f"{attempts_remaining} tries left"

    while True:
        result = await ctx.wait(
            _RustLayout(
                trezorui2.request_pin(
                    prompt=prompt,
                    subprompt=subprompt,
                    allow_cancel=allow_cancel,
                    shuffle=shuffle,
                )
            )
        )
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
    await confirm(
        ctx=ctx,
        br_type=br_type,
        title=header,
        data=content,
        description="",
        br_code=ButtonRequestType.Other,
    )
    raise exc


async def show_pubkey(
    ctx: wire.Context, pubkey: str, title: str = "Confirm public key"
) -> Awaitable[None]:
    return await confirm_blob(
        ctx,
        br_type="show_pubkey",
        title=title,
        data=pubkey,
        br_code=ButtonRequestType.PublicKey,
    )


async def confirm_amount(
    ctx: wire.GenericContext,
    title: str,
    amount: str,
    description: str = "Amount:",
    br_type: str = "confirm_amount",
    br_code: ButtonRequestType = ButtonRequestType.Other,
    icon: str = ui.ICON_SEND,  # TODO cleanup @ redesign
    icon_color: int = ui.GREEN,  # TODO cleanup @ redesign
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type=br_type,
        title=title,
        data=amount,
        description=description,
        br_code=br_code,
    )


async def confirm_properties(
    ctx: wire.GenericContext,
    br_type: str,
    title: str,
    props: Iterable[PropertyType],
    icon: str = ui.ICON_SEND,  # TODO cleanup @ redesign
    icon_color: int = ui.GREEN,  # TODO cleanup @ redesign
    hold: bool = False,
    br_code: ButtonRequestType = ButtonRequestType.ConfirmOutput,
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type=br_type,
        title=title,
        data="\n\n".join(f"{name or ''}\n{value or ''}" for name, value in props),
        description="",
        br_code=br_code,
    )


async def confirm_joint_total(
    ctx: wire.GenericContext, spending_amount: str, total_amount: str
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type="confirm_joint_total",
        title="Joint transaction",
        data=f"You are contributing:\n{spending_amount}\nto the total amount:\n{total_amount}",
        description="",
        br_code=ButtonRequestType.SignTx,
    )


async def confirm_metadata(
    ctx: wire.GenericContext,
    br_type: str,
    title: str,
    content: str,
    param: str | None = None,
    br_code: ButtonRequestType = ButtonRequestType.SignTx,
    hide_continue: bool = False,
    hold: bool = False,
    param_font: int = ui.BOLD,
    icon: str = ui.ICON_SEND,  # TODO cleanup @ redesign
    icon_color: int = ui.GREEN,  # TODO cleanup @ redesign
    larger_vspace: bool = False,  # TODO cleanup @ redesign
) -> Awaitable[None]:
    text = content.format(param)
    if not hide_continue:
        text += "\n\nContinue?"
    return await confirm(
        ctx=ctx,
        br_type=br_type,
        title=title,
        data=text,
        description="",
        br_code=br_code,
    )


async def confirm_replacement(
    ctx: wire.GenericContext, description: str, txid: str
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type="confirm_replacement",
        title=description,
        data=f"Confirm transaction ID:\n{txid}",
        description="",
        br_code=ButtonRequestType.SignTx,
    )


async def confirm_modify_output(
    ctx: wire.GenericContext,
    address: str,
    sign: int,
    amount_change: str,
    amount_new: str,
) -> Awaitable[None]:
    text = "Address:\n{address}\n\n"
    if sign < 0:
        text += "Decrease amount by:\n{amount_change}\n\n"
    else:
        text += "Increase amount by:\n{amount_change}\n\n"
    text += "New amount:\n{amount_new}"
    return await confirm(
        ctx=ctx,
        br_type="modify_output",
        title="Modify amount",
        data=text,
        description="",
        br_code=ButtonRequestType.ConfirmOutput,
    )


async def confirm_modify_fee(
    ctx: wire.GenericContext,
    sign: int,
    user_fee_change: str,
    total_fee_new: str,
) -> Awaitable[None]:
    text = ""
    if sign == 0:
        text += "Your fee did not change.\n"
    else:
        if sign < 0:
            text += "Decrease your fee by:\n"
        else:
            text += "Increase your fee by:\n"
        text += f"{user_fee_change}\n"
    text += f"Transaction fee:\n{total_fee_new}"
    return await confirm(
        ctx=ctx,
        br_type="modify_fee",
        title="Modify fee",
        data=text,
        description="",
        br_code=ButtonRequestType.SignTx,
    )


async def confirm_coinjoin(
    ctx: wire.GenericContext, coin_name: str, max_rounds: int, max_fee_per_vbyte: str
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type="coinjoin_final",
        title="Authorize CoinJoin",
        data=f"Coin name: {coin_name}\n\nMaximum rounds: {max_rounds}\n\nMaximum mining fee:\n{max_fee_per_vbyte} sats/vbyte",
        description="",
        br_code=ButtonRequestType.Other,
    )


# TODO cleanup @ redesign
async def confirm_sign_identity(
    ctx: wire.GenericContext, proto: str, identity: str, challenge_visual: str | None
) -> Awaitable[None]:
    text = ""
    if challenge_visual:
        text += f"{challenge_visual}\n\n"
    text += identity
    return await confirm(
        ctx=ctx,
        br_type="confirm_sign_identity",
        title=f"Sign {proto}",
        data=text,
        description="",
        br_code=ButtonRequestType.Other,
    )


async def confirm_signverify(
    ctx: wire.GenericContext, coin: str, message: str, address: str, verify: bool
) -> Awaitable[None]:
    if verify:
        header = f"Verify {coin} message"
        br_type = "verify_message"
    else:
        header = f"Sign {coin} message"
        br_type = "sign_message"

    return await confirm(
        ctx=ctx,
        br_type=br_type,
        title=header,
        data=f"Confirm address:\n{address}\n\nConfirm message:\n{message}",
        description="",
        br_code=ButtonRequestType.Other,
    )


# TODO cleanup @ redesign
async def confirm_backup(ctx: wire.GenericContext) -> bool:
    if await get_bool(
        ctx=ctx,
        title="Success",
        data="New wallet created successfully!\n\nYou should back up your new wallet right now.",
        br_type="backup_device",
        br_code=ButtonRequestType.ResetDevice,
    ):
        return True

    confirmed = await get_bool(
        ctx=ctx,
        title="Warning",
        data="Are you sure you want to skip the backup?\n\nYou can back up your Trezor once, at any time.",
        br_type="backup_device",
        br_code=ButtonRequestType.ResetDevice,
    )
    return confirmed


async def confirm_path_warning(
    ctx: wire.GenericContext, path: str, path_type: str = "Path"
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type="path_warning",
        title="Confirm path",
        data=f"{path_type}\n{path} is unknown.\nAre you sure?",
        description="",
        br_code=ButtonRequestType.UnknownDerivationPath,
    )


async def show_xpub(
    ctx: wire.GenericContext, xpub: str, title: str, cancel: str
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type="show_xpub",
        title=title,
        data=xpub,
        description="",
        br_code=ButtonRequestType.PublicKey,
    )


async def show_popup(
    title: str,
    description: str,
    subtitle: str | None = None,
    description_param: str = "",
    timeout_ms: int = 3000,
) -> None:
    raise NotImplementedError


async def should_show_more(
    ctx: wire.GenericContext,
    title: str,
    para: Iterable[tuple[int, str]],
    button_text: str = "Show all",
    br_type: str = "should_show_more",
    br_code: ButtonRequestType = ButtonRequestType.Other,
    icon: str = ui.ICON_DEFAULT,
    icon_color: int = ui.ORANGE_ICON,
) -> bool:
    return await get_bool(
        ctx=ctx,
        title=title,
        data="Should show more?",
        br_type=br_type,
        br_code=br_code,
    )


async def confirm_payment_request(
    ctx: wire.GenericContext,
    recipient_name: str,
    amount: str,
    memos: list[str],
) -> Awaitable[None]:
    memos_str = "\n".join(memos)
    return await confirm(
        ctx=ctx,
        br_type="confirm_payment_request",
        title="Confirm sending",
        data=f"{amount} to\n{recipient_name}\n{memos_str}",
        description="",
        br_code=ButtonRequestType.ConfirmOutput,
    )


async def _show_modal(
    ctx: wire.GenericContext,
    br_type: str,
    br_code: ButtonRequestType,
    header: str,
    subheader: str | None,
    content: str,
    button_confirm: str | None,
    button_cancel: str | None,
    icon: str,
    icon_color: int,
    exc: ExceptionType = wire.ActionCancelled,
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type=br_type,
        title=header,
        data=content,
        description=subheader,
        br_code=br_code,
    )


async def request_passphrase_on_device(ctx: wire.GenericContext, max_len: int) -> str:
    return NotImplementedError
