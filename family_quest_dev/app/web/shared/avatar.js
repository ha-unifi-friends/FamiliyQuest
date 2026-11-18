// Avatar drawn as SVG from the same part ids the server knows (rewards/avatar.py).
"use strict";

const AVATAR_DEFAULT = { skin: "#f1c27d", hair: "short", hairColor: "#6b3e1f", eyes: "round", mouth: "smile", outfit: "tshirt", outfitColor: "#4f8cff", items: {} };

function shade(hex, f) {
  const n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  const m = x => Math.round(f < 0 ? x * (1 + f) : x + (255 - x) * f);
  return "#" + [m(r), m(g), m(b)].map(x => x.toString(16).padStart(2, "0")).join("");
}

// the degu (there is no emoji for it): a brown-grey rodent with round ears and a long tail with a dark tuft, drawn in 0…100
const DEGU_SVG = `<path d="M30 72Q10 70 11 46Q12 30 7 21" fill="none" stroke="#6b5b4b" stroke-width="4.5" stroke-linecap="round"/>` +
  `<ellipse cx="7" cy="17" rx="5.5" ry="9" transform="rotate(-18 7 17)" fill="#2b2420"/>` +
  `<ellipse cx="40" cy="86" rx="7" ry="3.5" fill="#6b5b4b"/><ellipse cx="66" cy="87" rx="7" ry="3.5" fill="#6b5b4b"/>` +
  `<ellipse cx="50" cy="67" rx="29" ry="22" fill="#8d7b68"/><ellipse cx="57" cy="75" rx="16" ry="11" fill="#cdbca5"/>` +
  `<circle cx="57" cy="27" r="10" fill="#8d7b68"/><circle cx="57" cy="27" r="5.5" fill="#e8a5a5"/>` +
  `<circle cx="79" cy="28" r="10" fill="#8d7b68"/><circle cx="79" cy="28" r="5.5" fill="#e8a5a5"/>` +
  `<circle cx="69" cy="46" r="19" fill="#9a8873"/><circle cx="74" cy="43" r="4" fill="#1b1b1b"/><circle cx="75.4" cy="41.6" r="1.4" fill="#fff"/>` +
  `<circle cx="87" cy="51" r="3" fill="#e07a8a"/><path d="M84 53l13-4M84 55l13 2" stroke="#4a3f36" stroke-width="1.2" stroke-linecap="round"/>`;
const PET_EMOJI = { cat: "🐱", dog: "🐶", owl: "🦉", parrot: "🦜", hamster: "🐹", dino: "🦕", turtle: "🐢" };
// the goldfish (the fish emoji is blue): orange, round, with a big tail, drawn in 0…100
const GOLDFISH_SVG = `<path d="M26 50L6 30q-4 20 2 22-6 2-2 22z" fill="#ff922b" stroke="#e8590c" stroke-width="2.5" stroke-linejoin="round"/>` +
  `<ellipse cx="54" cy="50" rx="34" ry="24" fill="#ff922b" stroke="#e8590c" stroke-width="2.5"/>` +
  `<path d="M48 27q10-14 22-4-8 2-12 8zM50 73q8 10 18 4-8-2-10-8z" fill="#ffa94d" stroke="#e8590c" stroke-width="2"/>` +
  `<path d="M40 40q-6 10 0 20M48 36q-6 14 0 28" fill="none" stroke="#ffc078" stroke-width="2.5" stroke-linecap="round"/>` +
  `<circle cx="72" cy="44" r="7" fill="#fff"/><circle cx="74" cy="44" r="4" fill="#212529"/><circle cx="75.5" cy="42.5" r="1.4" fill="#fff"/>` +
  `<path d="M84 56q-4 4-8 2" fill="none" stroke="#c2410c" stroke-width="2" stroke-linecap="round"/>`;
const PET_SVG = { degu: () => DEGU_SVG, goldfish: () => GOLDFISH_SVG };

// pet shop (familyquest/pets.py SHOP): items without an emoji are drawn here (0…100); some outfits are drawn when worn
const PET_SHOP_EMOJI = { bow: "🎀", sweater: "🧶", dress: "👗", sunglasses: "🕶️", party_hat: "🥳", crown: "👑", castle: "🏰",
  bed: "🛏️", bowl: "🥣", ball: "⚽", lamp: "💡", plant: "🪴" };
const _coat = (fill, line, extra = "") => `<path d="M30 20L50 30L70 20L88 40L78 50L74 44V92H26V44L22 50L12 40Z" fill="${fill}" stroke="${line}" stroke-width="3" stroke-linejoin="round"/>${extra}`;
const PET_SHOP_SVG = {
  collar: `<path d="M14 40q36 22 72 0" fill="none" stroke="#e03131" stroke-width="10" stroke-linecap="round"/><circle cx="50" cy="66" r="10" fill="#fcc419" stroke="#e67700" stroke-width="2.5"/>`,
  raincoat: _coat("#fcc419", "#e67700", `<path d="M50 30V92" stroke="#e67700" stroke-width="2"/><circle cx="57" cy="52" r="3" fill="#e67700"/><circle cx="57" cy="70" r="3" fill="#e67700"/>`),
  dog_house: `<rect x="18" y="44" width="64" height="48" fill="#d9a066" stroke="#a0673a" stroke-width="2"/><path d="M18 58h64M18 72h64" stroke="#c08850" stroke-width="1.5"/>` +
    `<path d="M38 92V72a12 12 0 0 1 24 0v20z" fill="#5c3a21"/><path d="M8 50L50 12L92 50" fill="#c92a2a" stroke="#a61e1e" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>` +
    `<rect x="40" y="36" width="20" height="8" rx="2" fill="#fff" stroke="#a0673a"/>`,
  cat_tree: `<rect x="58" y="12" width="9" height="74" fill="#c8a27a"/><path d="M58 22h9M58 30h9M58 38h9M58 46h9M58 54h9M58 62h9M58 70h9" stroke="#a07850" stroke-width="1.5"/>` +
    `<rect x="46" y="8" width="42" height="8" rx="3" fill="#7048e8"/><rect x="62" y="40" width="32" height="7" rx="3" fill="#7048e8"/><rect x="44" y="86" width="54" height="7" rx="3" fill="#7048e8"/>` +
    `<path d="M6 72q28 30 56 0z" fill="#e8b04b" stroke="#b7791f" stroke-width="2"/><ellipse cx="34" cy="72" rx="28" ry="7" fill="#f8d9a0" stroke="#b7791f" stroke-width="2"/><path d="M16 80l8 6M30 82l6 5M44 80l4 5" stroke="#b7791f" stroke-width="1.5"/>`,
  bird_cage: `<path d="M20 88V45a30 30 0 0 1 60 0v43" fill="#fff9db" fill-opacity=".45" stroke="#e0a800" stroke-width="3"/>` +
    `<path d="M35 88V22M50 88V15M65 88V22M28 88V30M72 88V30" stroke="#e0a800" stroke-width="2"/><path d="M26 66h48" stroke="#8d6e63" stroke-width="3" stroke-linecap="round"/>` +
    `<rect x="14" y="86" width="72" height="8" rx="3" fill="#e0a800"/><circle cx="50" cy="9" r="5" fill="none" stroke="#e0a800" stroke-width="3"/>`,
  degu_house: `<rect x="8" y="20" width="84" height="72" rx="4" fill="#e7f5ff" fill-opacity=".55" stroke="#a0673a" stroke-width="4"/><rect x="10" y="80" width="80" height="10" fill="#f4d58d"/>` +
    `<path d="M10 54h38" stroke="#a0673a" stroke-width="4"/><path d="M46 54L70 82" stroke="#c8a27a" stroke-width="5" stroke-linecap="round"/><path d="M14 20V10h72v10" fill="none" stroke="#a0673a" stroke-width="3"/>` +
    `<path d="M20 30h60M20 40h60" stroke="#fff" stroke-width="2" stroke-opacity=".7"/>`,
  hamster_cage: `<rect x="10" y="26" width="80" height="66" rx="8" fill="#fff4e6" fill-opacity=".5" stroke="#d9822b" stroke-width="4"/>` +
    `<path d="M22 26V92M34 26V92M46 26V92M58 26V92M70 26V92M82 26V92" stroke="#d9822b" stroke-width="2"/><rect x="10" y="80" width="80" height="12" rx="3" fill="#f4d58d"/>` +
    `<circle cx="68" cy="60" r="16" fill="none" stroke="#f59f00" stroke-width="4"/><path d="M68 44v32M52 60h32" stroke="#f59f00" stroke-width="2"/>` +
    `<path d="M24 18h52l6 8H18z" fill="#d9822b"/><path d="M14 78h22v-14h14" fill="none" stroke="#a0673a" stroke-width="3"/>`,
  aquarium: `<rect x="8" y="24" width="84" height="66" rx="6" fill="#a5d8ff" fill-opacity=".55" stroke="#1c7ed6" stroke-width="4"/>` +
    `<path d="M10 36h80" stroke="#74c0fc" stroke-width="2"/><path d="M10 80q20-8 40 0t40 0v8H10z" fill="#f4d58d"/>` +
    `<path d="M24 82q-6-16 2-30M30 82q4-14-2-26M74 82q6-18-2-34" fill="none" stroke="#2f9e44" stroke-width="3" stroke-linecap="round"/>` +
    `<circle cx="60" cy="50" r="3" fill="#fff" fill-opacity=".8"/><circle cx="64" cy="40" r="2" fill="#fff" fill-opacity=".8"/>`,
  terrarium: `<rect x="8" y="30" width="84" height="60" rx="5" fill="#e6fcf5" fill-opacity=".5" stroke="#5c940d" stroke-width="4"/>` +
    `<path d="M10 76q20-10 40-2t40-4v18H10z" fill="#c8a27a"/><ellipse cx="70" cy="78" rx="12" ry="5" fill="#74c0fc"/>` +
    `<path d="M22 76q-2-18 8-26M30 76q6-14 2-24" fill="none" stroke="#2f9e44" stroke-width="3" stroke-linecap="round"/><path d="M8 30l42-16 42 16" fill="none" stroke="#5c940d" stroke-width="3"/>`,
  dino_nest: `<ellipse cx="50" cy="74" rx="44" ry="16" fill="#a0673a"/><path d="M8 72q10-10 20 0t20 0 20 0 20 0 6-2" fill="none" stroke="#c8a27a" stroke-width="4" stroke-linecap="round"/>` +
    `<path d="M10 78q12 8 24 2M40 84q12 6 24 0M68 80q12 6 22-2" fill="none" stroke="#7a4a24" stroke-width="3" stroke-linecap="round"/>` +
    `<path d="M70 30q6-14 14-6 4-10 10 0" fill="none" stroke="#2f9e44" stroke-width="4" stroke-linecap="round"/><path d="M82 26v40" stroke="#5c940d" stroke-width="5"/>`,
  wheel: `<path d="M50 54L30 94M50 54L70 94M24 94h52" stroke="#868e96" stroke-width="5" stroke-linecap="round"/><circle cx="50" cy="48" r="38" fill="#fff3bf" stroke="#f59f00" stroke-width="6"/>` +
    `<circle cx="50" cy="48" r="30" fill="none" stroke="#ffd43b" stroke-width="3" stroke-dasharray="3 5"/><path d="M50 10v76M12 48h76M23 21l54 54M77 21L23 75" stroke="#f59f00" stroke-width="2.5"/><circle cx="50" cy="48" r="6" fill="#e67700"/>`,
  cushion: `<rect x="10" y="38" width="80" height="38" rx="17" fill="#f783ac" stroke="#d6336c" stroke-width="2.5"/><circle cx="50" cy="57" r="4" fill="#d6336c"/><path d="M10 40l-4-6M90 40l4-6M10 74l-4 6M90 74l4 6" stroke="#d6336c" stroke-width="3" stroke-linecap="round"/>`,
  rug: `<ellipse cx="50" cy="60" rx="45" ry="20" fill="#4f8cff" stroke="#1c7ed6" stroke-width="2"/><ellipse cx="50" cy="60" rx="32" ry="12" fill="none" stroke="#fff" stroke-width="3" stroke-dasharray="6 4"/><ellipse cx="50" cy="60" rx="12" ry="4" fill="#fcc419"/>`,
};
// what the pet wears (if it looks better drawn than the emoji of the shop)
const PET_WEAR_SVG = {
  sweater: _coat("#e64980", "#a61e4d", `<path d="M26 56h48M26 68h48M26 80h48" stroke="#fff" stroke-width="3" stroke-dasharray="4 3"/>`),
  party_hat: `<path d="M50 6L74 90H26Z" fill="#845ef7" stroke="#5f3dc4" stroke-width="2" stroke-linejoin="round"/><path d="M40 46h20M33 68h34" stroke="#fcc419" stroke-width="6"/><circle cx="50" cy="7" r="8" fill="#ff6b6b"/>`,
};
const PET_WEAR_POS = { bow: "ear", collar: "neck", sweater: "body", raincoat: "body", dress: "body", sunglasses: "eyes", party_hat: "top", crown: "top" };

/** A pet shop item as an element: its emoji or its drawing. `worn`: the drawing for wearing it, where there is one. */
function petShopIcon(id, size = 32, worn = false) {
  const svg = (worn && PET_WEAR_SVG[id]) || (PET_SHOP_EMOJI[id] ? "" : PET_SHOP_SVG[id]);
  const el = document.createElement("span");
  el.className = "pet-shop-ic";
  if (svg) {
    el.style.cssText = `display:inline-block;width:${size}px;height:${size}px;line-height:0;vertical-align:middle`;
    el.innerHTML = `<svg viewBox="0 0 100 100" width="${size}" height="${size}" aria-hidden="true">${svg}</svg>`;
  } else {
    el.style.cssText = `display:inline-block;font-size:${Math.round(size * .86)}px;line-height:1;vertical-align:middle`;
    el.textContent = PET_SHOP_EMOJI[id] || "🎁";
  }
  return el;
}

/** The picture of a pet kind as an element: the emoji, or the drawn degu (also for bots of the kind «degu»). */
function petIcon(kind, size = 32, emoji = "") {
  if (PET_SVG[kind]) {
    const el = document.createElement("span");
    el.className = "pet-svg";
    el.style.cssText = `display:inline-block;width:${size}px;height:${size}px;line-height:0;vertical-align:middle`;
    el.innerHTML = `<svg viewBox="0 0 100 100" width="${size}" height="${size}" aria-hidden="true">${PET_SVG[kind]()}</svg>`;
    return el;
  }
  return document.createTextNode(PET_EMOJI[kind] || emoji || "🐾");
}

// backgrounds for new XP (rewards/avatar.py: rule {"xp": 500}) – 200×200, clipped to the circle by avatarSvg
const XP_BG = {
  bg_sunset: () => `<rect width="200" height="200" fill="#ffb37a"/><rect width="200" height="70" fill="#ff8a65"/><circle cx="100" cy="118" r="34" fill="#ffe066"/>` +
    `<rect y="118" width="200" height="40" fill="#4dabf7"/><path d="M60 128h80M76 138h48M88 148h24" stroke="#ffe066" stroke-width="3" opacity=".7"/>` +
    `<rect y="156" width="200" height="44" fill="#f3d9a4"/><path d="M28 160c2-26 6-44 2-60" stroke="#8d5524" stroke-width="5" fill="none"/>` +
    `<path d="M30 100c-14-6-26-2-30 6M30 100c14-8 26-6 32 2M30 100c-6-12-18-16-26-14M30 100c8-12 20-14 28-10" stroke="#2f9e44" stroke-width="7" fill="none" stroke-linecap="round"/>`,
  bg_forest: () => `<rect width="200" height="200" fill="#d3f9d8"/><rect y="160" width="200" height="40" fill="#8ce99a"/>` +
    [[20, 150, 1], [60, 160, 1.3], [110, 150, 1.1], [160, 162, 1.35], [190, 148, 1]].map(([x, y, k]) =>
      `<rect x="${x - 4}" y="${y - 6}" width="8" height="${26 * k}" fill="#8d5524"/><path d="M${x} ${y - 90 * k}l${30 * k} ${84 * k}h${-60 * k}z" fill="#2b8a3e"/><path d="M${x} ${y - 70 * k}l${22 * k} ${46 * k}h${-44 * k}z" fill="#37b24d"/>`).join(""),
  bg_desert: () => `<rect width="200" height="200" fill="#fff3bf"/><circle cx="160" cy="44" r="20" fill="#ffd43b"/>` +
    `<path d="M0 150q50-30 100-6t100-8v64H0z" fill="#f8c77e"/><path d="M0 170q60-20 120 0t80-6v36H0z" fill="#f4a95c"/>` +
    `<g fill="#40c057"><rect x="40" y="96" width="12" height="62" rx="6"/><rect x="24" y="110" width="10" height="26" rx="5"/><rect x="58" y="104" width="10" height="24" rx="5"/>` +
    `<path d="M29 132h12M57 124h-6" stroke="#40c057" stroke-width="10"/></g>`,
  bg_ocean: () => `<rect width="200" height="200" fill="#1c7ed6"/><rect width="200" height="60" fill="#4dabf7"/><rect y="170" width="200" height="30" fill="#f3d9a4"/>` +
    `<path d="M30 170c-6-20 8-30 0-50M44 170c6-18-6-26 2-44M170 170c-8-22 6-30-2-48" stroke="#37b24d" stroke-width="5" fill="none"/>` +
    [[60, 40], [150, 90], [40, 110], [120, 30]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="5" fill="none" stroke="#d0ebff" stroke-width="2"/>`).join("") +
    `<path d="M140 140q14-10 28 0-14 10-28 0zM168 140l8-6v12z" fill="#ff922b"/><path d="M20 80q10-8 20 0-10 8-20 0zM40 80l6-5v10z" fill="#fcc419"/>`,
  bg_space: () => `<rect width="200" height="200" fill="#0b1026"/>` +
    [[20, 30], [60, 15], [170, 25], [185, 90], [15, 120], [40, 170], [160, 175], [120, 12], [90, 185]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="1.8" fill="#fff"/>`).join("") +
    `<circle cx="150" cy="58" r="22" fill="#ff922b"/><ellipse cx="150" cy="58" rx="38" ry="9" fill="none" stroke="#ffd8a8" stroke-width="4" transform="rotate(-18 150 58)"/>` +
    `<circle cx="36" cy="64" r="12" fill="#74c0fc"/><circle cx="32" cy="60" r="3" fill="#4dabf7"/>`,
  bg_snow: () => `<rect width="200" height="200" fill="#cfe8ff"/><path d="M0 140q60-40 120-10t80-20v90H0z" fill="#fff"/><path d="M0 170q70-30 200 0v30H0z" fill="#e7f5ff"/>` +
    `<path d="M150 136l18 34h-36z" fill="#2b8a3e"/><path d="M150 120l14 26h-28z" fill="#2f9e44"/>` +
    [[30, 30], [80, 50], [130, 25], [175, 60], [50, 90], [110, 85], [20, 120]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="3" fill="#fff"/>`).join(""),
  bg_city: () => `<rect width="200" height="200" fill="#1e1b4b"/><circle cx="160" cy="40" r="14" fill="#fff9db"/>` +
    [[0, 110, 34], [36, 80, 30], [68, 120, 28], [98, 70, 36], [136, 100, 30], [168, 85, 32]].map(([x, y, w]) =>
      `<rect x="${x}" y="${y}" width="${w}" height="${200 - y}" fill="#364fc7"/>` +
      Array.from({ length: Math.floor((190 - y) / 16) }, (_, r) => [0, 1].map(c => `<rect x="${x + 6 + c * (w / 2)}" y="${y + 8 + r * 16}" width="7" height="8" fill="${(x + r + c) % 3 ? "#ffe066" : "#4c6ef5"}"/>`).join("")).join("")).join(""),
  bg_volcano: () => `<rect width="200" height="200" fill="#ffc9a9"/><path d="M20 200 80 90h40l60 110z" fill="#5c3a21"/><path d="M80 90h40l-8 16-8-6-8 12-8-10-8 8z" fill="#ff6b00"/>` +
    `<circle cx="96" cy="60" r="16" fill="#adb5bd"/><circle cx="114" cy="44" r="20" fill="#ced4da"/><circle cx="90" cy="30" r="12" fill="#dee2e6"/>` +
    `<path d="M100 92q-6 30-20 50M104 96q6 26 16 40" stroke="#fa5252" stroke-width="5" fill="none" stroke-linecap="round"/>`,
  bg_aurora: () => `<rect width="200" height="200" fill="#0b2239"/>` +
    `<path d="M-10 90q50-50 100-10t120-30" stroke="#63e6be" stroke-width="18" fill="none" opacity=".7"/><path d="M-10 110q60-40 110-10t110-20" stroke="#9775fa" stroke-width="12" fill="none" opacity=".55"/>` +
    [[30, 30], [170, 20], [120, 40], [60, 55]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="1.8" fill="#fff"/>`).join("") +
    `<path d="M0 160l40-30 30 20 40-34 40 30 50-20v74H0z" fill="#e7f5ff"/>`,
  bg_meadow: () => `<rect width="200" height="200" fill="#d0ebff"/><circle cx="40" cy="40" r="16" fill="#ffd43b"/><rect y="130" width="200" height="70" fill="#69db7c"/>` +
    [[20, 150, "#ff6b6b"], [55, 170, "#f783ac"], [90, 145, "#ffd43b"], [130, 172, "#9775fa"], [165, 150, "#ff922b"], [185, 182, "#ff6b6b"], [40, 188, "#ffd43b"]].map(([x, y, c]) =>
      `<path d="M${x} ${y}v14" stroke="#2b8a3e" stroke-width="2"/><circle cx="${x}" cy="${y}" r="6" fill="${c}"/><circle cx="${x}" cy="${y}" r="2.5" fill="#fff3bf"/>`).join(""),
  bg_candy: () => `<rect width="200" height="200" fill="#ffdeeb"/><path d="M0 160q50-24 100 0t100 0v40H0z" fill="#f783ac"/>` +
    `<g><rect x="40" y="60" width="6" height="100" fill="#fff"/><circle cx="43" cy="56" r="22" fill="#ff6b6b"/><path d="M43 56m-14 0a14 14 0 1 1 14 14" stroke="#fff" stroke-width="5" fill="none"/></g>` +
    `<g><rect x="150" y="80" width="6" height="80" fill="#fff"/><circle cx="153" cy="76" r="18" fill="#74c0fc"/><path d="M141 70l24 12M141 82l24-12" stroke="#fff" stroke-width="4"/></g>` +
    [[90, 40, "#ffd43b"], [110, 110, "#69db7c"], [80, 130, "#9775fa"]].map(([x, y, c]) => `<ellipse cx="${x}" cy="${y}" rx="9" ry="6" fill="${c}"/>`).join(""),
  bg_castle: () => `<rect width="200" height="200" fill="#bac8ff"/><rect y="170" width="200" height="30" fill="#69db7c"/>` +
    `<g fill="#adb5bd"><rect x="50" y="100" width="100" height="70"/><rect x="36" y="76" width="30" height="94"/><rect x="134" y="76" width="30" height="94"/>` +
    `<path d="M36 76h6v-8h6v8h6v-8h6v8h6v-6H36z"/></g><path d="M36 76l15-30 15 30zM134 76l15-30 15 30z" fill="#5c7cfa"/>` +
    `<path d="M88 170v-28a12 12 0 0 1 24 0v28z" fill="#5c3a21"/><path d="M51 46v-16l12 5-12 5" fill="#ff6b6b"/>`,
  bg_balloons: () => `<rect width="200" height="200" fill="#a5d8ff"/><ellipse cx="40" cy="160" rx="40" ry="14" fill="#fff"/><ellipse cx="170" cy="40" rx="30" ry="10" fill="#fff"/>` +
    [[60, 60, 26, "#ff6b6b"], [140, 100, 20, "#fcc419"], [160, 160, 14, "#9775fa"]].map(([x, y, r, c]) =>
      `<path d="M${x - r} ${y}a${r} ${r * 1.15} 0 1 1 ${2 * r} 0q0 ${r * 0.8} ${-r * 0.5} ${r * 1.2}h${-r}q${-r * 0.5} ${-r * 0.4} ${-r * 0.5} ${-r * 1.2}z" fill="${c}"/>` +
      `<path d="M${x - r * 0.3} ${y + r * 1.2}v${r * 0.4}M${x + r * 0.3} ${y + r * 1.2}v${r * 0.4}" stroke="#5c3a21" stroke-width="1.5"/><rect x="${x - r * 0.35}" y="${y + r * 1.6}" width="${r * 0.7}" height="${r * 0.45}" fill="#8d5524"/>`).join(""),
  bg_autumn: () => `<rect width="200" height="200" fill="#fff4e6"/><rect y="160" width="200" height="40" fill="#e8590c" opacity=".35"/>` +
    `<rect x="150" y="70" width="14" height="100" fill="#5c3a21"/><circle cx="157" cy="60" r="40" fill="#f76707"/><circle cx="130" cy="78" r="22" fill="#fd7e14"/><circle cx="182" cy="82" r="20" fill="#e8590c"/>` +
    [[30, 40, "#f76707"], [70, 90, "#fcc419"], [40, 130, "#e8590c"], [100, 50, "#fd7e14"], [90, 150, "#fcc419"]].map(([x, y, c], i) =>
      `<path d="M${x} ${y}q8-10 16 0q-8 10-16 0z" fill="${c}" transform="rotate(${i * 40} ${x + 8} ${y})"/>`).join(""),
  bg_savanna: () => `<rect width="200" height="200" fill="#ffd8a8"/><circle cx="100" cy="120" r="44" fill="#ff922b"/><rect y="140" width="200" height="60" fill="#e9b949"/>` +
    `<path d="M150 150c0-24-4-40 4-56" stroke="#5c3a21" stroke-width="5" fill="none"/><path d="M118 96q36-24 74 0z" fill="#5c940d"/>` +
    `<path d="M20 160h40M30 168h50" stroke="#c49a2c" stroke-width="3"/>`,
};

function avatarSvg(av, size = 96, opts = {}) {
  const a = Object.assign({}, AVATAR_DEFAULT, av || {});
  const it = a.items || {};
  const skin = a.skin, hc = a.hairColor, oc = a.outfitColor, dark = shade(skin, -0.25);
  const p = [];
  // background
  const bg = it.background;
  if (bg === "bg_stars") p.push(`<circle cx="100" cy="100" r="100" fill="#1b2a4a"/>` + [[40, 40], [160, 50], [30, 120], [170, 130], [70, 20], [130, 25], [150, 90]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="2.5" fill="#ffe066"/>`).join(""));
  else if (bg === "bg_mountains") p.push(`<circle cx="100" cy="100" r="100" fill="#a5d8ff"/><path d="M0 150 60 80 100 130 140 70 200 150 200 200 0 200z" fill="#69db7c"/><path d="M60 80 72 94 48 94zM140 70 154 86 126 86z" fill="#fff"/>`);
  else if (bg === "bg_rainbow") p.push(`<circle cx="100" cy="100" r="100" fill="#d0ebff"/>` +
    ["#ff6b6b", "#ffa94d", "#ffd43b", "#69db7c", "#4dabf7", "#9775fa"].map((c, i) => `<path d="M${10 + i * 9} 150a${90 - i * 9} ${90 - i * 9} 0 0 1 ${180 - i * 18} 0" fill="none" stroke="${c}" stroke-width="9"/>`).join("") +
    `<ellipse cx="34" cy="150" rx="26" ry="12" fill="#fff"/><ellipse cx="166" cy="150" rx="26" ry="12" fill="#fff"/>`);
  else if (bg === "bg_lake") p.push(`<circle cx="100" cy="100" r="100" fill="#c5f6fa"/><rect y="130" width="200" height="70" fill="#4dabf7"/><path d="M150 128h26l-4 6h-18z" fill="#fff"/><path d="M162 104v24l12-8z" fill="#ff8787"/>`);
  else if (XP_BG[bg]) p.push(XP_BG[bg]());
  else if (!opts.transparent) p.push(`<circle cx="100" cy="100" r="100" fill="${shade(oc, 0.78)}"/>`);
  // on the back (behind the body): jetpack, wings
  if (it.back === "jetpack") p.push(`<g stroke="#495057" stroke-width="3"><rect x="32" y="122" width="28" height="60" rx="13" fill="#ced4da"/><rect x="140" y="122" width="28" height="60" rx="13" fill="#ced4da"/></g>` +
    `<rect x="34" y="134" width="24" height="7" fill="#e03131"/><rect x="142" y="134" width="24" height="7" fill="#e03131"/>` +
    `<path d="M36 182l10 18 10-18zM144 182l10 18 10-18z" fill="#ff922b"/><path d="M41 182l5 10 5-10zM149 182l5 10 5-10z" fill="#ffe066"/>`);
  if (it.back === "wings") {
    const wing = `<path d="M84 158C60 150 30 134 16 104 10 90 12 72 20 60c4 14 10 20 18 22-2-14 2-26 10-34 2 14 8 22 16 26 0-12 4-22 12-28 2 16 6 30 10 44 6 20 6 44 2 68z" fill="#fff" stroke="#adb5bd" stroke-width="2.5" stroke-linejoin="round"/>` +
      `<path d="M26 98q22 22 52 46M40 84q16 26 40 50M58 76q10 28 24 54" fill="none" stroke="#ced4da" stroke-width="2" stroke-linecap="round"/>`;
    p.push(wing, `<g transform="translate(200 0) scale(-1 1)">${wing}</g>`);
  }
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
  const torso = "M40 200q2-44 36-52h48q34 8 36 52z";
  const suit = {
    camo_sweater: `<clipPath id="av-camo"><path d="${torso}"/></clipPath><path d="${torso}" fill="#6b7d3a"/>` +
      `<g clip-path="url(#av-camo)"><path d="M40 160q14-8 26 2t20 18q-16 10-34 2zM96 150q18-6 30 6-6 14-24 10t-6-16zM120 176q20-6 34 6-4 16-24 12zM70 186q14-6 22 4-6 10-22 10z" fill="#3f4a22"/>` +
      `<path d="M62 150q10 0 12 8-8 6-16 0zM110 182q10-4 16 4-8 8-16 2zM138 156q10-2 12 6-6 4-12 0zM50 182q8-2 10 4-6 6-12 2z" fill="#a8a25c"/></g>` +
      `<path d="M80 148q20 12 40 0" fill="none" stroke="#3f4a22" stroke-width="6"/>`,
    tshirt_pets: `<path d="${torso}" fill="#fff" stroke="#dee2e6" stroke-width="2"/>` +
      `<text x="100" y="178" text-anchor="middle" font-size="15" font-weight="800" font-family="system-ui,sans-serif" fill="#212529">I <tspan fill="#e03131">♥</tspan> 🐾</text>`,
    pyjamas: `<path d="${torso}" fill="#a5d8ff"/><path d="M44 174h112M42 188h116M50 162h100" stroke="#fff" stroke-width="4" stroke-dasharray="2 8" stroke-linecap="round"/>` +
      `<path d="M78 148l22 18 22-18" fill="none" stroke="#74c0fc" stroke-width="5"/><circle cx="100" cy="176" r="3" fill="#fff"/><circle cx="100" cy="188" r="3" fill="#fff"/>`,
    // pirate apprentice (own design): wide white shirt with puffy sleeves and lacing, dark waistcoat with brass buttons
    pirate_apprentice: `<path d="M34 200q0-50 42-54h48q42 4 42 54z" fill="#f8f9fa" stroke="#dee2e6" stroke-width="2"/>` +
      `<path d="M40 176q-6-18 8-30M160 176q6-18-8-30" fill="none" stroke="#dee2e6" stroke-width="2.5" stroke-linecap="round"/>` +
      `<path d="M86 146l14 22 14-22" fill="#ffe8cc" stroke="#dee2e6" stroke-width="2"/>` +
      `<path d="M94 152l12 6M106 152l-12 6M95 160l10 5M105 160l-10 5" stroke="#4dabf7" stroke-width="2.5" stroke-linecap="round"/>` +
      `<path d="M62 200q-2-30 14-48l10 22v26zM138 200q2-30-14-48l-10 22v26z" fill="#495057" stroke="#343a40" stroke-width="2"/>` +
      `<path d="M86 174h28v26H86z" fill="#5c636a"/><path d="M88 176v24M112 176v24" stroke="#343a40" stroke-width="2"/>` +
      `<circle cx="80" cy="180" r="3" fill="#e9c46a" stroke="#b08900"/><circle cx="80" cy="192" r="3" fill="#e9c46a" stroke="#b08900"/>` +
      `<circle cx="120" cy="180" r="3" fill="#e9c46a" stroke="#b08900"/><circle cx="120" cy="192" r="3" fill="#e9c46a" stroke="#b08900"/>`,
    chicken_suit: `<path d="${torso}" fill="#fff" stroke="#dee2e6" stroke-width="2"/>` +
      `<path d="M52 176q8 8 16 0t16 0 16 0 16 0 16 0 16 0M48 190q8 8 16 0t16 0 16 0 16 0 16 0 16 0 16 0M66 162q8 8 16 0t16 0 16 0 16 0" fill="none" stroke="#e9ecef" stroke-width="3"/>` +
      `<path d="M44 168q-14 10-10 30q10-4 16-14zM156 168q14 10 10 30q-10-4-16-14z" fill="#f8f9fa" stroke="#ced4da" stroke-width="2"/>`,
  }[it.suit];
  p.push(`<rect x="88" y="128" width="24" height="24" rx="8" fill="${dark}"/>`, suit || body);
  if (it.figure === "round_belly") {
    const bc = { camo_sweater: "#6b7d3a", chicken_suit: "#fff", tshirt_pets: "#fff", pyjamas: "#a5d8ff", pirate_apprentice: "#f8f9fa" }[it.suit] || (a.outfit === "overall" ? oc : oc);
    p.push(`<path d="M18 200C12 156 56 142 100 142S188 156 182 200Z" fill="${bc}" stroke="${shade(bc, -0.15)}" stroke-width="2"/>` +
      `<ellipse cx="100" cy="184" rx="52" ry="24" fill="${shade(bc, 0.18)}" opacity=".55"/>` +
      `<path d="M58 196q42 14 84 0" fill="none" stroke="${shade(bc, -0.14)}" stroke-width="3" stroke-linecap="round"/><ellipse cx="100" cy="188" rx="3" ry="4" fill="${shade(bc, -0.3)}"/>` +
      (it.suit === "tshirt_pets" ? `<text x="100" y="174" text-anchor="middle" font-size="15" font-weight="800" font-family="system-ui,sans-serif" fill="#212529">I <tspan fill="#e03131">♥</tspan> 🐾</text>` : ""));
  }
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
  if (it.suit === "chicken_suit" && !it.hat) p.push(`<path d="M82 48q-4-16 8-14q0-14 10-10q6-12 14 0q12-2 8 14q4 6-2 10H84q-6-4-2-10z" fill="#e03131" stroke="#c92a2a" stroke-width="2"/>`);
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
  if (it.eyewear === "monocle") p.push(`<circle cx="118" cy="94" r="12" fill="#e7f5ff" fill-opacity=".35" stroke="#e0a800" stroke-width="3"/><path d="M130 98q8 22-2 44" fill="none" stroke="#e0a800" stroke-width="1.6"/>`);
  if (it.eyewear === "sleep_mask") p.push(`<path d="M58 88q42-16 84 0v12q-20 10-42 2-22 8-42-2z" fill="#845ef7"/><path d="M56 92h-4M144 92h4" stroke="#5f3dc4" stroke-width="4"/>` +
    `<path d="M74 96q8 4 16 0M110 96q8 4 16 0" fill="none" stroke="#e5dbff" stroke-width="2.5" stroke-linecap="round"/>`);
  if (it.eyewear === "pirate_patch") p.push(`<path d="M58 78l84 30" stroke="#212529" stroke-width="3"/><ellipse cx="118" cy="95" rx="13" ry="11" fill="#212529"/>`);
  if (it.eyewear === "mask") p.push(`<path d="M62 86q38-14 76 0l-4 18q-14 8-26-2h-16q-12 10-26 2z" fill="#be4bdb"/><circle cx="82" cy="94" r="6" fill="${skin}"/><circle cx="118" cy="94" r="6" fill="${skin}"/>`);
  // ears
  if (it.ear === "earrings") p.push(`<circle cx="54" cy="110" r="4" fill="#fcc419"/><circle cx="146" cy="110" r="4" fill="#fcc419"/>`);
  if (it.ear === "earbuds") p.push(`<g fill="#fff" stroke="#adb5bd" stroke-width="1.5"><ellipse cx="54" cy="95" rx="6.5" ry="7.5"/><rect x="50.5" y="99" width="7" height="17" rx="3.5"/>` +
    `<ellipse cx="146" cy="95" rx="6.5" ry="7.5"/><rect x="142.5" y="99" width="7" height="17" rx="3.5"/></g>`);
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
    helmet: `<path d="M52 72q0-46 48-46t48 46z" fill="#1c7ed6"/><path d="M70 40l6 22M100 30v30M130 40l-6 22" stroke="#74c0fc" stroke-width="6" stroke-linecap="round"/>` +
      `<rect x="48" y="68" width="104" height="8" rx="4" fill="#1864ab"/>`,
    // briefs pulled over the head: the waistband round the forehead, the leg holes on top, the gusset in the middle
    pants_head: `<path d="M50 72L58 34Q74 50 100 50Q126 50 142 34L150 72Z" fill="#fff" stroke="#adb5bd" stroke-width="2.5" stroke-linejoin="round"/>` +
      `<path d="M58 34Q74 50 100 50Q126 50 142 34" fill="none" stroke="#ced4da" stroke-width="4"/>` +
      `<path d="M86 52l14 18 14-18" fill="none" stroke="#dee2e6" stroke-width="2.5"/>` +
      `<rect x="46" y="62" width="108" height="11" rx="4" fill="#fff" stroke="#adb5bd" stroke-width="2"/><path d="M52 67.5h96" stroke="#74c0fc" stroke-width="2.5" stroke-dasharray="6 4"/>`,
    sleep_cap: `<path d="M56 64q2-40 50-36 34 4 50 50-16-14-28-16 4-6 0-14" fill="#4dabf7"/><path d="M56 64q2-40 50-36" fill="none" stroke="#339af0" stroke-width="2"/>` +
      `<rect x="52" y="58" width="96" height="12" rx="6" fill="#fff"/><circle cx="158" cy="80" r="9" fill="#fff"/>`,
    mouse_ears: `<circle cx="58" cy="38" r="22" fill="#212529"/><circle cx="142" cy="38" r="22" fill="#212529"/><path d="M58 66q42-34 84 0" fill="none" stroke="#212529" stroke-width="8" stroke-linecap="round"/>`,
    drink_helmet: `<path d="M56 64q0-36 44-36t44 36z" fill="#fcc419"/><rect x="50" y="60" width="100" height="8" rx="4" fill="#f08c00"/>` +
      `<rect x="36" y="30" width="18" height="30" rx="4" fill="#e03131" stroke="#a61e1e" stroke-width="2"/><rect x="146" y="30" width="18" height="30" rx="4" fill="#1c7ed6" stroke="#1864ab" stroke-width="2"/>` +
      `<path d="M45 32q-20 46 45 86M155 32q20 46-45 86" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round"/>` +
      `<path d="M45 32q-20 46 45 86M155 32q20 46-45 86" fill="none" stroke="#ff8787" stroke-width="4" stroke-linecap="round" stroke-dasharray="5 6"/>`,
    // won the last family game: the «No. 1» hat (until the next family game)
    champion: `<ellipse cx="100" cy="64" rx="58" ry="10" fill="#e8a400" stroke="#b07a00" stroke-width="2"/>` +
      `<path d="M66 64V24q0-8 8-8h52q8 0 8 8v40z" fill="#ffd43b" stroke="#b07a00" stroke-width="2.5"/>` +
      `<rect x="66" y="50" width="68" height="10" fill="#e03131"/>` +
      `<text x="100" y="46" text-anchor="middle" font-size="30" font-weight="900" font-family="system-ui,sans-serif" fill="#b07a00">1</text>` +
      `<path d="M76 24q2-4 6-4" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".7"/>`,
    // the whole head in a black, glossy helmet with a face mask (own design)
    dark_helmet: `<path d="M48 104q-4-76 52-76t52 76l10 32q-14 8-30 6l-6-22H76l-6 22q-16 2-30-6z" fill="#16181d" stroke="#000" stroke-width="2"/>` +
      `<path d="M62 70q8-30 38-32" fill="none" stroke="#5c6370" stroke-width="5" stroke-linecap="round" opacity=".7"/>` +
      `<path d="M100 40v34" stroke="#2b2f36" stroke-width="4"/>` +
      `<path d="M64 88q14-10 32 0l-4 16H70zM136 88q-14-10-32 0l4 16h22z" fill="#2b2f36"/>` +
      `<path d="M68 90q12-6 24 0l-3 10H72zM132 90q-12-6-24 0l3 10h18z" fill="#4dabf7" opacity=".25"/>` +
      `<path d="M74 112h52l-6 28H80z" fill="#22252b"/>` +
`<path d="M100 104l-16 34h32z" fill="#3a3f47"/><path d="M92 120h16M90 126h20M88 132h24" stroke="#16181d" stroke-width="2"/>` +
      `<path d="M84 106l-6 10M116 106l6 10" stroke="#5c6370" stroke-width="2.5"/>`,
    // a black cowl with pointed ears and a mask over the eyes – mouth and chin stay free (own design)
    bat_mask: `<path d="M54 100q-4-60 46-62t46 62l-4 6q-10-6-20-2l-6-4H84l-6 4q-10-4-20 2z" fill="#25262b"/>` +
      `<path d="M60 64l4-40 18 22zM140 64l-4-40-18 22z" fill="#25262b"/>` +
      `<path d="M66 86q16-10 30 0l-2 8q-14-4-26 2zM134 86q-16-10-30 0l2 8q14-4 26 2z" fill="#fff"/>` +
      `<path d="M74 52q26-14 52 0" fill="none" stroke="#495057" stroke-width="3" stroke-linecap="round"/>`,
    // little red devil horns on top of the head
    devil_horns: `<path d="M66 60q-12-14-6-36 10 16 22 28z" fill="#e03131" stroke="#a51111" stroke-width="2" stroke-linejoin="round"/>` +
      `<path d="M134 60q12-14 6-36-10 16-22 28z" fill="#e03131" stroke="#a51111" stroke-width="2" stroke-linejoin="round"/>` +
      `<path d="M66 40q2 8 8 12M134 40q-2 8-8 12" fill="none" stroke="#ff8787" stroke-width="2" stroke-linecap="round"/>`,
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
  // in the hand: the laser sword, held in front at the right, the blade glowing upwards
  if (it.hand === "lightsaber") p.push(`<g transform="rotate(-6 160 182)">` +
    `<rect x="151" y="18" width="18" height="140" rx="9" fill="#4dabf7" opacity=".35"/>` +
    `<rect x="155" y="22" width="10" height="134" rx="5" fill="#a5d8ff"/><rect x="157.5" y="26" width="5" height="128" rx="2.5" fill="#fff"/>` +
    `<rect x="153" y="156" width="14" height="38" rx="3" fill="#adb5bd" stroke="#495057" stroke-width="2"/>` +
    `<path d="M153 164h14M153 172h14M153 180h14" stroke="#495057" stroke-width="2"/><rect x="151" y="154" width="18" height="6" rx="2" fill="#495057"/>` +
    `<circle cx="160" cy="186" r="2.5" fill="#e03131"/></g>` +
    `<ellipse cx="156" cy="184" rx="11" ry="9" fill="${skin}" stroke="${dark}" stroke-width="1.5"/>`);
  if (it.neck === "bowtie") p.push(`<path d="M100 150l-18-10v20zM100 150l18-10v20z" fill="#e03131"/><circle cx="100" cy="150" r="4" fill="#c92a2a"/>`);
  const pet = PET_EMOJI[it.pet] || (PET_SVG[it.pet] ? it.pet : "");
  // the pet sits as a badge on top of the circle (bottom right) – not clipped, so it is fully visible.
  // With the pet info of the server (a.pet = {kind, age, stage}): smaller with a bottle as a baby, bigger as an adult,
  // the age in days in a small pill under the emoji.
  const info = a.pet && a.pet.kind === it.pet ? a.pet : null;
  const grow = info ? { baby: 0.8, young: 1, adult: 1.12 }[info.stage] || 1 : 1;
  const r = Math.round((size < 40 ? 30 : 34) * grow), cx = 200 - Math.max(r, 34) - 8, cy = cx;
  let petBadge = "";
  if (pet) {
    const days = info ? I18N.tr(T("{0} days old")).replace("{0}", info.age) : "";
    petBadge = `<g>${info ? `<title>${days.replace(/[<&]/g, "")}</title>` : ""}<circle cx="${cx}" cy="${cy}" r="${r}" fill="#fff" stroke="rgba(0,0,0,.18)" stroke-width="3"/>` +
      (info && info.stage === "egg" ? `<text x="${cx}" y="${cy + r * 0.42}" font-size="${Math.round(r * 1.35)}" text-anchor="middle">🥚</text>`
        : PET_SVG[pet] ? `<g transform="translate(${cx - r * 0.8} ${cy - r * 0.78}) scale(${r * 1.6 / 100})">${PET_SVG[pet]()}</g>`
        : `<text x="${cx}" y="${cy + r * 0.42}" font-size="${Math.round(r * 1.35)}" text-anchor="middle">${pet}</text>`);
    const outfit = info && info.outfit;
    if (outfit) {                       // the outfit of the pet: small, top right of the badge
      const os = Math.round(r * 0.9), ox = cx + r * 0.62, oy = cy - r * 0.72, svg = PET_WEAR_SVG[outfit] || (PET_SHOP_EMOJI[outfit] ? "" : PET_SHOP_SVG[outfit]);
      petBadge += svg ? `<g transform="translate(${ox - os / 2} ${oy - os / 2}) scale(${os / 100})">${svg}</g>`
        : `<text x="${ox}" y="${oy + os * 0.36}" font-size="${os}" text-anchor="middle">${PET_SHOP_EMOJI[outfit] || ""}</text>`;
    }
    if (info && info.stage === "baby") petBadge += `<text x="${cx - r * 0.78}" y="${cy - r * 0.45}" font-size="${Math.round(r * 0.75)}" text-anchor="middle">🍼</text>`;
    if (info && size >= 80) {           // the age only where it can be read (not in the header)
      const label = String(info.age), w = 14 + label.length * 9;
      petBadge += `<rect x="${cx - w / 2}" y="${cy + r - 13}" width="${w}" height="18" rx="9" fill="#5b5bd6" stroke="#fff" stroke-width="2"/>` +
        `<text x="${cx}" y="${cy + r + 1}" font-size="13" font-weight="700" fill="#fff" text-anchor="middle" font-family="system-ui,sans-serif">${label}</text>`;
    }
    petBadge += "</g>";
  }
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
