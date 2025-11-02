"""Sync a full month of heart rate data from Fitbit API to MariaDB.

This script syncs heart rate data for all days in a specified month.

Juan Hernandez-Vargas - 2025
"""

import os
import sys
from datetime import datetime, timedelta

import lib.auth
import lib.client
from sync_heart_rate import HeartRateSync


def generate_date_range(year: int, month: int):
    """Generate all dates for a given month.

    Args:
        year: Year (e.g., 2025)
        month: Month (1-12)

    Yields:
        Date strings in YYYY-MM-DD format
    """
    start_date = datetime(year, month, 1)

    # Get last day of month
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(days=1)

    current_date = start_date
    while current_date <= end_date:
        yield current_date.strftime('%Y-%m-%d')
        current_date += timedelta(days=1)


def main():
    """Main entry point for month sync."""
    # Load environment variables
    client_id = os.getenv('FITBIT_CLIENT_ID')
    client_secret = os.getenv('FITBIT_CLIENT_SECRET')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_user = os.getenv('DB_USER', 'fitbit_user')
    db_pass = os.getenv('DB_PASS', 'fitbit_pass')
    db_name = os.getenv('DB_NAME', 'fitbit')

    if not client_id or not client_secret:
        print('✗ Error: FITBIT_CLIENT_ID and FITBIT_CLIENT_SECRET environment variables required')
        sys.exit(1)

    # Get year and month from command line
    if len(sys.argv) < 3:
        print('Usage: python sync_heart_rate_month.py <year> <month>')
        print('Example: python sync_heart_rate_month.py 2025 10')
        sys.exit(1)

    try:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
        if month < 1 or month > 12:
            raise ValueError('Month must be between 1 and 12')
    except ValueError as e:
        print(f'✗ Error: Invalid year or month - {e}')
        sys.exit(1)

    # Initialize Fitbit auth
    auth = lib.auth.FitbitAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_url='http://localhost:8080/redirect',
    )

    # Load tokens
    token_file = '.fitbit_tokens.json'
    if not os.path.exists(token_file):
        print(f'✗ Error: Token file {token_file} not found. Run login command first.')
        sys.exit(1)

    auth.load_tokens(token_file)
    client = lib.client.FitbitClient(auth)

    # Database config
    db_config = {
        'host': db_host,
        'user': db_user,
        'password': db_pass,
        'database': db_name,
    }

    # Sync heart rate data for the entire month
    sync = HeartRateSync(db_config, client)

    try:
        sync.connect()

        total_daily = 0
        total_intraday = 0
        dates = list(generate_date_range(year, month))

        print(f'\n💓 Syncing heart rate data for {year}-{month:02d} ({len(dates)} days)\n')

        for i, date in enumerate(dates, 1):
            print(f'[{i}/{len(dates)}] {date}')
            try:
                daily, intraday = sync.sync_heart_rate_date(date)
                total_daily += daily
                total_intraday += intraday
            except Exception as e:
                print(f'  ⚠ Warning: Failed to sync {date}: {str(e)}')
                continue

        print(f'\n✓ Month sync complete!')
        print(f'  Total daily records: {total_daily}')
        print(f'  Total intraday records: {total_intraday}')
        print(f'  Total days processed: {len(dates)}')

    except Exception as e:
        print(f'\n✗ Sync failed: {str(e)}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        sync.close()


if __name__ == '__main__':
    main()
