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
    if (enable) {
      clearThemes();
      document.documentElement.classList.add("matrix");
      // Optional: Add a canvas for falling code rain here
    } else {
      document.documentElement.classList.remove("matrix");
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
    const meter = document.getElementById("fps-counter");
    if (meter) meter.style.display = enable ? "block" : "none";
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
