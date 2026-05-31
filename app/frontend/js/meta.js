let metaItems = [];
let shipmentItems = [];
let currentUser = null;

const SHIPMENT_STATUS_LABELS = {
  needs_configuration: "LLM saknas",
  queued: "Köad",
  analyzing: "Analyserar",
  analyzed: "Klar",
  manual_review: "Kontrollera",
  analysis_failed: "Fel",
  pending_analysis: "Väntar",
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]
  );
}

function formatTimestamp(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("sv-SE", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  if (value >= 1024) return `${(value / 1024).toFixed(1)} kB`;
  return `${value} B`;
}

function mediaUrl(item) {
  return `/api/meta/uploads/${encodeURIComponent(item.id)}/content`;
}

function shipmentMediaFilename(item, fallback = "meta-fil") {
  const hash = String(item?.video_hash || item?.label_image_hash || "").slice(0, 10);
  return hash ? `${fallback}-${hash}` : fallback;
}

async function downloadMetaItem(item) {
  if (!item) return;
  try {
    await api.download(mediaUrl(item), item.filename || "meta-upload");
  } catch (error) {
    showToast(error.message || "Kunde inte ladda ner filen.", "error", 7000);
  }
}

async function downloadShipmentMedia(item, kind) {
  const url = kind === "label" ? item?.label_still_url : item?.video_url;
  if (!url) return;
  const fallback = kind === "label" ? "etikett.jpg" : "meta-video";
  try {
    await api.download(url, shipmentMediaFilename(item, fallback));
  } catch (error) {
    showToast(error.message || "Kunde inte ladda ner filen.", "error", 7000);
  }
}

async function analyzeShipmentVideo(item, button = null) {
  if (!item?.media_upload_id) return;
  if (button) button.disabled = true;
  try {
    const response = await api.post(`/api/meta/uploads/${encodeURIComponent(item.media_upload_id)}/analyze`, {}, {
      logLabel: "Meta-analys",
    });
    if (response?.status === "needs_configuration") {
      showToast("Meta-analys saknar LLM-konfiguration.", "warn", 7000);
    } else if (response?.status === "analysis_failed") {
      showToast(response.message || "Meta-analysen misslyckades.", "error", 7000);
    } else {
      showToast("Meta-analys uppdaterad.", "success", 2500);
    }
    await loadMetaItems(false);
  } catch (error) {
    showToast(error.message || "Kunde inte analysera videon.", "error", 7000);
  } finally {
    if (button) button.disabled = false;
  }
}

async function deleteMetaItem(item, button = null) {
  if (!item) return;
  const filename = item.filename || item.original_filename || "filen";
  if (!confirm(`Radera ${filename}? Det går inte att ångra.`)) return;
  if (button) button.disabled = true;
  try {
    await api.del(`/api/meta/uploads/${encodeURIComponent(item.id)}`, {
      logLabel: "Meta-fil borttagen",
    });
    metaItems = metaItems.filter((entry) => Number(entry.id) !== Number(item.id));
    renderMetaItems();
    showToast("Meta-fil raderad.", "success", 2500);
  } catch (error) {
    if (button) button.disabled = false;
    showToast(error.message || "Kunde inte radera filen.", "error", 7000);
  }
}

function renderSummary() {
  const total = metaItems.length;
  const videos = metaItems.filter((item) => item.media_type === "video").length;
  const images = metaItems.filter((item) => item.media_type === "image").length;
  document.getElementById("metaSummary").textContent = `${total} filer - ${videos} videor - ${images} bilder`;
}

function statusLabel(status) {
  return SHIPMENT_STATUS_LABELS[status] || status || "-";
}

function renderShipmentRows() {
  const tbody = document.getElementById("metaShipmentRows");
  const summary = document.getElementById("metaShipmentSummary");
  if (!tbody || !summary) return;
  summary.textContent = `${shipmentItems.length} sändningsrader`;
  if (!shipmentItems.length) {
    tbody.innerHTML = '<tr><td colspan="10" class="meta-admin-empty-cell">Inga sändningsanalyser ännu.</td></tr>';
    return;
  }

  tbody.innerHTML = shipmentItems.map((item) => {
    const deviations = Array.isArray(item.deviations) && item.deviations.length
      ? item.deviations.join(", ")
      : "-";
    const status = item.analysis_status || "pending_analysis";
    const hashTitle = `Video: ${item.video_hash || "-"}\nRad: ${item.record_hash || "-"}`;
    return `
      <tr>
        <td>${escapeHtml(item.order_number || "-")}</td>
        <td>${escapeHtml(item.username || "-")}</td>
        <td>${escapeHtml(item.customer_name || "-")}</td>
        <td>${escapeHtml(item.pallet_id || "-")}</td>
        <td title="${escapeHtml(deviations)}">${escapeHtml(deviations)}</td>
        <td>
          <span class="meta-status-pill ${escapeHtml(status)}">${escapeHtml(statusLabel(status))}</span>
          ${item.uncertainty_notes ? `<div class="meta-admin-note" title="${escapeHtml(item.uncertainty_notes)}">Osäkert</div>` : ""}
        </td>
        <td><button type="button" data-download-shipment-video="${item.id}" ${item.video_url ? "" : "disabled"}>Video</button></td>
        <td><button type="button" data-download-shipment-label="${item.id}" ${item.label_still_url ? "" : "disabled"}>Stillbild</button></td>
        <td class="meta-admin-hash" title="${escapeHtml(hashTitle)}">${escapeHtml((item.record_hash || "").slice(0, 10) || "-")}</td>
        <td><button type="button" data-analyze-upload="${item.id}" ${status === "analyzing" ? "disabled" : ""}>Analysera</button></td>
      </tr>
    `;
  }).join("");

  tbody.querySelectorAll("[data-download-shipment-video]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = shipmentItems.find((entry) => Number(entry.id) === Number(button.dataset.downloadShipmentVideo));
      void downloadShipmentMedia(item, "video");
    });
  });
  tbody.querySelectorAll("[data-download-shipment-label]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = shipmentItems.find((entry) => Number(entry.id) === Number(button.dataset.downloadShipmentLabel));
      void downloadShipmentMedia(item, "label");
    });
  });
  tbody.querySelectorAll("[data-analyze-upload]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = shipmentItems.find((entry) => Number(entry.id) === Number(button.dataset.analyzeUpload));
      void analyzeShipmentVideo(item, button);
    });
  });
}

function renderMetaItems() {
  const grid = document.getElementById("metaGrid");
  renderSummary();
  renderShipmentRows();
  if (!metaItems.length) {
    grid.innerHTML = '<div class="meta-admin-empty">Inga uppladdningar hittades.</div>';
    return;
  }

  grid.innerHTML = metaItems.map((item) => `
    <article class="meta-admin-card">
      <div class="meta-admin-thumb ${escapeHtml(item.media_type)}">
        <span>${item.media_type === "video" ? "Video" : "Bild"}</span>
      </div>
      <div class="meta-admin-card-body">
        <h3 title="${escapeHtml(item.filename)}">${escapeHtml(item.filename)}</h3>
        <dl class="meta-admin-details">
          <div><dt>Uppladdad</dt><dd>${escapeHtml(formatTimestamp(item.created_at))}</dd></div>
          <div><dt>Storlek</dt><dd>${escapeHtml(item.size_label || formatBytes(item.size_bytes))}</dd></div>
          <div><dt>Original</dt><dd title="${escapeHtml(item.original_filename)}">${escapeHtml(item.original_filename || "-")}</dd></div>
          <div><dt>Status</dt><dd>${escapeHtml(item.status || "-")}</dd></div>
        </dl>
        <div class="meta-admin-actions">
          <button type="button" class="primary" data-open-media="${item.id}">Visa</button>
          <button type="button" data-download-media="${item.id}">Ladda ner</button>
          <button type="button" class="danger" data-delete-media="${item.id}">Radera</button>
        </div>
      </div>
    </article>
  `).join("");

  grid.querySelectorAll("[data-open-media]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = metaItems.find((entry) => Number(entry.id) === Number(button.dataset.openMedia));
      if (item) openMediaModal(item);
    });
  });
  grid.querySelectorAll("[data-download-media]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = metaItems.find((entry) => Number(entry.id) === Number(button.dataset.downloadMedia));
      void downloadMetaItem(item);
    });
  });
  grid.querySelectorAll("[data-delete-media]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = metaItems.find((entry) => Number(entry.id) === Number(button.dataset.deleteMedia));
      void deleteMetaItem(item, button);
    });
  });
}

function openMediaModal(item) {
  const isVideo = item.media_type === "video";
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal wide meta-preview-modal">
      <h2>${escapeHtml(item.filename)}</h2>
      <div class="meta-preview-frame">
        ${isVideo
          ? `<video src="${mediaUrl(item)}" controls autoplay playsinline></video>`
          : `<img src="${mediaUrl(item)}" alt="${escapeHtml(item.filename)}" />`}
      </div>
      <div class="actions">
        <button type="button" data-download-media="${item.id}">Ladda ner</button>
        <button type="button" class="primary" id="metaPreviewClose">Stäng</button>
      </div>
    </div>
  `;
  document.body.appendChild(backdrop);
  backdrop.querySelector("[data-download-media]")?.addEventListener("click", () => {
    void downloadMetaItem(item);
  });
  backdrop.querySelector("#metaPreviewClose").addEventListener("click", () => backdrop.remove());
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) backdrop.remove();
  });
}

async function loadMetaItems(showDone = false) {
  const mediaType = document.getElementById("metaMediaType").value;
  const params = new URLSearchParams({ limit: "200" });
  if (mediaType) params.set("media_type", mediaType);
  const [response, shipmentResponse] = await Promise.all([
    api.get(`/api/meta/uploads?${params.toString()}`, {
      skipCache: true,
      logGetUserEvent: false,
    }),
    api.get("/api/meta/shipment-observations?limit=200", {
      skipCache: true,
      logGetUserEvent: false,
    }),
  ]);
  metaItems = response.items || [];
  shipmentItems = shipmentResponse.items || [];
  renderMetaItems();
  if (showDone) showToast("Meta uppdaterad.", "success", 2000);
}

document.addEventListener("DOMContentLoaded", async () => {
  currentUser = await initPage("meta", { requireSuperUser: true });
  if (!currentUser) return;

  document.getElementById("metaRefresh").addEventListener("click", () => loadMetaItems(true));
  document.getElementById("metaMediaType").addEventListener("change", () => loadMetaItems());
  await loadMetaItems();
});
