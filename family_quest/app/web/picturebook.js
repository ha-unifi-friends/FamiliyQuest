// ---------------------------------------------------------------- 📕 Picture books (familyquest/picturebooks.py)
// Pages with a picture and a text, read page by page. The shelf, visibility, approval and pictures upload are the ones of
// the adventure books (stories.js). pictureReader() turns the pages (buttons, swipe, arrow keys), pictureEditor() writes
// a book (cover, pages with three layouts, pictures from the library, emoji, painter, photo or own SVG code).
"use strict";

// layouts of a page (picturebooks.py LAYOUTS)
const PB_LAYOUTS = () => ({ top: ["🖼️", T("Picture on top")], full: ["🌄", T("Full-page picture")], text: ["📝", T("Text only")] });
const PB_MSG = { title: T("Give the book a title"), empty: T("The book has no pages yet"), no_text: T("Page {0} has no text yet"),
  no_pic: T("Page {0} has no picture yet") };
const PB_TEXT = 600, PB_MAX_PAGES = 60;

// a picture of a page: library scene, own SVG (always as an <img>, so nothing in it can run), drawing / photo, emoji
function pbPic(pic, cls = "") {
  if (!pic) return null;
  if (pic.k === "svg") return h("img.pb-img" + cls, { src: "data:image/svg+xml;charset=utf-8," + encodeURIComponent(pic.v), alt: "", draggable: false });
  if (pic.k === "lib") return h("img.pb-img" + cls, { src: sbBgUrl(pic.v), alt: "", draggable: false });
  if (pic.k === "img") return h("img.pb-img.pb-photo" + cls, { src: sbImg(pic.v), alt: "", draggable: false, loading: "lazy" });
  if (pic.k === "emoji") return h("span.pb-emo" + cls, { translate: "no", "aria-hidden": "true" }, pic.v);
  return null;
}

function pbCheck(data, title) {
  const out = [], add = (code, page, ...args) => out.push({ code, page, msg: PB_MSG[code], args: args.map(String) });
  if (!String(title || "").trim()) add("title", null);
  const pages = data.pages || [];
  if (!pages.length) add("empty", null);
  pages.forEach((p, i) => {
    if (!(p.text || "").trim() && (p.layout === "text" || !p.pic)) add("no_text", p.id, i + 1);
    if (p.layout !== "text" && !p.pic) add("no_pic", p.id, i + 1);
  });
  return out;
}

// ---------------------------------------------------------------- reading
function pbServerEngine(id) {
  const lang = "?lang=" + encodeURIComponent(sbAppLang());
  return { read: () => api(`stories/${id}/read${lang}`), restart: () => api(`stories/${id}/read/restart${lang}`, { method: "POST" }),
    turn: page => api(`stories/${id}/read/page`, { method: "POST", body: { page } }), rate: n => api(`stories/${id}/rate`, { method: "POST", body: { stars: n } }) };
}

// a try-out of a working copy (editor ▶, a book waiting for approval): nothing is saved
function pbLocalEngine(book) {
  const view = { type: "picture", title: book.title, emoji: book.emoji, color: book.color, lang: book.lang, author: book.author || "",
    cover: (book.data.cover || {}).pic, pages: book.data.pages, at: 0, finished: 0, rating: null, may_rate: false };
  return { read: async () => view, restart: async () => ({ ...view, at: 0 }), turn: async page => ({ at: page, finished: 0, may_rate: false }), rate: async () => {} };
}

function pictureReader(engine, { onClose = null, preview = false } = {}) {
  const full = h("div.quiz-full.sb-full.pb-reader");
  let st = null, at = 0, closed = false, dir = 0;
  const close = () => {
    if (closed) return; closed = true;
    full.remove(); window.removeEventListener("hashchange", close); document.removeEventListener("keydown", key);
    if (!document.querySelector(".sb-full")) document.body.classList.remove("quiz-open");
    onClose && onClose();
  };
  const key = e => {
    if (!st || document.querySelector(".modal-back")) return;
    if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); go(at + 1); }
    else if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); go(at - 1); }
    else if (e.key === "Escape") close();
  };
  window.addEventListener("hashchange", close);
  document.addEventListener("keydown", key);
  const n = () => st.pages.length;
  const go = async i => {
    if (!st || i < 0 || i > n() || i === at) return;
    dir = i > at ? 1 : -1; at = i; draw();
    if (i > 0) Sound.play("tap");
    try {
      const r = await engine.turn(i);
      Object.assign(st, { finished: r.finished, may_rate: r.may_rate, rating: r.rating ?? st.rating });
      if (r.new_finish || (i === n() && preview)) { confetti(full); Sound.play("done"); }
      if (at === n()) draw(false);
    } catch (e) { toast(e.message, "bad"); }
  };
  const restart = async () => { try { await engine.restart(); } catch {} dir = -1; at = 0; draw(); };
  // the page: the cover, a page in its layout, the end below the last page
  const coverPage = () => h("article.pb-page.pb-cover", { lang: st.lang, style: { "--sb-c": SB_COVERS[st.color] || SB_COVERS[0] } },
    h("div.pb-cpic", st.cover ? pbPic(st.cover) : h("span.pb-emo", { translate: "no" }, st.emoji)),
    h("div.pb-ctitle", C(st.title, "h2"), st.author ? h("p.pb-by", sbFmt(T("by {0}"), "⁨" + st.author + "⁩")) : null));
  const endBox = () => h("div.pb-end",
    h("p.pb-endtitle", "🎉 ", T("The end")),
    st.may_rate ? h("div.sb-rateme", h("span.small", T("How did you like the book?")),
      h("div.sb-stars", ...[1, 2, 3, 4, 5].map(v => h("button.sb-star" + (v <= (st.rating || 0) ? ".on" : ""), { "aria-label": v + " ★",
        onclick: async () => { try { await engine.rate(v); st.rating = v; draw(false); toast(T("Thank you!"), "good"); } catch (e) { toast(e.message, "bad"); } } }, "★")))) : null,
    h("div.row.center.wrap.pb-endbtns", h("button.btn.small", { onclick: restart }, "↺ ", T("Read again")),
      h("button.btn.small.ghost", { onclick: close }, "📚 ", T("Back to the bookshelf"))));
  const page = p => h("article.pb-page.pb-l-" + p.layout, { lang: st.lang },
    p.layout !== "text" ? h("div.pb-pic" + (p.pic ? "" : ".none"), pbPic(p.pic)) : null,
    p.text ? C(p.text, "div.pb-text") : null);
  const draw = (anim = true) => {
    const last = at === n();
    const pg = at === 0 ? coverPage() : page(st.pages[at - 1]);
    if (anim && dir) pg.classList.add(dir > 0 ? "pb-next" : "pb-prev");
    sbSet(full,
      h("div.sb-rtop",
        h("button.icon-btn", { title: T("Close"), "aria-label": T("Close"), onclick: close }, "✕"),
        h("div.sb-rtitle", h("span", { translate: "no" }, st.emoji), C(st.title, "strong")),
        h("span.sb-pill.pb-count", { title: T("Page") }, at === 0 ? T("Cover") : at + " / " + n())),
      preview ? h("p.sb-try.small", "👀 ", T("Try-out – nothing is saved")) : null,
      h("div.pb-stage", pg, last ? endBox() : null),
      h("div.pb-nav",
        h("button.pb-arrow", { "aria-label": T("Previous page"), title: T("Previous page"), disabled: at === 0, onclick: () => go(at - 1) }, "◀"),
        h("div.pb-dots", { "aria-hidden": "true" }, ...Array.from({ length: Math.min(n() + 1, 24) }, (_, i) =>
          h("i" + (i === Math.min(at, 23) ? ".on" : "")))),
        h("button.pb-arrow.next", { "aria-label": T("Next page"), title: T("Next page"), disabled: last, onclick: () => go(at + 1) }, "▶")));
    const stage = full.querySelector(".pb-stage");
    if (anim) stage.scrollTop = 0;
    // swipe: a horizontal move of the finger turns the page
    let x0 = null, y0 = 0;
    stage.addEventListener("pointerdown", e => { if (e.pointerType !== "mouse") { x0 = e.clientX; y0 = e.clientY; } });
    stage.addEventListener("pointerup", e => {
      if (x0 == null) return;
      const dx = e.clientX - x0, dy = e.clientY - y0; x0 = null;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.4) go(at + (dx < 0 ? 1 : -1));
    });
    stage.addEventListener("pointercancel", () => { x0 = null; });
  };
  document.body.append(full);
  document.body.classList.add("quiz-open");
  (async () => {
    try { st = await engine.read(); } catch (e) { toast(e.message, "bad"); return close(); }
    at = Math.min(st.at || 0, st.pages.length);
    if (at === st.pages.length && at > 0) at = 0;                 // read to the end before: start again with the cover
    draw(false);
  })();
}

// ---------------------------------------------------------------- writing
async function pictureEditor(id, onClose = null) {
  let ed;
  try { ed = await api("stories/" + id); } catch (e) { return toast(e.message, "bad"); }
  const data = ed.data;
  data.cover = data.cover || { pic: null };
  const meta = { title: ed.title, emoji: ed.emoji, color: ed.color, lang: ed.lang };
  let visSent = ed.visibility, dirty = false, timer = null, saving = null, showIssues = false, closed = false;
  const full = h("div.quiz-full.sb-full.sb-editor.pb-editor");
  const head = h("div.sb-ehead"), infoEl = h("div.pb-einfo"), checker = h("div.sb-checker"), body = h("div.sb-ebody");
  const stateEl = h("span.sb-state");
  full.append(head, infoEl, checker, body);
  const issues = () => pbCheck(data, meta.title);
  const setState = s => { stateEl.className = "sb-state " + s; stateEl.textContent = { dirty: "●", saving: "…", saved: "✓", error: "⚠" }[s] || "";
    stateEl.title = I18N.tr({ dirty: T("Not saved yet"), saving: T("Saving …"), saved: T("Saved"), error: T("Not saved") }[s] || ""); };
  const save = async () => {
    clearTimeout(timer);
    if (saving) await saving;
    if (!dirty) return true;
    dirty = false; setState("saving");
    const b = { data, ...meta };
    if (visSent !== ed.visibility) b.visibility = visSent;
    saving = api("stories/" + id, { method: "PUT", body: b }).then(r => {
      const vis = r.visibility !== ed.visibility || r.pending !== ed.pending; ed = r; visSent = r.visibility;
      // the server cleans own SVG pictures: show what is left
      r.data.pages.forEach((p, i) => { if (data.pages[i] && data.pages[i].id === p.id && JSON.stringify(data.pages[i].pic) !== JSON.stringify(p.pic) && !dirty) data.pages[i].pic = p.pic; });
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
  const finish = () => { window.removeEventListener("hashchange", close); full.remove();
    if (!document.querySelector(".sb-full")) document.body.classList.remove("quiz-open"); onClose && onClose(); };
  const close = async () => { if (closed) return; closed = true; await save(); finish(); };
  window.addEventListener("hashchange", close);

  // ---------- header
  const publish = async () => {
    if (!(await save())) return;
    if (issues().length) { showIssues = true; drawChecker(); return toast(I18N.tr(T("Not finished yet – look at the checker")), "bad"); }
    try {
      const r = await api(`stories/${id}/publish`, { method: "POST" });
      if (r.status === "pending") toast(I18N.tr(T("Sent to the parents – they check it first")), "good");
      else { toast(I18N.tr(T("Published! The family can read it now.")), "good"); confetti(full); Sound.play("done"); }
      ed = await api("stories/" + id); drawHead();
    } catch (e) { toast(e.message, "bad"); }
  };
  const tryOut = () => pictureReader(pbLocalEngine({ ...meta, author: ed.author, data: JSON.parse(JSON.stringify(data)) }), { preview: true });
  const drawHead = () => { sbSet(head,
    h("div.sb-erow",
      h("button.icon-btn", { title: T("Close"), "aria-label": T("Close"), onclick: close }, "✕"),
      h("button.sb-etitle", { title: T("Book settings"), onclick: () => metaDialog() },
        h("span.sb-eic", { style: { background: SB_COVERS[meta.color] || SB_COVERS[0] }, translate: "no" }, meta.emoji),
        C(meta.title || "…", "strong"), h("span.sb-pen", "⚙️")),
      stateEl),
    h("div.sb-erow.sb-tools",
      h("span.sb-st", "📕 ", T("Picture book")),
      h("span.grow"),
      h("button.btn.small.ghost", { onclick: tryOut, title: T("Try it out") }, "▶ ", h("span.sb-hide-s", T("Read"))),
      h("button.btn.small", { onclick: publish }, "🚀 ", ed.live && !ed.changed ? T("On the shelf") : ed.pending ? T("Waiting") : T("Publish"))));
  sbSet(infoEl,                                       // below the sticky head: it scrolls away while writing
    ed.mine ? h("div.sb-erow.sb-visrow", h("b.small", T("Who can read it?")), sbVisPicker(visSent, v => { visSent = v; changed(); save(); }))
      : h("p.sb-note", SB_VIS()[ed.visibility][0], " ", SB_VIS()[ed.visibility][1], " · ", C(ed.author)),
    ed.pending ? h("p.sb-note", "⏳ ", ed.parent ? T("This book waits for a parent's approval (Family › My books).") : T("Your book waits for a parent's approval.")) : null,
    ed.reward && (ed.reward.write_coins || ed.reward.write_xp) && !ed.shared ? h("p.sb-note", "🎁 ", sbFmt(T("When the others can read it you get {0}"),
      [ed.reward.write_coins ? ed.reward.write_coins + " 🪙" : "", ed.reward.write_xp ? ed.reward.write_xp + " XP" : ""].filter(Boolean).join(" + "))) : null); };

  // ---------- checker
  const goPage = pid => { const el = full.querySelector("#pbp-" + pid); if (el) { el.scrollIntoView({ behavior: "smooth", block: "start" }); el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); } };
  const drawChecker = () => {
    const list = issues();
    sbSet(checker, list.length
      ? h("details.sb-issues", { open: showIssues, ontoggle: e => { showIssues = e.target.open; } },
          h("summary", "⚠️ ", sbFmt(T("{0} things to finish before publishing"), list.length)),
          h("ul", ...list.map(i => h("li", i.page ? h("button.link", { onclick: () => goPage(i.page) }, sbIssueText(i)) : sbIssueText(i)))))
      : h("div.sb-ready", "✅ ", T("Ready to publish – every page has its picture and text.")));
  };
  const markCards = () => {
    const list = issues();
    for (const el of full.querySelectorAll(".pb-pcard")) {
      const mine = list.filter(i => i.page === +el.dataset.id);
      el.classList.toggle("bad", mine.length > 0);
      const box = el.querySelector(".sb-pissues");
      if (box) sbSet(box, ...mine.map(i => h("li", sbIssueText(i))));
    }
  };

  // ---------- cover and pages
  const coverCard = () => h("section.card.pb-pcard.pb-covercard", { style: { "--sb-c": SB_COVERS[meta.color] || SB_COVERS[0] } },
    h("div.sb-phead", h("span.sb-pnum", "📕"), h("b", T("Cover")), h("span.grow")),
    h("div.pb-emain",
      h("button.pb-picbtn.cover", { title: T("Picture"), onclick: () => picDialog(data.cover) },
        data.cover.pic ? pbPic(data.cover.pic) : h("span.pb-emo", { translate: "no" }, meta.emoji)),
      h("div.pb-covertxt", C(meta.title || "…", "strong"), h("span.small.muted", T("The cover shows the title and the author. Tap the picture to change it.")),
        h("button.btn.small.ghost", { onclick: () => metaDialog() }, "⚙️ ", T("Title, colour, language")))));
  const move = (p, d) => { const i = data.pages.indexOf(p), j = i + d; if (j < 0 || j >= data.pages.length) return;
    data.pages.splice(i, 1); data.pages.splice(j, 0, p); changed(true); setTimeout(() => goPage(p.id), 50); };
  const pageCard = (p, i) => {
    const text = h("textarea.sb-ptext.pb-ptext", { rows: 4, maxlength: PB_TEXT, lang: meta.lang, placeholder: I18N.tr(T("What does this page tell?")) });
    text.value = p.text || "";
    const count = h("span.pb-chars.small.muted", (p.text || "").length + " / " + PB_TEXT);
    text.oninput = () => { p.text = text.value; count.textContent = text.value.length + " / " + PB_TEXT; changed(); };
    const lays = h("div.sb-kinds.pb-lays", ...Object.entries(PB_LAYOUTS()).map(([k, [ic, label]]) => h("button.sb-kind" + (p.layout === k ? ".on" : ""),
      { title: label, "aria-label": label, onclick: () => { if (p.layout !== k) { p.layout = k; changed(true); } } }, ic, h("span.sb-hide-s", " ", label))));
    return h("section.card.sb-pcard.pb-pcard.pb-cl-" + p.layout, { id: "pbp-" + p.id, "data-id": p.id },
      h("div.sb-phead", h("span.sb-pnum", String(i + 1)), lays, h("span.grow"),
        h("button.icon-btn.pb-mv", { title: T("Move up"), "aria-label": T("Move up"), disabled: i === 0, onclick: () => move(p, -1) }, "↑"),
        h("button.icon-btn.pb-mv", { title: T("Move down"), "aria-label": T("Move down"), disabled: i === data.pages.length - 1, onclick: () => move(p, 1) }, "↓"),
        h("button.icon-btn.sb-del", { title: T("Remove page"), "aria-label": T("Remove page"), onclick: () => {
          if ((p.text || p.pic) && !confirm(I18N.tr(T("Remove this page?")))) return;
          data.pages.splice(data.pages.indexOf(p), 1); changed(true);
        } }, "🗑")),
      h("div.pb-emain",
        p.layout !== "text" ? h("button.pb-picbtn", { title: T("Picture"), onclick: () => picDialog(p) },
          p.pic ? pbPic(p.pic) : h("span.sb-nopic", "🖼️", h("span.small", T("Choose a picture")))) : null,
        h("label.pb-tlab", text, count)),
      h("ul.sb-pissues"));
  };
  const addPage = layout => {
    if (data.pages.length >= PB_MAX_PAGES) return toast(I18N.tr(T("A picture book can have at most 60 pages")), "bad");
    const pid = Math.max(0, ...data.pages.map(p => p.id)) + 1;
    data.pages.push({ id: pid, layout, text: "", pic: null }); changed(true); setTimeout(() => goPage(pid), 50);
  };
  const drawBody = () => {
    sbSet(body, h("div.sb-cards.pb-cards", coverCard(), ...data.pages.map(pageCard)),
      h("div.sb-addrow", h("span.small.muted", T("New page:")),
        ...Object.entries(PB_LAYOUTS()).map(([k, [ic, label]]) => h("button.btn.small.ghost", { onclick: () => addPage(k) }, ic, " ", label))));
    markCards();
  };

  // ---------- pictures: library, emoji, painter, photo, own SVG code
  const picDialog = target => {
    const set = pic => { target.pic = pic; m.close(); changed(true); };
    let tab = "lib";
    const box = h("div.pb-pictab");
    const own = h("input.sb-ownemo", { type: "text", maxlength: 8, placeholder: "🙂", "aria-label": T("Own emoji") });
    const file = h("input", { type: "file", accept: "image/*", hidden: true });
    file.onchange = async () => {
      const f = file.files[0]; if (!f) return;
      try { const blob = await sbShrink(f); const r = await sbUpload(blob, "photo.jpg"); set({ k: "img", v: r.name, src: "photo" }); } catch (e) { toast(e.message, "bad"); }
    };
    const code = h("textarea.sb-imptext.pb-svgcode", { rows: 7, spellcheck: false, placeholder: "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 300'>…</svg>" });
    if (target.pic && target.pic.k === "svg") code.value = target.pic.v;
    const drawTab = () => {
      for (const b of tabs.querySelectorAll(".sb-seg")) b.classList.toggle("on", b.dataset.k === tab);
      if (tab === "lib") sbSet(box, h("div.sb-bggrid", ...Object.entries(SB_BGS()).map(([k, n]) => h("button.sb-bgtile" + (target.pic && target.pic.k === "lib" && target.pic.v === k ? ".on" : ""),
        { type: "button", onclick: () => set({ k: "lib", v: k }) }, h("span.sb-bgimg", { style: { backgroundImage: `url(${sbBgUrl(k)})` } }), h("span.small", n)))));
      else if (tab === "emoji") sbSet(box, h("div.sb-picgrid", ...SB_PICS.map(e => h("button.sb-pe", { type: "button", translate: "no", onclick: () => set({ k: "emoji", v: e }) }, e)),
        own, h("button.btn.small", { onclick: () => own.value.trim() && set({ k: "emoji", v: own.value.trim() }) }, "✓")));
      else if (tab === "own") sbSet(box, h("div.row.wrap.pb-ownbtns",
        h("button.btn", { onclick: async () => {
          m.close();
          const blob = await sbPainter(target.pic && target.pic.k === "img" && target.pic.src === "draw" ? sbImg(target.pic.v) : null);
          if (!blob) return;
          try { const r = await sbUpload(blob, "drawing.png"); target.pic = { k: "img", v: r.name, src: "draw" }; changed(true); } catch (e) { toast(e.message, "bad"); }
        } }, "🎨 ", T("Paint")),
        h("button.btn.ghost", { onclick: () => file.click() }, "📷 ", T("Photo")), file));
      else sbSet(box, h("p.small.muted", T("Paste an SVG drawing (e.g. made by an AI): simple shapes with a viewBox, max. 12 KB. Scripts, links and external files are removed.")),
        code, h("button.btn", { onclick: async () => {
          try { const r = await api("stories/svg", { method: "POST", body: { svg: code.value } }); set({ k: "svg", v: r.svg }); } catch (e) { toast(e.message, "bad"); }
        } }, "✓ ", T("Use picture")));
    };
    const tabs = h("div.sb-segs.pb-tabs", ...[["lib", "🏞️", T("Pictures")], ["emoji", "😀", T("Emoji")], ["own", "🎨", T("Own picture")], ["svg", "</>", T("SVG code")]]
      .map(([k, ic, n]) => h("button.sb-seg", { type: "button", "data-k": k, title: n, "aria-label": n, onclick: () => { tab = k; drawTab(); } }, h("span", { translate: "no" }, ic), h("span.sb-hide-s", " ", n))));
    const m = modal(h("div.form.pb-picdlg", h("h2", "🖼️ ", T("Picture")), tabs, box,
      h("div.row.wrap", target.pic ? h("button.btn.ghost", { onclick: () => set(null) }, "🗑 ", T("No picture")) : null,
        h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
    drawTab();
  };

  // ---------- title, colour, language, export, remove
  const metaDialog = () => {
    let emoji = meta.emoji, color = meta.color;
    const title = h("input", { type: "text", maxlength: 80, value: meta.title });
    const lang = h("select", ...I18N.LANGS.filter(([k]) => k !== "auto").map(([k, nm]) => h("option", { value: k, translate: "no", selected: k === meta.lang }, nm)));
    const ownE = h("input.sb-ownemo", { type: "text", maxlength: 8, placeholder: "🙂", "aria-label": T("Own emoji") });
    const pick = h("div.sb-emojis"), cols = h("div.sb-colors");
    const drawPick = () => {
      sbSet(pick, ...["📕", ...SB_EMOJI.slice(1)].map(e => h("button.sb-pe" + (e === emoji ? ".on" : ""), { type: "button", translate: "no", onclick: () => { emoji = e; ownE.value = ""; drawPick(); } }, e)), ownE);
      sbSet(cols, ...SB_COVERS.map((g, i) => h("button.sb-col" + (i === color ? ".on" : ""), { type: "button", "aria-label": String(i + 1), style: { background: g }, onclick: () => { color = i; drawPick(); } })));
    };
    ownE.oninput = () => { if (ownE.value.trim()) emoji = ownE.value.trim(); };
    drawPick();
    const run = async (path, method, msg, after) => { try { await api(path, { method }); toast(msg, "good"); m.close(); after(); } catch (e) { toast(e.message, "bad"); } };
    const m = modal(h("div.form", h("h2", "⚙️ ", T("Book settings")),
      h("label.field", T("Title"), title), h("div.field", h("b", T("Shelf icon and colour")), pick, cols),
      h("label.field", T("Language of the book"), lang),
      h("div.row", h("button.btn", { onclick: () => {
        if (!title.value.trim()) return title.focus();
        Object.assign(meta, { title: title.value.trim(), emoji, color, lang: lang.value }); m.close(); drawHead(); changed(true);
      } }, "💾 ", T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel"))),
      h("div.row.wrap", h("button.btn.small.ghost", { onclick: async () => { await save(); downloadApi(`stories/${id}/export`, `family-quest-picturebook-${id}.json`); } }, "⬇️ ", T("Export as a file")),
        h("span.small.muted", T("For a backup, another family or an AI – SVG, library and emoji pictures go along, own drawings and photos stay out."))),
      h("div.sb-danger.row.wrap",
        ed.live || ed.pending ? h("button.btn.small.ghost", { onclick: () => confirm(I18N.tr(T("Take the book off the shelf? It stays here as a draft."))) &&
          run(`stories/${id}/unpublish`, "POST", T("The book is a draft again"), async () => { ed = await api("stories/" + id); drawHead(); }) }, "📥 ", T("Unpublish")) : null,
        h("button.btn.small.bad", { onclick: () => confirm(I18N.tr(T("Remove this book for good? This cannot be undone."))) &&
          run(`stories/${id}`, "DELETE", T("Removed"), () => { closed = true; dirty = false; clearTimeout(timer); finish(); }) }, "🗑 ", T("Remove book")))), { wide: true });
  };

  document.body.append(full);
  document.body.classList.add("quiz-open");
  setState("saved");
  drawHead(); drawChecker(); drawBody();
}
