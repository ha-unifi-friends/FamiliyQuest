// ---------------------------------------------------------------- 📷 Photos: made smaller in the browser, Home Assistant Media picker, file dialog (learning packs, photo sets, crest)
// A part of the parent area (parent.js): loaded after it, before boot() runs (eltern.html).
"use strict";

// Phone photos are large: scale down to max. 1024 px as JPEG before uploading.
// photos made smaller (and turned into JPEG) in the browser before the upload – also iPhone photos (HEIC), which Safari can read
async function shrinkPhoto(file, max = 1024, { short = false } = {}) {
  if (file.type === "image/gif") return file;                       // keep animations
  const heic = /hei[cf]$/i.test(file.type) || /\.hei[cf]$/i.test(file.name || "");
  if (!/^image\//.test(file.type) && !heic) return file;
  const decode = async () => {
    try { return await createImageBitmap(file); } catch {}
    const url = URL.createObjectURL(file);                          // fallback: some browsers only decode through <img>
    try { const img = new Image(); img.src = url; await img.decode(); return img; } finally { setTimeout(() => URL.revokeObjectURL(url), 1000); }
  };
  try {
    const bmp = await decode();
    const w0 = bmp.width || bmp.naturalWidth, h0 = bmp.height || bmp.naturalHeight;
    const k = Math.min(1, max / (short ? Math.min(w0, h0) : Math.max(w0, h0)));   // short: the shorter edge counts
    const cv = h("canvas", { width: Math.round(w0 * k), height: Math.round(h0 * k) });
    cv.getContext("2d").drawImage(bmp, 0, 0, cv.width, cv.height);
    const alpha = /^image\/(png|webp)$/.test(file.type);          // keep transparency (a drawn crest) – photos become JPEG
    return await new Promise(res => cv.toBlob(b => res(b || file), alpha ? "image/png" : "image/jpeg", 0.85));
  } catch {
    if (heic) throw new Error(I18N.tr(T("This photo format cannot be read – please use JPEG or PNG.")));
    return file;
  }
}

// ---------------------------------------------------------------- pairs game: own photo sets and the family crest
// pick pictures from Home Assistant Media (Media → My media, mapped read-only): folders, thumbnails, choose
const MAX_PICK = 40;                                           // as many as a photo set holds (memorygame.MAX_PHOTOS)
async function haMediaPicker({ single = false } = {}) {
  return new Promise(resolve => {
    let picked = new Set(), cur = "", data = null, done = false;
    const body = h("div.hm-body"), foot = h("div.row");
    const finish = v => { if (done) return; done = true; if (seen) seen.disconnect(); m.close(); resolve(v);
      setTimeout(() => urls.forEach(p => p.then(u => u && URL.revokeObjectURL(u))), 5000); };
    const urls = new Map();                                    // thumbnails loaded once (the parent header cannot go into <img src>)
    const load = (el, rel) => {
      if (!urls.has(rel)) urls.set(rel, fetch("api/parent/ha-media/file?path=" + encodeURIComponent(rel), { headers: { "X-FQ-Parent": Auth.parent } })
        .then(r => r.ok ? r.blob() : null).then(b => b ? URL.createObjectURL(b) : null).catch(() => null));
      urls.get(rel).then(u => { if (u) el.src = u; });
    };
    // only the pictures that come into view are loaded – a camera folder with hundreds of photos stays light
    const seen = "IntersectionObserver" in window ? new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) { seen.unobserve(e.target); load(e.target, e.target.dataset.rel); }
    }), { rootMargin: "200px" }) : null;
    const thumb = (img, rel) => {
      const el = h("img", { alt: "" });
      el.dataset.rel = rel;
      if (seen) seen.observe(el); else load(el, rel);
      return el;
    };
    const drawFoot = () => foot.replaceChildren(...[
      !single && data && data.images.length ? h("button.btn.ghost.small", { onclick: () => {
        const all = data.images.map(x => (cur ? cur + "/" : "") + x.name).slice(0, MAX_PICK);
        picked = picked.size === all.length ? new Set() : new Set(all); draw(); } }, T("Select all")) : null,
      !single && picked.size >= MAX_PICK ? h("span.small.muted", I18N.tr(T("At most {0} pictures at once")).replace("{0}", MAX_PICK)) : null,
      h("span.grow"), h("button.btn.ghost", { onclick: () => finish(null) }, T("Cancel")),
      single ? null : h("button.btn", { disabled: !picked.size, onclick: () => finish([...picked]) }, "✓ ", I18N.tr(T("Add ({0})")).replace("{0}", picked.size))].filter(Boolean));
    const draw = () => {
      if (!data) return;
      if (!data.available) {
        body.replaceChildren(h("p", T("No Home Assistant Media found.")),
          h("p.small.muted", T("Put photos into Home Assistant → Media → My media (e.g. with the File editor, Samba or the upload in the Media browser). After an update of the app, restart it once so it can see the folder.")));
        return drawFoot();
      }
      const parts = cur ? cur.split("/") : [];
      body.replaceChildren(...[
        h("div.hm-crumbs", h("button.link", { onclick: () => open("") }, "🏠 ", T("My media")),
          ...parts.map((p, i) => [" / ", h("button.link", { onclick: () => open(parts.slice(0, i + 1).join("/")) }, C(p))])),
        data.folders.length ? h("div.hm-folders", ...data.folders.map(f => h("button.hm-folder", { onclick: () => open((cur ? cur + "/" : "") + f) }, "📁 ", C(f)))) : null,
        data.images.length ? h("div.hm-grid", ...data.images.map(x => {
          const rel = (cur ? cur + "/" : "") + x.name;
          return h("button.hm-pic" + (picked.has(rel) ? ".on" : ""), { title: x.name, onclick: () => {
            if (single) return finish([rel]);
            if (picked.has(rel)) picked.delete(rel); else if (picked.size < MAX_PICK) picked.add(rel);
            draw(); } }, thumb(x, rel));
        })) : !data.folders.length ? h("p.small.muted", T("No pictures in this folder.")) : null].filter(Boolean));
      drawFoot();
    };
    const open = async path => {
      cur = path; body.replaceChildren(h("div.spinner"));
      try { data = await call("parent/ha-media?path=" + encodeURIComponent(path)); cur = data.path || ""; } catch { data = { available: true, path: cur, folders: [], images: [] }; }
      draw();
    };
    const m = modal(h("div", h("div.sec-head", h("h2", "🏠 ", T("Home Assistant Media")),
        h("div.head-actions", haMediaOpenBtn(), h("button.btn.small.ghost", { title: T("Refresh"), onclick: () => open(cur) }, "🔄 ", T("Refresh")))),
      body, foot), { wide: true, onClose: () => finish(null) });
    open("");
  });
}

// photos for the pairs game and the crest: upload from this device or take them from Home Assistant Media
// The cards of the pairs game are small: the shorter edge becomes at most PHOTO_EDGE px (sharp enough on phones and
// tablets, a few KB per photo instead of megabytes).
const PHOTO_EDGE = 240;
// a file dialog that works reliably in phone browsers and the Home Assistant app: the input must be part of the page
// while the dialog is open (a detached one is sometimes collected before «change» fires); removed afterwards
function pickFiles({ accept = "image/*", multiple = false } = {}, then) {
  const inp = h("input", { type: "file", accept, multiple, style: { position: "fixed", left: "-1000px", top: "0", opacity: "0" } });
  const done = () => setTimeout(() => inp.remove(), 1000);
  inp.addEventListener("change", () => { const files = [...inp.files]; done(); if (files.length) then(files); });
  inp.addEventListener("cancel", done);
  document.body.append(inp);
  inp.click();
}

const Photos = {
  async upload(file, edge = PHOTO_EDGE) {          // the crest (printed on the poster) passes a larger edge
    const blob = await shrinkPhoto(file, edge, { short: true });
    for (let attempt = 0; ; attempt++) {            // one more try after a network hiccup (phones on Wi-Fi)
      const fd = new FormData(); fd.append("file", blob, "foto.jpg");
      try { return (await api("parent/memory/photo", { method: "POST", form: fd })).name; }
      catch (e) { if (attempt >= 1 || /\b(400|413|415)\b|large|photos? \(/i.test(e.message || "")) throw e; await new Promise(r => setTimeout(r, 800)); }
    }
  },
  async uploadAll(files, edge) {                           // every photo on its own – one bad file does not stop the others
    const out = [];
    for (const [i, file] of files.entries()) {
      if (files.length > 1) toast("⏳ " + I18N.tr(T("Uploading photo {0} of {1} …")).replace("{0}", i + 1).replace("{1}", files.length));
      try { out.push(await Photos.upload(file, edge)); } catch (e) { toast(`${file.name}: ${e.message}`, "bad"); }
    }
    return out;
  },
  pick(multiple, then, edge) {
    pickFiles({ accept: "image/*", multiple }, async files => { const names = await Photos.uploadAll(files, edge); if (names.length) await then(names); });
  },
  async fromHa(single, then, edge) {
    const paths = await haMediaPicker({ single });
    if (!paths || !paths.length) return;
    // a small copy of every picture (the original in Home Assistant Media stays as it is); a picture that cannot be
    // loaded here falls back to the reference «ha:<path>» as before
    const names = [], refs = [];
    for (const rel of paths) {
      try {
        const res = await fetch("api/parent/ha-media/file?path=" + encodeURIComponent(rel), { headers: { "X-FQ-Parent": Auth.parent } });
        if (!res.ok) throw new Error(res.status);
        const blob = await res.blob();
        names.push(await Photos.upload(new File([blob], rel.split("/").pop() || "foto.jpg", { type: blob.type || "image/jpeg" }), edge));
      } catch { refs.push(rel); }
    }
    if (refs.length) try { names.push(...(await call("parent/memory/ha-media", { method: "POST", body: { paths: refs } })).names); } catch {}
    if (names.length) await then(names);
  },
};

// the media browser of Home Assistant (upload photos there), in a new tab
async function haMediaHref() {
  if (P.info && P.info.via_ha) return "/media-browser/browser";
  try { const p = await api("ha-panel"); if (p.port) return `${p.ssl ? "https" : "http"}://${location.hostname}:${p.port}/media-browser/browser`; } catch {}
  return null;
}
function haMediaOpenBtn() {
  const a = h("a.btn.small.ghost", { href: "/media-browser/browser", target: "_blank", rel: "noopener" }, "↗ ", T("Open Home Assistant Media"));
  haMediaHref().then(u => { if (u) a.href = u; else a.hidden = true; });
  return a;
}
