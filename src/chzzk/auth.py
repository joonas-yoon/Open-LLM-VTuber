"""Chzzk authentication module for OAuth2 token handling."""
import httpx
import threading

from urllib.parse import quote
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from loguru import logger

CHZZK_AUTH_URL = "https://chzzk.naver.com/account-interlock"
CHZZK_API_URL = "https://openapi.chzzk.naver.com"


class ChzzkAuth:
    """Handles Chzzk/Naver OAuth2 authentication flow.

    Args:
        client_id: OAuth2 client ID.
        client_secret: OAuth2 client secret.
    """
    CHZZK_TOKEN_URL = f"{CHZZK_API_URL}/auth/v1/token"

    def __init__(self, client_id: str, client_secret: str) -> None:
        """Initialize Chzzk authentication handler.

        Args:
            client_id: OAuth2 client ID.
            client_secret: OAuth2 client secret.
        """
        self.client_id = client_id
        self.client_secret = client_secret

    def get_auth_url(self, redirect_uri: str, state: str) -> str:
        """Generate OAuth2 authorization URL.

        Args:
            redirect_uri: Redirect URI for OAuth2 callback.
            state: State parameter for CSRF protection.

        Returns:
            Authorization URL for user redirect.
        """
        encoded_redirect = quote(redirect_uri, safe="")
        return (
            f"{CHZZK_AUTH_URL}"
            f"?response_type=code"
            f"&clientId={self.client_id}"
            f"&redirectUri={encoded_redirect}"
            f"&state={state}"
        )

    def get_access_token(
        self, code: str, state: str, redirect_uri: str
    ) -> dict | str:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth2 callback.
            state: State parameter from OAuth2 callback.
            redirect_uri: Redirect URI used in authorization request.

        Returns:
            Token response dictionary on success, or error message string on failure.
        """
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.client_secret}",
        }

        data = {
            "grantType": "authorization_code",
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "code": code,
            "state": state,
            "redirectUri": redirect_uri,
        }

        try:
            response = httpx.post(
                self.CHZZK_TOKEN_URL, headers=headers, json=data, timeout=10.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            return error_msg
        except httpx.RequestError as e:
            error_msg = f"Request error: {e}"
            logger.error(error_msg)
            return error_msg


class CallbackHandler(BaseHTTPRequestHandler):
    response_queue = None

    def do_GET(self):
        if self.path.startswith("/callback"):
            query_params = parse_qs(urlparse(self.path).query)
            code = query_params.get("code", [None])[0]
            state = query_params.get("state", [None])[0]

            print(f"✓ Callback received: code={code}, state={state}")

            # Put the code and state into the queue
            if self.response_queue:
                self.response_queue.put((code, state))

            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<html><body>"
                             b"<h1>Authorization successful!</h1>"
                             b"<p>You can close this window.</p>"
                             b"</body></html>")

            # Stop the server
            threading.Thread(target=self.server.shutdown,
                             daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()
