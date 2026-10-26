import re

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import analysis as A
from . import config as C

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

app = FastAPI(title="Wind forecast accuracy API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])
router = APIRouter(prefix="/api")

Cutoff = Query(C.DEFAULT_CUTOFF_HOUR, ge=C.ALLOWED_CUTOFF_HOURS[0], le=C.ALLOWED_CUTOFF_HOURS[-1],
               description="Day-ahead gate, hour (UK time) on the day before delivery")


def _date(v: str | None) -> str | None:
    if v is not None and not DATE_RE.match(v):
        raise HTTPException(422, "Dates must look like 2026-01-15")
    return v


def _guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except A.DataNotReady as e:
        raise HTTPException(503, str(e))
    except KeyError as e:
        raise HTTPException(404, f"No data for {e}")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/meta")
def get_meta(cutoff_hour: int = Cutoff):
    return _guard(A.meta, cutoff_hour)


@router.get("/forecast")
def get_forecast(day: str = Query(...), cutoff_hour: int = Cutoff):
    return _guard(A.day_view, _date(day), cutoff_hour)


@router.get("/accuracy")
def get_accuracy(start: str | None = None, end: str | None = None, cutoff_hour: int = Cutoff):
    return _guard(A.accuracy, cutoff_hour, _date(start), _date(end))


@router.get("/accuracy/horizon")
def get_horizon(start: str | None = None, end: str | None = None):
    return _guard(A.horizon_curve, _date(start), _date(end))


app.include_router(router)
