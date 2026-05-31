const form = document.getElementById("metaUploadForm");
const input = document.getElementById("metaFiles");
const dropzone = document.getElementById("metaDropzone");
const fileList = document.getElementById("metaFileList");
const uploadButton = document.getElementById("metaUploadButton");
const statusBox = document.getElementById("metaStatus");

let selectedFiles = [];

function formatBytes(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} kB`;
  return `${bytes} B`;
}

function setStatus(message, type = "") {
  statusBox.textContent = message || "";
  statusBox.className = `meta-status${type ? ` ${type}` : ""}`;
}

function renderFiles() {
  fileList.textContent = "";
  uploadButton.disabled = selectedFiles.length === 0;
  selectedFiles.forEach((file) => {
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

    fileList.appendChild(item);
  });
}

function setFiles(files) {
  selectedFiles = Array.from(files || []).filter(Boolean);
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
  if (!selectedFiles.length) return;

  const body = new FormData();
  selectedFiles.forEach((file) => body.append("files", file, file.name));

  uploadButton.disabled = true;
  setStatus("Laddar upp...");
  try {
    const response = await fetch("/api/meta/uploads", {
      method: "POST",
      body,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    input.value = "";
    selectedFiles = [];
    renderFiles();
    setStatus(`${payload.saved_count || 0} filer uppladdade.`, "success");
  } catch (error) {
    uploadButton.disabled = selectedFiles.length === 0;
    setStatus(error.message || "Uppladdningen misslyckades.", "error");
  }
});
