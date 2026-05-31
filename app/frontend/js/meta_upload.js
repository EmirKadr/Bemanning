const form = document.getElementById("metaUploadForm");
const input = document.getElementById("metaFiles");
const dropzone = document.getElementById("metaDropzone");
const fileList = document.getElementById("metaFileList");
const progressPanel = document.getElementById("metaProgress");
const progressLabel = document.getElementById("metaProgressLabel");
const progressPercent = document.getElementById("metaProgressPercent");
const progressBar = document.getElementById("metaProgressBar");
const progressRemaining = document.getElementById("metaProgressRemaining");
const uploadButton = document.getElementById("metaUploadButton");
const statusBox = document.getElementById("metaStatus");

let selectedFiles = [];
let uploading = false;

function formatBytes(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} kB`;
  return `${bytes} B`;
}

function setStatus(message, type = "") {
  statusBox.textContent = message || "";
  statusBox.className = `meta-status${type ? ` ${type}` : ""}`;
}

function totalSelectedBytes() {
  return selectedFiles.reduce((sum, file) => sum + (Number(file.size) || 0), 0);
}

function fileOffsets() {
  let offset = 0;
  return selectedFiles.map((file) => {
    const start = offset;
    offset += Number(file.size) || 0;
    return { start, end: offset };
  });
}

function renderFiles() {
  fileList.textContent = "";
  uploadButton.disabled = uploading || selectedFiles.length === 0;
  selectedFiles.forEach((file, index) => {
    const item = document.createElement("div");
    item.className = "meta-file-item";

    const name = document.createElement("div");
    name.className = "meta-file-name";
    name.textContent = file.name || "Namnlös fil";
    item.appendChild(name);

    const size = document.createElement("div");
    size.className = "meta-file-size";
    size.textContent = formatBytes(file.size || 0);
    item.appendChild(size);

    const state = document.createElement("div");
    state.className = "meta-file-state";
    state.dataset.fileState = String(index);
    state.textContent = uploading ? "Väntar" : "Vald";
    item.appendChild(state);

    const track = document.createElement("div");
    track.className = "meta-file-progress";
    track.innerHTML = `<div class="meta-file-progress-bar" data-file-progress="${index}"></div>`;
    item.appendChild(track);

    fileList.appendChild(item);
  });
}

function setUploadControlsLocked(locked) {
  uploading = locked;
  input.disabled = locked;
  uploadButton.disabled = locked || selectedFiles.length === 0;
  dropzone.classList.toggle("uploading", locked);
  dropzone.setAttribute("aria-busy", locked ? "true" : "false");
}

function resetProgress() {
  progressPanel.hidden = true;
  progressBar.style.width = "0%";
  progressPercent.textContent = "0%";
  progressLabel.textContent = "Laddar upp";
  progressRemaining.textContent = "";
}

function updateProgress(loadedBytes, totalBytes = totalSelectedBytes()) {
  const total = Math.max(Number(totalBytes) || totalSelectedBytes(), 1);
  const loaded = Math.min(Math.max(Number(loadedBytes) || 0, 0), total);
  const percent = Math.min(100, Math.round((loaded / total) * 100));
  const remaining = Math.max(0, total - loaded);
  const offsets = fileOffsets();
  let activeIndex = offsets.findIndex((item) => loaded >= item.start && loaded < item.end);
  if (activeIndex === -1 && loaded >= total && offsets.length) activeIndex = offsets.length - 1;

  progressPanel.hidden = false;
  progressBar.style.width = `${percent}%`;
  progressPercent.textContent = `${percent}%`;
  progressRemaining.textContent = remaining > 0
    ? `${formatBytes(remaining)} kvar av ${formatBytes(total)}`
    : `${formatBytes(total)} uppladdat`;
  progressLabel.textContent = activeIndex >= 0
    ? `Laddar upp ${selectedFiles[activeIndex]?.name || "fil"}`
    : "Laddar upp";

  offsets.forEach((item, index) => {
    const file = selectedFiles[index];
    const fileSize = Math.max(Number(file?.size) || 0, 1);
    const fileLoaded = Math.min(Math.max(loaded - item.start, 0), fileSize);
    const filePercent = Math.min(100, Math.round((fileLoaded / fileSize) * 100));
    const bar = fileList.querySelector(`[data-file-progress="${index}"]`);
    const state = fileList.querySelector(`[data-file-state="${index}"]`);
    if (bar) bar.style.width = `${filePercent}%`;
    if (state) {
      state.textContent = filePercent >= 100
        ? "Klar"
        : index === activeIndex ? `${filePercent}%` : "Väntar";
    }
  });
}

function setFiles(files) {
  if (uploading) return;
  selectedFiles = Array.from(files || []).filter(Boolean);
  resetProgress();
  renderFiles();
  setStatus(selectedFiles.length ? `${selectedFiles.length} filer valda.` : "");
}

input.addEventListener("change", () => setFiles(input.files));

["dragenter", "dragover"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragging");
  });
});

dropzone.addEventListener("drop", (event) => {
  setFiles(event.dataTransfer?.files);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedFiles.length || uploading) return;

  const body = new FormData();
  selectedFiles.forEach((file) => body.append("files", file, file.name));

  setUploadControlsLocked(true);
  renderFiles();
  updateProgress(0);
  setStatus("Laddar upp...");
  try {
    const payload = await uploadWithProgress(body);
    updateProgress(totalSelectedBytes(), totalSelectedBytes());
    input.value = "";
    selectedFiles = [];
    renderFiles();
    setStatus(`${payload.saved_count || 0} filer uppladdade.`, "success");
  } catch (error) {
    setUploadControlsLocked(false);
    renderFiles();
    setStatus(error.message || "Uppladdningen misslyckades.", "error");
    return;
  }
  setUploadControlsLocked(false);
});

function uploadWithProgress(body) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/meta/uploads");
    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        updateProgress(event.loaded, event.total);
      } else {
        updateProgress(event.loaded, totalSelectedBytes());
      }
    });
    xhr.addEventListener("load", () => {
      let payload = {};
      try {
        payload = xhr.responseText ? JSON.parse(xhr.responseText) : {};
      } catch (_error) {
        payload = {};
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new Error(payload.detail || `HTTP ${xhr.status}`));
        return;
      }
      resolve(payload);
    });
    xhr.addEventListener("error", () => reject(new Error("Kunde inte ansluta till servern.")));
    xhr.addEventListener("abort", () => reject(new Error("Uppladdningen avbröts.")));
    xhr.send(body);
  });
}
