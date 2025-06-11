// Confetti Animation for Winner Celebration
class Confetti {
    constructor() {
        this.canvas = document.getElementById('confetti-canvas');
        if (!this.canvas) {
            this.canvas = document.createElement('canvas');
            this.canvas.id = 'confetti-canvas';
            this.canvas.style.position = 'fixed';
            this.canvas.style.top = '0';
            this.canvas.style.left = '0';
            this.canvas.style.width = '100%';
            this.canvas.style.height = '100%';
            this.canvas.style.pointerEvents = 'none';
            this.canvas.style.zIndex = '999';
            document.body.appendChild(this.canvas);
        }
        
        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.colors = [
            '#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#feca57',
            '#ff6b9d', '#c7ceea', '#8b9dc3', '#dda0dd', '#98d8c8',
            '#ffd700', '#ff4500', '#32cd32', '#ff69b4', '#00ced1'
        ];
        
        this.resize();
        this.animationId = null;
        
        // Bind resize event
        window.addEventListener('resize', () => this.resize());
    }
    
    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }
    
    createParticle() {
        return {
            x: Math.random() * this.canvas.width,
            y: -10,
            vx: (Math.random() - 0.5) * 6,
            vy: Math.random() * 3 + 2,
            rotation: Math.random() * 360,
            rotationSpeed: (Math.random() - 0.5) * 10,
            size: Math.random() * 8 + 4,
            color: this.colors[Math.floor(Math.random() * this.colors.length)],
            shape: Math.random() > 0.5 ? 'circle' : 'square',
            life: 1.0,
            decay: Math.random() * 0.01 + 0.005
        };
    }
    
    drawParticle(particle) {
        this.ctx.save();
        this.ctx.globalAlpha = particle.life;
        this.ctx.translate(particle.x, particle.y);
        this.ctx.rotate(particle.rotation * Math.PI / 180);
        this.ctx.fillStyle = particle.color;
        
        if (particle.shape === 'circle') {
            this.ctx.beginPath();
            this.ctx.arc(0, 0, particle.size, 0, Math.PI * 2);
            this.ctx.fill();
        } else {
            this.ctx.fillRect(-particle.size/2, -particle.size/2, particle.size, particle.size);
        }
        
        this.ctx.restore();
    }
    
    updateParticle(particle) {
        particle.x += particle.vx;
        particle.y += particle.vy;
        particle.vy += 0.1; // gravity
        particle.rotation += particle.rotationSpeed;
        particle.life -= particle.decay;
        
        // Add some wind effect
        particle.vx += (Math.random() - 0.5) * 0.1;
        
        return particle.life > 0 && particle.y < this.canvas.height + 50;
    }
    
    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Add new particles
        for (let i = 0; i < 5; i++) {
            this.particles.push(this.createParticle());
        }
        
        // Update and draw particles
        this.particles = this.particles.filter(particle => {
            const alive = this.updateParticle(particle);
            if (alive) {
                this.drawParticle(particle);
            }
            return alive;
        });
        
        // Continue animation if particles exist
        if (this.particles.length > 0 || this.shouldContinue) {
            this.animationId = requestAnimationFrame(() => this.animate());
        }
    }
    
    start(duration = 10000) {
        this.shouldContinue = true;
        this.animate();
        
        // Stop after specified duration
        setTimeout(() => {
            this.shouldContinue = false;
        }, duration);
        
        // Cleanup after particles fade out
        setTimeout(() => {
            this.stop();
        }, duration + 5000);
    }
    
    stop() {
        this.shouldContinue = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        this.particles = [];
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }
    
    burst(x, y, count = 30) {
        for (let i = 0; i < count; i++) {
            const particle = this.createParticle();
            particle.x = x;
            particle.y = y;
            particle.vx = (Math.random() - 0.5) * 15;
            particle.vy = Math.random() * -15 - 5;
            this.particles.push(particle);
        }
    }
}

// Global confetti instance
let confettiInstance = null;

function startConfetti(duration = 10000) {
    if (!confettiInstance) {
        confettiInstance = new Confetti();
    }
    confettiInstance.start(duration);
}

function stopConfetti() {
    if (confettiInstance) {
        confettiInstance.stop();
    }
}

function confettiBurst(x, y, count = 30) {
    if (!confettiInstance) {
        confettiInstance = new Confetti();
    }
    confettiInstance.burst(x, y, count);
    
    // Auto-animate for bursts
    if (!confettiInstance.animationId) {
        confettiInstance.shouldContinue = false;
        confettiInstance.animate();
    }
}

// Auto-start confetti on page load if winner is present
document.addEventListener('DOMContentLoaded', function() {
    const winnerElement = document.querySelector('.winner-celebration');
    if (winnerElement) {
        setTimeout(() => {
            startConfetti(15000); // 15 seconds of confetti
        }, 1000);
        
        // Add click event for extra bursts
        document.addEventListener('click', function(e) {
            confettiBurst(e.clientX, e.clientY, 20);
        });
    }
});

// Fireworks effect for special occasions
function createFireworks() {
    if (!confettiInstance) {
        confettiInstance = new Confetti();
    }
    
    const canvas = confettiInstance.canvas;
    const fireworkInterval = setInterval(() => {
        const x = Math.random() * canvas.width;
        const y = Math.random() * canvas.height * 0.6 + canvas.height * 0.1;
        confettiBurst(x, y, 50);
    }, 1000);
    
    // Stop fireworks after 10 seconds
    setTimeout(() => {
        clearInterval(fireworkInterval);
    }, 10000);
}

// Export functions for global use
window.startConfetti = startConfetti;
window.stopConfetti = stopConfetti;
window.confettiBurst = confettiBurst;
window.createFireworks = createFireworks;
