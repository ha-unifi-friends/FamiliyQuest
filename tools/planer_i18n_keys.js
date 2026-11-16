// Collect the English texts of the planer UI (family_quest/app/web/planer/src) as keys for the
// Family Quest dictionaries i18n/planer/<lang>.json.
//
//   npm install --prefix /tmp/acorn acorn@8 acorn-walk@8
//   NODE_PATH=/tmp/acorn/node_modules node tools/planer_i18n_keys.js
//
// Sources of English text:
//  - object properties named `en` (TXT = { de: {...}, en: {...} }, labels { de, en })
//  - settings fields F(key, type, de, en, descDe, descEn)
//  - `lang === 'en' ? 'English' : 'Deutsch'`
//  - the English week/plan cards: src/i18n_en.py replacements (strings that only exist in the English variant)
// Planer placeholders like {n} and template expressions ${…} become {0}, {1} … (Family Quest pattern keys).
// Writes family_quest/app/web/i18n/planer/keys.json (sorted). tests/test_planer_i18n.py checks the dictionaries.
"use strict";
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const acorn = require("acorn");
const walk = require("acorn-walk");

const ROOT = path.resolve(__dirname, "..");
const SRC = path.join(ROOT, "family_quest/app/web/planer/src");
const OUT = path.join(ROOT, "family_quest/app/web/i18n/planer/keys.json");

const keys = new Set();

function norm(raw) {
  // HTML → text segments; placeholders → {0}, {1} …
  const out = [];
  const text = raw.replace(/<style[\s\S]*?<\/style>/g, " ").replace(/<!--[\s\S]*?-->/g, " ");
  // title/placeholder/aria-label inside HTML are translated too
  const attrs = [...text.matchAll(/\b(?:title|placeholder|aria-label|alt)="([^"]*)"/g)].map(m => m[1]);
  for (let seg of [...text.split(/<[^>]*>/), ...attrs]) {
    seg = seg.replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"');
    seg = seg.replace(/\s+/g, " ").trim();
    if (!seg) continue;
    let i = 0;
    const map = new Map();
    seg = seg.replace(/\{([a-zA-Z_]\w*|\d+|§\d+)\}/g, (m, name) => {
      if (!map.has(name)) map.set(name, i++);
      return `{${map.get(name)}}`;
    });
    const letters = seg.replace(/\{\d+\}/g, "").replace(/[^A-Za-z]/g, "");
    if (letters.length < 2) continue;
    if (/^(mdi|av2?|svg|img|fp\d?|http|https|calendar|todo|weather|sensor|person|notify):/.test(seg)) continue;
    if (/^[a-z][\w.-]*$/.test(seg) && !/^(on|off|open|all|done|ok|from|to|in|at|and|or|no|yes|points?|min|today|tomorrow)$/.test(seg)) continue;
    if (/[;{}]\s*$|^[.#][\w-]+|^\w+\(|=>|===|\bvar\(--|^[\w-]+\s*:\s*[\w#-]+;?$/.test(seg.replace(/\{\d+\}/g, ""))) continue;
    out.push(seg);
  }
  return out;
}

function strings(node, src) {
  const res = [];
  walk.full(node, n => {
    if (n.type === "Literal" && typeof n.value === "string") res.push(n.value);
    else if (n.type === "TemplateLiteral") {
      let s = "";
      n.quasis.forEach((q, i) => { s += q.value.cooked ?? q.value.raw; if (i < n.expressions.length) s += `{§${i}}`; });
      res.push(s);
    }
  });
  // TemplateLiteral quasis are Literal-free; but walk.full also visits nested template literals inside expressions
  return res;
}

function addAll(node, src) { for (const s of strings(node, src)) for (const k of norm(s)) keys.add(k); }

function harvest(code, file) {
  let ast;
  try { ast = acorn.parse(code, { ecmaVersion: "latest", sourceType: "script", allowHashBang: true }); }
  catch (e) { throw new Error(`${file}: ${e.message}`); }
  walk.full(ast, n => {
    if (n.type === "Property" && ((n.key.type === "Identifier" && n.key.name === "en") || (n.key.type === "Literal" && n.key.value === "en"))) addAll(n.value, code);
    else if (n.type === "CallExpression" && n.callee.type === "Identifier" && n.callee.name === "F" && n.arguments.length >= 6) {
      addAll(n.arguments[3], code); addAll(n.arguments[5], code);
    } else if (n.type === "CallExpression" && n.callee.type === "Identifier" && n.callee.name === "lbl" && n.arguments.length >= 2) {
      addAll(n.arguments[1], code);                                   // lbl('Deutsch', 'English')
    } else if (n.type === "CallExpression" && n.callee.type === "MemberExpression" && code.slice(n.callee.start, n.callee.end) === "Object.assign"
               && n.arguments.length >= 2 && /\.en\b/.test(code.slice(n.arguments[0].start, n.arguments[0].end))) {
      for (const a of n.arguments.slice(1)) addAll(a, code);          // Object.assign(T.en.n, {...})
    } else if (n.type === "ArrayExpression" && n.elements.length >= 3 && n.elements.slice(0, 2).every(e => e && e.type === "Literal" && typeof e.value === "string")
               && n.elements[2] && n.elements[2].type === "Literal" && typeof n.elements[2].value === "number") {
      addAll(n.elements[1], code);                                    // ["Deutsch", "English", 1, {...}] (avatar items)
    } else if (n.type === "ConditionalExpression") {
      const test = code.slice(n.test.start, n.test.end);
      if (/===\s*'en'|==\s*'en'/.test(test)) addAll(n.consequent, code);
      else if (/!==\s*'en'/.test(test)) addAll(n.alternate, code);
    }
  });
  return ast;
}

function literals(code) {
  const set = new Set();
  const ast = acorn.parse(code, { ecmaVersion: "latest", sourceType: "script" });
  for (const s of strings(ast, code)) for (const k of norm(s)) set.add(k);
  return set;
}

for (const f of fs.readdirSync(SRC).filter(f => f.endsWith(".js") && !f.startsWith("eslint"))) {
  harvest(fs.readFileSync(path.join(SRC, f), "utf8"), f);
}

// English week/plan cards: apply src/i18n_en.py and take the strings that only exist in the English variant
const py = `
import json, sys, pathlib
sys.path.insert(0, ${JSON.stringify(SRC)})
from i18n_en import PLAN, WEEK
src = pathlib.Path(${JSON.stringify(SRC)})
out = {}
for name, pairs in (("ui_week.js", WEEK), ("ui_plan.js", PLAN)):
    de = (src / name).read_text(encoding="utf-8")
    en = de
    for a, b in pairs:
        en = en.replace(a, b)
    out[name] = [de, en]
print(json.dumps(out))
`;
const variants = JSON.parse(execFileSync("python3", ["-c", py], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 }));
for (const [name, [de, en]] of Object.entries(variants)) {
  const deSet = literals(de);
  for (const k of literals(en)) if (!deSet.has(k)) keys.add(k);
}

// texts that web/planer/build_fq.py puts in instead of Home Assistant menus
for (const k of ["No list set up yet. Planner → Settings → Lists.", "The module \"{0}\" is switched off. Switch it on under Planner → Settings → General.",
                 "Cropped to a square and stored only in Family Quest.", "Level {0} · {1}", "pts", "points"]) keys.add(k);
for (const k of ["-en", "(until"]) keys.delete(k);                  // code fragments, not UI text
for (const k of [...keys]) if (/Devices & services|Home Assistant\.$|your Home Assistant/.test(k)) keys.delete(k);

const list = [...keys].sort((a, b) => a.localeCompare(b, "en"));
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(list, null, 1) + "\n");
console.log(`${list.length} keys → ${path.relative(ROOT, OUT)}`);
