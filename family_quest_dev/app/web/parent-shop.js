// ---------------------------------------------------------------- 🛒 Shop: own rewards and every avatar item
// A part of the parent area (parent.js): loaded after it, before boot() runs (eltern.html).
"use strict";

// ---------------------------------------------------------------- shop: own rewards on top, then every avatar item
async function shopSettingsView(main) {
  const scratch = h("div");
  const { rewardBox, rewardCard } = await rewardsView(scratch, { onlyShop: true });
  const d = await call("parent/shop/items");
  const SLOT_NAMES = { background: T("Background"), hat: T("Hat"), hairclip: T("Hair clip"), eyewear: T("Glasses"), face: T("Face"), teeth: T("Teeth"),
    ear: T("Ears"), neck: T("Neck"), suit: T("Clothes"), figure: T("Figure"), back: T("On the back"), hand: T("In the hand"), pet: T("Pet") };
  const howText = b => b.free ? T("free") : b.level ? I18N.tr(T("From level {0}")).replace("{0}", b.level) : b.badge ? T("With a badge")
    : b.season ? T("Only in season") : b.xp ? b.xp + " " + I18N.tr(T("new XP")) : b.cost != null ? b.cost + " 🪙" : "";
  const row = it => {
    const o = it.override || {};
    const base = it.base, baseCur = base.xp ? "xp" : "coins", basePrice = base.xp ?? base.cost ?? null;
    const f = { on: h("input", { type: "checkbox", checked: !o.off, "aria-label": T("In the shop") }),
      price: h("input", { type: "number", min: 0, max: 100000, value: o.price ?? "", placeholder: basePrice != null ? String(basePrice) : "–", "aria-label": T("Price") }),
      cur: h("select", { "aria-label": T("Paid with") }, h("option", { value: "" }, I18N.tr(T("as in the app")) + " (" + (baseCur === "xp" ? "✨ XP" : "🪙") + ")"),
        h("option", { value: "coins", selected: o.currency === "coins" }, "🪙 " + I18N.tr(T("Coins"))),
        h("option", { value: "xp", selected: o.currency === "xp" }, "✨ " + I18N.tr(T("new XP")))) };
    const tr = h("tr" + (o.off ? ".off" : ""));
    const save = async () => {
      try {
        const r = await call(`parent/shop/items/${encodeURIComponent(it.id)}`, { method: "PUT",
          body: { off: !f.on.checked, price: f.price.value === "" ? null : +f.price.value, currency: f.cur.value || null } });
        tr.classList.toggle("off", !f.on.checked); toast(T("Saved"), "good"); it.override = r.override;
      } catch (e) { toast(e.message, "bad"); }
    };
    Object.values(f).forEach(x => x.addEventListener("change", save));
    tr.append(h("td", avatarSvg({ ...DEFAULT_AV, items: { [it.slot]: it.id } }, 44)), h("td", C(I18N.tr(it.name), "strong"), h("div.small.muted", SLOT_NAMES[it.slot] || it.slot)),
      h("td.small.muted", howText(base)), h("td.c", f.on), h("td.num", f.price), h("td", f.cur));
    return tr;
  };
  const DEFAULT_AV = { skin: "#f1c27d", hair: "short", hairColor: "#6b3e1f", eyes: "round", mouth: "smile", outfit: "tshirt", outfitColor: "#4f8cff", items: {} };
  const bySlot = d.slots.map(sl => [sl, d.items.filter(i => i.slot === sl)]).filter(([, l]) => l.length);
  // search: own rewards (name) and avatar items (name, kind) – matching groups open, the others hide
  const search = h("input.pack-search", { type: "search", placeholder: "🔍 " + I18N.tr(T("Search the shop …")), value: P.shopSearch || "",
    "aria-label": T("Search the shop …"), oninput: () => { P.shopSearch = search.value; filterShop(); } });
  const noShop = noMatch(T("Nothing found in the shop"), () => { search.value = ""; P.shopSearch = ""; filterShop(); });
  const filterShop = () => {
    const q = (search.value || "").trim().toLowerCase();
    main.querySelectorAll(".reward-ed").forEach(c => { c.hidden = !!q && ![...c.querySelectorAll("input")].some(i => (i.value || "").toLowerCase().includes(q)); });
    const rf = rewardBox.closest("details.set-fold");
    if (rf) { const any = [...rewardBox.querySelectorAll(".reward-ed")].some(c => !c.hidden); rf.hidden = !!q && !any; if (q && any) rf.open = true; }
    main.querySelectorAll("details.shop-slot").forEach(dt => {
      const rows = [...dt.querySelectorAll("tbody tr")];
      rows.forEach(r => { r.hidden = !!q && !r.textContent.toLowerCase().includes(q) && !dt.querySelector("summary").textContent.toLowerCase().includes(q); });
      const any = rows.some(r => !r.hidden);
      dt.hidden = !!q && !any;
      if (q && any) dt.open = true;
    });
    noShop.hidden = !q || [...main.querySelectorAll(".reward-ed, details.shop-slot")].some(x => !x.hidden);
  };
  setTimeout(filterShop);
  main.append(pageHead(T("Shop")), search, noShop,
    sectionAdd("🎁 " + I18N.tr(T("Own rewards")), h("button.btn.small", { onclick: () => rewardBox.prepend(rewardCard({ name: "", kind: "voucher", account: "coins", cost: 50, approval: 1, weekly_limit: null, icon: "🎁", config: {}, active: 1 })) }, "+ ", T("Add reward")),
      rewardBox),
    // the avatar items: one folded box per kind (background, hat, …) under their group heading – like every fold
    h("h2.set-group", { "data-ik": "Avatar items" }, "🧑‍🎨 ", T("Avatar items")),
    ...bySlot.map(([sl, list]) => {
      const off = list.filter(i => i.override && i.override.off).length;
      const d = setFold("shop." + sl, SLOT_NAMES[sl] || sl, h("section.card.sec",
        // phones: every item a small card (stack) – no table to scroll sideways, the «Paid with» choice readable
        h("div.scroll", stackTable(h("table.tbl.stack.shop-tbl", h("thead", h("tr", h("th"), h("th", T("Item")), h("th", T("In the app")), h("th", T("In the shop")), h("th", T("Price")), h("th", T("Paid with")))),
          h("tbody", ...list.map(row)))))));
      d.classList.add("shop-slot");
      d.querySelector(".set-status").textContent = I18N.tr(T("Items: {0}")).replace("{0}", list.length) + (off ? " · " + I18N.tr(T("switched off: {0}")).replace("{0}", off) : "");
      return d;
    }));
  foldBoxes(main, "shop", () => I18N.tr(T("Rewards: {0}")).replace("{0}", rewardBox.children.length));
}
