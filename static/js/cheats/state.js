// static/js/cheats/state.js

const STORAGE_KEY_PREFIX = "cheat_state_";

export function getCookie(name) {
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

export function notify(msg, type = "info") {
    window.dispatchEvent(
        new CustomEvent("show-toast", {
            detail: { message: msg, type: type },
        })
    );
}

export function saveState(cheatName, value) {
    if (value) {
        localStorage.setItem(STORAGE_KEY_PREFIX + cheatName, value);
    } else {
        localStorage.removeItem(STORAGE_KEY_PREFIX + cheatName);
    }
}

export function getState(cheatName) {
    return localStorage.getItem(STORAGE_KEY_PREFIX + cheatName);
}

export function isStateActive(cheatName) {
    return localStorage.getItem(STORAGE_KEY_PREFIX + cheatName) === "true";
}