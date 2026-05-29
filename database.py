import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "set_market.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS stocks (
                symbol          TEXT PRIMARY KEY,
                name_en         TEXT,
                name_th         TEXT,
                market          TEXT,
                security_type   TEXT,
                industry        TEXT,
                sector          TEXT,
                updated_at      TEXT
            );

            CREATE TABLE IF NOT EXISTS indices (
                symbol          TEXT PRIMARY KEY,
                name_en         TEXT,
                name_th         TEXT,
                market          TEXT,
                level           TEXT,
                parent_index    TEXT
            );

            CREATE TABLE IF NOT EXISTS stock_prices (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol          TEXT NOT NULL,
                date            TEXT NOT NULL,
                prior           REAL,
                open            REAL,
                high            REAL,
                low             REAL,
                average         REAL,
                close           REAL,
                change          REAL,
                percent_change  REAL,
                total_volume    REAL,
                total_value     REAL,
                pe              REAL,
                pbv             REAL,
                book_value      REAL,
                div_yield       REAL,
                market_cap      REAL,
                listed_shares   REAL,
                par             REAL,
                UNIQUE(symbol, date)
            );

            CREATE TABLE IF NOT EXISTS stock_snapshot (
                symbol          TEXT PRIMARY KEY,
                last            REAL,
                prior           REAL,
                open            REAL,
                high            REAL,
                low             REAL,
                average         REAL,
                floor           REAL,
                ceiling         REAL,
                change          REAL,
                percent_change  REAL,
                total_volume    REAL,
                total_value     REAL,
                market_status   TEXT,
                market_datetime TEXT,
                industry        TEXT,
                sector          TEXT,
                name_en         TEXT,
                name_th         TEXT,
                refreshed_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS index_snapshot (
                symbol          TEXT PRIMARY KEY,
                name_en         TEXT,
                prior           REAL,
                open            REAL,
                high            REAL,
                low             REAL,
                last            REAL,
                change          REAL,
                percent_change  REAL,
                volume          REAL,
                value           REAL,
                market_status   TEXT,
                market_datetime TEXT,
                refreshed_at    TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_prices_symbol ON stock_prices(symbol);
            CREATE INDEX IF NOT EXISTS idx_prices_date   ON stock_prices(date);
        """)
    print(f"Database ready: {DB_PATH}")