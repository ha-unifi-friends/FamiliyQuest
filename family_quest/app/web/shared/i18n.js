// ---------- translations: English is the source; other languages come from i18n/<lang>.json ----------
// Taken over from ha-unifi-friends/ha-ip-manager-unifi (MIT) so both apps translate the same way:
// Text nodes and title/placeholder/aria-label/alt attributes are translated as they appear (MutationObserver).
// Keys may contain {0},{1}… for interpolated parts; those parts are translated again where possible.
// Learning content, names and pack titles carry translate="no" and are never touched.
window.T = s => s; // marks English source text for tools/i18n_extract.py – the DOM observer translates it
window.I18N = (() => {
  "use strict";
  const LANGS = [["auto", "Auto"], ["en", "English"], ["de-DE", "Deutsch"], ["de-CH", "Schwiizerdütsch"], ["fr-FR", "Français"], ["it-IT", "Italiano"], ["es-ES", "Español"], ["nl-NL", "Nederlands"], ["pl-PL", "Polski"], ["pt-BR", "Português (Brasil)"], ["sv-SE", "Svenska"]];
  const BASE = { en: "en", de: "de-DE", fr: "fr-FR", it: "it-IT", es: "es-ES", nl: "nl-NL", pl: "pl-PL", pt: "pt-BR", sv: "sv-SE" }; // "Auto": Swiss German Mundart only when chosen explicitly
  let pref = "auto"; try { pref = JSON.parse(localStorage.getItem("familyquest.lang")) || "auto"; } catch {}
  if (BASE[pref] && pref !== "en") pref = BASE[pref];
  const auto = () => { for (const l of navigator.languages || [navigator.language || "en"]) { const b = BASE[String(l).toLowerCase().split("-")[0]]; if (b) return b; } return "en"; };
  const lang = pref === "auto" ? auto() : pref;
  // own languages of the family ("x-…"): built on a base language, remembered with the choice
  let base = lang; if (/^x-/.test(lang)) { try { base = JSON.parse(localStorage.getItem("familyquest.langbase")) || "de-DE"; } catch { base = "de-DE"; } }
  const custom = [];   // [{code, name, base, flag}] from i18n/languages.json
  let active = lang !== "en";   // English is the source – only translated when the family has own English texts
  const exact = new Map(), byPrefix = new Map(), generic = [];
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  function load(dict) {
    for (const [k, v] of Object.entries(dict)) {
      if (!v || v === k) continue;
      exact.set(k, v);                     // also a template itself: I18N.tr(T("{0} rooms")) → "{0} salles" (short keys have no pattern)
      if (!/\{\d+\}/.test(k)) continue;
      const order = [], re = new RegExp("^" + k.split(/(\{\d+\})/).map(p => { const m = p.match(/^\{(\d+)\}$/); if (m) { order.push(+m[1]); return "(.*?)"; } return esc(p); }).join("") + "$", "s");
      const parts = k.split(/\{\d+\}/), pre = parts[0], ent = { re, order, v, statics: parts.filter(Boolean).sort((a, b) => b.length - a.length), weight: parts.join("").replace(/\s/g, "").length };
      if (pre.length >= 2) { const b = pre.slice(0, 2); (byPrefix.get(b) || byPrefix.set(b, []).get(b)).push(ent); }
      else if (ent.weight >= 6) generic.push(ent); // "{0} of {1}" alone would match far too much
    }
  }
  function tryPattern(ent, s, depth) {
    if (ent.statics[0] && !s.includes(ent.statics[0])) return null;
    const m = s.match(ent.re); if (!m) return null;
    const val = {}; ent.order.forEach((n, i) => { val[n] = m[i + 1]; });
    const part = x => { const y = tr(x, depth + 1); if (y !== x || !/ [+·] /.test(x)) return y; return x.split(/( [+·] )/).map((q, i) => i % 2 ? q : tr(q, depth + 1)).join(""); };
    return ent.v.replace(/\{(\d+)\}/g, (_, n) => val[n] == null ? "" : part(val[n]));
  }
  function tr(s, depth = 0) {
    if (!active || !s || depth > 4) return s;
    const t = s.trim(); if (!t || !/[A-Za-z]/.test(t)) return s;
    const lead = s.slice(0, s.indexOf(t[0])), trail = s.slice(s.indexOf(t[0]) + t.length);
    let r = exact.get(t);
    if (r == null && t.length < 400) {
      // the most specific matching pattern wins (most fixed text)
      let best = null;
      for (const ent of [...(byPrefix.get(t.slice(0, 2)) || []), ...generic]) if ((!best || ent.weight > best.weight) && (ent.statics[0] ? t.includes(ent.statics[0]) : true) && ent.re.test(t)) best = ent;
      if (best) r = tryPattern(best, t, depth);
      if (r == null) { // "5 min", "+10 XP", "· done"
        let m = t.match(/^([\d.,:%/–+\- ]+)\s(.+)$/); if (m && exact.has(m[2])) r = m[1] + " " + exact.get(m[2]);
        else if ((m = t.match(/^(.*?[A-Za-z)])\s+([\d.,:%/–\- ]+)$/)) && exact.has(m[1])) r = exact.get(m[1]) + " " + m[2];
        else if ((m = t.match(/^([·•–→↻✓]\s*)(.+)$/)) && exact.has(m[2])) r = m[1] + exact.get(m[2]);
        else if ((m = t.match(/^([^\p{L}\p{N}"„«(]+\s)(.+)$/u)) && m[2] !== t) { const x = tr(m[2], depth + 1); if (x !== m[2]) r = m[1] + x; } // "🍂 Autumn"
      }
    }
    if (r == null && depth < 4 && /^[A-Z][a-z]/.test(t)) { // "Save the pack …" built from "save the pack …"
      const low = t[0].toLowerCase() + t.slice(1), x = tr(low, depth + 1); if (x !== low) r = x[0].toUpperCase() + x.slice(1);
    }
    return r == null ? s : lead + r + trail;
  }
  const mine = new WeakMap(), mineAttr = new WeakMap(); // text nodes / attributes we wrote – not translated again
  const SKIP = "script,style,code,textarea,input,.mono,[translate=no]";
  const ATTRS = ["title", "placeholder", "aria-label", "alt"];
  function el(e) {
    if (e.closest("[translate=no]")) return;
    const w = mineAttr.get(e) || {};
    for (const a of ATTRS) { const v = e.getAttribute(a); if (!v || w[a] === v) continue; const n = tr(v); if (n !== v) { w[a] = n; e.setAttribute(a, n); } }
    mineAttr.set(e, w);
  }
  function node(n) {
    if (n.nodeType === 3) { const p = n.parentElement; if (!p || p.closest(SKIP)) return; const v = n.nodeValue; if (mine.get(n) === v) return; const x = tr(v); if (x !== v) { n.nodeValue = x; mine.set(n, x); } return; }
    if (n.nodeType !== 1) return;
    el(n);
    const w = document.createTreeWalker(n, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, { acceptNode: x => x.nodeType === 1 && x.matches("[translate=no]") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
    for (let x = w.nextNode(); x; x = w.nextNode()) x.nodeType === 3 ? node(x) : el(x);
  }
  let on = false;
  function start() {
    if (on || !active) return; on = true;
    node(document.body); document.title = tr(document.title);
    new MutationObserver(ms => { for (const m of ms) {
      if (m.type === "childList") m.addedNodes.forEach(node);
      else if (m.type === "characterData") node(m.target);
      else if (m.type === "attributes") el(m.target);
    } }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  }
  const ver = document.documentElement.dataset.version || "";
  // window.I18N_EXTRA = ["planer"] (set before this script) also loads i18n/planer/<lang>.json
  const get = u => fetch(u).then(r => r.ok ? r.json() : {}).catch(() => ({}));
  // (not for German and Swiss German: the planer shows its own German texts there – planer/fq-pre.js – no dictionary to fetch)
  const extra = /^de/.test(base) ? [] : (window.I18N_EXTRA || []);
  const dicts = lang === "en" ? [] : ["i18n/" + lang + ".json", ...extra.map(d => "i18n/" + d + "/" + lang + ".json")].map(u => u + "?v=" + encodeURIComponent(ver));
  const languages = get("i18n/languages.json").then(ls => { if (Array.isArray(ls)) custom.push(...ls); return custom; });
  // the family's own texts come last, so they win over the built-in dictionaries
  const ready = Promise.all([...dicts.map(get), get("i18n/custom/" + lang + ".json")])
    .then(ds => { ds.forEach(load); if (Object.keys(ds[ds.length - 1] || {}).length) active = true; }).catch(() => {});
  document.documentElement.lang = lang;
  if (lang !== "en") document.documentElement.classList.add("i18n-wait");
  ready.then(() => { const go = () => { start(); document.documentElement.classList.remove("i18n-wait"); }; document.body ? go() : document.addEventListener("DOMContentLoaded", go); });
  setTimeout(() => document.documentElement.classList.remove("i18n-wait"), 1500);
  const locale = base === "en" ? "en-GB" : base;
  // shadow roots (the planer's web components): translate what is there and whatever is added later
  function observe(root) {
    if (!root) return;
    ready.then(() => {
      if (!active) return;
      root.childNodes.forEach(node);
      new MutationObserver(ms => { for (const m of ms) {
        if (m.type === "childList") m.addedNodes.forEach(node);
        else if (m.type === "characterData") node(m.target);
        else if (m.type === "attributes") el(m.target);
      } }).observe(root, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
    });
  }
  return { LANGS, lang, base, pref, tr, locale, ready, observe, custom, languages, set(l, b) {
    try { localStorage.setItem("familyquest.lang", JSON.stringify(l)); if (b) localStorage.setItem("familyquest.langbase", JSON.stringify(b)); } catch {}
    location.reload(); } };
})();

// ---------- language picker: flags (SVG, so they look the same on every OS) ----------
let flagN = 0;
function flagSvg(k) {
  const W = 'viewBox="0 0 60 40" class="flag" aria-hidden="true"';
  if (k === "auto") return '<svg viewBox="0 0 24 24" class="flag globe" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>';
  if (k === "en") { const id = "uk" + (++flagN); return `<svg ${W} preserveAspectRatio="none"><clipPath id="${id}"><path d="M30 20h30v20zv20H0zH0V0zV0h30z"/></clipPath><rect width="60" height="40" fill="#012169"/><path d="M0 0l60 40M60 0L0 40" stroke="#fff" stroke-width="8"/><path d="M0 0l60 40M60 0L0 40" clip-path="url(#${id})" stroke="#C8102E" stroke-width="4"/><path d="M30 0v40M0 20h60" stroke="#fff" stroke-width="12"/><path d="M30 0v40M0 20h60" stroke="#C8102E" stroke-width="7"/></svg>`; }
  if (k === "de-DE") return `<svg ${W}><rect width="60" height="13.4" fill="#000"/><rect y="13.3" width="60" height="13.4" fill="#DD0000"/><rect y="26.6" width="60" height="13.4" fill="#FFCE00"/></svg>`;
  if (k === "de-CH") return `<svg ${W}><rect width="60" height="40" fill="#DA291C"/><path d="M26 9h8v7h7v8h-7v7h-8v-7h-7v-8h7z" fill="#fff"/></svg>`;
  if (k === "fr-FR") return `<svg ${W}><rect width="20" height="40" fill="#002395"/><rect x="20" width="20" height="40" fill="#fff"/><rect x="40" width="20" height="40" fill="#ED2939"/></svg>`;
  if (k === "it-IT") return `<svg ${W}><rect width="20" height="40" fill="#009246"/><rect x="20" width="20" height="40" fill="#fff"/><rect x="40" width="20" height="40" fill="#CE2B37"/></svg>`;
  if (k === "nl-NL") return `<svg ${W}><rect width="60" height="13.4" fill="#AE1C28"/><rect y="13.3" width="60" height="13.4" fill="#fff"/><rect y="26.6" width="60" height="13.4" fill="#21468B"/></svg>`;
  if (k === "pl-PL") return `<svg ${W}><rect width="60" height="20" fill="#fff"/><rect y="20" width="60" height="20" fill="#DC143C"/></svg>`;
  if (k === "pt-BR") return `<svg ${W}><rect width="60" height="40" fill="#009C3B"/><path d="M30 5 54 20 30 35 6 20z" fill="#FFDF00"/><circle cx="30" cy="20" r="8.5" fill="#002776"/><path d="M21.8 18.3q8.5-1.6 16.4 3" stroke="#fff" stroke-width="1.6" fill="none"/></svg>`;
  if (k === "sv-SE") return `<svg ${W}><rect width="60" height="40" fill="#006AA7"/><rect x="17" width="8" height="40" fill="#FECC00"/><rect y="16" width="60" height="8" fill="#FECC00"/></svg>`;
  if (k === "es-ES") return `<svg ${W}><rect width="60" height="40" fill="#AA151B"/><rect y="10" width="60" height="20" fill="#F1BF00"/></svg>`;
  return "";
}

// <span class="lang-wrap"> with a flag button and a menu (flag + name, 🌐 = Auto)
function langPicker() {
  const wrap = document.createElement("span");
  wrap.className = "lang-wrap";
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const cust = I18N.custom.find(l => l.code === I18N.pref);
  const cur = cust ? [cust.code, cust.name] : I18N.LANGS.find(([k]) => k === I18N.pref) || I18N.LANGS[0];
  wrap.innerHTML = `<button type="button" class="icon-btn lang-btn" aria-haspopup="menu" aria-expanded="false" title="${esc(I18N.tr(T("Language: {0}")).replace("{0}", cur[1]))}" aria-label="${esc(I18N.tr(T("Language: {0}")).replace("{0}", cur[1]))}">${cust ? `<span class="emoji-flag">${esc(cust.flag || "🗣️")}</span>` : flagSvg(cur[0])}</button><div class="lang-menu" role="menu" hidden></div>`;
  const btn = wrap.firstChild, menu = wrap.lastChild;
  const fill = () => { menu.innerHTML = I18N.LANGS.map(([k, n]) => `<button type="button" role="menuitemradio" data-lang="${k}" aria-checked="${k === I18N.pref}" translate="no">${flagSvg(k)}<span>${k === "auto" ? "Auto" : n}</span><svg class="ck" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m5 12 5 5 9-10"/></svg></button>`).join("") +
    I18N.custom.map(l => `<button type="button" role="menuitemradio" data-lang="${esc(l.code)}" data-base="${esc(l.base)}" aria-checked="${l.code === I18N.pref}" translate="no"><span class="emoji-flag">${esc(l.flag || "🗣️")}</span><span>${esc(l.name)}</span><svg class="ck" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m5 12 5 5 9-10"/></svg></button>`).join(""); };
  fill(); I18N.languages.then(() => { fill(); if (cust == null && I18N.custom.some(l => l.code === I18N.pref)) { const l = I18N.custom.find(x => x.code === I18N.pref); btn.innerHTML = `<span class="emoji-flag">${esc(l.flag || "🗣️")}</span>`; btn.title = I18N.tr(T("Language: {0}")).replace("{0}", l.name); } });
  const close = () => { menu.hidden = true; btn.setAttribute("aria-expanded", "false"); };
  btn.addEventListener("click", e => { e.stopPropagation(); menu.hidden = !menu.hidden; btn.setAttribute("aria-expanded", String(!menu.hidden)); });
  menu.addEventListener("click", e => { const b = e.target.closest("[data-lang]"); if (!b) return; close(); if (b.dataset.lang !== I18N.pref) I18N.set(b.dataset.lang, b.dataset.base); });
  const onClick = e => { if (!wrap.isConnected) return off(); if (!wrap.contains(e.target)) close(); };
  const onKey = e => { if (!wrap.isConnected) return off(); if (e.key === "Escape") close(); };
  const off = () => { document.removeEventListener("click", onClick); document.removeEventListener("keydown", onKey); };
  document.addEventListener("click", onClick);
  document.addEventListener("keydown", onKey);
  return wrap;
}

// a language name inside a sentence: «Contenu en allemand» – lower case where the language writes it so (not de, en, nl)
function langInText(name) {
  const b = String(I18N.base || I18N.lang || "").split("-")[0];
  return ["fr", "it", "es", "pl", "pt", "sv"].includes(b) ? String(name).toLowerCase() : name;
}
