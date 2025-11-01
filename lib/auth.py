"""OAuth 2.0 authentication module for Fitbit API.

This module handles the OAuth 2.0 authentication flow including authorization
and token management.

Juan Hernandez-Vargas - 2025
"""

import base64
import json
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from typing import Any
from typing import Dict
from typing import Optional
from urllib.parse import parse_qs
from urllib.parse import urlencode
from urllib.parse import urlparse

import requests


class FitbitAuth:
    """Handles Fitbit OAuth 2.0 authentication flow."""

    AUTHORIZATION_URI = 'https://www.fitbit.com/oauth2/authorize'
    TOKEN_URI = 'https://api.fitbit.com/oauth2/token'

    def __init__(self, client_id: str, client_secret: str, redirect_url: str):
        """Initialize FitbitAuth with OAuth credentials.

        Args:
            client_id: OAuth 2.0 client ID.
            client_secret: OAuth 2.0 client secret.
            redirect_url: OAuth 2.0 redirect URL.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_url = redirect_url
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_type: Optional[str] = None
        self.expires_in: Optional[int] = None

    def _generate_code_verifier(self) -> str:
        """Generate a code verifier for PKCE.

        Returns:
            A random code verifier string.
        """
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

    def _generate_code_challenge(self, verifier: str) -> str:
        """Generate a code challenge from the verifier for PKCE.

        Args:
            verifier: The code verifier.

        Returns:
            The code challenge.
        """
        return verifier

    def get_authorization_url(self, scopes: list[str]) -> tuple[str, str]:
        """Generate the authorization URL for OAuth flow.

        Args:
            scopes: List of permission scopes to request.

        Returns:
            Tuple of (authorization_url, code_verifier).
        """
        code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(code_verifier)

        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_url,
            'scope': ' '.join(scopes),
            'code_challenge': code_challenge,
            'code_challenge_method': 'plain',
        }

        auth_url = f'{self.AUTHORIZATION_URI}?{urlencode(params)}'
        return auth_url, code_verifier

    def exchange_code_for_token(self, code: str, code_verifier: str) -> Dict[str, Any]:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code received from callback.
            code_verifier: Code verifier used in authorization.

        Returns:
            Dictionary containing token information.

        Raises:
            requests.exceptions.HTTPError: If token exchange fails.
        """
        auth_header = base64.b64encode(
            f'{self.client_id}:{self.client_secret}'.encode()
        ).decode()

        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = {
            'client_id': self.client_id,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_url,
            'code_verifier': code_verifier,
        }

        response = requests.post(self.TOKEN_URI, headers=headers, data=data)
        response.raise_for_status()

        token_data = response.json()
        self.access_token = token_data.get('access_token')
        self.refresh_token = token_data.get('refresh_token')
        self.token_type = token_data.get('token_type')
        self.expires_in = token_data.get('expires_in')

        return token_data

    def refresh_access_token(self) -> Dict[str, Any]:
        """Refresh the access token using refresh token.

        Returns:
            Dictionary containing new token information.

        Raises:
            ValueError: If refresh token is not available.
            requests.exceptions.HTTPError: If token refresh fails.
        """
        if not self.refresh_token:
            raise ValueError('No refresh token available')

        auth_header = base64.b64encode(
            f'{self.client_id}:{self.client_secret}'.encode()
        ).decode()

        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
        }

        response = requests.post(self.TOKEN_URI, headers=headers, data=data)
        response.raise_for_status()

        token_data = response.json()
        self.access_token = token_data.get('access_token')
        self.refresh_token = token_data.get('refresh_token')
        self.token_type = token_data.get('token_type')
        self.expires_in = token_data.get('expires_in')

        return token_data

    def authorize(self, scopes: list[str]) -> Dict[str, Any]:
        """Complete the full OAuth authorization flow.

        Args:
            scopes: List of permission scopes to request.

        Returns:
            Dictionary containing token information.
        """
        auth_url, code_verifier = self.get_authorization_url(scopes)

        print(f'Opening browser for authorization: {auth_url}')
        webbrowser.open(auth_url)

        # Parse redirect URL to get port
        parsed_url = urlparse(self.redirect_url)
        port = parsed_url.port or 8080

        # Start local server to capture callback
        auth_code = self._run_callback_server(port)

        if not auth_code:
            raise ValueError('Authorization failed: No code received')

        return self.exchange_code_for_token(auth_code, code_verifier)

    def _run_callback_server(self, port: int) -> Optional[str]:
        """Run a local HTTP server to capture OAuth callback.

        Args:
            port: Port number to run the server on.

        Returns:
            Authorization code from the callback, or None if failed.
        """
        auth_code = None

        class CallbackHandler(BaseHTTPRequestHandler):
            """Handle OAuth callback request."""

            def do_GET(self):
                """Handle GET request from OAuth callback."""
                nonlocal auth_code

                parsed_path = urlparse(self.path)
                query_params = parse_qs(parsed_path.query)

                if 'code' in query_params:
                    auth_code = query_params['code'][0]
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(
                        b'<html><body><h1>Authorization successful!</h1>'
                        b'<p>You can close this window.</p></body></html>'
                    )
                else:
                    self.send_response(400)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(
                        b'<html><body><h1>Authorization failed!</h1></body></html>'
                    )

            def log_message(self, format, *args):
                """Suppress server log messages."""
                pass

        server = HTTPServer(('localhost', port), CallbackHandler)
        print(f'Waiting for authorization callback on port {port}...')
        server.handle_request()

        return auth_code

    def save_tokens(self, filepath: str) -> None:
        """Save tokens to a file.

        Args:
            filepath: Path to save tokens to.
        """
        token_data = {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'token_type': self.token_type,
            'expires_in': self.expires_in,
        }

        with open(filepath, 'w') as f:
            json.dump(token_data, f, indent=2)

    def load_tokens(self, filepath: str) -> None:
        """Load tokens from a file.

        Args:
            filepath: Path to load tokens from.
        """
        with open(filepath, 'r') as f:
            token_data = json.load(f)

        self.access_token = token_data.get('access_token')
        self.refresh_token = token_data.get('refresh_token')
        self.token_type = token_data.get('token_type')
        self.expires_in = token_data.get('expires_in')
