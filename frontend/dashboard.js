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
        <td>${esc(i.name)}</td>
        <td class="num">${esc(i.qty)}</td>
        <td>${esc(i.unit)}</td>
        <td class="num">${esc((i.cost_per_unit / 100).toFixed(2))}</td>
        <td class="num">${i.days_of_cover == null ? "&ndash;" : esc(i.days_of_cover)}</td>
      </tr>`).join("");
    status.textContent = "";
  } catch (err) {
    status.textContent = err.message || "Cannot reach the server.";
    status.className = "error";
  }
}
load();
