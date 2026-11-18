// ---------------------------------------------------------------- My adventure books (familyquest/stories.py)
// Children and parents write branching stories (scenes with 2–4 choices, good and bad endings, items), the family reads
// them on the shelf. storyShelf(box) draws the family bookshelf with every book type (📕 picture books: picturebook.js,
// 📖 adventure books, 🗝️ adventure games: adventure.js) and the sample books (kid app #/stories, parent area › Family),
// storyReader() reads a book (on the server – or a try-out of the working copy right here), storyEditor() writes one.
"use strict";

const SB_COVERS = ["linear-gradient(135deg,#5b5bd6,#8f6bf0)", "linear-gradient(135deg,#e8590c,#f59f00)", "linear-gradient(135deg,#d6336c,#f783ac)",
  "linear-gradient(135deg,#2f9e44,#94d82d)", "linear-gradient(135deg,#0c8599,#3bc9db)", "linear-gradient(135deg,#1c2a6b,#5c7cfa)",
  "linear-gradient(135deg,#7c4a1e,#d9a35b)", "linear-gradient(135deg,#343a40,#868e96)"];
const SB_EMOJI = ["📖", "🦁", "🚀", "🏰", "🐠", "🐉", "🧙", "🏴‍☠️", "🦄", "🌋", "🤖", "👻", "🦖", "🧚", "🕵️", "⚽"];
const SB_PICS = ["🌴", "🦁", "🐒", "🐍", "🐊", "🦜", "🐘", "🦒", "🌳", "🌊", "🏝️", "⛰️", "🌋", "🏜️", "🌲", "🏞️",
  "🚀", "🌕", "⭐", "👽", "🛸", "🪐", "🌌", "☄️", "🏰", "👻", "🦇", "🕯️", "🗝️", "📚", "🧙", "🐉",
  "🐠", "🐙", "🐢", "🦈", "🧜", "🪸", "🐚", "⚓", "🏠", "🏫", "🚗", "🚂", "🍌", "🍎", "🎁", "💎",
  "👑", "🗺️", "💰", "🍫", "🌈", "⛈️", "🌙", "🔥", "😀", "😱", "😴", "🤩", "🙈", "🏆", "💀", "❓"];
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
// the CSS background of a page: a library scene (its key) or an own drawing {k: "svg", v} (always as an image: nothing in it runs)
const sbBgCss = (bg, game = false) => !bg ? null : typeof bg === "object" ? (bg.k === "svg" ? `url("${svgDataUrl(bg.v)}")` : null)
  : `url(${game ? agBgUrl(bg) : sbBgUrl(bg)})`;
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
  if (pic && pic.k === "svg") return h("img.sb-img.sb-svg" + cls, { src: svgDataUrl(pic.v), alt: "", draggable: false });
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
// the number of the page a choice leads to, in the purple circle of the page cards («?»: no target yet)
const sbTargetNum = n => h("span.sb-pnum.sb-tnum" + (n ? "" : ".none"), { title: n ? sbFmt(T("Goes to page {0}"), n) : T("No page chosen yet"),
  "aria-label": n ? sbFmt(T("Goes to page {0}"), n) : T("No page chosen yet") }, n ? String(n) : "?");

// ---------------------------------------------------------------- kid app: #/stories
async function storiesView() {
  const box = h("div.sb-wrap");
  screen("stories", { back: () => go("") }, h("h1", "📚 ", T("Library")), box);
  await storyShelf(box, { types: LIBRARY_TYPES });
}
// the library: books and adventure books – the adventure games are a game of their own (kid app › Games, parent area › Games)
const LIBRARY_TYPES = ["picture", "adventure"];

// kid app #/advgames: the shelf of the adventure games (from the games page)
async function adventureGamesView() {
  const box = h("div.sb-wrap");
  screen("advgames", { back: () => go("games") }, h("h1", "🗝️ ", T("Adventure games")), box);
  await storyShelf(box, { types: ["game"] });
}

// the card on the games page of the kid app
function adventureGamesCard() {
  return h("section.card.sb-famcard.sb-gamecard", h("div.row", h("span.sb-famic", "🗝️"),
    h("div.grow", h("strong", T("Adventure games")), h("div.small.muted", T("Point & click: rooms, things to find, riddles – play the games of the family or make your own."))),
    h("button.btn", { onclick: () => go("advgames") }, T("Open"))));
}

// the card on the Family page of the kid app
function storiesCard() {
  return h("section.card.sb-famcard", h("div.row", h("span.sb-famic", "📚"),
    h("div.grow", h("strong", T("Library")), h("div.small.muted", T("Books and adventure books: write your own and read the books of the family."))),
    h("button.btn", { onclick: () => go("stories") }, T("Open"))));
}

// parent area › Family: the shelf, books waiting for approval and the settings (⚙️)
async function storiesSection() {
  const sec = h("section.card.sec.sb-psec");
  const box = h("div.sb-wrap");
  const set = h("details.sb-settings", h("summary", "⚙️ ", T("Settings for the bookshelf")));
  set.addEventListener("toggle", () => { if (set.open && !set.dataset.done) { set.dataset.done = "1"; storiesSettings(set); } });
  sec.append(h("h2", "📚 ", T("Library")),
    h("p.small.muted", T("Children and parents write books and choose-your-path stories, the whole family reads them. Parents can edit, unpublish and remove every book except the private ones. The adventure games are under Games.")),
    box, set);
  await storyShelf(box, { byType: true, types: LIBRARY_TYPES });   // one box per type, each with its own import / new
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
  const sample = h("input", { type: "checkbox", checked: !(s.samples_off || []).includes("dwarf") });
  const num = v => h("input", { type: "number", min: 0, max: 10000, value: v, inputmode: "numeric" });
  const f = { write_coins: num(s.write_coins), write_xp: num(s.write_xp), read_coins: num(s.read_coins), read_xp: num(s.read_xp) };
  const save = async () => {
    const out = { off: on.filter(([, c]) => !c.checked).map(([id]) => id), approval: appr.checked, samples_off: sample.checked ? [] : ["dwarf"] };
    for (const [k, el] of Object.entries(f)) out[k] = Math.max(0, Math.min(10000, Math.round(+el.value || 0)));
    try { await api("stories/settings", { method: "PUT", body: out }); toast(T("Saved"), "good"); } catch (e) { toast(e.message, "bad"); }
  };
  sbSet(body,
    h("div.field", h("b", T("Bookshelf for")), kids.length ? h("div.row.wrap", ...on.map(([id, c]) => h("label.check", c, " ", C(kids.find(k => k.id === id).name)))) : h("span.small.muted", T("No child profile yet"))),
    h("label.check", appr, " ", T("Books need a parent's approval before the family sees them")),
    h("label.check", sample, " ", T("Show the sample book of Family Quest on the shelf")),
    h("div.sb-rew", h("b", T("Reward for every published book")),
      h("label.field", h("span", "🪙 ", T("Coins")), f.write_coins), h("label.field", h("span", "⭐ XP"), f.write_xp)),
    h("div.sb-rew", h("b", T("Reward when somebody else reads it to an end (once per reader)")),
      h("label.field", h("span", "🪙 ", T("Coins")), f.read_coins), h("label.field", h("span", "⭐ XP"), f.read_xp)),
    h("button.btn", { onclick: save }, "💾 ", T("Save")));
}

// ---------------------------------------------------------------- the shelf: 📕 picture books, 📖 adventure books, 🗝️ adventure games (later)
// book types (stories.py TYPES): icon, name, plural, what it is
const SB_TYPES = () => ({
  picture: ["📕", T("Book"), T("Books"), T("Pages with a picture and a text, read page by page.")],
  adventure: ["📖", T("Adventure book"), T("Adventure books"), T("Choose-your-path: choices, good and bad endings.")],
  game: ["🗝️", T("Adventure game"), T("Adventure games"), T("Point & click: rooms, things to find, riddles and characters.")] });
const sbType = b => SB_TYPES()[b.type] || SB_TYPES().adventure;
const sbOpen = (b, onClose) => b.type === "picture" ? pictureReader(pbServerEngine(b.id), { onClose })
  : b.type === "game" ? gamePlayer(agServerEngine(b.id), { onClose }) : storyReader(sbServerEngine(b.id), { onClose });
const sbEdit = (id, type, onClose) => type === "picture" ? pictureEditor(id, onClose) : type === "game" ? gameEditor(id, onClose) : storyEditor(id, onClose);
const sbSize = b => sbFmt(b.type === "game" ? T("Rooms: {0}") : T("Pages: {0}"), b.pages);

async function storyShelf(box, opts = {}) {
  let filter = "all";
  try { filter = localStorage.getItem("fq.sb.type") || "all"; } catch {}
  const draw = async () => {
    let d;
    try { d = await api("stories?lang=" + encodeURIComponent(sbAppLang())); } catch (e) { return sbSet(box, h("p.bad", e.message)); }
    // `opts.types`: only these book types (the library: books and adventure books; the games: adventure games)
    const types = (opts.types || ["picture", "adventure", "game"]).filter(k => (d.types || ["picture", "adventure", "game"]).includes(k));
    const ofTypes = b => types.includes(b.type);
    const books = d.books.filter(ofTypes), samples = (d.samples || []).filter(ofTypes);
    d = { ...d, creatable: (d.creatable || []).filter(k => types.includes(k)), private: (d.private || []).filter(ofTypes) };
    if (!SB_TYPES()[filter] || !types.includes(filter) || types.length === 1) filter = "all";
    const ofType = b => filter === "all" || b.type === filter;
    const onShelf = [...books.filter(b => b.live), ...samples.filter(b => !b.hidden)];
    const live = onShelf.filter(ofType), mine = books.filter(b => b.mine);
    const others = d.oversee ? books.filter(b => !b.mine && !b.live) : [];
    const pend = d.oversee ? books.filter(b => b.pending) : [];
    const read = b => sbOpen(b, draw);
    const visBadge = b => { const [ic, n] = SB_VIS()[b.visibility] || SB_VIS().me; return h("span.sb-vis", { title: n, "aria-label": n }, ic); };
    const typeBadge = b => h("span.sb-type", { title: sbType(b)[1], "aria-label": sbType(b)[1] }, sbType(b)[0]);
    const author = b => b.sample ? h("span.sb-by", h("span.sb-fq", "✨"), C(b.author.name)) : h("span.sb-by", avatarSvg(b.author.avatar, 22), C(b.author.name));
    const progress = b => b.type === "picture"
      ? h("span.sb-found" + (b.finished ? ".all" : ""), b.finished ? ["✅ ", T("Read")] : b.at ? ["📄 ", sbFmt(T("Page {0} of {1}"), b.at, b.pages)] : ["📄 ", sbFmt(T("Pages: {0}"), b.pages)])
      : h("span.sb-found" + (b.found && b.found === b.endings ? ".all" : ""), "🏁 ", sbFmt(T("{0} of {1} endings found"), b.found, b.endings));
    const coverArt = b => b.type === "picture" || b.type === "game"
      ? (b.cover ? pbPic(b.cover, ".pb-cimg") : h("span.sb-cemo", { translate: "no" }, b.emoji))
      : (b.cover ? sbPic(b.cover) : h("span.sb-cemo", { translate: "no" }, b.emoji));
    const cover = b => h("button.sb-book.t-" + b.type, { onclick: () => read(b), style: { "--sb-c": SB_COVERS[b.color] || SB_COVERS[0] } },
      h("span.sb-cover", { style: b.cover_bg && (!b.cover || (b.type === "adventure" && b.cover.k !== "img")) ? { backgroundImage: sbBgCss(b.cover_bg, b.type === "game") } : null },
        coverArt(b), b.reading ? h("span.sb-cont", "▶ ", T("Continue")) : null, typeBadge(b), b.sample ? null : visBadge(b)),
      h("span.sb-binfo", C(b.title, "strong.sb-btitle"), author(b), progress(b),
        b.rating ? h("span.sb-rate", { title: sbFmt(T("Ratings: {0}"), b.votes) }, stars(Math.round(b.rating)), " ", fmt(b.rating, 1)) : null));
    const status = b => [!b.live && !b.pending ? h("span.sb-st", "📝 ", T("Draft")) : null,
      b.pending ? h("span.sb-st.wait", "⏳ ", T("Waiting for approval")) : null,
      b.live ? h("span.sb-st.ok", "✅ ", T("On the shelf")) : null,
      b.changed ? h("span.sb-st", "✏️ ", T("Changes not published yet")) : null,
      h("span.sb-st", SB_VIS()[b.visibility][0], " ", SB_VIS()[b.visibility][1])];
    const rowIcon = b => h("span.sb-rowic", { style: { background: SB_COVERS[b.color] || SB_COVERS[0] }, translate: "no" }, b.emoji, h("span.sb-rowtype", sbType(b)[0]));
    const row = b => h("div.sb-row",
      rowIcon(b),
      h("div.grow.sb-rowtt", C(b.title, "strong"), h("div.sb-chips", ...status(b),
        h("span.small.muted", sbType(b)[1], " · ", sbSize(b), b.mine ? "" : [" · ", C(b.author.name)]))),
      h("div.sb-rowbtn", b.live ? h("button.btn.small.ghost", { title: T("Read"), onclick: () => read(b) }, sbType(b)[0]) : null,
        b.edit ? h("button.btn.small", { onclick: () => sbEdit(b.id, b.type, draw) }, "✏️ ", T("Edit")) : null));
    // a private book of somebody else (parent area only): that it exists – no title, no content
    const privRow = b => h("div.sb-row.sb-priv",
      h("span.sb-rowic", "🔒", h("span.sb-rowtype", (SB_TYPES()[b.type] || SB_TYPES().adventure)[0])),
      h("div.grow.sb-rowtt", h("strong", b.type === "picture" ? T("Private book") : b.type === "game" ? T("Private adventure game") : T("Private adventure book")), h("div.sb-chips",
        h("span.sb-by", avatarSvg(b.author.avatar, 22), C(b.author.name)),
        h("span.small.muted", sbSize(b), " · ", fmtDate(b.updated_at)))));
    const preview = async b => {
      if (b.type === "game") return gamePlayer(agTryEngine(b.id, { pending: true }), { preview: true });
      try {
        const e = await api("stories/" + b.id), book = { ...e, data: e.pending || e.data };
        if (e.type === "picture") pictureReader(pbLocalEngine(book), { preview: true }); else storyReader(sbLocalEngine(book), { preview: true });
      } catch (er) { toast(er.message, "bad"); }
    };
    const approveRow = b => h("div.sb-row.sb-pend",
      rowIcon(b),
      h("div.grow.sb-rowtt", C(b.title, "strong"), h("div.sb-chips", h("span.small.muted", C(b.author.name)), visBadge(b))),
      h("div.sb-rowbtn",
        h("button.btn.small.ghost", { onclick: () => preview(b) }, "👀 ", T("Read")),
        h("button.btn.small.good", { onclick: () => act(`stories/${b.id}/approve`, T("Approved – the others can read it now")) }, "✓ ", T("Approve")),
        h("button.btn.small.ghost", { onclick: () => confirm(I18N.tr(T("Send the book back as a draft?"))) && act(`stories/${b.id}/reject`, T("Back to a draft")) }, "✗")));
    // parent area: the sample books of the app – take them off the shelf or put them back
    const sampleRow = b => h("div.sb-row" + (b.hidden ? ".sb-hidden" : ""),
      rowIcon(b),
      h("div.grow.sb-rowtt", C(b.title, "strong"), h("div.sb-chips", h("span.sb-st", "✨ ", T("Sample book")),
        b.hidden ? h("span.sb-st", "🙈 ", T("Hidden")) : h("span.sb-st.ok", "✅ ", T("On the shelf")))),
      h("div.sb-rowbtn", h("button.btn.small.ghost", { title: T("Read"), onclick: () => read(b) }, sbType(b)[0]),
        h("button.btn.small" + (b.hidden ? "" : ".ghost"), { onclick: async () => {
          try { await api("stories/samples/" + b.sample, { method: "PUT", body: { hidden: !b.hidden } }); draw(); } catch (e) { toast(e.message, "bad"); } } },
        b.hidden ? ["👀 ", T("Show again")] : ["🙈 ", T("Hide")])));
    const act = async (path, msg) => { try { await api(path, { method: "POST" }); toast(msg, "good"); draw(); } catch (e) { toast(e.message, "bad"); } };
    const chip = (k, ic, label, n, off = false) => h("button.sb-tchip" + (filter === k ? ".on" : "") + (off ? ".soon" : ""), { type: "button", disabled: off,
      title: off ? I18N.tr(T("Coming soon")) : null, onclick: () => { filter = k; try { localStorage.setItem("fq.sb.type", k); } catch {} draw(); } },
      h("span", { translate: "no" }, ic), " ", label, off ? h("small", " · ", T("soon")) : h("small.sb-tn", String(n)));
    const count = k => onShelf.filter(b => k === "all" || b.type === k).length;
    const T_ = SB_TYPES();
    const filters = h("div.sb-tfilter", { role: "group", "aria-label": T("Book types") },
      chip("all", "📚", T("All"), count("all")),
      ...types.map(k => chip(k, T_[k][0], T_[k][2], count(k), !(d.creatable || []).includes(k))));
    const done = (id, type) => sbEdit(id, type, draw);
    // parent area: a box per type – 📕 books, 📖 adventure books, 🗝️ adventure games – each with its own import and new
    const typeBox = k => {
      const [ic, , plural, what] = T_[k], on = (d.creatable || []).includes(k);
      const shelf = onShelf.filter(b => b.type === k), own = mine.filter(b => b.type === k), fam = others.filter(b => b.type === k);
      return h("section.sb-sec.sb-typebox.t-" + k,
        h("div.sec-head", h("h2", h("span", { translate: "no" }, ic), " ", plural),
          on ? h("div.head-actions",
            h("button.btn.ghost", { onclick: () => storyImportDialog(done, k) }, "📥 ", T("Import")),
            h("button.btn", { onclick: () => storyNewDialog(done, d.creatable, k) }, "+ ", T("New"))) : null),
        h("p.small.muted", what),
        shelf.length ? h("div.sb-shelf", ...shelf.map(cover)) : h("p.small.muted.sb-empty", T("Nothing on the shelf yet.")),
        own.length ? [h("h3.sb-sub", "✏️ ", T("Mine")), h("div.sb-rows", ...own.map(row))] : null,
        fam.length ? [h("h3.sb-sub", "📝 ", T("Drafts of the family")), h("div.sb-rows", ...fam.map(row))] : null);
    };
    // parent area › Games › Adventure games: Import / New in `opts.actions`, then one list – waiting, every game, private ones
    if (opts.actions) {
      const on = (d.creatable || []).includes(types[0]);
      sbSet(opts.actions, on ? [h("button.btn.ghost", { onclick: () => storyImportDialog(done, types[0]) }, "📥 ", T("Import")),
        h("button.btn", { onclick: () => storyNewDialog(done, d.creatable, types[0]) }, "+ ", T("New"))] : null);
      const all = [...onShelf, ...mine, ...others].filter((b, i, a) => !b.sample && a.indexOf(b) === i);
      if (opts.onCount) opts.onCount(all.length + d.private.length);
      return sbSet(box,
        pend.length ? h("section.sb-sec.sb-wait", h("h3.sb-sub", "⏳ ", T("Waiting for approval")), ...pend.map(approveRow)) : null,
        all.length || d.private.length ? h("div.sb-rows", ...all.map(row), ...d.private.map(privRow)) : h("p.small.muted.sb-empty", T("Nothing here yet – start with «+ New».")));
    }
    if (opts.byType) return sbSet(box,
      pend.length ? h("section.sb-sec.sb-wait", h("h2", "⏳ ", T("Waiting for approval")), ...pend.map(approveRow)) : null,
      ...types.map(typeBox),
      d.oversee && samples.length ? h("section.sb-sec", h("h2", "✨ ", T("Sample books")),
        h("p.small.muted", T("Ready-made books of Family Quest for the whole family, in the language of the app. Hide them if you do not want them on the shelf.")),
        h("div.sb-rows", ...samples.map(sampleRow))) : null,
      (d.private || []).length ? h("section.sb-sec", h("h2", "🔒 ", T("Private books")),
        h("p.small.muted", T("Only their authors can read these books – parents neither. You see only that they exist.")),
        h("div.sb-rows", ...d.private.map(privRow))) : null);
    const one = types.length === 1 ? types[0] : null;       // a shelf of one type: no filter chips, import / new for that type
    sbSet(box,
      pend.length ? h("section.sb-sec.sb-wait", h("h2", "⏳ ", T("Waiting for approval")), ...pend.map(approveRow)) : null,
      h("section.sb-sec", h("div.sec-head", h("h2", one ? ["📚 ", T("On the shelf")] : ["📚 ", T("Family bookshelf")]),
        (d.creatable || []).length ? h("div.head-actions", h("button.btn.ghost", { onclick: () => storyImportDialog(done, one, types) }, "📥 ", T("Import")),
          h("button.btn", { onclick: () => storyNewDialog(done, d.creatable, one) }, "+ ", one ? T("New") : T("New book"))) : null),
        one ? null : filters,
        live.length ? h("div.sb-shelf", ...live.map(cover))
          : h("p.muted", one === "game" ? T("No adventure games on the shelf yet – make the first one!") : filter === "all" ? T("No books on the shelf yet – write the first one!") : T("No books of this type on the shelf yet."))),
      h("section.sb-sec", h("h2", "✏️ ", one === "game" ? T("My adventure games") : T("My books")),
        mine.length ? h("div.sb-rows", ...mine.map(row))
          : h("p.small.muted", one === "game" ? T("Make your own adventure game – or start with a template.") : T("Write your own book or adventure – or start with a template.")),
        d.rewards.write_coins || d.rewards.write_xp ? h("p.small.muted.sb-rewhint", "🎁 ", sbFmt(T("Every book the others can read: {0}"),
          [d.rewards.write_coins ? d.rewards.write_coins + " 🪙" : "", d.rewards.write_xp ? d.rewards.write_xp + " XP" : ""].filter(Boolean).join(" + "))) : null),
      others.length ? h("section.sb-sec", h("h2", "📝 ", T("Drafts of the family")), h("div.sb-rows", ...others.map(row))) : null,
      d.oversee && samples.length ? h("section.sb-sec", h("h2", "✨ ", T("Sample books")),
        h("p.small.muted", T("Ready-made books of Family Quest for the whole family, in the language of the app. Hide them if you do not want them on the shelf.")),
        h("div.sb-rows", ...samples.map(sampleRow))) : null,
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

function storyNewDialog(done, creatable = ["picture", "adventure", "game"], fixedType = null) {
  let type = "picture", tpl = null, emoji = "📖", color = 0, visibility = "family";   // new books: the whole family
  try { type = ["adventure", "game"].includes(localStorage.getItem("fq.sb.newtype")) ? localStorage.getItem("fq.sb.newtype") : "picture"; } catch {}
  if (fixedType) type = fixedType;                       // parent area: the box of a type – no choice needed
  if (!creatable.includes(type)) type = "picture";
  const title = h("input", { type: "text", maxlength: 80 });
  const lang = h("select", ...I18N.LANGS.filter(([k]) => k !== "auto").map(([k, n]) => h("option", { value: k, translate: "no", selected: k === sbAppLang() }, n)));
  const types = h("div.sb-newtypes"), tiles = h("div.sb-tpls"), tplField = h("div.field", h("b", T("Start with")), tiles);
  const titleHint = h("span.hint", T("With a template you may leave it empty – the template has one."));
  const drawTypes = () => {
    sbSet(types, ...Object.entries(SB_TYPES()).filter(([k]) => creatable.includes(k)).map(([k, [ic, n, , what]]) => {
      const off = !creatable.includes(k);
      return h("button.sb-newtype" + (type === k ? ".on" : "") + (off ? ".soon" : ""), { type: "button", disabled: off,
        onclick: () => { type = k; tpl = null; try { localStorage.setItem("fq.sb.newtype", k); } catch {} drawTypes(); drawTiles(); } },
        h("span.sb-newic", { translate: "no" }, ic), h("span.sb-newtx", h("b", n), h("span.small.muted", what)));
    }));
    tplField.hidden = type === "picture"; titleHint.hidden = type === "picture";
    title.placeholder = I18N.tr(type === "picture" ? T("e.g. The bear who could not sleep") : type === "game" ? T("e.g. Escape from the haunted castle") : T("e.g. The secret cave"));
  };
  const drawTiles = async () => {
    if (type === "picture") return;
    let list = [];
    try { list = await api("stories/templates?type=" + type + "&lang=" + encodeURIComponent(lang.value)); } catch {}
    const tile = (key, ic, name, c) => h("button.sb-tpl" + (tpl === key ? ".on" : ""), { type: "button", style: { "--sb-c": SB_COVERS[c] },
      onclick: () => { tpl = key; drawTiles(); } }, h("span.sb-tplic", ic), key ? C(name, "span") : h("span", name));
    sbSet(tiles, tile(null, "📄", type === "game" ? T("Empty game") : T("Empty book"), 0), ...list.map(t => tile(t.key, t.emoji, t.title, t.color)));
  };
  lang.onchange = drawTiles;
  drawTypes(); drawTiles();
  const create = async () => {
    if (!(type !== "picture" && tpl) && !title.value.trim()) return title.focus();
    try {
      const r = await api("stories", { method: "POST", body: { title: title.value.trim(), lang: lang.value, template: type !== "picture" ? tpl : null,
        emoji: type === "picture" ? "📕" : type === "game" ? "🗝️" : emoji, color, visibility, type } });
      m.close(); done(r.id, type);
    } catch (e) { toast(e.message, "bad"); }
  };
  const heading = fixedType ? { picture: ["📕", T("New book")], adventure: ["📖", T("New adventure book")], game: ["🗝️", T("New adventure game")] }[type]
    : ["📚", T("New book")];
  const m = modal(h("div.form.sb-new", h("h2", heading[0], " ", heading[1]),
    fixedType ? null : h("div.field", h("b", T("What kind of book?")), types),
    fixedType ? tplField : null,                         // one type only: the templates first
    h("label.field", T("Title"), title, titleHint),
    h("label.field", T("Language of the book"), lang),
    fixedType ? null : tplField,
    h("div.field", h("b", T("Who can read it?")), sbVisPicker(visibility, v => { visibility = v; })),
    h("div.row", h("button.btn", { onclick: create }, "✏️ ", T("Start writing")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
}

// import: a file or the answer of an AI (paste) – becomes a private draft (picture books and adventure books)
function storyImportDialog(done, fixedType = null, kinds = ["picture", "adventure", "game"]) {
  let type = "picture";
  try { type = ["adventure", "game"].includes(localStorage.getItem("fq.sb.newtype")) ? localStorage.getItem("fq.sb.newtype") : "picture"; } catch {}
  if (!kinds.includes(type)) type = kinds[0];
  if (fixedType) type = fixedType;                       // parent area: the box of a type – its template only
  const text = h("textarea.sb-imptext", { rows: 8, placeholder: I18N.tr(T("Paste the answer of the AI here …")) });
  const file = h("input", { type: "file", accept: ".json,.txt,application/json,text/plain" });
  file.onchange = async () => { const f = file.files[0]; if (!f) return; if (f.size > 1e6) return toast(I18N.tr(T("The file is too large")), "bad"); text.value = await f.text(); };
  const tplUrl = () => "api/stories/ai-template" + (type === "adventure" ? "" : "?type=" + type);
  const tplName = () => type === "picture" ? "family-quest-picturebook-template.json" : type === "game" ? "family-quest-adventuregame-template.json" : "family-quest-story-template.json";
  const go = async () => {
    try {
      const r = await api("stories/import", { method: "POST", body: { text: text.value } });
      m.close(); toast(I18N.tr(T("Imported as a private draft")), "good");
      const e = await api("stories/" + r.ids[0]);
      if (fixedType && e.type !== fixedType) toast(sbFmt(T("This file is: {0} – it was added there."), SB_TYPES()[e.type][1]), "good");
      done(r.ids[0], e.type);
    } catch (e) { toast(e.message, "bad"); }
  };
  const tpls = h("div");
  const drawTpl = () => sbSet(tpls,
    fixedType ? null : h("div.sb-segs.sb-impsegs", ...kinds.map(k => h("button.sb-seg" + (type === k ? ".on" : ""), { type: "button", title: SB_TYPES()[k][1],
      onclick: () => { type = k; drawTpl(); } }, SB_TYPES()[k][0], h("span.sb-hide-s", " ", SB_TYPES()[k][1])))),
    aiPromptBox({ picture: T("Write a picture book for a child aged [5].\nStory idea: [e.g. a little fox who is afraid of the dark]\nAbout [8] pages, language: [English]."),
      adventure: T("Write an adventure book with choices for children aged [8 to 10].\nStory idea: [e.g. a secret door in grandma's attic]\nAbout [15] pages with [3] different endings, language: [English]."),
      game: T("Make an adventure game for children aged [8 to 12].\nStory idea: [e.g. the lost treasure in the old castle]\n[4] rooms with doors, objects and characters, a small puzzle in each room, language: [English].") }[type],
      { template: tplUrl(), name: tplName() }));
  drawTpl();
  const impHead = fixedType ? { picture: T("Import a book"), adventure: T("Import an adventure book"), game: T("Import an adventure game") }[type] : T("Import a book");
  const m = modal(h("div.form.sb-imp", h("h2", "📥 ", impHead),
    h("p.small", T("1. Copy the prompt (the template comes with it) and paste it into any AI chat. 2. Fill in the highlighted parts with your story idea. 3. Paste the answer here – or choose a book file that was exported.")),
    tpls, text, h("label.field", T("…or a file"), file),
    h("p.small.muted", "🔒 ", T("The book comes in as a private draft – the checker shows what is still missing. Own drawings come along, photos are not part of the file.")),
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
        p.pic || p.bg ? h("div.sb-ppic" + (p.bg ? ".bg" : ""), { style: p.bg ? { backgroundImage: sbBgCss(p.bg) } : null }, sbPic(p.pic)) : null,
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
      ed.pending ? h("p.sb-note", "⏳ ", ed.parent ? T("This book waits for a parent's approval (Family › Library).") : T("Your book waits for a parent's approval.")) : null,
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
          h("button.sb-picbtn" + (p.bg ? ".bg" : ""), { title: T("Picture"), onclick: () => picDialog(p), style: p.bg ? { backgroundImage: sbBgCss(p.bg) } : null },
            p.pic ? sbPic(p.pic) : h("span.sb-nopic", "🖼️", h("span.small", T("Picture")))),
          h("button.btn.small.ghost.sb-bgbtn", { onclick: () => bgDialog(p), title: p.bg ? (typeof p.bg === "string" ? SB_BGS()[p.bg] : I18N.tr(T("Own background"))) : T("Background") }, "🏞️ ", h("span.small", T("Background")))),
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
        h("div.sb-cfields", t, h("div.sb-csel", sbTargetNum(c.to && byId(c.to) ? num(c.to) : null), targetSelect(p, c),
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
      const g = S_("g", { class: cls, transform: `translate(${a.x} ${a.y})`, tabindex: 0, role: "button", "aria-label": sbFmt(T("Page {0}"), num(p.id)) });
      g.addEventListener("click", () => goPage(p.id));
      g.addEventListener("keydown", e => { if (e.key === "Enter") goPage(p.id); });
      const pic = p.pic && p.pic.k === "emoji" ? p.pic.v : p.pic ? "🖼️" : SB_KIND()[p.kind][0];
      g.append(S_("rect", { width: W, height: H, rx: 12 }),
        S_("circle", { cx: 22, cy: 20, r: 13, class: "sb-nnumc" }),          // the page number in the purple circle (like the cards)
        S_("text", { x: 22, y: 20, class: "sb-nnum", "text-anchor": "middle", "dominant-baseline": "central" }, String(num(p.id))),
        S_("text", { x: 40, y: 25, class: "sb-nstar" }, p.id === data.start ? "⭐" : ""),
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
          const svg = await svgPaint({ kind: "art", svg: p.pic && p.pic.k === "svg" ? p.pic.v : null });
          if (svg) { p.pic = { k: "svg", v: svg }; changed(true); }
        } }, p.pic && p.pic.k === "svg" ? ["✏️ ", T("Change drawing")] : ["🎨 ", T("Draw a thing")]),
        h("button.btn.ghost", { onclick: () => file.click() }, "📷 ", T("Photo")), file,
        p.pic ? h("button.btn.ghost", { onclick: () => set(null) }, "🗑 ", T("No picture")) : null,
        h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
  };

  // ---------- backgrounds: library scenes or an own drawing behind the picture
  const bgDialog = p => {
    const set = bg => { p.bg = bg; m.close(); changed(true); };
    const own = p.bg && typeof p.bg === "object" ? p.bg : null;
    const draw = async () => { m.close(); const svg = await svgPaint({ kind: "bg", svg: own ? own.v : null }); if (svg) { p.bg = { k: "svg", v: svg }; changed(true); } };
    const m = modal(h("div.form.sb-bgdlg", h("h2", "🏞️ ", T("Background")),
      h("div.sb-bggrid",
        h("button.sb-bgtile.own" + (own ? ".on" : ""), { type: "button", onclick: draw },
          h("span.sb-bgimg", { style: own ? { backgroundImage: sbBgCss(own) } : null }, own ? null : "🎨"), h("span.small", own ? T("Change drawing") : T("Draw own background"))),
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
        h("span.small.muted", T("For a backup, another family or an AI – own drawings go along, photos stay out."))),
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

// ---------------------------------------------------------------- pictures: upload, photos smaller (drawings: svgpaint.js)
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
