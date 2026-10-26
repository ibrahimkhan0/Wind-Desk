"""Download the January 2026 snapshot from Elexon into backend/data/.

Run from the backend/ directory:  python -m scripts.fetch_data
The app serves this snapshot, so the deployed site never depends on Elexon being up.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from app import config as C  # noqa: E402
from app.elexon import fetch_actuals, fetch_forecasts  # noqa: E402


def main() -> None:
    C.DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching actuals (FUELHH, WIND)...")
    act = fetch_actuals(C.DELIVERY_START, C.DELIVERY_END_EXCL)
    act = act[(act.start_time >= C.DELIVERY_START) & (act.start_time < C.DELIVERY_END_EXCL)]
    act.to_csv(C.ACTUALS_FILE, index=False)
    print(f"  {len(act)} half-hours  ->  {C.ACTUALS_FILE}")

    print("Fetching forecasts (WINDFOR)... this takes a minute")
    fc = fetch_forecasts(C.PUBLISH_FROM, C.PUBLISH_TO_EXCL)
    horizon_h = (fc.start_time - fc.publish_time) / pd.Timedelta(hours=1)
    fc = fc[
        (fc.start_time >= C.DELIVERY_START)
        & (fc.start_time < C.DELIVERY_END_EXCL)
        & (horizon_h >= 0)
        & (horizon_h <= C.MAX_HORIZON_H)
    ]
    fc.to_csv(C.FORECASTS_FILE, index=False)
    print(f"  {len(fc)} forecast rows  ->  {C.FORECASTS_FILE}")
    print(f"  publish times: {fc.publish_time.min()}  ..  {fc.publish_time.max()}")


if __name__ == "__main__":
    main()
