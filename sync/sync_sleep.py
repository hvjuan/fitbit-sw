"""Sync sleep data from Fitbit API to MariaDB.

This module handles syncing sleep sessions from Fitbit to the database.

Juan Hernandez-Vargas - 2025
"""

import os
import sys
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Dict
from typing import List
from zoneinfo import ZoneInfo

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
                print(f'  ⊙ Sleep session {sleep_session["logId"]} already exists')
                # Still try to insert minute data if it doesn't exist
                try:
                    start_time = datetime.fromisoformat(sleep_session['startTime'].replace('Z', '+00:00'))
                    if 'levels' in sleep_session and 'data' in sleep_session['levels']:
                        self._insert_sleep_minutes(cursor, sleep_session['logId'], sleep_session['levels']['data'], start_time)
                        print(f'    ✓ Added minute-by-minute data')
                    elif 'minuteData' in sleep_session:
                        self._insert_sleep_minutes_classic(cursor, sleep_session['logId'], sleep_session['minuteData'], sleep_session['dateOfSleep'])
                        print(f'    ✓ Added minute-by-minute data')
                except Exception as e:
                    print(f'    ⊙ Minute data already exists or error: {str(e)}')
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
                efficiency, sleep_score, is_main_sleep, awake_count, awake_duration_ms,
                awakenings_count, restless_count, restless_duration_ms,
                time_in_bed_minutes, minutes_asleep, minutes_awake,
                minutes_to_fall_asleep
            ) VALUES (
                %(log_id)s, %(date_of_sleep)s, %(start_time)s, %(end_time)s, %(duration_ms)s,
                %(efficiency)s, %(sleep_score)s, %(is_main_sleep)s, %(awake_count)s, %(awake_duration_ms)s,
                %(awakenings_count)s, %(restless_count)s, %(restless_duration_ms)s,
                %(time_in_bed_minutes)s, %(minutes_asleep)s, %(minutes_awake)s,
                %(minutes_to_fall_asleep)s
            )
        """

        # Parse datetime strings
        # Fitbit API returns times in user's local timezone (no Z suffix)
        start_time = datetime.fromisoformat(session['startTime'].replace('.000', ''))
        end_time = datetime.fromisoformat(session['endTime'].replace('.000', ''))
        
        # Calculate sleep score
        sleep_score = self._calculate_sleep_score(session)

        params = {
            'log_id': session['logId'],
            'date_of_sleep': session['dateOfSleep'],
            'start_time': start_time,
            'end_time': end_time,
            'duration_ms': session['duration'],
            'efficiency': session.get('efficiency'),
            'sleep_score': sleep_score,
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

        # Insert minute-by-minute sleep data if available
        if 'levels' in session and 'data' in session['levels']:
            self._insert_sleep_minutes(cursor, session['logId'], session['levels']['data'], start_time)
        elif 'minuteData' in session:
            self._insert_sleep_minutes_classic(cursor, session['logId'], session['minuteData'], session['dateOfSleep'])

    def _calculate_sleep_score(self, session: Dict[str, Any]) -> int:
        """Calculate a sleep quality score (0-100) based on duration, efficiency, and restoration.

        Args:
            session: Sleep session data from Fitbit API.

        Returns:
            Sleep score from 0-100.
        """
        minutes_asleep = session.get('minutesAsleep', 0)
        efficiency = session.get('efficiency', 0)
        awake_count = session.get('awakeCount', 0)
        restless_count = session.get('restlessCount', 0)
        minutes_to_fall_asleep = session.get('minutesToFallAsleep', 0)

        # Duration Score (0-100): optimal is 7-9 hours
        duration_hours = minutes_asleep / 60
        if 7 <= duration_hours <= 9:
            duration_score = 100
        elif duration_hours < 7:
            # Penalty for too little sleep: lose 20 points per hour under 7
            duration_score = max(0, 100 - ((7 - duration_hours) * 20))
        else:
            # Penalty for too much sleep: lose 20 points per hour over 9
            duration_score = max(0, 100 - ((duration_hours - 9) * 20))

        # Quality Score: Sleep efficiency percentage
        quality_score = efficiency or 0

        # Restoration Score: based on interruptions
        interruption_penalty = min(50, (awake_count * 5) + (restless_count * 2))
        restoration_score = max(0, 100 - interruption_penalty - (minutes_to_fall_asleep * 2))

        # Weighted average: Duration 30%, Quality 40%, Restoration 30%
        sleep_score = (duration_score * 0.30) + (quality_score * 0.40) + (restoration_score * 0.30)

        return int(round(sleep_score))

    def _insert_sleep_minutes(self, cursor, log_id: int, minutes_data: List[Dict[str, Any]], start_time: datetime):
        """Insert minute-by-minute sleep stage data (new format with levels.data).

        Args:
            cursor: Database cursor.
            log_id: Sleep session log ID.
            minutes_data: List of minute-by-minute sleep stage data.
            start_time: Sleep session start time.
        """
        # Sleep stage mapping (Fitbit API values to our schema)
        stage_map = {
            'wake': 0,
            'light': 1,
            'deep': 2,
            'rem': 3,
        }

        sql = """
            INSERT INTO sleep_minutes (log_id, minute_time, sleep_stage)
            VALUES (%(log_id)s, %(minute_time)s, %(sleep_stage)s)
        """

        for entry in minutes_data:
            stage = entry.get('level', 'wake').lower()
            sleep_stage = stage_map.get(stage, 0)
            # Fitbit API returns times in user's local timezone
            minute_time = datetime.fromisoformat(entry['dateTime'].replace('.000', '').replace('Z', '+00:00'))
            
            # If it has timezone info (Z suffix), convert to local
            if minute_time.tzinfo:
                ny_tz = ZoneInfo('America/New_York')
                minute_time = minute_time.astimezone(ny_tz).replace(tzinfo=None)

            params = {
                'log_id': log_id,
                'minute_time': minute_time,
                'sleep_stage': sleep_stage,
            }

            try:
                cursor.execute(sql, params)
            except mysql.connector.IntegrityError:
                # Skip duplicates
                pass

    def _insert_sleep_minutes_classic(self, cursor, log_id: int, minute_data: List[Dict[str, Any]], date_of_sleep: str):
        """Insert minute-by-minute sleep stage data (classic format with minuteData).

        Args:
            cursor: Database cursor.
            log_id: Sleep session log ID.
            minute_data: List of minute-by-minute sleep stage data (classic format).
            date_of_sleep: Date of sleep in YYYY-MM-DD format.
        """
        # Sleep stage mapping for classic format
        # "1" = asleep (light), "2" = restless (awake), "3" = awake
        stage_map = {
            '1': 1,  # asleep -> light
            '2': 0,  # restless -> awake
            '3': 0,  # awake -> awake
        }

        sql = """
            INSERT INTO sleep_minutes (log_id, minute_time, sleep_stage)
            VALUES (%(log_id)s, %(minute_time)s, %(sleep_stage)s)
        """

        for entry in minute_data:
            # Parse time (format is "HH:MM:SS")
            time_str = entry['dateTime']
            minute_time = datetime.strptime(f"{date_of_sleep} {time_str}", "%Y-%m-%d %H:%M:%S")
            
            # Assume the date_of_sleep is already in the user's local timezone
            # No conversion needed for classic format as times are relative to the date
            
            # Get sleep stage
            value = entry.get('value', '3')
            sleep_stage = stage_map.get(value, 0)

            params = {
                'log_id': log_id,
                'minute_time': minute_time,
                'sleep_stage': sleep_stage,
            }

            try:
                cursor.execute(sql, params)
            except mysql.connector.IntegrityError:
                # Skip duplicates
                pass


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
