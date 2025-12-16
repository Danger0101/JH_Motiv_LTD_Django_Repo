# core/cheats.py

# We use Numeric IDs to obfuscate the meaning in the JavaScript.
# 100-199: Special/Hidden
# 200-299: Redirects
CHEAT_CODES = {
    # The Konami Code (Hash -> 101)
    101: {
        "action": "coupon",  # Frontend handles this action type
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
        "url": "/products/",
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
}