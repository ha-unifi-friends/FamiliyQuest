// Avatar drawn as SVG from the same part ids the server knows (rewards/avatar.py).
"use strict";

const AVATAR_DEFAULT = { skin: "#f1c27d", hair: "short", hairColor: "#6b3e1f", eyes: "round", mouth: "smile", outfit: "tshirt", outfitColor: "#4f8cff", items: {} };

function shade(hex, f) {
  const n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  const m = x => Math.round(f < 0 ? x * (1 + f) : x + (255 - x) * f);
  return "#" + [m(r), m(g), m(b)].map(x => x.toString(16).padStart(2, "0")).join("");
}

function avatarSvg(av, size = 96, opts = {}) {
  const a = Object.assign({}, AVATAR_DEFAULT, av || {});
  const it = a.items || {};
  const skin = a.skin, hc = a.hairColor, oc = a.outfitColor, dark = shade(skin, -0.25);
  const p = [];
  // background
  const bg = it.background;
  if (bg === "bg_stars") p.push(`<circle cx="100" cy="100" r="100" fill="#1b2a4a"/>` + [[40, 40], [160, 50], [30, 120], [170, 130], [70, 20], [130, 25], [150, 90]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="2.5" fill="#ffe066"/>`).join(""));
  else if (bg === "bg_mountains") p.push(`<circle cx="100" cy="100" r="100" fill="#a5d8ff"/><path d="M0 150 60 80 100 130 140 70 200 150 200 200 0 200z" fill="#69db7c"/><path d="M60 80 72 94 48 94zM140 70 154 86 126 86z" fill="#fff"/>`);
  else if (bg === "bg_lake") p.push(`<circle cx="100" cy="100" r="100" fill="#c5f6fa"/><rect y="130" width="200" height="70" fill="#4dabf7"/><path d="M150 128h26l-4 6h-18z" fill="#fff"/><path d="M162 104v24l12-8z" fill="#ff8787"/>`);
  else if (!opts.transparent) p.push(`<circle cx="100" cy="100" r="100" fill="${shade(oc, 0.78)}"/>`);
  // hair behind the head
  if (a.hair === "long") p.push(`<path d="M52 92q-6 60 10 86h76q16-26 10-86z" fill="${hc}"/>`);
  if (a.hair === "ponytail") p.push(`<path d="M140 70q34 10 22 62q-6-20-24-36z" fill="${hc}"/>`);
  if (a.hair === "bun") p.push(`<circle cx="100" cy="40" r="18" fill="${hc}"/>`);
  // body / outfit
  const body = {
    tshirt: `<path d="M40 200q2-44 36-52h48q34 8 36 52z" fill="${oc}"/>`,
    hoodie: `<path d="M68 150q32-18 64 0l-6 10h-52z" fill="${shade(oc, -0.2)}"/><path d="M38 200q2-46 38-54h48q36 8 38 54z" fill="${oc}"/><path d="M92 160v24M108 160v24" stroke="${shade(oc, 0.6)}" stroke-width="3" stroke-linecap="round"/>`,
    dress: `<path d="M30 200q10-46 46-54h48q36 8 46 54z" fill="${oc}"/><path d="M76 146q24 16 48 0" fill="none" stroke="${shade(oc, 0.5)}" stroke-width="4"/>`,
    sweater: `<path d="M40 200q2-44 36-52h48q34 8 36 52z" fill="${oc}"/><path d="M50 178h100M46 190h108" stroke="${shade(oc, 0.45)}" stroke-width="5"/><path d="M80 148q20 12 40 0" fill="none" stroke="${shade(oc, -0.25)}" stroke-width="6"/>`,
    overall: `<path d="M40 200q2-44 36-52h48q34 8 36 52z" fill="#f8f9fa"/><path d="M66 200v-38h68v38z" fill="${oc}"/><path d="M74 162l-6-16M126 162l6-16" stroke="${oc}" stroke-width="7" stroke-linecap="round"/><circle cx="76" cy="168" r="3" fill="#fff"/><circle cx="124" cy="168" r="3" fill="#fff"/>`,
  }[a.outfit] || "";
  p.push(`<rect x="88" y="128" width="24" height="24" rx="8" fill="${dark}"/>`, body);
  // neck item
  if (it.neck === "scarf") p.push(`<path d="M72 146q28 14 56 0l2 10q-30 16-60 0z" fill="#e03131"/><path d="M118 152l6 26h-12z" fill="#c92a2a"/>`);
  if (it.neck === "medal") p.push(`<path d="M84 148l16 26 16-26" fill="none" stroke="#1c7ed6" stroke-width="6"/><circle cx="100" cy="180" r="10" fill="#fcc419" stroke="#e67700" stroke-width="2"/><text x="100" y="184" font-size="10" text-anchor="middle" fill="#e67700">★</text>`);
  // head
  p.push(`<circle cx="54" cy="96" r="9" fill="${skin}"/><circle cx="146" cy="96" r="9" fill="${skin}"/>`,
    `<ellipse cx="100" cy="92" rx="45" ry="48" fill="${skin}"/>`);
  // hair on top
  const hair = {
    short: `<path d="M55 86q0-46 45-46t45 46q-8-20-26-24-16 10-40 8-16 4-24 16z" fill="${hc}"/>`,
    long: `<path d="M54 92q-2-52 46-52t46 52q-10-26-28-28-22 8-38 4-20 4-26 24z" fill="${hc}"/>`,
    curly: [[62, 62], [78, 48], [98, 42], [118, 48], [136, 62], [146, 80], [54, 80]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="15" fill="${hc}"/>`).join(""),
    bun: `<path d="M56 84q0-44 44-44t44 44q-10-18-44-22-34 4-44 22z" fill="${hc}"/>`,
    // tufts all around the head plus a fringe over the forehead (the old three big spikes looked like a crown)
    spiky: `<path d="M55 90L54.3 75.9Q52.6 69.0 54.9 62.0L60.2 62.9Q59.0 54.9 61.7 46.9L69.1 52.2Q69.5 43.9 73.9 35.5L80.5 44.5Q82.8 36.2 89.1 28.0L93.3 40.5Q97.7 33.9 106.1 27.3L106.7 40.5Q112.5 36.5 122.2 32.5L119.5 44.5Q125.5 43.8 135.5 43.0L130.9 52.2Q136.0 54.4 145.1 56.5L139.8 62.9Q142.8 67.6 149.7 72.3L145.7 75.9L145 90L140 74L132 80L126 70L118 78L110 66L102 76L94 66L86 76L78 68L70 78L64 72L58 84Z" fill="${hc}" stroke="${hc}" stroke-width="2" stroke-linejoin="round"/>`,
    ponytail: `<path d="M55 86q0-46 45-46t45 46q-10-18-45-22-35 4-45 22z" fill="${hc}"/>`,
    bald: "",
  }[a.hair] || "";
  p.push(hair);
  // eyes
  const eyes = {
    round: `<circle cx="82" cy="94" r="6" fill="#222"/><circle cx="118" cy="94" r="6" fill="#222"/><circle cx="84" cy="92" r="2" fill="#fff"/><circle cx="120" cy="92" r="2" fill="#fff"/>`,
    happy: `<path d="M74 96q8-10 16 0M110 96q8-10 16 0" fill="none" stroke="#222" stroke-width="4" stroke-linecap="round"/>`,
    wink: `<circle cx="82" cy="94" r="6" fill="#222"/><circle cx="84" cy="92" r="2" fill="#fff"/><path d="M110 96q8-8 16 0" fill="none" stroke="#222" stroke-width="4" stroke-linecap="round"/>`,
    big: `<circle cx="82" cy="94" r="10" fill="#fff" stroke="#222" stroke-width="2"/><circle cx="118" cy="94" r="10" fill="#fff" stroke="#222" stroke-width="2"/><circle cx="83" cy="96" r="5" fill="#222"/><circle cx="119" cy="96" r="5" fill="#222"/>`,
    // sad: eyes looking down, eyebrows raised in the middle, a small tear
    sad: `<circle cx="82" cy="97" r="5.5" fill="#222"/><circle cx="118" cy="97" r="5.5" fill="#222"/><circle cx="83.5" cy="95.5" r="1.8" fill="#fff"/><circle cx="119.5" cy="95.5" r="1.8" fill="#fff"/>` +
      `<path d="M72 86q8-2 16-8M128 86q-8-2-16-8" fill="none" stroke="${shade(hc, -0.1)}" stroke-width="3.5" stroke-linecap="round"/>` +
      `<path d="M78 105q-3 5 0 7q3-2 0-7z" fill="#74c0fc"/>`,
    // tired: closed, drooping eyes
    sleepy: `<path d="M74 96q8 6 16 0M110 96q8 6 16 0" fill="none" stroke="#222" stroke-width="4" stroke-linecap="round"/>` +
      `<text x="140" y="70" font-size="16" fill="#748ffc" font-weight="700">z</text>`,
    // confused / dizzy: little spirals
    dizzy: `<g fill="none" stroke="#222" stroke-width="3" stroke-linecap="round"><path d="M82 94m-7 0a7 7 0 1 0 7-7a4.5 4.5 0 1 0 3 4"/><path d="M118 94m-7 0a7 7 0 1 0 7-7a4.5 4.5 0 1 0 3 4"/></g>`,
    // angry: eyebrows down in the middle
    angry: `<circle cx="82" cy="96" r="5.5" fill="#222"/><circle cx="118" cy="96" r="5.5" fill="#222"/>` +
      `<path d="M70 80l20 8M130 80l-20 8" stroke="${shade(hc, -0.1)}" stroke-width="4.5" stroke-linecap="round"/>`,
  }[a.eyes] || "";
  p.push(eyes, `<circle cx="72" cy="112" r="7" fill="#ff8787" opacity=".35"/><circle cx="128" cy="112" r="7" fill="#ff8787" opacity=".35"/>`);
  const mouth = {
    smile: `<path d="M86 116q14 14 28 0" fill="none" stroke="#7a2e2e" stroke-width="4" stroke-linecap="round"/>`,
    grin: `<path d="M84 114q16 22 32 0z" fill="#7a2e2e"/><path d="M88 115h24v4h-24z" fill="#fff"/>`,
    open: `<ellipse cx="100" cy="120" rx="8" ry="10" fill="#7a2e2e"/>`,
    neutral: `<path d="M88 120h24" stroke="#7a2e2e" stroke-width="4" stroke-linecap="round"/>`,
    sad: `<path d="M86 124q14-12 28 0" fill="none" stroke="#7a2e2e" stroke-width="4" stroke-linecap="round"/>`,
    // sick: wavy mouth and a green face
    wavy: `<path d="M84 120q4-6 8 0t8 0t8 0t8 0" fill="none" stroke="#2b8a3e" stroke-width="4" stroke-linecap="round"/>` +
      `<ellipse cx="100" cy="118" rx="34" ry="12" fill="#69db7c" opacity=".25"/>`,
  }[a.mouth] || "";
  p.push(mouth);
  // braces over the teeth (free item), placed by the mouth
  if (it.teeth === "braces" || it.teeth === "braces_color") {
    const at = { grin: [88, 112, 117], smile: [91, 109, 120], open: [94, 106, 114] }[a.mouth] || [93, 107, 120];
    const cols = it.teeth === "braces_color" ? ["#f06595", "#4dabf7", "#51cf66", "#fcc419"] : ["#ced4da"];
    const n = 4, step = (at[1] - at[0]) / (n - 1);
    p.push(`<path d="M${at[0]} ${at[2]}H${at[1]}" stroke="#adb5bd" stroke-width="1.6"/>` +
      Array.from({ length: n }, (_, i) => `<rect x="${(at[0] + i * step - 2).toFixed(1)}" y="${at[2] - 2}" width="4" height="4" rx="1" fill="${cols[i % cols.length]}" stroke="#868e96" stroke-width=".6"/>`).join(""));
  }
  // face: specials over the mouth
  if (it.face === "clown_nose") p.push(`<circle cx="100" cy="106" r="9" fill="#e03131"/><circle cx="97" cy="103" r="2.5" fill="#fff" opacity=".7"/>`);
  if (it.face === "mustache_curl") {
    // twirled moustache: a thick middle and two thin ends that curl upwards
    const half = m => `M${m(100)} 108C${m(93)} 102 ${m(84)} 115 ${m(73)} 109C${m(65)} 104 ${m(67)} 95 ${m(74)} 97C${m(78)} 98.5 ${m(77)} 103.5 ${m(73)} 102.5`;
    p.push(`<g fill="none" stroke="${shade(hc, -0.25)}" stroke-linecap="round"><path d="${half(x => x)}" stroke-width="4.5"/><path d="${half(x => 200 - x)}" stroke-width="4.5"/></g>` +
      `<path d="M100 106q-8-4-15 2q7 5 15 1q8 4 15-1q-7-6-15-2z" fill="${shade(hc, -0.25)}"/>`);
  }
  if (it.face === "mustache") p.push(`<path d="M100 110q-10-6-22 2q8 6 22-1q14 7 22 1q-12-8-22-2z" fill="${shade(hc, -0.15)}"/>`);
  // eyewear
  if (it.eyewear === "glasses") p.push(`<g fill="none" stroke="#343a40" stroke-width="3"><circle cx="82" cy="94" r="12"/><circle cx="118" cy="94" r="12"/><path d="M94 94h12M70 92l-14-4M130 92l14-4"/></g>`);
  if (it.eyewear === "glasses_square") p.push(`<g fill="none" stroke="#343a40" stroke-width="3"><rect x="69" y="84" width="26" height="20" rx="4"/><rect x="105" y="84" width="26" height="20" rx="4"/><path d="M95 92h10M69 90l-13-3M131 90l13-3"/></g>`);
  if (it.eyewear === "glasses_pink") p.push(`<g fill="none" stroke="#e64980" stroke-width="3.5"><circle cx="82" cy="94" r="12"/><circle cx="118" cy="94" r="12"/><path d="M94 94h12M70 92l-14-4M130 92l14-4"/></g>`);
  if (it.eyewear === "sunglasses") p.push(`<g fill="#212529"><rect x="68" y="84" width="28" height="18" rx="6"/><rect x="104" y="84" width="28" height="18" rx="6"/></g><path d="M96 90h8M68 88l-12-4M132 88l12-4" stroke="#212529" stroke-width="3"/>`);
  if (it.eyewear === "pirate_patch") p.push(`<path d="M58 78l84 30" stroke="#212529" stroke-width="3"/><ellipse cx="118" cy="95" rx="13" ry="11" fill="#212529"/>`);
  if (it.eyewear === "mask") p.push(`<path d="M62 86q38-14 76 0l-4 18q-14 8-26-2h-16q-12 10-26 2z" fill="#be4bdb"/><circle cx="82" cy="94" r="6" fill="${skin}"/><circle cx="118" cy="94" r="6" fill="${skin}"/>`);
  // ears
  if (it.ear === "earrings") p.push(`<circle cx="54" cy="110" r="4" fill="#fcc419"/><circle cx="146" cy="110" r="4" fill="#fcc419"/>`);
  if (it.ear === "headphones") p.push(`<path d="M52 92q0-60 48-60t48 60" fill="none" stroke="#495057" stroke-width="7"/><rect x="42" y="84" width="16" height="26" rx="7" fill="#e03131"/><rect x="142" y="84" width="16" height="26" rx="7" fill="#e03131"/>`);
  // hats
  const hat = {
    cap: `<path d="M56 70q4-36 44-36t44 36z" fill="#e03131"/><path d="M100 66h56q-6 10-56 8z" fill="#c92a2a"/>`,
    hat: `<ellipse cx="100" cy="58" rx="62" ry="10" fill="#495057"/><path d="M68 58q0-38 32-38t32 38z" fill="#343a40"/><rect x="68" y="48" width="64" height="7" fill="#e03131"/>`,
    beret: `<ellipse cx="96" cy="50" rx="50" ry="16" fill="#1c1c3c"/><circle cx="96" cy="34" r="4" fill="#1c1c3c"/>`,
    hardhat: `<path d="M54 66q0-38 46-38t46 38z" fill="#fcc419"/><rect x="48" y="62" width="104" height="8" rx="4" fill="#f08c00"/>`,
    crown: `<path d="M64 56l8-28 14 16 14-22 14 22 14-16 8 28z" fill="#fcc419" stroke="#e67700" stroke-width="2"/><circle cx="100" cy="40" r="4" fill="#e03131"/>`,
    wizard: `<path d="M60 60l40-56 40 56z" fill="#5f3dc4"/><ellipse cx="100" cy="60" rx="50" ry="8" fill="#5f3dc4"/><text x="100" y="44" font-size="14" text-anchor="middle" fill="#ffe066">★</text>`,
    santa: `<path d="M58 62q10-40 52-32 26 6 30 40" fill="#e03131"/><circle cx="146" cy="74" r="8" fill="#fff"/><rect x="54" y="56" width="92" height="12" rx="6" fill="#fff"/>`,
    pirate_hat: `<path d="M40 62q60-46 120 0q-20-8-60-6t-60 6z" fill="#212529"/><path d="M58 54q42-40 84 0z" fill="#212529"/>` +
      `<circle cx="100" cy="40" r="7" fill="#fff"/><path d="M93 50l14-6M93 44l14 6" stroke="#fff" stroke-width="2.5"/>`,
    viking: `<path d="M56 64q0-38 44-38t44 38z" fill="#adb5bd"/><rect x="54" y="58" width="92" height="10" rx="4" fill="#868e96"/>` +
      `<path d="M58 50q-22-6-20-34q8 18 26 22zM142 50q22-6 20-34q-8 18-26 22z" fill="#fff4e6" stroke="#e8c39e" stroke-width="2"/>`,
    unicorn: `<path d="M92 50l8-46 8 46z" fill="#fcc2d7" stroke="#e64980" stroke-width="2"/><path d="M93 40l14-4M94 28l12-4" stroke="#e64980" stroke-width="2"/>` +
      `<circle cx="70" cy="56" r="7" fill="#b197fc"/><circle cx="130" cy="56" r="7" fill="#74c0fc"/>`,
    party_hat: `<path d="M78 58l22-52 22 52z" fill="#ff922b"/><path d="M84 44l32 0M89 32l22 0M94 20l12 0" stroke="#fff" stroke-width="4"/><circle cx="100" cy="6" r="6" fill="#fcc419"/>`,
    antennae: `<path d="M82 50q-10-24-20-34M118 50q10-24 20-34" fill="none" stroke="#2b8a3e" stroke-width="4" stroke-linecap="round"/>` +
      `<circle cx="62" cy="16" r="8" fill="#94d82d"/><circle cx="138" cy="16" r="8" fill="#94d82d"/>`,
    // crown for a day (given by the parents)
    royal: `<path d="M56 60l6-36 18 18 20-30 20 30 18-18 6 36z" fill="#ffd43b" stroke="#e67700" stroke-width="2.5"/>` +
      `<rect x="56" y="56" width="88" height="10" rx="3" fill="#fab005" stroke="#e67700" stroke-width="2"/>` +
      `<circle cx="100" cy="40" r="5" fill="#e03131"/><circle cx="74" cy="46" r="4" fill="#1c7ed6"/><circle cx="126" cy="46" r="4" fill="#2f9e44"/>`,
  }[it.hat] || "";
  p.push(hat);
  // hair clip on the side of the head (not with a hat or without hair)
  if (it.hairclip && !it.hat && a.hair !== "bald") p.push({
    clip_bow: `<g transform="translate(128 56) rotate(20)"><path d="M0 0l-14-9v18zM0 0l14-9v18z" fill="#f06595"/><circle r="4" fill="#d6336c"/></g>`,
    clip_star: `<path d="M130 46l3.5 7.5 8 1-6 5.5 1.5 8-7-4-7 4 1.5-8-6-5.5 8-1z" fill="#fcc419" stroke="#e67700" stroke-width="1.2"/>`,
    clip_heart: `<path d="M130 66c-10-6-12-14-6-17 3-1.5 5 0 6 2 1-2 3-3.5 6-2 6 3 4 11-6 17z" fill="#ff6b6b" stroke="#e03131" stroke-width="1.2"/>`,
  }[it.hairclip] || "");
  if (it.neck === "bowtie") p.push(`<path d="M100 150l-18-10v20zM100 150l18-10v20z" fill="#e03131"/><circle cx="100" cy="150" r="4" fill="#c92a2a"/>`);
  const pet = { cat: "🐱", dog: "🐶", owl: "🦉", parrot: "🦜" }[it.pet];
  // the pet sits as a badge on top of the circle (bottom right) – not clipped, so it is fully visible
  const r = size < 40 ? 30 : 34;
  const petBadge = pet ? `<g><circle cx="158" cy="158" r="${r}" fill="#fff" stroke="rgba(0,0,0,.18)" stroke-width="3"/>` +
    `<text x="158" y="${158 + r * 0.42}" font-size="${Math.round(r * 1.35)}" text-anchor="middle">${pet}</text></g>` : "";
  const svg = `<svg viewBox="0 0 200 200" width="${size}" height="${size}" role="img" aria-hidden="true"><clipPath id="avc"><circle cx="100" cy="100" r="100"/></clipPath><g clip-path="url(#avc)">${p.join("")}</g>${petBadge}</svg>`;
  const el = document.createElement("span");
  el.className = "avatar";
  el.style.width = el.style.height = size + "px";
  el.innerHTML = svg;
  return el;
}

// Compact avatar editor (parent area › profile dialog): base parts and the items this profile has unlocked.
// d = catalog from the server ({parts, slots, items}), a = avatar object (changed in place).
function avatarEditorBox(d, a) {
  a.items = a.items || {};
  const TABS = [["skin", T("Skin")], ["hair", T("Hair")], ["hairColor", T("Hair colour")], ["eyes", T("Eyes")], ["mouth", T("Mouth")],
    ["outfit", T("Clothes")], ["outfitColor", T("Colour")], ["items", T("Items")]];
  let tab = "skin";
  const preview = h("div.av-preview"), tabs = h("div.av-tabs"), panel = h("div.av-panel");
  const draw = () => preview.replaceChildren(avatarSvg(a, 140));
  const drawTabs = () => tabs.replaceChildren(...TABS.map(([k, n]) => h("button" + (tab === k ? ".on" : ""), { type: "button", onclick: () => { tab = k; drawTabs(); drawPanel(); } }, n)));
  const drawPanel = () => {
    if (tab === "items") {
      panel.replaceChildren(h("div.av-opts",
        ...d.slots.flatMap(slot => d.items.filter(i => i.slot === slot && i.unlocked).map(i =>
          h("button.av-opt.item" + (a.items[slot] === i.id ? ".on" : ""), { type: "button", title: I18N.tr(i.name),
            onclick: () => { if (a.items[slot] === i.id) delete a.items[slot]; else a.items[slot] = i.id; draw(); drawPanel(); } },
            avatarSvg(Object.assign({}, a, { items: Object.assign({}, a.items, { [slot]: i.id }) }), 52))))));
      return;
    }
    panel.replaceChildren(h("div.av-opts", ...(d.parts[tab] || []).map(v => {
      const sample = /^#/.test(v) ? h("span.swatch", { style: { background: v } }) : avatarSvg(Object.assign({}, a, { [tab]: v }), 52);
      return h("button.av-opt" + (a[tab] === v ? ".on" : ""), { type: "button", "aria-label": v, onclick: () => { a[tab] = v; draw(); drawPanel(); } }, sample);
    })));
  };
  draw(); drawTabs(); drawPanel();
  return h("div.av-editor.compact", preview, h("div.av-side", tabs, panel));
}
