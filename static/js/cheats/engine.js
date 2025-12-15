// static/js/cheats/engine.js
import { getCookie, notify, saveState, getState, isStateActive } from './state.js';
import { effects } from './effects.js';

document.addEventListener("alpine:init", () => {
    
    // --- INIT: Restore Active Cheats on Page Load ---
    // We check every saved state and re-apply effects
    const allToggles = ["devmode", "doom", "bighead", "fps", "darkmode", "cyber", "retro"];
    
    allToggles.forEach((key) => {
        if (isStateActive(key)) effects[key](true);
    });

    const savedSeason = getState("season");
    if (savedSeason && effects.season) {
        effects.season(savedSeason);
    }

    // --- CONFIG ---
    const INPUT_TIMEOUT_MS = 5000;
    let inputTimer = null;
    const keySequence = [];
    const konamiCode = "arrowuparrowuparrowdownarrowdownarrowleftarrowrightarrowleftarrowrightarrowba";

    // --- KEY LISTENER ---
    document.addEventListener("keydown", async function (e) {
        clearTimeout(inputTimer);
        inputTimer = setTimeout(() => { keySequence.length = 0; }, INPUT_TIMEOUT_MS);

        keySequence.push(e.key.toLowerCase());
        if (keySequence.length > 20) keySequence.shift();
        const currentSequence = keySequence.join("");

        // 1. THEME TOGGLES
        const themes = {
            darkmode: "🌙 Dark Mode",
            cyber: "🤖 Cyberpunk Mode",
            retro: "📜 Retro Mode",
            devmode: "👨‍💻 Developer Mode",
            doom: "😈 Nightmare Difficulty",
            bighead: "🏀 Big Head Mode",
            fps: "⚡ FPS Counter"
        };

        for (const [code, label] of Object.entries(themes)) {
            if (currentSequence.endsWith(code)) {
                // Toggle state
                const newState = !isStateActive(code);
                saveState(code, newState);
                
                // Apply effect
                effects[code](newState);
                
                // Notify
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

        // 3. RESET
        if (currentSequence.endsWith("seasonpass")) {
            saveState("season", null);
            notify("🔄 Time Sync: Returning to Server Time", "warning");
            setTimeout(() => location.reload(), 1000);
            keySequence.length = 0;
        }

        // 4. KONAMI COUPON
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

        // 5. ONE-OFFS (Redirects/Actions)
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
});