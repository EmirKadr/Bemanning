const form = document.getElementById("metaUploadForm");
const input = document.getElementById("metaFiles");
const dropzone = document.getElementById("metaDropzone");
const fileList = document.getElementById("metaFileList");
const progressPanel = document.getElementById("metaProgress");
const progressLabel = document.getElementById("metaProgressLabel");
const progressPercent = document.getElementById("metaProgressPercent");
const progressBar = document.getElementById("metaProgressBar");
const progressRemaining = document.getElementById("metaProgressRemaining");
const statusBox = document.getElementById("metaStatus");

let selectedFiles = [];
let uploading = false;
const selectedVideoDurations = new WeakMap();
let durationProbeGeneration = 0;

function formatBytes(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} kB`;
  return `${bytes} B`;
}

function formatDuration(seconds) {
  if (seconds == null || seconds === "") return "";
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0) return "";
  const total = Math.round(value);
  const sec = total % 60;
  const minutesTotal = Math.floor(total / 60);
  const min = minutesTotal % 60;
  const hours = Math.floor(minutesTotal / 60);
  if (hours > 0) return `${hours}:${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${min}:${String(sec).padStart(2, "0")}`;
}

function isVideoFile(file) {
  const type = String(file?.type || "").toLowerCase();
  const name = String(file?.name || "").toLowerCase();
  return type.startsWith("video/") || /\.(3g2|3gp|avi|m4v|mov|mp4|mpeg|mpg|webm)$/.test(name);
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
  selectedFiles.forEach((file, index) => {
    const item = document.createElement("div");
    item.className = "meta-file-item";

    const name = document.createElement("div");
    name.className = "meta-file-name";
    name.textContent = file.name || "Namnlös fil";
    item.appendChild(name);

    const size = document.createElement("div");
    size.className = "meta-file-size";
    const duration = selectedVideoDurations.has(file) ? formatDuration(selectedVideoDurations.get(file)) : "";
    size.textContent = duration ? `${formatBytes(file.size || 0)} - ${duration}` : formatBytes(file.size || 0);
    size.dataset.fileDurationLabel = String(index);
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

function updateFileDurationLabel(index, file) {
  const node = fileList.querySelector(`[data-file-duration-label="${index}"]`);
  if (!node) return;
  const duration = selectedVideoDurations.has(file) ? formatDuration(selectedVideoDurations.get(file)) : "";
  node.textContent = duration ? `${formatBytes(file.size || 0)} - ${duration}` : formatBytes(file.size || 0);
}

function loadSelectedVideoDurations() {
  const generation = ++durationProbeGeneration;
  selectedFiles.forEach((file, index) => {
    if (!isVideoFile(file) || selectedVideoDurations.has(file)) return;
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.muted = true;
    video.playsInline = true;
    const cleanup = () => {
      URL.revokeObjectURL(url);
      video.removeAttribute("src");
      video.load();
    };
    video.addEventListener("loadedmetadata", () => {
      if (generation === durationProbeGeneration && selectedFiles[index] === file) {
        selectedVideoDurations.set(file, video.duration);
        updateFileDurationLabel(index, file);
      }
      cleanup();
    }, { once: true });
    video.addEventListener("error", cleanup, { once: true });
    video.src = url;
  });
}

function setUploadControlsLocked(locked) {
  uploading = locked;
  input.disabled = locked;
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
  loadSelectedVideoDurations();
  setStatus(selectedFiles.length ? `${selectedFiles.length} filer valda. Startar uppladdning...` : "");
  if (selectedFiles.length) void startUpload();
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

async function startUpload() {
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
    const savedCount = Number(payload.saved_count || 0);
    const skippedCount = Number(payload.skipped_count || 0);
    if (skippedCount && savedCount) {
      setStatus(`${savedCount} filer uppladdade. ${skippedCount} dubbletter hoppades över.`, "success");
    } else if (skippedCount) {
      setStatus(`Inga nya filer sparades. ${skippedCount} dubbletter fanns redan.`, "success");
    } else {
      setStatus(`${savedCount} filer uppladdade.`, "success");
    }
  } catch (error) {
    setUploadControlsLocked(false);
    input.value = "";
    renderFiles();
    setStatus(error.message || "Uppladdningen misslyckades.", "error");
    return;
  }
  setUploadControlsLocked(false);
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  void startUpload();
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
