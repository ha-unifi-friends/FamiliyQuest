"""API of 📈 Analytics in the parent area (analytics.py): the whitelist, the templates, a read-only aggregation and the
saved reports («My reports»). Parents only (X-FQ-Parent)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..analytics import Analytics, AnalyticsError, Dashboards, meta
from .auth import Parent, app_of

router = APIRouter(prefix="/api/parent/analytics")


class ReportIn(BaseModel):
    name: str | None = None
    spec: dict[str, Any] | None = None


class DashboardIn(BaseModel):
    name: str | None = None
    tiles: list[Any] | None = None
    period: dict[str, Any] | None = None


def _dash(request: Request) -> Dashboards:
    return Dashboards(app_of(request).db, _an(request))


def _an(request: Request) -> Analytics:
    fq = app_of(request)
    return Analytics(fq.db, fq.weather)


def _run(fn, *a, **k):
    try:
        return fn(*a, **k)
    except AnalyticsError as e:
        raise HTTPException(400, str(e)) from e
    except KeyError as e:
        raise HTTPException(404, "Not found") from e


@router.get("/meta")
def get_meta(request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    people = fq.db.q("SELECT id, name, role, color FROM profile WHERE archived=0 AND role IN ('kid','parent') ORDER BY role='parent', id")
    return {**meta(), "profiles": people, "reports": _an(request).reports(), "dashboards": _dash(request).list()}


@router.post("/query")
def query(spec: dict[str, Any], request: Request, me: dict = Parent) -> dict:
    return _run(_an(request).query, spec)


@router.get("/reports")
def reports(request: Request, me: dict = Parent) -> list[dict]:
    return _an(request).reports()


@router.post("/reports")
def save_report(body: ReportIn, request: Request, me: dict = Parent) -> dict:
    return _run(_an(request).save, body.name, body.spec)


@router.put("/reports/{rid}")
def update_report(rid: str, body: ReportIn, request: Request, me: dict = Parent) -> dict:
    return _run(_an(request).update, rid, body.name, body.spec)


@router.delete("/reports/{rid}")
def delete_report(rid: str, request: Request, me: dict = Parent) -> dict:
    _run(_an(request).delete, rid)
    return {"ok": True}


# ---------------------------------------------------------------- dashboards
@router.get("/dashboards")
def dashboards(request: Request, me: dict = Parent) -> list[dict]:
    return _dash(request).list()


@router.post("/dashboards")
def create_dashboard(body: DashboardIn, request: Request, me: dict = Parent) -> dict:
    return _run(_dash(request).create, body.name)


@router.put("/dashboards/{did}")
def update_dashboard(did: str, body: DashboardIn, request: Request, me: dict = Parent) -> dict:
    return _run(_dash(request).update, did, body.name, body.tiles, body.period)


@router.delete("/dashboards/{did}")
def delete_dashboard(did: str, request: Request, me: dict = Parent) -> dict:
    _run(_dash(request).delete, did)
    return {"ok": True}
