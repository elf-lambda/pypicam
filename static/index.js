"use static";

const diskStatsElement = document.getElementById("diskStats");
const serverUptime = document.getElementById("serverUptime");
const recordingUptime = document.getElementById("recordingUptime");
const statusElement = document.getElementById("recordingStatus");
const recordBtn = document.getElementById("recordBtn");
const stopBtn = document.getElementById("stopBtn");
const recordStatus = document.getElementById("recordingStatus");
const recordUptime = document.getElementById("recordingUptime");
const daysInput = document.getElementById("daysInput");
const deleteBtn = document.getElementById("deleteBtn");
const cleanupStatusElement = document.getElementById("cleanupStatus");

let serverStartTimeMillis = -1;
let currentRecordingStartTimeMillis = -1;

deleteBtn.addEventListener("click", () => sendDeleteCommand());

recordBtn.addEventListener("click", async () => {
    const response = await fetch("/record");
    if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
    } else {
        const data = await response.json();
        recordStatus.innerText = "Recording Status: " + data.message;
    }
});

stopBtn.addEventListener("click", async () => {
    const response = await fetch("/stoprecord");
    if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
    } else {
        console.log("recording stopped!");
        const data = await response.json();
        recordStatus.innerText = "Recording Status: " + data.message;
    }
});

async function sendDeleteCommand() {
    const days = daysInput.value;

    if (days === "" || isNaN(days) || parseInt(days) < 0) {
        cleanupStatusElement.textContent =
            "Deletion Status: Please enter a valid number of days (0 or more).";
        return;
    }

    cleanupStatusElement.textContent = `Deletion Status: Deleting files older than ${days} days...`;
    deleteBtn.disabled = true;

    let response = null;

    try {
        response = await fetch("/delete", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: "days=" + days,
        });

        const result = await response.text();

        if (response.ok) {
            cleanupStatusElement.textContent = `Status: ${result}`;
        } else {
            cleanupStatusElement.textContent = `Status: Error (${response.status}) - ${result}`;
        }
    } catch (error) {
        console.error("Fetch error (delete):", error);
        cleanupStatusElement.textContent = `Status: Network Error - ${error.message}`;
    } finally {
        deleteBtn.disabled = false;
    }
}

async function fetchStatistics() {
    try {
        const response = await fetch("/statistics");

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();

        const statsHTML = `
                <div class="stat-item">
                    <span class="stat-label">Total Space:</span>
                    <span class="stat-value">${data.totalSpaceFormatted}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Free Space:</span>
                    <span class="stat-value">${data.freeSpaceFormatted}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Usable Space:</span>
                    <span class="stat-value">${data.usableSpaceFormatted}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Space Used:</span>
                    <span class="stat-value">${data.usedSpacePercentage}</span>
                </div>
            `;

        diskStatsElement.innerHTML = statsHTML;
        serverStartTimeMillis = Number(data.serverStartTimeMillis);
        currentRecordingStartTimeMillis = Number(data.recordingStartTimeMillis);
    } catch (error) {
        console.error("Error fetching disk statistics:", error);
        diskStatsElement.innerHTML = `<p>Error loading disk statistics: ${error.message}</p>`;
    }
}

function updateUptimesDisplay() {
    const currentTimeMillis = Date.now();

    if (serverStartTimeMillis !== -1) {
        const serverUptimeMillis = currentTimeMillis - serverStartTimeMillis;
        serverUptime.textContent = formatDurationJS(serverUptimeMillis);
    } else {
        serverUptime.textContent = "Loading...";
    }

    if (currentRecordingStartTimeMillis !== -1) {
        const recordingUptimeMillis =
            currentTimeMillis - currentRecordingStartTimeMillis;
        recordingUptime.textContent = formatDurationJS(recordingUptimeMillis);
        statusElement.textContent = `Status: Recording`;
    } else {
        recordingUptime.textContent = "Idle";
    }
}

function formatDurationJS(millis) {
    if (millis < 0) {
        console.log("millis: ", millis);
        return "N/A";
    }

    const totalSeconds = Math.floor(millis / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    const parts = [];
    if (hours > 0) parts.push(hours + " h");
    if (minutes > 0 || hours > 0) parts.push(minutes + " m");
    if (seconds > 0 || totalSeconds === 0) parts.push(seconds + " s");

    return parts.join(" ");
}

fetchStatistics();
updateUptimesDisplay();
setInterval(fetchStatistics, 30000);
setInterval(updateUptimesDisplay, 1000);
