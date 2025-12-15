document.addEventListener("alpine:init", () => {
  // ==========================================
  //  1. CONFIGURATION & HELPERS
  // ==========================================

  // How long to wait before resetting the keystroke buffer (in ms)
  const INPUT_TIMEOUT_MS = 5000;
  let inputTimer = null;

  // Persistence Keys
  const STORAGE_KEY_PREFIX = "cheat_state_";

  // --- HELPER: Get CSRF Token ---
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  // --- HELPER: Trigger Toast ---
  function notify(msg, type = "info") {
    window.dispatchEvent(
      new CustomEvent("show-toast", {
        detail: { message: msg, type: type },
      })
    );
  }

  // --- HELPER: State Management ---
  function saveState(cheatName, isActive) {
    if (isActive) {
      localStorage.setItem(STORAGE_KEY_PREFIX + cheatName, "true");
    } else {
      localStorage.removeItem(STORAGE_KEY_PREFIX + cheatName);
    }
  }

  function isStateActive(cheatName) {
    return localStorage.getItem(STORAGE_KEY_PREFIX + cheatName) === "true";
  }

  // ==========================================
  //  2. EFFECT APPLICATORS (Reusable)
  // ==========================================

  const effects = {
    devmode: (enable) => {
      if (enable) {
        document.body.classList.add("font-mono", "text-green-500", "bg-black");
      } else {
        document.body.classList.remove(
          "font-mono",
          "text-green-500",
          "bg-black"
        );
      }
    },
    doom: (enable) => {
      if (enable) {
        document.body.style.transition = "filter 0.5s";
        document.body.style.filter =
          "contrast(200%) grayscale(100%) drop-shadow(0 0 5px red)";
        document.documentElement.style.backgroundColor = "#1a0505";
      } else {
        document.body.style.filter = "none";
        document.documentElement.style.backgroundColor = "";
      }
    },
    bighead: (enable) => {
      const images = document.querySelectorAll("img");
      images.forEach((img) => {
        if (enable) {
          img.style.transition = "transform 0.3s ease";
          img.style.transform = "scale(1.5)";
          img.style.zIndex = "50";
          img.style.position = "relative";
        } else {
          img.style.transform = "none";
          img.style.zIndex = "auto";
          img.style.position = "static";
        }
      });
    },
    fps: (enable) => {
      let fpsCounter = document.getElementById("cheat-fps-counter");
      if (enable) {
        if (!fpsCounter) {
          fpsCounter = document.createElement("div");
          fpsCounter.id = "cheat-fps-counter";
          fpsCounter.style.position = "fixed";
          fpsCounter.style.top = "10px";
          fpsCounter.style.right = "10px";
          fpsCounter.style.backgroundColor = "rgba(0,0,0,0.8)";
          fpsCounter.style.color = "#00ff00";
          fpsCounter.style.fontFamily = "monospace";
          fpsCounter.style.padding = "5px 10px";
          fpsCounter.style.borderRadius = "4px";
          fpsCounter.style.zIndex = "9999";
          fpsCounter.innerText = "60 FPS";
          document.body.appendChild(fpsCounter);

          // Start the fake loop
          window.fpsInterval = setInterval(() => {
            const fps = Math.floor(Math.random() * (61 - 58) + 58);
            const el = document.getElementById("cheat-fps-counter");
            if (el) el.innerText = fps + " FPS";
          }, 500);
        }
      } else {
        if (fpsCounter) fpsCounter.remove();
        if (window.fpsInterval) clearInterval(window.fpsInterval);
      }
    },
  };

  // ==========================================
  //  3. INIT: RESTORE STATE ON LOAD
  // ==========================================
  // This runs on every page load to check if cheats should be active
  Object.keys(effects).forEach((key) => {
    if (isStateActive(key)) {
      effects[key](true); // Re-apply the effect
    }
  });

  // ==========================================
  //  4. INPUT LISTENER
  // ==========================================
  const keySequence = [];
  const konamiCode = [
    "arrowup",
    "arrowup",
    "arrowdown",
    "arrowdown",
    "arrowleft",
    "arrowright",
    "arrowleft",
    "arrowright",
    "b",
    "a",
  ];

  document.addEventListener("keydown", async function (e) {
    // A. Reset timer on every keypress
    clearTimeout(inputTimer);
    inputTimer = setTimeout(() => {
      keySequence.length = 0; // Clear buffer
      // console.log("Cheat Buffer Cleared");
    }, INPUT_TIMEOUT_MS);

    // B. Track keys
    keySequence.push(e.key.toLowerCase());
    if (keySequence.length > 20) {
      keySequence.shift();
    }
    const currentSequence = keySequence.join("");

    // --- CHEAT 1: KONAMI (Coupon) ---
    const konamiString = konamiCode.join("");
    if (currentSequence.endsWith(konamiString)) {
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

    // --- CHEAT 2: DEV MODE (Persistent) ---
    if (currentSequence.endsWith("devmode")) {
      const newState = !isStateActive("devmode");
      saveState("devmode", newState);
      effects.devmode(newState);
      notify(
        newState ? "👨‍💻 Developer Mode: ON" : "👨‍💻 Developer Mode: OFF",
        "success"
      );
      keySequence.length = 0;
    }

    // --- CHEAT 3: NIGHTMARE MODE (Persistent) ---
    if (currentSequence.endsWith("doom")) {
      const newState = !isStateActive("doom");
      saveState("doom", newState);
      effects.doom(newState);
      notify(
        newState ? "😈 NIGHTMARE DIFFICULTY STARTED" : "☀️ Nightmare Ended",
        newState ? "error" : "info"
      );
      keySequence.length = 0;
    }

    // --- CHEAT 4: BIG HEAD MODE (Persistent) ---
    if (currentSequence.endsWith("bighead")) {
      const newState = !isStateActive("bighead");
      saveState("bighead", newState);
      effects.bighead(newState);
      notify(
        newState ? "🏀 Big Head Mode: ON" : "🏀 Big Head Mode: OFF",
        "info"
      );
      keySequence.length = 0;
    }

    // --- CHEAT 5: FPS COUNTER (Persistent) ---
    if (currentSequence.endsWith("fps")) {
      const newState = !isStateActive("fps");
      saveState("fps", newState);
      effects.fps(newState);
      notify(
        newState ? "System Stats Visible" : "System Stats Hidden",
        "success"
      );
      keySequence.length = 0;
    }

    // --- CHEAT 6: INVENTORY (Redirect - No persistence needed) ---
    if (currentSequence.endsWith("loot")) {
      notify("💰 Opening Inventory...", "success");
      setTimeout(() => {
        window.location.href = "/cart/";
      }, 500);
      keySequence.length = 0;
    }

    // --- CHEAT 7: GOD MODE (Temporary - 2s Duration) ---
    if (currentSequence.endsWith("idkfa")) {
      document.body.style.transition = "transform 1s";
      document.body.style.transform = "rotate(180deg)";
      notify("⚡ GOD MODE: ACTIVATED", "warning");
      setTimeout(() => {
        document.body.style.transform = "none";
      }, 2000);
      keySequence.length = 0;
    }
  });
});
