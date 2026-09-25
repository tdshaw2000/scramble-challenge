from app.routes import NAME_COOKIE_NAME
from app.services import MAX_NAME_LENGTH


def name_cookie(client):
    found = client.get_cookie(NAME_COOKIE_NAME)
    return found.value if found else None


def name_box(response):
    html = response.get_data(as_text=True)
    start = html.index('name="display_name"')
    return html[html.rindex("<input", 0, start) : html.index(">", start) + 1]


def test_starting_a_challenge_remembers_the_cleaned_name(client):
    client.post("/challenges", data={"display_name": "  Tom  "})

    assert name_cookie(client) == "Tom"


def test_joining_a_challenge_remembers_the_name(client, challenge):
    client.post(f"/c/{challenge.slug}/join", data={"display_name": "Amy"})

    assert name_cookie(client) == "Amy"


def test_rejoining_remembers_the_name_already_in_the_challenge(client, challenge):
    client.post(f"/c/{challenge.slug}/join", data={"display_name": "Amy"})

    client.post(f"/c/{challenge.slug}/join", data={"display_name": "Someone else"})

    assert name_cookie(client) == "Amy"


def test_a_rejected_name_is_not_remembered(client):
    client.post("/challenges", data={"display_name": "Tom"})

    client.post("/challenges", data={"display_name": "   "})

    assert name_cookie(client) == "Tom"


def test_name_cookie_is_long_lived_and_hidden_from_scripts(client):
    response = client.post("/challenges", data={"display_name": "Tom"})

    set_cookie = next(
        h for h in response.headers.getlist("Set-Cookie") if h.startswith(NAME_COOKIE_NAME)
    )
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie
    assert "Max-Age=" in set_cookie


def test_landing_name_box_is_empty_without_a_remembered_name(client):
    assert "value=" not in name_box(client.get("/"))


def test_landing_name_box_is_filled_from_the_cookie(client):
    client.set_cookie(NAME_COOKIE_NAME, "Tom")

    assert 'value="Tom"' in name_box(client.get("/"))


def test_join_name_box_is_filled_from_the_cookie(client, challenge):
    client.set_cookie(NAME_COOKIE_NAME, "Amy")

    assert 'value="Amy"' in name_box(client.get(f"/c/{challenge.slug}"))


def test_name_from_the_cookie_is_escaped(client):
    client.set_cookie(NAME_COOKIE_NAME, '"><script>x</script>')

    box = name_box(client.get("/"))

    assert "<script>" not in box
    assert 'value="&#34;&gt;&lt;script&gt;x&lt;/script&gt;"' in box


def test_names_with_spaces_and_accents_survive_the_round_trip(client, challenge):
    client.post("/challenges", data={"display_name": "Zoë Ångström"})

    assert 'value="Zoë Ångström"' in name_box(client.get(f"/c/{challenge.slug}"))


def test_an_overlong_cookie_name_is_cut_to_the_box_limit(client):
    client.set_cookie(NAME_COOKIE_NAME, "x" * (MAX_NAME_LENGTH + 30))

    assert f'value="{"x" * MAX_NAME_LENGTH}"' in name_box(client.get("/"))
