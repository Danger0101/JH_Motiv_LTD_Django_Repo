// static/js/cheats/engine.js
import { getCookie, notify, saveState, getState, isStateActive } from './state.js';
import { effects } from './effects.js';

document.addEventListener("alpine:init", () => {
    
    // --- RESTORE STATE ---
    ["devmode", "doom", "bighead", "fps", "matrix", "darkmode", "cyber"].forEach((key) => {
        if (isStateActive(key)) effects[key](true);
    });

    const savedSeason = getState("season");
    if (savedSeason && effects.season) {
        effects.season(savedSeason);
    }

    // --- INPUT CONFIG ---
    const INPUT_TIMEOUT_MS = 5000;
    let inputTimer = null;
    const keySequence = [];
    const konamiCode = "arrowuparrowuparrowdownarrowdownarrowleftarrowrightarrowleftarrowrightarrowba";

    // --- MAIN LISTENER ---
    document.addEventListener("keydown", async function (e) {
        // Reset timer
        clearTimeout(inputTimer);
        inputTimer = setTimeout(() => { keySequence.length = 0; }, INPUT_TIMEOUT_MS);

        // Track key
        keySequence.push(e.key.toLowerCase());
        if (keySequence.length > 20) keySequence.shift();
        const currentSequence = keySequence.join("");

        // 1. GLOBAL CHEATS (State Toggles)
        const toggleCheats = {
            devmode: "👨‍💻 Developer Mode",
            doom: "😈 Nightmare Difficulty",
            bighead: "🏀 Big Head Mode",
            fps: "⚡ FPS Counter",
            matrix: "💊 Matrix Rain",
            darkmode: "🌙 Dark Mode",  // NEW
            cyber: "🤖 Cyberpunk Mode" // NEW
        };

        for (const [code, label] of Object.entries(toggleCheats)) {
            if (currentSequence.endsWith(code)) {
                const newState = !isStateActive(code);
                saveState(code, newState);
                effects[code](newState);
                
                // Special message logic
                let msg = `${label}: ${newState ? 'ON' : 'OFF'}`;
                if (code === 'doom' && newState) msg = "😈 NIGHTMARE DIFFICULTY STARTED";
                
                notify(msg, newState && code === 'doom' ? "error" : "success");
                keySequence.length = 0;
                return;
            }
        }

        // 2. SEASONS
        ["spring", "summer", "fall", "winter"].forEach((season) => {
            if (currentSequence.endsWith(season)) {
                saveState("season", season);
                effects.season(season);
                const emojis = { spring: "🌸", summer: "☀️", fall: "🍂", winter: "❄️" };
                notify(`${emojis[season]} Season Pass: ${season.toUpperCase()} Activated`, "info");
                keySequence.length = 0;
            }
        });

        // 3. RESET SEASONS
        if (currentSequence.endsWith("seasonpass")) {
            saveState("season", null);
            notify("🔄 Time Sync: Returning to Server Time", "warning");
            setTimeout(() => location.reload(), 1000);
            keySequence.length = 0;
        }

        // 4. KONAMI CODE (Coupon)
        if (currentSequence.endsWith(konamiCode)) {
            notify("👾 Input Accepted. Processing Cheat...", "info");
            try {
                const response = await fetch("/api/cheat-code/", {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCookie("csrftoken"),
                        "Content-Type": "application/json",
                    },
                });
                const data = await response.json();
                notify(data.message, data.status === "error" ? "error" : "success");
                if (data.status === "success" && data.code) {
                    navigator.clipboard.writeText(data.code);
                }
            } catch (error) {
                notify("🚫 System Error: Cheat Failed.", "error");
            }
            keySequence.length = 0;
        }

        // 5. ONE-OFF ACTIONS
        const oneOffs = {
            loot: { msg: "💰 Opening Inventory...", action: () => setTimeout(() => window.location.href = "/cart/", 500) },
            idkfa: { msg: "⚡ GOD MODE: ACTIVATED", type: "warning", action: () => {
                document.body.style.transition = "transform 1s";
                document.body.style.transform = "rotate(180deg)";
                setTimeout(() => { document.body.style.transform = "none"; }, 2000);
            }},
            ban: { msg: "⛔ ACCESS DENIED.", type: "error", action: () => setTimeout(() => window.location.href = "/system/glitch/403/", 1000) },
            lost: { msg: "🗺️ Signal Lost.", type: "warning", action: () => setTimeout(() => window.location.href = "/system/glitch/404/", 1000) },
            crash: { msg: "🔥 SYSTEM FAILURE", type: "error", action: () => setTimeout(() => window.location.href = "/system/glitch/500/", 1000) }
        };

        for (const [code, config] of Object.entries(oneOffs)) {
            if (currentSequence.endsWith(code)) {
                notify(config.msg, config.type || "success");
                if (config.action) config.action();
                keySequence.length = 0;
                return;
            }
        }
    });
});