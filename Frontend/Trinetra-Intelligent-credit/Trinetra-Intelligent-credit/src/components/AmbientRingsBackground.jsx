import { useEffect, useRef } from 'react';

export default function AmbientRingsBackground() {
    const canvasRef = useRef(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        let animationFrameId;
        let time = 0;

        // Setup configuration for the premium light theme
        const rings = [
            { radiusOffset: 0.2, speed: 0.001, dashArray: [5, 15], width: 1, color: 'rgba(0, 0, 0, 0.03)' },
            { radiusOffset: 0.4, speed: -0.0008, dashArray: [20, 30], width: 1, color: 'rgba(0, 0, 0, 0.05)' },
            { radiusOffset: 0.6, speed: 0.0005, dashArray: [0, 0], width: 1.5, color: 'rgba(0, 0, 0, 0.02)' },
            { radiusOffset: 0.8, speed: -0.0012, dashArray: [2, 8], width: 1, color: 'rgba(0, 212, 170, 0.07)' }, // subtle teal hint
        ];

        const particles = Array.from({ length: 40 }).map(() => ({
            x: Math.random(), // percentage of width
            y: Math.random(), // percentage of height
            size: Math.random() * 2 + 0.5,
            speedX: (Math.random() - 0.5) * 0.2,
            speedY: (Math.random() - 0.5) * 0.2,
            opacity: Math.random() * 0.4 + 0.1
        }));

        const resize = () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        };

        const draw = () => {
            time += 1;
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            const centerX = canvas.width / 2;
            const centerY = canvas.height * 0.4; // Center rings slightly higher than middle
            const maxRadius = Math.max(canvas.width, canvas.height);

            // 1. Draw Volumetric Light Rays (Top-down gradients)
            const rayCount = 3;
            for (let i = 0; i < rayCount; i++) {
                const gradient = ctx.createLinearGradient(
                    centerX + Math.sin(time * 0.002 + i) * 200, 0,
                    centerX + Math.cos(time * 0.001 + i) * 300, canvas.height
                );

                // Pure elegant soft white/gray/teal light
                gradient.addColorStop(0, 'rgba(255, 255, 255, 0.8)');
                gradient.addColorStop(0.3, i === 1 ? 'rgba(204, 255, 0, 0.03)' : 'rgba(240, 245, 255, 0.4)'); // Hint of acid green
                gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');

                ctx.fillStyle = gradient;

                ctx.beginPath();
                ctx.moveTo(centerX - 400 + (i * 300), -100);
                ctx.lineTo(centerX + 200 + (i * 300), -100);
                // Swing the bottom of the rays slowly
                ctx.lineTo(centerX + 600 + Math.sin(time * 0.003 + i) * 400, canvas.height + 100);
                ctx.lineTo(centerX - 600 + Math.cos(time * 0.002 + i) * 400, canvas.height + 100);
                ctx.fill();
            }

            // 2. Draw Concentric Technical Rings
            rings.forEach((ring, index) => {
                ctx.beginPath();
                const radius = maxRadius * ring.radiusOffset;
                ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);

                ctx.strokeStyle = ring.color;
                ctx.lineWidth = ring.width;

                if (ring.dashArray[0] !== 0) {
                    ctx.setLineDash(ring.dashArray);
                    ctx.lineDashOffset = time * ring.speed * 100;
                } else {
                    ctx.setLineDash([]);
                }

                ctx.stroke();
            });
            ctx.setLineDash([]); // Reset dash for particles

            // 3. Draw Ambient Dust/Particles
            particles.forEach(p => {
                // Move particles
                p.x += (p.speedX / canvas.width) * 2;
                p.y += (p.speedY / canvas.height) * 2;
                const floatOffset = Math.sin(time * 0.02 + p.x * 10) * 0.5;

                // Wrap around edges
                if (p.x < 0) p.x = 1;
                if (p.x > 1) p.x = 0;
                if (p.y < 0) p.y = 1;
                if (p.y > 1) p.y = 0;

                const actualX = p.x * canvas.width;
                const actualY = (p.y * canvas.height) + floatOffset;

                ctx.beginPath();
                ctx.arc(actualX, actualY, p.size, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(0, 0, 0, ${p.opacity})`;
                ctx.fill();

                // Add tiny subtle glow to some particles
                if (p.size > 2) {
                    ctx.beginPath();
                    ctx.arc(actualX, actualY, p.size * 3, 0, Math.PI * 2);
                    ctx.fillStyle = `rgba(0, 212, 170, ${p.opacity * 0.1})`;
                    ctx.fill();
                }
            });

            // 4. Subtle overall paper/noise texture overlay (simulated)
            // Just a very faint gradient overlay to soften everything
            const overlay = ctx.createLinearGradient(0, 0, 0, canvas.height);
            overlay.addColorStop(0, 'rgba(255, 255, 255, 0)');
            overlay.addColorStop(1, 'rgba(250, 250, 252, 0.4)');
            ctx.fillStyle = overlay;
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            animationFrameId = requestAnimationFrame(draw);
        };

        resize();
        window.addEventListener('resize', resize);
        draw();

        return () => {
            cancelAnimationFrame(animationFrameId);
            window.removeEventListener('resize', resize);
        };
    }, []);

    return (
        <canvas
            ref={canvasRef}
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                pointerEvents: 'none',
                zIndex: 1, // Keep behind text, but above fixed blobs if any
                opacity: 0.8
            }}
        />
    );
}
