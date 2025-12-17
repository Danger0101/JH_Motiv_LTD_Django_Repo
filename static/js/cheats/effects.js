// static/js/cheats/effects.js

// Helper to clear all theme classes before applying a new one
const clearThemes = () => {
  document.documentElement.classList.remove(
    "matrix",
    "retro",
    "cyber",
    "doom",
    "bighead",
    "dark",
    "devmode"
  );
  // Also clear body classes if any were added manually
  document.body.classList.remove("matrix-active");
};

export const effects = {
  // --- THEMES ---

  darkmode: (enable) => {
    // Standard Tailwind Dark Mode
    document.documentElement.classList.toggle("dark", enable);
  },

  matrix: (enable) => {
    let canvas = document.getElementById("matrix-canvas");
    if (enable) {
      clearThemes();
      document.documentElement.classList.add("matrix");

      if (!canvas) {
        canvas = document.createElement("canvas");
        canvas.id = "matrix-canvas";
        Object.assign(canvas.style, {
          position: "fixed",
          top: "0",
          left: "0",
          width: "100vw",
          height: "100vh",
          zIndex: "50", // Bring to front so it's visible over opaque backgrounds
          pointerEvents: "none",
          mixBlendMode: "screen", // Ensures the black fade background doesn't darken the page
          opacity: "0.8",
        });
        document.body.appendChild(canvas);

        // Simple Matrix Rain Logic
        const ctx = canvas.getContext("2d");
        const w = (canvas.width = window.innerWidth);
        const h = (canvas.height = window.innerHeight);
        const cols = Math.floor(w / 20) + 1;
        const ypos = Array(cols).fill(0);

        window.matrixInterval = setInterval(() => {
          ctx.fillStyle = "#0001"; // Fade effect
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
      document.documentElement.classList.remove("matrix");
      if (canvas) canvas.remove();
      if (window.matrixInterval) clearInterval(window.matrixInterval);
    }
  },

  cyber: (enable) => {
    if (enable) {
      clearThemes();
      document.documentElement.classList.add("cyber");
    } else {
      document.documentElement.classList.remove("cyber");
    }
  },

  retro: (enable) => {
    if (enable) {
      clearThemes();
      document.documentElement.classList.add("retro");
    } else {
      document.documentElement.classList.remove("retro");
    }
  },

  doom: (enable) => {
    if (enable) {
      clearThemes(); // Doom overrides everything
      document.documentElement.classList.add("doom");
      // Optional: Play sound or add screen shake
      document.body.style.animation =
        "shake 0.5s cubic-bezier(.36,.07,.19,.97) both";
    } else {
      document.documentElement.classList.remove("doom");
      document.body.style.animation = "";
    }
  },

  devmode: (enable) => {
    if (enable) {
      clearThemes();
      document.documentElement.classList.add("devmode");
    } else {
      document.documentElement.classList.remove("devmode");
    }
  },

  // --- VISUAL TWEAKS ---

  godmode: () => {
    document.body.style.transition = "transform 1s";
    document.body.style.transform = "rotate(180deg)";
    setTimeout(() => {
      document.body.style.transform = "none";
    }, 2000);
  },

  bighead: (enable) => {
    // This needs a global style injection for images
    if (enable) {
      document.documentElement.classList.add("bighead");
      const style = document.createElement("style");
      style.id = "bighead-style";
      style.textContent = `img { transform: scale(1.5) !important; transition: transform 0.5s; }`;
      document.head.appendChild(style);
    } else {
      document.documentElement.classList.remove("bighead");
      const style = document.getElementById("bighead-style");
      if (style) style.remove();
    }
  },

  fps: (enable) => {
    // Toggle FPS counter visibility
    let meter = document.getElementById("fps-counter");
    if (enable) {
      if (!meter) {
        meter = document.createElement("div");
        meter.id = "fps-counter";
        // Basic styling (position handled by engine.js)
        meter.style.color = "#00ff00";
        meter.style.fontFamily = "monospace";
        meter.style.fontWeight = "bold";
        meter.style.zIndex = "9999";
        meter.innerText = "60 FPS";
        document.body.appendChild(meter);

        // Simple Fake FPS for effect (or replace with real requestAnimationFrame)
        window.fpsInterval = setInterval(() => {
          meter.innerText = Math.floor(Math.random() * (61 - 58) + 58) + " FPS";
        }, 500);
      }
      meter.style.display = "block";
    } else {
      if (meter) meter.style.display = "none";
      if (window.fpsInterval) clearInterval(window.fpsInterval);
    }
  },

  // --- SEASONAL ---
  season: (seasonName) => {
    // Remove old seasons
    document.documentElement.classList.remove(
      "spring",
      "summer",
      "fall",
      "winter"
    );
    if (seasonName) {
      document.documentElement.classList.add(seasonName);
    }

    // Legacy asset swapping logic (optional, kept for compatibility if needed)
    if (!seasonName) return;
    const assetMap = {
      spring: { banner: "spring_banner.webp", footer: "spring_footer.webp" },
      summer: { banner: "summer_banner.webp", footer: "summer_footer.webp" },
      fall: { banner: "Fall_banner.webp", footer: "fall_footer.webp" },
      winter: { banner: "winter_banner.webp", footer: "winter_footer.webp" },
    };

    const config = assetMap[seasonName];
    if (!config) return;

    const heroBg = document.getElementById("seasonal-hero-bg");
    const footerBg = document.getElementById("seasonal-footer-bg");
    if (heroBg) heroBg.src = `/static/images/${config.banner}`;
    if (footerBg) footerBg.src = `/static/images/${config.footer}`;
  },

  confetti: () => {
    const canvas = document.createElement("canvas");
    Object.assign(canvas.style, {
      position: "fixed",
      top: "0",
      left: "0",
      width: "100%",
      height: "100%",
      pointerEvents: "none",
      zIndex: "10001",
    });
    document.body.appendChild(canvas);

    const ctx = canvas.getContext("2d");
    const w = (canvas.width = window.innerWidth);
    const h = (canvas.height = window.innerHeight);

    const particles = Array.from({ length: 100 }).map(() => ({
      x: w / 2,
      y: h / 2,
      vx: (Math.random() - 0.5) * 20,
      vy: (Math.random() - 0.5) * 20 - 5,
      color: `hsl(${Math.random() * 360}, 100%, 50%)`,
      life: 1.0,
    }));

    function animate() {
      ctx.clearRect(0, 0, w, h);
      let active = false;
      particles.forEach((p) => {
        if (p.life > 0) {
          active = true;
          p.x += p.vx;
          p.y += p.vy;
          p.vy += 0.5;
          p.life -= 0.02;
          ctx.globalAlpha = p.life;
          ctx.fillStyle = p.color;
          ctx.fillRect(p.x, p.y, 8, 8);
        }
      });
      if (active) requestAnimationFrame(animate);
      else canvas.remove();
    }
    animate();
  },
};
