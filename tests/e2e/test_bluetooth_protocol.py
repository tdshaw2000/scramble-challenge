"""The QiYi timer protocol's building blocks (bluetooth-timer.js), run in a real browser.

Each block of a QiYi message is AES-128 encrypted with a fixed, publicly known key (sixteen
0x77 bytes). The vendored AES library is checked against the FIPS-197 test vector first, so
the fake timer in the other tests, which uses the same library, can be trusted.
"""

import re
from pathlib import Path

import pytest

VENDOR = Path(__file__).resolve().parents[2] / "app" / "static" / "vendor"
FIXED_KEY = [0x77] * 16


@pytest.fixture
def page(new_player):
    page = new_player()
    page.goto("/")
    page.add_script_tag(url="/static/vendor/aes.js")
    return page


def test_the_aes_library_is_vendored_with_its_licence_and_pinned_version():
    library = (VENDOR / "aes.js").read_text()
    assert re.search(r"aes-js v\d+\.\d+\.\d+", library)
    assert "MIT" in (VENDOR / "LICENSE-aes-js.txt").read_text()


def test_the_aes_library_matches_the_fips_197_test_vector(page):
    encrypted = page.evaluate(
        """() => {
          const key = Array.from({ length: 16 }, (_, i) => i);
          const plain = aesjs.utils.hex.toBytes("00112233445566778899aabbccddeeff");
          return aesjs.utils.hex.fromBytes(new aesjs.AES(key).encrypt(plain));
        }"""
    )
    assert encrypted == "69c4e0d86a7b0430d8cdb78070b4c55a"


def test_one_block_encrypted_with_the_fixed_key_decrypts_to_the_original(page):
    block = list(range(16))
    result = page.evaluate(
        """([key, block]) => {
          const aes = new aesjs.AES(key);
          const encrypted = Array.from(aes.encrypt(block));
          return { encrypted, decrypted: Array.from(aes.decrypt(encrypted)) };
        }""",
        [FIXED_KEY, block],
    )
    assert result["encrypted"] != block
    assert result["decrypted"] == block
