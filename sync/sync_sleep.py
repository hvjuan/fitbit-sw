"""Sync sleep data from Fitbit API to MariaDB.

This module handles syncing sleep sessions from Fitbit to the database.

Juan Hernandez-Vargas - 2025
"""

import os
import sys
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List

import mysql.connector

import lib.auth
import lib.client


class SleepSync:
    """Sync sleep data from Fitbit API to MariaDB."""

    def __init__(self, db_config: Dict[str, str], fitbit_client: lib.client.FitbitClient):
        """Initialize SleepSync.

        Args:
            db_config: Database configuration dict with host, user, password, database.
            fitbit_client: Authenticated FitbitClient instance.
        """
        self.db_config = db_config
        self.fitbit_client = fitbit_client
        self.conn = None

    def connect(self):
        """Connect to the database."""
        self.conn = mysql.connector.connect(**self.db_config)
        print('✓ Connected to database')

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            print('✓ Database connection closed')

    def sync_sleep_date(self, date: str) -> int:
        """Sync sleep data for a specific date.

        Args:
            date: Date in YYYY-MM-DD format or 'today'.

        Returns:
            Number of sleep sessions synced.
        """
        print(f'Fetching sleep data for {date}...')
        sleep_data = self.fitbit_client.get_sleep_log(date)

        if not sleep_data.get('sleep'):
            print(f'  No sleep data found for {date}')
            return 0

        cursor = self.conn.cursor()
        sessions_synced = 0

        for sleep_session in sleep_data['sleep']:
            try:
                self._insert_sleep_session(cursor, sleep_session)
                sessions_synced += 1
                print(f'  ✓ Synced sleep session {sleep_session["logId"]}')
            except mysql.connector.IntegrityError:
                print(f'  ⊙ Sleep session {sleep_session["logId"]} already exists, skipping')
            except Exception as e:
                print(f'  ✗ Error syncing session {sleep_session["logId"]}: {str(e)}')

        self.conn.commit()
        cursor.close()
        return sessions_synced

    def _insert_sleep_session(self, cursor, session: Dict[str, Any]):
        """Insert a sleep session into the database.

        Args:
            cursor: Database cursor.
            session: Sleep session data from Fitbit API.
        """
        sql = """
            INSERT INTO sleep_sessions (
                log_id, date_of_sleep, start_time, end_time, duration_ms,
                efficiency, is_main_sleep, awake_count, awake_duration_ms,
                awakenings_count, restless_count, restless_duration_ms,
                time_in_bed_minutes, minutes_asleep, minutes_awake,
                minutes_to_fall_asleep
            ) VALUES (
                %(log_id)s, %(date_of_sleep)s, %(start_time)s, %(end_time)s, %(duration_ms)s,
                %(efficiency)s, %(is_main_sleep)s, %(awake_count)s, %(awake_duration_ms)s,
                %(awakenings_count)s, %(restless_count)s, %(restless_duration_ms)s,
                %(time_in_bed_minutes)s, %(minutes_asleep)s, %(minutes_awake)s,
                %(minutes_to_fall_asleep)s
            )
        """

        # Parse datetime strings
        start_time = datetime.fromisoformat(session['startTime'].replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(session['endTime'].replace('Z', '+00:00'))

        params = {
            'log_id': session['logId'],
            'date_of_sleep': session['dateOfSleep'],
            'start_time': start_time,
            'end_time': end_time,
            'duration_ms': session['duration'],
            'efficiency': session.get('efficiency'),
            'is_main_sleep': session.get('isMainSleep', True),
            'awake_count': session.get('awakeCount'),
            'awake_duration_ms': session.get('awakeDuration'),
            'awakenings_count': session.get('awakeningsCount'),
            'restless_count': session.get('restlessCount'),
            'restless_duration_ms': session.get('restlessDuration'),
            'time_in_bed_minutes': session.get('timeInBed'),
            'minutes_asleep': session.get('minutesAsleep'),
            'minutes_awake': session.get('minutesAwake'),
            'minutes_to_fall_asleep': session.get('minutesToFallAsleep'),
        }

        cursor.execute(sql, params)


def main():
    """Main entry point for sleep sync."""
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

    # Sync sleep data
    sync = SleepSync(db_config, client)

    try:
        sync.connect()

        # Get date from command line or default to today
        date = sys.argv[1] if len(sys.argv) > 1 else 'today'

        synced = sync.sync_sleep_date(date)
        print(f'\n✓ Total sessions synced: {synced}')

    except Exception as e:
        print(f'\n✗ Sync failed: {str(e)}')
        sys.exit(1)
    finally:
        sync.close()


if __name__ == '__main__':
    main()
