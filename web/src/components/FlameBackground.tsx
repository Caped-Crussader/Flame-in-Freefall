import { useEffect, useRef } from 'react';

interface Ember {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  hue: number;
  alpha: number;
  pulse: number;
}

export function FlameBackground() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let ctx: CanvasRenderingContext2D | null = null;
    try {
      ctx = canvas.getContext('2d');
    } catch {
      return;
    }
    if (!ctx) return;

    let animId = 0;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);
    let mouseX = 0.5;
    let mouseY = 0.5;

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };

    const handlePointer = (e: MouseEvent) => {
      mouseX = e.clientX / Math.max(1, width);
      mouseY = e.clientY / Math.max(1, height);
    };

    window.addEventListener('resize', handleResize);
    window.addEventListener('mousemove', handlePointer, { passive: true });

    const count = Math.min(90, Math.floor((width * height) / 17000));
    const embers: Ember[] = Array.from({ length: count }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.32,
      vy: -0.18 - Math.random() * 0.55,
      r: 0.9 + Math.random() * 2.5,
      hue: Math.random() > 0.42 ? 18 + Math.random() * 26 : 192 + Math.random() * 22,
      alpha: 0.18 + Math.random() * 0.52,
      pulse: Math.random() * Math.PI * 2,
    }));

    let t = 0;
    const render = () => {
      t += 0.014;
      ctx.clearRect(0, 0, width, height);

      // 1. Ambient Microgravity Spherical Flame Aura (Mouse-Reactive Parallax)
      const cx = width * (0.76 + (mouseX - 0.5) * 0.04);
      const cy = height * (0.3 + (mouseY - 0.5) * 0.04);
      const baseR = Math.min(width, height) * 0.25;
      const breathe = 1 + Math.sin(t * 1.4) * 0.045;

      const sphereGrad = ctx.createRadialGradient(cx, cy, 2, cx, cy, baseR * breathe);
      sphereGrad.addColorStop(0, 'rgba(224, 242, 254, 0.13)');
      sphereGrad.addColorStop(0.28, 'rgba(56, 189, 248, 0.09)');
      sphereGrad.addColorStop(0.58, 'rgba(255, 106, 26, 0.06)');
      sphereGrad.addColorStop(0.82, 'rgba(99, 102, 241, 0.03)');
      sphereGrad.addColorStop(1, 'rgba(5, 8, 22, 0)');

      ctx.fillStyle = sphereGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, baseR * breathe, 0, Math.PI * 2);
      ctx.fill();

      // Subtle concentric reaction-front rings
      ctx.save();
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.06)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, baseR * 0.56 * breathe, 0, Math.PI * 2);
      ctx.stroke();
      ctx.strokeStyle = 'rgba(255, 106, 26, 0.045)';
      ctx.beginPath();
      ctx.arc(cx, cy, baseR * 0.82 * (2 - breathe), 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      // 2. Bottom Thermal Diffusion Ribbons
      for (let w = 0; w < 3; w++) {
        ctx.beginPath();
        const baseY = height - 42 - w * 26;
        ctx.moveTo(0, height);
        for (let x = 0; x <= width; x += 28) {
          const y =
            baseY +
            Math.sin(x * 0.004 + t * (1.1 + w * 0.28) + w) * (16 + w * 7) +
            Math.cos(x * 0.009 - t * 0.75) * 9;
          ctx.lineTo(x, y);
        }
        ctx.lineTo(width, height);
        ctx.closePath();
        const waveGrad = ctx.createLinearGradient(0, baseY - 40, 0, height);
        if (w === 0) {
          waveGrad.addColorStop(0, 'rgba(255, 106, 26, 0.065)');
          waveGrad.addColorStop(1, 'rgba(255, 69, 0, 0.01)');
        } else if (w === 1) {
          waveGrad.addColorStop(0, 'rgba(56, 189, 248, 0.055)');
          waveGrad.addColorStop(1, 'rgba(37, 99, 235, 0.01)');
        } else {
          waveGrad.addColorStop(0, 'rgba(129, 140, 248, 0.04)');
          waveGrad.addColorStop(1, 'rgba(5, 8, 22, 0)');
        }
        ctx.fillStyle = waveGrad;
        ctx.fill();
      }

      // 3. Rising Embers & 0g Chemi-Ion Particles
      for (const e of embers) {
        e.pulse += 0.032;
        e.x += e.vx + Math.sin(t + e.pulse) * 0.16;
        e.y += e.vy;

        if (e.y < -12) {
          e.y = height + 12;
          e.x = Math.random() * width;
        }
        if (e.x < -12) e.x = width + 12;
        if (e.x > width + 12) e.x = -12;

        const a = e.alpha * (0.65 + 0.35 * Math.sin(e.pulse));
        const g = ctx.createRadialGradient(e.x, e.y, 0, e.x, e.y, e.r * 3.8);
        g.addColorStop(0, `hsla(${e.hue}, 100%, 76%, ${a})`);
        g.addColorStop(0.45, `hsla(${e.hue}, 95%, 56%, ${a * 0.45})`);
        g.addColorStop(1, `hsla(${e.hue}, 95%, 50%, 0)`);

        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(e.x, e.y, e.r * 3.8, 0, Math.PI * 2);
        ctx.fill();
      }

      animId = window.requestAnimationFrame(render);
    };

    animId = window.requestAnimationFrame(render);
    return () => {
      window.cancelAnimationFrame(animId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handlePointer);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position: 'fixed',
        inset: 0,
        width: '100vw',
        height: '100vh',
        pointerEvents: 'none',
        zIndex: 0,
        opacity: 0.9,
      }}
    />
  );
}
