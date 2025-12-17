# core/cheats.py

# We use Numeric IDs to obfuscate the meaning in the JavaScript.
# 100-199: Special/Hidden
# 200-299: Redirects
CHEAT_CODES = {
    # --- REWARDS (100-199) ---
    101: {
        "action": "coupon",
        "message": "👾 KONAMI CODE ACTIVATED!",
        "type": "success"
    },
    # God Mode (Hash -> 102)
    102: {
        "action": "godmode",
        "message": "⚡ GOD MODE: ACTIVATED",
        "type": "warning"
    },
    # Neo (Hash -> 103)
    103: {
        "action": "toggle",
        "effect_id": "matrix",
        "message": "💊 WAKE UP, NEO...",
        "type": "success"
    },

    # --- VISUAL TOGGLES (200-299) ---
    # The JS will receive 'toggle' and the internal effect name
    201: { "action": "toggle", "effect_id": "matrix" },
    202: { "action": "toggle", "effect_id": "darkmode" },
    203: { "action": "toggle", "effect_id": "cyber" },
    204: { "action": "toggle", "effect_id": "retro" },
    205: { "action": "toggle", "effect_id": "devmode" },
    206: { "action": "toggle", "effect_id": "doom" },
    207: { "action": "toggle", "effect_id": "bighead" },
    208: { "action": "toggle", "effect_id": "fps" },

    # --- SEASONS (300-399) ---
    301: { "action": "season", "value": "spring" },
    302: { "action": "season", "value": "summer" },
    303: { "action": "season", "value": "fall" },
    304: { "action": "season", "value": "winter" },
    305: { "action": "season_reset" },
}