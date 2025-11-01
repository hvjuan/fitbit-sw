-- Fitbit Database Schema
-- Juan Hernandez-Vargas - 2025

-- ============================================================================
-- SLEEP TABLES
-- ============================================================================

-- Main sleep sessions table (one row per sleep session)
CREATE TABLE IF NOT EXISTS sleep_sessions (
    log_id BIGINT PRIMARY KEY,
    date_of_sleep DATE NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    duration_ms BIGINT NOT NULL COMMENT 'Duration in milliseconds',
    duration_minutes INT GENERATED ALWAYS AS (duration_ms / 60000) STORED,
    efficiency INT COMMENT 'Sleep efficiency percentage (0-100)',
    is_main_sleep BOOLEAN DEFAULT TRUE COMMENT 'Main sleep vs nap',
    awake_count INT COMMENT 'Number of times awake',
    awake_duration_ms INT COMMENT 'Total awake time in ms',
    awakenings_count INT COMMENT 'Number of awakenings',
    restless_count INT COMMENT 'Number of restless periods',
    restless_duration_ms INT COMMENT 'Total restless time in ms',
    time_in_bed_minutes INT COMMENT 'Total time in bed',
    minutes_asleep INT COMMENT 'Actual sleep time',
    minutes_awake INT COMMENT 'Time awake',
    minutes_to_fall_asleep INT COMMENT 'Time to fall asleep',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_date (date_of_sleep),
    INDEX idx_start_time (start_time),
    INDEX idx_main_sleep (is_main_sleep)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Sleep sessions with daily summary data';

-- Minute-by-minute sleep stages
CREATE TABLE IF NOT EXISTS sleep_minutes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    log_id BIGINT NOT NULL,
    minute_time DATETIME NOT NULL,
    sleep_stage TINYINT NOT NULL COMMENT '1=asleep, 2=restless, 3=awake',
    FOREIGN KEY (log_id) REFERENCES sleep_sessions(log_id) ON DELETE CASCADE,
    UNIQUE KEY idx_log_minute (log_id, minute_time),
    INDEX idx_stage (sleep_stage)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Minute-by-minute sleep stage data';

-- ============================================================================
-- HEART RATE TABLES
-- ============================================================================

-- Daily heart rate summaries
CREATE TABLE IF NOT EXISTS heart_rate_daily (
    date DATE PRIMARY KEY,
    resting_heart_rate INT COMMENT 'Resting heart rate for the day',
    calories_out DECIMAL(10,2) COMMENT 'Calories burned from heart rate',
    -- Heart rate zones
    fat_burn_minutes INT COMMENT 'Minutes in fat burn zone',
    fat_burn_calories DECIMAL(10,2) COMMENT 'Calories in fat burn zone',
    cardio_minutes INT COMMENT 'Minutes in cardio zone',
    cardio_calories DECIMAL(10,2) COMMENT 'Calories in cardio zone',
    peak_minutes INT COMMENT 'Minutes in peak zone',
    peak_calories DECIMAL(10,2) COMMENT 'Calories in peak zone',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_resting_hr (resting_heart_rate),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Daily heart rate summaries and zones';

-- Intraday minute-by-minute heart rate
CREATE TABLE IF NOT EXISTS heart_rate_intraday (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    datetime DATETIME NOT NULL,
    heart_rate INT NOT NULL COMMENT 'Heart rate in BPM',
    date DATE GENERATED ALWAYS AS (DATE(datetime)) STORED,
    UNIQUE KEY idx_datetime (datetime),
    INDEX idx_date (date),
    INDEX idx_hr (heart_rate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Minute-by-minute heart rate data';

-- ============================================================================
-- ACTIVITY TABLES
-- ============================================================================

-- Daily activity summaries
CREATE TABLE IF NOT EXISTS activity_daily (
    date DATE PRIMARY KEY,
    steps INT DEFAULT 0 COMMENT 'Total steps',
    distance_km DECIMAL(10,2) COMMENT 'Distance in kilometers',
    floors INT DEFAULT 0 COMMENT 'Floors climbed',
    elevation_meters DECIMAL(10,2) COMMENT 'Elevation in meters',
    calories_burned INT COMMENT 'Total calories burned',
    active_minutes INT COMMENT 'Active minutes',
    sedentary_minutes INT COMMENT 'Sedentary minutes',
    lightly_active_minutes INT COMMENT 'Lightly active minutes',
    fairly_active_minutes INT COMMENT 'Fairly active minutes',
    very_active_minutes INT COMMENT 'Very active minutes',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_steps (steps),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Daily activity summaries';

-- ============================================================================
-- DEVICE INFORMATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS devices (
    device_id VARCHAR(50) PRIMARY KEY,
    device_version VARCHAR(100),
    type VARCHAR(50) COMMENT 'Device type (e.g., TRACKER)',
    battery_level INT COMMENT 'Battery level 0-100',
    battery_status VARCHAR(20) COMMENT 'Battery status (e.g., High, Medium, Low)',
    last_sync_time DATETIME COMMENT 'Last sync timestamp',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_last_sync (last_sync_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Fitbit device information';

-- ============================================================================
-- SYNC LOG
-- ============================================================================

CREATE TABLE IF NOT EXISTS sync_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sync_date DATE NOT NULL,
    sync_type VARCHAR(50) NOT NULL COMMENT 'Type of data synced (sleep, heart_rate, activity)',
    records_synced INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'success' COMMENT 'success, failed, partial',
    error_message TEXT,
    sync_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_completed_at TIMESTAMP NULL,
    INDEX idx_sync_date (sync_date),
    INDEX idx_sync_type (sync_type),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Log of data sync operations';
