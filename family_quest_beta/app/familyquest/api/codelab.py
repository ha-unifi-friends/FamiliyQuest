"""💡 Code Workshop API (familyquest/codelab.py): the family only – children and parents with their login, never guests.

Puzzles, own programs and the heartbeat take the learning-app login (or the parent login); settings and the overview
of the parent area need the parent PIN. Who may see / change a program is decided in codelab.py.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..community import CommunityError
from .auth import Learner, Parent, app_of

router = APIRouter(prefix="/api/codelab")


def _run(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except CommunityError as e:
        raise HTTPException(400, str(e)) from None


def _oversee(request: Request, prof: dict) -> bool:
    """The parent area (parent login, no app login): parents see every program that is not private."""
    return prof["role"] == "parent" and not request.headers.get("x-fq-token")


class ProjectIn(BaseModel):
    title: str = Field(default="", max_length=400)
    visibility: str = Field(default="family", max_length=16)     # new programs: the whole family
    data: dict[str, Any] | None = None


class ProjectEditIn(BaseModel):
    title: str | None = Field(default=None, max_length=400)
    visibility: str | None = Field(default=None, max_length=16)
    data: dict[str, Any] | None = None


class TryIn(BaseModel):
    scripts: list[Any] = Field(default_factory=list, max_length=200)
    inputs: list[str] = Field(default_factory=list, max_length=400)


class SvgIn(BaseModel):
    svg: str = Field(max_length=200_000)
    use: str = Field(default="art", max_length=8)      # «art» a sprite costume (transparent) · «bg» a backdrop


@router.get("")
def home(request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).codelab.home, prof)


@router.post("/tick")
def tick(request: Request, prof: dict = Learner) -> dict:
    """Heartbeat of the open workshop: the time counts as learning time."""
    return app_of(request).codelab.tick(prof)


@router.get("/levels/{lid}")
def level_get(lid: str, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).codelab.level_get, prof, lid[:12])


@router.put("/levels/{lid}")
def level_save(lid: str, body: TryIn, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).codelab.level_save, prof, lid[:12], body.scripts)
    return {"ok": True}


@router.post("/levels/{lid}/solve")
def solve(lid: str, body: TryIn, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).codelab.solve, prof, lid[:12], body.scripts, body.inputs)


@router.get("/projects")
def projects(request: Request, prof: dict = Learner) -> dict:
    fq = app_of(request)
    _run(fq.codelab._need, prof)
    return fq.codelab.projects(prof, _oversee(request, prof))


@router.post("/projects")
def create(body: ProjectIn, request: Request, prof: dict = Learner) -> dict:
    return {"id": _run(app_of(request).codelab.create, prof, body.title, body.data or {}, body.visibility)}


@router.get("/projects/{pid}")
def get(pid: int, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).codelab.get, prof, pid, _oversee(request, prof))


@router.put("/projects/{pid}")
def save(pid: int, body: ProjectEditIn, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).codelab.save, prof, pid, body.data, body.title, body.visibility)


@router.post("/projects/{pid}/remix")
def remix(pid: int, request: Request, prof: dict = Learner) -> dict:
    return {"id": _run(app_of(request).codelab.remix, prof, pid)}


@router.delete("/projects/{pid}")
def delete(pid: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).codelab.delete, prof, pid)
    return {"ok": True}


@router.post("/svg")
def svg(body: SvgIn, request: Request, prof: dict = Learner) -> dict:
    """An own drawing (svgpaint.js): cleaned – what the program will keep – or 400 with the reason."""
    fq = app_of(request)
    _run(fq.codelab._need, prof)
    from ..svgsafe import LIMITS, SvgError, clean_svg
    use = body.use if body.use in LIMITS else "art"
    try:
        return {"svg": clean_svg(body.svg, LIMITS[use])}
    except SvgError as e:
        if str(e) in ("too large", "too many parts"):
            raise HTTPException(400, "The drawing is too large (max. 20 KB)" if use == "art" else "The drawing is too large (max. 60 KB)") from None
        raise HTTPException(400, "This is not a usable SVG picture (<svg viewBox=…> with simple shapes)") from None


@router.get("/settings")
def settings_get(request: Request, me: dict = Parent) -> dict:
    return app_of(request).codelab.settings()


@router.put("/settings")
def settings_put(body: dict[str, Any], request: Request, me: dict = Parent) -> dict:
    return app_of(request).codelab.save_settings(body)


@router.get("/overview")
def overview(request: Request, me: dict = Parent) -> dict:
    """Parent area: puzzle progress per child, shared programs and only the existence of private ones."""
    return _run(app_of(request).codelab.overview, me)
