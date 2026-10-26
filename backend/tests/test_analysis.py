"""Tests run on small synthetic data, never on the real snapshot."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import analysis as A
from app import config as C


def make_data(tmp_path, monkeypatch):
    rng = np.random.default_rng(0)
    times = pd.date_range("2026-01-02", "2026-01-06 23:30", freq="30min", tz="UTC")
    actual = 5000 + 3000 * np.sin(np.arange(len(times)) / 20)
    act = pd.DataFrame({"start_time": times, "actual": actual})

    rows = []
    for pub in pd.date_range("2026-01-01", "2026-01-06 12:00", freq="1h", tz="UTC"):
        for t, a in zip(times, actual):
            h = (t - pub) / pd.Timedelta(hours=1)
            if 0 <= h <= 48:
                rows.append((t, pub, a + 100 + rng.normal(0, 50 + 10 * h)))
    fc = pd.DataFrame(rows, columns=["start_time", "publish_time", "forecast"])

    monkeypatch.setattr(C, "ACTUALS_FILE", tmp_path / "a.csv")
    monkeypatch.setattr(C, "FORECASTS_FILE", tmp_path / "f.csv.gz")
    act.to_csv(C.ACTUALS_FILE, index=False)
    fc.to_csv(C.FORECASTS_FILE, index=False)
    A.load_raw.cache_clear()
    A.decision_table.cache_clear()
    return act, fc


@pytest.fixture
def data(tmp_path, monkeypatch):
    return make_data(tmp_path, monkeypatch)


def test_decision_forecast_respects_cutoff(data):
    for cutoff in (8, 9, 11):
        tbl = A.decision_table(cutoff)
        gate = tbl["day"] - pd.Timedelta(days=1) + pd.Timedelta(hours=cutoff)
        assert (tbl["publish_time"] <= gate).all()
        # and it is the LATEST such run: top of the hour right at/below the gate
        assert (tbl["publish_time"] == gate).all()


def test_later_cutoff_is_never_less_recent(data):
    early, late = A.decision_table(7), A.decision_table(11)
    assert (late["publish_time"].values >= early["publish_time"].values).all()


def test_error_sign_convention(data):
    tbl = A.decision_table(9)
    assert np.allclose(tbl["error"], tbl["forecast"] - tbl["actual"])
    assert A.compute_metrics(tbl)["bias_mw"] > 0  # synthetic forecast is +100 high


def test_metrics_known_values():
    df = pd.DataFrame(
        {
            "actual": [100.0, 200.0],
            "forecast": [110.0, 180.0],
            "day": pd.to_datetime(["2026-01-02"] * 2, utc=True),
            "horizon_h": [20.0, 20.0],
        }
    )
    df["error"] = df.forecast - df.actual
    df["abs_error"] = df.error.abs()
    m = A.compute_metrics(df)
    assert m["mae_mw"] == 15 and m["bias_mw"] == -5
    assert m["rmse_mw"] == pytest.approx(np.sqrt((100 + 400) / 2))
    assert m["wmape_pct"] == pytest.approx(100 * 30 / 300)


def test_horizon_error_grows(data):
    curve = A.horizon_curve(None, None, max_h=40)["curve"]
    assert curve[-1]["rmse"] > curve[0]["rmse"]


def test_api_endpoints(data):
    from app.main import app

    c = TestClient(app)
    assert c.get("/api/health").json() == {"status": "ok"}
    meta = c.get("/api/meta").json()
    assert meta["delivery_days"][0] == "2026-01-02"
    r = c.get("/api/forecast", params={"day": "2026-01-03"}).json()
    assert len(r["series"]) == 48 and r["cutoff_time"] == "2026-01-02T09:00:00Z"
    acc = c.get("/api/accuracy").json()
    assert acc["metrics"]["n"] > 0 and len(acc["histogram"]) == 24
    assert c.get("/api/accuracy/horizon").json()["curve"]
    assert c.get("/api/forecast", params={"day": "2030-01-01"}).status_code == 404
    assert c.get("/api/forecast", params={"day": "bad"}).status_code == 422
    assert c.get("/api/meta", params={"cutoff_hour": 3}).status_code == 422


def test_missing_data_gives_503(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "ACTUALS_FILE", tmp_path / "nope.csv")
    A.load_raw.cache_clear()
    from app.main import app

    assert TestClient(app).get("/api/meta").status_code == 503
