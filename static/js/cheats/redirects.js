// static/js/cheats/redirects.js
import { notify } from './state.js';

// --- CONFIGURATION: Add your redirects here ---
const pageMap = {
    // SHORTCUTS
    'loot':   { url: '/cart/',              msg: "💰 Opening Inventory...",       type: 'success' },
    'shop':   { url: '/products/',          msg: "🛡️ Visiting Armory...",         type: 'info' },
    'home':   { url: '/',                   msg: "🏠 Teleporting to Hub...",      type: 'info' },
    'login':  { url: '/accounts/login/',    msg: "🔑 Access Protocol Initiated",  type: 'warning' },
    'team':   { url: '/about/',             msg: "👥 Loading Guild Roster...",    type: 'info' },

    // SYSTEM GLITCHES (Easter Eggs)
    'ban':    { url: '/system/glitch/403/', msg: "⛔ ACCESS DENIED.",             type: 'error' },
    'lost':   { url: '/system/glitch/404/', msg: "🗺️ Signal Lost.",               type: 'warning' },
    'crash':  { url: '/system/glitch/500/', msg: "🔥 CRITICAL SYSTEM FAILURE",    type: 'error' }
};

export function checkRedirects(currentSequence) {
    // Iterate through our map to find a match
    for (const [keyword, config] of Object.entries(pageMap)) {
        if (currentSequence.endsWith(keyword)) {
            // 1. Notify User
            notify(config.msg, config.type);
            
            // 2. Wait 1 second (so they see the message), then redirect
            setTimeout(() => {
                window.location.href = config.url;
            }, 1000);
            
            return true; // Tell the engine we handled this action
        }
    }
    return false; // No match found
}