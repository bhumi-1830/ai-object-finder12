
"use strict";

// ==========================================
// AI OBJECT FINDER - COMPLETE SCRIPT.JS
// ==========================================

// CONFIGURATION
const BACKEND_URL = "http://127.0.0.1:5000";
const ESP32_URL = "http://10.128.3.99";

// DOM ELEMENTS
const $ = (id) => document.getElementById(id);

const targetObject = $("targetObject");
const targetDisplay = $("targetDisplay");
const cameraInput = $("cameraInput");
const uploadInput = $("uploadInput");
const referencePreview = $("referencePreview");

const robotStatus = $("robotStatus");
const detectionStatus = $("detectionStatus");
const confidence = $("confidence");
const confidenceBar = $("confidenceBar");
const detectedObject = $("detectedObject");
const detectedConfidence = $("detectedConfidence");
const aiStatus = $("aiStatus");
const historyCount = $("historyCount");
const cloudStatus = $("cloudStatus");
const robotLink = $("robotLink");
const movementState = $("movementState");

// STATE
let referenceImageFile = null;
let referenceUploaded = false;
let searchRunning = false;
let historyEvents = 0;
let previewURL = null;

// Supported by the current ESP32 Code 2
const ALLOWED_COMMANDS = new Set([
    "forward", "backward", "left", "right",
    "stop", "found", "reset", "scan"
]);

// COMMON HELPERS
function setText(element, value) {
    if (element) element.textContent = value;
}

function updateRobotStatus(value) {
    setText(robotStatus, value);
}

function updateDetectionStatus(value) {
    setText(detectionStatus, value);
}

function updateConfidence(value) {
    const number = Number(value);
    const percent = Number.isFinite(number)
        ? Math.max(0, Math.min(100, number))
        : 0;

    setText(confidence, `${percent}%`);
    setText(detectedConfidence, `${percent}%`);

    if (confidenceBar) {
        confidenceBar.style.width = `${percent}%`;
    }
}

// TARGET OBJECT
function updateTargetDisplay() {
    if (!targetObject || !targetDisplay) return;

    targetDisplay.textContent =
        targetObject.options[targetObject.selectedIndex]?.text ||
        targetObject.value ||
        "Not Selected";
}

if (targetObject) {
    targetObject.addEventListener("change", updateTargetDisplay);
    updateTargetDisplay();
}

// IMAGE PICKER
if (cameraInput) {
    cameraInput.addEventListener("change", handleReferenceImage);
}

if (uploadInput) {
    uploadInput.addEventListener("change", handleReferenceImage);
}

function handleReferenceImage(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
        alert("Please select a valid image file.");
        event.target.value = "";
        return;
    }

    referenceImageFile = file;
    referenceUploaded = false;

    showReferencePreview(file);
    setText(aiStatus, "Reference image selected");
    updateDetectionStatus("IMAGE READY");

    console.log("Reference image selected:", file.name);
}

function showReferencePreview(file) {
    if (!referencePreview) return;

    if (previewURL) URL.revokeObjectURL(previewURL);
    previewURL = URL.createObjectURL(file);

    referencePreview.replaceChildren();

    const image = document.createElement("img");
    image.src = previewURL;
    image.alt = "Reference object";
    image.style.width = "100%";
    image.style.maxHeight = "180px";
    image.style.objectFit = "contain";
    image.style.borderRadius = "12px";

    const label = document.createElement("div");
    label.textContent = file.name;
    label.style.marginTop = "8px";
    label.style.fontSize = "12px";

    referencePreview.append(image, label);
}

// UPLOAD REFERENCE IMAGE TO FLASK
async function uploadReferenceImage() {
    if (!referenceImageFile) {
        alert("Please take a photo or upload the lost object's image first.");
        return false;
    }

    setText(aiStatus, "Uploading reference image...");

    try {
        const formData = new FormData();
        formData.append("image", referenceImageFile);

        const response = await fetch(
            `${BACKEND_URL}/upload-reference`,
            {
                method: "POST",
                body: formData,
                signal: AbortSignal.timeout(15000)
            }
        );

        const result = await response.json();

        if (!response.ok || result.success !== true) {
            throw new Error(
                result.message || `Upload failed: HTTP ${response.status}`
            );
        }

        referenceUploaded = true;
        setText(aiStatus, "Reference image uploaded");
        console.log("Upload result:", result);

        return true;
    } catch (error) {
        console.error("Reference upload failed:", error);
        referenceUploaded = false;
        setText(aiStatus, "Image upload failed");

        alert(
            "Image upload failed.\n" +
            error.message +
            "\nCheck Flask and the /upload-reference endpoint."
        );

        return false;
    }
}

// SEND COMMAND TO ESP32
async function sendRobotCommand(command) {
    command = String(command || "").toLowerCase().trim();

    if (!ALLOWED_COMMANDS.has(command)) {
        console.error("Unsupported ESP32 command:", command);
        setText(movementState, "UNSUPPORTED COMMAND");
        return null;
    }

    const url = `${ESP32_URL}/${command}`;
    console.log("Sending ESP32 command:", url);

    try {
        const response = await fetch(url, {
            method: "GET",
            mode: "cors",
            cache: "no-store",
            signal: AbortSignal.timeout(4000)
        });

        const result = await response.text();
        console.log("ESP32 response:", result);

        if (!response.ok) {
            throw new Error(`ESP32 returned HTTP ${response.status}`);
        }

        if (robotLink) robotLink.textContent = "CONNECTED";
        return result;
    } catch (error) {
        console.error("ESP32 command failed:", error);

        if (robotLink) robotLink.textContent = "OFFLINE";
        setText(movementState, "CONNECTION ERROR");

        return null;
    }
}

// MANUAL ROBOT CONTROLS
async function robotCommand(command) {
    const result = await sendRobotCommand(command);

    if (result === null) {
        updateRobotStatus("CONNECTION ERROR");
        return false;
    }

    const label = command.toUpperCase();
    updateRobotStatus(label);
    setText(movementState, label);

    if (robotLink) robotLink.textContent = "CONNECTED";
    return true;
}

// FIX: expose function to HTML onclick handlers
function moveRobot(command) {
    return robotCommand(command);
}

window.moveRobot = moveRobot;
window.robotCommand = robotCommand;
window.sendRobotCommand = sendRobotCommand;

// SEARCH BUTTON
async function startSearch() {
    if (searchRunning) return;

    if (!referenceImageFile) {
        alert("First take a photo or upload the lost object's image.");
        return;
    }

    searchRunning = true;

    try {
        if (!referenceUploaded) {
            const uploaded = await uploadReferenceImage();
            if (!uploaded) return;
        }

        updateRobotStatus("STARTING SCAN");
        updateDetectionStatus("REQUESTING SCAN");
        setText(aiStatus, "Sending scan command to ESP32");
        setText(detectedObject, "Waiting for detection result");
        updateConfidence(0);

        // ESP32 Code 2 supports /scan, not /search.
        const result = await sendRobotCommand("scan");

        if (result === null) {
            updateRobotStatus("CONNECTION ERROR");
            updateDetectionStatus("SCAN REQUEST FAILED");
            setText(aiStatus, "Check ESP32 connection");
            return;
        }

        updateRobotStatus("SCAN REQUEST SENT");
        updateDetectionStatus("SCAN REQUEST SENT");
        setText(
            aiStatus,
            "Scan command sent. Object matching requires a working camera and detection endpoint."
        );

        console.log("Scan requested for:", targetObject?.value || "No target");
    } finally {
        searchRunning = false;
    }
}

window.startSearch = startSearch;

// STOP BUTTON
async function stopSearch() {
    searchRunning = false;

    const result = await sendRobotCommand("stop");

    updateRobotStatus(result === null ? "CONNECTION ERROR" : "STOPPED");
    updateDetectionStatus("SEARCH STOPPED");
    setText(movementState, "STOPPED");
    setText(aiStatus, "Stop command sent");
}

window.stopSearch = stopSearch;

// OBJECT FOUND BUTTON / ACTION
async function objectFound() {
    const result = await sendRobotCommand("found");
    if (result === null) return;

    searchRunning = false;
    updateRobotStatus("OBJECT FOUND");
    updateDetectionStatus("FOUND");
    setText(movementState, "STOPPED");
    setText(aiStatus, "Object found command sent");
}

window.objectFound = objectFound;

// HISTORY HELPER
function addHistory(object, conf, status) {
    const table = $("history");
    if (!table) return;

    historyEvents++;

    const row = document.createElement("tr");
    [object, `${conf}%`, status, new Date().toLocaleTimeString()]
        .forEach(value => {
            const cell = document.createElement("td");
            cell.textContent = String(value);
            row.appendChild(cell);
        });

    if (status === "Found") {
        row.children[2].className = "status-found";
    }

    table.prepend(row);
    setText(
        historyCount,
        `${historyEvents} ${historyEvents === 1 ? "event" : "events"}`
    );
}

window.addHistory = addHistory;

// CONNECTION STATUS
async function checkRobotConnection() {
    try {
        const response = await fetch(`${ESP32_URL}/`, {
            method: "GET",
            mode: "cors",
            cache: "no-store",
            signal: AbortSignal.timeout(4000)
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const result = await response.text();
        console.log("ESP32 connected:", result);

        if (robotLink) robotLink.textContent = "CONNECTED";
        updateRobotStatus("IDLE");
        return true;
    } catch (error) {
        console.error("ESP32 connection failed:", error);
        if (robotLink) robotLink.textContent = "OFFLINE";
        return false;
    }
}

async function checkBackendConnection() {
    try {
        const response = await fetch(`${BACKEND_URL}/`, {
            method: "GET",
            cache: "no-store",
            signal: AbortSignal.timeout(4000)
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const result = await response.json();
        console.log("Flask backend connected:", result);

        if (cloudStatus) {
            cloudStatus.textContent = "ML Backend Connected";
            cloudStatus.style.color = "#00ff88";
        }

        return true;
    } catch (error) {
        console.error("Flask backend connection failed:", error);

        if (cloudStatus) {
            cloudStatus.textContent = "Backend Offline";
            cloudStatus.style.color = "#ff4d6d";
        }

        return false;
    }
}

window.checkRobotConnection = checkRobotConnection;
window.checkBackendConnection = checkBackendConnection;

// These endpoints are not implemented in the current ESP32 Code 2.
function setRobotSpeed(speed) {
    console.warn("Speed control is not supported by the current ESP32 code.");
    setText(aiStatus, "Speed control is not available.");
}

function setServoAngle(angle) {
    console.warn("Servo control is not supported by the current ESP32 code.");
    setText(aiStatus, "Servo control is not available.");
}

window.setRobotSpeed = setRobotSpeed;
window.setServoAngle = setServoAngle;

// KEYBOARD CONTROL (only while search is active)
document.addEventListener("keydown", event => {
    if (!searchRunning) return;

    if (["INPUT", "TEXTAREA", "SELECT"].includes(event.target?.tagName)) {
        return;
    }

    const commands = {
        ArrowUp: "forward",
        ArrowDown: "backward",
        ArrowLeft: "left",
        ArrowRight: "right",
        " ": "stop"
    };

    const command = commands[event.key];

    if (command) {
        event.preventDefault();
        robotCommand(command);
    }
});

// INITIALIZE
async function initializeDashboard() {
    console.log("AI Object Finder frontend loaded");
    console.log("ESP32 URL:", ESP32_URL);
    console.log("Backend URL:", BACKEND_URL);

    await Promise.all([
        checkBackendConnection(),
        checkRobotConnection()
    ]);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeDashboard);
} else {
    initializeDashboard();
}
