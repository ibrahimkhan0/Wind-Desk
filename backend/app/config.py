"""Central configuration. Every assumption about the problem lives here."""
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ACTUALS_FILE = DATA_DIR / "actuals.csv"
FORECASTS_FILE = DATA_DIR / "forecasts.csv.gz"

# "Purchase decisions made in January 2026": decisions are taken on D-1 for
# delivery day D, so decision dates 1-31 Jan 2026 => delivery days 2 Jan - 1 Feb 2026.
DELIVERY_START = pd.Timestamp("2026-01-02", tz="UTC")
DELIVERY_END_EXCL = pd.Timestamp("2026-02-02", tz="UTC")

# Forecasts needed: anything published from 48h before the first delivery period.
PUBLISH_FROM = pd.Timestamp("2025-12-31", tz="UTC")
PUBLISH_TO_EXCL = pd.Timestamp("2026-02-02", tz="UTC")
MAX_HORIZON_H = 48

# Day-ahead decision gate: the buyer must commit by this hour (UK local time)
# on the day before delivery. In January UK time == UTC, so we work in UTC.
DEFAULT_CUTOFF_HOUR = 9
ALLOWED_CUTOFF_HOURS = list(range(6, 13))

ELEXON_BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
