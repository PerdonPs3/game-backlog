"""Exercise authentication and real SQL isolation without contacting Supabase."""

from io import BytesIO
import json
import pytest

from app import create_app
from app.auth import AuthError, fingerprint
from app.db import get_db
from tests.conftest import CSRFTokenParser


ALICE = "11111111-1111-4111-8111-111111111111"
BOB = "22222222-2222-4222-8222-222222222222"


class FakeAuth:
    unavailable = False
    invalid = False
    calls = None

    def __init__(self):
        self.calls = []

    def call(self, path, payload=None, token=None, method=None):
        self.calls.append((path, payload, token, method))
        if self.unavailable:
            raise AuthError(unavailable=True)
        if self.invalid:
            raise AuthError()
        if path.startswith("token") or path == "verify":
            name = payload.get("email", payload.get("refresh_token", "alice")).split("@")[0].split("-")[0]
            return {"access_token": name + "-access", "refresh_token": name + "-refresh", "expires_in": 3600}
        if path == "user" and method != "PUT":
            name = "alice" if token.startswith("alice") else "bob"
            return {"id": ALICE if name == "alice" else BOB, "email": name + "@example.test", "email_confirmed_at": "2026-10-19T00:00:00Z"}
        return {}


@pytest.fixture
def accounts(postgres_config, tmp_path):
    if not postgres_config:
        pytest.skip("Account isolation requires disposable PostgreSQL schemas.")
    application = create_app({"TESTING": True, "SECRET_KEY": "account-tests-only", "AUTH_ENABLED": True,
                              "SUPABASE_URL": "https://auth.example.invalid", "SUPABASE_PUBLISHABLE_KEY": "public-test-key",
                              **postgres_config})
    result = application.test_cli_runner().invoke(args=["migrate-db"])
    assert result.exit_code == 0, result.output
    application.extensions["supabase_auth"] = FakeAuth()
    return application


def submit(client, path, data, source=None):
    page = client.get(source or path)
    assert page.status_code == 200, page.get_data(as_text=True)
    parser = CSRFTokenParser()
    parser.feed(page.get_data(as_text=True))
    assert parser.token
    return client.post(path, data={**data, "csrf_token": parser.token})


def sign_in(application, name, complete_profile=True):
    client = application.test_client()
    response = submit(client, "/account/login", {"email": name + "@example.test", "password": "test-password"})
    assert response.status_code == 302, response.get_data(as_text=True)
    if complete_profile:
        with application.app_context():
            get_db().execute("UPDATE profiles SET display_name = ? WHERE id = ?", (name.capitalize(), ALICE if name == "alice" else BOB))
    return client


@pytest.fixture
def libraries(accounts):
    alice, bob = sign_in(accounts, "alice"), sign_in(accounts, "bob")
    with accounts.app_context():
        db = get_db()
        ids = {}
        for name, owner in (("alice", ALICE), ("bob", BOB)):
            game_id = db.execute("INSERT INTO games (title, platform, owner_id) VALUES (?, 'PC', ?) RETURNING id", (name + " secret game", owner)).fetchone()[0]
            list_id = db.execute("INSERT INTO game_lists (name, name_key, owner_id) VALUES ('Favorites', 'favorites', ?) RETURNING id", (owner,)).fetchone()[0]
            db.execute("INSERT INTO game_list_members (list_id, game_id, owner_id) VALUES (?, ?, ?)", (list_id, game_id, owner))
            ids[name] = (game_id, list_id)
        db.execute("INSERT INTO games (title, platform) VALUES ('Legacy private game', 'PC')")
    return alice, bob, ids


@pytest.mark.parametrize("path", ["/library", "/lists", "/games/new", "/games/pick", "/games/1", "/games/1/edit", "/games/1/delete", "/backups/import", "/backups/export"])
def test_anonymous_collection_access_requires_login(accounts, path):
    response = accounts.test_client().get(path)
    assert response.status_code == 302
    assert response.location.endswith("/account/login")


def test_public_landing_and_json_auth_boundary(accounts):
    client = accounts.test_client()
    assert client.get("/").status_code == 200
    for path in ("/catalog/search?q=Portal", "/catalog/games/123", "/library"):
        response = client.get(path, headers={"Accept": "application/json"})
        assert response.status_code == 401
        assert response.json["error"]


def test_private_collections_lists_statistics_and_exports(libraries):
    alice, bob, ids = libraries
    for client, name, other in ((alice, "alice", "bob"), (bob, "bob", "alice")):
        for path in ("/library", "/games/pick?pick=1", "/lists", "/backups/export"):
            response = client.get(path)
            assert response.status_code == 200
            body = response.get_data(as_text=True)
            if path != "/lists":
                assert name + " secret game" in body
            assert other + " secret game" not in body
            assert "Legacy private game" not in body
            assert response.headers["Cache-Control"] == "private, no-store"
        backup = client.get("/backups/export").json
        assert len(backup["games"]) == 1
        assert len(backup["lists"]) == 1
        assert "owner_id" not in json.dumps(backup)
        assert '<dd>1</dd>' in client.get("/account/profile").get_data(as_text=True)


def test_tampered_game_and_list_ids_cannot_read_or_write(libraries):
    alice, bob, ids = libraries
    game_id, list_id = ids["bob"]
    paths = [f"/games/{game_id}", f"/games/{game_id}/edit", f"/games/{game_id}/delete",
             f"/lists/{list_id}/edit", f"/lists/{list_id}/delete", f"/library?list={list_id}"]
    for path in paths:
        assert alice.get(path).status_code == 404
    for path in paths[1:5]:
        assert submit(alice, path, {"title": "Hijacked", "name": "Hijacked"}, source="/account/profile").status_code == 404
    assert "bob secret game" in bob.get("/library").get_data(as_text=True)
    assert "Favorites" in bob.get("/lists").get_data(as_text=True)


def test_membership_cannot_reference_other_account(libraries, accounts):
    alice, _, ids = libraries
    response = submit(alice, f"/lists/{ids['alice'][1]}/edit", {"name": "Favorites", "games": str(ids["bob"][0])})
    assert "no longer in your collection" in response.get_data(as_text=True)
    with accounts.app_context():
        db = get_db()
        assert db.execute("SELECT game_id FROM game_list_members WHERE list_id = ?", (ids["alice"][1],)).fetchone()[0] == ids["alice"][0]
        from psycopg import IntegrityError
        with pytest.raises(IntegrityError):
            db.execute("INSERT INTO game_list_members (list_id, game_id, owner_id) VALUES (?, ?, ?)", (ids["alice"][1], ids["bob"][0], ALICE))


def test_import_deduplication_and_memberships_are_per_account(libraries):
    alice, bob, _ = libraries
    backup = bob.get("/backups/export").json
    response = submit(alice, "/backups/import", {"confirm_import": "yes", "backup": (BytesIO(json.dumps(backup).encode()), "backup.json")})
    assert response.status_code == 200
    saved = alice.get("/backups/export").json
    assert len(saved["games"]) == 2
    assert len(saved["lists"]) == 1
    assert len(saved["lists"][0]["games"]) == 2
    assert len(bob.get("/backups/export").json["games"]) == 1


def test_profile_is_private_validated_and_escaped(libraries):
    alice, bob, _ = libraries
    response = submit(alice, "/account/profile", {"display_name": "<script>Alice</script>", "bio": "<b>Hello</b>", "avatar": "ghost"})
    assert response.status_code == 303
    response = alice.get(response.location)
    assert "Changes saved" in response.get_data(as_text=True)
    assert "&lt;script&gt;Alice&lt;/script&gt;" in response.get_data(as_text=True)
    assert "Alice" not in bob.get("/account/profile").get_data(as_text=True)
    response = submit(alice, "/account/profile", {"display_name": "x" * 61, "avatar": "invalid"})
    assert "Choose a name" in response.get_data(as_text=True)


def test_opaque_session_logout_and_csrf(accounts):
    client = sign_in(accounts, "alice")
    with client.session_transaction() as cookie:
        assert "account_session" in cookie
        assert "access_token" not in cookie and "refresh_token" not in cookie and "user_id" not in cookie
        opaque = cookie["account_session"]
    assert client.post("/account/logout").status_code == 400
    assert client.get("/account/logout").status_code == 405
    assert submit(client, "/account/logout", {}, source="/account/profile").status_code == 302
    assert client.get("/library").status_code == 302
    with accounts.app_context():
        assert get_db().execute("SELECT 1 FROM account_sessions WHERE id_hash = ?", (fingerprint(opaque),)).fetchone() is None
    with client.session_transaction() as cookie:
        cookie["account_session"] = opaque
    assert client.get("/library").status_code == 302


def test_refresh_invalid_tokens_and_provider_outage_fail_closed(accounts):
    client = sign_in(accounts, "alice")
    with accounts.app_context():
        get_db().execute("UPDATE account_sessions SET expires_at = 0")
    assert client.get("/library").status_code == 200
    fake = accounts.extensions["supabase_auth"]
    assert any(call[0] == "token?grant_type=refresh_token" for call in fake.calls)
    fake.unavailable = True
    assert client.get("/library").status_code == 503
    fake.unavailable = False
    assert client.get("/library").status_code == 200
    fake.invalid = True
    assert client.get("/library").status_code == 302


def test_expired_session_cannot_access_collection(accounts):
    client = sign_in(accounts, "alice")
    with accounts.app_context():
        get_db().execute("UPDATE account_sessions SET valid_until = 0")
    assert client.get("/library").status_code == 302


def test_registration_confirmation_login_errors_and_csrf(accounts):
    client = accounts.test_client()
    assert client.post("/account/register", data={"email": "alice@example.test", "password": "test-password"}).status_code == 400
    response = submit(client, "/account/register", {"email": "alice@example.test", "password": "test-password"})
    assert "Check your email" in response.get_data(as_text=True)
    assert client.get("/library").status_code == 302
    accounts.extensions["supabase_auth"].invalid = True
    assert submit(client, "/account/login", {"email": "alice@example.test", "password": "test-password"}).status_code == 400


def test_password_recovery_cannot_be_used_to_browse_and_revokes_old_sessions(accounts):
    previous = sign_in(accounts, "alice")
    client = accounts.test_client()
    response = submit(client, "/account/recover", {"email": "alice@example.test"})
    assert "If an account exists" in response.get_data(as_text=True)
    response = submit(client, "/account/verify-recovery", {"email": "alice@example.test", "code": "123456"})
    assert response.location.endswith("/account/password")
    assert client.get("/library").location.endswith("/account/password")
    assert client.get("/account/profile").location.endswith("/account/password")
    response = submit(client, "/account/password", {"password": "new-test-password", "confirmation": "new-test-password"})
    assert response.location.endswith("/account/login")
    assert previous.get("/library").status_code == 302


def test_legacy_collection_requires_explicit_assignment(libraries, accounts):
    alice, _, _ = libraries
    runner = accounts.test_cli_runner()
    assert runner.invoke(args=["assign-legacy-collection", "--user-id", "invalid"]).exit_code != 0
    result = runner.invoke(args=["assign-legacy-collection", "--user-id", ALICE])
    assert result.exit_code == 0 and "Found 1 games" in result.output
    assert "Legacy private game" not in alice.get("/library").get_data(as_text=True)
    result = runner.invoke(args=["assign-legacy-collection", "--user-id", ALICE, "--apply"])
    assert result.exit_code == 0, result.output
    assert "Legacy private game" in alice.get("/library").get_data(as_text=True)


def test_default_recovery_email_uses_browser_bound_pkce(accounts):
    from base64 import urlsafe_b64encode
    from hashlib import sha256
    client = accounts.test_client()
    submit(client, "/account/recover", {"email": "alice@example.test"})
    fake = accounts.extensions["supabase_auth"]
    call = next(call for call in fake.calls if call[0] == "recover")
    with client.session_transaction() as cookie:
        verifier = cookie["recovery_verifier"]
    assert call[1]["code_challenge_method"] == "s256"
    assert call[1]["code_challenge"] == urlsafe_b64encode(sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert verifier not in str(call)
    code = "33333333-3333-4333-8333-333333333333"
    unrelated = accounts.test_client()
    assert unrelated.get("/account/login?code=" + code).location.endswith("/account/recover")
    assert not any(call[0] == "token?grant_type=pkce" for call in fake.calls)
    response = client.get("/account/login?code=" + code)
    assert response.location.endswith("/account/password")
    assert "code=" not in response.location
    assert client.get("/library").location.endswith("/account/password")
    assert client.get("/account/login?code=" + code).location.endswith("/account/recover")


@pytest.mark.parametrize("failure", ["expired", "malformed", "provider", "wrong-email"])
def test_recovery_links_fail_closed(accounts, failure):
    client = accounts.test_client()
    submit(client, "/account/recover", {"email": "bob@example.test" if failure == "wrong-email" else "alice@example.test"})
    if failure == "expired":
        with client.session_transaction() as cookie:
            cookie["recovery_started"] = 0
    if failure == "provider":
        accounts.extensions["supabase_auth"].invalid = True
    code = "invalid" if failure == "malformed" else "33333333-3333-4333-8333-333333333333"
    response = client.get("/account/login?code=" + code)
    assert response.location.endswith("/account/recover")
    assert client.get("/library").location.endswith("/account/login")
    with client.session_transaction() as cookie:
        assert "recovery_verifier" not in cookie
        assert "account_session" not in cookie


def test_database_tables_remain_denied_to_public_api_roles(accounts):
    with accounts.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM pg_policies WHERE schemaname = current_schema()").fetchone()[0] == 0
        rows = db.execute("SELECT relrowsecurity FROM pg_class WHERE relnamespace = current_schema()::regnamespace AND relname IN ('profiles', 'account_sessions', 'games', 'game_lists', 'game_list_members')").fetchall()
        assert len(rows) == 5 and all(row[0] for row in rows)


def test_game_create_update_delete_and_list_limits_use_current_owner(accounts):
    game_data = {"title": "Portal 2", "platform": "PC", "status": "Playing", "rating": "9", "review": "A great puzzle game.", "igdb_id": "123"}
    alice, bob = sign_in(accounts, "alice"), sign_in(accounts, "bob")
    from unittest.mock import Mock
    catalog = Mock()
    catalog.get_game.return_value = {"id": 123, "name": "Portal 2", "platforms": [{"id": 6, "name": "PC"}]}
    accounts.extensions["igdb_client"] = catalog
    for client in (alice, bob):
        assert submit(client, "/games/new", game_data).status_code == 302
        assert "already in your collection" in submit(client, "/games/new", game_data).get_data(as_text=True)
        assert submit(client, "/lists", {"name": "Shared name"}).status_code == 302
    with accounts.app_context():
        db = get_db()
        alice_id = db.execute("SELECT id FROM games WHERE owner_id = ?", (ALICE,)).fetchone()[0]
        for number in range(99):
            db.execute("INSERT INTO game_lists (name, name_key, owner_id) VALUES (?, ?, ?)", (f"List {number}", f"list {number}", ALICE))
    assert "up to 100 lists" in submit(alice, "/lists", {"name": "Overflow"}).get_data(as_text=True)
    assert submit(bob, "/lists", {"name": "Still allowed"}).status_code == 302
    assert submit(alice, f"/games/{alice_id}/edit", {**game_data, "review": "Alice's new review"}).status_code == 302
    assert "Alice&#39;s new review" not in bob.get("/library").get_data(as_text=True)
    assert submit(alice, f"/games/{alice_id}/delete", {}).status_code == 302
    assert len(alice.get("/backups/export").json["games"]) == 0
    assert len(bob.get("/backups/export").json["games"]) == 1


def test_first_login_requires_profile_before_library_and_saved_profile_unlocks_it(accounts):
    client = sign_in(accounts, "alice", complete_profile=False)
    for path in ("/library", "/lists", "/games/new", "/games/pick", "/backups/export"):
        assert client.get(path).location.endswith("/account/profile")
    response = client.get("/catalog/search?q=Portal", headers={"Accept": "application/json"})
    assert response.status_code == 409 and response.json["profile_url"] == "/account/profile"
    page = client.get("/account/profile")
    assert "Create your profile" in page.get_data(as_text=True)
    result = submit(client, "/account/profile", {"display_name": "New player", "bio": "", "avatar": "rocket"})
    assert result.status_code == 303 and result.location.endswith("#profile-feedback")
    saved = client.get(result.location)
    assert "Your profile is ready" in saved.get_data(as_text=True)
    assert 'data-saved="true"' in saved.get_data(as_text=True)
    assert "Open library" in saved.get_data(as_text=True)
    assert client.get("/library").status_code == 200
    assert "Your profile is ready" not in client.get("/account/profile").get_data(as_text=True)
    submit(client, "/account/logout", {}, source="/account/profile")
    result = submit(client, "/account/login", {"email": "alice@example.test", "password": "test-password"})
    assert result.location.endswith("/library")


def test_invalid_setup_preserves_fields_and_does_not_unlock_collection(accounts):
    client = sign_in(accounts, "alice", complete_profile=False)
    response = submit(client, "/account/profile", {"display_name": "   ", "bio": "A story in progress", "avatar": "ghost"})
    body = response.get_data(as_text=True)
    assert response.status_code == 200 and "Choose a name" in body
    assert "A story in progress" in body
    assert 'name="avatar_color" value="#64748b"' in body
    assert client.get("/library").location.endswith("/account/profile")


def test_confirmed_registration_with_provider_session_goes_to_creator(accounts):
    fake = accounts.extensions["supabase_auth"]
    original = fake.call
    def confirmed_signup(path, payload=None, token=None, method=None):
        if path == "signup":
            return {"access_token": "alice-access", "refresh_token": "alice-refresh", "expires_in": 3600}
        return original(path, payload, token, method)
    fake.call = confirmed_signup
    client = accounts.test_client()
    response = submit(client, "/account/register", {"email": "alice@example.test", "password": "test-password"})
    assert response.location.endswith("/account/profile")
    assert "Create your profile" in client.get(response.location).get_data(as_text=True)


def test_registration_still_requires_a_provider_confirmed_email(accounts):
    fake = accounts.extensions["supabase_auth"]
    original = fake.call
    def unconfirmed_signup(path, payload=None, token=None, method=None):
        if path == "signup":
            return {"access_token": "alice-access", "refresh_token": "alice-refresh", "expires_in": 3600}
        if path == "user":
            return {"id": ALICE, "email_confirmed_at": None}
        return original(path, payload, token, method)
    fake.call = unconfirmed_signup
    client = accounts.test_client()
    response = submit(client, "/account/register", {"email": "alice@example.test", "password": "test-password"})
    assert "Registration could not be completed" in response.get_data(as_text=True)
    assert client.get("/account/profile").location.endswith("/account/login")
    with accounts.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0


def test_profile_save_feedback_is_specific_to_current_account_and_not_query_parameters(libraries):
    alice, bob, _ = libraries
    response = submit(alice, "/account/profile", {"display_name": "Alice", "avatar": "star", "bio": "Saved biography"})
    assert response.status_code == 303
    assert 'data-saved="true"' in alice.get(response.location).get_data(as_text=True)
    assert 'data-saved="true"' not in bob.get("/account/profile?saved=1").get_data(as_text=True)
    assert 'data-saved="true"' not in alice.get("/account/profile?saved=1").get_data(as_text=True)


def test_uploaded_photo_is_private_normalized_and_can_be_removed(accounts):
    from PIL import Image
    alice, bob = sign_in(accounts, "alice"), sign_in(accounts, "bob")
    image = BytesIO()
    Image.new("RGB", (400, 200), "blue").save(image, format="PNG")
    image.seek(0)
    result = submit(alice, "/account/profile", {"display_name": "Alice", "avatar_color": "#aa44bb", "photo": (image, "photo.png")})
    assert result.status_code == 303
    photo = alice.get("/account/profile/photo")
    assert photo.status_code == 200 and photo.mimetype == "image/jpeg"
    assert photo.headers["Cache-Control"] == "private, no-store"
    assert photo.headers["X-Content-Type-Options"] == "nosniff"
    assert Image.open(BytesIO(photo.data)).size == (256, 256)
    assert bob.get("/account/profile/photo").status_code == 404
    assert accounts.test_client().get("/account/profile/photo").status_code == 401
    assert alice.get("/account/profile/photo?user_id=" + BOB).data == photo.data
    invalid = submit(alice, "/account/profile", {"display_name": "Changed", "photo": (BytesIO(b"<svg/>"), "bad.png")})
    assert "Choose a valid" in invalid.get_data(as_text=True)
    assert alice.get("/account/profile/photo").data == photo.data
    with accounts.app_context():
        row = get_db().execute("SELECT display_name, avatar_color FROM profiles WHERE id = ?", (ALICE,)).fetchone()
        assert row["display_name"] == "Alice" and row["avatar_color"] == "#aa44bb"
    result = submit(alice, "/account/profile", {"display_name": "Alice", "remove_photo": "yes", "avatar_color": "#228844"})
    assert result.status_code == 303
    assert alice.get("/account/profile/photo").status_code == 404
    assert 'name="avatar_color" value="#228844"' in alice.get("/account/profile").get_data(as_text=True)


def test_photo_requests_keep_csrf_size_and_color_validation(accounts):
    client = sign_in(accounts, "alice")
    assert client.post("/account/profile", data={"display_name": "Alice"}).status_code == 400
    invalid = submit(client, "/account/profile", {"display_name": "Alice", "avatar_color": "red; background:url(evil)"})
    assert "Choose a valid profile color" in invalid.get_data(as_text=True)
    oversized = submit(client, "/account/profile", {"display_name": "Alice", "photo": (BytesIO(b"x" * (4 * 1024 * 1024)), "huge.jpg")})
    assert oversized.status_code == 303
    assert "Your previous profile has been kept" in client.get(oversized.location).get_data(as_text=True)


def test_profile_saves_chosen_crop_and_rejects_invalid_crop_without_replacing_photo(accounts):
    from PIL import Image
    client = sign_in(accounts, "alice")
    def photo():
        stream = BytesIO()
        source = Image.new("RGB", (400, 200), "red")
        source.paste(Image.new("RGB", (200, 200), "blue"), (200, 0))
        source.save(stream, format="PNG")
        stream.seek(0)
        return stream, "split.png"
    result = submit(client, "/account/profile", {"display_name":"Alice", "photo":photo(), "photo_crop":'{"x":200,"y":0,"size":200}'})
    assert result.status_code == 303
    saved = client.get("/account/profile/photo").data
    with Image.open(BytesIO(saved)) as image:
        assert image.getpixel((128,128))[2] > 230
    result = submit(client, "/account/profile", {"display_name":"Alice", "photo":photo(), "photo_crop":'{"x":200,"y":0,"size":400}'})
    assert "Choose a crop inside" in result.get_data(as_text=True)
    assert client.get("/account/profile/photo").data == saved
