from unittest import mock

import pytest
import shamir_mnemonic as shamir

from trezorlib import device, messages as proto
from trezorlib.messages import ButtonRequestType as B, ResetDeviceBackupType

from .common import click_through, generate_entropy, read_and_confirm_mnemonic

EXTERNAL_ENTROPY = b"zlutoucky kun upel divoke ody" * 2


@pytest.mark.skip_t1
class TestMsgResetDeviceT2:
    # TODO: test with different options
    @pytest.mark.setup_client(uninitialized=True)
    def test_reset_device_supershamir(self, client):
        strength = 128
        word_count = 20
        member_threshold = 3
        all_mnemonics = []

        def input_flow():
            # 1. Confirm Reset
            # 2. Backup your seed
            # 3. Confirm warning
            # 4. shares info
            # 5. Set & Confirm number of groups
            # 6. threshold info
            # 7. Set & confirm group threshold value
            # 8-17: for each of 5 groups:
            #   1. Set & Confirm number of shares
            #   2. Set & confirm share threshold value
            # 18. Confirm show seeds
            yield from click_through(client.debug, screens=18, code=B.ResetDevice)

            # show & confirm shares for all groups
            for g in range(5):
                for h in range(5):
                    # mnemonic phrases
                    btn_code = yield
                    assert btn_code == B.Other
                    mnemonic = read_and_confirm_mnemonic(client.debug, words=word_count)
                    all_mnemonics.append(mnemonic)

                    # Confirm continue to next share
                    btn_code = yield
                    assert btn_code == B.Success
                    client.debug.press_yes()

            # safety warning
            btn_code = yield
            assert btn_code == B.Success
            client.debug.press_yes()

        os_urandom = mock.Mock(return_value=EXTERNAL_ENTROPY)
        with mock.patch("os.urandom", os_urandom), client:
            client.set_expected_responses(
                [
                    proto.ButtonRequest(code=B.ResetDevice),
                    proto.EntropyRequest(),
                    proto.ButtonRequest(code=B.ResetDevice),
                    proto.ButtonRequest(code=B.ResetDevice),
                    proto.ButtonRequest(code=B.ResetDevice),
                    proto.ButtonRequest(code=B.ResetDevice),
                    proto.ButtonRequest(code=B.ResetDevice),
                    proto.ButtonRequest(code=B.ResetDevice),
                    proto.ButtonRequest(code=B.ResetDevice),
                    proto.ButtonRequest(code=B.ResetDevice),  # group #1 counts
                    proto.ButtonRequest(code=B.ResetDevice),
                    proto.ButtonRequest(code=B.ResetDevice),  # group #2 counts
                    proto.ButtonRequest(code=B.ResetDevice),
                    proto.ButtonRequest(code=B.ResetDevice),  # group #3 counts
                    proto.ButtonRequest(code=B.ResetDevice),
                    proto.ButtonRequest(code=B.ResetDevice),  # group #4 counts
                    proto.ButtonRequest(code=B.ResetDevice),
                    proto.ButtonRequest(code=B.ResetDevice),  # group #5 counts
                    proto.ButtonRequest(code=B.ResetDevice),
                    proto.ButtonRequest(code=B.Other),  # show seeds
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),
                    proto.ButtonRequest(code=B.Other),
                    proto.ButtonRequest(code=B.Success),  # show seeds ends here
                    proto.ButtonRequest(code=B.Success),
                    proto.Success(),
                    proto.Features(),
                ]
            )
            client.set_input_flow(input_flow)

            # No PIN, no passphrase, don't display random
            device.reset(
                client,
                display_random=False,
                strength=strength,
                passphrase_protection=False,
                pin_protection=False,
                label="test",
                language="english",
                backup_type=ResetDeviceBackupType.Slip39_Multiple_Groups,
            )

        # generate secret locally
        internal_entropy = client.debug.state().reset_entropy
        secret = generate_entropy(strength, internal_entropy, EXTERNAL_ENTROPY)

        # validate that all combinations will result in the correct master secret
        validate_mnemonics(all_mnemonics, member_threshold, secret)

        # Check if device is properly initialized
        assert client.features.initialized is True
        assert client.features.needs_backup is False
        assert client.features.pin_protection is False
        assert client.features.passphrase_protection is False


def validate_mnemonics(mnemonics, threshold, expected_ems):
    # 3of5 shares 3of5 groups
    # TODO: test all possible group+share combinations?
    test_combination = mnemonics[0:3] + mnemonics[5:8] + mnemonics[10:13]
    ms = shamir.combine_mnemonics(test_combination)
    identifier, iteration_exponent, _, _, _ = shamir._decode_mnemonics(test_combination)
    ems = shamir._encrypt(ms, b"", iteration_exponent, identifier)
    assert ems == expected_ems