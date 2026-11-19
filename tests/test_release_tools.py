"""tools/release.py and tools/publish_beta.py: --no-push pushes nothing, nothing goes out from a dirty tree or with
missing translations (git and the subprocesses are stand-ins – nothing is written or pushed)."""
import importlib.util
import sys
import types
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"


def _load(name):
    sys.path.insert(0, str(TOOLS))
    try:
        spec = importlib.util.spec_from_file_location(f"fq_tool_{name}", TOOLS / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(TOOLS))


def _fake(monkeypatch, rel, dirty_work=False, i18n_ok=True):
    calls = []

    def git(*args, cwd=None, check=True):
        calls.append(args)
        if args[:2] == ("status", "--porcelain"):
            if "--untracked-files=no" in args:
                return " M family_quest/x.py" if dirty_work else ""
            return "M family_quest_beta/config.yaml"           # something to commit (work branch and main)
        return "abc123" if args[0] in ("rev-parse", "log") else ""

    def run(cmd, **kw):
        calls.append(tuple(str(c) for c in cmd))
        ok = i18n_ok or not any("i18n_extract" in str(c) for c in cmd)
        return types.SimpleNamespace(returncode=0 if ok else 1, stdout="" if ok else "de-DE: 3 missing", stderr="")
    monkeypatch.setattr(rel, "git", git)
    monkeypatch.setattr(rel.subprocess, "run", run)
    return calls


def test_release_no_push_pushes_nothing(monkeypatch):
    rel = _load("release")
    calls = _fake(monkeypatch, rel)
    rel.main(["beta", "9.9.9-beta.1", "Notes", "--no-push"])
    assert ("commit", "-q", "-m") == calls[[c[:1] for c in calls].index(("commit",))][:3]
    assert not [c for c in calls if "push" in c], calls
    assert any("i18n_extract.py" in " ".join(c) for c in calls)       # the preflight ran first
    calls.clear()
    rel.main(["beta", "9.9.9-beta.1", "Notes"])
    assert [c for c in calls if c[:1] == ("push",)]


def test_release_refuses_a_dirty_tree_and_missing_translations(monkeypatch):
    rel = _load("release")
    calls = _fake(monkeypatch, rel, dirty_work=True)
    with pytest.raises(SystemExit, match="commit your changes"):
        rel.main(["stable", "--no-push"])
    calls = _fake(monkeypatch, rel, i18n_ok=False)
    with pytest.raises(SystemExit, match="translations are missing"):
        rel.main(["stable", "--no-push"])
    assert not [c for c in calls if c[:1] in (("commit",), ("push",), ("fetch",))]


def test_publish_refuses_uncommitted_app_changes(monkeypatch, tmp_path):
    pb = _load("publish_beta")
    monkeypatch.setattr(pb, "ROOT", tmp_path)                       # nothing of the real repository is touched
    monkeypatch.setattr(pb.subprocess, "run", lambda cmd, **kw: types.SimpleNamespace(stdout=" M family_quest/app/x.py\n"))
    with pytest.raises(SystemExit, match="uncommitted"):
        pb.publish("family_quest_beta", "Family Quest Beta", "BETA", 8098, tmp_path, "9.9.9-beta.1", ["x"])
    assert not (tmp_path / "family_quest_beta").exists()
