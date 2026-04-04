document.addEventListener("DOMContentLoaded", () => {
    const statusDot = document.getElementById("status-indicator");
    const statusText = document.getElementById("status-text");
    const toggleBtn = document.getElementById("toggle-btn");
    const detectedGesture = document.getElementById("detected-gesture");
    const detectedConfidence = document.getElementById("detected-confidence");
    const mappingsList = document.getElementById("mappings-list");
    const cooldownSlider = document.getElementById("cooldown");
    const cooldownValue = document.getElementById("cooldown-value");
    const thresholdSlider = document.getElementById("threshold");
    const thresholdValue = document.getElementById("threshold-value");
    const saveBtn = document.getElementById("save-btn");
    const saveStatus = document.getElementById("save-status");
    const presetModal = document.getElementById("preset-modal");
    const presetGrid = document.getElementById("preset-grid");
    const modalClose = document.getElementById("modal-close");

    let config = null;
    let activePresetGesture = null;

    // Gesture icons
    const GESTURE_ICONS = {
        "Closed_Fist": "\u270a",
        "Open_Palm": "\u270b",
        "Pointing_Up": "\u261d\ufe0f",
        "Thumb_Down": "\ud83d\udc4e",
        "Thumb_Up": "\ud83d\udc4d",
        "Victory": "\u270c\ufe0f",
        "ILoveYou": "\ud83e\udd1f",
    };

    // Common shortcut presets
    const PRESETS = [
        { label: "Enter", keys: ["enter"] },
        { label: "Space", keys: ["space"] },
        { label: "Escape", keys: ["esc"] },
        { label: "Tab", keys: ["tab"] },
        { label: "Backspace", keys: ["backspace"] },
        { label: "Delete", keys: ["delete"] },
        { label: "Up", keys: ["up"] },
        { label: "Down", keys: ["down"] },
        { label: "Left", keys: ["left"] },
        { label: "Right", keys: ["right"] },
        { label: "Alt + F4", keys: ["alt", "f4"] },
        { label: "Alt + Tab", keys: ["alt", "tab"] },
        { label: "Ctrl + C", keys: ["ctrl", "c"] },
        { label: "Ctrl + V", keys: ["ctrl", "v"] },
        { label: "Ctrl + Z", keys: ["ctrl", "z"] },
        { label: "Ctrl + S", keys: ["ctrl", "s"] },
        { label: "Ctrl + A", keys: ["ctrl", "a"] },
        { label: "Ctrl + W", keys: ["ctrl", "w"] },
        { label: "Win + D", keys: ["win", "d"] },
        { label: "Win + L", keys: ["win", "l"] },
        { label: "Ctrl+Shift+Esc", keys: ["ctrl", "shift", "esc"] },
        { label: "Ctrl+Alt+Del", keys: ["ctrl", "alt", "delete"] },
        { label: "Print Screen", keys: ["printscreen"] },
        { label: "F5 (Refresh)", keys: ["f5"] },
        { label: "F11 (Fullscreen)", keys: ["f11"] },
        { label: "Volume Up", keys: ["volumeup"] },
        { label: "Volume Down", keys: ["volumedown"] },
        { label: "Play/Pause", keys: ["playpause"] },
    ];

    // Load config
    async function loadConfig() {
        try {
            const res = await fetch("/api/config");
            config = await res.json();
            renderMappings();
            cooldownSlider.value = config.cooldown_ms;
            cooldownValue.textContent = config.cooldown_ms;
            thresholdSlider.value = config.confidence_threshold;
            thresholdValue.textContent = config.confidence_threshold.toFixed(2);
        } catch (e) {
            console.error("Failed to load config:", e);
        }
    }

    // Render styled key badges
    function renderKeyBadges(keys) {
        if (!keys || keys.length === 0) {
            return '<span class="key-empty">Not assigned</span>';
        }
        return keys.map(k => {
            const display = k.charAt(0).toUpperCase() + k.slice(1);
            return `<span class="key-badge">${display}</span>`;
        }).join('<span class="key-plus">+</span>');
    }

    // Render gesture mapping rows
    function renderMappings() {
        if (!config || !config.mappings) return;
        mappingsList.innerHTML = "";
        for (const [gesture, mapping] of Object.entries(config.mappings)) {
            const row = document.createElement("div");
            row.className = "mapping-row";
            row.dataset.gesture = gesture;

            // Gesture icon + name
            const labelArea = document.createElement("div");
            labelArea.className = "gesture-info";
            const icon = GESTURE_ICONS[gesture] || "";
            labelArea.innerHTML = `<span class="gesture-icon">${icon}</span><span class="gesture-label">${gesture.replaceAll("_", " ")}</span>`;

            // Shortcut display area
            const shortcutArea = document.createElement("div");
            shortcutArea.className = "shortcut-area";

            const keyDisplay = document.createElement("div");
            keyDisplay.className = "key-display";
            keyDisplay.innerHTML = renderKeyBadges(mapping.keys);
            keyDisplay.title = "Click to record new shortcut";

            // Hidden input for recording
            const keyInput = document.createElement("input");
            keyInput.type = "text";
            keyInput.className = "key-recorder";
            keyInput.style.display = "none";
            keyInput.placeholder = "Press keys...";

            // Action buttons
            const actions = document.createElement("div");
            actions.className = "shortcut-actions";

            const recordBtn = document.createElement("button");
            recordBtn.className = "btn-icon btn-record";
            recordBtn.innerHTML = "\u2328";
            recordBtn.title = "Record shortcut";

            const presetBtn = document.createElement("button");
            presetBtn.className = "btn-icon btn-preset";
            presetBtn.innerHTML = "\u2630";
            presetBtn.title = "Choose from presets";

            const clearBtn = document.createElement("button");
            clearBtn.className = "btn-icon btn-clear";
            clearBtn.innerHTML = "\u2715";
            clearBtn.title = "Clear shortcut";

            actions.appendChild(recordBtn);
            actions.appendChild(presetBtn);
            actions.appendChild(clearBtn);

            shortcutArea.appendChild(keyDisplay);
            shortcutArea.appendChild(keyInput);
            shortcutArea.appendChild(actions);

            // Toggle switch
            const toggle = document.createElement("label");
            toggle.className = "toggle-switch";
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.checked = mapping.enabled;
            checkbox.addEventListener("change", () => {
                config.mappings[gesture].enabled = checkbox.checked;
                row.classList.toggle("mapping-disabled", !checkbox.checked);
            });
            const slider = document.createElement("span");
            slider.className = "toggle-slider";
            toggle.appendChild(checkbox);
            toggle.appendChild(slider);

            if (!mapping.enabled) row.classList.add("mapping-disabled");

            // Record click
            function startRecording() {
                keyDisplay.style.display = "none";
                keyInput.style.display = "block";
                keyInput.value = "";
                keyInput.focus();
                row.classList.add("recording");
            }

            function stopRecording() {
                keyDisplay.style.display = "flex";
                keyInput.style.display = "none";
                row.classList.remove("recording");
            }

            keyDisplay.addEventListener("click", startRecording);
            recordBtn.addEventListener("click", startRecording);

            keyInput.addEventListener("keydown", (e) => {
                e.preventDefault();
                e.stopPropagation();

                const keys = [];
                if (e.ctrlKey) keys.push("ctrl");
                if (e.altKey) keys.push("alt");
                if (e.shiftKey) keys.push("shift");
                if (e.metaKey) keys.push("win");

                const key = e.key;
                if (!["Control", "Alt", "Shift", "Meta"].includes(key)) {
                    if (key === " ") {
                        keys.push("space");
                    } else if (key.length === 1) {
                        keys.push(key.toLowerCase());
                    } else {
                        const mapped = key.replace(/^Arrow/, "").toLowerCase();
                        keys.push(mapped);
                    }

                    // Limit to 3 keys
                    const finalKeys = keys.slice(0, 3);
                    config.mappings[gesture].keys = finalKeys;
                    keyDisplay.innerHTML = renderKeyBadges(finalKeys);
                    stopRecording();
                }
            });

            keyInput.addEventListener("blur", stopRecording);

            // Preset click
            presetBtn.addEventListener("click", () => {
                activePresetGesture = gesture;
                showPresetModal();
            });

            // Clear click
            clearBtn.addEventListener("click", () => {
                config.mappings[gesture].keys = [];
                keyDisplay.innerHTML = renderKeyBadges([]);
            });

            row.appendChild(labelArea);
            row.appendChild(shortcutArea);
            row.appendChild(toggle);
            mappingsList.appendChild(row);
        }
    }

    // Preset modal
    function showPresetModal() {
        presetGrid.innerHTML = "";
        for (const preset of PRESETS) {
            const btn = document.createElement("button");
            btn.className = "preset-btn";
            btn.innerHTML = renderKeyBadges(preset.keys);
            btn.addEventListener("click", () => {
                if (activePresetGesture && config.mappings[activePresetGesture]) {
                    config.mappings[activePresetGesture].keys = [...preset.keys];
                    renderMappings();
                }
                presetModal.style.display = "none";
            });
            presetGrid.appendChild(btn);
        }
        presetModal.style.display = "flex";
    }

    modalClose.addEventListener("click", () => {
        presetModal.style.display = "none";
    });
    presetModal.addEventListener("click", (e) => {
        if (e.target === presetModal) presetModal.style.display = "none";
    });

    // Sliders
    cooldownSlider.addEventListener("input", () => {
        cooldownValue.textContent = cooldownSlider.value;
        config.cooldown_ms = parseInt(cooldownSlider.value, 10);
    });

    thresholdSlider.addEventListener("input", () => {
        thresholdValue.textContent = parseFloat(thresholdSlider.value).toFixed(2);
        config.confidence_threshold = parseFloat(thresholdSlider.value);
    });

    // Save
    saveBtn.addEventListener("click", async () => {
        try {
            const res = await fetch("/api/config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(config),
            });
            if (res.ok) {
                saveStatus.textContent = "Saved!";
                saveStatus.style.color = "#00d4aa";
                setTimeout(() => { saveStatus.textContent = ""; }, 2000);
            } else {
                const data = await res.json();
                saveStatus.textContent = data.error || "Error saving";
                saveStatus.style.color = "#ff6b6b";
            }
        } catch (e) {
            saveStatus.textContent = "Connection error";
            saveStatus.style.color = "#ff6b6b";
        }
    });

    // Toggle engine
    toggleBtn.addEventListener("click", async () => {
        try {
            const res = await fetch("/api/toggle", { method: "POST" });
            const data = await res.json();
            updateStatusUI(data.running);
        } catch (e) {
            console.error("Toggle failed:", e);
        }
    });

    function updateStatusUI(running) {
        statusDot.className = "status-dot " + (running ? "active" : "paused");
        statusText.textContent = running ? "Running" : "Paused";
        toggleBtn.textContent = running ? "Disable" : "Enable";
        toggleBtn.className = "btn btn-toggle" + (running ? "" : " paused");
    }

    // Poll status - highlight active gesture
    async function pollStatus() {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();
            updateStatusUI(data.running);
            detectedGesture.textContent = data.gesture || "None";
            detectedConfidence.textContent = data.gesture
                ? `(${(data.confidence * 100).toFixed(0)}%)`
                : "";

            // Highlight active gesture row
            document.querySelectorAll(".mapping-row").forEach(row => {
                row.classList.toggle("gesture-active",
                    row.dataset.gesture === data.gesture);
            });
        } catch { /* ignore */ }
    }

    // Init
    loadConfig();
    setInterval(pollStatus, 300);
});
