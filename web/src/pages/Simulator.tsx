import { useEffect, useRef, useState } from 'react';
import {
  simulateRisk,
  type FlammabilityEnvelope,
  type RiskSimulationResult,
} from '../api/client';

const POPULAR_MATERIALS = [
  'SIBAL (Cotton-Fiberglass Blend)',
  'PMMA (Acrylic)',
  'Nomex (Aramid)',
  'Velcro Hook-and-Loop (Nylon)',
  'Cotton Fabric',
  'Polyurethane Foam (Open-Cell)',
  'Methanol',
  'n-Heptane',
  'Ethanol',
  'Cellulose Tissue / Kimwipe',
];

function riskToRgba(score: number): string {
  const s = Math.max(0, Math.min(1, score));
  if (s < 0.35) {
    const t = s / 0.35;
    const r = Math.round(16 + t * 218);
    const g = Math.round(115 + t * 64);
    const b = Math.round(80 - t * 60);
    return `rgba(${r}, ${g}, ${b}, 0.78)`;
  }
  if (s < 0.7) {
    const t = (s - 0.35) / 0.35;
    const r = Math.round(234 + t * 15);
    const g = Math.round(179 - t * 85);
    const b = Math.round(20 - t * 10);
    return `rgba(${r}, ${g}, ${b}, 0.82)`;
  }
  const t = (s - 0.7) / 0.3;
  const r = Math.round(249 - t * 30);
  const g = Math.round(94 - t * 68);
  const b = Math.round(10 + t * 20);
  return `rgba(${r}, ${g}, ${b}, 0.88)`;
}

function MocEnvelopeCanvas({
  envelope,
  oxygen,
  pressure,
  onSelectPoint,
}: {
  envelope: FlammabilityEnvelope;
  oxygen: number;
  pressure: number;
  onSelectPoint: (pKpa: number, o2Pct: number) => void;
}) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const padL = 52;
    const padR = 20;
    const padT = 26;
    const padB = 42;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;

    const pGrid = envelope.pressure_grid_kpa;
    const o2Grid = envelope.oxygen_grid_pct;
    const zMat = envelope.risk_matrix;
    if (!pGrid.length || !o2Grid.length || !zMat.length) return;

    const pMin = pGrid[0];
    const pMax = pGrid[pGrid.length - 1];
    const o2Min = o2Grid[0];
    const o2Max = o2Grid[o2Grid.length - 1];

    const toX = (p: number) => padL + ((p - pMin) / (pMax - pMin)) * plotW;
    const toY = (o2: number) => padT + plotH - ((o2 - o2Min) / (o2Max - o2Min)) * plotH;

    ctx.clearRect(0, 0, W, H);

    // 1. Draw 19x19 risk contour cells
    const cellW = plotW / Math.max(1, pGrid.length - 1);
    const cellH = plotH / Math.max(1, o2Grid.length - 1);
    for (let r = 0; r < o2Grid.length; r++) {
      for (let c = 0; c < pGrid.length; c++) {
        const val = zMat[r]?.[c] ?? 0;
        const cx = toX(pGrid[c]) - cellW / 2;
        const cy = toY(o2Grid[r]) - cellH / 2;
        ctx.fillStyle = riskToRgba(val);
        ctx.fillRect(
          Math.max(padL, cx),
          Math.max(padT, cy),
          Math.min(cellW + 1, padL + plotW - Math.max(padL, cx)),
          Math.min(cellH + 1, padT + plotH - Math.max(padT, cy)),
        );
      }
    }

    // 2. Draw 1g NASA-STD-6001 MOC dashed curve
    ctx.save();
    ctx.strokeStyle = '#4ade80';
    ctx.lineWidth = 2.5;
    ctx.setLineDash([6, 5]);
    ctx.beginPath();
    envelope.moc_1g_std6001_o2_pct.forEach((mocVal, idx) => {
      const x = toX(pGrid[idx]);
      const y = toY(Math.min(o2Max, Math.max(o2Min, mocVal)));
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.restore();

    // 3. Draw 0g Microgravity MOC solid cyan boundary curve
    ctx.save();
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 3.2;
    ctx.shadowColor = '#38bdf8';
    ctx.shadowBlur = 8;
    ctx.beginPath();
    envelope.moc_0g_o2_pct.forEach((mocVal, idx) => {
      const x = toX(pGrid[idx]);
      const y = toY(Math.min(o2Max, Math.max(o2Min, mocVal)));
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.restore();

    // 4. Overlay historical experiment points
    for (const pt of envelope.material_experiments) {
      if (pt.pressure_kpa < pMin || pt.pressure_kpa > pMax) continue;
      if (pt.oxygen_pct < o2Min || pt.oxygen_pct > o2Max) continue;
      const x = toX(pt.pressure_kpa);
      const y = toY(pt.oxygen_pct);
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = pt.sustained ? '#ef4444' : '#22c55e';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // 5. Reference Spacecraft Regimes
    const refs = [
      { label: 'ISS (21%)', p: 101.3, o2: 21.0 },
      { label: 'EVA (26.5%)', p: 70.3, o2: 26.5 },
      { label: 'Artemis SEA (34%)', p: 56.5, o2: 34.0 },
    ];
    ctx.font = '600 11px Inter, sans-serif';
    for (const rm of refs) {
      const rx = toX(rm.p);
      const ry = toY(rm.o2);
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(rx, ry, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#0f172a';
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.fillText(rm.label, rx - 28, ry - 9);
    }

    // 6. Selected User Operating Point
    const ux = toX(Math.min(pMax, Math.max(pMin, pressure)));
    const uy = toY(Math.min(o2Max, Math.max(o2Min, oxygen)));
    ctx.save();
    ctx.fillStyle = '#facc15';
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(ux, uy, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#fef08a';
    ctx.font = '700 11px JetBrains Mono, monospace';
    ctx.fillText(`Selected (${oxygen.toFixed(1)}% O₂, ${pressure.toFixed(1)} kPa)`, Math.min(W - 190, Math.max(padL + 6, ux - 60)), uy + 18);
    ctx.restore();

    // 7. Axes labels & ticks
    ctx.strokeStyle = 'rgba(226, 232, 240, 0.45)';
    ctx.lineWidth = 1;
    ctx.strokeRect(padL, padT, plotW, plotH);

    ctx.fillStyle = '#cbd5e1';
    ctx.font = '11px JetBrains Mono, monospace';
    for (const pTick of [30, 50, 70, 90, 110]) {
      const tx = toX(pTick);
      ctx.fillText(`${pTick}`, tx - 10, H - 22);
    }
    for (const o2Tick of [15, 25, 35, 45]) {
      const ty = toY(o2Tick);
      ctx.fillText(`${o2Tick}%`, 12, ty + 4);
    }
    ctx.fillText('Cabin Pressure (kPa) — Click map to set operating point', padL + 55, H - 6);
  }, [envelope, oxygen, pressure]);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = ref.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const cx = (e.clientX - rect.left) * scaleX;
    const cy = (e.clientY - rect.top) * scaleY;

    const padL = 52;
    const padR = 20;
    const padT = 26;
    const padB = 42;
    const plotW = canvas.width - padL - padR;
    const plotH = canvas.height - padT - padB;
    if (cx < padL || cx > padL + plotW || cy < padT || cy > padT + plotH) return;

    const pGrid = envelope.pressure_grid_kpa;
    const o2Grid = envelope.oxygen_grid_pct;
    const pMin = pGrid[0];
    const pMax = pGrid[pGrid.length - 1];
    const o2Min = o2Grid[0];
    const o2Max = o2Grid[o2Grid.length - 1];

    const newP = Math.round((pMin + ((cx - padL) / plotW) * (pMax - pMin)) * 2) / 2;
    const newO2 = Math.round((o2Min + (1 - (cy - padT) / plotH) * (o2Max - o2Min)) * 2) / 2;
    onSelectPoint(newP, newO2);
  };

  return (
    <canvas
      ref={ref}
      width={520}
      height={340}
      onClick={handleClick}
      style={{ width: '100%', height: 'auto', borderRadius: 12, cursor: 'crosshair' }}
    />
  );
}

function AirflowQuenchCanvas({
  envelope,
  oxygen,
  airflow,
  onSelectFlow,
}: {
  envelope: FlammabilityEnvelope;
  oxygen: number;
  airflow: number;
  onSelectFlow: (flowCms: number, o2Pct: number) => void;
}) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const padL = 52;
    const padR = 20;
    const padT = 26;
    const padB = 42;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;

    const fGrid = envelope.airflow_grid_cms;
    const o2Grid = envelope.oxygen_grid_pct;
    const zMat = envelope.airflow_risk_matrix;
    if (!fGrid.length || !o2Grid.length || !zMat.length) return;

    const fMin = fGrid[0];
    const fMax = fGrid[fGrid.length - 1];
    const o2Min = o2Grid[0];
    const o2Max = o2Grid[o2Grid.length - 1];

    const toX = (f: number) => padL + ((f - fMin) / (fMax - fMin)) * plotW;
    const toY = (o2: number) => padT + plotH - ((o2 - o2Min) / (o2Max - o2Min)) * plotH;

    ctx.clearRect(0, 0, W, H);

    const cellW = plotW / Math.max(1, fGrid.length - 1);
    const cellH = plotH / Math.max(1, o2Grid.length - 1);
    for (let r = 0; r < o2Grid.length; r++) {
      for (let c = 0; c < fGrid.length; c++) {
        const val = zMat[r]?.[c] ?? 0;
        const cx = toX(fGrid[c]) - cellW / 2;
        const cy = toY(o2Grid[r]) - cellH / 2;
        ctx.fillStyle = riskToRgba(val);
        ctx.fillRect(
          Math.max(padL, cx),
          Math.max(padT, cy),
          Math.min(cellW + 1, padL + plotW - Math.max(padL, cx)),
          Math.min(cellH + 1, padT + plotH - Math.max(padT, cy)),
        );
      }
    }

    // Quenching (<1.5 cm/s) and Blowoff (>32 cm/s) lines
    ctx.save();
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 4]);
    const qX = toX(1.5);
    ctx.beginPath();
    ctx.moveTo(qX, padT);
    ctx.lineTo(qX, padT + plotH);
    ctx.stroke();

    ctx.strokeStyle = '#c084fc';
    const bX = toX(32.0);
    ctx.beginPath();
    ctx.moveTo(bX, padT);
    ctx.lineTo(bX, padT + plotH);
    ctx.stroke();
    ctx.restore();

    ctx.fillStyle = '#e0f2fe';
    ctx.font = '600 10px Inter, sans-serif';
    ctx.fillText('Quench (<1.5 cm/s)', qX + 4, padT + 14);
    ctx.fillText('Blowoff (>32 cm/s)', bX - 96, padT + 14);

    // Selected operating point
    const ux = toX(Math.min(fMax, Math.max(fMin, airflow)));
    const uy = toY(Math.min(o2Max, Math.max(o2Min, oxygen)));
    ctx.fillStyle = '#facc15';
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(ux, uy, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.strokeStyle = 'rgba(226, 232, 240, 0.45)';
    ctx.lineWidth = 1;
    ctx.strokeRect(padL, padT, plotW, plotH);

    ctx.fillStyle = '#cbd5e1';
    ctx.font = '11px JetBrains Mono, monospace';
    for (const fTick of [0, 10, 20, 30, 40, 50]) {
      const tx = toX(fTick);
      ctx.fillText(`${fTick}`, tx - 8, H - 22);
    }
    for (const o2Tick of [15, 25, 35, 45]) {
      const ty = toY(o2Tick);
      ctx.fillText(`${o2Tick}%`, 12, ty + 4);
    }
    ctx.fillText('HVAC Airflow Velocity (cm/s) — Click map to adjust flow', padL + 45, H - 6);
  }, [envelope, oxygen, airflow]);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = ref.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const cx = (e.clientX - rect.left) * scaleX;
    const cy = (e.clientY - rect.top) * scaleY;

    const padL = 52;
    const padR = 20;
    const padT = 26;
    const padB = 42;
    const plotW = canvas.width - padL - padR;
    const plotH = canvas.height - padT - padB;
    if (cx < padL || cx > padL + plotW || cy < padT || cy > padT + plotH) return;

    const fGrid = envelope.airflow_grid_cms;
    const o2Grid = envelope.oxygen_grid_pct;
    const fMin = fGrid[0];
    const fMax = fGrid[fGrid.length - 1];
    const o2Min = o2Grid[0];
    const o2Max = o2Grid[o2Grid.length - 1];

    const newFlow = Math.round((fMin + ((cx - padL) / plotW) * (fMax - fMin)) * 2) / 2;
    const newO2 = Math.round((o2Min + (1 - (cy - padT) / plotH) * (o2Max - o2Min)) * 2) / 2;
    onSelectFlow(newFlow, newO2);
  };

  return (
    <canvas
      ref={ref}
      width={520}
      height={340}
      onClick={handleClick}
      style={{ width: '100%', height: 'auto', borderRadius: 12, cursor: 'crosshair' }}
    />
  );
}

export function Simulator() {
  const [oxygen, setOxygen] = useState<number>(34.0);
  const [pressure, setPressure] = useState<number>(56.5);
  const [airflow, setAirflow] = useState<number>(10.0);
  const [material, setMaterial] = useState<string>(POPULAR_MATERIALS[0]);
  const [res, setRes] = useState<RiskSimulationResult | null>(null);

  useEffect(() => {
    const ctl = new AbortController();
    simulateRisk(
      {
        oxygen_pct: oxygen,
        pressure_kpa: pressure,
        airflow_velocity_cms: airflow,
        fuel_material: material,
      },
      ctl.signal,
    )
      .then(setRes)
      .catch(() => undefined);
    return () => ctl.abort();
  }, [oxygen, pressure, airflow, material]);

  const applyPreset = (o2: number, kpa: number, flow: number) => {
    setOxygen(o2);
    setPressure(kpa);
    setAirflow(flow);
  };

  return (
    <main className="nx-page" id="main">
      <header className="nx-head nx-rise">
        <p className="nx-eyebrow">Random Forest + Microgravity Physics Model · 840 Physical Tests</p>
        <h1 className="sm">Spacecraft & Lunar Habitat Flammability Simulator</h1>
        <p className="nx-lead">
          Simulate cabin atmosphere fire risk, inspect the 2D Minimum Oxygen Concentration (MOC) boundary curve (0g vs.
          1g NASA-STD-6001), and retrieve the 5 closest real NASA/JAXA flight experiments.
        </p>
      </header>

      <div className="nx-actions" style={{ marginBottom: 20 }}>
        <button type="button" className="nx-btn ghost" onClick={() => applyPreset(21.0, 101.3, 8.0)}>
          🛰️ ISS Standard (21% O₂, 101.3 kPa)
        </button>
        <button type="button" className="nx-btn" onClick={() => applyPreset(34.0, 56.5, 10.0)}>
          🌙 Artemis Lunar Habitat (34% O₂, 56.5 kPa)
        </button>
        <button type="button" className="nx-btn ghost" onClick={() => applyPreset(26.5, 70.3, 6.0)}>
          👨‍🚀 EVA Pre-Breathe (26.5% O₂, 70.3 kPa)
        </button>
        <button type="button" className="nx-btn ghost" onClick={() => applyPreset(21.0, 101.3, 0.0)}>
          🛑 Fans Off / Quiescent (21% O₂, 0 cm/s)
        </button>
      </div>

      <section className="nx-card" style={{ marginBottom: 22 }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
            gap: 18,
          }}
        >
          <div>
            <label className="lbl-strong" htmlFor="sim-o2">
              Cabin Oxygen: <span className="mono">{oxygen.toFixed(1)}% O₂</span>
            </label>
            <input
              id="sim-o2"
              type="range"
              min={12}
              max={48}
              step={0.5}
              value={oxygen}
              onChange={(e) => setOxygen(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label className="lbl-strong" htmlFor="sim-kpa">
              Cabin Pressure: <span className="mono">{pressure.toFixed(1)} kPa</span>
            </label>
            <input
              id="sim-kpa"
              type="range"
              min={25}
              max={115}
              step={0.5}
              value={pressure}
              onChange={(e) => setPressure(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label className="lbl-strong" htmlFor="sim-flow">
              HVAC Airflow: <span className="mono">{airflow.toFixed(1)} cm/s</span>
            </label>
            <input
              id="sim-flow"
              type="range"
              min={0}
              max={55}
              step={0.5}
              value={airflow}
              onChange={(e) => setAirflow(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label className="lbl-strong" htmlFor="sim-mat">
              Fuel / Specimen Material
            </label>
            <select
              id="sim-mat"
              value={material}
              onChange={(e) => setMaterial(e.target.value)}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: 10,
                background: 'rgba(11, 16, 38, 0.9)',
                border: '1px solid rgba(106, 168, 255, 0.35)',
              }}
            >
              {POPULAR_MATERIALS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {res && (
        <>
          <div className="nx-stats" style={{ marginBottom: 20 }}>
            <div className={'nx-stat ' + (res.risk_level === 'CRITICAL' || res.risk_level === 'HIGH' ? 'red' : '')}>
              <b>
                {res.risk_level} ({res.risk_score.toFixed(2)})
              </b>
              <span>Flammability Risk Level (0–1.0)</span>
            </div>
            <div className="nx-stat">
              <b>{(res.sustained_burn_probability * 100).toFixed(1)}%</b>
              <span>Sustained Burn Probability (ML)</span>
            </div>
            <div className="nx-stat">
              <b>{res.predicted_burning_rate_mms.toFixed(2)} mm/s</b>
              <span>Predicted Burn / Spread Rate</span>
            </div>
            <div className="nx-stat">
              <b>{res.predicted_flame_temp_k.toFixed(0)} K</b>
              <span>Predicted Flame Temperature</span>
            </div>
          </div>

          <section className="nx-card" style={{ marginBottom: 22 }}>
            <h3>🗺️ Interactive 2D Flammability Envelope & MOC Boundary Curves</h3>
            <p className="k" style={{ marginBottom: 14 }}>
              <strong>Left:</strong> Pressure vs. O₂ surface showing the{' '}
              <span style={{ color: '#38bdf8', fontWeight: 600 }}>0g Microgravity MOC Boundary (solid cyan)</span> vs.{' '}
              <span style={{ color: '#4ade80', fontWeight: 600 }}>1g NASA-STD-6001 MOC (dashed green)</span>.{' '}
              <strong>Right:</strong> Ventilation U-curve showing Diffusive Quenching (&lt;1.5 cm/s) vs. High-Flow
              Blowoff (&gt;32 cm/s). Click either map to update parameters!
            </p>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
                gap: 18,
              }}
            >
              <div>
                <MocEnvelopeCanvas
                  envelope={res.envelope}
                  oxygen={oxygen}
                  pressure={pressure}
                  onSelectPoint={(newP, newO2) => {
                    setPressure(newP);
                    setOxygen(newO2);
                  }}
                />
              </div>
              <div>
                <AirflowQuenchCanvas
                  envelope={res.envelope}
                  oxygen={oxygen}
                  airflow={airflow}
                  onSelectFlow={(newFlow, newO2) => {
                    setAirflow(newFlow);
                    setOxygen(newO2);
                  }}
                />
              </div>
            </div>
          </section>

          <div className="nx-grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 18, marginBottom: 22 }}>
            <article className="nx-card">
              <h3>⚖️ 1g NASA-STD-6001 vs. Microgravity Comparison</h3>
              <p style={{ marginTop: 8 }}>{res.std6001_comparison}</p>
            </article>
            <article className="nx-card">
              <h3>🛡️ Recommended Spacecraft Fire-Safety Controls</h3>
              <ul style={{ margin: '8px 0 0', paddingLeft: 20, color: '#cbd5e1' }}>
                {res.recommendations.map((rec) => (
                  <li key={rec} style={{ marginBottom: 6 }}>
                    {rec}
                  </li>
                ))}
              </ul>
            </article>
          </div>

          <section className="nx-card">
            <h3>🔬 5 Closest Historical NASA/JAXA Experiments in (O₂, Pressure, Airflow, Material) Space</h3>
            <div className="wrap" style={{ marginTop: 12 }}>
              <table>
                <thead>
                  <tr>
                    <th>Experiment ID</th>
                    <th>Family</th>
                    <th>Fuel / Material</th>
                    <th>O₂ (%)</th>
                    <th>Pressure (kPa)</th>
                    <th>Airflow (cm/s)</th>
                    <th>Burn Rate (mm/s)</th>
                    <th>Outcome</th>
                    <th>Distance</th>
                  </tr>
                </thead>
                <tbody>
                  {res.nearest_experiments.map((ne) => (
                    <tr key={ne.experiment_id}>
                      <td>
                        <a href={ne.source_url} target="_blank" rel="noreferrer" className="link-btn">
                          {ne.experiment_id}
                        </a>
                      </td>
                      <td>{ne.dataset_family}</td>
                      <td>{ne.fuel_material}</td>
                      <td>{ne.oxygen_pct ?? '—'}</td>
                      <td>{ne.pressure_kpa ?? '—'}</td>
                      <td>{ne.airflow_velocity_cms ?? '—'}</td>
                      <td>{ne.burning_rate_mms ?? '—'}</td>
                      <td>{ne.extinction_outcome}</td>
                      <td>{ne.distance.toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
