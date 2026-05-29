import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

from database import get_conn, init_db

log = logging.getLogger(__name__)

BASE = "https://www.set.or.th/api/set"
TZ_BKK = timezone(timedelta(hours=7))


def _now_iso() -> str:
    return datetime.now(TZ_BKK).isoformat()


class SETClient:
    def __init__(self, delay: float = 0.3):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.set.or.th/en/home",
        })
        self.session.get("https://www.set.or.th/en/home", timeout=15)

    def _get(self, path: str) -> Optional[dict | list]:
        url = f"{BASE}/{path}"
        try:
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            log.warning(f"HTTP {e.response.status_code} for {url}")
            return None
        except Exception as e:
            log.warning(f"Request failed for {url}: {e}")
            return None
        finally:
            time.sleep(self.delay)

    # ------------------------------------------------------------------ #
    #  Fetch methods                                                       #
    # ------------------------------------------------------------------ #

    def fetch_stock_list(self) -> list[dict]:
        data = self._get("stock/list?lang=en")
        return data.get("securitySymbols", []) if data else []

    def fetch_index_list(self) -> list[dict]:
        data = self._get("index/list?lang=en")
        return data if isinstance(data, list) else []

    def fetch_stock_info(self, symbol: str) -> Optional[dict]:
        return self._get(f"stock/{symbol}/info?lang=en")

    def fetch_stock_historical(self, symbol: str) -> list[dict]:
        data = self._get(f"stock/{symbol}/historical-trading?lang=en")
        return data if isinstance(data, list) else []

    def fetch_index_info(self, symbol: str) -> Optional[dict]:
        return self._get(f"index/{symbol}/info?lang=en")


# ------------------------------------------------------------------ #
#  Save methods                                                        #
# ------------------------------------------------------------------ #

def save_stocks(stocks: list[dict]):
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO stocks (symbol, name_en, name_th, market, security_type, updated_at)
               VALUES (:symbol, :nameEN, :nameTH, :market, :securityType, :updated_at)
               ON CONFLICT(symbol) DO UPDATE SET
                 name_en=excluded.name_en, name_th=excluded.name_th,
                 market=excluded.market, security_type=excluded.security_type,
                 updated_at=excluded.updated_at""",
            [{**s, "updated_at": _now_iso()} for s in stocks],
        )
    log.info(f"Saved {len(stocks)} stocks")


def save_indices(indices: list[dict]):
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO indices (symbol, name_en, name_th, market, level, parent_index)
               VALUES (:symbol, :nameEN, :nameTH, :market, :level, :parentIndex)
               ON CONFLICT(symbol) DO UPDATE SET
                 name_en=excluded.name_en, market=excluded.market, level=excluded.level""",
            indices,
        )
    log.info(f"Saved {len(indices)} indices")


def save_stock_snapshot(info: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO stock_snapshot
                 (symbol, last, prior, open, high, low, average, floor, ceiling,
                  change, percent_change, total_volume, total_value,
                  market_status, market_datetime, industry, sector,
                  name_en, name_th, refreshed_at)
               VALUES
                 (:symbol, :last, :prior, :open, :high, :low, :average, :floor, :ceiling,
                  :change, :percentChange, :totalVolume, :totalValue,
                  :marketStatus, :marketDateTime, :industryName, :sectorName,
                  :nameEN, :nameTH, :refreshed_at)
               ON CONFLICT(symbol) DO UPDATE SET
                 last=excluded.last, prior=excluded.prior, open=excluded.open,
                 high=excluded.high, low=excluded.low, average=excluded.average,
                 change=excluded.change, percent_change=excluded.percent_change,
                 total_volume=excluded.total_volume, total_value=excluded.total_value,
                 market_status=excluded.market_status, market_datetime=excluded.market_datetime,
                 refreshed_at=excluded.refreshed_at""",
            {**info, "refreshed_at": _now_iso()},
        )


def save_index_snapshot(info: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO index_snapshot
                 (symbol, name_en, prior, open, high, low, last,
                  change, percent_change, volume, value,
                  market_status, market_datetime, refreshed_at)
               VALUES
                 (:symbol, :nameEN, :prior, :open, :high, :low, :last,
                  :change, :percentChange, :volume, :value,
                  :marketStatus, :marketDateTime, :refreshed_at)
               ON CONFLICT(symbol) DO UPDATE SET
                 last=excluded.last, change=excluded.change,
                 percent_change=excluded.percent_change,
                 volume=excluded.volume, value=excluded.value,
                 market_status=excluded.market_status, market_datetime=excluded.market_datetime,
                 refreshed_at=excluded.refreshed_at""",
            {**info, "refreshed_at": _now_iso()},
        )


def save_historical(symbol: str, rows: list[dict]):
    records = []
    for r in rows:
        records.append({
            "symbol": symbol,
            "date": r["date"][:10],
            "prior": r.get("prior"),
            "open": r.get("open"),
            "high": r.get("high"),
            "low": r.get("low"),
            "average": r.get("average"),
            "close": r.get("close"),
            "change": r.get("change"),
            "percent_change": r.get("percentChange"),
            "total_volume": r.get("totalVolume"),
            "total_value": r.get("totalValue"),
            "pe": r.get("pe"),
            "pbv": r.get("pbv"),
            "book_value": r.get("bookValuePerShare"),
            "div_yield": r.get("dividendYield"),
            "market_cap": r.get("marketCap"),
            "listed_shares": r.get("listedShare"),
            "par": r.get("par"),
        })
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO stock_prices
                 (symbol, date, prior, open, high, low, average, close,
                  change, percent_change, total_volume, total_value,
                  pe, pbv, book_value, div_yield, market_cap, listed_shares, par)
               VALUES
                 (:symbol, :date, :prior, :open, :high, :low, :average, :close,
                  :change, :percent_change, :total_volume, :total_value,
                  :pe, :pbv, :book_value, :div_yield, :market_cap, :listed_shares, :par)
               ON CONFLICT(symbol, date) DO NOTHING""",
            records,
        )
    return len(records)


# ------------------------------------------------------------------ #
#  High-level tasks                                                    #
# ------------------------------------------------------------------ #

def sync_stock_list(client: SETClient):
    print("Fetching stock list...")
    stocks = client.fetch_stock_list()
    if stocks:
        save_stocks(stocks)
        print(f"  Saved {len(stocks)} stocks")
    return stocks


def sync_index_list(client: SETClient):
    print("Fetching index list...")
    indices = client.fetch_index_list()
    if indices:
        save_indices(indices)
        print(f"  Saved {len(indices)} indices")
    return indices


def sync_snapshots(client: SETClient, symbols: list[str], label: str = "stocks"):
    print(f"Fetching snapshots for {len(symbols)} {label}...")
    ok = 0
    for i, sym in enumerate(symbols, 1):
        info = client.fetch_stock_info(sym)
        if info:
            save_stock_snapshot(info)
            ok += 1
        if i % 50 == 0:
            print(f"  {i}/{len(symbols)} done")
    print(f"  Snapshots saved: {ok}/{len(symbols)}")


def sync_index_snapshots(client: SETClient, symbols: list[str]):
    print(f"Fetching index snapshots for {len(symbols)} indices...")
    ok = 0
    for sym in symbols:
        info = client.fetch_index_info(sym)
        if info:
            save_index_snapshot(info)
            ok += 1
    print(f"  Index snapshots saved: {ok}/{len(symbols)}")


def sync_historical(client: SETClient, symbols: list[str]):
    print(f"Fetching historical data for {len(symbols)} stocks...")
    total = 0
    for i, sym in enumerate(symbols, 1):
        rows = client.fetch_stock_historical(sym)
        if rows:
            n = save_historical(sym, rows)
            total += n
        if i % 20 == 0:
            print(f"  {i}/{len(symbols)} done  ({total} rows so far)")
    print(f"  Historical rows saved: {total}")
