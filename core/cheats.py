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
    }
}