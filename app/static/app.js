// --- Tablero CRM: arrastrar y soltar ---
(function () {
  const board = document.querySelector(".board");
  if (!board) return;
  let dragged = null;
  board.addEventListener("dragstart", (e) => {
    dragged = e.target.closest(".deal");
    if (dragged) dragged.classList.add("dragging");
  });
  board.addEventListener("dragend", () => {
    if (dragged) dragged.classList.remove("dragging");
    board.querySelectorAll(".col").forEach((c) => c.classList.remove("over"));
  });
  board.querySelectorAll(".col").forEach((col) => {
    col.addEventListener("dragover", (e) => { e.preventDefault(); col.classList.add("over"); });
    col.addEventListener("dragleave", () => col.classList.remove("over"));
    col.addEventListener("drop", async (e) => {
      e.preventDefault();
      if (!dragged) return;
      const res = await fetch(`/crm/deals/${dragged.dataset.id}/move`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage: col.dataset.stage }),
      });
      if (res.ok) location.reload();
    });
  });
})();

// --- Formulario de factura: lineas dinamicas y totales en vivo ---
(function () {
  const body = document.getElementById("lines-body");
  if (!body) return;
  const num = (v) => parseFloat(String(v).replace(",", ".")) || 0;
  const eur = (v) => v.toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const round2 = (v) => Math.round((v + Number.EPSILON) * 100) / 100;

  function recalc() {
    let subtotal = 0; const vat = {};
    body.querySelectorAll("tr").forEach((tr) => {
      const f = (n) => num(tr.querySelector(`[name=${n}]`).value);
      const base = round2(f("quantity") * f("unit_price") * (100 - f("discount")) / 100);
      tr.querySelector(".line-total").textContent = eur(base);
      subtotal += base; vat[f("vat_rate")] = (vat[f("vat_rate")] || 0) + base;
    });
    const vatTotal = Object.entries(vat).reduce((s, [r, b]) => s + round2(b * r / 100), 0);
    const irpf = round2(subtotal * num(document.querySelector("[name=irpf_rate]").value) / 100);
    document.getElementById("t-sub").textContent = eur(subtotal);
    document.getElementById("t-vat").textContent = eur(vatTotal);
    document.getElementById("t-irpf").textContent = "-" + eur(irpf);
    document.getElementById("t-total").textContent = eur(subtotal + vatTotal - irpf) + " €";
  }

  document.getElementById("add-line").addEventListener("click", () => {
    const clone = body.querySelector("tr").cloneNode(true);
    clone.querySelectorAll("input").forEach((i) => {
      if (i.name === "description") i.value = "";
      else if (i.name === "quantity") i.value = "1";
      else if (i.name === "unit_price" || i.name === "discount") i.value = "0";
    });
    body.appendChild(clone); recalc();
  });
  body.addEventListener("click", (e) => {
    if (e.target.classList.contains("rm") && body.querySelectorAll("tr").length > 1) {
      e.target.closest("tr").remove(); recalc();
    }
  });
  document.addEventListener("input", (e) => { if (e.target.closest(".lines") || e.target.name === "irpf_rate") recalc(); });
  recalc();
})();

// --- Formulario de gasto: total en vivo ---
(function () {
  const form = document.getElementById("expense-form");
  if (!form) return;
  const num = (n) => parseFloat(String(form.elements[n].value).replace(",", ".")) || 0;
  function recalc() {
    const base = num("base"), total = base + base * num("vat_rate") / 100 - base * num("irpf_rate") / 100;
    document.getElementById("exp-total").textContent = total.toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  form.addEventListener("input", recalc); recalc();
})();

// --- Confirmaciones ---
document.addEventListener("submit", (e) => {
  const msg = e.target.dataset.confirm;
  if (msg && !confirm(msg)) e.preventDefault();
});
