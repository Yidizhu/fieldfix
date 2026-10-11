"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const vm = require("node:vm");

const staticDir = path.resolve(__dirname, "../static");
const source = fs.readFileSync(path.join(staticDir, "i18n.js"), "utf8");
function rows(name) {
  const match = source.match(new RegExp("const " + name + " = \\[([\\s\\S]*?)\\n  \\];"));
  assert.ok(match, name);
  return JSON.parse("[" + match[1].replace(/,\s*$/, "") + "]");
}
const baseRows = rows("rows"), extraRows = rows("extraRows");
const packs = {"zh-CN": {}, en: {}, es: {}, fr: {}, pt: {}};
baseRows.forEach(([key, zh, en]) => {packs["zh-CN"][key] = zh; packs.en[key] = en;});
extraRows.forEach(([key, es, fr, pt]) => {packs.es[key] = es; packs.fr[key] = fr; packs.pt[key] = pt;});
const locales = ["en", "zh-CN", "es", "fr", "pt"];
const parameters = value => [...value.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort();

function boot({languages=["en"], language="en", saved, failStorage=false}={}) {
  const stored = new Map();
  if (saved !== undefined) stored.set("fieldfix:locale", saved);
  const localStorage = {
    getItem(key) {if(failStorage) throw Error("blocked"); return stored.get(key) ?? null;},
    setItem(key, value) {if(failStorage) throw Error("blocked"); stored.set(key, String(value));}
  };
  const context = {window: {}, navigator:{languages, language}, localStorage};
  // No document, fetch or network are provided: i18n cannot replace draft DOM.
  vm.runInNewContext(source, context);
  return {api:context.window.FieldFixI18n, stored};
}

test("all five packs have every message exactly once", () => {
  assert.equal(baseRows.length, 287);
  assert.equal(extraRows.length, baseRows.length);
  assert.equal(new Set(baseRows.map(r=>r[0])).size, baseRows.length);
  assert.equal(new Set(extraRows.map(r=>r[0])).size, extraRows.length);
  const keys = Object.keys(packs.en).sort();
  for(const locale of locales) {
    assert.deepEqual(Object.keys(packs[locale]).sort(), keys);
    for(const key of keys) assert.equal(typeof packs[locale][key], "string", locale+":"+key);
  }
});

test("all original 286 Chinese and English messages remain unchanged", () => {
  const originals = baseRows.filter(row => row[0] !== "research_language_fallback");
  const sha = crypto.createHash("sha256").update(JSON.stringify(originals), "utf8").digest("hex");
  assert.equal(sha, "85a05b2f748a3ea816a24d8ec3303299f425e8301721a82980553b559fcd6f31");
});

test("all 1435 localized messages preserve exact placeholder names and multiplicity", () => {
  for(const [key, template] of Object.entries(packs.en)) {
    for(const locale of locales) {
      const translated=packs[locale][key];
      assert.ok(translated.trim().length, locale+":"+key);
      assert.deepEqual(parameters(translated), parameters(template), locale+":"+key);
      assert.ok(!/[<>][a-z]/i.test(translated), "UI messages remain plain text");
    }
  }
});

test("all messages render from their own pack, with no accidental English fallback", () => {
  const {api}=boot();
  for(const locale of locales) {
    for(const [key, template] of Object.entries(packs[locale])) {
      const params=Object.fromEntries(parameters(template).map(name=>[name, "VALUE_"+name]));
      const result=api.text(locale,key,params);
      const expected=template.replace(/\{(\w+)\}/g, (_, name)=>params[name]);
      assert.equal(result,expected,locale+":"+key);
      assert.ok(!/\{\w+\}/.test(result));
    }
  }
});

test("language variants normalize for explicit text and supported locale detection", () => {
  const {api}=boot();
  for(const [tag, expected] of [["es-MX","es"],["es-ES","es"],["fr-CA","fr"],["fr-FR","fr"],["pt-BR","pt"],["pt-PT","pt"],["PT_br","pt"],["zh-Hans-CN","zh-CN"],["en-NZ","en"]]) {
    assert.equal(api.normalize(tag), expected);
    assert.equal(api.text(tag,"save_review"),api.text(expected,"save_review"));
    assert.equal(boot({languages:[tag]}).api.detect(),expected);
  }
  assert.deepEqual(Array.from(api.supported).sort(),locales.slice().sort());
});

test("browser preference order and saved variants are respected", () => {
  assert.equal(boot({languages:["de-DE","fr-CA","es-MX"]}).api.detect(),"fr");
  assert.equal(boot({languages:["pt-BR","en-NZ"]}).api.detect(),"pt");
  assert.equal(boot({languages:["es-MX"],saved:"fr-CA"}).api.detect(),"fr");
  assert.equal(boot({languages:[],language:"es-AR"}).api.detect(),"es");
});

test("locale preferences are normalized on read and write without touching other state", () => {
  const {api,stored}=boot({saved:"pt-BR"});
  assert.equal(api.read("fieldfix:locale"),"pt");
  api.write("fieldfix:locale","fr-CA");
  assert.equal(stored.get("fieldfix:locale"),"fr");
  api.write("fieldfix:locale","es-419");
  assert.equal(api.detect(),"es");
  api.write("fieldfix:time-zone","local");
  const draft='现场笔记 / revisão / café — NZD 25.00 {amount}';
  api.write("draft",draft);
  api.write("fieldfix:locale","pt-PT");
  assert.equal(api.read("fieldfix:time-zone"),"local");
  assert.equal(api.read("draft"),draft);
});

test("unsupported or blocked storage has a safe predictable fallback", () => {
  const {api,stored}=boot({saved:"fr-CA",languages:["es"]});
  api.write("fieldfix:locale","not-a-locale");
  assert.equal(stored.get("fieldfix:locale"),"fr-CA");
  assert.equal(boot({saved:"not-a-locale",languages:["it","pt-PT"]}).api.detect(),"pt");
  assert.equal(boot({languages:["de-DE"]}).api.detect(),"en");
  const blocked=boot({failStorage:true,languages:["es-MX"]}).api;
  assert.equal(blocked.detect(),"es");
  assert.doesNotThrow(()=>blocked.write("fieldfix:locale","pt-BR"));
  assert.equal(blocked.read("fieldfix:locale"),null);
});

test("amount, currency, timestamps, zero and free text remain literal parameter data", () => {
  const {api}=boot();
  const params=Object.freeze({amount:"NZD 25.00",time:"2026-10-11T12:34:00Z",zone:"Pacific/Auckland",count:0,case:"FF-102"});
  for(const locale of locales) {
    assert.ok(api.text(locale,"charge_confirm",params).includes("NZD 25.00"));
    assert.ok(api.text(locale,"authorization_expires",params).includes(params.time));
    assert.ok(api.text(locale,"notes_original",params).includes(params.zone));
    assert.ok(api.text(locale,"history",params).includes("0"));
    assert.ok(api.text(locale,"checkout_returned",params).includes("FF-102"));
    assert.ok(api.text(locale,"charge_confirm").includes("{amount}"));
  }
});

test("authorization, charge and void keep distinct translated meanings", () => {
  const {api}=boot();
  assert.match(api.text("es","payment_authorized"),/sin cobrar/);
  assert.match(api.text("fr","payment_authorized"),/non débité/);
  assert.match(api.text("pt","payment_authorized"),/não cobrado/);
  assert.match(api.text("es","void_confirm"),/no es reembolsar/);
  assert.match(api.text("fr","void_confirm"),/n’est pas un remboursement/);
  assert.match(api.text("pt","void_confirm"),/não é reembolsar/);
  for(const locale of locales) {
    assert.notEqual(api.text(locale,"payment_authorized"),api.text(locale,"payment_completed"));
    assert.notEqual(api.text(locale,"payment_voided"),api.text(locale,"payment_completed"));
    for(const key of ["charge_confirm","approve_confirm"]) assert.equal(parameters(packs[locale][key]).filter(p=>p==="amount").length,1);
  }
});

test("static HTML and literal daily app messages all have translations", () => {
  const html=fs.readFileSync(path.join(staticDir,"index.html"),"utf8");
  const app=fs.readFileSync(path.join(staticDir,"app.js"),"utf8");
  const keys=[
    ...Array.from(html.matchAll(/data-i18n(?:-aria)?="([\w-]+)"/g),m=>m[1]),
    ...Array.from(app.matchAll(/\bt\(\s*["']([\w-]+)["']/g),m=>m[1]).filter(k=>!k.endsWith("_"))
  ];
  for(const key of keys) for(const locale of locales) assert.ok(packs[locale][key],locale+":"+key);
});

test("dynamic main-workflow message families cover normal and blocked states", () => {
  const keys=[
    ...["shared_connection","reading_anomaly","normal","insufficient_data","completed","voided","reviewed","pending","legacy","payment","awaiting_buyer","quote","authorize","warranty","recovery","charge"].map(k=>"next_"+k),
    ...["shared_connection","reading_anomaly","normal","insufficient_data","recorded","pending","legacy","payment","awaiting_buyer","quote","authorize","warranty","recovery","charge"].map(k=>"why_"+k),
    ...["awaiting_buyer","authorized","completed","voided","pending","expired","denied","unknown"].map(k=>"payment_"+k),
    ...["pass","fail","insufficient"].map(k=>"recovery_"+k),
    ...["pass","fail","insufficient"].map(k=>"check_"+k),
    ...["median_residual_vwc","detection_observed_points","flat_duration_hours","trailing_missing_hours","historical_noise_vwc"].map(k=>"ai_signal_"+k),
    ...["shared","shift","stuck","gap","normal","insufficient","unavailable","disagreement"].map(k=>"ai_"+k+"_reason")
  ];
  for(const key of keys) for(const locale of locales) assert.ok(packs[locale][key],locale+":"+key);
});

test("research fallback is explicit and missing keys still fail visibly", () => {
  const {api}=boot();
  for(const locale of ["es","fr","pt"]) assert.ok(api.text(locale,"research_language_fallback").length>40);
  assert.equal(api.text("unknown","save_review"),packs.en.save_review);
  assert.throws(()=>api.text("fr","nonexistent_key"),/Missing UI message/);
  assert.throws(()=>api.text("fr","__proto__"),/Missing UI message/);
  assert.ok(Object.isFrozen(api));
  assert.ok(Object.isFrozen(api.supported));
});
