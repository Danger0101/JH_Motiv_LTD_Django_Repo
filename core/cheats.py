# core/cheats.py

# We use Numeric IDs to obfuscate the meaning in the JavaScript.
# 100-199: Special/Hidden
# 200-299: Redirects
CHEAT_CODES = {
    # The Konami Code (Hash -> 101)
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
    # Redirects
    201: { # loot
        "action": "redirect",
        "url": "/cart/",
        "message": "💰 Opening Inventory...",
        "type": "success"
    },
    202: { # shop
        "action": "redirect",
        "url": "/shop/",
        "message": "🛡️ Visiting Armory...",
        "type": "info"
    },
    203: { # home
        "action": "redirect",
        "url": "/",
        "message": "🏠 Teleporting to Hub...",
        "type": "info"
    },
    204: { # login
        "action": "redirect",
        "url": "/accounts/login/",
        "message": "🔑 Access Protocol Initiated",
        "type": "warning"
    },
    205: { # team
        "action": "redirect",
        "url": "/about/",
        "message": "👥 Loading Guild Roster...",
        "type": "info"
    },
    206: { # ban
        "action": "redirect",
        "url": "/system/glitch/403/",
        "message": "⛔ ACCESS DENIED.",
        "type": "error"
    },
    207: { # lost
        "action": "redirect",
        "url": "/system/glitch/404/",
        "message": "🗺️ Signal Lost.",
        "type": "warning"
    },
    208: { # crash
        "action": "redirect",
        "url": "/system/glitch/500/",
        "message": "🔥 CRITICAL SYSTEM FAILURE",
        "type": "error"
    },
    # Visual Toggles (209-216)
    209: { # matrix
        "action": "toggle",
        "effect_id": "matrix"
    },
    210: { # devmode
        "action": "toggle",
        "effect_id": "devmode"
    },
    211: { # darkmode
        "action": "toggle",
        "effect_id": "darkmode"
    },
    212: { # cyber
        "action": "toggle",
        "effect_id": "cyber"
    },
    213: { # retro
        "action": "toggle",
        "effect_id": "retro"
    },
    214: { # doom
        "action": "toggle",
        "effect_id": "doom"
    },
    215: { # bighead
        "action": "toggle",
        "effect_id": "bighead"
    },
    216: { # fpsv -> fps
        "action": "toggle",
        "effect_id": "fps"
    },
    # Seasons (217-221)
    217: { # spring
        "action": "season",
        "value": "spring"
    },
    218: { # summer
        "action": "season",
        "value": "summer"
    },
    219: { # fall
        "action": "season",
        "value": "fall"
    },
    220: { # winter
        "action": "season",
        "value": "winter"
    },
    221: { # seasonpass
        "action": "season_reset"
    },
}