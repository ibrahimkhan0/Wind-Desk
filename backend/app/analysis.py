"""Pure analysis functions (no web code) so they are easy to test.

Conventions
-----------
* error = forecast - actual (MW).  error > 0  => wind was OVER-forecast, i.e. the buyer
  would have under-bought thermal/other power and be short in real time.
* The "decision forecast" for a delivery period is the latest forecast that was
  published at or before the day-ahead gate (cutoff_hour on the previous day).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from . import config as C

HALF_HOUR_H = 0.5


class DataNotReady(RuntimeError):
    pass


# ----------------------------------------------------------------- loading
@lru_cache(maxsize=1)
def load_raw() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not C.ACTUALS_FILE.exists() or not C.FORECASTS_FILE.exists():
        raise DataNotReady(
            "Data snapshot missing. Run `python -m scripts.fetch_data` in backend/ first."
        )
    act = pd.read_csv(C.ACTUALS_FILE, parse_dates=["start_time"])
    fc = pd.read_csv(C.FORECASTS_FILE, parse_dates=["start_time", "publish_time"])
    for df, cols in ((act, ["start_time"]), (fc, ["start_time", "publish_time"])):
        for c in cols:
            df[c] = pd.to_datetime(df[c], utc=True)
    return act, fc


# ----------------------------------------------------------- core selection
def pick_decision_forecast(fc: pd.DataFrame, cutoff_hour: int) -> pd.DataFrame:
    """For each target half-hour keep the latest forecast published by the day-ahead gate."""
    day = fc["start_time"].dt.floor("D")
    cutoff = day - pd.Timedelta(days=1) + pd.Timedelta(hours=cutoff_hour)
    eligible = fc[fc["publish_time"] <= cutoff]
    best = eligible.sort_values("publish_time").groupby("start_time", as_index=False).last()
    return best


def pick_fixed_horizon(fc: pd.DataFrame, horizon_h: float) -> pd.DataFrame:
    """Latest forecast published at least `horizon_h` hours before each target period."""
    ok = fc[fc["publish_time"] <= fc["start_time"] - pd.Timedelta(hours=horizon_h)]
    return ok.sort_values("publish_time").groupby("start_time", as_index=False).last()


def _join_actuals(fc_pick: pd.DataFrame, act: pd.DataFrame) -> pd.DataFrame:
    df = fc_pick.merge(act, on="start_time", how="inner")
    df["error"] = df["forecast"] - df["actual"]
    df["abs_error"] = df["error"].abs()
    df["horizon_h"] = (df["start_time"] - df["publish_time"]) / pd.Timedelta(hours=1)
    df["day"] = df["start_time"].dt.floor("D")
    return df.sort_values("start_time").reset_index(drop=True)


@lru_cache(maxsize=16)
def decision_table(cutoff_hour: int) -> pd.DataFrame:
    act, fc = load_raw()
    return _join_actuals(pick_decision_forecast(fc, cutoff_hour), act)


def _slice(df: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    if start:
        df = df[df["day"] >= pd.Timestamp(start, tz="UTC")]
    if end:
        df = df[df["day"] <= pd.Timestamp(end, tz="UTC")]
    return df


# ------------------------------------------------------------------ metrics
def compute_metrics(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"n": 0}
    e = df["error"]
    over = e.clip(lower=0)
    under = (-e).clip(lower=0)
    days = max(df["day"].nunique(), 1)
    return {
        "n": int(len(df)),
        "days": int(days),
        "mean_actual_mw": float(df["actual"].mean()),
        "mean_forecast_mw": float(df["forecast"].mean()),
        "mae_mw": float(e.abs().mean()),
        "rmse_mw": float(np.sqrt((e**2).mean())),
        "bias_mw": float(e.mean()),
        "wmape_pct": float(100 * e.abs().sum() / df["actual"].sum()) if df["actual"].sum() else None,
        "p90_abs_error_mw": float(e.abs().quantile(0.9)),
        "share_over_forecast_pct": float(100 * (e > 0).mean()),
        "p90_over_forecast_mw": float(max(e.quantile(0.9), 0)),
        "p90_under_forecast_mw": float(max((-e).quantile(0.9), 0)),
        "over_forecast_mwh_per_day": float(over.sum() * HALF_HOUR_H / days),
        "under_forecast_mwh_per_day": float(under.sum() * HALF_HOUR_H / days),
        "mean_horizon_h": float(df["horizon_h"].mean()),
        "correlation": float(df["forecast"].corr(df["actual"])) if len(df) > 2 else None,
    }


def error_band(df: pd.DataFrame) -> tuple[float, float]:
    """10th / 90th percentile of the error, used as an empirical planning band."""
    return float(df["error"].quantile(0.10)), float(df["error"].quantile(0.90))


# ------------------------------------------------------------- API payloads
def _iso(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(x) -> float | None:
    return None if pd.isna(x) else round(float(x), 1)


def meta(cutoff_hour: int) -> dict:
    act, fc = load_raw()
    tbl = decision_table(cutoff_hour)
    return {
        "first_delivery_day": _iso(tbl["day"].min())[:10],
        "last_delivery_day": _iso(tbl["day"].max())[:10],
        "delivery_days": sorted({_iso(d)[:10] for d in tbl["day"].unique()}),
        "default_cutoff_hour": C.DEFAULT_CUTOFF_HOUR,
        "cutoff_hours": C.ALLOWED_CUTOFF_HOURS,
        "n_actual_periods": int(len(act)),
        "n_forecast_rows": int(len(fc)),
        "first_publish": _iso(fc["publish_time"].min()),
        "last_publish": _iso(fc["publish_time"].max()),
    }


def day_view(day: str, cutoff_hour: int) -> dict:
    tbl = decision_table(cutoff_hour)
    d0 = pd.Timestamp(day, tz="UTC")
    sel = tbl[tbl["day"] == d0]
    if sel.empty:
        raise KeyError(day)

    q10, q90 = error_band(tbl)  # whole-period band => honest "typical error" for planning
    series = []
    for r in sel.itertuples():
        series.append(
            {
                "t": _iso(r.start_time),
                "actual": _num(r.actual),
                "forecast": _num(r.forecast),
                "lo": _num(max(r.forecast - q90, 0)),
                "hi": _num(r.forecast - q10),
                "publish_time": _iso(r.publish_time),
                "horizon_h": _num(r.horizon_h),
            }
        )

    # How did the forecast for this day move as new runs came out?
    _, fc = load_raw()
    day_fc = fc[fc["start_time"].dt.floor("D") == d0]
    runs = day_fc.groupby("publish_time").agg(n=("forecast", "size"), mean=("forecast", "mean"))
    runs = runs[runs["n"] == 48]
    cutoff = d0 - pd.Timedelta(days=1) + pd.Timedelta(hours=cutoff_hour)
    revisions = [
        {
            "publish_time": _iso(ts),
            "mean_mw": _num(row["mean"]),
            "before_cutoff": bool(ts <= cutoff),
        }
        for ts, row in runs.iterrows()
    ]

    m = compute_metrics(sel)
    return {
        "day": day,
        "cutoff_time": _iso(cutoff),
        "forecast_issued_min": _iso(sel["publish_time"].min()),
        "forecast_issued_max": _iso(sel["publish_time"].max()),
        "series": series,
        "summary": {
            "forecast_energy_mwh": _num(sel["forecast"].sum() * HALF_HOUR_H),
            "actual_energy_mwh": _num(sel["actual"].sum() * HALF_HOUR_H),
            "forecast_mean_mw": _num(sel["forecast"].mean()),
            "forecast_peak_mw": _num(sel["forecast"].max()),
            "forecast_min_mw": _num(sel["forecast"].min()),
            "day_mae_mw": _num(m["mae_mw"]),
            "day_bias_mw": _num(m["bias_mw"]),
        },
        "band": {"error_p10_mw": _num(q10), "error_p90_mw": _num(q90)},
        "revisions": revisions,
    }


def accuracy(cutoff_hour: int, start: str | None, end: str | None) -> dict:
    df = _slice(decision_table(cutoff_hour), start, end)
    if df.empty:
        raise KeyError("no data in range")

    daily = df.groupby("day").apply(
        lambda g: pd.Series(
            {
                "mae": g["abs_error"].mean(),
                "bias": g["error"].mean(),
                "mean_actual": g["actual"].mean(),
                "mean_forecast": g["forecast"].mean(),
            }
        ),
        include_groups=False,
    )
    by_hour = df.assign(hour=df["start_time"].dt.hour).groupby("hour").agg(
        mae=("abs_error", "mean"), bias=("error", "mean")
    )

    lim = float(np.ceil(df["error"].abs().max() / 500.0) * 500.0) or 500.0
    counts, edges = np.histogram(df["error"], bins=np.linspace(-lim, lim, 25))
    hist = [
        {"from": float(edges[i]), "to": float(edges[i + 1]), "count": int(counts[i])}
        for i in range(len(counts))
    ]

    # error size vs. how windy it was
    bins = pd.qcut(df["actual"], 4, duplicates="drop")
    by_level = df.groupby(bins, observed=True).agg(
        mae=("abs_error", "mean"), bias=("error", "mean"), mean_actual=("actual", "mean")
    )

    q10, q90 = error_band(df)
    return {
        "range": {"start": _iso(df["day"].min())[:10], "end": _iso(df["day"].max())[:10]},
        "metrics": compute_metrics(df),
        "band": {"error_p10_mw": _num(q10), "error_p90_mw": _num(q90)},
        "daily": [
            {"day": _iso(i)[:10], **{k: _num(v) for k, v in r.items()}} for i, r in daily.iterrows()
        ],
        "by_hour": [
            {"hour": int(i), "mae": _num(r["mae"]), "bias": _num(r["bias"])}
            for i, r in by_hour.iterrows()
        ],
        "histogram": hist,
        "by_wind_level": [
            {"label": f"{int(r['mean_actual']):,} MW avg", "mae": _num(r["mae"]), "bias": _num(r["bias"])}
            for _, r in by_level.iterrows()
        ],
    }


def horizon_curve(start: str | None, end: str | None, max_h: int = C.MAX_HORIZON_H) -> dict:
    act, fc = load_raw()
    rows = []
    for h in range(1, max_h + 1):
        df = _slice(_join_actuals(pick_fixed_horizon(fc, h), act), start, end)
        if df.empty:
            continue
        rows.append(
            {
                "horizon_h": h,
                "mae": _num(df["abs_error"].mean()),
                "rmse": _num(np.sqrt((df["error"] ** 2).mean())),
                "bias": _num(df["error"].mean()),
                "n": int(len(df)),
            }
        )
    return {"curve": rows}
