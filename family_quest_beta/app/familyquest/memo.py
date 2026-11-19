"""A memo per HTTP request: values that one request asks for many times (a setting, the games access, the running
tables, the game passes of a child …) are read once.

main.py opens it for every request (middleware); outside a request (background threads, tests calling the services
directly) there is none and everything is read every time. Every write (Database.x) empties it – the request reads
what it wrote. What is kept must not be changed by its callers: the readers here hand out copies. A task started
during a request inherits the request's context: once the request is over its memo is closed (no longer used).
"""
from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any, Callable


class _Memo(dict):
    closed = False


_MEMO: ContextVar[_Memo | None] = ContextVar("familyquest_request_memo", default=None)
_MISSING = object()


def begin() -> Token:
    return _MEMO.set(_Memo())


def end(token: Token) -> None:
    m = _MEMO.get()
    if m is not None:
        m.closed = True
        m.clear()
    _MEMO.reset(token)


def get(key: Any, fn: Callable[[], Any]) -> Any:
    """`fn()` once per request (every time when there is no open request memo)."""
    m = _MEMO.get()
    if m is None or m.closed:
        return fn()
    v = m.get(key, _MISSING)
    if v is _MISSING:
        v = fn()
        if not m.closed:
            m[key] = v
    return v


def clear() -> None:
    m = _MEMO.get()
    if m:
        m.clear()
