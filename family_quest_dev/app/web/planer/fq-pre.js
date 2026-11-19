// Loaded BEFORE the planer bundle (family-planer-cards.js).
// The planer UI (taken over from Family Planer) knows German and English. In Family Quest:
//  - German / Swiss German → the planer's own German texts
//  - every other language  → the planer's English texts, translated by the Family Quest i18n system
//    (dictionaries i18n/planer/<lang>.json; the observer also looks into the planer's shadow roots)
//  - weekday and month names come from the browser (Intl) in the chosen language
"use strict";
window.FQ_PLANER_LANG = String(I18N.base || "de").startsWith("de") ? "de" : "en";

// FQN(kind, fallback): names in the Family Quest language (only used where the planer shows English)
window.FQN = (() => {
  const loc = I18N.locale;
  const fmt = (o, d) => { try { return new Intl.DateTimeFormat(loc, o).format(d); } catch { return null; } };
  const day = i => new Date(Date.UTC(2024, 0, 7 + i, 12));     // 7 Jan 2024 = Sunday
  const cap = s => s && s[0].toUpperCase() + s.slice(1);
  const make = {
    wdSun: () => [0, 1, 2, 3, 4, 5, 6].map(i => cap(fmt({ weekday: "long", timeZone: "UTC" }, day(i)))),
    wdMon: () => [1, 2, 3, 4, 5, 6, 0].map(i => cap(fmt({ weekday: "long", timeZone: "UTC" }, day(i)))),
    wd3Sun: () => [0, 1, 2, 3, 4, 5, 6].map(i => cap(fmt({ weekday: "short", timeZone: "UTC" }, day(i))).replace(/\.$/, "")),
    wd3Mon: () => [1, 2, 3, 4, 5, 6, 0].map(i => cap(fmt({ weekday: "short", timeZone: "UTC" }, day(i))).replace(/\.$/, "")),
    wd2Mon: () => [1, 2, 3, 4, 5, 6, 0].map(i => cap(fmt({ weekday: "short", timeZone: "UTC" }, day(i))).replace(/\.$/, "").slice(0, 2)),
    mon: () => [...Array(12).keys()].map(m => fmt({ month: "long", timeZone: "UTC" }, new Date(Date.UTC(2024, m, 15)))),
  };
  return (kind, fallback) => {
    if (I18N.base === "en" || window.FQ_PLANER_LANG !== "en") return fallback;
    try { const v = make[kind](); return v.every(Boolean) ? v : fallback; } catch { return fallback; }
  };
})();

// translate inside the shadow roots of the planer's web components
(() => {
  if (window.FQ_PLANER_LANG !== "en") return;
  const attach = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function (opts) {
    const root = attach.call(this, opts);
    I18N.observe(root);
    return root;
  };
})();

// parent area (planer?mode=parent): the planer's views in the look of the parent area – their shadow roots get a
// style sheet on top (adoptedStyleSheets stay when a view draws itself anew) with the colours, font and controls
// of Family Quest instead of the planer's own dark design
(() => {
  if (window.FQ_PLANER_MODE !== "parent" || !("adoptedStyleSheets" in Document.prototype)) return;
  const css = `
    .card{background:transparent!important;border:0!important;padding:0!important;color:var(--fg)!important;font-family:var(--font)!important;box-shadow:none!important}
    .title{color:var(--fg)!important}.subt,.rl,.hint,.muted{color:var(--muted)!important}.rl b{color:var(--fg)!important}
    .badge{background:color-mix(in srgb,var(--accent) 14%,transparent)!important;color:var(--accent)!important}
    .sec{color:var(--accent)!important}
    .ov{background:var(--card)!important;border:1px solid var(--line)!important}.ovh,.ovt{color:var(--muted)!important}.ovp{color:var(--fg)!important}
    .list{background:var(--card)!important;border-color:var(--line)!important}.row{border-color:var(--line)!important}
    .in,.sel,.fq,input,select,textarea{background:var(--card)!important;border:1px solid var(--line)!important;color:var(--fg)!important;border-radius:12px!important;font-family:var(--font)!important}
    .in:focus,.sel:focus,.fq:focus{border-color:var(--accent)!important}
    .hadd,.fc,.pre,.addb,.del,.btn,button.b{background:var(--card)!important;border:1px solid var(--line)!important;color:var(--fg)!important;font-family:var(--font)!important;border-radius:12px!important}
    .hadd ha-icon,.addb ha-icon{color:var(--accent)!important}
    .fc.on,.pre.on{border-color:var(--accent)!important;color:var(--accent)!important}.fc i{color:var(--muted)!important}
    .day{background:var(--card)!important;border-color:var(--line)!important;color:var(--muted)!important}
    .day.on{color:var(--c)!important;border-color:var(--c)!important;background:var(--cb)!important}
    .new,.nw,.newbox{border-color:var(--line)!important;background:transparent!important}
    .pn{color:var(--fg)!important}
    .fqe .head{margin:0 0 4px}.fqe .badge,.fqe .title,.fqe .hsp,.fqe .hadd{display:none!important}.fqe .subt{margin:0;font-size:14px}
    .fqe .sec,.card>h2,.card>h3{font-size:17px!important;font-weight:700!important;text-transform:none!important;letter-spacing:0!important;color:var(--fg)!important}
    .fqe .sec{margin:22px 0 10px}.fqe .add .sec{margin-top:0}.fqe .foot{color:var(--muted)!important}
    .fc,.fq,.pre,.sg,.sz,.pc,.tab,.tb,.addp,.chip,.seg button,.in,.sel,.t,.ib,button.add,.day{min-height:44px!important}
    .rmp,.x{min-width:44px!important;min-height:44px!important}
    .fqe .tl .in{min-width:0}.tb[data-chpin],.tb[data-lock]{display:none!important}
    @media (max-width:560px){.fqe .ar{flex-wrap:wrap}.fqe .ar .pn{flex:1;width:auto}.fqe .days{order:5;flex:1 1 100%;flex-wrap:nowrap}.fqe .day{flex:1 1 0;width:auto!important;min-width:0}}
  `;
  const sheet = new CSSStyleSheet();
  try { sheet.replaceSync(css); } catch { return; }
  const attach = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function (opts) {
    const root = attach.call(this, opts);
    try { root.adoptedStyleSheets = [...root.adoptedStyleSheets, sheet]; } catch {}
    return root;
  };
})();
