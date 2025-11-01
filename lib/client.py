"""Fitbit API client for making authenticated requests.

This module provides a client for interacting with the Fitbit API to retrieve
user data including heart rate/pulse data.

Juan Hernandez-Vargas - 2025
"""

from typing import Any
from typing import Dict
from typing import Optional

import requests

import lib.auth


class FitbitClient:
    """Client for making authenticated requests to Fitbit API."""

    API_BASE_URL = 'https://api.fitbit.com'
    API_VERSION = '1'

    def __init__(self, auth: lib.auth.FitbitAuth):
        """Initialize FitbitClient with authentication.

        Args:
            auth: FitbitAuth instance with valid access token.
        """
        self.auth = auth

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated request to the Fitbit API.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path.
            params: Optional query parameters.
            data: Optional request body data.

        Returns:
            JSON response as dictionary.

        Raises:
            ValueError: If access token is not available.
            requests.exceptions.HTTPError: If request fails.
        """
        if not self.auth.access_token:
            raise ValueError('No access token available. Please authenticate first.')

        headers = {
            'Authorization': f'Bearer {self.auth.access_token}',
            'Accept': 'application/json',
        }

        url = f'{self.API_BASE_URL}/{self.API_VERSION}{endpoint}'

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=data,
        )

        response.raise_for_status()
        return response.json()

    def get_user_profile(self) -> Dict[str, Any]:
        """Get the authenticated user's profile information.

        Returns:
            User profile data.
        """
        return self._make_request('GET', '/user/-/profile.json')

    def get_heart_rate_intraday(
        self,
        date: str,
        detail_level: str = '1min',
    ) -> Dict[str, Any]:
        """Get intraday heart rate data for a specific date.

        Args:
            date: Date in format YYYY-MM-DD or 'today'.
            detail_level: Detail level ('1sec', '1min', '5min', '15min').

        Returns:
            Intraday heart rate data.
        """
        endpoint = f'/user/-/activities/heart/date/{date}/1d/{detail_level}.json'
        return self._make_request('GET', endpoint)

    def get_heart_rate_time_series(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        period: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get heart rate time series data.

        Args:
            start_date: Start date in format YYYY-MM-DD or 'today'.
            end_date: End date in format YYYY-MM-DD (mutually exclusive with period).
            period: Time period ('1d', '7d', '30d', '1w', '1m') (mutually exclusive with end_date).

        Returns:
            Heart rate time series data.

        Raises:
            ValueError: If both end_date and period are provided or neither is provided.
        """
        if (end_date is None and period is None) or (end_date is not None and period is not None):
            raise ValueError('Must provide either end_date or period, but not both')

        if end_date:
            endpoint = f'/user/-/activities/heart/date/{start_date}/{end_date}.json'
        else:
            endpoint = f'/user/-/activities/heart/date/{start_date}/{period}.json'

        return self._make_request('GET', endpoint)

    def get_heart_rate_today(self) -> Dict[str, Any]:
        """Get today's heart rate data.

        Returns:
            Today's heart rate data.
        """
        return self.get_heart_rate_time_series('today', period='1d')

    def get_all_heart_rate_data(
        self,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """Get all heart rate data between two dates.

        Args:
            start_date: Start date in format YYYY-MM-DD.
            end_date: End date in format YYYY-MM-DD.

        Returns:
            Heart rate data for the date range.
        """
        return self.get_heart_rate_time_series(start_date, end_date=end_date)

    def get_devices(self) -> Dict[str, Any]:
        """Get list of user's devices.

        Returns:
            List of devices.
        """
        return self._make_request('GET', '/user/-/devices.json')

    def get_activity_summary(self, date: str) -> Dict[str, Any]:
        """Get activity summary for a specific date.

        Args:
            date: Date in format YYYY-MM-DD or 'today'.

        Returns:
            Activity summary data.
        """
        endpoint = f'/user/-/activities/date/{date}.json'
        return self._make_request('GET', endpoint)
