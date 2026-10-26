"""Thin Elexon BMRS client. Used only by scripts/fetch_data.py."""
import time

import httpx
import pandas as pd

from .config import ELEXON_BASE

CHUNK_DAYS = 2  # keep each request small; the stream endpoints cap the window size


def _get_json(client: httpx.Client, url: str, params: dict, retries: int = 4) -> list[dict]:
    for attempt in range(retries):
        try:
            r = client.get(url, params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else data.get("data", [])
        except (httpx.HTTPError, ValueError):
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    return []


def _windows(start: pd.Timestamp, end: pd.Timestamp, days: int):
    cur = start
    while cur < end:
        nxt = min(cur + pd.Timedelta(days=days), end)
        yield cur, nxt
        cur = nxt


def fetch_actuals(start: pd.Timestamp, end_excl: pd.Timestamp) -> pd.DataFrame:
    """FUELHH, fuelType=WIND -> columns [start_time, actual] (MW, 30-min)."""
    rows: list[dict] = []
    with httpx.Client() as client:
        for a, b in _windows(start, end_excl, CHUNK_DAYS):
            rows += _get_json(
                client,
                f"{ELEXON_BASE}/FUELHH/stream",
                {
                    "settlementDateFrom": a.strftime("%Y-%m-%d"),
                    "settlementDateTo": (b - pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                    "fuelType": "WIND",
                },
            )
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("FUELHH returned no rows")
    df = df[df["fuelType"] == "WIND"].copy()
    df["start_time"] = pd.to_datetime(df["startTime"], utc=True)
    if "publishTime" in df:  # keep the latest publication for each period
        df["publish_time"] = pd.to_datetime(df["publishTime"], utc=True)
        df = df.sort_values("publish_time")
    df = df.drop_duplicates("start_time", keep="last")
    df = df.rename(columns={"generation": "actual"})[["start_time", "actual"]]
    return df.sort_values("start_time").reset_index(drop=True)


def fetch_forecasts(start: pd.Timestamp, end_excl: pd.Timestamp) -> pd.DataFrame:
    """WINDFOR -> columns [start_time, publish_time, forecast] (MW)."""
    rows: list[dict] = []
    with httpx.Client() as client:
        for a, b in _windows(start, end_excl, CHUNK_DAYS):
            rows += _get_json(
                client,
                f"{ELEXON_BASE}/WINDFOR/stream",
                {
                    "publishDateTimeFrom": a.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "publishDateTimeTo": b.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("WINDFOR returned no rows")
    df["start_time"] = pd.to_datetime(df["startTime"], utc=True)
    df["publish_time"] = pd.to_datetime(df["publishTime"], utc=True)
    df = df.rename(columns={"generation": "forecast"})[["start_time", "publish_time", "forecast"]]
    return df.drop_duplicates(["start_time", "publish_time"]).reset_index(drop=True)
