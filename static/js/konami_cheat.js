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
  function saveState(cheatName, value) {
    if (value) {
      localStorage.setItem(STORAGE_KEY_PREFIX + cheatName, value);
    } else {
      localStorage.removeItem(STORAGE_KEY_PREFIX + cheatName);
    }
  }

  function getState(cheatName) {
    return localStorage.getItem(STORAGE_KEY_PREFIX + cheatName);
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
        document.body.classList.remove("bg-gray-100", "text-gray-800");
        document.body.classList.add("font-mono", "text-green-500", "bg-black");
      } else {
        document.body.classList.remove(
          "font-mono",
          "text-green-500",
          "bg-black"
        );
        document.body.classList.add("bg-gray-100", "text-gray-800");
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
      // FIX 1: Only target images inside <main> to protect Navbar/Footer
      const images = document.querySelectorAll("main img");
      images.forEach((img) => {
        if (enable) {
          img.style.transition = "transform 0.3s ease";
          img.style.transform = "scale(1.5)";
          img.style.zIndex = "50";
          img.style.position = "relative";
          // FIX 2: Allow clicks to pass through image to buttons underneath
          img.style.pointerEvents = "none";
        } else {
          img.style.transform = "none";
          img.style.zIndex = "auto";
          img.style.position = "static";
          img.style.pointerEvents = "auto";
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
    matrix: (enable) => {
      let canvas = document.getElementById("matrix-canvas");
      if (enable) {
        if (!canvas) {
          canvas = document.createElement("canvas");
          canvas.id = "matrix-canvas";
          canvas.style.position = "fixed";
          canvas.style.top = "0";
          canvas.style.left = "0";
          canvas.style.width = "100vw";
          canvas.style.height = "100vh";
          canvas.style.zIndex = "9990";
          canvas.style.pointerEvents = "none";
          document.body.appendChild(canvas);

          const ctx = canvas.getContext("2d");
          const w = (canvas.width = window.innerWidth);
          const h = (canvas.height = window.innerHeight);
          const cols = Math.floor(w / 20) + 1;
          const ypos = Array(cols).fill(0);

          window.matrixInterval = setInterval(() => {
            ctx.fillStyle = "#0001";
            ctx.fillRect(0, 0, w, h);

            ctx.fillStyle = "#0f0";
            ctx.font = "15pt monospace";

            ypos.forEach((y, ind) => {
              const text = String.fromCharCode(Math.random() * 128);
              const x = ind * 20;
              ctx.fillText(text, x, y);
              if (y > 100 + Math.random() * 10000) ypos[ind] = 0;
              else ypos[ind] = y + 20;
            });
          }, 50);
        }
      } else {
        if (canvas) canvas.remove();
        if (window.matrixInterval) clearInterval(window.matrixInterval);
      }
    },
    // --- NEW: SEASON SELECTOR ---
    season: (seasonName) => {
      if (!seasonName) return; // Do nothing if reset/empty

      // Map inputs to filenames (handling the capitalization quirk in your files)
      const assetMap = {
        spring: {
          banner: "spring_banner.webp",
          footer: "spring_footer.webp",
          emoji: "🌸",
        },
        summer: {
          banner: "summer_banner.webp",
          footer: "summer_footer.webp",
          emoji: "☀️",
        },
        fall: {
          banner: "Fall_banner.webp",
          footer: "fall_footer.webp",
          emoji: "🍂",
        }, // Note 'Fall' vs 'fall'
        winter: {
          banner: "winter_banner.webp",
          footer: "winter_footer.webp",
          emoji: "❄️",
        },
      };

      const config = assetMap[seasonName];
      if (!config) return;

      // Target the elements by the IDs we just added
      const heroBg = document.getElementById("seasonal-hero-bg");
      const footerBg = document.getElementById("seasonal-footer-bg");

      if (heroBg) heroBg.src = `/static/images/${config.banner}`;
      if (footerBg) footerBg.src = `/static/images/${config.footer}`;
    },
  };

  // ==========================================
  //  3. INIT: RESTORE STATE ON LOAD
  // ==========================================
  // This runs on every page load to check if cheats should be active
  ["devmode", "doom", "bighead", "fps", "matrix"].forEach((key) => {
    if (isStateActive(key)) effects[key](true);
  });

  // Restore Season
  const savedSeason = getState("season");
  if (savedSeason) {
    effects.season(savedSeason);
  }

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
    clearTimeout(inputTimer);
    inputTimer = setTimeout(() => {
      keySequence.length = 0;
    }, INPUT_TIMEOUT_MS);

    keySequence.push(e.key.toLowerCase());
    if (keySequence.length > 20) keySequence.shift();
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

    // --- CHEAT 8: MATRIX MODE (Persistent) ---
    if (currentSequence.endsWith("matrix")) {
      const newState = !isStateActive("matrix");
      saveState("matrix", newState);
      effects.matrix(newState);
      notify(
        newState ? "💊 Matrix Mode: ON" : "💊 Matrix Mode: OFF",
        "success"
      );
      keySequence.length = 0;
    }

    // --- CHEAT 9: SEASON PASS (Persistent) ---
    const seasons = ["spring", "summer", "fall", "winter"];
    seasons.forEach((season) => {
      if (currentSequence.endsWith(season)) {
        saveState("season", season);
        effects.season(season);

        const emojis = {
          spring: "🌸",
          summer: "☀️",
          fall: "🍂",
          winter: "❄️",
        };
        notify(
          `${emojis[season]} Season Pass: ${season.toUpperCase()} Activated`,
          "info"
        );
        keySequence.length = 0;
      }
    });

    // Reset Season
    if (currentSequence.endsWith("seasonpass")) {
      saveState("season", null);
      notify("🔄 Time Sync: Returning to Server Time", "warning");
      setTimeout(() => location.reload(), 1000); // Reload to let Django fetch real date
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

    // ---------------------------------------------------------
    // 8. SIMULATE 403 (Access Denied) - Type: "ban"
    // ---------------------------------------------------------
    if (currentSequence.endsWith("ban")) {
      notify("⛔ ACCESS DENIED. TERMINATING SESSION...", "error");
      setTimeout(() => {
        window.location.href = "/system/glitch/403/";
      }, 1000);
      keySequence.length = 0;
    }

    // ---------------------------------------------------------
    // 9. SIMULATE 404 (Not Found) - Type: "lost"
    // ---------------------------------------------------------
    if (currentSequence.endsWith("lost")) {
      notify("🗺️ Signal Lost. Recalibrating...", "warning");
      setTimeout(() => {
        window.location.href = "/system/glitch/404/";
      }, 1000);
      keySequence.length = 0;
    }

    // ---------------------------------------------------------
    // 10. SIMULATE 500 (Server Crash) - Type: "crash"
    // ---------------------------------------------------------
    if (currentSequence.endsWith("crash")) {
      notify("🔥 CRITICAL SYSTEM FAILURE DETECTED", "error");
      // Add a slight shake effect before redirecting for drama
      document.body.style.animation =
        "shake 0.5s cubic-bezier(.36,.07,.19,.97) both";

      // Inject shake keyframes if not present
      if (!document.getElementById("shake-style")) {
        const style = document.createElement("style");
        style.id = "shake-style";
        style.innerHTML = `
                @keyframes shake { 
                    10%, 90% { transform: translate3d(-1px, 0, 0); }
                    20%, 80% { transform: translate3d(2px, 0, 0); }
                    30%, 50%, 70% { transform: translate3d(-4px, 0, 0); }
                    40%, 60% { transform: translate3d(4px, 0, 0); }
                }`;
        document.head.appendChild(style);
      }

      setTimeout(() => {
        window.location.href = "/system/glitch/500/";
      }, 1500);
      keySequence.length = 0;
    }
  });
});
