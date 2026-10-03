/* Apple Siri Fluid Liquid Wave Orb Renderer (Canvas 2D HTML5) */
class SiriOrb {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.width = this.canvas.width = 400;
        this.height = this.canvas.height = 400;
        this.centerX = this.width / 2;
        this.centerY = this.height / 2;
        
        this.state = 'idle'; // 'idle', 'listening', 'thinking', 'speaking'
        this.time = 0;
        this.amplitude = 15;
        this.speed = 0.04;
        this.radius = 70;
        this.audioLevel = 0.2; // Driven by microphone or TTS audio
        
        // Colors for Siri Mesh Blend (Cyan, Magenta, Violet, Blue, Gold)
        this.colors = [
            { r: 0, g: 242, b: 254 },   // Cyan
            { r: 127, g: 0, b: 255 },   // Electric Purple
            { r: 255, g: 0, b: 127 },   // Magenta
            { r: 79, g: 172, b: 254 }   // Ocean Blue
        ];

        this.init();
    }

    setState(newState) {
        this.state = newState;
        if (newState === 'listening') {
            this.speed = 0.08;
            this.amplitude = 35;
        } else if (newState === 'thinking') {
            this.speed = 0.12;
            this.amplitude = 25;
        } else if (newState === 'speaking') {
            this.speed = 0.09;
            this.amplitude = 40;
        } else { // idle
            this.speed = 0.03;
            this.amplitude = 12;
        }
    }

    setAudioLevel(level) {
        this.audioLevel = Math.max(0.1, Math.min(level, 1.0));
    }

    init() {
        const render = () => {
            this.draw();
            this.time += this.speed;
            requestAnimationFrame(render);
        };
        render();
    }

    draw() {
        this.ctx.clearRect(0, 0, this.width, this.height);
        
        const currentAmp = this.amplitude * (0.8 + this.audioLevel * 1.5);
        const baseRadius = this.radius + (this.state === 'listening' ? 15 : 0);

        // Draw multiple overlapping glowing fluid blobs
        for (let blob = 0; blob < 4; blob++) {
            this.ctx.save();
            this.ctx.globalCompositeOperation = 'screen';
            
            const color = this.colors[blob % this.colors.length];
            const angleOffset = (blob * Math.PI) / 2 + this.time * 0.5;
            
            this.ctx.beginPath();
            const points = 32;
            
            for (let i = 0; i <= points; i++) {
                const angle = (i / points) * Math.PI * 2;
                
                // Sinusoidal noise wave displacement
                const wave1 = Math.sin(angle * 3 + this.time * 2 + angleOffset) * currentAmp * 0.5;
                const wave2 = Math.cos(angle * 5 - this.time * 3) * currentAmp * 0.3;
                const wave3 = Math.sin(angle * 2 + this.time * 4) * (currentAmp * 0.4);
                
                const r = baseRadius + wave1 + wave2 + wave3;
                const x = this.centerX + Math.cos(angle) * r;
                const y = this.centerY + Math.sin(angle) * r;
                
                if (i === 0) {
                    this.ctx.moveTo(x, y);
                } else {
                    this.ctx.lineTo(x, y);
                }
            }
            
            this.ctx.closePath();
            
            // Radial Glowing Siri Gradient
            const gradient = this.ctx.createRadialGradient(
                this.centerX + Math.cos(angleOffset) * 20,
                this.centerY + Math.sin(angleOffset) * 20,
                5,
                this.centerX,
                this.centerY,
                baseRadius + currentAmp + 20
            );
            
            gradient.addColorStop(0, `rgba(${color.r}, ${color.g}, ${color.b}, 0.95)`);
            gradient.addColorStop(0.5, `rgba(${color.r}, ${color.g}, ${color.b}, 0.5)`);
            gradient.addColorStop(1, `rgba(${color.r}, ${color.g}, ${color.b}, 0)`);
            
            this.ctx.fillStyle = gradient;
            this.ctx.fill();
            
            this.ctx.restore();
        }

        // Core White/Gold Ambient Inner Glow
        this.ctx.save();
        this.ctx.globalCompositeOperation = 'screen';
        this.ctx.beginPath();
        this.ctx.arc(this.centerX, this.centerY, baseRadius * 0.45, 0, Math.PI * 2);
        
        const coreGradient = this.ctx.createRadialGradient(
            this.centerX, this.centerY, 0,
            this.centerX, this.centerY, baseRadius * 0.5
        );
        coreGradient.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
        coreGradient.addColorStop(0.6, 'rgba(0, 242, 254, 0.4)');
        coreGradient.addColorStop(1, 'rgba(127, 0, 255, 0)');
        
        this.ctx.fillStyle = coreGradient;
        this.ctx.fill();
        this.ctx.restore();
    }
}

// Instantiate Orb on Load
let siriOrb;
window.addEventListener('DOMContentLoaded', () => {
    siriOrb = new SiriOrb('siriOrbCanvas');
});
