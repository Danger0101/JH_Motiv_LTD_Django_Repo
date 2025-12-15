document.addEventListener("alpine:init", () => {
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

  // --- EASTER EGG ENGINE ---
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
    // Keep track of the last 20 keys pressed
    keySequence.push(e.key.toLowerCase());
    if (keySequence.length > 20) {
      keySequence.shift();
    }
    const currentSequence = keySequence.join("");

    // 1. KONAMI CODE (Coupon Generator)
    // Check if the end of the sequence matches the Konami code
    const konamiString = konamiCode.join("");
    if (currentSequence.endsWith(konamiString)) {
      // Trigger generic success sound/visual immediately
      window.dispatchEvent(
        new CustomEvent("show-toast", {
          detail: {
            message: "👾 Input Accepted. Processing Cheat...",
            type: "info",
          },
        })
      );

      // Call Backend
      try {
        const response = await fetch("/api/cheat-code/", {
          method: "POST",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            "Content-Type": "application/json",
          },
        });
        const data = await response.json();

        // Dispatch result notification
        window.dispatchEvent(
          new CustomEvent("show-toast", {
            detail: {
              message: data.message,
              type:
                data.status === "error"
                  ? "error"
                  : data.status === "info"
                  ? "info"
                  : "success",
            },
          })
        );

        // If success, copy code to clipboard
        if (data.status === "success" && data.code) {
          navigator.clipboard.writeText(data.code);
        }
      } catch (error) {
        window.dispatchEvent(
          new CustomEvent("show-toast", {
            detail: {
              message: "🚫 System Error: Cheat Failed.",
              type: "error",
            },
          })
        );
      }

      // Reset sequence to prevent double firing
      keySequence.length = 0;
    }

    // 2. DEV MODE (Fun Visual)
    // Typing "devmode" toggles a green terminal style
    if (currentSequence.endsWith("devmode")) {
      document.body.classList.toggle("font-mono");
      document.body.classList.toggle("text-green-500");
      document.body.classList.toggle("bg-black");
      window.dispatchEvent(
        new CustomEvent("show-toast", {
          detail: { message: "👨‍💻 Developer Mode Toggled", type: "success" },
        })
      );
      keySequence.length = 0;
    }

    // 3. GOD MODE (idkfa)
    // Reference: Classic Doom cheat
    if (currentSequence.endsWith("idkfa")) {
      document.body.style.transition = "transform 1s";
      document.body.style.transform = "rotate(180deg)";
      window.dispatchEvent(
        new CustomEvent("show-toast", {
          detail: { message: "⚡ GOD MODE: ACTIVATED", type: "warning" },
        })
      );
      setTimeout(() => {
        document.body.style.transform = "none";
      }, 2000);
      keySequence.length = 0;
    }

    // 4. INVENTORY CHECK (loot)
    if (currentSequence.endsWith("loot")) {
      window.dispatchEvent(
        new CustomEvent("show-toast", {
          detail: { message: "💰 Opening Inventory...", type: "success" },
        })
      );
      setTimeout(() => {
        window.location.href = "/cart/";
      }, 500);
      keySequence.length = 0;
    }
  });
});
