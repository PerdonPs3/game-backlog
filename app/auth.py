"""Supabase password authentication with opaque, server-side sessions."""

from hashlib import sha256
from base64 import urlsafe_b64encode
import json
from secrets import token_urlsafe
from time import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

import click
from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask.cli import with_appcontext

from app.db import get_db


auth = Blueprint("auth", __name__, url_prefix="/account")
SESSION_SECONDS = 12 * 60 * 60


class AuthError(Exception):
    def __init__(self, unavailable=False):
        self.unavailable = unavailable


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class SupabaseAuth:
    def call(self, path, payload=None, token=None, method=None):
        headers = {"apikey": current_app.config["SUPABASE_PUBLISHABLE_KEY"], "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = Request(current_app.config["SUPABASE_URL"].rstrip("/") + "/auth/v1/" + path,
                      data=json.dumps(payload).encode() if payload is not None else None,
                      headers=headers, method=method or ("POST" if payload is not None else "GET"))
        try:
            with build_opener(NoRedirects()).open(req, timeout=10) as response:
                raw = response.read(1024 * 1024)
                result = json.loads(raw) if raw else {}
                if not isinstance(result, dict):
                    raise ValueError("Invalid auth response")
                return result
        except HTTPError as error:
            raise AuthError(unavailable=error.code >= 500 or error.code == 429) from None
        except (URLError, OSError, ValueError, UnicodeError):
            raise AuthError(unavailable=True) from None


def provider():
    return current_app.extensions.setdefault("supabase_auth", SupabaseAuth())


def fingerprint(value):
    return sha256(value.encode()).hexdigest()


def verified_user(token):
    user = provider().call("user", token=token)
    try:
        if not isinstance(user, dict) or not isinstance(user.get("id"), str):
            raise ValueError("Invalid user identity")
        user["id"] = str(UUID(user["id"]))
        if not user.get("email_confirmed_at"):
            raise ValueError("Unconfirmed email")
    except (KeyError, TypeError, ValueError):
        raise AuthError() from None
    return user


def token_fields(payload):
    try:
        access, refresh = payload["access_token"], payload["refresh_token"]
        lifetime = payload["expires_in"]
        if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh:
            raise ValueError()
        if type(lifetime) is not int or not 0 < lifetime <= 7 * 86400:
            raise ValueError()
        return access, refresh, int(time()) + lifetime
    except (KeyError, TypeError, ValueError):
        raise AuthError(unavailable=True) from None


def start_session(payload, recovery=False):
    access, refresh, expiry = token_fields(payload)
    user = verified_user(access)
    db = get_db()
    db.execute("INSERT INTO profiles (id) VALUES (?) ON CONFLICT (id) DO NOTHING", (user["id"],))
    old = session.get("account_session")
    if isinstance(old, str):
        db.execute("DELETE FROM account_sessions WHERE id_hash = ?", (fingerprint(old),))
    # Tokens never enter Flask's signed-but-readable session cookie.
    opaque = token_urlsafe(32)
    db.execute("DELETE FROM account_sessions WHERE valid_until <= ?", (int(time()),))
    db.execute("INSERT INTO account_sessions (id_hash, user_id, access_token, refresh_token, expires_at, valid_until, recovery) VALUES (?, ?, ?, ?, ?, ?, ?)",
               (fingerprint(opaque), user["id"], access, refresh, expiry, int(time()) + SESSION_SECONDS, int(recovery)))
    session.clear()
    session["account_session"] = opaque


def load_user():
    g.user = None
    g.account_session = None
    if not current_app.config.get("AUTH_ENABLED") or request.endpoint == "static":
        return
    opaque = session.get("account_session")
    if not isinstance(opaque, str) or len(opaque) > 100:
        return
    db = get_db()
    key = fingerprint(opaque)
    # Lock refresh rotation across concurrent requests, including pooled connections.
    db.execute("BEGIN")
    try:
        stored = db.execute("SELECT * FROM account_sessions WHERE id_hash = ? FOR UPDATE", (key,)).fetchone()
        if stored is None or stored["valid_until"] <= int(time()):
            db.execute("DELETE FROM account_sessions WHERE id_hash = ?", (key,))
            session.clear()
            db.commit()
            return
        access = stored["access_token"]
        if stored["expires_at"] <= int(time()) + 30:
            payload = provider().call("token?grant_type=refresh_token", {"refresh_token": stored["refresh_token"]})
            access, refresh, expiry = token_fields(payload)
            db.execute("UPDATE account_sessions SET access_token = ?, refresh_token = ?, expires_at = ? WHERE id_hash = ?",
                       (access, refresh, expiry, key))
        user = verified_user(access)
        if user["id"] != str(stored["user_id"]):
            raise AuthError()
        g.user = user
        g.account_session = {"id_hash": key, "access_token": access, "recovery": bool(stored["recovery"])}
        db.commit()
    except AuthError as error:
        db.rollback()
        if error.unavailable:
            abort(503, description="Account services are temporarily unavailable. Please try again.")
        db.execute("DELETE FROM account_sessions WHERE id_hash = ?", (key,))
        session.clear()
    except Exception:
        db.rollback()
        raise


def protect_collection():
    if not current_app.config.get("AUTH_ENABLED"):
        return
    if request.blueprint == "main" and request.endpoint != "main.welcome":
        if not g.user:
            if request.accept_mimetypes.best == "application/json" or request.path.startswith("/catalog/"):
                return jsonify(error="Please sign in to access your library."), 401
            return redirect(url_for("auth.login"))
        if g.account_session["recovery"]:
            return redirect(url_for("auth.password"))


@auth.before_request
def require_accounts():
    if not current_app.config.get("AUTH_ENABLED"):
        abort(404)


def credentials():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    if not email or len(email) > 254 or "@" not in email or not 8 <= len(password) <= 128:
        raise ValueError("Enter a valid email and a password with 8 to 128 characters.")
    return {"email": email, "password": password}


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET" and "code" in request.args:
        return complete_recovery_link()
    error = None
    status = 200
    if request.method == "POST":
        try:
            start_session(provider().call("token?grant_type=password", credentials()))
            return redirect(url_for("main.index"))
        except ValueError as problem:
            error = str(problem)
        except AuthError as problem:
            status = 503 if problem.unavailable else 400
            error = "Account services are temporarily unavailable. Try again shortly." if problem.unavailable else "Could not sign in. Check your credentials and confirm your email."
    return render_template("account_auth.html", mode="login", error=error), status


def complete_recovery_link():
    """Exchange a one-use code bound to this browser's recovery request."""
    verifier = session.pop("recovery_verifier", None)
    started = session.pop("recovery_started", None)
    email = session.pop("recovery_email", None)
    try:
        code = str(UUID(request.args.get("code", "")))
        if not isinstance(verifier, str) or not 43 <= len(verifier) <= 128 or type(started) is not int or not 0 <= time() - started <= 1800 or not isinstance(email, str):
            raise ValueError("No active recovery request")
        payload = provider().call("token?grant_type=pkce", {"auth_code": code, "code_verifier": verifier})
        access, _, _ = token_fields(payload)
        user = verified_user(access)
        if user.get("email", "").casefold() != email.casefold():
            raise AuthError()
        start_session(payload, recovery=True)
        return redirect(url_for("auth.password"))
    except (ValueError, AuthError):
        flash("This recovery link is invalid, expired, or unavailable. Request a new link and open it in the same browser.", "account")
        # Remove the code from the address bar, including on failed exchanges.
        return redirect(url_for("auth.recover"))


@auth.route("/register", methods=["GET", "POST"])
def register():
    error = message = None
    if request.method == "POST":
        try:
            provider().call("signup", credentials())
            message = "Check your email to confirm your account, then sign in. If you already have an account, use Sign in."
        except ValueError as problem:
            error = str(problem)
        except AuthError:
            # Do not disclose whether an email already has an account.
            error = "Registration could not be completed. Try again later or sign in if you have an account."
    return render_template("account_auth.html", mode="register", error=error, message=message)


@auth.route("/recover", methods=["GET", "POST"])
def recover():
    error = message = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email or len(email) > 254 or "@" not in email:
            error = "Enter a valid email address."
        else:
            verifier = token_urlsafe(48)
            session["recovery_verifier"] = verifier
            session["recovery_started"] = int(time())
            session["recovery_email"] = email
            challenge = urlsafe_b64encode(sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            try:
                provider().call("recover", {"email": email, "code_challenge": challenge, "code_challenge_method": "s256"})
            except AuthError:
                pass
            message = "If an account exists, a recovery email will arrive shortly. Open its link in this browser within 30 minutes. If the email contains a code instead, use I have a recovery code."
    return render_template("account_auth.html", mode="recover", error=error, message=message)


@auth.route("/verify-recovery", methods=["GET", "POST"])
def verify_recovery():
    error = None
    if request.method == "POST":
        email, code = request.form.get("email", "").strip(), request.form.get("code", "").strip()
        if not email or len(email) > 254 or "@" not in email or not code.isascii() or not code.isdigit() or not 6 <= len(code) <= 10:
            error = "Enter your email and the recovery code."
        else:
            try:
                payload = provider().call("verify", {"email": email, "token": code, "type": "recovery"})
                start_session(payload, recovery=True)
                return redirect(url_for("auth.password"))
            except AuthError:
                error = "This recovery code is invalid, expired, or temporarily unavailable. Request a new code."
    return render_template("account_auth.html", mode="verify-recovery", error=error)


@auth.route("/password", methods=["GET", "POST"])
def password():
    if not g.user or not g.account_session["recovery"]:
        return redirect(url_for("auth.recover"))
    error = None
    if request.method == "POST":
        value = request.form.get("password", "")
        if not 8 <= len(value) <= 128 or value != request.form.get("confirmation"):
            error = "Use 8 to 128 characters and matching passwords."
        else:
            try:
                provider().call("user", {"password": value}, token=g.account_session["access_token"], method="PUT")
                get_db().execute("DELETE FROM account_sessions WHERE user_id = ?", (g.user["id"],))
                session.clear()
                return redirect(url_for("auth.login"))
            except AuthError:
                error = "Could not update your password. Try again or request a new code."
    return render_template("account_auth.html", mode="password", error=error)


@auth.post("/logout")
def logout():
    if g.account_session:
        get_db().execute("DELETE FROM account_sessions WHERE id_hash = ?", (g.account_session["id_hash"],))
        try:
            provider().call("logout?scope=local", {}, token=g.account_session["access_token"])
        except AuthError:
            pass
    session.clear()
    return redirect(url_for("auth.login"))


@auth.route("/profile", methods=["GET", "POST"])
def profile():
    if not g.user:
        return redirect(url_for("auth.login"))
    if g.account_session["recovery"]:
        return redirect(url_for("auth.password"))
    db = get_db()
    error = message = None
    if request.method == "POST":
        name, bio = request.form.get("display_name", "").strip(), request.form.get("bio", "").strip()
        avatar = request.form.get("avatar", "controller")
        if not 1 <= len(name) <= 60 or len(bio) > 500 or avatar not in ("controller", "star", "ghost", "rocket") or any(ord(char) < 32 for char in name):
            error = "Choose a name with 1 to 60 characters, a bio up to 500 characters, and an available avatar."
        else:
            db.execute("UPDATE profiles SET display_name = ?, bio = ?, avatar = ? WHERE id = ?", (name, bio, avatar, g.user["id"]))
            message = "Profile saved. Your profile and library are private."
    item = db.execute("SELECT display_name, bio, avatar FROM profiles WHERE id = ?", (g.user["id"],)).fetchone()
    from app.routes import collection_statistics
    return render_template("account_profile.html", profile=item, stats=collection_statistics(db), error=error, message=message)


@click.command("assign-legacy-collection")
@click.option("--user-id", required=True, help="Verified account UUID from Supabase Authentication > Users.")
@click.option("--apply", is_flag=True, help="Assign unowned rows. Default: inspect counts only.")
@with_appcontext
def assign_legacy(user_id, apply):
    """Assign the old shared collection only to an explicitly chosen account."""
    try:
        user_id = str(UUID(user_id))
    except ValueError:
        raise click.ClickException("Provide a valid account UUID.") from None
    if not current_app.config.get("DATABASE_URL"):
        raise click.ClickException("This command requires PostgreSQL.")
    db = get_db()
    db.execute("BEGIN")
    try:
        db.execute("LOCK TABLE games, game_lists, game_list_members IN SHARE ROW EXCLUSIVE MODE")
        if not db.execute("SELECT 1 FROM profiles WHERE id = ?", (user_id,)).fetchone():
            raise click.ClickException("The account must sign in once before assignment.")
        counts = [db.execute(f"SELECT COUNT(*) FROM {table} WHERE owner_id IS NULL").fetchone()[0] for table in ("games", "game_lists")]
        if apply:
            for table in ("games", "game_lists", "game_list_members"):
                db.execute(f"UPDATE {table} SET owner_id = ? WHERE owner_id IS NULL", (user_id,))
            db.commit()
        else:
            db.rollback()
        click.echo(f"{'Assigned' if apply else 'Found'} {counts[0]} games and {counts[1]} lists. Owner: {user_id}.")
    except Exception:
        db.rollback()
        raise


def init_app(app):
    app.register_blueprint(auth)
    app.before_request(load_user)
    app.before_request(protect_collection)
    app.cli.add_command(assign_legacy)

    @app.context_processor
    def account_context():
        return {"accounts_enabled": app.config.get("AUTH_ENABLED", False), "account_user": getattr(g, "user", None)}

    @app.after_request
    def private_responses(response):
        if app.config.get("AUTH_ENABLED") and request.endpoint != "static":
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["Referrer-Policy"] = "same-origin"
            response.vary.add("Cookie")
        return response
