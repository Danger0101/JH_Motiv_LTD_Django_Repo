// static/js/cheats/effects.js

export const effects = {
  // --- 1. THEMES ---

  // NEW: Clean Dark Mode
  darkmode: (enable) => {
    if (enable) {
      document.documentElement.classList.add("dark"); // If using Tailwind dark mode
      document.body.classList.add("bg-gray-900", "text-white");
      document.body.classList.remove("bg-gray-100", "text-gray-800");
    } else {
      document.documentElement.classList.remove("dark");
      document.body.classList.remove("bg-gray-900", "text-white");
      document.body.classList.add("bg-gray-100", "text-gray-800");
    }
  },

  // NEW: Cyberpunk / Vaporwave Mode
  cyber: (enable) => {
    if (enable) {
      document.body.classList.add("bg-slate-900", "text-pink-500", "font-mono");
      // Add a neon glow to all headings
      const style = document.createElement("style");
      style.id = "cyber-glow";
      style.innerHTML = `h1, h2, h3, a { text-shadow: 0 0 5px #d946ef, 0 0 10px #d946ef; }`;
      document.head.appendChild(style);
    } else {
      document.body.classList.remove(
        "bg-slate-900",
        "text-pink-500",
        "font-mono"
      );
      const style = document.getElementById("cyber-glow");
      if (style) style.remove();
    }
  },

  // Existing: Matrix Terminal
  devmode: (enable) => {
    if (enable) {
      document.body.classList.remove("bg-gray-100", "text-gray-800");
      document.body.classList.add("font-mono", "text-green-500", "bg-black");
    } else {
      document.body.classList.remove("font-mono", "text-green-500", "bg-black");
      document.body.classList.add("bg-gray-100", "text-gray-800");
    }
  },

  // Existing: Nightmare
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

  // --- 2. FUN MODS ---

  bighead: (enable) => {
    const images = document.querySelectorAll("main img");
    images.forEach((img) => {
      if (enable) {
        img.style.transition = "transform 0.3s ease";
        img.style.transform = "scale(1.5)";
        img.style.zIndex = "50";
        img.style.position = "relative";
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
        Object.assign(fpsCounter.style, {
          position: "fixed",
          top: "10px",
          right: "10px",
          backgroundColor: "rgba(0,0,0,0.8)",
          color: "#00ff00",
          fontFamily: "monospace",
          padding: "5px 10px",
          borderRadius: "4px",
          zIndex: "9999",
        });
        fpsCounter.innerText = "60 FPS";
        document.body.appendChild(fpsCounter);

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
        Object.assign(canvas.style, {
          position: "fixed",
          top: "0",
          left: "0",
          width: "100vw",
          height: "100vh",
          zIndex: "9990",
          pointerEvents: "none",
        });
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

  season: (seasonName) => {
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
