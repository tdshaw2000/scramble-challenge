"""The Monkey skin's harbour picture: the tall one on upright phones, the wide one otherwise."""

import pytest


def background_picture(page):
    return page.evaluate(
        "getComputedStyle(document.body, '::before').backgroundImage.match(/[\\w-]+\\.webp/)[0]"
    )


@pytest.mark.parametrize(
    ("width", "height", "picture"),
    [
        (390, 844, "harbour.webp"),
        (844, 390, "harbour-wide.webp"),
        (1280, 800, "harbour-wide.webp"),
    ],
)
def test_the_picture_suits_the_screen_shape(new_player, live_server, width, height, picture):
    page = new_player(viewport={"width": width, "height": height})
    page.context.add_cookies(
        [{"name": "scramble_skin", "value": "monkeyisland2", "url": live_server}]
    )
    page.goto("/")

    assert background_picture(page) == picture
