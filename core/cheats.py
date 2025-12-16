# The keys are the secret sequences (must be lowercase)
# The values are the configuration returned to the frontend
CHEAT_CODES = {
    # The Konami Code
    "arrowuparrowuparrowdownarrowdownarrowleftarrowrightarrowleftarrowrightarrowba": {
        "action": "coupon",  # Frontend handles this action type
        "message": "👾 KONAMI CODE ACTIVATED!",
        "type": "success"
    },
    # God Mode (Doom)
    "idkfa": {
        "action": "godmode",
        "message": "⚡ GOD MODE: ACTIVATED",
        "type": "warning"
    },
    # You can move your redirects here too if you want them hidden
    "loot": {
        "action": "redirect",
        "url": "/cart/",
        "message": "💰 Opening Inventory...",
        "type": "success"
    },
    "shop": {
        "action": "redirect",
        "url": "/products/",
        "message": "🛡️ Visiting Armory...",
        "type": "info"
    },
    "home": {
        "action": "redirect",
        "url": "/",
        "message": "🏠 Teleporting to Hub...",
        "type": "info"
    },
    "login": {
        "action": "redirect",
        "url": "/accounts/login/",
        "message": "🔑 Access Protocol Initiated",
        "type": "warning"
    },
    "team": {
        "action": "redirect",
        "url": "/about/",
        "message": "👥 Loading Guild Roster...",
        "type": "info"
    },
    "ban": {
        "action": "redirect",
        "url": "/system/glitch/403/",
        "message": "⛔ ACCESS DENIED.",
        "type": "error"
    },
    "lost": {
        "action": "redirect",
        "url": "/system/glitch/404/",
        "message": "🗺️ Signal Lost.",
        "type": "warning"
    },
    "crash": {
        "action": "redirect",
        "url": "/system/glitch/500/",
        "message": "🔥 CRITICAL SYSTEM FAILURE",
        "type": "error"
    },
}