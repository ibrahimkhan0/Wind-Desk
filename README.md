# Wind Desk: day-ahead wind forecasts and their accuracy (GB, January 2026)

A web app for a day-ahead power buying team. It answers two questions:

1. **What does the latest wind forecast say at the moment I have to decide?**
   For each delivery day it shows the forecast that was actually available at the day-ahead gate
   (default 09:00 UK time on the previous day), next to what really happened, with a planning
   band and the amount of power still to buy after wind.
2. **How far can I trust it?** MAE, RMSE, bias, wMAPE, the size of a "1 in 10" over-forecast, error by
   day, by time of day, by wind level, and by how far ahead the forecast was made.

Data: Elexon BMRS `FUELHH` (actual, `fuelType=WIND`) and `WINDFOR` (forecast), national level only.

**Live app:** `https://wind-desk-ten.vercel.app/`

## AI tool disclosure
AI tools (Claude) were used to assist with parts of the project, including suggesting the file structure and generating some code and tests. I reviewed and inspected the generated output, ran the application and tests, and worked to understand the implementation and how the components fit together.

## Key assumptions (change them in `backend/app/config.py`)
| Assumption | Choice | Why |
|---|---|---|
| "Decisions made in January 2026" | decision dates 1–31 Jan, so delivery days **2 Jan – 1 Feb 2026** | Day-ahead decisions are made on D−1 for delivery day D |
| Decision gate | **09:00 UK time on D−1** (selectable 06:00–12:00 in the UI) | Approximates the day-ahead auction deadline; the buyer needs the forecast before it |
| Decision forecast | latest WINDFOR run with `publishTime ≤ gate` for each half-hour | Anything published later could not have been used |
| Error | `forecast − actual`; positive = wind over-forecast = risk of under-buying | Over-forecasting is the costly direction for a buyer |
| Time zone | UTC, which equals UK time in January | No DST handling needed for this month |
| Demand | not in the dataset; user types a flat figure to see "left to buy" | Brief limited data to Elexon wind only |

## Repository layout
```
.
├── README.md
├── docker-compose.yml          # backend + nginx-served frontend, http://localhost:8080
├── vercel.json                 # static frontend + Python serverless API
├── requirements.txt            # Python deps used by Vercel
├── api/index.py                # Vercel entrypoint (imports the FastAPI app)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── data/                   # committed snapshot: actuals.csv, forecasts.csv.gz
│   ├── scripts/fetch_data.py   # downloads the snapshot from Elexon
│   ├── app/
│   │   ├── config.py           # all assumptions and date windows
│   │   ├── elexon.py           # BMRS client (chunked, with retries)
│   │   ├── analysis.py         # decision-forecast selection + metrics (pure pandas)
│   │   └── main.py             # FastAPI routes under /api
│   └── tests/test_analysis.py  # pytest, synthetic data
└── frontend/
    ├── Dockerfile, nginx.conf
    ├── vite.config.js          # dev proxy /api -> localhost:8000
    └── src/
        ├── App.jsx, api.js, format.js, styles.css
        └── components/ DecisionView, AccuracyView, Calendar, Kpi
```

## Run it

### Docker (recommended)
```bash
docker compose up --build
# open http://localhost:8080
```

### Without Docker
```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload            # http://localhost:8000/docs

# frontend (second terminal)
cd frontend
npm install
npm run dev                              # http://localhost:5173
```

### Refresh the data from Elexon (optional, snapshot is already committed)
```bash
cd backend && python -m scripts.fetch_data
```

### Tests
```bash
cd backend && python -m pytest -q
```

## API
| Endpoint | Purpose |
|---|---|
| `GET /api/meta?cutoff_hour=9` | delivery days available, publish range |
| `GET /api/forecast?day=2026-01-15&cutoff_hour=9` | decision-time forecast vs actual for one day, planning band, forecast revisions |
| `GET /api/accuracy?start=&end=&cutoff_hour=` | metrics, daily / hourly / histogram / wind-level breakdowns |
| `GET /api/accuracy/horizon?start=&end=` | MAE/RMSE/bias by forecast lead time (1–48 h) |

## Design notes
* **Snapshot, not live calls.** The app serves a committed Elexon snapshot, so the deployed site is fast and
  never breaks because the upstream API is slow or down. `fetch_data.py` reproduces it.
* **Analysis is separate from web code** (`analysis.py`) so it can be tested without HTTP.
* **Planning band** is the empirical 10th–90th percentile of January error applied around the forecast. It
  is estimated on the same month it is shown on, so treat it as descriptive, not a validated predictive interval.
* **Limits:** one month, national level, no demand or price data, no capacity normalisation (the dataset has no
  installed-capacity field, so errors are in MW and as a share of generation).
