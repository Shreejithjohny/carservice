"""
"Sign in with Google": checks the ID token (the `credential`) that Google's sign-in button gives
the browser. The token is verified with Google's public keys by the official google-auth library:
signature, expiry, issuer, and that it was issued for this app's client ID (GOOGLE_CLIENT_ID).
"""
from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


class GoogleSignInError(Exception):
    """The credential is invalid, expired, for another app, or has no verified email."""


class GoogleUnavailableError(Exception):
    """Google's keys could not be fetched (network problem); worth retrying."""


def verify_google_credential(credential: str, client_id: str) -> dict:
    """Returns the token's claims (email, given_name, family_name, ...) or raises."""
    try:
        claims = id_token.verify_oauth2_token(credential, google_requests.Request(), client_id, clock_skew_in_seconds=10)
    except google_exceptions.TransportError as exc:
        raise GoogleUnavailableError(str(exc)) from exc
    except ValueError as exc:  # bad signature, expired, wrong audience or issuer, malformed
        raise GoogleSignInError(str(exc)) from exc
    if not claims.get("email") or claims.get("email_verified") is not True:
        raise GoogleSignInError("Google account has no verified email address")
    return claims
