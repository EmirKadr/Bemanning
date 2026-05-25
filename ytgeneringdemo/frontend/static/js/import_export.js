
const _SUCCESS_RE = /\b(loaded|upserted|inserted)\s+[1-9]\d*\s+rows/;

function showImportToast(outputText, isError) {
  const existing = document.getElementById("import-toast");
  if (existing) existing.remove();

  const el = document.createElement("div");
  el.id = "import-toast";
  el.className = "toast toast--import";

  const lines = outputText
    .split("\n")
    .map(l => l.trim())
    .filter(l => l
      && !l.startsWith("Scanning:")
      && !l.startsWith("Deleted:")
      && !l.startsWith("Note:")
    );

  const hasSuccess = lines.some(l => _SUCCESS_RE.test(l));
  const hasError   = isError || lines.some(l => l.startsWith("ERROR") || l.includes("ERROR:"));
  const allMissing = !hasSuccess && !hasError
    && lines.length > 0
    && lines.every(l => l.includes("no file found"));

  const title = document.createElement("div");
  title.className = "toast-title";
  title.textContent = (hasError && !hasSuccess) ? "Import failed"
    : hasSuccess                                 ? "Import complete"
    :                                              "Nothing imported";
  el.appendChild(title);

  if (isError) {
    const row = document.createElement("div");
    row.className = "toast-row toast-row--error";
    row.textContent = outputText;
    el.appendChild(row);
  } else if (allMissing) {
    const row = document.createElement("div");
    row.className = "toast-row toast-row--missing";
    row.textContent = "No matching files were found";
    el.appendChild(row);
  } else {
    for (const line of lines) {
      const isErr     = line.startsWith("ERROR") || line.includes("ERROR:");
      const isMissing = !isErr && line.includes("no file found");
      const isWarn    = !isErr && line.startsWith("WARNING:");
      const isSuccess = !isErr && _SUCCESS_RE.test(line);

      const row = document.createElement("div");
      row.className = "toast-row"
        + (isErr     ? " toast-row--error"   : "")
        + (isMissing ? " toast-row--missing"  : "")
        + (isWarn    ? " toast-row--warning"  : "")
        + (isSuccess ? " toast-row--success"  : "");
      row.textContent = line;
      el.appendChild(row);
    }
  }

  document.body.appendChild(el);
  setTimeout(() => {
    el.classList.add("toast--fade");
    setTimeout(() => el.remove(), 350);
  }, 6000);
}

const importFilesInput = document.getElementById("import-files-input");
const _DISPATCH_AREA_RE = /^dispatch_area-\d{14}\.csv$/;

document.getElementById("import-files").addEventListener("click", () => {
  importFilesInput.click();
});

importFilesInput.addEventListener("change", async function () {
  if (!this.files.length) return;

  const dispatchFiles = [];
  const regularFiles = [];
  for (const file of this.files) {
    if (_DISPATCH_AREA_RE.test(file.name)) {
      dispatchFiles.push(file);
    } else {
      regularFiles.push(file);
    }
  }

  const btn = document.getElementById("import-files");
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Importing…";

  try {
    if (regularFiles.length) {
      const formData = new FormData();
      for (const file of regularFiles) formData.append("files", file);
      const res = await fetch("/api/db/import-wms-upload", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Import failed");
      showImportToast(data.output, false);
    }

    if (dispatchFiles.length) {
      const dayNames = { 1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday" };
      const day = sessionStorage.getItem("activeDay");
      if (!day) {
        showImportToast("dispatch_area: Select a day first to import assignments.", true);
      } else {
        const label = dayNames[day] || `Day ${day}`;
        if (confirm(`Import locations from Ask? This will override current assignments for ${label}.`)) {
          const file = dispatchFiles[dispatchFiles.length - 1];
          const formData = new FormData();
          formData.append("file", file);
          const res = await fetch(`/api/assignments/import-ask?day=${day}`, { method: "POST", body: formData });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Assignment import failed");
          let msg = `dispatch_area: imported ${data.imported} assignments for ${label}`;
          if (data.skipped > 0) msg += ` (${data.skipped} rows skipped)`;
          showImportToast(msg, false);
          if (window.__reloadDay) window.__reloadDay(parseInt(day));
        }
      }
    }

    btn.textContent = "Done!";
  } catch (err) {
    btn.textContent = "Error!";
    showImportToast(err.message, true);
    console.error("[import-wms-upload]", err);
  } finally {
    setTimeout(() => { btn.textContent = original; btn.disabled = false; }, 2000);
    this.value = "";
  }
});

document.getElementById("auto-import").addEventListener("click", async function () {
  const btn = this;
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Importing…";
  try {
    const res = await fetch("/api/db/import-wms", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Import failed");
    btn.textContent = "Done!";
    showImportToast(data.output, false);
  } catch (err) {
    btn.textContent = "Error!";
    showImportToast(err.message, true);
    console.error("[import-wms]", err);
  } finally {
    setTimeout(() => { btn.textContent = original; btn.disabled = false; }, 2000);
  }
});


const exportOverlay = document.getElementById("export-overlay");

function openExportModal() {
  exportOverlay.classList.add("open");
}

function closeExportModal() {
  exportOverlay.classList.remove("open");
}

document.getElementById("export-files").addEventListener("click", openExportModal);
document.getElementById("export-modal-close").addEventListener("click", closeExportModal);
exportOverlay.addEventListener("click", (e) => {
  if (e.target === exportOverlay) closeExportModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && exportOverlay.classList.contains("open")) closeExportModal();
});
