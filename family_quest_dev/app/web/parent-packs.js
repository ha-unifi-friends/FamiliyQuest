// ---------------------------------------------------------------- 📦 Learning packs: list, editor, Code Workshop, import
// A part of the parent area (parent.js): loaded after it, before boot() runs (eltern.html).
"use strict";

// ---------------------------------------------------------------- packs
const LANG_FLAG = { de: "🇩🇪", en: "🇬🇧", fr: "🇫🇷", it: "🇮🇹", es: "🇪🇸", nl: "🇳🇱", pl: "🇵🇱", pt: "🇧🇷", sv: "🇸🇪" };
const LANG_NAME = { de: T("German"), en: T("English"), fr: T("French"), it: T("Italian"), es: T("Spanish"), nl: T("Dutch"), pl: T("Polish"), pt: T("Portuguese"), sv: T("Swedish") };

async function packsView(main) {
  const [d, profiles] = await Promise.all([call("parent/packs"), call("parent/profiles")]);
  const kids = profiles.filter(p => p.role === "kid");
  const drafts = d.packs.filter(p => p.status === "draft");
  const imported = p => !["builtin", "share"].includes(p.source);      // own packs: imported, made with the AI or edited – shown on top
  // «More packs»: optional packs of the app (e.g. German content only) – not installed until a parent adds them
  const available = d.packs.filter(p => p.status === "available");
  const shown = d.packs.filter(p => p.status !== "available");
  const importedPacks = shown.filter(p => p.status !== "draft" && imported(p));
  const bundles = shown.filter(p => p.kind === "bundle" && p.status !== "draft");
  const packs = shown.filter(p => p.kind === "pack" && p.status !== "draft");
  const actRow = p => h("div.act", ...kids.map(k => h("label.check", h("input", { type: "checkbox", checked: p.profiles.includes(k.id),
    onchange: async e => {
      try { await call("parent/packs/activate", { method: "POST", body: { profile_id: k.id, pack_id: p.id, on: e.target.checked } }); toast(T("Saved"), "good"); }
      catch { e.target.checked = !e.target.checked; return; }   // call() showed the error
      if (p.kind === "bundle") render();
    } }),
    C(k.name))));
  const byId = Object.fromEntries(d.packs.map(p => [p.id, p]));
  // «⋯»: the rarely used actions (export, delete) – the row keeps room for the title
  const moreMenu = p => h("details.more-menu",
    h("summary.btn.small.ghost", { title: T("More"), "aria-label": T("More") }, "⋯"),
    h("div.more-pop",
      h("button.btn.small.ghost", { title: T("Export as ZIP (with pictures)"), onclick: e => { e.target.closest("details").open = false; download(p.id, "zip"); } }, "⬇️ ", T("Export as ZIP (with pictures)")),
      h("button.btn.small.ghost", { onclick: e => { e.target.closest("details").open = false; download(p.id, "json"); } }, "⬇️ ", T("Export as JSON")),
      // an optional pack of the app goes back to «More packs» (deleting it would only bring it back at the next start)
      p.optional && !imported(p)
        ? h("button.btn.small.ghost", { onclick: e => { e.target.closest("details").open = false; uninstall(p); } }, "↩️ ", T("Remove from the family"))
        : h("button.btn.small.ghost.danger-text", { onclick: e => { e.target.closest("details").open = false; del(p); } }, "🗑️ ", T("Delete"))));
  // the language the content is written in (packs that do not follow the app language)
  const langNote = p => (p.content_langs || []).length ? h("span.chip.pack-lang", { title: T("The questions and answers of this pack are written in this language") },
    (p.content_langs || []).map(l => (LANG_FLAG[l] || "🗣️") + " ").join(""), I18N.tr(T("Content in {0}")).replace("{0}", p.content_langs.map(l => langInText(I18N.tr(LANG_NAME[l] || l))).join(", "))) : null;
  const card = p => h("div.card.pack" + (p.status === "draft" ? ".draft" : ""), { "data-find": [p.id, p.title, p.level, p.subject && I18N.tr(p.subject.name), ...(p.units || []).map(u => u.title)].filter(Boolean).join(" ") },
    h("div.row.pack-head", h("span.big-ic", p.kind === "bundle" ? "🎒" : (p.icon || "📚")), h("div.grow", C(p.title, "strong"),
      h("div.small.muted", p.kind === "bundle" ? T("Level pack") : subjectName(p.subject.key), p.level ? h("span", { translate: "no" }, " · " + p.level) : null, " · ",
        STATUS[p.status] || p.status, p.private ? " · 🔒 " + I18N.tr(T("private")) : ""), langNote(p)), moreMenu(p)),
    h("div.row.wrap.pack-acts",
      // a draft is checked, then published – the same two verbs as on the import page
      p.kind === "pack" ? h("button.btn.small.ghost", { onclick: () => packEditor(p.id) }, "✏️ ", p.status === "draft" ? T("Check") : T("Edit")) : null,
      p.kind === "pack" ? h("button.btn.small.ghost", { title: T("XP and coins per finished lesson of this pack"), onclick: () => packRewards(p) },
        "🏅 ", p.rewards && (p.rewards.xp != null || p.rewards.coins != null)
          ? [p.rewards.xp != null ? p.rewards.xp + " XP" : "", p.rewards.xp != null && p.rewards.coins != null ? " · " : "", p.rewards.coins != null ? p.rewards.coins + " 🪙" : ""]
          : T("Rewards")) : null,
      p.kind === "pack" ? h("button.btn.small.ghost", { title: T("Opens the pack in the app in a new tab – parents can try every pack"), onclick: () => openInApp("pack/" + encodeURIComponent(p.id)) }, "▶ ", T("Try in the app")) : null,
      p.status === "draft" ? h("button.btn.small.good", { onclick: () => setStatus(p.id, "active") }, "✓ ", T("Publish"))
        : h("button.btn.small.ghost", { onclick: () => setStatus(p.id, p.status === "active" ? "disabled" : "active") }, p.status === "active" ? T("Switch off") : T("Switch on"))),
    p.kind === "pack" ? h("div.small.units", ...p.units.map(u => chip([u.icon ? u.icon + " " : "", C(u.title), " · " + u.count]))) :
      // level pack: its packs by title (the internal ids mean nothing to parents)
      h("div.small", ...(p.semesters || []).map(s => h("div", C(s.titel || s.id, "strong"), ": ",
        C(s.pakete.map(id => byId[id] ? byId[id].title : id).join(", ") || "–")))),
    kids.length ? (p.status === "draft" ? h("div", h("div.small.muted", "👧 ", T("Assign now – the child sees it as soon as you publish it:")), actRow(p)) : actRow(p)) : null);
  // switch: sorted by packs (which children have a pack) or grouped by children (which packs a child has)
  let mode = "packs"; try { mode = localStorage.getItem("fq.packs.view") || "packs"; } catch {}
  if (!kids.length) mode = "packs";
  const seg = h("div.seg", { role: "radiogroup", "aria-label": T("Show") }, ...[["packs", "📚 ", T("By pack")], ["kids", "👧 ", T("By child")]].map(([k, ic, n]) =>
    h("button" + (mode === k ? ".on" : ""), { type: "button", role: "radio", "aria-checked": String(mode === k), disabled: k === "kids" && !kids.length,
      onclick: () => { try { localStorage.setItem("fq.packs.view", k); } catch {} render(); } }, ic, n)));
  const toggle = async (kid, pack, on) => {
    await call("parent/packs/activate", { method: "POST", body: { profile_id: kid.id, pack_id: pack.id, on } });
    render();
  };
  const byKid = () => kids.map(k => {
    const mine = [...bundles, ...packs].filter(p => p.profiles.includes(k.id));
    const others = [...bundles, ...packs].filter(p => !p.profiles.includes(k.id) && p.status === "active");
    const add = h("select", { onchange: () => { const p = others.find(x => x.id === add.value); if (p) toggle(k, p, true); } },
      h("option", { value: "" }, "＋ " + I18N.tr(T("Add pack …"))),
      ...others.map(p => h("option", { value: p.id, translate: "no" }, (p.kind === "bundle" ? "🎒 " : (p.icon || "📚") + " ") + p.title)));
    return h("section.card.sec.kid-packs",
      h("div.row", avatarSvg(k.avatar, 44), C(k.name, "h2.grow"), h("span.muted", I18N.tr(T("Packs: {0}")).replace("{0}", mine.length))),
      mine.length ? h("ul.pack-mini-list", ...mine.map(p => h("li.row.pack-mini" + (p.status !== "active" ? ".off" : ""),
        h("span.big-ic", p.kind === "bundle" ? "🎒" : (p.icon || "📚")),
        h("div.grow", C(p.title, "strong"), h("div.small.muted", p.kind === "bundle" ? T("Level pack") : subjectName(p.subject.key),
          p.level ? h("span", { translate: "no" }, " · " + p.level) : null, p.status !== "active" ? " · " + I18N.tr(STATUS[p.status] || p.status) : "")),
        h("button.btn.small.ghost", { title: T("Remove"), onclick: () => toggle(k, p, false) }, "✕")))) : h("p.muted", T("No packs yet.")),
      others.length ? add : null);
  });
  // search: filters the pack cards (title, subject, level, units, id) – remembered while the page is open
  const search = h("input.pack-search", { type: "search", placeholder: "🔍 " + I18N.tr(T("Search packs …")), value: P.packSearch || "",
    "aria-label": T("Search packs …"), oninput: () => { P.packSearch = search.value; filterPacks(); } });
  const noPacks = noMatch(T("No packs found"), () => { search.value = ""; P.packSearch = ""; filterPacks(); });
  const filterPacks = () => {
    const q = (search.value || "").trim().toLowerCase();
    const all = [...main.querySelectorAll(".card.pack, .pack-mini")];
    all.forEach(c => { c.hidden = !!q && !((c.dataset.find || c.textContent).toLowerCase().includes(q)); });
    noPacks.hidden = !q || all.some(c => !c.hidden);
    main.querySelectorAll("section.sec, section.card.sec").forEach(sec => {
      const cards = sec.querySelectorAll(".card.pack, .pack-mini");
      if (!cards.length) return;
      const fold = sec.closest("details.set-fold") || sec, hit = [...cards].some(c => !c.hidden);
      fold.hidden = !!q && !hit && !sec.classList.contains("kid-packs");
      if (q && hit && fold.tagName === "DETAILS") fold.open = true;          // a search opens the boxes with what it found
    });
  };
  setTimeout(filterPacks);
  main.append(pageHead(T("Learning packs"), seg,
    h("button.btn.ghost", { title: T("All packs in one JSON file"), onclick: () => download(null, "json") }, "⬇️ ", T("Export all")),
    h("button.btn", { onclick: () => { P.tab = "import"; render(); } }, "📥 ", T("Import"))));
  main.append(search, noPacks);
  // 💡 Code Workshop (codelab.js): only in the dev channel (channel.DEV_FEATURES)
  const codeSec = P.info && P.info.codelab ? await codelabSection().catch(e => section("💡 " + I18N.tr(T("Code Workshop")), h("p.bad", e.message))) : null;
  const german = String(I18N.lang || "").startsWith("de");
  const more = moreSection(german);
  // every box folded like the settings (the grouping stays): its title and how many packs it holds in the row
  const packCount = sec => sec.classList.contains("kid-packs") ? "" : I18N.tr(T("Packs: {0}")).replace("{0}", sec.querySelectorAll(".card.pack").length);
  const kidStatus = sec => { const r = sec.querySelector(":scope > .row > span.muted"); return r ? r.textContent : ""; };
  if (mode === "kids") {
    main.append(...byKid(), drafts.length ? section("📝 " + I18N.tr(T("To check")), ...drafts.map(card)) : null, codeSec, more);
    return foldBoxes(main, "packs", sec => kidStatus(sec) || packCount(sec));
  }
  const levelPacks = bundles.filter(p => !imported(p)), ownPacks = packs.filter(p => !imported(p));
  main.append(
    german ? more : null,
    drafts.length ? section("📝 " + I18N.tr(T("Imported as draft – to check")), ...drafts.map(card)) : null,
    importedPacks.length ? section("⭐ " + I18N.tr(T("Own packs")), ...importedPacks.map(card)) : null,
    levelPacks.length ? section("🎒 " + I18N.tr(T("Level packs")), ...levelPacks.map(card)) : null,
    ownPacks.length ? section("📚 " + I18N.tr(T("Packs")), ...ownPacks.map(card)) : null, codeSec, german ? null : more);
  foldBoxes(main, "packs", sec => sec.querySelector(".cw-pk, table") && !sec.querySelector(".card.pack") ? "" : packCount(sec));
  // ➕ More packs: optional packs of the app, added with one click (then switched on per child as every other pack)
  function moreSection(top) {
    if (!available.length) return null;
    const de = available.filter(p => (p.content_langs || []).includes("de"));
    const avCard = p => h("div.card.pack.pack-avail", { "data-find": [p.id, p.title, p.level, p.subject && I18N.tr(p.subject.name), ...(p.units || []).map(u => u.title)].filter(Boolean).join(" ") },
      h("div.row.pack-head", h("span.big-ic", p.kind === "bundle" ? "🎒" : (p.icon || "📚")), h("div.grow", C(p.title, "strong"),
        h("div.small.muted", p.kind === "bundle" ? T("Level pack") : subjectName(p.subject.key), p.level ? h("span", { translate: "no" }, " · " + p.level) : null), langNote(p)),
        h("button.btn.small.good", { onclick: () => install([p.id]) }, "＋ ", T("Add"))),
      p.description ? C(p.description, "p.small.muted") : null,
      p.kind === "pack" ? h("div.small.units", ...p.units.map(u => chip([u.icon ? u.icon + " " : "", C(u.title), " · " + u.count]))) :
        h("div.small", ...(p.semesters || []).map(s => h("div", C(s.titel || s.id, "strong"), ": ",
          C(s.pakete.map(id => byId[id] ? byId[id].title : id).join(", ") || "–")))));
    return section("➕ " + I18N.tr(T("More packs")),
      de.length > 1 ? h("button.btn", { onclick: () => install(de.map(p => p.id)) }, "🇩🇪 ", T("Add all German-language packs")) : null,
      ...available.map(avCard));
  }
  async function install(ids) {
    try { await call("parent/packs/install", { method: "POST", body: { ids, on: true } }); toast(T("Added"), "good"); } catch { return; }
    render();
  }
  async function uninstall(p) {
    if (!(await confirmDialog(I18N.tr(T("Remove {0} from the family? It is switched off for every child and goes back to «More packs». The learning progress is kept.")).replace("{0}", p.title)))) return;
    try { await call("parent/packs/install", { method: "POST", body: { ids: [p.id], on: false } }); } catch { return; }
    render();
  }
  function packRewards(p) {
    const r = p.rewards || {};
    const xp = h("input", { type: "number", min: 0, max: 10000, value: r.xp ?? "", placeholder: "–", inputmode: "numeric" });
    const coins = h("input", { type: "number", min: 0, max: 10000, value: r.coins ?? "", placeholder: "–", inputmode: "numeric" });
    const num = el => el.value === "" ? null : Math.max(0, parseInt(el.value, 10) || 0);
    const save = async () => {
      try { await call(`parent/packs/${encodeURIComponent(p.id)}/rewards`, { method: "POST", body: { xp: num(xp), coins: num(coins) } }); m.close(); toast(T("Saved"), "good"); render(); }
      catch (e) { toast(e.message, "bad"); }
    };
    const m = modal(h("div.form", h("h2", "🏅 ", C(p.title), fieldInfo(T("What a finished lesson of this pack gives. Empty: the family rule (Points & rules › Rules «Lesson finished»). The daily limit of the rule still applies."))),
      // both numbers side by side, the icon inline in the label; empty = the family rule, «Reset» empties both
      h("div.reward-nums", h("label.field", { title: T("XP per finished lesson") }, h("span", "⭐ XP"), xp),
        h("label.field", { title: T("Coins per finished lesson") }, h("span", "🪙 ", T("Coins")), coins)),
      h("p.small.muted", T("Empty = family rule"), " · ", h("a", { href: "#", onclick: e => { e.preventDefault(); xp.value = ""; coins.value = ""; } }, T("Reset"))),
      h("div.row", h("button.btn", { onclick: save }, T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  }
  async function setStatus(id, status) { await call(`parent/packs/${encodeURIComponent(id)}/status`, { method: "POST", body: { status } }); render(); }
  async function del(p) { if (!(await confirmDialog(I18N.tr(T("Delete {0}? Learning progress for it is lost.")).replace("{0}", p.title)))) return; await call(`parent/packs/${encodeURIComponent(p.id)}`, { method: "DELETE" }); render(); }
}

// 💡 Code Workshop (familyquest/codelab.py): on / off per child, puzzle rewards, the progress of every child, the programs
// the family shares (open in the app, remove) – of private programs only that they exist
async function codelabSection() {
  const d = await call("codelab/overview");
  const s = d.settings;
  const on = d.kids.map(k => [k.id, h("input", { type: "checkbox", checked: !s.off.includes(k.id) })]);
  const num = v => h("input", { type: "number", min: 0, max: 10000, value: v, inputmode: "numeric" });
  const xp = num(s.level_xp), coins = num(s.level_coins);
  const save = async () => {
    const body = { off: on.filter(([, c]) => !c.checked).map(([id]) => id), level_xp: Math.max(0, Math.round(+xp.value || 0)), level_coins: Math.max(0, Math.round(+coins.value || 0)) };
    try { await call("codelab/settings", { method: "PUT", body }); toast(T("Saved"), "good"); } catch {}
  };
  const worlds = [...new Set(d.levels.map(l => l.world))];
  const kidRow = k => h("tr", h("td", h("div.row.cw-pk", avatarSvg(k.avatar, 30), C(k.name, "strong"))),
    h("td", { translate: "no" }, k.solved + " / " + d.total), h("td", { translate: "no" }, "⭐ " + k.stars),
    ...worlds.map(w => h("td.cw-pw", { translate: "no" }, d.levels.filter(l => l.world === w).map(l => k.levels[l.id] ? "★".repeat(k.levels[l.id]) : "·").join(" "))));
  const proj = d.projects;
  const shared = [...proj.mine, ...proj.others];
  const remove = async p => {
    if (!(await confirmDialog(I18N.tr(T("Remove the program «{0}»?")).replace("{0}", p.title)))) return;
    try { await call("codelab/projects/" + p.id, { method: "DELETE" }); render(); } catch {}
  };
  const VIS = { me: "🔒", kids: "🧒", family: "👨‍👩‍👧" };
  return section("💡 " + I18N.tr(T("Code Workshop")),
    h("div.field", h("b", T("Code Workshop for")), d.kids.length ? h("div.row.wrap", ...on.map(([id, c]) => h("label.check", c, " ", C(d.kids.find(k => k.id === id).name)))) : h("span.small.muted", T("No child profile yet"))),
    h("div.sb-rew", h("b", T("Reward for the first solve of a puzzle level")),
      h("label.field", h("span", "⭐ XP"), xp), h("label.field", h("span", "🪙 ", T("Coins")), coins)),
    h("button.btn", { onclick: save }, "💾 ", T("Save")),
    d.kids.length ? h("div.cw-ptable", h("h3", "🧩 ", T("Puzzle progress")), h("div.tbl-wrap", h("table.tbl",
      h("thead", h("tr", h("th", T("Child")), h("th", T("Levels")), h("th", "⭐"), ...worlds.map(w => h("th", { translate: "no" }, "#" + w)))),
      h("tbody", ...d.kids.map(kidRow))))) : null,
    h("h3", "🎨 ", T("Programs of the family")),
    shared.length ? h("ul.cw-plist-p", ...shared.map(p => h("li.row",
      h("span", VIS[p.visibility] || ""), h("div.grow", C(p.title, "strong"), h("div.small.muted", C(p.author.name), " · 🧱 " + p.blocks + " · " + fmtDate(p.updated_at))),
      h("button.btn.small.ghost", { onclick: () => openInApp("codelab/play/" + p.id) }, "▶ ", T("Open in the app")),
      h("button.btn.small.ghost", { "aria-label": T("Remove"), onclick: () => remove(p) }, "🗑️")))) : h("p.small.muted", T("No shared programs yet.")),
    proj.private.length ? h("div", h("p.small.muted", "🔒 ", T("Private programs – only the child can open them:")),
      h("ul.cw-plist-p", ...proj.private.map(p => h("li.row.small", h("span", "🔒"), C(p.author.name, "strong"), h("span.muted", " · 🧱 " + p.blocks + " · " + fmtDate(p.updated_at)))))) : null);
}

async function download(id, format = "zip") {
  const path = id ? `api/parent/packs/${encodeURIComponent(id)}/export?format=${format}` : "api/parent/packs/export";
  const r = await fetch(path, { headers: { "X-FQ-Parent": Auth.parent } });
  if (!r.ok) return toast(T("Export failed"), "bad");
  const url = URL.createObjectURL(await r.blob());
  const a = h("a", { href: url, download: (id || "family-quest-packs") + "." + format }); document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

async function packEditor(id, { afterSave } = {}) {
  const d = await call(`parent/packs/${encodeURIComponent(id)}/raw`);
  const pack = d.data;
  let mode = "cards";
  const body = h("div");
  const yamlBox = h("textarea.yaml", { spellcheck: false, rows: 24 });
  const subjects = P.meta.subjects;
  const metaF = {
    titel: h("input", { type: "text", value: pack.titel || "" }),
    fach: h("select", ...subjects.map(s => h("option", { value: s.key, selected: s.key === pack.fach }, s.icon + " " + I18N.tr(s.name)))),
    stufe: h("input", { type: "text", value: pack.stufe || "" }),
    sprache: h("input", { type: "text", value: pack.sprache || "", placeholder: "fr / en / it" }),
    pfad: h("input", { type: "checkbox", checked: pack.pfad === true }),
    privat: h("input", { type: "checkbox", checked: !!pack.privat }),
  };
  if (!subjects.some(s => s.key === pack.fach)) metaF.fach.append(h("option", { value: pack.fach, selected: true }, pack.fach));
  const src = pack.quellsprache || "de", tgt = pack.sprache || "";
  const promptOf = c => c.frage ?? c[src] ?? "", answerOf = c => c.antwort ?? (tgt ? c[tgt] : undefined) ?? "";
  const drawCards = () => {
    body.replaceChildren(
      h("div.grid3", h("label.field", T("Title"), metaF.titel), h("label.field", T("Subject"), metaF.fach), h("label.field", T("Level"), metaF.stufe),
        h("label.field", T("Language learnt"), metaF.sprache), h("label.check", metaF.pfad, T("Units unlock one after the other")),
        h("label.check", metaF.privat, T("Private (from school material, never share)"))),
      ...(pack.einheiten || []).map((u, ui) => unitEditor(u, ui)),
      h("button.btn.ghost", { onclick: () => { pack.einheiten.push({ id: "einheit-" + (pack.einheiten.length + 1), titel: I18N.tr(T("New unit")), karten: [{ frage: "", antwort: "" }] }); drawCards(); } }, "+ ", T("Add unit")));
  };
  function unitEditor(u, ui) {
    if (u.generator) return h("div.unit-ed", h("h3", u.icon || "🧮", " ", C(u.titel || u.id)), h("p.small.muted", T("Generator"), ": ", u.generator, " ", C(JSON.stringify(u.parameter || {}))));
    const rows = h("tbody");
    const draw = () => rows.replaceChildren(...u.karten.map((c, i) => h("tr",
      h("td", h("input", { type: "text", value: promptOf(c), "aria-label": T("Question"), oninput: e => { c.frage = e.target.value; delete c[src]; } })),
      h("td", h("input", { type: "text", value: answerOf(c), "aria-label": T("Answer"), oninput: e => { c.antwort = e.target.value; if (tgt) delete c[tgt]; } })),
      h("td.narrow", h("input", { type: "text", value: c.emoji || "", "aria-label": "Emoji", oninput: e => { c.emoji = e.target.value || undefined; } })),
      h("td.narrow", photoCell(c, draw)),
      h("td", h("input", { type: "text", value: c.satz || "", placeholder: "… ___ …", "aria-label": T("Sentence with gap"), oninput: e => { c.satz = e.target.value || undefined; } })),
      h("td", h("input", { type: "text", value: (c.optionen || []).join(" | "), placeholder: "a | b | c", "aria-label": T("Wrong options"), oninput: e => { c.optionen = e.target.value ? e.target.value.split("|").map(x => x.trim()).filter(Boolean) : undefined; } })),
      h("td.narrow", h("button.icon-btn", { title: T("Delete"), onclick: () => { u.karten.splice(i, 1); draw(); } }, "✕")))));
    draw();
    const ex = h("div.row.small", ...Object.entries(EXERCISES).map(([k, n]) => h("label.check", h("input", { type: "checkbox", checked: (u.uebungen || []).includes(k),
      onchange: e => { u.uebungen = u.uebungen || []; if (e.target.checked) u.uebungen.push(k); else u.uebungen = u.uebungen.filter(x => x !== k); } }), n)));
    return h("div.unit-ed",
      h("div.row", h("input.unit-title", { type: "text", value: u.titel || "", "aria-label": T("Unit title"), oninput: e => { u.titel = e.target.value; } }),
        h("button.btn.small.ghost", { onclick: () => { pack.einheiten.splice(ui, 1); drawCards(); } }, "🗑️ ", T("Remove unit"))),
      ex,
      h("table.tbl.cards-tbl", h("thead", h("tr", h("th", T("Question")), h("th", T("Answer")), h("th", "Emoji"), h("th", T("Photo")), h("th", T("Sentence with gap")), h("th", T("Wrong options")), h("th"))), rows),
      h("div.row", h("button.btn.small.ghost", { onclick: () => { u.karten.push({ frage: "", antwort: "" }); draw(); } }, "+ ", T("Add card")),
        h("button.btn.small.ghost", { onclick: () => pickPhotos(true, async files => {
          for (const f of files) { const n = await uploadPhoto(f); if (n) u.karten.push({ bild: n, antwort: "" }); }
          draw();
        }) }, "📷 ", T("Add photos as cards")),
        fieldInfo(T("Own photos: one card per photo – write the answer (e.g. the name) next to it. Shown in «Pairs», quiz and flash cards."), { title: T("Add photos as cards") })));
  }
  function pickPhotos(multiple, cb) { pickFiles({ accept: "image/*", multiple }, cb); }
  async function uploadPhoto(file) {
    try {
      const blob = await shrinkPhoto(file);
      const fd = new FormData(); fd.append("file", blob, "foto.jpg");
      const r = await call(`parent/packs/${encodeURIComponent(id)}/media`, { method: "POST", form: fd });
      return r.name;
    } catch { return null; }
  }
  function photoCell(c, redraw) {
    const set = n => { c.bild = n || undefined; redraw(); };
    if (c.bild) return h("div.photo-cell",
      h("img.card-thumb", { src: /^(https?:|data:)/.test(c.bild) ? c.bild : `media/${encodeURIComponent(id)}/${encodeURIComponent(c.bild)}`, alt: "" }),
      h("button.icon-btn", { title: T("Remove photo"), onclick: () => set(null) }, "✕"));
    return h("button.icon-btn", { title: T("Upload photo"), onclick: () => pickPhotos(false, async ([f]) => set(await uploadPhoto(f))) }, "📷");
  }
  const tabs = h("div.row.tabs",
    h("button.btn.small" + (mode === "cards" ? "" : ".ghost"), { onclick: () => { mode = "cards"; syncFromYaml(); drawCards(); tabsRedraw(); } }, T("Cards")),
    h("button.btn.small.ghost", { onclick: () => { mode = "yaml"; collectMeta(); yamlBox.value = toYaml(); body.replaceChildren(yamlBox); tabsRedraw(); } }, "YAML"));
  const tabsRedraw = () => { const [a, b] = tabs.children; a.className = "btn small" + (mode === "cards" ? "" : " ghost"); b.className = "btn small" + (mode === "yaml" ? "" : " ghost"); };
  function collectMeta() {
    pack.titel = metaF.titel.value; pack.fach = metaF.fach.value; pack.stufe = metaF.stufe.value; pack.sprache = metaF.sprache.value;
    pack.pfad = metaF.pfad.checked; pack.privat = metaF.privat.checked;
  }
  const toYaml = () => JSON.stringify(pack, null, 2);   // JSON is valid YAML – the server stores either
  function syncFromYaml() { if (mode === "yaml") try { Object.assign(pack, JSON.parse(yamlBox.value)); } catch {} }
  drawCards();
  const m = modal(h("div.form", h("div.row", h("h2.grow", T("Edit pack")), tabs), d.summary && d.summary.status === "draft" ? h("p.small.warn-text", T("This is a draft – check every card, then publish it.")) : null,
    body,
    h("div.row.sticky-actions", h("button.btn", { onclick: save }, "💾 ", T("Save")),
      d.summary && d.summary.status === "draft" ? h("button.btn.good", { onclick: () => save(true) }, "✓ ", T("Save and publish")) : null,
      h("button.btn.ghost", { onclick: () => m.close() }, T("Close")))), { wide: true });
  async function save(publish) {
    let payload;
    if (mode === "yaml") payload = { yaml: yamlBox.value };
    else {
      collectMeta();
      for (const u of pack.einheiten || []) if (u.karten) u.karten = u.karten.filter(c => (c.frage ?? c[src]) || (c.antwort ?? c[tgt]) || c.bild);
      payload = { data: JSON.parse(JSON.stringify(pack)) };
    }
    await call(`parent/packs/${encodeURIComponent(id)}/raw`, { method: "PUT", body: payload });
    if (publish) await call(`parent/packs/${encodeURIComponent(id)}/status`, { method: "POST", body: { status: "active" } });
    toast(T("Saved"), "good"); m.close(); afterSave ? afterSave() : render();
  }
}

// ---------------------------------------------------------------- import
async function importView(main) {
  const file = h("input", { type: "file", accept: ".yaml,.yml,.json,.zip,.csv,.tsv,.xlsx" + (P.meta.ai ? ",.pdf,.png,.jpg,.jpeg,.webp" : "") });
  const out = h("div");
  const drop = h("label.drop", file, h("span.big-ic", "📄"), h("strong", T("Choose or drop a file")),
    h("span.small.muted", P.meta.ai ? T("YAML, JSON, ZIP, CSV, Excel, PDF or photo") : T("YAML, JSON, ZIP, CSV or Excel")));
  ["dragover", "dragenter"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, () => drop.classList.remove("over")));
  drop.addEventListener("drop", e => { e.preventDefault(); if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]); });
  file.addEventListener("change", () => file.files[0] && upload(file.files[0]));
  main.append(pageHead(T("Import"), h("button.btn.ghost", { onclick: () => { P.tab = "packs"; location.hash = "packs"; render(); } }, "← ", T("Learning packs"))),
    out,                                        // the imported drafts: on top, right where you look after the upload
    section(T("From a file"), drop,
      P.meta.ai ? null : h("p.small.muted", "📸 ", T("Photo/PDF import: set up an AI in Home Assistant (Settings › Devices & services › AI Task, e.g. OpenAI, Google, Anthropic or a local Ollama)."))),
    section("🤖 " + I18N.tr(T("Made with your AI")),
      aiPromptBox(T("Make me a learning pack for Family Quest.\nSubject: [e.g. French vocabulary]\nSchool year: [e.g. 5th grade]\nTopic or textbook unit: [e.g. unit 3 – at school]\nAbout [20] cards, my child speaks [English]."),
        // the AI hands back a JSON file: the same upload as «From a file» (its checks and messages)
        { template: "api/ai-template/pack", name: "family-quest-pack-template.json", accept: ".json,.yaml,.yml,.txt,application/json,text/plain", onFile: f => upload(f) })));
  async function upload(f) {
    const fd = new FormData(); fd.append("file", f);
    out.replaceChildren(h("p", "⏳ ", T("Reading…")));
    let r;
    try { r = await call("parent/import/file", { method: "POST", form: fd }); } catch { out.replaceChildren(); return; }
    if (r.table) return tableMapping(r.table, out);
    showDrafts(r.drafts, out);
  }
}

async function showDrafts(drafts, out) {
  setTimeout(() => out.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  let kids = [];
  try { kids = (await call("parent/profiles")).filter(p => p.role === "kid"); } catch {}
  const assign = d => kids.length ? h("div.act.draft-assign", h("span.small.muted", "👧 ", T("For:")), ...kids.map(k => h("label.check",
    h("input", { type: "checkbox", onchange: async e => { try { await call("parent/packs/activate", { method: "POST", body: { profile_id: k.id, pack_id: d.id, on: e.target.checked } }); toast(T("Saved"), "good"); } catch (err) { toast(err.message, "bad"); } } }),
    C(k.name)))) : null;
  out.replaceChildren(section("✓ " + I18N.tr(T("Imported as draft")), ...drafts.map(d => h("div.draft-box", h("div.row.draft-row",
    h("span.big-ic", d.kind === "bundle" ? "🎒" : (d.icon || "📚")), h("div.grow", C(d.title, "strong"),
      h("div.small.muted", d.units ? d.units.map(u => u.title + " (" + u.count + ")").join(", ") : ""),
      d.replaces ? h("div.small.warn-text", T("Replaces the existing pack with the same id.")) : null,
      d.uncertain && d.uncertain.length ? h("div.small.warn-text", T("Not readable for sure:"), " ", C(d.uncertain.join(", "))) : null),
    d.kind !== "bundle" ? h("button.btn.small", { onclick: () => packEditor(d.id, { afterSave: () => { P.tab = "packs"; render(); } }) }, "✏️ ", T("Check")) : null,
    h("button.btn.small.good", { onclick: async () => { await call(`parent/packs/${encodeURIComponent(d.id)}/status`, { method: "POST", body: { status: "active" } }); toast(T("Published"), "good"); P.tab = "packs"; render(); } }, "✓ ", T("Publish"))),
    assign(d)))));
}

function tableMapping(t, out) {
  const opt = (sel) => h("select", h("option", { value: "" }, "–"), ...t.header.map((c, i) => h("option", { value: i, selected: sel === i }, c)));
  const cols = { prompt: opt(t.columns.prompt), answer: opt(t.columns.answer), unit: opt(t.columns.unit), image: opt(t.columns.image),
    sentence: opt(t.columns.sentence), hint: opt(t.columns.hint), also: opt(t.columns.also) };
  const meta = {
    titel: h("input", { type: "text", value: t.meta.titel }),
    fach: h("select", ...P.meta.subjects.map(s => h("option", { value: s.key, selected: s.key === t.meta.fach }, s.icon + " " + I18N.tr(s.name)))),
    stufe: h("input", { type: "text", value: t.meta.stufe }),
    sprache: h("input", { type: "text", value: t.meta.sprache, placeholder: "fr / en / it" }),
    privat: h("input", { type: "checkbox", checked: true }),
  };
  out.replaceChildren(section(T("Assign the columns"),
    h("p.small.muted", I18N.tr(T("{0} rows found.")).replace("{0}", t.count)),
    h("div.scroll", h("table.tbl", h("thead", h("tr", ...t.header.map(c => h("th", C(c))))), h("tbody", ...t.preview.map(r => h("tr", ...r.map(c => h("td", C(c)))))))),
    h("div.grid3",
      h("label.field", T("Question (what the child sees)"), cols.prompt), h("label.field", T("Answer"), cols.answer),
      h("label.field", T("Unit (optional)"), cols.unit), h("label.field", T("Picture or emoji (optional)"), cols.image),
      h("label.field", T("Sentence with gap (optional)"), cols.sentence), h("label.field", T("Hint (optional)"), cols.hint),
      h("label.field", T("Also correct (optional, separated by |)"), cols.also)),
    h("h3", T("Pack")),
    h("div.grid3", h("label.field", T("Title"), meta.titel), h("label.field", T("Subject"), meta.fach), h("label.field", T("Level"), meta.stufe),
      h("label.field", T("Language learnt"), meta.sprache), h("label.check", meta.privat, T("Private (from school material, never share)"))),
    h("div.row", h("button.btn", { onclick: build }, T("Create draft")),
      h("button.btn.ghost", { onclick: () => out.replaceChildren() }, T("Cancel")))));
  async function build() {
    const c = {}; for (const [k, s] of Object.entries(cols)) if (s.value !== "") c[k] = +s.value;
    const m = { titel: meta.titel.value, fach: meta.fach.value, stufe: meta.stufe.value, sprache: meta.sprache.value, privat: meta.privat.checked };
    const r = await call("parent/import/table", { method: "POST", body: { upload_id: t.upload_id, meta: m, columns: c } });
    showDrafts(r.drafts, out);
  }
}
