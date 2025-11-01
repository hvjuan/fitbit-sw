# Fitbit API Client

Python CLI tool for downloading and storing Fitbit health data (heart rate, sleep, activity).

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export FITBIT_CLIENT_ID=your_client_id
export FITBIT_CLIENT_SECRET=your_client_secret
```

## CLI Commands

### Authentication

**Login** - Authenticate with Fitbit and save access tokens
```bash
python -m cli.fitbit_cli login
```

Options:
- `--client-id TEXT` - Fitbit OAuth 2.0 client ID [required]
- `--client-secret TEXT` - Fitbit OAuth 2.0 client secret [required]
- `--redirect-url TEXT` - OAuth 2.0 redirect URL (default: http://localhost:8080/redirect)
- `--token-file TEXT` - File to save authentication tokens (default: .fitbit_tokens.json)
- `--scope TEXT` - OAuth scopes to request (can specify multiple times, default: activity, heartrate, profile, sleep)

**Refresh** - Refresh access token using refresh token
```bash
python -m cli.fitbit_cli refresh
```

### User Profile

**Profile** - Get user profile information
```bash
python -m cli.fitbit_cli profile
```

**Devices** - List user's Fitbit devices
```bash
python -m cli.fitbit_cli devices
```

### Heart Rate Data

**Download Heart Rate** - Download heart rate data for a date range
```bash
python -m cli.fitbit_cli download-heartrate --start-date 2025-10-01 --end-date 2025-10-31 --output heart_rate.json
```

Options:
- `--start-date TEXT` - Start date (YYYY-MM-DD format) [required]
- `--end-date TEXT` - End date (YYYY-MM-DD format) [required]
- `--output TEXT` - Output file for heart rate data (default: heart_rate_data.json)

**Download Intraday Heart Rate** - Download minute-by-minute heart rate data for a specific date
```bash
python -m cli.fitbit_cli download-intraday --date today --detail-level 1min --output hr_intraday.json
```

Options:
- `--date TEXT` - Date for intraday data (YYYY-MM-DD or "today", default: today)
- `--detail-level [1sec|1min|5min|15min]` - Detail level for intraday data (default: 1min)
- `--output TEXT` - Output file (default: heart_rate_intraday.json)

### Sleep Data

**Download Sleep** - Download sleep data for a specific date
```bash
python -m cli.fitbit_cli download-sleep --date today --output sleep.json
```

Options:
- `--date TEXT` - Date for sleep data (YYYY-MM-DD or "today", default: today)
- `--output TEXT` - Output file for sleep data (default: sleep_data.json)

**Download Sleep Range** - Download sleep data for a date range
```bash
python -m cli.fitbit_cli download-sleep-range --start-date 2025-10-01 --end-date 2025-10-31 --output sleep_range.json
```

Options:
- `--start-date TEXT` - Start date (YYYY-MM-DD format) [required]
- `--end-date TEXT` - End date (YYYY-MM-DD format) [required]
- `--output TEXT` - Output file for sleep data (default: sleep_range_data.json)

## Examples

### Full Workflow

1. Authenticate:
```bash
export FITBIT_CLIENT_ID=23TGD4
export FITBIT_CLIENT_SECRET=your_secret_here
python -m cli.fitbit_cli login
```

2. Get your profile:
```bash
python -m cli.fitbit_cli profile
```

3. Download last month's heart rate:
```bash
python -m cli.fitbit_cli download-heartrate --start-date 2025-10-01 --end-date 2025-10-31
```

4. Download today's minute-by-minute heart rate:
```bash
python -m cli.fitbit_cli download-intraday --date today
```

5. Download last night's sleep:
```bash
python -m cli.fitbit_cli download-sleep --date today
```

## Development

Built with:
- Python 3.12
- requests (HTTP client)
- click (CLI framework)

Data includes:
- Heart rate (daily summaries, intraday minute-by-minute)
- Sleep (stages, duration, efficiency)
- Activity (steps, calories, distance)

## License

Juan Hernandez-Vargas - 2025
