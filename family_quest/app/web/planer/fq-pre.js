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
