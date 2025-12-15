// static/js/cheats/engine.js

import { getCookie, notify, saveState, getState, isStateActive } from './state.js';
import { effects } from './effects.js';
import { checkRedirects } from './redirects.js';

(function initCheatEngine() {
    
    // --- 1. RESTORE STATE ---
    const allToggles = ["devmode", "doom", "bighead", "fps", "darkmode", "cyber", "retro", "matrix"];
    allToggles.forEach((key) => {
        if (isStateActive(key) && effects[key]) effects[key](true);
    });

    const savedSeason = getState("season");
    if (savedSeason && effects.season) effects.season(savedSeason);

    // --- 2. CONFIG ---
    const INPUT_TIMEOUT_MS = 5000;
    let inputTimer = null;
    const keySequence = [];
    const konamiCode = "arrowuparrowuparrowdownarrowdownarrowleftarrowrightarrowleftarrowrightarrowba";

    // --- 3. LISTENER ---
    document.addEventListener("keydown", async function (e) {
        clearTimeout(inputTimer);
        inputTimer = setTimeout(() => { keySequence.length = 0; }, INPUT_TIMEOUT_MS);

        keySequence.push(e.key.toLowerCase());
        if (keySequence.length > 50) keySequence.shift();
        const currentSequence = keySequence.join("");

        // A. CHECK REDIRECTS (Navigation)
        if (checkRedirects(currentSequence)) {
            keySequence.length = 0;
            return;
        }

        // B. THEME TOGGLES (Visuals)
        const themes = {
            darkmode: "🌙 Dark Mode",
            cyber: "🤖 Cyberpunk Mode",
            retro: "📜 Retro Mode",
            devmode: "👨‍💻 Developer Mode",
            doom: "😈 Nightmare Difficulty",
            bighead: "🏀 Big Head Mode",
            fps: "⚡ FPS Counter",
            matrix: "💊 Matrix Rain"
        };

        for (const [code, label] of Object.entries(themes)) {
            if (currentSequence.endsWith(code)) {
                const newState = !isStateActive(code);
                saveState(code, newState);
                if (effects[code]) effects[code](newState);
                
                let msg = `${label}: ${newState ? 'ON' : 'OFF'}`;
                if (code === 'doom' && newState) msg = "😈 NIGHTMARE DIFFICULTY STARTED";
                notify(msg, newState && code === 'doom' ? "error" : "success");
                
                keySequence.length = 0; 
                return;
            }
        }

        // C. SEASONS
        ["spring", "summer", "fall", "winter"].forEach((season) => {
            if (currentSequence.endsWith(season)) {
                saveState("season", season);
                effects.season(season);
                const emojis = { spring: "🌸", summer: "☀️", fall: "🍂", winter: "❄️" };
                notify(`${emojis[season]} Season Pass: ${season.toUpperCase()} Activated`, "info");
                keySequence.length = 0;
            }
        });

        // D. GOD MODE (Restored!)
        if (currentSequence.endsWith("idkfa")) {
            notify("⚡ GOD MODE: ACTIVATED", "warning");
            document.body.style.transition = "transform 1s";
            document.body.style.transform = "rotate(180deg)";
            setTimeout(() => { document.body.style.transform = "none"; }, 2000);
            keySequence.length = 0;
        }

        // E. SEASON RESET
        if (currentSequence.endsWith("seasonpass")) {
            saveState("season", null);
            notify("🔄 Time Sync: Returning to Server Time", "warning");
            setTimeout(() => location.reload(), 1000);
            keySequence.length = 0;
        }

        // F. KONAMI CODE (Coupon)
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
    });
})();