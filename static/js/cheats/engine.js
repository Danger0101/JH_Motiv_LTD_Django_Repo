// static/js/cheats/engine.js

import {
  getCookie,
  notify,
  saveState,
  getState,
  isStateActive,
} from "./state.js";
import { effects } from "./effects.js";

(function initCheatEngine() {
  // --- 1. STATE MANAGEMENT (Visual Toggles) ---
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

  // --- 2. SECURE CONFIGURATION ---
  const INPUT_TIMEOUT_MS = 3000; // Reset buffer if user stops typing
  let inputTimer = null;
  const keySequence = [];

  // 🔒 SECURE MAP: SHA-256 Hash -> Cheat ID
  // The keys look like gibberish, hiding the real code from snoopers.
  const secureTriggers = {
    // Sequence: "arrowuparrowuparrowdownarrowdownarrowarrowleftarrowrightarrowarrowleftarrowrightarrowba" -> ID: 101 (konami)
    "26483306fe596f32966dc4a03ff8d4325bccbdce03856380fd9e73f498ca32ef": 101,
    // Sequence: "idkfa" -> ID: 102 (godmode)
    "527aee4e3b96dc5928ee45348c11c6f87f67bae2530fc20ea0b4463a1a8658d0": 102,
    // Sequence: "loot" -> ID: 201
    "5c52b6deb3631a09d8c4f642675052e28acb2e7fff38a3e86067a25ef23b796a": 201,
    // Sequence: "shop" -> ID: 202
    "8d9001d32c6a703d95921a77115050f33dd823d3f1730bd35215dcbecad6dc20": 202,
    // Sequence: "home" -> ID: 203
    "4ea140588150773ce3aace786aeef7f4049ce100fa649c94fbbddb960f1da942": 203,
    // Sequence: "login" -> ID: 204
    "428821350e9691491f616b754cd8315fb86d797ab35d843479e732ef90665324": 204,
    // Sequence: "team" -> ID: 205
    "ca8b22d0db83a22db163b560b3e4e51527e533d31d067b614a0c33c4d2df8432": 205,
    // Sequence: "ban" -> ID: 206
    "b2a96c3d3fc2b6accdb4816e22467a7448defe3208a72a79a96d671e4087106e": 206,
    // Sequence: "lost" -> ID: 207
    "76f75e6129fe30135bd44d80ab7cc46fdba81907758dc808f3e2517beef2b1e9": 207,
    // Sequence: "crash" -> ID: 208
    "cdb2e0d0f873ce5326e87cf7dec48de8da3043cfc950a7eba05a059150e873f5": 208,
  };

  // --- 3. CRYPTO UTILITY ---
  // Converts string -> SHA-256 Hash using browser native API
  async function sha256(message) {
    const msgBuffer = new TextEncoder().encode(message);
    const hashBuffer = await crypto.subtle.digest("SHA-256", msgBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  // --- 4. SERVER COMMUNICATION ---
  // Only called when a hash match is confirmed locally
  async function redeemCheat(cheatId) {
    try {
      const response = await fetch("/api/verify-cheat/", {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ cheat_id: cheatId }), // We send "konami", not the keys
      });

      const data = await response.json();

      if (data.status === "success") {
        // Run the visual effect (Confetti, etc)
        if (effects.confetti) effects.confetti();

        // Handle Server Actions (e.g. Coupon)
        const effect = data.effect;
        if (effect.message) notify(effect.message, effect.type || "success");

        if (effect.payload) {
          navigator.clipboard.writeText(effect.payload);
          notify("📋 Code copied to clipboard!", "info");
        }

        if (effect.action === "godmode" && effects.godmode) {
          effects.godmode();
        } else if (effect.action === "redirect" && effect.url) {
          setTimeout(() => {
            window.location.href = effect.url;
          }, 1000);
        }
      }
    } catch (error) {
      console.error("Redemption failed:", error);
    }
  }

  // --- 5. KEY LISTENER ---
  document.addEventListener("keydown", async function (e) {
    // 1. Manage Buffer
    clearTimeout(inputTimer);
    inputTimer = setTimeout(() => {
      keySequence.length = 0;
    }, INPUT_TIMEOUT_MS);

    // Add key (lowercase)
    keySequence.push(e.key.toLowerCase());

    // Keep buffer short to optimize hashing performance
    if (keySequence.length > 50) keySequence.shift();

    const currentSequence = keySequence.join("");

    // 2. CHECK VISUAL CHEATS (Client-side toggles)
    // These don't need security, just simple string matching
    for (const code of allToggles) {
      if (currentSequence.endsWith(code)) {
        const newState = !isStateActive(code);
        saveState(code, newState);
        if (effects[code]) effects[code](newState);
        notify(`${code.toUpperCase()} ${newState ? "ON" : "OFF"}`, "info");
        keySequence.length = 0;
        return;
      }
    }

    // 3. SEASONS (Client-side)
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

    // 4. CHECK SECURE SERVER CHEATS
    // Calculate hash of current buffer
    const currentHash = await sha256(currentSequence);

    // Does this hash exist in our secure map?
    if (secureTriggers[currentHash]) {
      const cheatId = secureTriggers[currentHash];

      // Activate!
      redeemCheat(cheatId);

      // Clear buffer immediately to prevent double activation
      keySequence.length = 0;
    }
  });
})();
