"""SQLite Database connection and schema initialization for StudyLife Orchestrator."""

import sqlite3
from pathlib import Path
from typing import Generator
from contextlib import contextmanager

DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_FILE = DB_DIR / "studylife.db"


def get_db_path() -> Path:
    """Ensure data directory exists and return database path."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    return DB_FILE


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager yielding a SQLite connection with Row factory and WAL mode."""
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize SQLite database tables if they do not exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. User Profile table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL DEFAULT 'student',
                study_program TEXT NOT NULL DEFAULT 'Informatik / UZH',
                semester INTEGER NOT NULL DEFAULT 3,
                wake_time TEXT NOT NULL DEFAULT '07:00',
                sleep_time TEXT NOT NULL DEFAULT '23:00',
                max_daily_study_minutes INTEGER NOT NULL DEFAULT 180,
                pomodoro_minutes INTEGER NOT NULL DEFAULT 25,
                calendar_ics_url TEXT,
                ankiweb_email TEXT,
                last_ankiweb_sync TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Migration: ensure calendar_ics_url exists in existing DBs
        try:
            cursor.execute("ALTER TABLE user_profile ADD COLUMN calendar_ics_url TEXT;")
        except sqlite3.OperationalError:
            pass  # Column already exists

        for col, ctype in [
            ("olat_webdav_user", "TEXT"),
            ("olat_webdav_password", "TEXT"),
            ("olat_course_url", "TEXT"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE user_profile ADD COLUMN {col} {ctype};")
            except sqlite3.OperationalError:
                pass

        # 2. Saved Calendar Events (Lectures, Labs, Seminars)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_date TEXT NOT NULL,
                title TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                location TEXT,
                description TEXT,
                module_name TEXT,
                lecture_attended INTEGER DEFAULT NULL, -- 1=Yes, 0=No, NULL=Upcoming/Not Decided
                consumption_mode TEXT DEFAULT NULL, -- 'live', 'stream_1_25', 'stream_1_5', 'stream_2_0', 'slides_only', 'skipped'
                speed_factor REAL DEFAULT 1.0,
                time_saved_minutes INTEGER DEFAULT 0,
                recommendation TEXT DEFAULT NULL, -- 'attend', 'stream', 'skip'
                recommendation_reason TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Migration columns for saved_events
        for col_def in [
            ("consumption_mode", "TEXT DEFAULT NULL"),
            ("speed_factor", "REAL DEFAULT 1.0"),
            ("time_saved_minutes", "INTEGER DEFAULT 0"),
            ("recommendation", "TEXT DEFAULT NULL"),
            ("recommendation_reason", "TEXT DEFAULT NULL"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE saved_events ADD COLUMN {col_def[0]} {col_def[1]};")
            except sqlite3.OperationalError:
                pass

        # 3. Saved Manual Activities (Gym, Meals, Commute, Breaks)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_date TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Anki Decks and Topics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anki_decks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_name TEXT NOT NULL,
                total_cards INTEGER NOT NULL DEFAULT 0,
                total_estimated_minutes INTEGER NOT NULL DEFAULT 0,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anki_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id INTEGER,
                name TEXT NOT NULL,
                cluster_name TEXT NOT NULL,
                card_count INTEGER NOT NULL DEFAULT 0,
                estimated_minutes INTEGER NOT NULL DEFAULT 0,
                difficulty_score REAL NOT NULL DEFAULT 3.0,
                matched_lecture TEXT,
                relevance_score REAL NOT NULL DEFAULT 0.0,
                relevance_reason TEXT,
                urgency TEXT NOT NULL DEFAULT 'normal',
                FOREIGN KEY (deck_id) REFERENCES anki_decks(id) ON DELETE CASCADE
            );
        """)

        # 5. Study Session Logs (Historical reviews to compute learning speed & retention)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_session_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date TEXT NOT NULL,
                topic_name TEXT NOT NULL,
                module_name TEXT,
                duration_minutes INTEGER NOT NULL,
                cards_reviewed INTEGER NOT NULL,
                seconds_per_card REAL NOT NULL,
                retention_rate REAL NOT NULL, -- 0.0 to 1.0 (e.g. 0.88 = 88% correct)
                lecture_attended INTEGER NOT NULL, -- 1=Yes (attended lecture), 0=No (pure self-study)
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 6. AnkiWeb Synced Statistics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ankiweb_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_email TEXT NOT NULL,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_cards_reviewed INTEGER NOT NULL DEFAULT 0,
                overall_retention_rate REAL NOT NULL DEFAULT 0.85,
                avg_seconds_per_card REAL NOT NULL DEFAULT 22.5,
                mature_cards_count INTEGER NOT NULL DEFAULT 0,
                young_cards_count INTEGER NOT NULL DEFAULT 0,
                streak_days INTEGER NOT NULL DEFAULT 12,
                deck_name TEXT DEFAULT NULL,
                deck_scope TEXT DEFAULT 'curriculum',
                total_cards INTEGER DEFAULT 9319,
                first_reviewed_at TEXT DEFAULT NULL,
                last_reviewed_at TEXT DEFAULT NULL
            );
        """)

        # Migration columns for ankiweb_stats
        for col_def in [
            ("deck_name", "TEXT DEFAULT NULL"),
            ("deck_scope", "TEXT DEFAULT 'curriculum'"),
            ("total_cards", "INTEGER DEFAULT 9319"),
            ("first_reviewed_at", "TEXT DEFAULT NULL"),
            ("last_reviewed_at", "TEXT DEFAULT NULL"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE ankiweb_stats ADD COLUMN {col_def[0]} {col_def[1]};")
            except sqlite3.OperationalError:
                pass

        # 7. Exams (Prüfungstermine UZH)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'student',
                subject_name TEXT NOT NULL,
                exam_date TEXT NOT NULL,
                target_cards INTEGER NOT NULL DEFAULT 9633,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 8. Study Schedule Configuration (Freie Tage, Joker-Tage, Puffer)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_schedule_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL DEFAULT 'student',
                free_weekdays TEXT NOT NULL DEFAULT '[6]', -- 6 = Sonntag frei (0=Mo, 6=So)
                joker_dates TEXT NOT NULL DEFAULT '[]',     -- Spezifische freie Tage ['2026-10-15', ...]
                revision_buffer_days INTEGER NOT NULL DEFAULT 14, -- 14 Tage vor Prüfung reines Wiederholen
                total_curriculum_cards INTEGER NOT NULL DEFAULT 9633,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 9. Daily Progress Logs (Ist-Erfassung)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_progress_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'student',
                log_date TEXT NOT NULL,
                cards_completed INTEGER NOT NULL DEFAULT 0,
                minutes_spent INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'manual', -- 'manual' oder 'anki_sync'
                notes TEXT,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, log_date) ON CONFLICT REPLACE
            );
        """)

        # 10. Rhythm Block Actions (Delete, Postpone to tomorrow)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rhythm_block_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'student',
                source_date TEXT NOT NULL,
                target_date TEXT,
                block_id TEXT NOT NULL,
                action TEXT NOT NULL, -- 'delete' or 'postpone'
                block_payload TEXT,    -- JSON dump of the block properties
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 11. Curriculum Schedule Overrides (Day Swaps & Custom Ordering)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS curriculum_schedule_overrides (
                user_id TEXT NOT NULL DEFAULT 'student',
                target_date TEXT NOT NULL,
                assigned_day_number INTEGER NOT NULL,
                PRIMARY KEY (user_id, target_date)
            );
        """)

        # Insert default student profile if not present
        cursor.execute("SELECT id FROM user_profile WHERE username = 'student'")
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO user_profile (
                    username, study_program, semester, wake_time, sleep_time,
                    max_daily_study_minutes, pomodoro_minutes, ankiweb_email
                ) VALUES (
                    'student', 'Medizin / UZH', 3, '07:00', '23:00',
                    180, 25, 'constantingrandidier@gmail.com'
                );
            """)

        # Seed default exams (19.01.2027 and 21.01.2027) if table is empty
        cursor.execute("SELECT count(*) FROM exams WHERE user_id = 'student'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO exams (user_id, subject_name, exam_date, target_cards, notes)
                VALUES 
                ('student', 'Medizin 2. SJ – Prüfung 1', '2027-01-19', 9633, 'Erste Modulprüfung 2. Studienjahr UZH'),
                ('student', 'Medizin 2. SJ – Prüfung 2', '2027-01-21', 9633, 'Zweite Modulprüfung 2. Studienjahr UZH');
            """)

        # Seed default schedule config if not present
        cursor.execute("SELECT id FROM study_schedule_config WHERE user_id = 'student'")
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO study_schedule_config (
                    user_id, free_weekdays, joker_dates, revision_buffer_days, total_curriculum_cards
                ) VALUES (
                    'student', '[6]', '[]', 14, 9633
                );
            """)

        conn.commit()


# Automatically initialize schema when module is loaded
init_db()
