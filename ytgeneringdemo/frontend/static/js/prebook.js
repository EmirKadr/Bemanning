import { state, agencyColor, showToast } from "./state.js";

const expandAllBtn = document.getElementById("expand-all");
let allExpanded = false;

export async function loadOverview(day) {
  let rows;
  try {
    const res = await fetch(`/api/prebook?day=${day}`);
    if (!res.ok) throw new Error(res.status);
    rows = await res.json();
  } catch (e) {
    showToast("Failed to load prebook.");
    return;
  }

  const grouped = new Map();
  rows.forEach(({ agency_alias, custom_num, day_num, custom_desc, weight_kg, assign_weight, pall_required, assign_pall }) => {
    if (!grouped.has(agency_alias)) grouped.set(agency_alias, []);
    grouped.get(agency_alias).push({ custom_num, day_num, custom_desc, weight_kg, assign_weight, pall_required, assign_pall });
  });

  const sorted = [...grouped.entries()].sort(
    (a, b) => state.agencyOrder.indexOf(a[0]) - state.agencyOrder.indexOf(b[0])
  );

  allExpanded = false;
  expandAllBtn.textContent = "Expand all";

  const list = document.getElementById("legend-list");
  list.innerHTML = "";

  sorted.forEach(([alias, customers]) => {
    const color = agencyColor(alias);
    const li = document.createElement("li");
    li.className = "agency-item";

    const header = document.createElement("div");
    header.className = "agency-header";
    header.innerHTML = `
      <div class="agency-header-left">
        <span class="legend-swatch" style="background:${color}"></span>
        <span class="legend-label">${alias}</span>
      </div>
      <span class="agency-chevron">›</span>
    `;

    const body = document.createElement("ul");
    body.className = "agency-customers";
    body.style.borderLeftColor = color;

    customers.forEach(({ custom_num, day_num, custom_desc, weight_kg, assign_weight, pall_required, assign_pall }) => {
      const row = document.createElement("li");
      row.className = "customer-row";

      const weightChanged = assign_weight !== weight_kg;
      const pallChanged   = assign_pall !== pall_required;
      const isEdited      = weightChanged || pallChanged;
      const origWeight = weightChanged ? ` <span class="customer-weight-orig">(${weight_kg})</span>` : "";
      const origPall   = pallChanged   ? ` <span class="customer-weight-orig">(${pall_required})</span>` : "";

      row.innerHTML = `
        <span class="customer-name">${custom_desc}</span>
        <span class="customer-meta">
          <span class="customer-weight" title="Double-click to edit">${assign_weight}</span> kg${origWeight} · <span class="customer-pall">${assign_pall}${origPall} pall</span>
          ${isEdited ? `<button class="customer-reset" title="Reset to original">↺</button>` : ""}
        </span>
      `;

      row.dataset.customNum    = custom_num;
      row.dataset.dayNum       = day_num;
      row.dataset.weightKg     = weight_kg;
      row.dataset.pallRequired = pall_required;

      body.appendChild(row);
    });

    body.addEventListener("click", (e) => {
      const btn = e.target.closest(".customer-reset");
      if (!btn) return;
      const row      = btn.closest(".customer-row");
      const custNum  = parseInt(row.dataset.customNum);
      const dayNum   = parseInt(row.dataset.dayNum);
      const weightKg = parseFloat(row.dataset.weightKg);

      fetch("/api/prebook", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ custom_num: custNum, day_num: dayNum, assign_weight: weightKg }),
      }).then(r => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      }).then(data => {
        const weightSpan = row.querySelector(".customer-weight");
        if (weightSpan) {
          weightSpan.textContent = weightKg;
          const weightOrigEl = weightSpan.nextElementSibling?.classList.contains("customer-weight-orig")
            ? weightSpan.nextElementSibling : null;
          if (weightOrigEl) weightOrigEl.remove();
        }
        const pallEl = row.querySelector(".customer-pall");
        if (pallEl) pallEl.innerHTML = `${data.pall_required} pall`;
        btn.remove();
      }).catch(() => showToast("Failed to reset weight."));
    });

    body.addEventListener("dblclick", (e) => {
      const span = e.target.closest(".customer-weight");
      if (!span || span.querySelector("input")) return;
      const row        = span.closest(".customer-row");
      const custom_num = parseInt(row.dataset.customNum);
      const day_num    = parseInt(row.dataset.dayNum);
      const original   = parseFloat(span.textContent);

      const input = document.createElement("input");
      input.type = "number";
      input.value = original;
      input.className = "weight-edit-input";
      span.replaceWith(input);
      input.focus();
      input.select();

      const commit = async () => {
        const val    = parseFloat(input.value);
        const newVal = isNaN(val) ? original : val;
        const newSpan = document.createElement("span");
        newSpan.className = "customer-weight";
        newSpan.title = "Double-click to edit";
        newSpan.textContent = newVal;
        input.replaceWith(newSpan);

        const weightKg = parseFloat(row.dataset.weightKg);

        const weightOrigEl = newSpan.nextElementSibling?.classList.contains("customer-weight-orig")
          ? newSpan.nextElementSibling : null;
        if (newVal !== weightKg) {
          if (weightOrigEl) weightOrigEl.textContent = `(${weightKg})`;
          else newSpan.insertAdjacentHTML("afterend", ` <span class="customer-weight-orig">(${weightKg})</span>`);
        } else {
          if (weightOrigEl) weightOrigEl.remove();
        }

        if (newVal !== original) {
          try {
            const res = await fetch("/api/prebook", {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ custom_num, day_num, assign_weight: newVal }),
            });
            if (!res.ok) throw new Error(res.status);
            const data = await res.json();
            const pallEl = row.querySelector(".customer-pall");
            if (pallEl) {
              const origPall   = row.dataset.pallRequired;
              const pallChanged = data.pall_required !== origPall;
              pallEl.innerHTML = `${data.pall_required}${pallChanged ? ` <span class="customer-weight-orig">(${origPall})</span>` : ""} pall`;
            }
          } catch (e) {
            showToast("Failed to save weight.");
          }
        }

        const meta       = row.querySelector(".customer-meta");
        const pallEl     = row.querySelector(".customer-pall");
        const isEdited   = (newVal !== weightKg) || !!pallEl?.querySelector(".customer-weight-orig");
        const resetBtn   = meta?.querySelector(".customer-reset");
        if (isEdited && !resetBtn) {
          const btn = document.createElement("button");
          btn.className = "customer-reset";
          btn.title = "Reset to original";
          btn.textContent = "↺";
          meta.appendChild(btn);
        } else if (!isEdited && resetBtn) {
          resetBtn.remove();
        }
      };

      input.addEventListener("blur", commit);
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") input.blur();
        if (e.key === "Escape") {
          const newSpan = document.createElement("span");
          newSpan.className = "customer-weight";
          newSpan.title = "Double-click to edit";
          newSpan.textContent = original;
          input.replaceWith(newSpan);
        }
      });
    });

    header.addEventListener("click", () => {
      const open = li.classList.toggle("open");
      header.querySelector(".agency-chevron").style.transform = open ? "rotate(90deg)" : "";
    });

    li.appendChild(header);
    li.appendChild(body);
    list.appendChild(li);
  });
}

expandAllBtn.addEventListener("click", () => {
  allExpanded = !allExpanded;
  document.querySelectorAll(".agency-item").forEach(item => {
    item.classList.toggle("open", allExpanded);
    const chevron = item.querySelector(".agency-chevron");
    if (chevron) chevron.style.transform = allExpanded ? "rotate(90deg)" : "";
  });
  expandAllBtn.textContent = allExpanded ? "Collapse all" : "Expand all";
});

const prebookOverlay = document.getElementById("prebook-overlay");

document.getElementById("import-prebook").addEventListener("click", () => prebookOverlay.classList.add("open"));
document.getElementById("prebook-close").addEventListener("click", () => prebookOverlay.classList.remove("open"));
prebookOverlay.addEventListener("click", (e) => {
  if (e.target === prebookOverlay) prebookOverlay.classList.remove("open");
});

document.getElementById("prebook-submit").addEventListener("click", async () => {
  const text   = document.getElementById("prebook-input").value.trim();
  const btn    = document.getElementById("prebook-submit");
  const status = document.getElementById("prebook-status");
  if (!text) return;
  btn.disabled     = true;
  btn.textContent  = "Importing...";
  status.className = "prebook-status";
  status.textContent = "";
  try {
    const res = await fetch("/api/prebook/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const raw = await res.text();
    let data;
    try { data = JSON.parse(raw); } catch {
      status.className   = "prebook-status error";
      status.textContent = "Server error — check console.";
      console.error(raw);
      return;
    }
    if (data.error) {
      status.className   = "prebook-status error";
      status.textContent = data.error;
    } else {
      status.className   = "prebook-status success";
      status.textContent = `Imported ${data.upserted} row(s).`;
      setTimeout(() => {
        prebookOverlay.classList.remove("open");
        document.getElementById("prebook-input").value = "";
        status.className   = "prebook-status";
        status.textContent = "";
      }, 1500);
    }
  } catch (e) {
    status.className   = "prebook-status error";
    status.textContent = "Request failed.";
  } finally {
    btn.disabled    = false;
    btn.textContent = "Import";
  }
});

document.getElementById("clear-prebook").addEventListener("click", async () => {
  const dayNames = { 1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday" };
  const day = sessionStorage.getItem("activeDay");
  if (!day) { showToast("Select a day first."); return; }
  const label = dayNames[day] || `Day ${day}`;
  if (!confirm(`Clear Prebook data for ${label}?`)) return;
  try {
    const r = await fetch(`/api/prebook?day=${day}`, { method: "DELETE" });
    if (!r.ok) throw new Error(r.status);
    loadOverview(parseInt(day));
    showToast(`Prebook cleared for ${label}.`);
  } catch {
    showToast("Failed to clear Prebook.");
  }
});
