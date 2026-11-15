// director skill — ตรวจการ์ดก่อน render: node scripts/card_check.mjs index.html CHROME_PATH → JSON
// error ในหน้า (timeline พัง = การ์ดว่าง) · ฟอนต์ที่ประกาศแต่โหลดไม่ขึ้น · ตัวหนังสือไทยโดนตัด (สระบน/วรรณยุกต์/สระล่าง)
// · ข้อความบนจอเกิน 8 คำ · ข้อความหลุดขอบเฟรม — ไล่ timeline ทุก 0.25 วิ
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import path from "node:path";

const [html, chrome] = process.argv.slice(2);
const require = createRequire(path.join(path.dirname(path.resolve(html)), "package.json"));
const puppeteer = require("puppeteer-core");
const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ["--no-sandbox", "--allow-file-access-from-files"] });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.message || e)));
  await page.evaluateOnNewDocument(() => { window.__timelines = window.__timelines || {}; });
  await page.setViewport({ width: 1080, height: 1920 });
  await page.goto(pathToFileURL(path.resolve(html)).href, { waitUntil: "networkidle0", timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  // a variable / subset-split face loads its Thai file only when Thai text is drawn with it: ask for it before measuring
  await page.evaluate(async () => {
    const want = new Set();
    for (const el of document.querySelectorAll("[data-composition-id] *")) {
      if (el.childElementCount || !/[\u0E00-\u0E7F]/.test(el.textContent)) continue;
      const cs = getComputedStyle(el);
      want.add(`${cs.fontStyle === "italic" ? "italic " : ""}${cs.fontWeight} 48px ${cs.fontFamily}`);
    }
    await Promise.all([...want].map((f) => document.fonts.load(f, "กขคงจฉ่้ิีุู").catch(() => [])));
    await document.fonts.ready;
  });
  const got = await page.evaluate(() => {
    const root = document.querySelector("[data-composition-id]");
    if (!root) return { fatal: "ไม่มี element ที่มี data-composition-id" };
    root.style.width = root.dataset.width + "px"; root.style.height = root.dataset.height + "px";
    const tl = window.__timelines[root.dataset.compositionId];
    if (!tl) return { fatal: `ไม่ได้ลงทะเบียน window.__timelines["${root.dataset.compositionId}"]` };
    const W = +root.dataset.width, H = +root.dataset.height, dur = +root.dataset.duration;
    // fonts declared in CSS that never loaded fall back silently (a Thai serif/loop font shows up instead)
    // checked at the weight actually used (a card that only uses 600/800 never loads 400 — that is not a fault)
    const fams = new Map();
    for (const el of root.querySelectorAll("*")) {
      if (el.childElementCount || !el.textContent.trim()) continue;
      const cs = getComputedStyle(el), f = cs.fontFamily.split(",")[0].replace(/["']/g, "").trim();
      const k = f + "|" + cs.fontWeight + "|" + cs.fontStyle;      // sample = this element's own text (a Thai subset is a separate file)
      fams.set(k, [f, cs.fontWeight, cs.fontStyle, ((fams.get(k) || [])[3] || "") + el.textContent.trim().slice(0, 12)]);
    }
    // Thai text in a face with no Thai glyphs falls back silently and fonts.check() still says yes (outside its
    // unicode-range): measure the Thai text with the face and with the bare fallback — equal widths = not this face
    const cv = document.createElement("canvas").getContext("2d"), noThai = new Set();
    for (const [f, w, st, smp] of fams.values()) {
      const th = (smp.match(/[\u0E00-\u0E7F]+/g) || []).join("");
      if (!th || /^(sans-serif|serif|monospace|system-ui)$/.test(f)) continue;
      // what the faces declare: a subset with a Thai range = has Thai; only Latin ranges = no Thai (Inter, Plex Mono…)
      const faces = [...document.fonts].filter((x) => x.family.replace(/["']/g, "") === f);
      const thaiIn = (r) => r.split(",").some((p) => { const m = p.trim().match(/U\+([0-9A-F?]+)(?:-([0-9A-F]+))?/i);
        if (!m) return false; const a = parseInt(m[1].replace(/\?/g, "0"), 16), b = m[2] ? parseInt(m[2], 16) : parseInt(m[1].replace(/\?/g, "F"), 16);
        return a <= 0x0E7F && b >= 0x0E00; });
      const ranged = faces.filter((x) => x.unicodeRange && x.unicodeRange.toUpperCase() !== "U+0-10FFFF");
      if (ranged.length && !ranged.some((x) => thaiIn(x.unicodeRange))) { noThai.add(`${f} ${w}`); continue; }
      if (ranged.length || !faces.length) continue;      // a Thai subset exists, or a system font: trust it
      // one full-range local file: measure against two fallbacks (equal to both = the face has no Thai glyphs)
      const m = (fam) => { cv.font = `${st === "italic" ? "italic " : ""}${w} 48px ${fam}`; return cv.measureText(th).width; };
      if (Math.abs(m(`"${f}", serif`) - m("serif")) < 0.5 && Math.abs(m(`"${f}", monospace`) - m("monospace")) < 0.5) noThai.add(`${f} ${w}`);
    }
    const fonts = [...noThai].map((x) => x + " (ไม่มีตัวไทย)").concat([...new Set([...fams.values()].filter(([f, w, st, smp]) => !/^(sans-serif|serif|monospace|system-ui)$/.test(f)
      && !document.fonts.check(`${st === "italic" ? "italic " : ""}${w} 32px "${f}"`, smp)).map(([f, w]) => `${f} ${w}`))]);
    const clip = new Map(), dense = new Map(), out = new Map(), lastBox = new Map();
    // Thai has no spaces between words: count with the browser's Thai word segmenter, not by whitespace
    const seg = new Intl.Segmenter("th", { granularity: "word" });
    const words = (s) => [...seg.segment(s)].filter((x) => x.isWordLike).length;
    for (let t = 0; t <= dur; t += 0.25) {
      tl.seek(t, false);
      const shown = [];
      const blocks = new Set();
      for (const el of root.querySelectorAll("*")) {
        if (el.childElementCount || !el.textContent.trim()) continue;
        if (el.closest("[aria-hidden=true], [data-deco], [data-legal]")) continue;   // decoration / required fine print      // echo copies, glow layers: decoration, not words
        const cs = getComputedStyle(el); if (cs.visibility === "hidden") continue;
        // opacity does not inherit in computed style: a child of a hidden (opacity 0) parent reads 1 — multiply up the tree
        let op = 1; for (let a = el; a && a !== root.parentElement; a = a.parentElement) op *= +getComputedStyle(a).opacity;
        if (op < 0.2) continue;
        const r = el.getBoundingClientRect(); if (r.width < 2) continue;
        const txt = el.textContent.trim().slice(0, 30);
        // inside a clipping box (mask): fully outside it = hidden on purpose (not on screen, not words)
        let hiddenByMask = false;
        for (let a = el.parentElement; a && a !== root; a = a.parentElement) {
          const sa = getComputedStyle(a);
          if (sa.overflow === "visible" && sa.overflowY === "visible" && sa.clipPath === "none") continue;
          const b = a.getBoundingClientRect();
          if (r.bottom <= b.top + 1 || r.top >= b.bottom - 1 || r.right <= b.left + 1 || r.left >= b.right - 1) hiddenByMask = true;
          break;
        }
        if (hiddenByMask) continue;
        // a word split into spans (typewriter, per-letter moves) is ONE block: count its parent's text once
        const par = el.parentElement;
        const inline = (c) => !c.childElementCount && /^inline/.test(getComputedStyle(c).display);   // letters in one line, not stacked boxes
        const blk = par && par !== root && par.childElementCount > 1 && [...par.children].every(inline) ? par : el;
        const key = blk.textContent.trim();                 // the same text twice on screen (echo, shadow copy) reads once
        if (!blocks.has(blk) && !shown.some((x) => x.trim() === key)) { blocks.add(blk); shown.push(blk.textContent); }
        // Thai marks above/below the line: the GLYPHS (a Range over the text) reach past the nearest box that clips —
        // compare the text's own ink box with that box, not the box's scroll size (a big background layer inside
        // #root made every line look clipped)
        if (/[\u0E31\u0E34-\u0E3A\u0E47-\u0E4E]/.test(el.textContent) && !clip.has(txt)) {
          const rg = document.createRange(); rg.selectNodeContents(el);
          const ink = rg.getBoundingClientRect(), pad = parseFloat(cs.fontSize) * 0.12;   // marks sit ~12 % beyond the line box
          for (let a = el; a && a !== root; a = a.parentElement) {
            const s = getComputedStyle(a);
            if (s.overflow === "visible" && s.overflowY === "visible" && s.clipPath === "none") continue;
            const b = a.getBoundingClientRect();
            // a mask reveal moves the text RELATIVE to its box; a box that clips its own text moves with it —
            // so judge only when the text sits still inside the box (same offset as the last sample)
            const rel = `${Math.round(ink.top - b.top)},${Math.round(ink.bottom - b.bottom)}`;
            const still = lastBox.get(el) === rel; lastBox.set(el, rel);
            if (still && (ink.top - pad < b.top - 1 || ink.bottom + pad > b.bottom + 1)) clip.set(txt, +t.toFixed(2));
            break;
          }
        }
        if (+cs.fontSize >= 0 && (r.left < -2 || r.right > W + 2 || r.top < -2 || r.bottom > H + 2) && !out.has(txt)) out.set(txt, +t.toFixed(2));
      }
      const n = shown.reduce((s, x) => s + words(x), 0);
      if (n > 10 && !dense.has(n)) dense.set(n, +t.toFixed(2));
    }
    const seq = new Map(), pops = [];
    for (let t = 0; t <= dur; t += 0.1) {
      tl.seek(t, false);
      for (const el of root.querySelectorAll("*")) {
        const r = el.getBoundingClientRect(); if (r.width * r.height < 400) continue;
        const o = +getComputedStyle(el).opacity, st = o > 0.6 ? "on" : o < 0.1 ? "off" : null; if (!st) continue;
        const q = seq.get(el) || { s: [], t: [] }; if (q.s[q.s.length - 1] !== st) { q.s.push(st); q.t.push(+t.toFixed(2)); } seq.set(el, q);
      }
    }
    for (const [el, q] of seq) if (q.s[0] === "on" && q.s[1] === "off" && q.s[2] === "on" && q.t[1] > 0.15 && !el.closest("[data-intro-ok]"))
      pops.push({ text: (el.textContent || el.id || el.tagName).trim().slice(0, 30), t: q.t[1], back: q.t[2] });
    return { pops: pops.slice(0, 6), fonts, clip: [...clip].map(([text, t]) => ({ text, t })), dense: [...dense].map(([n, t]) => ({ n, t })).slice(0, 3),
             out: [...out].map(([text, t]) => ({ text, t })).slice(0, 5), cues: window.__cues || [] };
  });
  process.stdout.write(JSON.stringify({ errors, ...got }));
} finally {
  await browser.close();
}
