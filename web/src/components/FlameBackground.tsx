import { useEffect, useRef } from 'react';

interface Ember {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  alpha: number;
  phase: number;
  isCyan: boolean;
}

export function FlameBackground() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const prefersReduced =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const onResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', onResize);

    let mouseX = 0.5;
    let mouseY = 0.3;
    const onMouseMove = (e: MouseEvent) => {
      mouseX = e.clientX / Math.max(1, width);
      mouseY = e.clientY / Math.max(1, height);
    };
    window.addEventListener('mousemove', onMouseMove, { passive: true });

    const embers: Ember[] = Array.from({ length: 68 }, (_, i) => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.45,
      vy: -(0.45 + Math.random() * 1.35),
      r: 1.2 + Math.random() * 2.8,
      alpha: 0.2 + Math.random() * 0.65,
      phase: i * 0.7,
      isCyan: i % 4 === 0,
    }));

    let animId = 0;
    let t = 0;

    const render = () => {
      t += 0.018;
      ctx.clearRect(0, 0, width, height);

      // 1. Ambient 0g Spherical Blue Microgravity Diffusion Flame Orb (Upper-Right)
      const orbX = width * 0.84 + (mouseX - 0.5) * -36;
      const orbY = height * 0.22 + (mouseY - 0.5) * -28 + Math.sin(t * 0.7) * 10;
      const orbRadius = Math.min(width, height) * 0.21 * (1 + 0.04 * Math.sin(t * 1.3));

      const orbGrad = ctx.createRadialGradient(orbX, orbY, 2, orbX, orbY, orbRadius);
      orbGrad.addColorStop(0.0, 'rgba(255, 255, 255, 0.42)');
      orbGrad.addColorStop(0.22, 'rgba(56, 189, 248, 0.30)');
      orbGrad.addColorStop(0.52, 'rgba(14, 165, 233, 0.14)');
      orbGrad.addColorStop(0.76, 'rgba(249, 115, 22, 0.06)');
      orbGrad.addColorStop(1.0, 'rgba(0, 0, 0, 0)');

      ctx.fillStyle = orbGrad;
      ctx.beginPath();
      ctx.arc(orbX, orbY, orbRadius, 0, Math.PI * 2);
      ctx.fill();

      // 2. Layered Bottom Buoyant Flame Plumes along the Horizon
      const layers = [
        { amp: 34, freq: 0.0045, speed: 1.1, baseH: 185, cTop: 'rgba(220, 38, 38, 0)', cMid: 'rgba(234, 88, 12, 0.16)', cBot: 'rgba(185, 28, 28, 0.34)' },
        { amp: 28, freq: 0.0068, speed: -1.45, baseH: 135, cTop: 'rgba(249, 115, 22, 0)', cMid: 'rgba(251, 146, 60, 0.18)', cBot: 'rgba(234, 88, 12, 0.36)' },
        { amp: 20, freq: 0.0095, speed: 1.9, baseH: 92, cTop: 'rgba(250, 204, 21, 0)', cMid: 'rgba(253, 224, 71, 0.14)', cBot: 'rgba(245, 158, 11, 0.28)' },
      ];

      for (const layer of layers) {
        const grad = ctx.createLinearGradient(0, height - layer.baseH - 60, 0, height);
        grad.addColorStop(0, layer.cTop);
        grad.addColorStop(0.55, layer.cMid);
        grad.addColorStop(1, layer.cBot);

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(0, height);
        for (let x = 0; x <= width; x += 18) {
          const wave1 = Math.sin(x * layer.freq + t * layer.speed) * layer.amp;
          const wave2 = Math.cos(x * layer.freq * 1.8 - t * layer.speed * 1.3) * (layer.amp * 0.45);
          const y = height - layer.baseH + wave1 + wave2;
          ctx.lineTo(x, y);
        }
        ctx.lineTo(width, height);
        ctx.closePath();
        ctx.fill();
      }

      // 3. Rising Glowing Ember & Chemi-Ion Particles
      for (const p of embers) {
        if (!prefersReduced) {
          p.y += p.vy;
          p.x += p.vx + Math.sin(t * 1.5 + p.phase) * 0.35;
          if (p.y < -20) {
            p.y = height + 10;
            p.x = Math.random() * width;
          }
          if (p.x < -20) p.x = width + 10;
          if (p.x > width + 20) p.x = -10;
        }

        const flicker = 0.65 + 0.35 * Math.sin(t * 3.2 + p.phase);
        const a = p.alpha * flicker;
        const pGrad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 3.2);
        if (p.isCyan) {
          pGrad.addColorStop(0, `rgba(224, 242, 254, ${a})`);
          pGrad.addColorStop(0.45, `rgba(56, 189, 248, ${a * 0.65})`);
          pGrad.addColorStop(1, 'rgba(56, 189, 248, 0)');
        } else {
          pGrad.addColorStop(0, `rgba(255, 247, 237, ${a})`);
          pGrad.addColorStop(0.4, `rgba(251, 146, 60, ${a * 0.75})`);
          pGrad.addColorStop(1, 'rgba(234, 88, 12, 0)');
        }
        ctx.fillStyle = pGrad;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * 3.2, 0, Math.PI * 2);
        ctx.fill();
      }

      if (!prefersReduced) {
        animId = window.requestAnimationFrame(render);
      }
    };

    render();

    return () => {
      window.cancelAnimationFrame(animId);
      window.removeEventListener('resize', onResize);
      window.removeEventListener('mousemove', onMouseMove);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="flame-canvas-bg"
      aria-hidden="true"
      style={{
        position: 'fixed',
        inset: 0,
        width: '100vw',
        height: '100vh',
        pointerEvents: 'none',
        zIndex: 0,
      }}
    />
  );
}
