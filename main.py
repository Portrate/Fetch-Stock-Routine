"""
SET Market Data Scraper
Usage:
  python main.py                          # Full sync for all listed_companies symbols
  python main.py --list-only              # Only update stock & index lists
  python main.py --snapshot-only          # Only update current-price snapshots
  python main.py --historical-only        # Only fetch historical price data
  python main.py --symbol AOT PTT         # Target specific symbols
  python main.py --source-db PATH         # Use custom source DB (default: C:/demo/resource/listed_companies.db)
  python main.py --query                  # Show quick DB summary
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

# Check local Windows path first, then fall back to repo-relative path
_LOCAL_DB = Path(r"C:\demo\resource\listed_companies.db")
_REPO_DB = Path(__file__).parent / "listed_companies.db"
LISTED_COMPANIES_DB = _LOCAL_DB if _LOCAL_DB.exists() else _REPO_DB


def load_symbols_from_source(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT symbol FROM masterset ORDER BY symbol").fetchall()
    conn.close()
    return [r[0] for r in rows]

sys.path.insert(0, str(Path(__file__).parent))

from database import init_db, get_conn, DB_PATH
from scraper import (
    SETClient,
    sync_stock_list,
    sync_index_list,
    sync_snapshots,
    sync_index_snapshots,
    sync_historical,
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)


def query_summary():
    with get_conn() as conn:
        def count(table):
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        stocks = count("stocks")
        snap = count("stock_snapshot")
        prices = count("stock_prices")
        idx = count("indices")
        idx_snap = count("index_snapshot")

        print(f"\n{'='*45}")
        print(f"  Database: {DB_PATH}")
        print(f"{'='*45}")
        print(f"  stocks            : {stocks:>8,}")
        print(f"  stock_snapshot    : {snap:>8,}")
        print(f"  stock_prices      : {prices:>8,}")
        print(f"  indices           : {idx:>8,}")
        print(f"  index_snapshot    : {idx_snap:>8,}")

        if prices > 0:
            row = conn.execute(
                "SELECT MIN(date), MAX(date) FROM stock_prices"
            ).fetchone()
            print(f"\n  Price history range: {row[0]} to {row[1]}")

        print(f"{'='*45}")

        if snap > 0:
            print("\nTop 10 stocks by volume today:")
            rows = conn.execute(
                """SELECT symbol, last, change, percent_change, total_volume
                   FROM stock_snapshot ORDER BY total_volume DESC LIMIT 10"""
            ).fetchall()
            print(f"  {'Symbol':<8} {'Last':>8} {'Chg':>8} {'%Chg':>8} {'Volume':>15}")
            print(f"  {'-'*55}")
            for r in rows:
                print(f"  {r[0]:<8} {r[1]:>8.2f} {r[2]:>8.2f} {r[3]:>7.2f}% {int(r[4] or 0):>15,}")
        print()


def main():
    parser = argparse.ArgumentParser(description="SET.or.th Market Data Scraper")
    parser.add_argument("--list-only", action="store_true", help="Sync stock/index lists only")
    parser.add_argument("--snapshot-only", action="store_true", help="Sync current snapshots only")
    parser.add_argument("--historical-only", action="store_true", help="Sync historical prices only")
    parser.add_argument("--symbol", nargs="+", metavar="SYM", help="Specific symbols to process")
    parser.add_argument("--source-db", type=Path, default=LISTED_COMPANIES_DB,
                        metavar="PATH", help="Source DB with listed companies")
    parser.add_argument("--query", action="store_true", help="Show database summary and exit")
    parser.add_argument("--delay", type=float, default=0.3, metavar="SEC",
                        help="Delay between API calls in seconds (default 0.3)")
    args = parser.parse_args()

    init_db()

    if args.query:
        query_summary()
        return

    client = SETClient(delay=args.delay)

    # Determine which symbols to use
    if args.symbol:
        symbols = [s.upper() for s in args.symbol]
        print(f"Targeting {len(symbols)} symbol(s): {', '.join(symbols)}")
    elif args.source_db.exists():
        symbols = load_symbols_from_source(args.source_db)
        print(f"Loaded {len(symbols)} symbols from {args.source_db.name}")
    else:
        symbols = None  # fall back to full stock list from API
        print(f"Source DB not found at {args.source_db}, will use full API stock list")

    do_list = not (args.snapshot_only or args.historical_only)
    do_snap = not (args.list_only or args.historical_only)
    do_hist = not (args.list_only or args.snapshot_only)

    if do_list or symbols is None:
        stocks = sync_stock_list(client)
        indices = sync_index_list(client)
        all_index_symbols = [i["symbol"] for i in indices]
        if symbols is None:
            symbols = [s["symbol"] for s in stocks]
        # Enrich stocks table with industry/sector from source DB
        if args.source_db.exists():
            src = sqlite3.connect(args.source_db)
            rows = src.execute("SELECT symbol, industry_group, sector FROM masterset").fetchall()
            src.close()
            with get_conn() as conn:
                conn.executemany(
                    "UPDATE stocks SET industry=?, sector=? WHERE symbol=?",
                    [(r[1], r[2], r[0]) for r in rows],
                )
            print(f"  Enriched industry/sector for {len(rows)} stocks")
    else:
        with get_conn() as conn:
            all_index_symbols = [r[0] for r in conn.execute("SELECT symbol FROM indices").fetchall()]

    target_stocks = symbols
    target_indices = all_index_symbols if not args.symbol else []

    if do_snap:
        sync_snapshots(client, target_stocks)
        sync_index_snapshots(client, target_indices)

    if do_hist:
        sync_historical(client, target_stocks)

    query_summary()


if __name__ == "__main__":
    main()
