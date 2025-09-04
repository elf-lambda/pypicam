"use strict";

let currentPath = "";

async function loadFiles(path = "") {
    try {
        const response = await fetch(
            `/api/files?path=${encodeURIComponent(path)}`
        );
        const data = await response.json();

        if (response.ok) {
            currentPath = path;
            updateBreadcrumb(path);
            renderFileList(data.items);
        } else {
            document.getElementById(
                "fileList"
            ).innerHTML = `<p class="error">Error: ${data.detail}</p>`;
        }
    } catch (error) {
        console.error("Error loading files:", error);
        document.getElementById(
            "fileList"
        ).innerHTML = `<p class="error">Error loading files: ${error.message}</p>`;
    }
}

function updateBreadcrumb(path) {
    const breadcrumb = document.getElementById("breadcrumb");
    if (!path) {
        breadcrumb.innerHTML =
            '<span class="breadcrumb-item">Recordings</span>';
        return;
    }

    const parts = path.split("/");
    let html = '<a href="#" onclick="loadFiles(\'\')">Recordings</a>';
    let currentPath = "";

    parts.forEach((part, index) => {
        if (part) {
            currentPath += (currentPath ? "/" : "") + part;
            if (index === parts.length - 1) {
                html += ` / <span class="breadcrumb-item">${part}</span>`;
            } else {
                html += ` / <a href="#" onclick="loadFiles('${currentPath}')">${part}</a>`;
            }
        }
    });

    breadcrumb.innerHTML = html;
}

function renderFileList(items) {
    const fileList = document.getElementById("fileList");

    if (items.length === 0) {
        fileList.innerHTML = '<p class="empty">No files or folders found.</p>';
        return;
    }

    let html = '<div class="files-grid">';

    items.forEach((item) => {
        if (item.type === "directory") {
            html += `
                        <div class="file-item folder" onclick="loadFiles('${item.path}')">
                            <div class="file-icon">📁</div>
                            <div class="file-name">${item.name}</div>
                        </div>
                    `;
        } else {
            html += `
                        <div class="file-item file">
                            <div class="file-icon">🎬</div>
                            <div class="file-details">
                                <div class="file-name">${item.name}</div>
                                <div class="file-size">${item.size}</div>
                            </div>
                            <a href="/download/${encodeURIComponent(
                                item.path
                            )}" 
                               class="download-btn" 
                               download="${item.name}">
                                Download
                            </a>
                        </div>
                    `;
        }
    });

    html += "</div>";
    fileList.innerHTML = html;
}

document.addEventListener("DOMContentLoaded", function () {
    loadFiles();
});
