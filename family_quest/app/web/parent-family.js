// ---------------------------------------------------------------- 👨‍👩‍👧 Family: goals, family crest, the community page, family view, FamilyTime settings
// A part of the parent area (parent.js): loaded after it, before boot() runs (eltern.html).
"use strict";

// ---------------------------------------------------------------- goals
/** Family › 🎯 Goals: the running goals, «+ Add goal» / «+ Start family goal» (was its own page «Goals»). */
async function goalsSection() {
  const [goals, profiles, packs] = await Promise.all([call("parent/goals"), call("parent/profiles"), call("parent/packs")]);
  P.accounts = await call("parent/accounts");
  const kids = profiles.filter(p => p.role === "kid");
  const list = goals.map(g => {
    const kid = kids.find(k => k.id === g.profile_id);
    const pack = packs.packs.find(p => p.id === g.pack_id);
    const unit = pack && pack.units ? pack.units.find(u => u.id === g.unit_id) : null;
    return h("li.row", h("span.big-ic", g.kind === "family" ? "🤝" : "🎯"), h("div.grow",
      C(g.title || (pack ? pack.title + (unit ? " – " + unit.title : "") : ""), "strong"),
      h("div.small.muted", g.kind === "family" ? I18N.tr(T("Family goal")) + " · " + fmt(g.target) + " " + (g.account || "") : [C(kid ? kid.name : "?"), " · ", unit ? g.target + " ★" : g.target + " %"])),
      h("button.icon-btn", { title: T("Delete"), onclick: async () => { await call(`parent/goals/${g.id}`, { method: "DELETE" }); render(); } }, "✕"));
  });
  const f = { kid: h("select", ...kids.map(k => h("option", { value: k.id }, k.name))),
    pack: h("select", ...packs.packs.filter(p => p.kind === "pack" && p.status === "active").map(p => h("option", { value: p.id }, p.title))),
    unit: h("select"), target: h("input", { type: "number", min: 1, max: 100, value: 3 }), title: h("input", { type: "text", placeholder: T("e.g. French unit 3 done") }) };
  const fillUnits = () => { const p = packs.packs.find(x => x.id === f.pack.value); f.unit.replaceChildren(h("option", { value: "" }, I18N.tr(T("whole pack (%)"))), ...((p && p.units) || []).map(u => h("option", { value: u.id }, u.title))); };
  f.pack.addEventListener("change", fillUnits); fillUnits();
  const fg = { title: h("input", { type: "text", placeholder: T("e.g. pizza evening") }), account: h("select", ...P.accounts.filter(a => a.active).map(a => h("option", { value: a.key }, a.icon + " " + I18N.tr(a.name)))),
    target: h("input", { type: "number", min: 1, value: 2000 }) };
  const goalDialog = family => { const m = modal(h("div.form", family ? formFamily : formKid, h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))); };
  const formKid = h("div.form", h("h2", T("Weekly goal for a child")),
      h("div.grid3", h("label.field", T("Child"), f.kid), h("label.field", T("Pack"), f.pack), h("label.field", T("Unit"), f.unit),
        h("label.field", T("Target (stars or %)"), f.target), h("label.field", T("Title (optional)"), f.title)),
      h("button.btn", { onclick: async () => { await call("parent/goals", { method: "POST", body: { kind: "unit", profile_id: +f.kid.value, pack_id: f.pack.value,
        unit_id: f.unit.value || null, target: +f.target.value, title: f.title.value } }); document.querySelector(".modal-back")?.remove(); render(); } }, "💾 ", T("Add goal")));
  const formFamily = h("div.form", h("h2", T("Family goal")),
      h("div.grid3", h("label.field", T("What for?"), fg.title), h("label.field", T("Account"), fg.account), h("label.field", T("Target"), fg.target)),
      h("button.btn", { onclick: async () => { if (!fg.title.value) return fg.title.focus(); await call("parent/goals", { method: "POST", body: { kind: "family", title: fg.title.value,
        account: fg.account.value, target: +fg.target.value } }); document.querySelector(".modal-back")?.remove(); render(); } }, "💾 ", T("Start family goal")));
  const sec = sectionAdd("🎯 " + I18N.tr(T("Current goals")), [h("button.btn.small.ghost", { onclick: () => goalDialog(true) }, "+ ", T("Start family goal")),
      h("button.btn.small", { onclick: () => goalDialog(false) }, "+ ", T("Add goal"))],
    // empty: the row of the fold already says «No goals yet.» – here what to do
    goals.length ? h("ul.list", ...list) : h("p.muted", T("Set a goal for one child or start a family goal with the buttons above.")));
  sec.dataset.fold = "goals";
  sec.dataset.status = goals.length ? I18N.tr(T("Current goals")) + ": " + goals.length : I18N.tr(T("No goals yet."));
  return sec;
}

// family crest (Settings): drawn from colours, pattern and symbol – or an own picture
async function crestSection() {
  let d = { crest: null };
  try { d = await call("parent/memory"); } catch {}
  const crest = d.crest || { name: "", icon: "🏠", colors: ["#5b5bd6", "#fcc419"], pattern: "split", motto: "", image: null };
  let useCrest = !!d.crest;
  const preview = h("div.crest-prev");
  const drawCrest = () => preview.replaceChildren(useCrest ? crestSvg(crest) : h("p.small.muted", T("No family crest yet.")));
  const inp = (key, attrs = {}) => h("input", { type: "text", value: crest[key] || "", ...attrs, oninput: e => { crest[key] = e.target.value; drawCrest(); } });
  const color = i => h("input", { type: "color", value: crest.colors[i], oninput: e => { crest.colors[i] = e.target.value; drawCrest(); } });
  const PATTERNS = { plain: T("plain"), split: T("split"), quarter: T("quartered"), band: T("diagonal band"), chevron: T("chevron") };
  const save = async (quiet = false) => {
    try { d = await call("parent/memory", { method: "PUT", body: { crest: useCrest ? crest : null } }); if (!quiet) toast(T("Saved"), "good"); }
    catch (e) { toast(e.message, "bad"); }
  };
  const setImage = async ([n]) => { crest.image = n; drawCrest(); drawPictureRow(); await save(true); };
  const pictureRow = h("div.row.wrap");
  const drawnFields = h("div",
    h("div.grid2", h("label.field", T("Symbol (emoji)"), inp("icon", { maxlength: 8 })),
      h("label.field", T("Pattern"), h("select", { onchange: e => { crest.pattern = e.target.value; drawCrest(); } },
        ...Object.entries(PATTERNS).map(([k, n]) => h("option", { value: k, selected: crest.pattern === k }, I18N.tr(n)))))),
    h("label.field", T("Colours"), h("div.row", color(0), color(1))));
  const drawPictureRow = () => { drawnFields.hidden = !!crest.image; pictureRow.replaceChildren(...[
    h("button.btn.small.ghost", { onclick: () => Photos.pick(false, setImage, 800) }, "📷 ", T("Upload picture")),
    crest.image ? h("button.btn.small.ghost", { onclick: () => { crest.image = null; drawCrest(); drawPictureRow(); } }, "✕ ", T("Remove picture")) : null].filter(Boolean)); };
  const crestForm = h("div.form",
    h("label.field", T("Family name"), inp("name", { maxlength: 40, placeholder: T("e.g. Miller") })),
    h("div.field", h("span", T("Own picture as crest"), fieldInfo(T("A photo or drawing of your crest – it is shown in the shield. Without a picture the crest is drawn from colours, pattern and symbol."))), pictureRow),
    drawnFields);
  const onOff = h("input", { type: "checkbox", checked: useCrest, onchange: e => { useCrest = e.target.checked; crestForm.hidden = !useCrest; drawCrest(); } });
  crestForm.hidden = !useCrest;
  drawCrest(); drawPictureRow();
  return section("🛡️ " + I18N.tr(T("Family crest")),
    h("label.check", onOff, h("span", T("We have a family crest"))),
    h("div.crest-edit", preview, crestForm),
    h("div.row", h("button.btn", { onclick: () => save() }, "💾 ", T("Save"))));
}

// ---------------------------------------------------------------- community: family council, polls, Wichteln, history (the games: gamesView)
async function communityView(main) {
  const me = P.meta.me;
  const [profiles, s, mem] = await Promise.all([call("parent/profiles"), call("parent/settings"), call("parent/memory").catch(() => null)]);
  const t = k => I18N.tr(k), f = (k, ...v) => v.reduce((a, x, i) => a.split("{" + i + "}").join(String(x)), I18N.tr(k));
  const mark = (sec, id, status) => { if (sec) { sec.dataset.fold = id; if (status != null) sec.dataset.status = status; } return sec; };
  // the same folds as the settings: groups with their ⓘ, every box folded with a short status in its row
  const group = setGroup;
  const price = s.familytime_game_price ?? 150, c = mem && mem.crest;
  const vis = { percent: T("Only percentages"), goal: T("Only the family goal") }[s.family_visibility] || T("Everything");
  main.append(h("h1", T("Family")),
    group("Goals", "🎯", T("Goals")), mark(await goalsSection(), "goals"),
    group("fam.together", "🤝", T("Together")),
    mark(await familyTimeSection(me, { settings: redraw => familyTimeSettings(redraw, true) }), "familytime",
      s.familytime_wishes === false ? t(T("Game wishes off")) : price > 0 ? f(T("Game wishes on · fix a game: {0} coins"), price) : t(T("Game wishes on"))),
    mark(await councilSection(me), "council"), mark(await pollsSection(me), "polls"),
    mark(await boardsSection(me, (id, refresh) => { const b = h("div"); document.body.append(b); boardLive(b, me, id, () => { b.remove(); refresh(); }); }), "boards"),
    mark(await wichtelnSection(me), "wichteln"),
    group("Deals", "💱", T("Deals")), ...(await dealsFamilySections().catch(() => [])),
    group("fam.ours", "🏡", T("Our family")),
    mark(await storiesSection(), "library"),
    mark(await crestSection(), "crest", !c ? t(T("No family crest")) : [t(c.image ? T("Own picture") : T("Drawn crest")), c.name || null].filter(Boolean).join(" · ")),
    mark(familyViewSection(s), "view", f(T("Comparison: {0}"), t(vis)) + " · " + t(s.sound !== false ? T("Sound on") : T("Sound off"))));
  foldBoxes(main, "fam", sec => {
    // lists with «Active / Closed»: how many of each; the bookshelf: how many books are on it
    const seg = sec.querySelectorAll(".inst-filter .inst-n");
    if (seg.length === 2) return t(T("Active")) + " " + seg[0].textContent + " · " + t(T("Closed")) + " " + seg[1].textContent;
    if (sec.dataset.fold === "library") return t(T("On the shelf")) + ": " + sec.querySelectorAll(".sb-shelf > *").length;
    return "";
  });
}

/** Family › Family view: what children see in the comparison, the sound (was a part of the settings). */
function familyViewSection(s) {
  const vis = h("select", ...[["all", T("Everything")], ["percent", T("Only percentages")], ["goal", T("Only the family goal")]].map(([k, n]) => h("option", { value: k, selected: s.family_visibility === k }, n)));
  const sound = h("input", { type: "checkbox", checked: s.sound !== false });
  return section("👀 " + I18N.tr(T("Family view")), h("label.field", T("What children see in the comparison"), vis), h("label.check", sound, T("Sound on by default")),
    h("div.row", h("button.btn", { onclick: async () => {
      try { await call("parent/settings", { method: "PUT", body: { family_visibility: vis.value, sound: sound.checked } }); toast(T("Saved"), "good"); } catch {}
    } }, "💾 ", T("Save"))));
}

// FamilyTime games (community.js familyTimeSection): on/off, the coin price of «fix a game», when the wishes close –
// in the «Family» tab (`inBox`: a small ⚙️ box at the end of the section) and in «Settings» (own section)
function familyTimeSettings(after = null, inBox = false) {
  const box = h("div" + (inBox ? ".game-settings.ftg-settings" : ""), h("p.small.muted", "…"));
  call("parent/settings").then(s => {
    const on = h("input", { type: "checkbox", checked: s.familytime_wishes !== false });
    const price = h("input", { type: "number", min: 0, max: 10000, value: s.familytime_game_price ?? 150 });
    const hours = h("input", { type: "number", min: 0, max: 336, value: s.familytime_vote_hours ?? 24 });
    const save = async () => {
      await call("parent/settings", { method: "PUT", body: { familytime_wishes: on.checked,
        familytime_game_price: Math.max(0, Math.min(10000, Math.round(+price.value || 0))),
        familytime_vote_hours: Math.max(0, Math.min(336, Math.round(+hours.value || 0))) } });
      toast(T("Saved"), "good"); if (after) after();
    };
    box.replaceChildren(inBox ? h("div.small.muted.game-settings-h", "⚙️ ", T("Settings")) : null,
      h("label.check", on, T("Game wishes for FamilyTime (wishes, vote, buying a game)")),
      h("div.field-row",
        h("label.field", h("span", "🪙 ", T("Fix a game: price in coins"), fieldInfo(T("A child pays this to set the game of a FamilyTime that has none yet. 0 = buying is off."))), price),
        h("label.field", h("span", "⏰ ", T("Wishes close (hours before)"), fieldInfo(T("Then the vote starts by itself – one wish is set directly."))), hours)),
      h("button.btn.small", { onclick: () => save().catch(() => {}) }, "💾 ", T("Save")));
  }).catch(() => box.replaceChildren());
  return box;
}
