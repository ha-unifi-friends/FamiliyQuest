"""«Made with your AI»: every AI import shows the example prompt in one component (ui.js aiPromptBox) – translated."""
import json
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"
LANGS = ["de-CH", "de-DE", "es-ES", "fr-FR", "it-IT", "nl-NL", "pl-PL", "pt-BR", "sv-SE"]


def src(name):
    return (WEB / name).read_text(encoding="utf-8")


def prompts():
    """The prompts passed to aiPromptBox (T("…") right after it, and the per-type map of the book import)."""
    out = []
    for name in ("parent.js", "community.js", "stories.js"):
        text = src(name)
        for m in re.finditer(r"aiPromptBox\((.*?)\{ template:", text, re.S):
            out += [json.loads('"' + s + '"') for s in re.findall(r'\bT\("((?:[^"\\]|\\.)*)"\)', m.group(1))]
    return out


def test_every_ai_import_uses_the_prompt_box():
    ui = src("shared/ui.js")
    assert "function aiPromptBox(promptText, { template, name } = {})" in ui and "aiTemplateButtons" not in ui
    assert 'T("Copy prompt")' in ui and 'document.execCommand("copy")' in ui and "selectNodeContents(pre)" in ui
    assert 'aiPromptBox(T("Make me a learning pack' in src("parent.js") and 'template: "api/ai-template/pack"' in src("parent.js")
    assert 'aiPromptBox(T("Make me a family quiz' in src("community.js") and 'template: "api/ai-template/quiz"' in src("community.js")
    st = src("stories.js")
    assert "aiPromptBox({ picture:" in st and "adventure:" in st and "game:" in st and "template: tplUrl()" in st
    assert 'T("Copy for the AI")' not in st + ui
    css = src("shared/base.css")
    assert ".ai-prompt-text {" in css and "white-space: pre-wrap" in css and ".ai-ph {" in css


def test_prompts_have_placeholders_and_are_translated():
    ps = prompts()
    assert len(ps) == 5
    keys = ps + ["Copy prompt", "Example prompt", "Use exactly the format of the attached Family Quest template and answer only with the JSON."]
    for lang in LANGS:
        d = json.loads((WEB / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        for k in keys:
            assert d.get(k), (lang, k)
        for p in ps:   # the parts to fill in stay [in brackets] – highlighted in the box
            assert len(re.findall(r"\[[^\]\n]+\]", d[p])) == len(re.findall(r"\[[^\]\n]+\]", p)), (lang, p)
            assert d[p].count("\n") == p.count("\n"), (lang, p)
