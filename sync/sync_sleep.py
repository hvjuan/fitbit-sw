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
                    start_time = datetime.fromisoformat(sleep_session['startTime'].replace('.000', ''))
                    if 'levels' in sleep_session and 'data' in sleep_session['levels']:
                        self._insert_sleep_minutes(cursor, sleep_session['logId'], sleep_session['levels']['data'], start_time)
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
                efficiency, info_code, log_type, sleep_type, sleep_score, is_main_sleep,
                awakenings_count, time_in_bed_minutes, minutes_asleep, minutes_awake,
                minutes_to_fall_asleep, minutes_after_wakeup
            ) VALUES (
                %(log_id)s, %(date_of_sleep)s, %(start_time)s, %(end_time)s, %(duration_ms)s,
                %(efficiency)s, %(info_code)s, %(log_type)s, %(sleep_type)s, %(sleep_score)s,
                %(is_main_sleep)s, %(awakenings_count)s, %(time_in_bed_minutes)s,
                %(minutes_asleep)s, %(minutes_awake)s, %(minutes_to_fall_asleep)s,
                %(minutes_after_wakeup)s
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
            'info_code': session.get('infoCode', 0),
            'log_type': session.get('logType'),
            'sleep_type': session.get('type'),
            'sleep_score': sleep_score,
            'is_main_sleep': session.get('isMainSleep', True),
            'awakenings_count': session.get('awakeningsCount'),
            'time_in_bed_minutes': session.get('timeInBed'),
            'minutes_asleep': session.get('minutesAsleep'),
            'minutes_awake': session.get('minutesAwake'),
            'minutes_to_fall_asleep': session.get('minutesToFallAsleep'),
            'minutes_after_wakeup': session.get('minutesAfterWakeup'),
        }

        cursor.execute(sql, params)

        # Insert minute-by-minute sleep data - only stages format is supported now
        if 'levels' in session and 'data' in session['levels']:
            self._insert_sleep_minutes(cursor, session['logId'], session['levels']['data'], start_time)

    def _calculate_sleep_score(self, session: Dict[str, Any]) -> int:
        """Calculate a sleep quality score (0-100) based on Fitbit's algorithm.
        
        Fitbit's sleep score has 3 components:
        - Duration (50 points): Time asleep compared to goal
        - Composition (25 points): Deep & REM sleep percentages
        - Restoration (25 points): Sleep efficiency and interruptions

        Args:
            session: Sleep session data from Fitbit API.

        Returns:
            Sleep score from 0-100.
        """
        minutes_asleep = session.get('minutesAsleep', 0)
        efficiency = session.get('efficiency', 0)

        # ==== DURATION SCORE (50 points max) ====
        # Fitbit scores based on comparison to goal (typically 7-9 hours)
        # 6.77 hours → 41/50 points, 4.43 hours → ~27/50 points
        duration_hours = minutes_asleep / 60
        if 7 <= duration_hours <= 9:
            duration_score = 50
        elif duration_hours < 7:
            # Score drops off with sleep under 7 hours
            # Using observed pattern: roughly 50 * (hours/7)^1.15
            duration_score = 50 * ((duration_hours / 7) ** 1.15)
        else:
            # Penalty for over 9 hours
            duration_score = max(0, 50 - ((duration_hours - 9) * 8))

        # ==== COMPOSITION SCORE (25 points max) ====
        # Based on Deep & REM sleep percentages
        if 'levels' in session and 'summary' in session['levels']:
            summary = session['levels']['summary']
            deep_min = summary.get('deep', {}).get('minutes', 0)
            rem_min = summary.get('rem', {}).get('minutes', 0)
            
            deep_pct = (deep_min / minutes_asleep * 100) if minutes_asleep > 0 else 0
            rem_pct = (rem_min / minutes_asleep * 100) if minutes_asleep > 0 else 0
            
            # Deep sleep: optimal 13-23%
            if 13 <= deep_pct <= 23:
                deep_score = 12.5
            elif deep_pct < 13:
                deep_score = 12.5 * (deep_pct / 13)
            else:
                deep_score = max(0, 12.5 - (deep_pct - 23) * 1.5)
            
            # REM sleep: optimal 20-25%
            if 20 <= rem_pct <= 25:
                rem_score = 12.5
            elif rem_pct < 20:
                rem_score = 12.5 * (rem_pct / 20)
            else:
                rem_score = max(0, 12.5 - (rem_pct - 25) * 1.5)
            
            composition_score = deep_score + rem_score
        else:
            # Fallback if no detailed stages available
            composition_score = 20

        # ==== RESTORATION SCORE (25 points max) ====
        # Based on sleep efficiency and wake time
        if 'levels' in session and 'summary' in session['levels']:
            wake_min = session['levels']['summary'].get('wake', {}).get('minutes', 0)
            wake_pct = (wake_min / minutes_asleep * 100) if minutes_asleep > 0 else 0
            
            # Efficiency component (15 points)
            efficiency_score = (efficiency / 100) * 15
            
            # Wake penalty component (10 points)
            wake_score = max(0, 10 - (wake_pct * 2))
            
            restoration_score = efficiency_score + wake_score
        else:
            # Fallback: use efficiency only
            restoration_score = (efficiency / 100) * 25

        # Total score
        sleep_score = duration_score + composition_score + restoration_score

        return int(round(sleep_score))

    def _insert_sleep_minutes(self, cursor, log_id: int, minutes_data: List[Dict[str, Any]], start_time: datetime):
        """Insert minute-by-minute sleep stage data (new format with levels.data).

        Args:
            cursor: Database cursor.
            log_id: Sleep session log ID.
            minutes_data: List of sleep stage periods with seconds duration.
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
            seconds_duration = entry.get('seconds', 0)
            
            # Parse the start time of this period
            # Fitbit API returns times in user's local timezone
            period_start = datetime.fromisoformat(entry['dateTime'].replace('.000', ''))
            
            # Generate a record for each minute in this period
            minutes_in_period = seconds_duration // 60
            for minute_offset in range(minutes_in_period):
                from datetime import timedelta
                minute_time = period_start + timedelta(minutes=minute_offset)
                
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
