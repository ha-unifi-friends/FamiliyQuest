// kiosk: ?lang=fr-FR fixes the language of this screen (no language picker on a wall display) – runs before i18n.js
(() => { const l = new URLSearchParams(location.search).get("lang"); if (l) try { localStorage.setItem("familyquest.lang", JSON.stringify(l)); } catch {} })();
