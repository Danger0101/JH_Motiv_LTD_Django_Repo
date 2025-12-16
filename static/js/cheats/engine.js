import {
  getCookie,
  notify,
  saveState,
  getState,
  isStateActive,
} from "./state.js";
import { effects } from "./effects.js";

(function initCheatEngine() {
  // --- 0. INJECT STYLES ---
  const style = document.createElement("style");
  style.textContent = `
    #fps-counter, .fps-meter { top: 10px !important; left: 10px !important; right: auto !important; background: transparent !important; }
    #cookie-banner, .cookie-consent, #cookie-consent { top: 40px !important; left: 10px !important; bottom: auto !important; background: transparent !important; }
  `;
  document.head.appendChild(style);

  // --- 1. STATE RESTORATION (Obfuscated) ---
  // We use Base64 to hide the names of effects we need to check on load.
  // "bWF0cml4" = "matrix", "ZG9vbQ==" = "doom", etc.
  const knownEffects = [
    "ZGV2bW9kZQ==",
    "ZG9vbQ==",
    "YmlnaGVhZA==",
    "ZnBz",
    "ZGFya21vZGU=",
    "Y3liZXI=",
    "cmV0cm8=",
    "bWF0cml4",
  ];

  // Decode and check state
  knownEffects.forEach((encoded) => {
    try {
      const key = atob(encoded); // Decode Base64 to string
      if (isStateActive(key) && effects[key]) effects[key](true);
    } catch (e) {
      /* Ignore decode errors */
    }
  });

  // Restore Season
  const savedSeason = getState("season");
  if (savedSeason && effects.season) effects.season(savedSeason);

  // --- 2. CONFIGURATION ---
  const INPUT_TIMEOUT_MS = 2500;
  let inputTimer = null;
  const keySequence = [];

  const secureTriggers = {
    // Server Cheats
    "26483306fe596f32966dc4a03ff8d4325bccbdce03856380fd9e73f498ca32ef": 101,
    "527aee4e3b96dc5928ee45348c11c6f87f67bae2530fc20ea0b4463a1a8658d0": 102,
    "6e00cd562cc2d88e238dfb81d9439de7ec843ee9d0c9879d549cb1436786f975": 201,
    "c6b6adcb2249cb01bec3079c8574c0daac0a5713350359f3029c533dbc282826": 202,
    "b4bf5d7e5fcf89ef8adb64ec9c624db850d10f2afef020ed9ef23892df0833af": 203,
    "85e5464309915bf26655dc96473ac4eba700f78f757d67765a0360fb4e336aa4": 204,
    "8f0b5d8d5193f2a0aeefe48d108706a6623978f8216a26032697e5083e98ef58": 205,
    "910ecd3e43c7d241425a16a378dae72ea48201f9bada186f036d9bdeb4368444": 206,
    "c59d4aff30b0cba314b35c62e1704eee1bd05941aa576efdb965220b072f8864": 207,
    "1691107d9cceeda2cce620b1d20abe137294e9c148fb967c7af21db9957b9a5e": 208,
    "622a494d3ea8c7ba2fed4f37909f14d9b50ab412322de39be62c8d6c2418bfca": 301,
    "e83664255c6963e962bb20f9fcfaad1b570ddf5da69f5444ed37e5260f3ef689": 302,
    "2dc46af1b78c32dfe99dedfbdff6ca7f33e0f652716482f55b03622b67c06dea": 303,
    "30c5461fc27b84f1f1ad0a83162a26882b22d11cdfa45978dd21c810056e8d0e": 304,
    "56f2bffebefdebf8c0a12f233b7df7dd3cefad01fc785c836bd9a9805d3ca0a2": 305,
  };

  // --- 3. CRYPTO UTILITY ---
  async function sha256(message) {
    const msgBuffer = new TextEncoder().encode(message);
    const hashBuffer = await crypto.subtle.digest("SHA-256", msgBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  // --- 4. SERVER COMMUNICATION ---
  async function redeemCheat(cheatId) {
    try {
      const response = await fetch("/api/verify-cheat/", {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ cheat_id: cheatId }),
      });

      const data = await response.json();

      if (data.status === "success") {
        if (effects.confetti) effects.confetti();

        const effect = data.effect;
        if (effect.message) notify(effect.message, effect.type || "success");

        // Action Router
        switch (effect.action) {
          case "coupon":
            if (effect.payload) {
              navigator.clipboard.writeText(effect.payload);
              notify("📋 Code copied!", "info");
            }
            break;
          case "godmode":
            if (effects.godmode) effects.godmode();
            break;
          case "redirect":
            if (effect.url)
              setTimeout(() => (window.location.href = effect.url), 1000);
            break;
          case "toggle":
            if (effect.effect_id) {
              const code = effect.effect_id;
              const newState = !isStateActive(code);
              saveState(code, newState);
              if (effects[code]) effects[code](newState);
              notify(
                `${code.toUpperCase()} ${newState ? "ON" : "OFF"}`,
                "info"
              );
            }
            break;
          case "season":
            if (effect.value) {
              saveState("season", effect.value);
              if (effects.season) effects.season(effect.value);
              notify(`Season: ${effect.value.toUpperCase()}`, "info");
            }
            break;
          case "season_reset":
            saveState("season", null);
            notify("Syncing...", "warning");
            setTimeout(() => location.reload(), 1000);
            break;
        }
      }
    } catch (error) {
      console.error("Error:", error);
    }
  }

  // --- 5. KEY LISTENER ---
  document.addEventListener("keydown", async function (e) {
    clearTimeout(inputTimer);
    inputTimer = setTimeout(() => {
      keySequence.length = 0;
    }, INPUT_TIMEOUT_MS);

    keySequence.push(e.key.toLowerCase());
    if (keySequence.length > 50) keySequence.shift();

    const currentSequence = keySequence.join("");
    const currentHash = await sha256(currentSequence);

    if (secureTriggers[currentHash]) {
      redeemCheat(secureTriggers[currentHash]);
      keySequence.length = 0;
    }
  });
})();
