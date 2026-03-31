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

    let config = null;

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

    // Render gesture mapping rows
    function renderMappings() {
        if (!config || !config.mappings) return;
        mappingsList.innerHTML = "";
        for (const [gesture, mapping] of Object.entries(config.mappings)) {
            const row = document.createElement("div");
            row.className = "mapping-row";

            const label = document.createElement("span");
            label.className = "gesture-label";
            label.textContent = gesture.replaceAll("_", " ");

            const keyInput = document.createElement("input");
            keyInput.type = "text";
            keyInput.value = mapping.keys.join(" + ");
            keyInput.placeholder = "Click and press keys...";
            keyInput.readOnly = true;
            keyInput.dataset.gesture = gesture;

            keyInput.addEventListener("click", () => {
                keyInput.value = "";
                keyInput.classList.add("recording");
                keyInput.placeholder = "Press key combo...";
            });

            keyInput.addEventListener("keydown", (e) => {
                if (!keyInput.classList.contains("recording")) return;
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
                        // F1-F12, Enter, Escape, ArrowUp, etc.
                        const mapped = key.replace(/^Arrow/, "").toLowerCase();
                        keys.push(mapped);
                    }

                    keyInput.value = keys.join(" + ");
                    keyInput.classList.remove("recording");
                    config.mappings[gesture].keys = keys;
                }
            });

            keyInput.addEventListener("blur", () => {
                keyInput.classList.remove("recording");
                if (!keyInput.value) {
                    keyInput.value = mapping.keys.join(" + ");
                }
            });

            const toggle = document.createElement("label");
            toggle.className = "toggle-switch";
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.checked = mapping.enabled;
            checkbox.addEventListener("change", () => {
                config.mappings[gesture].enabled = checkbox.checked;
            });
            const slider = document.createElement("span");
            slider.className = "toggle-slider";
            toggle.appendChild(checkbox);
            toggle.appendChild(slider);

            row.appendChild(label);
            row.appendChild(keyInput);
            row.appendChild(toggle);
            mappingsList.appendChild(row);
        }
    }

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

    // Poll status
    async function pollStatus() {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();
            updateStatusUI(data.running);
            detectedGesture.textContent = data.gesture || "None";
            detectedConfidence.textContent = data.gesture
                ? `(${(data.confidence * 100).toFixed(0)}%)`
                : "";
        } catch { /* ignore */ }
    }

    // Init
    loadConfig();
    setInterval(pollStatus, 300);
});
