"use strict";

const API = new URLSearchParams(location.search).get("api") || "http://localhost:8000";
const SHOP_ID = 1;
const UNITS = ["packet", "box", "sack", "dozen", "kg", "gram", "litre", "piece"];
const MAX_EDGE = 1024;

// Per-tab sender id (contract: from sessionStorage).
let sender = null;
try { sender = sessionStorage.getItem("munim-sender"); } catch (_) {}
if (!sender) {
  sender = "web-" + Math.random().toString(36).slice(2, 10);
  try { sessionStorage.setItem("munim-sender", sender); } catch (_) {}
}

const $ = (id) => document.getElementById(id);
let scan = null;        // last /api/scan response
let confirming = false; // in-flight guard

// Everything that came from the API (OCR text especially) goes through this.
function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function setStatus(msg, isError) {
  const s = $("status");
  s.textContent = msg || "";
  s.className = isError ? "error" : "";
}

function show(which) {
  $("capture").hidden = which !== "capture";
  $("review").hidden = which !== "review";
  $("result").hidden = which !== "result";
}

// ---- image downscale (client-side, before upload) -----------------------

async function downscale(file) {
  // imageOrientation applies EXIF rotation, so a sideways phone photo is upright.
  const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
  const scale = Math.min(1, MAX_EDGE / Math.max(bmp.width, bmp.height));
  const w = Math.round(bmp.width * scale), h = Math.round(bmp.height * scale);
  const canvas = document.createElement("canvas");
  canvas.width = w; canvas.height = h;
  canvas.getContext("2d").drawImage(bmp, 0, 0, w, h);
  bmp.close?.();
  return new Promise((res, rej) =>
    canvas.toBlob((b) => (b ? res(b) : rej(new Error("could not encode image"))), "image/jpeg", 0.85));
}

async function api(path, opts) {
  let r;
  try { r = await fetch(API + path, opts); }
  catch (_) { throw new Error("Cannot reach the server. Check the connection."); }
  let data = null;
  try { data = await r.json(); } catch (_) {}
  if (!r.ok) {
    const err = new Error(data?.error || `Server error (${r.status})`);
    err.status = r.status;
    throw err;
  }
  return data;
}

// ---- scan ---------------------------------------------------------------

$("photo").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  e.target.value = ""; // allow re-picking the same file
  if (!file) return;
  document.querySelector(".portrait").classList.add("busy");
  setStatus("Preparing photo…");
  try {
    const blob = await downscale(file);
    setStatus("Reading the bill… this can take several seconds");
    const fd = new FormData();
    fd.append("shop_id", SHOP_ID);
    fd.append("sender", sender);
    fd.append("image", blob, "bill.jpg");
    const qs = new URLSearchParams(location.search).get("fail") ? "?fail=1" : "";
    scan = await api("/api/scan" + qs, { method: "POST", body: fd });
    setStatus("");
    renderReview(scan);
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    document.querySelector(".portrait").classList.remove("busy");
  }
});

// ---- review table -------------------------------------------------------

function unitSelect(item) {
  const opts = (item.unit_ok ? "" : '<option value="">Pick unit…</option>') +
    UNITS.map((u) => `<option value="${u}"${u === item.unit ? " selected" : ""}>${u}</option>`).join("");
  return `<select class="unit${item.unit_ok ? "" : " invalid"}">${opts}</select>`;
}

function itemCell(item) {
  const r = item.resolution;
  if (r.status === "exact" || r.status === "fuzzy") {
    return `<span class="tag ${r.status}">${r.status === "exact" ? "&#10003; matched" : "check match"}</span>
      <div>${esc(r.sku_name)}</div>`;
  }
  if (r.status === "ambiguous") {
    const opts = r.candidates.map((c) => `<option value="${esc(c.sku_id)}">${esc(c.name)}</option>`).join("");
    return `<span class="tag ambiguous">which one?</span>
      <select class="pick invalid"><option value="">Choose item…</option>${opts}
        <option value="new">+ Create new item</option></select>
      <input class="newname" type="text" placeholder="New item name" value="${esc(item.name)}" hidden>`;
  }
  return `<span class="tag unknown">not in catalogue</span>
    <select class="pick invalid"><option value="">Choose…</option>
      <option value="new">+ Create new item</option></select>
    <input class="newname" type="text" placeholder="New item name" value="${esc(item.name)}" hidden>`;
}

function renderReview(s) {
  show("review");
  const banner = $("banner");
  banner.hidden = true;

  $("reply").textContent = s.reply || "";
  $("warnings").innerHTML = (s.warnings || []).map((w) => `<div>&#9888; ${esc(w)}</div>`).join("");
  $("raw").textContent = s.raw_text || "";
  $("rawbox").hidden = !s.raw_text;

  const tbody = $("items").querySelector("tbody");
  tbody.innerHTML = "";

  if (!s.legible) {
    banner.className = "banner illegible";
    banner.textContent = "Couldn't read this photo as a bill. Nothing was added. Try again in good light.";
    banner.hidden = false;
    $("items").closest(".table-wrap").hidden = true;
    $("confirm").hidden = true;
    $("discard").textContent = "Try another photo";
    $("reviewhint").textContent = "";
    return;
  }
  $("items").closest(".table-wrap").hidden = false;
  $("confirm").hidden = false;
  $("discard").textContent = "Discard";
  if (s.confidence === "low") {
    banner.className = "banner low";
    banner.textContent = "Hard to read. Check every line carefully before confirming.";
    banner.hidden = false;
  }

  for (const item of s.items) {
    const tr = document.createElement("tr");
    const st = item.resolution.status;
    tr.className = st === "exact" ? "exact" : st === "fuzzy" ? "fuzzy" : "needs";
    tr.dataset.line = item.line_index;
    tr.innerHTML = `
      <td class="line" data-label="Bill line">${esc(item.line)}</td>
      <td data-label="Item">${itemCell(item)}</td>
      <td data-label="Qty"><input class="qty" type="number" min="0" step="any" value="${esc(item.qty)}"></td>
      <td data-label="Unit">${unitSelect(item)}</td>
      <td data-label="Price ₹"><input class="price" type="number" min="0" step="0.01"
           value="${item.price_paise == null ? "" : esc((item.price_paise / 100).toFixed(2))}"></td>
      <td data-label="Skip"><input class="skip" type="checkbox" aria-label="Skip this line"></td>`;
    tbody.appendChild(tr);
  }
  updateConfirm();
  $("review").scrollIntoView?.({ behavior: "smooth" });
}

$("items").addEventListener("change", onRowChange);
$("items").addEventListener("input", () => scan && updateConfirm());

function onRowChange(e) {
  const tr = e.target.closest("tr");
  if (!tr) return;
  if (e.target.classList.contains("pick")) {
    const isNew = e.target.value === "new";
    tr.querySelector(".newname").hidden = !isNew;
    e.target.classList.toggle("invalid", !e.target.value);
  }
  if (e.target.classList.contains("unit")) e.target.classList.toggle("invalid", !e.target.value);
  if (e.target.classList.contains("skip")) tr.classList.toggle("skipped", e.target.checked);
  updateConfirm();
}

// A row is ready when skipped, or when it has an item, unit and positive qty.
function rowProblem(tr) {
  if (tr.querySelector(".skip").checked) return null;
  const item = scan.items.find((i) => String(i.line_index) === tr.dataset.line);
  const pick = tr.querySelector(".pick");
  if (pick) {
    if (!pick.value) return "choose an item";
    if (pick.value === "new" && !tr.querySelector(".newname").value.trim()) return "name the new item";
  }
  if (!tr.querySelector(".unit").value) return "pick a unit";
  const q = parseFloat(tr.querySelector(".qty").value);
  if (!(q > 0)) return "enter a quantity";
  return item ? null : "unknown line";
}

function updateConfirm() {
  const rows = [...$("items").querySelectorAll("tbody tr")];
  const bad = rows.filter((tr) => rowProblem(tr));
  const allSkipped = rows.every((tr) => tr.querySelector(".skip").checked);
  $("confirm").disabled = confirming || bad.length > 0 || allSkipped;
  $("reviewhint").textContent = bad.length
    ? `${bad.length} line(s) need your attention (${rowProblem(bad[0])}), or skip them.`
    : allSkipped ? "Every line is skipped." : "";
}

function collectDecisions() {
  return [...$("items").querySelectorAll("tbody tr")].map((tr) => {
    const line_index = Number(tr.dataset.line);
    if (tr.querySelector(".skip").checked) return { line_index, action: "skip" };
    const item = scan.items.find((i) => i.line_index === line_index);
    const base = {
      line_index,
      qty: parseFloat(tr.querySelector(".qty").value),
      unit: tr.querySelector(".unit").value,
      price_paise: tr.querySelector(".price").value === ""
        ? null : Math.round(parseFloat(tr.querySelector(".price").value) * 100),
    };
    const pick = tr.querySelector(".pick");
    if (pick && pick.value === "new") {
      return { ...base, action: "new", name: tr.querySelector(".newname").value.trim() };
    }
    const sku_id = pick ? Number(pick.value) : item.resolution.sku_id;
    return { ...base, action: "book", sku_id };
  });
}

// ---- confirm ------------------------------------------------------------

$("confirm").addEventListener("click", async () => {
  if (confirming) return; // double-tap is a no-op
  confirming = true;
  $("confirm").disabled = true;
  $("confirm").textContent = "Saving…";
  try {
    const res = await api("/api/scan/confirm", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ shop_id: SHOP_ID, scan_id: scan.scan_id, decisions: collectDecisions() }),
    });
    renderResult(res);
  } catch (err) {
    $("reviewhint").textContent = err.status === 409
      ? "This bill was already confirmed. Nothing was booked twice."
      : err.message;
    $("confirm").textContent = "Confirm";
    confirming = false;
    updateConfirm();
  }
});

$("discard").addEventListener("click", reset);
$("again").addEventListener("click", reset);

function renderResult(res) {
  show("result");
  window.scrollTo({ top: 0 });
  $("result-reply").textContent = res.reply || "";
  $("result-actions").innerHTML = (res.actions || []).map((a) =>
    `<li>${esc(a.sku_name)}: +${esc(a.qty)} ${esc(a.unit)} &rarr; now ${esc(a.new_qty)}</li>`).join("");
  const learned = $("learned");
  if (res.aliases_learned?.length) {
    learned.innerHTML = res.aliases_learned.map((a) =>
      `I'll remember <b>"${esc(a.text)}"</b> next time, so I won't ask again.`).join("<br>");
    learned.hidden = false;
  } else learned.hidden = true;
}

function reset() {
  scan = null;
  confirming = false;
  $("confirm").textContent = "Confirm";
  $("items").querySelector("tbody").innerHTML = "";
  setStatus("");
  show("capture");
  window.scrollTo({ top: 0 });
}
