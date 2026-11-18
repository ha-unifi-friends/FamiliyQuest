// ---------------------------------------------------------------- My adventure books (familyquest/stories.py)
// Children and parents write branching stories (scenes with 2–4 choices, good and bad endings, items), the family reads
// them on the shelf. storyShelf(box) draws the shelf (kid app #/stories, parent area › Family), storyReader() reads a book
// (on the server – or a try-out of the working copy right here), storyEditor() writes one (cards and a map).
"use strict";

const SB_COVERS = ["linear-gradient(135deg,#5b5bd6,#8f6bf0)", "linear-gradient(135deg,#e8590c,#f59f00)", "linear-gradient(135deg,#d6336c,#f783ac)",
  "linear-gradient(135deg,#2f9e44,#94d82d)", "linear-gradient(135deg,#0c8599,#3bc9db)", "linear-gradient(135deg,#1c2a6b,#5c7cfa)",
  "linear-gradient(135deg,#7c4a1e,#d9a35b)", "linear-gradient(135deg,#343a40,#868e96)"];
const SB_EMOJI = ["📖", "🦁", "🚀", "🏰", "🐠", "🐉", "🧙", "🏴‍☠️", "🦄", "🌋", "🤖", "👻", "🦖", "🧚", "🕵️", "⚽"];
const SB_PICS = ["🌴", "🦁", "🐒", "🐍", "🐊", "🦜", "🐘", "🦒", "🌳", "🌊", "🏝️", "⛰️", "🌋", "🏜️", "🌲", "🏞️",
  "🚀", "🌕", "⭐", "👽", "🛸", "🪐", "🌌", "☄️", "🏰", "👻", "🦇", "🕯️", "🗝️", "📚", "🧙", "🐉",
  "🐠", "🐙", "🐢", "🦈", "🧜", "🪸", "🐚", "⚓", "🏠", "🏫", "🚗", "🚂", "🍌", "🍎", "🎁", "💎",
  "👑", "🗺️", "💰", "🍫", "🌈", "⛈️", "🌙", "🔥", "😀", "😱", "😴", "🤩", "🙈", "🏆", "💀", "❓"];
const SB_INK = ["#1f2433", "#ffffff", "#868e96", "#e03131", "#f76707", "#fcc419", "#2f9e44", "#0b7285", "#74c0fc", "#1c7ed6",
  "#7048e8", "#f783ac", "#8d5524", "#ffd8a8"];
const SB_SIZES = [4, 10, 22, 44];
const SB_LETTERS = "ABCD";
// who reads a book (stories.py VISIBILITY)
const SB_VIS = () => ({ me: ["🔒", T("Only me"), T("Only you can read it – also parents can't.")],
  kids: ["🧒", T("Other children"), T("All children of the family can read it.")],
  family: ["👨‍👩‍👧", T("Whole family"), T("Children and parents can read it.")] });
// backgrounds of a page: own SVG scenes in img/stories (stories.py BACKGROUNDS)
const SB_BGS = () => ({ jungle: T("Jungle"), beach: T("Beach and island"), deepsea: T("Deep sea"), space: T("Space and planets"),
  castle: T("Haunted castle"), forest: T("Enchanted forest"), mountains: T("Snowy mountains"), desert: T("Desert and pyramids"),
  pirate: T("Pirate ship"), cave: T("Crystal cave"), city: T("City at night"), village: T("Village and farm"), dragon: T("Dragon's lair"),
  candy: T("Candy land"), dino: T("Dinosaur valley"), volcano: T("Volcano"), northpole: T("North Pole"), mine: T("Underground mine"),
  clouds: T("Castle in the clouds"), station: T("Train station"), school: T("School"), kidsroom: T("Kids' room"), attic: T("Attic"), lab: T("Laboratory") });
const sbBgUrl = key => "img/stories/" + key + ".svg";
const SB_KIND = () => ({ scene: ["📄", T("Scene")], good: ["🏆", T("Good ending")], bad: ["💀", T("Bad ending")] });
// the checker (same rules and texts as stories.py check – the server checks again when publishing)
const SB_MSG = {
  title: T("Give the book a title"), empty: T("The book has no pages yet"), start: T("The first page must be a scene"),
  no_text: T("Page {0} has no text yet"), dead_end: T("Page {0} has no continuation"), one_choice: T("Page {0} needs at least 2 choices"),
  no_target: T("Page {0}: choice {1} has no target"), choice_text: T("Page {0}: choice {1} has no text"),
  all_gated: T("Page {0}: at least one choice must work without an item"), item_never: T("Page {0}: choice {1} needs «{2}», but no page gives it"),
  no_good: T("No good ending yet"), unreachable: T("Page {0} cannot be reached from the start"),
};

// replaceChildren without the «null» texts of left-out parts
const sbSet = (el, ...kids) => el.replaceChildren(...kids.flat(Infinity).filter(k => k != null && k !== false && k !== ""));
const sbImg = name => "media/_stories/" + encodeURIComponent(name);
const sbFmt = (s, ...a) => a.reduce((t, v, i) => t.replace("{" + i + "}", v), I18N.tr(s));
// the language of a new book: the app language (Swiss German included), English for an own language of the family
function sbAppLang() {
  const langs = I18N.LANGS.map(([k]) => k).filter(k => k !== "auto");
  const l = /^x-/.test(I18N.lang) ? (I18N.base || "en") : I18N.lang;
  return langs.includes(l) ? l : "en";
}
const sbLangName = code => (I18N.LANGS.find(([k]) => k === code) || [code, code])[1];

function sbPic(pic, cls = "") {
  if (pic && pic.k === "img") return h("img.sb-img" + cls, { src: sbImg(pic.v), alt: "", draggable: false, loading: "lazy" });
  if (pic && pic.k === "emoji") return h("span.sb-emo" + cls, { translate: "no", "aria-hidden": "true" }, pic.v);
  return null;
}

function sbCheck(data, title) {
  const out = [], add = (code, page, ...args) => out.push({ code, page, msg: SB_MSG[code], args: args.map(String) });
  if (!String(title || "").trim()) add("title", null);
  const pages = data.pages || [];
  if (!pages.length) { add("empty", null); return out; }
  const by = new Map(pages.map(p => [p.id, p])), num = new Map(pages.map((p, i) => [p.id, i + 1]));
  if ((by.get(data.start) || {}).kind !== "scene") add("start", data.start);
  const given = new Set(pages.map(p => (p.give || "").trim()).filter(Boolean));
  for (const p of pages) {
    const n = num.get(p.id);
    if (!(p.text || "").trim()) add("no_text", p.id, n);
    if (p.kind !== "scene") continue;
    const ch = p.choices || [];
    if (!ch.length) { add("dead_end", p.id, n); continue; }
    if (ch.length < 2) add("one_choice", p.id, n);
    ch.forEach((c, i) => {
      if (!(c.t || "").trim()) add("choice_text", p.id, n, SB_LETTERS[i]);
      if (!c.to || !by.has(c.to)) add("no_target", p.id, n, SB_LETTERS[i]);
      if (c.need && !given.has(c.need)) add("item_never", p.id, n, SB_LETTERS[i], c.need);
    });
    if (ch.every(c => c.need)) add("all_gated", p.id, n);
  }
  if (!pages.some(p => p.kind === "good")) add("no_good", null);
  const reach = sbReach(data);
  for (const p of pages) if (!reach.has(p.id)) add("unreachable", p.id, num.get(p.id));
  return out;
}
function sbReach(data) {
  const by = new Map(data.pages.map(p => [p.id, p])), seen = new Set(), todo = [data.start];
  while (todo.length) { const id = todo.pop(); if (seen.has(id) || !by.has(id)) continue; seen.add(id); (by.get(id).choices || []).forEach(c => c.to && todo.push(c.to)); }
  return seen;
}
const sbIssueText = i => sbFmt(i.msg, ...i.args);

// ---------------------------------------------------------------- kid app: #/stories
async function storiesView() {
  const box = h("div.sb-wrap");
  screen("stories", { back: () => go("") }, h("h1", "📖 ", T("My adventure books")), box);
  await storyShelf(box);
}

// the card on the Family page of the kid app
function storiesCard() {
  return h("section.card.sb-famcard", h("div.row", h("span.sb-famic", "📖"),
    h("div.grow", h("strong", T("My adventure books")), h("div.small.muted", T("Write your own choose-your-path stories and read the books of the family."))),
    h("button.btn", { onclick: () => go("stories") }, T("Open"))));
}

// parent area › Family: the shelf, books waiting for approval and the settings (⚙️)
async function storiesSection() {
  const sec = h("section.card.sec.sb-psec");
  const box = h("div.sb-wrap");
  const set = h("details.sb-settings", h("summary", "⚙️ ", T("Settings for the adventure books")));
  set.addEventListener("toggle", () => { if (set.open && !set.dataset.done) { set.dataset.done = "1"; storiesSettings(set); } });
  sec.append(h("h2", "📖 ", T("My adventure books")),
    h("p.small.muted", T("Children and parents write choose-your-path stories, the whole family reads them. Parents can edit, unpublish and remove every book.")),
    box, set);
  await storyShelf(box);
  return sec;
}

async function storiesSettings(box) {
  const body = h("div.form.sb-setform", h("p.small.muted", "…"));
  box.append(body);
  let s, kids;
  try { [s, kids] = await Promise.all([api("stories/settings"), api("parent/profiles")]); } catch (e) { return sbSet(body, h("p.bad", e.message)); }
  kids = kids.filter(p => p.role !== "parent");
  const on = kids.map(k => [k.id, h("input", { type: "checkbox", checked: !s.off.includes(k.id) })]);
  const appr = h("input", { type: "checkbox", checked: !!s.approval });
  const num = v => h("input", { type: "number", min: 0, max: 10000, value: v, inputmode: "numeric" });
  const f = { write_coins: num(s.write_coins), write_xp: num(s.write_xp), read_coins: num(s.read_coins), read_xp: num(s.read_xp) };
  const save = async () => {
    const out = { off: on.filter(([, c]) => !c.checked).map(([id]) => id), approval: appr.checked };
    for (const [k, el] of Object.entries(f)) out[k] = Math.max(0, Math.min(10000, Math.round(+el.value || 0)));
    try { await api("stories/settings", { method: "PUT", body: out }); toast(T("Saved"), "good"); } catch (e) { toast(e.message, "bad"); }
  };
  sbSet(body, 
    h("div.field", h("b", T("Adventure books for")), kids.length ? h("div.row.wrap", ...on.map(([id, c]) => h("label.check", c, " ", C(kids.find(k => k.id === id).name)))) : h("span.small.muted", T("No child profile yet"))),
    h("label.check", appr, " ", T("Books need a parent's approval before the family sees them")),
    h("div.sb-rew", h("b", T("Reward for every published book")),
      h("label.field", h("span", "🪙 ", T("Coins")), f.write_coins), h("label.field", h("span", "⭐ XP"), f.write_xp)),
    h("div.sb-rew", h("b", T("Reward when somebody else reads it to an end (once per reader)")),
      h("label.field", h("span", "🪙 ", T("Coins")), f.read_coins), h("label.field", h("span", "⭐ XP"), f.read_xp)),
    h("button.btn", { onclick: save }, "💾 ", T("Save")));
}

// ---------------------------------------------------------------- the shelf
async function storyShelf(box) {
  const draw = async () => {
    let d;
    try { d = await api("stories"); } catch (e) { return sbSet(box, h("p.bad", e.message)); }
    const books = d.books, live = books.filter(b => b.live), mine = books.filter(b => b.mine);
    const others = d.oversee ? books.filter(b => !b.mine && !b.live) : [];
    const pend = d.oversee ? books.filter(b => b.pending) : [];
    const read = b => storyReader(sbServerEngine(b.id), { onClose: draw });
    const visBadge = b => { const [ic, n] = SB_VIS()[b.visibility] || SB_VIS().me; return h("span.sb-vis", { title: n, "aria-label": n }, ic); };
    const cover = b => h("button.sb-book", { onclick: () => read(b), style: { "--sb-c": SB_COVERS[b.color] || SB_COVERS[0] } },
      h("span.sb-cover", { style: b.cover_bg && !b.cover ? { backgroundImage: `url(${sbBgUrl(b.cover_bg)})` } : null },
        b.cover ? sbPic(b.cover) : h("span.sb-cemo", { translate: "no" }, b.emoji),
        b.reading ? h("span.sb-cont", "▶ ", T("Continue")) : null, visBadge(b)),
      h("span.sb-binfo", C(b.title, "strong.sb-btitle"),
        h("span.sb-by", avatarSvg(b.author.avatar, 22), C(b.author.name)),
        h("span.sb-found" + (b.found && b.found === b.endings ? ".all" : ""), "🏁 ", sbFmt(T("{0} of {1} endings found"), b.found, b.endings)),
        b.rating ? h("span.sb-rate", { title: sbFmt(T("Ratings: {0}"), b.votes) }, stars(Math.round(b.rating)), " ", fmt(b.rating, 1)) : null));
    const status = b => [!b.live && !b.pending ? h("span.sb-st", "📝 ", T("Draft")) : null,
      b.pending ? h("span.sb-st.wait", "⏳ ", T("Waiting for approval")) : null,
      b.live ? h("span.sb-st.ok", "✅ ", T("On the shelf")) : null,
      b.changed ? h("span.sb-st", "✏️ ", T("Changes not published yet")) : null,
      h("span.sb-st", SB_VIS()[b.visibility][0], " ", SB_VIS()[b.visibility][1])];
    const row = b => h("div.sb-row",
      h("span.sb-rowic", { style: { background: SB_COVERS[b.color] || SB_COVERS[0] }, translate: "no" }, b.emoji),
      h("div.grow.sb-rowtt", C(b.title, "strong"), h("div.sb-chips", ...status(b),
        h("span.small.muted", sbFmt(T("Pages: {0}"), b.pages), b.mine ? "" : [" · ", C(b.author.name)]))),
      h("div.sb-rowbtn", b.live ? h("button.btn.small.ghost", { title: T("Read"), onclick: () => read(b) }, "📖") : null,
        b.edit ? h("button.btn.small", { onclick: () => storyEditor(b.id, draw) }, "✏️ ", T("Edit")) : null));
    // a private book of somebody else (parent area only): that it exists – no title, no content
    const privRow = b => h("div.sb-row.sb-priv",
      h("span.sb-rowic", "🔒"),
      h("div.grow.sb-rowtt", h("strong", T("Private adventure book")), h("div.sb-chips",
        h("span.sb-by", avatarSvg(b.author.avatar, 22), C(b.author.name)),
        h("span.small.muted", sbFmt(T("Pages: {0}"), b.pages), " · ", fmtDate(b.updated_at)))));
    const approveRow = b => h("div.sb-row.sb-pend",
      h("span.sb-rowic", { style: { background: SB_COVERS[b.color] || SB_COVERS[0] }, translate: "no" }, b.emoji),
      h("div.grow.sb-rowtt", C(b.title, "strong"), h("div.sb-chips", h("span.small.muted", C(b.author.name)), visBadge(b))),
      h("div.sb-rowbtn",
        h("button.btn.small.ghost", { onclick: async () => {
          try { const e = await api("stories/" + b.id); storyReader(sbLocalEngine({ ...e, data: e.pending || e.data }), { preview: true }); } catch (er) { toast(er.message, "bad"); } } }, "👀 ", T("Read")),
        h("button.btn.small.good", { onclick: () => act(`stories/${b.id}/approve`, T("Approved – the others can read it now")) }, "✓ ", T("Approve")),
        h("button.btn.small.ghost", { onclick: () => confirm(I18N.tr(T("Send the book back as a draft?"))) && act(`stories/${b.id}/reject`, T("Back to a draft")) }, "✗")));
    const act = async (path, msg) => { try { await api(path, { method: "POST" }); toast(msg, "good"); draw(); } catch (e) { toast(e.message, "bad"); } };
    sbSet(box,
      pend.length ? h("section.sb-sec.sb-wait", h("h2", "⏳ ", T("Waiting for approval")), ...pend.map(approveRow)) : null,
      h("section.sb-sec", h("div.sec-head", h("h2", "📚 ", T("Family bookshelf")),
        h("div.head-actions", h("button.btn.ghost", { onclick: () => storyImportDialog(id => storyEditor(id, draw)) }, "📥 ", T("Import")),
          h("button.btn", { onclick: () => storyNewDialog(id => storyEditor(id, draw)) }, "+ ", T("New book")))),
        live.length ? h("div.sb-shelf", ...live.map(cover)) : h("p.muted", T("No books on the shelf yet – write the first one!"))),
      h("section.sb-sec", h("h2", "✏️ ", T("My books")),
        mine.length ? h("div.sb-rows", ...mine.map(row))
          : h("p.small.muted", T("Write your own adventure: pages with choices, good and bad endings – or start with a template.")),
        d.rewards.write_coins || d.rewards.write_xp ? h("p.small.muted.sb-rewhint", "🎁 ", sbFmt(T("Every book the others can read: {0}"),
          [d.rewards.write_coins ? d.rewards.write_coins + " 🪙" : "", d.rewards.write_xp ? d.rewards.write_xp + " XP" : ""].filter(Boolean).join(" + "))) : null),
      others.length ? h("section.sb-sec", h("h2", "📝 ", T("Drafts of the family")), h("div.sb-rows", ...others.map(row))) : null,
      (d.private || []).length ? h("section.sb-sec", h("h2", "🔒 ", T("Private books")),
        h("p.small.muted", T("Only their authors can read these books – parents neither. You see only that they exist.")),
        h("div.sb-rows", ...d.private.map(privRow))) : null);
  };
  await draw();
}

// who reads a book: three buttons and what they mean
function sbVisPicker(value, onPick) {
  const box = h("div.sb-vispick");
  const draw = () => sbSet(box,
    h("div.sb-segs.sb-visseg", ...Object.entries(SB_VIS()).map(([k, [ic, n]]) => h("button.sb-seg" + (k === value ? ".on" : ""), { type: "button",
      onclick: () => { if (k === value) return; value = k; draw(); onPick(k); } }, ic, " ", n))),
    h("span.small.muted.sb-vishint", SB_VIS()[value][2]));
  draw();
  return box;
}

function storyNewDialog(done) {
  let tpl = null, emoji = "📖", color = 0, visibility = "me";
  const title = h("input", { type: "text", maxlength: 80, placeholder: I18N.tr(T("e.g. The secret cave")) });
  const lang = h("select", ...I18N.LANGS.filter(([k]) => k !== "auto").map(([k, n]) => h("option", { value: k, translate: "no", selected: k === sbAppLang() }, n)));
  const tiles = h("div.sb-tpls");
  const drawTiles = async () => {
    let list = [];
    try { list = await api("stories/templates?lang=" + encodeURIComponent(lang.value)); } catch {}
    const tile = (key, ic, name, c) => h("button.sb-tpl" + (tpl === key ? ".on" : ""), { type: "button", style: { "--sb-c": SB_COVERS[c] },
      onclick: () => { tpl = key; drawTiles(); } }, h("span.sb-tplic", ic), key ? C(name, "span") : h("span", name));
    sbSet(tiles, tile(null, "📄", T("Empty book"), 0), ...list.map(t => tile(t.key, t.emoji, t.title, t.color)));
  };
  lang.onchange = drawTiles;
  drawTiles();
  const create = async () => {
    if (!tpl && !title.value.trim()) return title.focus();
    try {
      const r = await api("stories", { method: "POST", body: { title: title.value.trim(), lang: lang.value, template: tpl, emoji, color, visibility } });
      m.close(); done(r.id);
    } catch (e) { toast(e.message, "bad"); }
  };
  const m = modal(h("div.form.sb-new", h("h2", "📖 ", T("New book")),
    h("label.field", T("Title"), title, h("span.hint", T("With a template you may leave it empty – the template has one."))),
    h("label.field", T("Language of the book"), lang),
    h("div.field", h("b", T("Start with")), tiles),
    h("div.field", h("b", T("Who can read it?")), sbVisPicker(visibility, v => { visibility = v; })),
    h("div.row", h("button.btn", { onclick: create }, "✏️ ", T("Start writing")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
}

// import: a file or the answer of an AI (paste) – becomes a private draft
function storyImportDialog(done) {
  const text = h("textarea.sb-imptext", { rows: 8, placeholder: I18N.tr(T("Paste the answer of the AI here …")) });
  const file = h("input", { type: "file", accept: ".json,.txt,application/json,text/plain" });
  file.onchange = async () => { const f = file.files[0]; if (!f) return; if (f.size > 1e6) return toast(I18N.tr(T("The file is too large")), "bad"); text.value = await f.text(); };
  const tplUrl = "api/stories/ai-template";
  const go = async () => {
    try {
      const r = await api("stories/import", { method: "POST", body: { text: text.value } });
      m.close(); toast(I18N.tr(T("Imported as a private draft")), "good"); done(r.ids[0]);
    } catch (e) { toast(e.message, "bad"); }
  };
  const m = modal(h("div.form.sb-imp", h("h2", "📥 ", T("Import a book")),
    h("p.small", T("1. Copy the template for the AI and paste it into any AI chat. 2. Describe your story idea. 3. Paste the answer here – or choose a book file that was exported.")),
    h("div.row.wrap",
      h("a.btn.small.ghost", { style: { textDecoration: "none" }, href: tplUrl, download: "family-quest-story-template.json" }, "⬇️ ", T("Template for the AI")),
      h("button.btn.small.ghost", { onclick: async () => {
        try { await navigator.clipboard.writeText(await (await fetch(tplUrl)).text()); toast(T("Copied – paste it into the chat of your AI"), "good"); }
        catch { toast(T("Copying did not work – use the download"), "bad"); } } }, "📋 ", T("Copy for the AI"))),
    text, h("label.field", T("…or a file"), file),
    h("p.small.muted", "🔒 ", T("The book comes in as a private draft – the checker shows what is still missing. Own drawings and photos are not part of the file.")),
    h("div.row", h("button.btn", { onclick: go }, "📥 ", T("Import")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
}

// ---------------------------------------------------------------- reading
function sbServerEngine(id) {
  const post = (p, body) => api(`stories/${id}/${p}`, { method: "POST", body });
  return { read: () => api(`stories/${id}/read`), choose: i => post("read/choose", { i }), restart: () => post("read/restart"), rate: n => post("rate", { stars: n }) };
}

// a try-out of a working copy (editor ▶, a book waiting for approval): runs right here, nothing is saved
function sbLocalEngine(book) {
  const d = book.data, pg = id => d.pages.find(p => p.id === id);
  const ends = d.pages.filter(p => p.kind !== "scene").map(p => p.id), found = new Set();
  let page = null, items = [], finished = 0;
  const enter = id => { page = id; const p = pg(id); if (p && p.give && !items.includes(p.give)) items = [...items, p.give]; };
  const view = (ne = false) => {
    const p = pg(page) || d.pages[0];
    return { title: book.title, emoji: book.emoji, color: book.color, lang: book.lang, items, endings: ends.length, found: found.size,
      new_ending: ne, finished, may_rate: false, number: d.pages.indexOf(p) + 1,
      page: { id: p.id, kind: p.kind, text: p.text, pic: p.pic, bg: p.bg, give: p.give, start: p.id === d.start,
        choices: (p.choices || []).map((c, i) => ({ i, t: c.t, need: c.need })).filter(c => !c.need || items.includes(c.need)) } };
  };
  return {
    read: async () => { if (page == null) enter(d.start || (d.pages[0] || {}).id); return view(); },
    restart: async () => { items = []; enter(d.start); return view(); },
    choose: async i => {
      const c = ((pg(page) || {}).choices || [])[i];
      if (!c || !c.to || !pg(c.to)) throw new Error(I18N.tr(T("This choice has no target yet")));
      enter(c.to);
      let ne = false;
      if (pg(c.to).kind !== "scene") { ne = !found.has(c.to); found.add(c.to); finished++; }
      return view(ne);
    },
    rate: async () => {},
  };
}

function storyReader(engine, { onClose = null, preview = false } = {}) {
  const full = h("div.quiz-full.sb-full.sb-reader");
  let st = null, busy = false, closed = false;
  const close = () => {
    if (closed) return; closed = true;
    full.remove(); window.removeEventListener("hashchange", close);
    if (!document.querySelector(".sb-full")) document.body.classList.remove("quiz-open");
    onClose && onClose();
  };
  window.addEventListener("hashchange", close);
  const act = async (fn, fresh = true) => {
    if (busy) return; busy = true;
    try { st = await fn(); draw(fresh); } catch (e) { toast(e.message, "bad"); } finally { busy = false; }
  };
  const restart = () => act(() => engine.restart());
  const bag = () => { const m = modal(h("div.sb-bag", h("h2", "🎒 ", T("Backpack")),
    st.items.length ? h("ul", ...st.items.map(i => C(i, "li"))) : h("p.muted", T("Nothing yet")),
    h("button.btn", { onclick: () => m.close() }, T("Close")))); };
  const draw = fresh => {
    const p = st.page, end = p.kind !== "scene";
    const rateBox = st.may_rate ? h("div.sb-rateme", h("span.small", T("How did you like the book?")),
      h("div.sb-stars", ...[1, 2, 3, 4, 5].map(n => h("button.sb-star" + (n <= (st.rating || 0) ? ".on" : ""), { "aria-label": n + " ★",
        onclick: async () => { try { await engine.rate(n); st.rating = n; draw(false); toast(T("Thank you!"), "good"); } catch (e) { toast(e.message, "bad"); } } }, "★")))) : null;
    sbSet(full, 
      h("div.sb-rtop",
        h("button.icon-btn", { title: T("Close"), "aria-label": T("Close"), onclick: close }, "✕"),
        h("div.sb-rtitle", h("span", { translate: "no" }, st.emoji), C(st.title, "strong")),
        h("span.sb-pill", { title: T("Endings found") }, "🏁 ", st.found + "/" + st.endings),
        st.items.length ? h("button.sb-pill", { title: T("Backpack"), onclick: bag }, "🎒 ", String(st.items.length)) : null,
        !p.start ? h("button.icon-btn", { title: T("Back to the start"), "aria-label": T("Back to the start"), onclick: restart }, "⏮") : null),
      preview ? h("p.sb-try.small", "👀 ", T("Try-out – nothing is saved")) : null,
      h("article.sb-page.k-" + p.kind + (fresh ? ".fresh" : ""), { lang: st.lang },
        p.pic || p.bg ? h("div.sb-ppic" + (p.bg ? ".bg" : ""), { style: p.bg ? { backgroundImage: `url(${sbBgUrl(p.bg)})` } : null }, sbPic(p.pic)) : null,
        end ? h("div.sb-endtag", p.kind === "good" ? "🏆 " : "💀 ", p.kind === "good" ? T("Good ending") : T("Bad ending")) : null,
        C(p.text, "div.sb-text"),
        p.give ? h("div.sb-gift", "🎒 ", T("You get:"), " ", C(p.give, "b")) : null),
      !end ? (p.choices.length ? h("div.sb-choices", { lang: st.lang }, ...p.choices.map(c => h("button.sb-choice", { onclick: () => act(() => engine.choose(c.i)) },
        h("span.sb-letter.l" + c.i, SB_LETTERS[c.i]), C(c.t || "…", "span.grow"), c.need ? h("span.sb-need", { title: c.need, translate: "no" }, "🎒") : null)))
        : h("p.muted.center", T("This page has no continuation yet")))
      : h("div.sb-endbox",
          st.new_ending ? h("p.sb-newend", p.kind === "good" ? "🎉 " : "😬 ", p.kind === "good" ? T("New ending found!") : T("New ending found – but not a happy one!")) : null,
          h("p.sb-count", sbFmt(T("{0} of {1} endings found"), st.found, st.endings)),
          h("div.row.center.wrap", h("button.btn" + (p.kind === "bad" ? ".big" : ""), { onclick: restart }, "↺ ", p.kind === "bad" ? T("Try again") : T("Read again")),
            h("button.btn.ghost", { onclick: close }, "📚 ", T("Back to the bookshelf"))),
          rateBox));
    if (fresh) {
      full.scrollTo(0, 0);
      if (end && p.kind === "good") { Sound.play("done"); confetti(full); }
      else if (end) Sound.play("wrong");
      else if (st.number > 1) Sound.play("tap");
    }
  };
  document.body.append(full);
  document.body.classList.add("quiz-open");
  act(() => engine.read(), false);
}

// ---------------------------------------------------------------- writing
async function storyEditor(id, onClose = null) {
  let ed;
  try { ed = await api("stories/" + id); } catch (e) { return toast(e.message, "bad"); }
  const data = ed.data;
  const meta = { title: ed.title, emoji: ed.emoji, color: ed.color, lang: ed.lang };
  let visSent = ed.visibility;                            // sent with the next save only when it changed
  let mode = "cards", dirty = false, timer = null, saving = null, showIssues = false, closed = false, zoom = null;
  try { mode = localStorage.getItem("fq.sb.mode") === "map" ? "map" : "cards"; } catch {}
  const full = h("div.quiz-full.sb-full.sb-editor");
  const head = h("div.sb-ehead"), checker = h("div.sb-checker"), body = h("div.sb-ebody");
  const stateEl = h("span.sb-state");
  full.append(head, checker, body);

  const issues = () => sbCheck(data, meta.title);
  const setState = s => { stateEl.className = "sb-state " + s; stateEl.textContent = { dirty: "●", saving: "…", saved: "✓", error: "⚠" }[s] || "";
    stateEl.title = I18N.tr({ dirty: T("Not saved yet"), saving: T("Saving …"), saved: T("Saved"), error: T("Not saved") }[s] || ""); };
  const save = async () => {
    clearTimeout(timer);
    if (saving) await saving;
    if (!dirty) return true;
    dirty = false; setState("saving");
    const body = { data, ...meta };
    if (visSent !== ed.visibility) body.visibility = visSent;
    saving = api("stories/" + id, { method: "PUT", body }).then(r => { const vis = r.visibility !== ed.visibility || r.pending !== ed.pending; ed = r; visSent = r.visibility;
      setState(dirty ? "dirty" : "saved"); if (vis) drawHead(); return true; })
      .catch(e => { dirty = true; setState("error"); toast(e.message, "bad"); return false; }).finally(() => { saving = null; });
    return saving;
  };
  const changed = (redraw = false) => {
    dirty = true; setState("dirty");
    clearTimeout(timer); timer = setTimeout(save, 1200);
    drawChecker();
    if (redraw) drawBody(); else markCards();
  };
  const close = async () => {
    if (closed) return;
    closed = true;
    window.removeEventListener("hashchange", close);
    await save();
    full.remove();
    if (!document.querySelector(".sb-full")) document.body.classList.remove("quiz-open");
    onClose && onClose();
  };
  window.addEventListener("hashchange", close);

  const byId = pid => data.pages.find(p => p.id === pid);
  const num = pid => data.pages.findIndex(p => p.id === pid) + 1;
  const items = () => [...new Set(data.pages.map(p => (p.give || "").trim()).filter(Boolean))];
  const newPage = kind => {
    const pid = Math.max(0, ...data.pages.map(p => p.id)) + 1;
    const p = { id: pid, kind, text: "", pic: null };
    if (kind === "scene") Object.assign(p, { give: null, choices: [{ t: "", to: null, need: null }, { t: "", to: null, need: null }] });
    data.pages.push(p);
    if (!data.start) data.start = pid;
    return p;
  };
  const excerpt = (p, n = 26) => { const t = (p.text || "").replace(/\s+/g, " ").trim(); return t.length > n ? t.slice(0, n - 1) + "…" : t || "…"; };
  const goPage = pid => {
    if (mode !== "cards") { mode = "cards"; drawHead(); drawBody(); }
    const el = full.querySelector("#sbp-" + pid);
    if (el) { el.scrollIntoView({ behavior: "smooth", block: "start" }); el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); }
  };

  // ---------- header
  const publish = async () => {
    if (!(await save())) return;
    const list = issues();
    if (list.length) { showIssues = true; drawChecker(); return toast(I18N.tr(T("Not finished yet – look at the checker")), "bad"); }
    try {
      const r = await api(`stories/${id}/publish`, { method: "POST" });
      if (r.status === "pending") toast(I18N.tr(T("Sent to the parents – they check it first")), "good");
      else { toast(I18N.tr(T("Published! The family can read it now.")), "good"); confetti(full); Sound.play("done"); }
      ed = await api("stories/" + id); drawHead();
    } catch (e) { toast(e.message, "bad"); }
  };
  const tryOut = () => storyReader(sbLocalEngine({ ...meta, data: JSON.parse(JSON.stringify(data)) }), { preview: true });
  const drawHead = () => {
    const seg = (k, ic, label) => h("button.sb-seg" + (mode === k ? ".on" : ""), { onclick: () => { mode = k; try { localStorage.setItem("fq.sb.mode", k); } catch {} drawHead(); drawBody(); } }, ic, " ", label);
    sbSet(head, 
      h("div.sb-erow",
        h("button.icon-btn", { title: T("Close"), "aria-label": T("Close"), onclick: close }, "✕"),
        h("button.sb-etitle", { title: T("Book settings"), onclick: () => metaDialog() },
          h("span.sb-eic", { style: { background: SB_COVERS[meta.color] || SB_COVERS[0] }, translate: "no" }, meta.emoji),
          C(meta.title || "…", "strong"), h("span.sb-pen", "⚙️")),
        stateEl),
      h("div.sb-erow.sb-tools",
        h("div.sb-segs", seg("cards", "🃏", T("Pages")), seg("map", "🗺️", T("Map"))),
        h("span.grow"),
        h("button.btn.small.ghost", { onclick: tryOut, title: T("Try it out") }, "▶ ", h("span.sb-hide-s", T("Try"))),
        h("button.btn.small", { onclick: publish },
          "🚀 ", ed.live && !ed.changed ? T("On the shelf") : ed.pending ? T("Waiting") : T("Publish"))),
      ed.mine ? h("div.sb-erow.sb-visrow", h("b.small", T("Who can read it?")), sbVisPicker(visSent, v => { visSent = v; changed(); save(); }))
        : h("p.sb-note", SB_VIS()[ed.visibility][0], " ", SB_VIS()[ed.visibility][1], " · ", C(ed.author)),
      ed.pending ? h("p.sb-note", "⏳ ", ed.parent ? T("This book waits for a parent's approval (Family › My adventure books).") : T("Your book waits for a parent's approval.")) : null,
      ed.reward && (ed.reward.write_coins || ed.reward.write_xp) && !ed.shared ? h("p.sb-note", "🎁 ", sbFmt(T("When the others can read it you get {0}"),
        [ed.reward.write_coins ? ed.reward.write_coins + " 🪙" : "", ed.reward.write_xp ? ed.reward.write_xp + " XP" : ""].filter(Boolean).join(" + "))) : null);
  };

  // ---------- checker
  const drawChecker = () => {
    const list = issues();
    sbSet(checker, list.length
      ? h("details.sb-issues", { open: showIssues, ontoggle: e => { showIssues = e.target.open; } },
          h("summary", "⚠️ ", sbFmt(T("{0} things to finish before publishing"), list.length)),
          h("ul", ...list.map(i => h("li", i.page ? h("button.link", { onclick: () => goPage(i.page) }, sbIssueText(i)) : sbIssueText(i)))))
      : h("div.sb-ready", "✅ ", T("Ready to publish – every path leads somewhere.")));
  };

  // ---------- cards
  const markCards = () => {
    const list = issues();
    for (const el of full.querySelectorAll(".sb-pcard")) {
      const pid = +el.dataset.id, mine = list.filter(i => i.page === pid);
      el.classList.toggle("bad", mine.length > 0);
      const box = el.querySelector(".sb-pissues");
      if (box) sbSet(box, ...mine.map(i => h("li", sbIssueText(i))));
    }
  };
  const targetSelect = (p, c) => {
    const sel = h("select.sb-target", { "aria-label": T("Goes to") },
      h("option", { value: "" }, "→ ", T("choose a page")),
      ...data.pages.filter(x => x.id !== p.id).map(x => h("option", { value: x.id, selected: x.id === c.to, translate: "no" },
        `${num(x.id)}. ${SB_KIND()[x.kind][0]} ${excerpt(x)}`)),
      h("option", { value: "new:scene" }, "＋ ", T("New scene")),
      h("option", { value: "new:good" }, "＋ 🏆 ", T("New good ending")),
      h("option", { value: "new:bad" }, "＋ 💀 ", T("New bad ending")));
    sel.onchange = () => {
      if (sel.value.startsWith("new:")) {
        const np = newPage(sel.value.slice(4)); c.to = np.id;
        toast(sbFmt(T("Page {0} added"), num(np.id)), "good");
      } else c.to = sel.value ? +sel.value : null;
      changed(true);
    };
    return sel;
  };
  const needSelect = (c, its) => {
    const all = [...new Set([...its, ...(c.need ? [c.need] : [])])];
    if (!all.length) return null;
    const sel = h("select.sb-needsel", { "aria-label": T("Needs an item") },
      h("option", { value: "" }, "🎒 ", T("no item needed")),
      ...all.map(i => h("option", { value: i, selected: i === c.need, translate: "no" }, "🎒 " + i)));
    sel.onchange = () => { c.need = sel.value || null; changed(true); };
    return sel;
  };
  const pageCard = (p, i) => {
    const K = SB_KIND();
    const text = h("textarea.sb-ptext", { rows: 4, maxlength: 1500, lang: meta.lang,
      placeholder: I18N.tr(p.kind === "scene" ? T("What happens here?") : p.kind === "good" ? T("How does it end well?") : T("What goes wrong?")) });
    text.value = p.text || "";
    text.oninput = () => { p.text = text.value; changed(); };
    const kinds = h("div.sb-kinds", ...Object.entries(K).map(([k, [ic, label]]) => h("button.sb-kind" + (p.kind === k ? ".on" : ""), { title: label, "aria-label": label,
      onclick: () => {
        if (p.kind === k) return;
        if (k !== "scene" && (p.choices || []).some(c => c.t || c.to) && !confirm(I18N.tr(T("An ending has no choices – remove them?")))) return;
        p.kind = k;
        if (k === "scene") { p.choices = p.choices && p.choices.length ? p.choices : [{ t: "", to: null, need: null }, { t: "", to: null, need: null }]; p.give = p.give || null; }
        else { delete p.choices; delete p.give; }
        changed(true);
      } }, ic, h("span.sb-hide-s", " ", label))));
    const card = h("section.card.sb-pcard.k-" + p.kind, { id: "sbp-" + p.id, "data-id": p.id },
      h("div.sb-phead", h("span.sb-pnum", String(i + 1)), kinds, p.id === data.start ? h("span.sb-startchip", "⭐ ", T("First page")) : null, h("span.grow"),
        h("button.icon-btn.sb-del", { title: T("Remove page"), "aria-label": T("Remove page"), onclick: () => {
          if (data.pages.length > 1 && !confirm(I18N.tr(T("Remove this page?")))) return;
          data.pages.splice(data.pages.indexOf(p), 1);
          data.pages.forEach(x => (x.choices || []).forEach(c => { if (c.to === p.id) c.to = null; }));
          if (data.start === p.id) data.start = (data.pages[0] || {}).id || null;
          changed(true);
        } }, "🗑")),
      h("div.sb-pmain",
        h("div.sb-picbtns",
          h("button.sb-picbtn" + (p.bg ? ".bg" : ""), { title: T("Picture"), onclick: () => picDialog(p), style: p.bg ? { backgroundImage: `url(${sbBgUrl(p.bg)})` } : null },
            p.pic ? sbPic(p.pic) : h("span.sb-nopic", "🖼️", h("span.small", T("Picture")))),
          h("button.btn.small.ghost.sb-bgbtn", { onclick: () => bgDialog(p), title: p.bg ? SB_BGS()[p.bg] : T("Background") }, "🏞️ ", h("span.small", T("Background")))),
        text),
      p.kind === "scene" ? sceneParts(p) : null,
      h("ul.sb-pissues"),
      p.kind === "scene" && p.id !== data.start ? h("button.link.small", { onclick: () => { data.start = p.id; changed(true); } }, "⭐ ", T("Make this the first page")) : null);
    return card;
  };
  const sceneParts = p => {
    const its = items();
    const give = h("input.sb-give", { type: "text", maxlength: 40, value: p.give || "", placeholder: I18N.tr(T("e.g. 🍌 Banana")), lang: meta.lang });
    give.oninput = () => { p.give = give.value.trim() || null; changed(); };
    give.onchange = () => changed(true);
    const rows = (p.choices || []).map((c, i) => {
      const t = h("input.sb-ctext", { type: "text", maxlength: 120, value: c.t || "", lang: meta.lang, placeholder: sbFmt(T("Choice {0}"), SB_LETTERS[i]) });
      t.oninput = () => { c.t = t.value; changed(); };
      return h("div.sb-crow",
        h("span.sb-letter.l" + i, SB_LETTERS[i]),
        h("div.sb-cfields", t, h("div.sb-csel", targetSelect(p, c),
          c.to && byId(c.to) ? h("button.icon-btn.sb-go", { title: T("Go to this page"), "aria-label": T("Go to this page"), onclick: () => goPage(c.to) }, "↘") : null,
          needSelect(c, its))),
        h("button.icon-btn.sb-cdel", { title: T("Remove choice"), "aria-label": T("Remove choice"), onclick: () => { p.choices.splice(i, 1); changed(true); } }, "✕"));
    });
    return h("div.sb-scene",
      h("div.sb-choices-ed", h("b.small", T("Choices")), ...rows,
        p.choices.length < 4 ? h("button.btn.small.ghost", { onclick: () => { p.choices.push({ t: "", to: null, need: null }); changed(true); } }, "+ ", T("Add choice")) : null),
      h("label.sb-givelab", h("span.small", "🎒 ", T("On this page you find (optional):")), give));
  };
  const drawCards = () => {
    sbSet(body, h("div.sb-cards", ...data.pages.map(pageCard)),
      h("div.sb-addrow", h("span.small.muted", T("New page:")),
        h("button.btn.small.ghost", { onclick: () => { const p = newPage("scene"); changed(true); goPage(p.id); } }, "📄 ", T("Scene")),
        h("button.btn.small.ghost", { onclick: () => { const p = newPage("good"); changed(true); goPage(p.id); } }, "🏆 ", T("Good ending")),
        h("button.btn.small.ghost", { onclick: () => { const p = newPage("bad"); changed(true); goPage(p.id); } }, "💀 ", T("Bad ending"))));
    markCards();
  };

  // ---------- map: rows by distance from the start, arrows for the choices
  const drawMap = () => {
    const W = 132, H = 74, GX = 28, GY = 64, PAD = 20;
    const by = new Map(data.pages.map(p => [p.id, p]));
    const depth = new Map(), order = [];
    const queue = data.start && by.has(data.start) ? [data.start] : [];
    if (queue.length) depth.set(data.start, 0);
    while (queue.length) {
      const pid = queue.shift(); order.push(pid);
      for (const c of by.get(pid).choices || []) if (c.to && by.has(c.to) && !depth.has(c.to)) { depth.set(c.to, depth.get(pid) + 1); queue.push(c.to); }
    }
    const rows = [];
    order.forEach(pid => (rows[depth.get(pid)] = rows[depth.get(pid)] || []).push(pid));
    const lost = data.pages.filter(p => !depth.has(p.id)).map(p => p.id);
    if (lost.length) rows.push(lost);
    const cols = Math.max(1, ...rows.map(r => r.length));
    const width = PAD * 2 + cols * W + (cols - 1) * GX + 40, height = PAD * 2 + rows.length * H + (rows.length - 1) * GY;
    const pos = new Map();
    rows.forEach((r, y) => { const off = (width - 40 - (r.length * W + (r.length - 1) * GX)) / 2;
      r.forEach((pid, x) => pos.set(pid, { x: off + x * (W + GX), y: PAD + y * (H + GY) })); });
    const list = issues(), bad = new Set(list.filter(i => i.page).map(i => i.page));
    const NS = "http://www.w3.org/2000/svg";
    const S_ = (tag, attrs = {}, ...kids) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); kids.forEach(k => k != null && e.append(k)); return e; };
    if (zoom == null) zoom = Math.max(0.55, Math.min(1, ((body.clientWidth || full.clientWidth) - 24) / width));
    const svg = S_("svg", { width: width * zoom, height: height * zoom, viewBox: `0 0 ${width} ${height}`, class: "sb-svg", translate: "no" });
    svg.append(S_("defs", {}, S_("marker", { id: "sbArrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" },
      S_("path", { d: "M0 0 L10 5 L0 10 z", class: "sb-arrowhead" }))));
    const edges = S_("g", { class: "sb-edges" }), boxes = S_("g");
    for (const p of data.pages) {
      const a = pos.get(p.id);
      (p.choices || []).forEach((c, i) => {
        const b = c.to && pos.get(c.to);
        if (!b) {                                          // a choice without target: a short red stub
          const x = a.x + W / 2 + (i - ((p.choices.length - 1) / 2)) * 22, y = a.y + H;
          edges.append(S_("path", { d: `M${x} ${y} l0 18`, class: "sb-edge open" }), S_("text", { x, y: y + 30, class: "sb-elabel open", "text-anchor": "middle" }, SB_LETTERS[i] + "?"));
          return;
        }
        const x1 = a.x + W / 2 + (i - ((p.choices.length - 1) / 2)) * 22, y1 = a.y + H;
        let d, lx, ly;
        if (b.y > a.y) {
          const x2 = b.x + W / 2, y2 = b.y;
          d = `M${x1} ${y1} C${x1} ${y1 + GY / 2} ${x2} ${y2 - GY / 2} ${x2} ${y2 - 2}`; lx = x1 + 8; ly = y1 + 14;
        } else {                                            // back up (paths that merge into an earlier page, loops): round the right side
          const x2 = b.x + W, y2 = b.y + H / 2, bend = Math.max(a.x + W, b.x + W) + 30;
          d = `M${x1} ${y1} C${x1} ${y1 + 26} ${bend} ${y1 + 26} ${bend} ${(y1 + y2) / 2} S${x2 + 30} ${y2} ${x2 + 2} ${y2}`; lx = x1 + 8; ly = y1 + 14;
        }
        edges.append(S_("path", { d, class: "sb-edge" + (c.need ? " need" : ""), "marker-end": "url(#sbArrow)" }),
          S_("text", { x: lx, y: ly, class: "sb-elabel" }, SB_LETTERS[i] + (c.need ? "🎒" : "")));
      });
      const cls = "sb-node k-" + p.kind + (bad.has(p.id) ? " bad" : "") + (!depth.has(p.id) ? " lost" : "") + (p.id === data.start ? " start" : "");
      const g = S_("g", { class: cls, transform: `translate(${a.x} ${a.y})`, tabindex: 0, role: "button" });
      g.addEventListener("click", () => goPage(p.id));
      g.addEventListener("keydown", e => { if (e.key === "Enter") goPage(p.id); });
      const pic = p.pic && p.pic.k === "emoji" ? p.pic.v : p.pic ? "🖼️" : SB_KIND()[p.kind][0];
      g.append(S_("rect", { width: W, height: H, rx: 12 }),
        S_("text", { x: 10, y: 22, class: "sb-nnum" }, (p.id === data.start ? "⭐ " : "") + num(p.id)),
        S_("text", { x: W - 10, y: 24, class: "sb-npic", "text-anchor": "end" }, pic),
        S_("text", { x: 10, y: 46, class: "sb-ntext" }, excerpt(p, 17)),
        S_("text", { x: 10, y: 64, class: "sb-nkind" }, (p.kind !== "scene" ? SB_KIND()[p.kind][0] + " " : "") + (p.give ? "🎒 " + p.give.slice(0, 12) : "")));
      if (bad.has(p.id)) g.append(S_("text", { x: W - 8, y: H - 8, class: "sb-nwarn", "text-anchor": "end" }, "⚠️"));
      boxes.append(g);
    }
    svg.append(edges, boxes);
    const z = f => { zoom = Math.max(0.4, Math.min(2, zoom * f)); drawMap(); };
    sbSet(body, 
      h("div.sb-maphead", h("div.sb-legend.small", h("span", "⭐ ", T("First page")), h("span", "📄 ", T("Scene")), h("span", "🏆 ", T("Good ending")), h("span", "💀 ", T("Bad ending")),
        h("span.sb-lg-bad", "⚠️ ", T("needs work")), h("span.sb-lg-lost", T("cannot be reached"))),
        h("div.sb-zoom", h("button.icon-btn", { title: T("Zoom out"), "aria-label": T("Zoom out"), onclick: () => z(1 / 1.25) }, "−"),
          h("button.icon-btn", { title: T("Zoom in"), "aria-label": T("Zoom in"), onclick: () => z(1.25) }, "+"))),
      h("div.sb-map", svg),
      h("p.small.muted", T("Tap a page to edit it. Arrows show where the choices lead; arrows back up are paths that meet again.")));
  };
  const drawBody = () => { if (mode === "map") drawMap(); else drawCards(); };

  // ---------- pictures: emoji, own drawing, photo
  const picDialog = p => {
    const set = pic => { p.pic = pic; m.close(); changed(true); };
    const own = h("input.sb-ownemo", { type: "text", maxlength: 8, placeholder: "🙂", "aria-label": T("Own emoji") });
    const file = h("input", { type: "file", accept: "image/*", hidden: true });
    file.onchange = async () => {
      const f = file.files[0]; if (!f) return;
      try { const blob = await sbShrink(f); const r = await sbUpload(blob, "photo.jpg"); set({ k: "img", v: r.name, src: "photo" }); }
      catch (e) { toast(e.message, "bad"); }
    };
    const m = modal(h("div.form.sb-picdlg", h("h2", "🖼️ ", T("Picture")),
      h("div.sb-picgrid", ...SB_PICS.map(e => h("button.sb-pe", { type: "button", translate: "no", onclick: () => set({ k: "emoji", v: e }) }, e)),
        own, h("button.btn.small", { onclick: () => own.value.trim() && set({ k: "emoji", v: own.value.trim() }) }, "✓")),
      h("div.row.wrap",
        h("button.btn", { onclick: async () => {
          m.close();
          const blob = await sbPainter(p.pic && p.pic.k === "img" && p.pic.src === "draw" ? sbImg(p.pic.v) : null);
          if (!blob) return;
          try { const r = await sbUpload(blob, "drawing.png"); p.pic = { k: "img", v: r.name, src: "draw" }; changed(true); } catch (e) { toast(e.message, "bad"); }
        } }, "🎨 ", T("Paint")),
        h("button.btn.ghost", { onclick: () => file.click() }, "📷 ", T("Photo")), file,
        p.pic ? h("button.btn.ghost", { onclick: () => set(null) }, "🗑 ", T("No picture")) : null,
        h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
  };

  // ---------- backgrounds: own scenes behind the picture
  const bgDialog = p => {
    const set = bg => { p.bg = bg; m.close(); changed(true); };
    const m = modal(h("div.form.sb-bgdlg", h("h2", "🏞️ ", T("Background")),
      h("div.sb-bggrid",
        h("button.sb-bgtile.none" + (!p.bg ? ".on" : ""), { type: "button", onclick: () => set(null) }, h("span.sb-bgimg"), h("span.small", T("No background"))),
        ...Object.entries(SB_BGS()).map(([k, n]) => h("button.sb-bgtile" + (p.bg === k ? ".on" : ""), { type: "button", onclick: () => set(k) },
          h("span.sb-bgimg", { style: { backgroundImage: `url(${sbBgUrl(k)})` } }), h("span.small", n)))),
      h("div.row", h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
  };

  // ---------- title, cover, language, export, remove
  const metaDialog = () => {
    let emoji = meta.emoji, color = meta.color;
    const title = h("input", { type: "text", maxlength: 80, value: meta.title });
    const lang = h("select", ...I18N.LANGS.filter(([k]) => k !== "auto").map(([k, n]) => h("option", { value: k, translate: "no", selected: k === meta.lang }, n)));
    const own = h("input.sb-ownemo", { type: "text", maxlength: 8, placeholder: "🙂", "aria-label": T("Own emoji") });
    const pick = h("div.sb-emojis"), cols = h("div.sb-colors");
    const drawPick = () => {
      sbSet(pick, ...SB_EMOJI.map(e => h("button.sb-pe" + (e === emoji ? ".on" : ""), { type: "button", translate: "no", onclick: () => { emoji = e; own.value = ""; drawPick(); } }, e)), own);
      sbSet(cols, ...SB_COVERS.map((g, i) => h("button.sb-col" + (i === color ? ".on" : ""), { type: "button", "aria-label": String(i + 1), style: { background: g }, onclick: () => { color = i; drawPick(); } })));
    };
    own.oninput = () => { if (own.value.trim()) emoji = own.value.trim(); };
    drawPick();
    const run = async (path, method, msg, after) => { try { await api(path, { method }); toast(msg, "good"); m.close(); after(); } catch (e) { toast(e.message, "bad"); } };
    const m = modal(h("div.form", h("h2", "⚙️ ", T("Book settings")),
      h("label.field", T("Title"), title), h("div.field", h("b", T("Cover")), pick, cols),
      h("label.field", T("Language of the book"), lang),
      h("div.row", h("button.btn", { onclick: () => {
        if (!title.value.trim()) return title.focus();
        Object.assign(meta, { title: title.value.trim(), emoji, color, lang: lang.value }); m.close(); drawHead(); changed(true);
      } }, "💾 ", T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel"))),
      h("div.row.wrap", h("button.btn.small.ghost", { onclick: async () => { await save(); downloadApi(`stories/${id}/export`, `family-quest-book-${id}.json`); } }, "⬇️ ", T("Export as a file")),
        h("span.small.muted", T("For a backup, another family or an AI – own drawings and photos stay out."))),
      h("div.sb-danger.row.wrap",
        ed.live || ed.pending ? h("button.btn.small.ghost", { onclick: () => confirm(I18N.tr(T("Take the book off the shelf? It stays here as a draft."))) &&
          run(`stories/${id}/unpublish`, "POST", T("The book is a draft again"), async () => { ed = await api("stories/" + id); drawHead(); }) }, "📥 ", T("Unpublish")) : null,
        h("button.btn.small.bad", { onclick: () => confirm(I18N.tr(T("Remove this book for good? This cannot be undone."))) &&
          run(`stories/${id}`, "DELETE", T("Removed"), () => { closed = true; dirty = false; clearTimeout(timer); window.removeEventListener("hashchange", close); full.remove();
            if (!document.querySelector(".sb-full")) document.body.classList.remove("quiz-open"); onClose && onClose(); }) }, "🗑 ", T("Remove book")))), { wide: true });
  };

  document.body.append(full);
  document.body.classList.add("quiz-open");
  setState("saved");
  drawHead(); drawChecker(); drawBody();
}

// ---------------------------------------------------------------- pictures: upload, photos smaller, the painter
async function sbUpload(blob, name) {
  const fd = new FormData();
  fd.append("file", blob, name);
  return api("stories/image", { method: "POST", form: fd });
}

async function sbShrink(file, max = 1024) {
  if (file.type === "image/gif" && file.size < 1.5e6) return file;
  try {
    const bmp = await createImageBitmap(file);
    const k = Math.min(1, max / Math.max(bmp.width, bmp.height));
    const cv = h("canvas", { width: Math.round(bmp.width * k), height: Math.round(bmp.height * k) });
    cv.getContext("2d").drawImage(bmp, 0, 0, cv.width, cv.height);
    return await new Promise(res => cv.toBlob(b => res(b || file), "image/jpeg", 0.85));
  } catch { throw new Error(I18N.tr(T("This photo format cannot be read – please use JPEG or PNG."))); }
}

// a simple painter for finger and stylus: pens, colours, rubber, fill, undo – resolves with a PNG (or null)
function sbPainter(src = null) {
  return new Promise(resolve => {
    const CW = 800, CH = 600;
    const cv = h("canvas.sb-canvas", { width: CW, height: CH });
    const ctx = cv.getContext("2d", { willReadFrequently: true });
    ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, CW, CH);
    if (src) { const img = new Image(); img.onload = () => ctx.drawImage(img, 0, 0, CW, CH); img.src = src; }
    let color = SB_INK[0], size = SB_SIZES[1], tool = "pen", undo = [], cur = null, done = false;
    const snap = () => { undo.push(ctx.getImageData(0, 0, CW, CH)); if (undo.length > 15) undo.shift(); drawBar(); };
    const at = e => { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * CW / r.width, (e.clientY - r.top) * CH / r.height]; };
    const width = e => size * (e.pointerType === "pen" && e.pressure > 0 ? 0.35 + e.pressure * 1.3 : 1);
    cv.addEventListener("pointerdown", e => {
      if (e.button > 0 || cur) return;
      e.preventDefault();
      const [x, y] = at(e);
      snap();
      if (tool === "fill") { sbFlood(ctx, Math.floor(x), Math.floor(y), color); return; }
      cv.setPointerCapture(e.pointerId);
      cur = { id: e.pointerId, x, y };
      ctx.fillStyle = tool === "eraser" ? "#ffffff" : color;
      ctx.beginPath(); ctx.arc(x, y, width(e) / 2, 0, Math.PI * 2); ctx.fill();
    });
    const move = e => {
      if (!cur || e.pointerId !== cur.id) return;
      e.preventDefault();
      for (const ev of (e.getCoalescedEvents ? e.getCoalescedEvents() : null) || [e]) {
        const [x, y] = at(ev);
        ctx.strokeStyle = tool === "eraser" ? "#ffffff" : color; ctx.lineWidth = width(ev); ctx.lineCap = ctx.lineJoin = "round";
        ctx.beginPath(); ctx.moveTo(cur.x, cur.y); ctx.lineTo(x, y); ctx.stroke();
        cur.x = x; cur.y = y;
      }
    };
    cv.addEventListener("pointermove", move);
    const up = e => { if (cur && e.pointerId === cur.id) cur = null; };
    cv.addEventListener("pointerup", up); cv.addEventListener("pointercancel", up);
    const bar = h("div.sb-pbar");
    const drawBar = () => sbSet(bar, 
      h("div.sb-ptools",
        ...[["pen", "✏️", T("Pen")], ["eraser", "🧽", T("Rubber")], ["fill", "🪣", T("Fill")]].map(([k, ic, n]) =>
          h("button.sb-ptool" + (tool === k ? ".on" : ""), { title: n, "aria-label": n, onclick: () => { tool = k; drawBar(); } }, ic)),
        ...SB_SIZES.map(s => h("button.sb-ptool.sb-size" + (size === s && tool !== "fill" ? ".on" : ""), { title: s + " px", "aria-label": s + " px",
          onclick: () => { size = s; if (tool === "fill") tool = "pen"; drawBar(); } }, h("i", { style: { width: Math.min(26, s / 1.6 + 3) + "px", height: Math.min(26, s / 1.6 + 3) + "px" } }))),
        h("button.sb-ptool", { title: T("Undo"), "aria-label": T("Undo"), disabled: !undo.length, onclick: () => { const d = undo.pop(); if (d) ctx.putImageData(d, 0, 0); drawBar(); } }, "↶"),
        h("button.sb-ptool", { title: T("Clear"), "aria-label": T("Clear"), onclick: () => { snap(); ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, CW, CH); } }, "🗑")),
      h("div.sb-pcolors", ...SB_INK.map(c => h("button.sb-pcol" + (c === color ? ".on" : ""), { "aria-label": c, style: { background: c },
        onclick: () => { color = c; if (tool === "eraser") tool = "pen"; drawBar(); } }))));
    drawBar();
    const finish = blob => { if (done) return; done = true; wrap.remove(); window.removeEventListener("hashchange", cancel); resolve(blob); };
    const cancel = () => finish(null);
    window.addEventListener("hashchange", cancel);
    const wrap = h("div.quiz-full.sb-full.sb-painter",
      h("div.sb-erow", h("button.icon-btn", { title: T("Cancel"), "aria-label": T("Cancel"), onclick: cancel }, "✕"), h("strong.grow", "🎨 ", T("Draw a picture")),
        h("button.btn.small", { onclick: () => cv.toBlob(b => finish(b), "image/png") }, "✓ ", T("Use picture"))),
      bar, h("div.sb-cvwrap", cv));
    document.body.append(wrap);
  });
}

// flood fill (scanline) – similar colours count as the same area, so anti-aliased edges fill nicely
function sbFlood(ctx, x0, y0, hex) {
  const { width: W, height: H } = ctx.canvas;
  const img = ctx.getImageData(0, 0, W, H), d = img.data;
  const fill = [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
  const i0 = (y0 * W + x0) * 4, base = [d[i0], d[i0 + 1], d[i0 + 2]];
  if (Math.abs(base[0] - fill[0]) + Math.abs(base[1] - fill[1]) + Math.abs(base[2] - fill[2]) < 12) return;
  const same = i => Math.abs(d[i] - base[0]) + Math.abs(d[i + 1] - base[1]) + Math.abs(d[i + 2] - base[2]) < 90;
  const seen = new Uint8Array(W * H), stack = [[x0, y0]];
  while (stack.length) {
    let [x, y] = stack.pop();
    while (x > 0 && !seen[y * W + x - 1] && same((y * W + x - 1) * 4)) x--;
    let up = false, down = false;
    for (; x < W && !seen[y * W + x] && same((y * W + x) * 4); x++) {
      const k = y * W + x, i = k * 4;
      seen[k] = 1; d[i] = fill[0]; d[i + 1] = fill[1]; d[i + 2] = fill[2]; d[i + 3] = 255;
      if (y > 0) { const ok = !seen[k - W] && same(i - W * 4); if (ok && !up) stack.push([x, y - 1]); up = ok; }
      if (y < H - 1) { const ok = !seen[k + W] && same(i + W * 4); if (ok && !down) stack.push([x, y + 1]); down = ok; }
    }
  }
  ctx.putImageData(img, 0, 0);
}
