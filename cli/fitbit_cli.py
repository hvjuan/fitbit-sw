"""Command-line interface for Fitbit API.

This CLI utility provides commands to authenticate with Fitbit and download
heart rate/pulse data.

Juan Hernandez-Vargas - 2025
"""

import json
import os
import sys
from pathlib import Path

import click

import lib.auth
import lib.client


DEFAULT_TOKEN_FILE = '.fitbit_tokens.json'
DEFAULT_SCOPES = ['activity', 'heartrate', 'profile']


@click.group()
@click.pass_context
def cli(ctx):
    """Fitbit API CLI tool for authentication and data retrieval."""
    ctx.ensure_object(dict)


@cli.command()
@click.option(
    '--client-id',
    envvar='FITBIT_CLIENT_ID',
    required=True,
    help='Fitbit OAuth 2.0 client ID.',
)
@click.option(
    '--client-secret',
    envvar='FITBIT_CLIENT_SECRET',
    required=True,
    help='Fitbit OAuth 2.0 client secret.',
)
@click.option(
    '--redirect-url',
    envvar='FITBIT_REDIRECT_URL',
    default='http://localhost:8080/redirect',
    help='OAuth 2.0 redirect URL.',
)
@click.option(
    '--token-file',
    default=DEFAULT_TOKEN_FILE,
    help='File to save authentication tokens.',
)
@click.option(
    '--scope',
    multiple=True,
    default=DEFAULT_SCOPES,
    help='OAuth scopes to request (can specify multiple times).',
)
def login(client_id, client_secret, redirect_url, token_file, scope):
    """Authenticate with Fitbit and save access tokens."""
    click.echo('Starting Fitbit authentication...')

    auth = lib.auth.FitbitAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_url=redirect_url,
    )

    try:
        token_data = auth.authorize(list(scope))
        auth.save_tokens(token_file)
        click.echo(f'✓ Authentication successful! Tokens saved to {token_file}')
        click.echo(f'Access token expires in {token_data.get("expires_in")} seconds')
    except Exception as e:
        click.echo(f'✗ Authentication failed: {str(e)}', err=True)
        sys.exit(1)


@cli.command()
@click.option(
    '--client-id',
    envvar='FITBIT_CLIENT_ID',
    required=True,
    help='Fitbit OAuth 2.0 client ID.',
)
@click.option(
    '--client-secret',
    envvar='FITBIT_CLIENT_SECRET',
    required=True,
    help='Fitbit OAuth 2.0 client secret.',
)
@click.option(
    '--redirect-url',
    envvar='FITBIT_REDIRECT_URL',
    default='http://localhost:8080/redirect',
    help='OAuth 2.0 redirect URL.',
)
@click.option(
    '--token-file',
    default=DEFAULT_TOKEN_FILE,
    help='File containing authentication tokens.',
)
def refresh(client_id, client_secret, redirect_url, token_file):
    """Refresh access token using refresh token."""
    if not Path(token_file).exists():
        click.echo(f'✗ Token file not found: {token_file}', err=True)
        click.echo('Please run "login" command first.', err=True)
        sys.exit(1)

    auth = lib.auth.FitbitAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_url=redirect_url,
    )

    try:
        auth.load_tokens(token_file)
        token_data = auth.refresh_access_token()
        auth.save_tokens(token_file)
        click.echo(f'✓ Token refreshed successfully! Saved to {token_file}')
        click.echo(f'Access token expires in {token_data.get("expires_in")} seconds')
    except Exception as e:
        click.echo(f'✗ Token refresh failed: {str(e)}', err=True)
        sys.exit(1)


@cli.command()
@click.option(
    '--client-id',
    envvar='FITBIT_CLIENT_ID',
    required=True,
    help='Fitbit OAuth 2.0 client ID.',
)
@click.option(
    '--client-secret',
    envvar='FITBIT_CLIENT_SECRET',
    required=True,
    help='Fitbit OAuth 2.0 client secret.',
)
@click.option(
    '--redirect-url',
    envvar='FITBIT_REDIRECT_URL',
    default='http://localhost:8080/redirect',
    help='OAuth 2.0 redirect URL.',
)
@click.option(
    '--token-file',
    default=DEFAULT_TOKEN_FILE,
    help='File containing authentication tokens.',
)
def profile(client_id, client_secret, redirect_url, token_file):
    """Get user profile information."""
    auth = _load_auth(client_id, client_secret, redirect_url, token_file)
    client = lib.client.FitbitClient(auth)

    try:
        profile_data = client.get_user_profile()
        click.echo(json.dumps(profile_data, indent=2))
    except Exception as e:
        click.echo(f'✗ Failed to get profile: {str(e)}', err=True)
        sys.exit(1)


@cli.command()
@click.option(
    '--client-id',
    envvar='FITBIT_CLIENT_ID',
    required=True,
    help='Fitbit OAuth 2.0 client ID.',
)
@click.option(
    '--client-secret',
    envvar='FITBIT_CLIENT_SECRET',
    required=True,
    help='Fitbit OAuth 2.0 client secret.',
)
@click.option(
    '--redirect-url',
    envvar='FITBIT_REDIRECT_URL',
    default='http://localhost:8080/redirect',
    help='OAuth 2.0 redirect URL.',
)
@click.option(
    '--token-file',
    default=DEFAULT_TOKEN_FILE,
    help='File containing authentication tokens.',
)
@click.option(
    '--start-date',
    required=True,
    help='Start date (YYYY-MM-DD format).',
)
@click.option(
    '--end-date',
    required=True,
    help='End date (YYYY-MM-DD format).',
)
@click.option(
    '--output',
    default='heart_rate_data.json',
    help='Output file for heart rate data.',
)
def download_heartrate(
    client_id,
    client_secret,
    redirect_url,
    token_file,
    start_date,
    end_date,
    output,
):
    """Download heart rate data for a date range."""
    auth = _load_auth(client_id, client_secret, redirect_url, token_file)
    client = lib.client.FitbitClient(auth)

    click.echo(f'Downloading heart rate data from {start_date} to {end_date}...')

    try:
        heart_rate_data = client.get_all_heart_rate_data(start_date, end_date)

        with open(output, 'w') as f:
            json.dump(heart_rate_data, f, indent=2)

        click.echo(f'✓ Heart rate data saved to {output}')
    except Exception as e:
        click.echo(f'✗ Failed to download heart rate data: {str(e)}', err=True)
        sys.exit(1)


@cli.command()
@click.option(
    '--client-id',
    envvar='FITBIT_CLIENT_ID',
    required=True,
    help='Fitbit OAuth 2.0 client ID.',
)
@click.option(
    '--client-secret',
    envvar='FITBIT_CLIENT_SECRET',
    required=True,
    help='Fitbit OAuth 2.0 client secret.',
)
@click.option(
    '--redirect-url',
    envvar='FITBIT_REDIRECT_URL',
    default='http://localhost:8080/redirect',
    help='OAuth 2.0 redirect URL.',
)
@click.option(
    '--token-file',
    default=DEFAULT_TOKEN_FILE,
    help='File containing authentication tokens.',
)
@click.option(
    '--date',
    default='today',
    help='Date for intraday data (YYYY-MM-DD or "today").',
)
@click.option(
    '--detail-level',
    default='1min',
    type=click.Choice(['1sec', '1min', '5min', '15min']),
    help='Detail level for intraday data.',
)
@click.option(
    '--output',
    default='heart_rate_intraday.json',
    help='Output file for intraday heart rate data.',
)
def download_intraday(
    client_id,
    client_secret,
    redirect_url,
    token_file,
    date,
    detail_level,
    output,
):
    """Download intraday heart rate data for a specific date."""
    auth = _load_auth(client_id, client_secret, redirect_url, token_file)
    client = lib.client.FitbitClient(auth)

    click.echo(f'Downloading intraday heart rate data for {date} at {detail_level} resolution...')

    try:
        intraday_data = client.get_heart_rate_intraday(date, detail_level)

        with open(output, 'w') as f:
            json.dump(intraday_data, f, indent=2)

        click.echo(f'✓ Intraday heart rate data saved to {output}')
    except Exception as e:
        click.echo(f'✗ Failed to download intraday data: {str(e)}', err=True)
        sys.exit(1)


@cli.command()
@click.option(
    '--client-id',
    envvar='FITBIT_CLIENT_ID',
    required=True,
    help='Fitbit OAuth 2.0 client ID.',
)
@click.option(
    '--client-secret',
    envvar='FITBIT_CLIENT_SECRET',
    required=True,
    help='Fitbit OAuth 2.0 client secret.',
)
@click.option(
    '--redirect-url',
    envvar='FITBIT_REDIRECT_URL',
    default='http://localhost:8080/redirect',
    help='OAuth 2.0 redirect URL.',
)
@click.option(
    '--token-file',
    default=DEFAULT_TOKEN_FILE,
    help='File containing authentication tokens.',
)
def devices(client_id, client_secret, redirect_url, token_file):
    """List user's Fitbit devices."""
    auth = _load_auth(client_id, client_secret, redirect_url, token_file)
    client = lib.client.FitbitClient(auth)

    try:
        devices_data = client.get_devices()
        click.echo(json.dumps(devices_data, indent=2))
    except Exception as e:
        click.echo(f'✗ Failed to get devices: {str(e)}', err=True)
        sys.exit(1)


def _load_auth(
    client_id: str,
    client_secret: str,
    redirect_url: str,
    token_file: str,
) -> lib.auth.FitbitAuth:
    """Load authentication from token file.

    Args:
        client_id: OAuth 2.0 client ID.
        client_secret: OAuth 2.0 client secret.
        redirect_url: OAuth 2.0 redirect URL.
        token_file: Path to token file.

    Returns:
        FitbitAuth instance with loaded tokens.

    Raises:
        SystemExit: If token file not found.
    """
    if not Path(token_file).exists():
        click.echo(f'✗ Token file not found: {token_file}', err=True)
        click.echo('Please run "login" command first.', err=True)
        sys.exit(1)

    auth = lib.auth.FitbitAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_url=redirect_url,
    )
    auth.load_tokens(token_file)
    return auth


if __name__ == '__main__':
    cli()
