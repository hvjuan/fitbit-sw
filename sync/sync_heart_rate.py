"""Sync heart rate data from Fitbit API to MariaDB.

This module handles syncing both daily summaries and intraday minute-by-minute
heart rate data from Fitbit to the database.

Juan Hernandez-Vargas - 2025
"""

import os
import sys
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from zoneinfo import ZoneInfo

import mysql.connector

import lib.auth
import lib.client


class HeartRateSync:
    """Sync heart rate data from Fitbit API to MariaDB."""

    def __init__(self, db_config: Dict[str, str], fitbit_client: lib.client.FitbitClient):
        """Initialize HeartRateSync.

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

    def sync_heart_rate_date(self, date: str) -> tuple[int, int]:
        """Sync heart rate data for a specific date.

        Args:
            date: Date in YYYY-MM-DD format or 'today'.

        Returns:
            Tuple of (daily records synced, intraday records synced).
        """
        print(f'Fetching heart rate data for {date}...')
        hr_data = self.fitbit_client.get_heart_rate_intraday(date, detail_level='1min')

        cursor = self.conn.cursor()
        daily_synced = 0
        intraday_synced = 0

        try:
            # Sync daily summary
            if 'activities-heart' in hr_data and hr_data['activities-heart']:
                daily_data = hr_data['activities-heart'][0]
                actual_date = daily_data.get('dateTime', date)  # Get actual date from API
                if self._insert_daily_heart_rate(cursor, actual_date, daily_data):
                    daily_synced = 1
                    print(f'  ✓ Synced daily heart rate summary')

            # Sync intraday minute-by-minute data
            if 'activities-heart-intraday' in hr_data:
                intraday_data = hr_data['activities-heart-intraday'].get('dataset', [])
                # Use the actual date from daily data
                actual_date = hr_data['activities-heart'][0].get('dateTime', date) if 'activities-heart' in hr_data else date
                intraday_synced = self._insert_intraday_heart_rate(cursor, actual_date, intraday_data)
                print(f'  ✓ Synced {intraday_synced} intraday heart rate records')

            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f'  ✗ Error syncing heart rate for {date}: {str(e)}')
            raise
        finally:
            cursor.close()

        return daily_synced, intraday_synced

    def _insert_daily_heart_rate(self, cursor, date: str, daily_data: Dict[str, Any]) -> bool:
        """Insert daily heart rate summary into the database.

        Args:
            cursor: Database cursor.
            date: Date string.
            daily_data: Daily heart rate data from Fitbit API.

        Returns:
            True if inserted, False if skipped.
        """
        value = daily_data.get('value', {})
        
        # Extract resting heart rate
        resting_hr = value.get('restingHeartRate')
        
        # Extract heart rate zones
        zones = value.get('heartRateZones', [])
        fat_burn = next((z for z in zones if z['name'] == 'Fat Burn'), {})
        cardio = next((z for z in zones if z['name'] == 'Cardio'), {})
        peak = next((z for z in zones if z['name'] == 'Peak'), {})

        sql = """
            INSERT INTO heart_rate_daily (
                date, resting_heart_rate, calories_out,
                fat_burn_minutes, fat_burn_calories,
                cardio_minutes, cardio_calories,
                peak_minutes, peak_calories
            ) VALUES (
                %(date)s, %(resting_hr)s, %(calories_out)s,
                %(fat_burn_minutes)s, %(fat_burn_calories)s,
                %(cardio_minutes)s, %(cardio_calories)s,
                %(peak_minutes)s, %(peak_calories)s
            )
            ON DUPLICATE KEY UPDATE
                resting_heart_rate = VALUES(resting_heart_rate),
                calories_out = VALUES(calories_out),
                fat_burn_minutes = VALUES(fat_burn_minutes),
                fat_burn_calories = VALUES(fat_burn_calories),
                cardio_minutes = VALUES(cardio_minutes),
                cardio_calories = VALUES(cardio_calories),
                peak_minutes = VALUES(peak_minutes),
                peak_calories = VALUES(peak_calories)
        """

        params = {
            'date': date,
            'resting_hr': resting_hr,
            'calories_out': value.get('caloriesOut'),
            'fat_burn_minutes': fat_burn.get('minutes'),
            'fat_burn_calories': fat_burn.get('caloriesOut'),
            'cardio_minutes': cardio.get('minutes'),
            'cardio_calories': cardio.get('caloriesOut'),
            'peak_minutes': peak.get('minutes'),
            'peak_calories': peak.get('caloriesOut'),
        }

        cursor.execute(sql, params)
        return True

    def _insert_intraday_heart_rate(
        self,
        cursor,
        date: str,
        intraday_data: List[Dict[str, Any]],
    ) -> int:
        """Insert intraday minute-by-minute heart rate data.

        Args:
            cursor: Database cursor.
            date: Date string.
            intraday_data: List of intraday heart rate records.

        Returns:
            Number of records inserted.
        """
        if not intraday_data:
            return 0

        sql = """
            INSERT INTO heart_rate_intraday (datetime, heart_rate)
            VALUES (%(datetime)s, %(heart_rate)s)
            ON DUPLICATE KEY UPDATE heart_rate = VALUES(heart_rate)
        """

        inserted = 0
        for record in intraday_data:
            time_str = record['time']
            heart_rate = record['value']
            
            # Combine date and time
            datetime_str = f"{date} {time_str}"
            
            params = {
                'datetime': datetime_str,
                'heart_rate': heart_rate,
            }

            try:
                cursor.execute(sql, params)
                inserted += 1
            except mysql.connector.IntegrityError:
                # Skip duplicates
                pass

        return inserted


def main():
    """Main entry point for heart rate sync."""
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

    # Sync heart rate data
    sync = HeartRateSync(db_config, client)

    try:
        sync.connect()

        # Get date from command line or default to today
        date = sys.argv[1] if len(sys.argv) > 1 else 'today'

        daily, intraday = sync.sync_heart_rate_date(date)
        print(f'\n✓ Sync complete!')
        print(f'  Daily records: {daily}')
        print(f'  Intraday records: {intraday}')

    except Exception as e:
        print(f'\n✗ Sync failed: {str(e)}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        sync.close()


if __name__ == '__main__':
    main()
