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
    const profilesList = document.getElementById("profiles-list");
    const addProfileBtn = document.getElementById("add-profile-btn");
    const activeAppEl = document.getElementById("active-app");
    const activeProfileEl = document.getElementById("active-profile");
    const cameraSelect = document.getElementById("camera-select");
    const refreshCamerasBtn = document.getElementById("refresh-cameras-btn");
    const videoFeed = document.getElementById("video-feed");
    const defaultEnabledToggle = document.getElementById("default-enabled-toggle");
    const mappingsListEl = document.getElementById("mappings-list");

    let config = null;
    let activePresetGesture = null;
    // When a preset is chosen, target either the default mappings or a specific profile.
    // Shape: { kind: "default" } or { kind: "profile", profileIndex: number, gesture: string }
    let presetTarget = null;

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
        { label: "Mute", keys: ["volumemute"] },
        { label: "Play/Pause", keys: ["playpause"] },
        { label: "Next Track", keys: ["nexttrack"] },
        { label: "Prev Track", keys: ["prevtrack"] },
    ];

    // Load config
    async function loadConfig() {
        try {
            const res = await fetch("/api/config");
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            config = await res.json();
            if (!Array.isArray(config.profiles)) config.profiles = [];
            if (typeof config.default_enabled !== "boolean") config.default_enabled = true;
            if (defaultEnabledToggle) {
                defaultEnabledToggle.checked = config.default_enabled;
                applyDefaultSectionState();
            }
            renderMappings();
            renderProfiles();
            cooldownSlider.value = config.cooldown_ms;
            cooldownValue.textContent = config.cooldown_ms;
            thresholdSlider.value = config.confidence_threshold;
            thresholdValue.textContent = config.confidence_threshold.toFixed(2);
            await loadCameras();
        } catch (e) {
            console.error("Failed to load config:", e);
        }
    }

    // Camera picker
    async function loadCameras() {
        if (!cameraSelect) return;
        const previous = cameraSelect.value;
        cameraSelect.disabled = true;
        cameraSelect.innerHTML = "<option>Scanning...</option>";
        try {
            const res = await fetch("/api/cameras");
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            cameraSelect.innerHTML = "";
            for (const cam of data.cameras) {
                const opt = document.createElement("option");
                opt.value = String(cam.index);
                const tags = [];
                if (cam.current) tags.push("current");
                if (!cam.available && !cam.current) tags.push("unavailable");
                const tagStr = tags.length ? ` (${tags.join(", ")})` : "";
                opt.textContent = `Camera ${cam.index}${tagStr}`;
                if (!cam.available && !cam.current) opt.disabled = true;
                cameraSelect.appendChild(opt);
            }
            // Prefer current camera from config, else preserve previous selection
            cameraSelect.value = String(config.camera_index);
            if (cameraSelect.value === "" && previous) cameraSelect.value = previous;
        } catch (e) {
            console.error("Failed to load cameras:", e);
            cameraSelect.innerHTML = "<option>Error</option>";
        } finally {
            cameraSelect.disabled = false;
        }
    }

    async function applyCamera(newIndex) {
        // Save just the camera_index field and trigger backend engine restart.
        saveStatus.textContent = "Switching camera...";
        saveStatus.style.color = "#aaa";
        try {
            const res = await fetch("/api/config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ camera_index: newIndex }),
            });
            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                saveStatus.textContent = data.error || "Camera switch failed";
                saveStatus.style.color = "#ff6b6b";
                return;
            }
            config.camera_index = newIndex;
            // Force MJPEG reconnect so the stream picks up the new engine
            if (videoFeed) {
                const src = videoFeed.src.split("?")[0];
                videoFeed.src = `${src}?t=${Date.now()}`;
            }
            saveStatus.textContent = "Camera switched";
            saveStatus.style.color = "#00d4aa";
            setTimeout(() => { saveStatus.textContent = ""; }, 2000);
        } catch (e) {
            saveStatus.textContent = "Connection error";
            saveStatus.style.color = "#ff6b6b";
        }
    }

    if (cameraSelect) {
        cameraSelect.addEventListener("change", () => {
            const val = parseInt(cameraSelect.value, 10);
            if (!Number.isNaN(val) && val !== config.camera_index) {
                applyCamera(val);
            }
        });
    }
    if (refreshCamerasBtn) {
        refreshCamerasBtn.addEventListener("click", () => {
            loadCameras();
        });
    }

    function applyDefaultSectionState() {
        if (!mappingsListEl) return;
        mappingsListEl.classList.toggle("section-disabled", !config.default_enabled);
    }

    if (defaultEnabledToggle) {
        defaultEnabledToggle.addEventListener("change", () => {
            config.default_enabled = defaultEnabledToggle.checked;
            applyDefaultSectionState();
        });
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
                presetTarget = { kind: "default" };
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
                if (!activePresetGesture) {
                    presetModal.style.display = "none";
                    return;
                }
                if (presetTarget && presetTarget.kind === "profile") {
                    const p = config.profiles[presetTarget.profileIndex];
                    if (p) {
                        if (!p.mappings[activePresetGesture]) {
                            p.mappings[activePresetGesture] = { keys: [], enabled: true };
                        }
                        p.mappings[activePresetGesture].keys = [...preset.keys];
                        p.mappings[activePresetGesture].enabled = true;
                        renderProfiles();
                    }
                } else if (config.mappings[activePresetGesture]) {
                    config.mappings[activePresetGesture].keys = [...preset.keys];
                    renderMappings();
                }
                presetModal.style.display = "none";
            });
            presetGrid.appendChild(btn);
        }
        presetModal.style.display = "flex";
    }

    // Profiles UI
    function renderProfiles() {
        profilesList.innerHTML = "";
        if (!config.profiles || config.profiles.length === 0) {
            const empty = document.createElement("p");
            empty.className = "profiles-empty";
            empty.textContent = "No profiles yet. Click + to add one (e.g. \"Spotify\" matching \"spotify\").";
            profilesList.appendChild(empty);
            return;
        }
        config.profiles.forEach((profile, idx) => {
            profilesList.appendChild(renderProfileCard(profile, idx));
        });
    }

    function renderProfileCard(profile, idx) {
        const card = document.createElement("div");
        card.className = "profile-card";

        // Header: name input + delete button
        const header = document.createElement("div");
        header.className = "profile-header";

        const nameInput = document.createElement("input");
        nameInput.type = "text";
        nameInput.className = "profile-name-input";
        nameInput.placeholder = "Profile name (e.g. Spotify)";
        nameInput.value = profile.name || "";
        nameInput.addEventListener("input", () => {
            config.profiles[idx].name = nameInput.value;
        });

        const deleteBtn = document.createElement("button");
        deleteBtn.className = "btn-icon btn-clear";
        deleteBtn.innerHTML = "✕";
        deleteBtn.title = "Delete profile";
        deleteBtn.addEventListener("click", () => {
            config.profiles.splice(idx, 1);
            renderProfiles();
        });

        header.appendChild(nameInput);
        header.appendChild(deleteBtn);

        // Patterns input — comma-separated
        const patternsRow = document.createElement("div");
        patternsRow.className = "profile-patterns-row";
        const patternsLabel = document.createElement("label");
        patternsLabel.textContent = "Match exe (comma-separated):";
        const patternsInput = document.createElement("input");
        patternsInput.type = "text";
        patternsInput.className = "profile-patterns-input";
        patternsInput.placeholder = "spotify, chrome";
        patternsInput.value = (profile.app_patterns || []).join(", ");
        patternsInput.addEventListener("input", () => {
            config.profiles[idx].app_patterns = patternsInput.value
                .split(",")
                .map(s => s.trim())
                .filter(s => s.length > 0);
        });
        patternsRow.appendChild(patternsLabel);
        patternsRow.appendChild(patternsInput);

        // Override rows — one per gesture
        const overridesList = document.createElement("div");
        overridesList.className = "profile-overrides";

        const GESTURES_ORDER = Object.keys(config.mappings);
        for (const gesture of GESTURES_ORDER) {
            const override = profile.mappings[gesture] || { keys: [], enabled: false };
            const isOverridden = override.keys.length > 0 && override.enabled;

            const row = document.createElement("div");
            row.className = "override-row" + (isOverridden ? " override-active" : "");

            const labelArea = document.createElement("div");
            labelArea.className = "gesture-info";
            const icon = GESTURE_ICONS[gesture] || "";
            labelArea.innerHTML = `<span class="gesture-icon">${icon}</span><span class="gesture-label">${gesture.replaceAll("_", " ")}</span>`;

            const keyDisplay = document.createElement("div");
            keyDisplay.className = "key-display";
            keyDisplay.innerHTML = renderKeyBadges(override.keys);
            keyDisplay.title = "Click to record override";

            const keyInput = document.createElement("input");
            keyInput.type = "text";
            keyInput.className = "key-recorder";
            keyInput.style.display = "none";

            const actions = document.createElement("div");
            actions.className = "shortcut-actions";

            const recordBtn = document.createElement("button");
            recordBtn.className = "btn-icon btn-record";
            recordBtn.innerHTML = "⌨";
            recordBtn.title = "Record override";

            const presetBtn = document.createElement("button");
            presetBtn.className = "btn-icon btn-preset";
            presetBtn.innerHTML = "☰";
            presetBtn.title = "Choose from presets";

            const clearBtn = document.createElement("button");
            clearBtn.className = "btn-icon btn-clear";
            clearBtn.innerHTML = "✕";
            clearBtn.title = "Clear override (gesture will not fire inside this profile)";

            actions.appendChild(recordBtn);
            actions.appendChild(presetBtn);
            actions.appendChild(clearBtn);

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
                if (["Control", "Alt", "Shift", "Meta"].includes(key)) return;
                if (key === " ") keys.push("space");
                else if (key.length === 1) keys.push(key.toLowerCase());
                else keys.push(key.replace(/^Arrow/, "").toLowerCase());
                const finalKeys = keys.slice(0, 3);
                config.profiles[idx].mappings[gesture] = {
                    keys: finalKeys,
                    enabled: true,
                };
                renderProfiles();
            });
            keyInput.addEventListener("blur", stopRecording);

            presetBtn.addEventListener("click", () => {
                activePresetGesture = gesture;
                presetTarget = { kind: "profile", profileIndex: idx, gesture };
                showPresetModal();
            });

            clearBtn.addEventListener("click", () => {
                delete config.profiles[idx].mappings[gesture];
                renderProfiles();
            });

            row.appendChild(labelArea);
            row.appendChild(keyDisplay);
            row.appendChild(keyInput);
            row.appendChild(actions);
            overridesList.appendChild(row);
        }

        card.appendChild(header);
        card.appendChild(patternsRow);
        card.appendChild(overridesList);
        return card;
    }

    addProfileBtn.addEventListener("click", () => {
        config.profiles.push({
            name: "",
            app_patterns: [],
            mappings: {},
        });
        renderProfiles();
    });

    modalClose.addEventListener("click", () => {
        presetModal.style.display = "none";
    });
    presetModal.addEventListener("click", (e) => {
        if (e.target === presetModal) presetModal.style.display = "none";
    });

    // Sliders — text updates immediately, config update is debounced so we
    // don't spam updates while the user drags the slider.
    function debounce(fn, wait) {
        let t = null;
        return (...args) => {
            if (t !== null) clearTimeout(t);
            t = setTimeout(() => { t = null; fn(...args); }, wait);
        };
    }

    const commitCooldown = debounce((value) => {
        if (config) config.cooldown_ms = value;
    }, 150);
    cooldownSlider.addEventListener("input", () => {
        const value = parseInt(cooldownSlider.value, 10);
        cooldownValue.textContent = cooldownSlider.value;
        commitCooldown(value);
    });

    const commitThreshold = debounce((value) => {
        if (config) config.confidence_threshold = value;
    }, 150);
    thresholdSlider.addEventListener("input", () => {
        const value = parseFloat(thresholdSlider.value);
        thresholdValue.textContent = value.toFixed(2);
        commitThreshold(value);
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
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
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
    let consecutivePollErrors = 0;
    async function pollStatus() {
        try {
            const res = await fetch("/api/status");
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            consecutivePollErrors = 0;
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

            // Active app + profile indicator
            if (activeAppEl) {
                activeAppEl.textContent = data.active_app || "-";
            }
            if (activeProfileEl) {
                if (data.active_profile) {
                    activeProfileEl.textContent = data.active_profile;
                    activeProfileEl.style.display = "";
                } else {
                    activeProfileEl.style.display = "none";
                }
            }
        } catch (e) {
            consecutivePollErrors += 1;
            // Log only the first few so a disconnected server doesn't flood the console.
            if (consecutivePollErrors <= 3) {
                console.warn("Status poll failed:", e);
            }
        }
    }

    // Init
    loadConfig();
    const pollHandle = setInterval(pollStatus, 300);
    window.addEventListener("beforeunload", () => clearInterval(pollHandle));
});
