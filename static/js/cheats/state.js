// static/js/cheats/state.js

const STORAGE_KEY_PREFIX = "cheat_state_";

// --- HELPER: Get CSRF Token for Coupons ---
export function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        try {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        } catch (e) {
          cookieValue = cookie.substring(name.length + 1);
        }
        break;
      }
    }
  }
  return cookieValue;
}

// --- HELPER: Trigger Toast Notification ---
export function notify(msg, type = "info") {
  window.dispatchEvent(
    new CustomEvent("show-toast", {
      detail: { message: msg, type: type },
    })
  );
}

// --- HELPER: Save/Load State ---
export function saveState(cheatName, value) {
  try {
    if (value) {
      localStorage.setItem(STORAGE_KEY_PREFIX + cheatName, value);
    } else {
      localStorage.removeItem(STORAGE_KEY_PREFIX + cheatName);
    }
  } catch (e) {
    console.warn("LocalStorage access denied:", e);
  }
}

export function getState(cheatName) {
  try {
    return localStorage.getItem(STORAGE_KEY_PREFIX + cheatName);
  } catch (e) {
    return null;
  }
}

export function isStateActive(cheatName) {
  try {
    return localStorage.getItem(STORAGE_KEY_PREFIX + cheatName) === "true";
  } catch (e) {
    return false;
  }
}
