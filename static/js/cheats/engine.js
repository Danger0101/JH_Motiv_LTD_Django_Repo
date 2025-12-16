// static/js/cheats/engine.js

import {
  getCookie,
  notify,
  saveState,
  getState,
  isStateActive,
} from "./state.js";
import { effects } from "./effects.js";
// We keep redirects client-side for speed, but you can move them to python if you prefer
import { checkRedirects } from "./redirects.js";

(function initCheatEngine() {
  // --- 1. RESTORE STATE ---
  const allToggles = [
    "devmode",
    "doom",
    "bighead",
    "fps",
    "darkmode",
    "cyber",
    "retro",
    "matrix",
  ];
  allToggles.forEach((key) => {
    if (isStateActive(key) && effects[key]) effects[key](true);
  });

  const savedSeason = getState("season");
  if (savedSeason && effects.season) effects.season(savedSeason);

  // --- 2. CONFIG ---
  const INPUT_TIMEOUT_MS = 5000; // Reset buffer after 5s of inactivity
  const SERVER_CHECK_DELAY = 800; // Wait 0.8s after typing stops to check server
  let inputTimer = null; // Timer for clearing buffer
  let serverCheckTimer = null; // Timer for debouncing API call
  const keySequence = [];

  // --- 3. HELPER: VERIFY WITH PYTHON ---
  async function verifyWithServer(sequence) {
    try {
      const response = await fetch("/api/verify-cheat/", {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ sequence: sequence }),
      });

      const data = await response.json();

      if (data.status === "success") {
        const effect = data.effect;

        // 1. Show Notification
        if (effect.message) {
          notify(effect.message, effect.type || "success");
        }

        // 2. Handle Actions
        if (effect.action === "coupon") {
          if (effects.confetti) effects.confetti();
          if (effect.payload) {
            navigator.clipboard.writeText(effect.payload);
            notify("📋 Code copied to clipboard!", "info");
          }
        } else if (effect.action === "godmode") {
          document.body.style.transition = "transform 1s";
          document.body.style.transform = "rotate(180deg)";
          setTimeout(() => {
            document.body.style.transform = "none";
          }, 2000);
        } else if (effect.action === "redirect") {
          setTimeout(() => {
            window.location.href = effect.url;
          }, 1000);
        }

        // Clear buffer on success so we don't re-trigger
        keySequence.length = 0;
      }
    } catch (error) {
      console.error("Cheat verification failed:", error);
    }
  }

  // --- 4. LISTENER ---
  document.addEventListener("keydown", async function (e) {
    // A. Manage Buffer
    clearTimeout(inputTimer);
    inputTimer = setTimeout(() => {
      keySequence.length = 0;
    }, INPUT_TIMEOUT_MS);

    keySequence.push(e.key.toLowerCase());
    if (keySequence.length > 50) keySequence.shift();
    const currentSequence = keySequence.join("");

    // B. CLIENT-SIDE CHEATS (Themes/UI - Kept here for instant feedback)
    // You can move these to Python too if you want, but they are purely visual.
    const themes = {
      darkmode: "🌙 Dark Mode",
      cyber: "🤖 Cyberpunk Mode",
      retro: "📜 Retro Mode",
      devmode: "👨‍💻 Developer Mode",
      doom: "😈 Nightmare Difficulty",
      bighead: "🏀 Big Head Mode",
      fps: "⚡ FPS Counter",
      matrix: "💊 Matrix Rain",
    };

    for (const [code, label] of Object.entries(themes)) {
      if (currentSequence.endsWith(code)) {
        const newState = !isStateActive(code);
        saveState(code, newState);
        if (effects[code]) effects[code](newState);

        let msg = `${label}: ${newState ? "ON" : "OFF"}`;
        if (code === "doom" && newState)
          msg = "😈 NIGHTMARE DIFFICULTY STARTED";
        notify(msg, newState && code === "doom" ? "error" : "success");

        keySequence.length = 0;
        return;
      }
    }

    // C. SEASONS (Client-side)
    ["spring", "summer", "fall", "winter", "seasonpass"].forEach((code) => {
      if (currentSequence.endsWith(code)) {
        if (code === "seasonpass") {
          saveState("season", null);
          notify("🔄 Time Sync: Returning to Server Time", "warning");
          setTimeout(() => location.reload(), 1000);
        } else {
          saveState("season", code);
          effects.season(code);
          notify(`Season Pass: ${code.toUpperCase()} Activated`, "info");
        }
        keySequence.length = 0;
        return;
      }
    });

    // D. SERVER-SIDE CHECK (Hidden Codes)
    // Wait for the user to pause typing, then ask Python
    clearTimeout(serverCheckTimer);
    serverCheckTimer = setTimeout(() => {
      verifyWithServer(currentSequence);
    }, SERVER_CHECK_DELAY);
  });
})();
