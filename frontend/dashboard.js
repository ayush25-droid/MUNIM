"use strict";

const API = new URLSearchParams(location.search).get("api") || "http://localhost:8000";
const esc = (v) => String(v ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function load() {
  const status = document.getElementById("status");
  try {
    const r = await fetch(`${API}/api/inventory?shop_id=1`);
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || `Server error (${r.status})`);
    document.querySelector("#stock tbody").innerHTML = data.items.map((i) => `
      <tr class="${i.low ? "low-row" : ""}">
        <td>${esc(i.name)}${i.low ? '<span class="chip-low">Running low</span>' : ""}</td>
        <td class="num" data-label="Qty">${esc(i.qty)}</td>
        <td data-label="Unit">${esc(i.unit)}</td>
        <td class="num" data-label="Cost &#8377;">${esc((i.cost_per_unit / 100).toFixed(2))}</td>
        <td class="num" data-label="Days left">${i.days_of_cover == null ? "&ndash;" : esc(i.days_of_cover)}</td>
      </tr>`).join("");
    const low = data.items.filter((i) => i.low).length;
    document.getElementById("summary").textContent =
      `${data.items.length} items` + (low ? `, ${low} running low.` : ", none running low.");
    status.textContent = "";
  } catch (err) {
    status.textContent = err.message || "Cannot reach the server.";
    status.className = "error";
  }
}
load();
