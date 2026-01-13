/* MATRIX RAIN ENGINE */
const canvas = document.getElementById('matrix-rain');
if (canvas) {
    const ctx = canvas.getContext('2d');
    
    // Config
    const sayings = ["WAKE UP", "NPC DETECTED", "ESCAPE", "PLAYER 1", "THE GLITCH", "SYSTEM FAILURE", "AUDIT STATS", "GRIND", "1", "0", "0", "1", "X", "$"];
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    
    let fontSize = 16, columns = 0, drops = [], columnState = [];
    
    // Resize Handler
    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        fontSize = Math.max(14, Math.floor(window.innerWidth / 60));
        columns = Math.ceil(canvas.width / fontSize);
        
        drops = [];
        columnState = [];
        for(let i=0; i<columns; i++) { 
            drops[i] = Math.random() * -100; 
            columnState[i] = null; 
        }
    }
    window.addEventListener('resize', resize);
    resize(); // Init
    
    // Draw Loop
    function draw() {
        // Trail Effect
        ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.font = fontSize + 'px "VT323", monospace';
    
        for(let i=0; i<columns; i++) {
            let text = '', isMsg = false;
            
            // Check if column is "Glitching" with a message
            if(columnState[i]) {
                text = columnState[i].phrase.charAt(columnState[i].index);
                isMsg = true;
                columnState[i].index++;
                // Reset word if done
                if(columnState[i].index >= columnState[i].phrase.length) {
                    columnState[i] = null;
                }
            } else {
                // Random Noise
                text = chars.charAt(Math.floor(Math.random()*chars.length));
                // 0.5% chance to start a word
                if(Math.random() > 0.995) { 
                    columnState[i] = { phrase: sayings[Math.floor(Math.random()*sayings.length)], index: 0 };
                }
            }
            
            // Color Logic
            if(isMsg) {
                ctx.fillStyle = '#FFF';
                ctx.shadowBlur = 5;
                ctx.shadowColor = '#00ff41';
            } else {
                ctx.fillStyle = '#0F0';
                ctx.shadowBlur = 0;
                ctx.globalAlpha = 0.5;
            }
            
            ctx.fillText(text, i*fontSize, drops[i]*fontSize);
            ctx.globalAlpha = 1.0;
            ctx.shadowBlur = 0;
    
            // Loop Drop
            if(drops[i]*fontSize > canvas.height && Math.random() > 0.975) {
                drops[i] = 0;
            }
            drops[i]++;
        }
        requestAnimationFrame(draw);
    }
    
    // Start Animation
    draw();
}

/* SYSTEM LOGIC (Clock & API) */
const clockEl = document.getElementById('clock');
if(clockEl) {
    setInterval(() => {
        clockEl.innerText = new Date().toLocaleTimeString();
    }, 1000);
}

// System Log Fetcher
window.initSystemLog = function(apiUrl) {
    function fetchLog() {
        fetch(apiUrl)
            .then(r => r.json())
            .then(data => {
                const log = document.getElementById('system-log');
                if(!log) return;

                const line = document.createElement('div');
                line.className = `${data.color} mb-1 opacity-0 transition-opacity duration-500`;
                line.innerHTML = `<span class="opacity-50">[${data.timestamp}]</span> ${data.message}`;
                
                // Add Glitch Effect to Purple "Both Pills" logs
                if(data.color.includes('purple')) {
                    line.classList.add('glitch-text');
                    line.setAttribute('data-text', data.message);
                }

                log.appendChild(line);
                requestAnimationFrame(() => line.classList.remove('opacity-0'));
                
                // Auto Scroll
                log.scrollTop = log.scrollHeight;
                
                // Cleanup
                if(log.children.length > 15) log.removeChild(log.firstChild);

                // Mobile Toast
                if(window.innerWidth < 768) {
                    const toast = document.getElementById('mobile-toast');
                    const msg = document.getElementById('mobile-msg');
                    if(toast && msg) {
                        msg.innerHTML = data.message;
                        toast.classList.remove('opacity-0');
                        setTimeout(() => toast.classList.add('opacity-0'), 3000);
                    }
                }
            })
            .catch(e => console.error(e));
            
        // Random Interval
        setTimeout(fetchLog, Math.random() * 4000 + 3000);
    }
    
    setTimeout(fetchLog, 2000);
};