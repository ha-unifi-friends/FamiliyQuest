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
    assert "function aiPromptBox(promptText, { template, name, onFile, accept" in ui and "aiTemplateButtons" not in ui
    assert 'T("Copy prompt")' in ui and 'document.execCommand("copy")' in ui and "selectNodeContents(pre)" in ui
    assert 'aiPromptBox(T("Make me a learning pack' in src("parent.js") and 'template: "api/ai-template/pack"' in src("parent.js")
    assert 'aiPromptBox(T("Make me a family quiz' in src("community.js") and 'template: "api/ai-template/quiz"' in src("community.js")
    st = src("stories.js")
    assert "aiPromptBox({ picture:" in st and "adventure:" in st and "game:" in st and "template: tplUrl()" in st
    assert 'T("Copy for the AI")' not in st + ui
    # every form imports the AI's answer through the upload of the shared box – no paste area anywhere
    assert 'onFile: f => upload(f)' in src("parent.js") and "onFile: (f, text) => importText(text)" in src("community.js") and "onFile: go" in st
    for name in ("parent.js", "community.js", "stories.js", "shared/ui.js"):
        assert "Paste the answer of the AI" not in src(name) and "textarea.ai-paste" not in src(name) and "textarea.sb-imptext" not in src(name), name
    # the order inside the box: template (primary), prompt, copy, hint, upload; a BOM is removed from the file
    box = ui[ui.index("function aiPromptBox("):ui.index("// link to the parent area")]
    ret = box[box.index('return h("div.ai-prompt"'):]
    order = [ret.index(x) for x in ['h("a.btn.ai-tpl"', "pre,", "ai-copy", "ai-hint", "ai-import"]]
    assert order == sorted(order), order
    assert "replace(/^\\uFEFF/, \"\")" in box and "downloadable .json file" in box
    css = src("shared/base.css")
    assert ".ai-prompt-text {" in css and "white-space: pre-wrap" in css and ".ai-ph {" in css


def test_prompts_have_placeholders_and_are_translated():
    ps = prompts()
    assert len(ps) == 5
    keys = ps + ["Copy prompt", "Example prompt", "Download template for the AI", "Import the AI's JSON file",
                 "Use exactly the format of the attached Family Quest template and give me the result as a downloadable .json file.",
                 "Download the template, copy the prompt, then attach the template in the chat of your AI (ChatGPT, Claude, Gemini …) and fill in the highlighted [parts]. Upload the JSON file you get back."]
    for lang in LANGS:
        d = json.loads((WEB / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        for k in keys:
            assert d.get(k), (lang, k)
        for p in ps:   # the parts to fill in stay [in brackets] – highlighted in the box
            assert len(re.findall(r"\[[^\]\n]+\]", d[p])) == len(re.findall(r"\[[^\]\n]+\]", p)), (lang, p)
            assert d[p].count("\n") == p.count("\n"), (lang, p)


def test_ai_file_import_with_a_bom(client):
    """The AI's JSON file may be saved with a UTF-8 BOM: the quiz and the book import read it all the same."""
    from test_api import setup_family
    ph = setup_family(client)[0]
    quiz = client.get("/api/ai-template/quiz", headers=ph)
    assert quiz.status_code == 200
    r = client.post("/api/community/quizzes/import", json={"text": "\ufeff" + quiz.text}, headers=ph)
    assert r.status_code == 200 and r.json()["ids"], r.text
    book = client.get("/api/stories/ai-template?type=picture", headers=ph)
    r = client.post("/api/stories/import", json={"text": "\ufeff" + book.text}, headers=ph)
    assert r.status_code == 200 and r.json()["ids"], r.text
