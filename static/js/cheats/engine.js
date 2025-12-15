// 1. Imports (Now matching your renamed 'effects.js' file)
import { getCookie, notify, saveState, getState, isStateActive } from './state.js';
import { effects } from './effects.js';

// 2. Main Function (Self-executing to run immediately)
(function initCheatEngine() {
    
    // --- RESTORE STATE ON LOAD ---
    // We loop through all known cheats. If one was active, we turn it back on.
    const allToggles = ["devmode", "doom", "bighead", "fps", "darkmode", "cyber", "retro", "matrix"];
    
    allToggles.forEach((key) => {
        if (isStateActive(key)) {
            // Safety check: Does this effect exist in effects.js?
            if (effects[key]) {
                effects[key](true);
            }
        }
    });

    // Restore Season
    const savedSeason = getState("season");
    if (savedSeason && effects.season) {
        effects.season(savedSeason);
    }

    // --- CONFIGURATION ---
    const INPUT_TIMEOUT_MS = 5000; // Reset typing after 5 seconds of silence
    let inputTimer = null;
    const keySequence = [];
    const konamiCode = "arrowuparrowuparrowdownarrowdownarrowleftarrowrightarrowleftarrowrightarrowba";

    // --- KEY LISTENER ---
    document.addEventListener("keydown", async function (e) {
        // A. Timer Logic
        clearTimeout(inputTimer);
        inputTimer = setTimeout(() => { keySequence.length = 0; }, INPUT_TIMEOUT_MS);

        // B. Track Keys
        keySequence.push(e.key.toLowerCase());
        if (keySequence.length > 50) keySequence.shift(); // Keep buffer small
        const currentSequence = keySequence.join("");

        // --- 1. VISUAL THEMES ---
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
                // Toggle State
                const newState = !isStateActive(code);
                saveState(code, newState);
                
                // Apply Effect
                if (effects[code]) effects[code](newState);
                
                // Notify User
                let msg = `${label}: ${newState ? 'ON' : 'OFF'}`;
                if (code === 'doom' && newState) msg = "😈 NIGHTMARE DIFFICULTY STARTED";
                notify(msg, newState && code === 'doom' ? "error" : "success");
                
                keySequence.length = 0; // Reset buffer so we don't trigger it again immediately
                return;
            }
        }

        // --- 2. SEASONS ---
        ["spring", "summer", "fall", "winter"].forEach((season) => {
            if (currentSequence.endsWith(season)) {
                saveState("season", season);
                effects.season(season);
                const emojis = { spring: "🌸", summer: "☀️", fall: "🍂", winter: "❄️" };
                notify(`${emojis[season]} Season Pass: ${season.toUpperCase()} Activated`, "info");
                keySequence.length = 0;
            }
        });

        // --- 3. RESET SEASONS ---
        if (currentSequence.endsWith("seasonpass")) {
            saveState("season", null);
            notify("🔄 Time Sync: Returning to Server Time", "warning");
            setTimeout(() => location.reload(), 1000);
            keySequence.length = 0;
        }

        // --- 4. KONAMI CODE (Coupon) ---
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

        // --- 5. PAGE REDIRECTS ---
        if (currentSequence.endsWith("loot")) {
            notify("💰 Opening Inventory...", "success");
            setTimeout(() => window.location.href = "/cart/", 500);
            keySequence.length = 0;
        }
        
        if (currentSequence.endsWith("ban")) {
             notify("⛔ ACCESS DENIED.", "error");
             setTimeout(() => window.location.href = "/system/glitch/403/", 1000);
             keySequence.length = 0;
        }
        
        if (currentSequence.endsWith("crash")) {
             notify("🔥 SYSTEM FAILURE", "error");
             setTimeout(() => window.location.href = "/system/glitch/500/", 1000);
             keySequence.length = 0;
        }
    });
})();