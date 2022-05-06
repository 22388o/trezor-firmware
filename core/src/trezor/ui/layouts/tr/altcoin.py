from typing import TYPE_CHECKING, Awaitable

from trezor.enums import ButtonRequestType

from . import confirm

if TYPE_CHECKING:
    from trezor import wire
    from typing import Sequence


async def confirm_total_ethereum(
    ctx: wire.GenericContext, total_amount: str, gas_price: str, fee_max: str
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type="confirm_total_ethereum",
        title="Confirm ETH",
        data=f"total_amount: {total_amount}, gas_price: {gas_price}, fee_max: {fee_max}",
        description="",
        br_code=ButtonRequestType.SignTx,
    )


async def confirm_total_ripple(
    ctx: wire.GenericContext,
    address: str,
    amount: str,
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type="confirm_total_ripple",
        title="Confirm Ripple",
        data=f"address: {address}, amount: {amount}",
        description="",
    )


async def confirm_transfer_binance(
    ctx: wire.GenericContext, inputs_outputs: Sequence[tuple[str, str, str]]
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type="confirm_transfer_binance",
        title="Confirm Binance",
        data=", ".join(str(x) for x in inputs_outputs),
        description="",
    )


async def confirm_decred_sstx_submission(
    ctx: wire.GenericContext,
    address: str,
    amount: str,
) -> Awaitable[None]:
    return await confirm(
        ctx=ctx,
        br_type="confirm_decred_sstx_submission",
        title="Confirm Decred",
        data=f"address: {address}, amount: {amount}",
        description="",
        br_code=ButtonRequestType.ConfirmOutput,
    )
