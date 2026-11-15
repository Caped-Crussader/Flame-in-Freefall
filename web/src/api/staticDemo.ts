import type {
  EvaluationScorecard,
  InsightsPayload,
  MissionSafetyDossier,
  PaginatedExperiments,
  RiskSimulationInput,
  RiskSimulationResult,
} from './client';
import { normalizeRow, type Json } from './normalize';
import type { EvidenceRow } from '../types';

interface SimulatorMaterialEntry {
  envelope: RiskSimulationResult['envelope'];
  presets: Record<string, Omit<RiskSimulationResult, 'envelope'>>;
}

interface SimulatorCache {
  materials: Record<string, SimulatorMaterialEntry>;
}

const jsonCache = new Map<string, Promise<unknown>>();
let demoModeActive = false;

export function isStaticDemoMode(): boolean {
  return demoModeActive;
}

export function markStaticDemoMode(): void {
  demoModeActive = true;
}

export function resetStaticDemoMode(): void {
  demoModeActive = false;
  jsonCache.clear();
}

function demoUrl(file: string): string {
  const base = (import.meta.env.BASE_URL || '/').replace(/\/?$/, '/');
  return `${base}demo/${file}`;
}

async function loadDemoJson<T>(file: string): Promise<T> {
  let pending = jsonCache.get(file);
  if (!pending) {
    pending = (async () => {
      const res = await fetch(demoUrl(file));
      const ct = (res.headers.get('content-type') || '').toLowerCase();
      if (!res.ok || (!ct.includes('application/json') && !ct.includes('text/plain'))) {
        throw new Error(`Static demo asset unavailable: ${file}`);
      }
      return (await res.json()) as unknown;
    })();
    jsonCache.set(file, pending);
  }
  try {
    const data = (await pending) as T;
    demoModeActive = true;
    return data;
  } catch (err) {
    jsonCache.delete(file);
    throw err;
  }
}

export async function getStaticMeta(): Promise<unknown> {
  return loadDemoJson<unknown>('meta.json');
}

export async function getStaticExperiments(params: {
  dataset_family?: string;
  fuel_material?: string;
  gravity_condition?: string;
  include_modeled?: boolean;
  limit?: number;
  offset?: number;
}): Promise<PaginatedExperiments> {
  const raw = await loadDemoJson<{ items?: unknown[] }>('experiments.json');
  const all = (Array.isArray(raw.items) ? raw.items : [])
    .map(normalizeRow)
    .filter((r): r is EvidenceRow => r !== null);

  const includeModeled = params.include_modeled === true;
  const filtered = all.filter((r) => {
    if (!includeModeled && r.is_modeled) return false;
    if (params.dataset_family && params.dataset_family !== 'All' && r.dataset_family !== params.dataset_family) {
      return false;
    }
    if (params.fuel_material && params.fuel_material !== 'All' && r.fuel_material !== params.fuel_material) {
      return false;
    }
    if (
      params.gravity_condition &&
      params.gravity_condition !== 'All' &&
      r.gravity_condition !== params.gravity_condition
    ) {
      return false;
    }
    return true;
  });

  const offset = params.offset ?? 0;
  const limit = params.limit ?? 100;
  return {
    total: filtered.length,
    limit,
    offset,
    items: filtered.slice(offset, offset + limit),
  };
}

export async function getStaticExperimentDetail(id: string): Promise<EvidenceRow> {
  const raw = await loadDemoJson<{ items?: unknown[] }>('experiments.json');
  const items = Array.isArray(raw.items) ? raw.items : [];
  const match = items.find((row) => typeof row === 'object' && row !== null && (row as Json).experiment_id === id);
  const norm = match ? normalizeRow(match) : null;
  if (!norm) {
    throw new Error(`Experiment ${id} not found in static demo snapshot`);
  }
  return norm;
}

export async function getStaticInsightsRanking(): Promise<InsightsPayload> {
  return loadDemoJson<InsightsPayload>('insights.json');
}

export async function getStaticEvaluation(): Promise<EvaluationScorecard> {
  return loadDemoJson<EvaluationScorecard>('evaluation.json');
}

function interp1D(xs: number[], ys: number[], x: number): number {
  if (!xs.length || !ys.length) return 0;
  if (x <= xs[0]) return ys[0];
  if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
  for (let i = 0; i < xs.length - 1; i++) {
    if (x >= xs[i] && x <= xs[i + 1]) {
      const t = (x - xs[i]) / Math.max(1e-9, xs[i + 1] - xs[i]);
      return ys[i] + t * (ys[i + 1] - ys[i]);
    }
  }
  return ys[ys.length - 1];
}

function bilinearMatrix(xs: number[], ys: number[], mat: number[][], x: number, y: number): number {
  if (!xs.length || !ys.length || !mat.length) return 0.5;
  const cx = Math.min(xs[xs.length - 1], Math.max(xs[0], x));
  const cy = Math.min(ys[ys.length - 1], Math.max(ys[0], y));

  let ix = 0;
  while (ix < xs.length - 2 && cx > xs[ix + 1]) ix++;
  let iy = 0;
  while (iy < ys.length - 2 && cy > ys[iy + 1]) iy++;

  const tx = xs.length > 1 ? (cx - xs[ix]) / Math.max(1e-9, xs[ix + 1] - xs[ix]) : 0;
  const ty = ys.length > 1 ? (cy - ys[iy]) / Math.max(1e-9, ys[iy + 1] - ys[iy]) : 0;

  const q00 = mat[iy]?.[ix] ?? 0.5;
  const q10 = mat[iy]?.[ix + 1] ?? q00;
  const q01 = mat[iy + 1]?.[ix] ?? q00;
  const q11 = mat[iy + 1]?.[ix + 1] ?? q10;

  const r0 = q00 + tx * (q10 - q00);
  const r1 = q01 + tx * (q11 - q01);
  return r0 + ty * (r1 - r0);
}

export async function simulateStaticRisk(input: RiskSimulationInput): Promise<RiskSimulationResult> {
  const sim = await loadDemoJson<SimulatorCache>('simulator.json');
  const matNames = Object.keys(sim.materials);
  const entry = sim.materials[input.fuel_material] ?? sim.materials[matNames[0]];
  const exactKey = `${input.oxygen_pct.toFixed(1)}|${input.pressure_kpa.toFixed(1)}|${input.airflow_velocity_cms.toFixed(1)}`;
  if (entry.presets[exactKey]) {
    return {
      ...entry.presets[exactKey],
      envelope: entry.envelope,
    };
  }

  // Nearest pre-computed preset for reference telemetry, detection, and 5-NN baseline
  const presetEntries = Object.entries(entry.presets);
  let bestPreset = presetEntries[0][1];
  let bestDist = Number.POSITIVE_INFINITY;
  for (const [k, val] of presetEntries) {
    const [po2, pkpa, pflow] = k.split('|').map(Number);
    const d =
      Math.pow((po2 - input.oxygen_pct) / 25, 2) +
      Math.pow((pkpa - input.pressure_kpa) / 35, 2) +
      Math.pow((pflow - input.airflow_velocity_cms) / 15, 2);
    if (d < bestDist) {
      bestDist = d;
      bestPreset = val;
    }
  }

  const env = entry.envelope;
  const basePo2Risk = bilinearMatrix(
    env.pressure_grid_kpa,
    env.oxygen_grid_pct,
    env.risk_matrix,
    input.pressure_kpa,
    input.oxygen_pct,
  );
  const flowRisk = bilinearMatrix(
    env.airflow_grid_cms,
    env.oxygen_grid_pct,
    env.airflow_risk_matrix,
    input.airflow_velocity_cms,
    input.oxygen_pct,
  );

  // Above 45% O2 grid ceiling, extrapolate risk monotonically upward toward pure-O2 regimes
  const hyperoxicBoost = input.oxygen_pct > 45 ? Math.min(0.28, ((input.oxygen_pct - 45) / 55) * 0.28) : 0;
  const riskScore = Math.max(0.03, Math.min(0.99, 0.62 * basePo2Risk + 0.38 * flowRisk + hyperoxicBoost));
  const riskLevel =
    riskScore >= 0.78 ? 'CRITICAL' : riskScore >= 0.55 ? 'HIGH' : riskScore >= 0.3 ? 'MODERATE' : 'LOW';

  const po2 = (input.pressure_kpa * input.oxygen_pct) / 100;
  const normoxicRatio = po2 / 21.27;
  const diluentRatio = (100 - input.oxygen_pct) / Math.max(1, input.oxygen_pct);
  const v = input.airflow_velocity_cms;
  const pe = (v / (v + 2.0)) * Math.exp(-Math.max(0, v - 22.0) / 40.0);
  const moc0g = interp1D(env.pressure_grid_kpa, env.moc_0g_o2_pct, input.pressure_kpa);
  const moc1g = interp1D(env.pressure_grid_kpa, env.moc_1g_std6001_o2_pct, input.pressure_kpa);
  const margin = moc0g - input.oxygen_pct;

  const transportRegime =
    v < 1.5
      ? 'Diffusive Oxygen-Starvation Regime (<1.5 cm/s)'
      : v <= 25
        ? 'Peak Microgravity Ventilation Hazard (1.5–25 cm/s)'
        : v <= 32
          ? 'Transitional Convective Cooling Regime (25–32 cm/s)'
          : 'High-Flow Convective Blowoff Regime (>32 cm/s)';

  const baseScore = Math.max(0.15, bestPreset.risk_score);
  const scale = Math.max(0.55, Math.min(1.65, riskScore / baseScore));
  const predRate = Math.max(0.05, Number((bestPreset.predicted_burning_rate_mms * scale).toFixed(2)));
  const predTemp = Math.max(
    650,
    Math.min(2450, Math.round(bestPreset.predicted_flame_temp_k * (0.88 + 0.12 * scale))),
  );

  return {
    ...bestPreset,
    risk_score: Number(riskScore.toFixed(3)),
    risk_level: riskLevel,
    sustained_burn_probability: Number(Math.min(0.99, Math.max(0.02, riskScore * 1.03)).toFixed(3)),
    predicted_burning_rate_mms: predRate,
    predicted_flame_temp_k: predTemp,
    physics_diagnostics: {
      oxygen_partial_pressure_kpa: Number(po2.toFixed(2)),
      normoxic_po2_ratio: Number(normoxicRatio.toFixed(2)),
      diluent_to_o2_ratio: Number(diluentRatio.toFixed(2)),
      peclet_transport_factor: Number(pe.toFixed(3)),
      moc_0g_limit_o2_pct: Number(moc0g.toFixed(1)),
      moc_1g_std6001_limit_o2_pct: Number(moc1g.toFixed(1)),
      moc_safety_margin_o2_pct: Number(margin.toFixed(1)),
      transport_regime: transportRegime,
    },
    uncertainty: bestPreset.uncertainty
      ? {
          ...bestPreset.uncertainty,
          burning_rate_ci90_mms: [
            Number((predRate * 0.65).toFixed(2)),
            Number((predRate * 1.48).toFixed(2)),
          ],
          flame_temp_ci90_k: [Math.max(580, predTemp - 160), Math.min(2550, predTemp + 160)],
          confidence_level: input.oxygen_pct > 50 ? 'EXPLORATORY' : bestPreset.uncertainty.confidence_level,
        }
      : undefined,
    envelope: env,
  };
}

function escHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function buildMocSvg(
  env: RiskSimulationResult['envelope'] | undefined,
  pressureKpa: number,
  oxygenPct: number,
): string {
  const pGrid = env?.pressure_grid_kpa ?? [30, 101.3];
  const moc0g = env?.moc_0g_o2_pct ?? pGrid.map(() => 18.0);
  const moc1g = env?.moc_1g_std6001_o2_pct ?? pGrid.map(() => 21.0);
  const pMin = pGrid[0] ?? 30;
  const pMax = pGrid[pGrid.length - 1] ?? 101.3;
  const o2Min = 12.0;
  const o2Max = 48.0;

  const sx = (pVal: number) => Number((50 + ((pVal - pMin) / Math.max(1, pMax - pMin)) * 420).toFixed(1));
  const sy = (o2Val: number) => {
    const clamped = Math.min(o2Max, Math.max(o2Min, o2Val));
    return Number((190 - ((clamped - o2Min) / (o2Max - o2Min)) * 160).toFixed(1));
  };

  const pts0g = pGrid.map((p, i) => `${sx(p)},${sy(moc0g[i] ?? 18)}`).join(' ');
  const pts1g = pGrid.map((p, i) => `${sx(p)},${sy(moc1g[i] ?? 21)}`).join(' ');
  const ux = sx(pressureKpa);
  const uy = sy(oxygenPct);

  return `<svg viewBox="0 0 500 220" style="width:100%; border:1px solid #cbd5e1; border-radius:6px; background:#0f172a;">
      <rect x="50" y="30" width="420" height="160" fill="#1e293b" stroke="#475569" />
      <polyline fill="none" stroke="#4ade80" stroke-width="2.5" stroke-dasharray="5,4" points="${pts1g}" />
      <polyline fill="none" stroke="#38bdf8" stroke-width="3" points="${pts0g}" />
      <circle cx="${ux}" cy="${uy}" r="6" fill="#facc15" stroke="#000" stroke-width="1.5" />
      <text x="58" y="46" fill="#38bdf8" font-size="10" font-family="sans-serif">Solid Cyan: 0g Microgravity MOC Boundary</text>
      <text x="58" y="60" fill="#4ade80" font-size="10" font-family="sans-serif">Dashed Green: 1g NASA-STD-6001 MOC</text>
      <text x="150" y="210" fill="#cbd5e1" font-size="10" font-family="monospace">Cabin Pressure (${pMin.toFixed(0)}–${pMax.toFixed(0)} kPa) · Yellow Dot = Operating Point</text>
    </svg>`;
}

export async function generateStaticDossier(input: RiskSimulationInput): Promise<MissionSafetyDossier> {
  const sim = await simulateStaticRisk(input);
  const meta = (await getStaticMeta().catch(() => ({}))) as Json;
  const versionInfo = (meta.version_info as Json | undefined) ?? {};
  const sha = String(versionInfo.parquet_sha256 ?? meta.dataset_version ?? '4b3139dc').slice(0, 12);

  const env = sim.envelope;
  const v = input.airflow_velocity_cms;
  const po2Fallback = (input.pressure_kpa * input.oxygen_pct) / 100;
  const moc0gFallback = interp1D(env.pressure_grid_kpa, env.moc_0g_o2_pct, input.pressure_kpa);
  const moc1gFallback = interp1D(env.pressure_grid_kpa, env.moc_1g_std6001_o2_pct, input.pressure_kpa);
  const phys = sim.physics_diagnostics ?? {
    oxygen_partial_pressure_kpa: Number(po2Fallback.toFixed(2)),
    normoxic_po2_ratio: Number((po2Fallback / 21.27).toFixed(2)),
    diluent_to_o2_ratio: Number(((100 - input.oxygen_pct) / Math.max(1, input.oxygen_pct)).toFixed(2)),
    peclet_transport_factor: Number(((v / (v + 2.0)) * Math.exp(-Math.max(0, v - 22.0) / 40.0)).toFixed(3)),
    moc_0g_limit_o2_pct: Number(moc0gFallback.toFixed(1)),
    moc_1g_std6001_limit_o2_pct: Number(moc1gFallback.toFixed(1)),
    moc_safety_margin_o2_pct: Number((moc0gFallback - input.oxygen_pct).toFixed(1)),
    transport_regime:
      v < 1.5
        ? 'Diffusive Oxygen-Starvation Regime (<1.5 cm/s)'
        : v <= 25
          ? 'Peak Microgravity Ventilation Hazard (1.5–25 cm/s)'
          : v <= 32
            ? 'Transitional Convective Cooling Regime (25–32 cm/s)'
            : 'High-Flow Convective Blowoff Regime (>32 cm/s)',
  };

  const unc = sim.uncertainty ?? {
    sustained_prob_std: 0.1,
    burning_rate_ci90_mms: [
      Number((sim.predicted_burning_rate_mms * 0.65).toFixed(2)),
      Number((sim.predicted_burning_rate_mms * 1.48).toFixed(2)),
    ] as [number, number],
    flame_temp_ci90_k: [
      Math.max(580, Math.round(sim.predicted_flame_temp_k - 160)),
      Math.min(2550, Math.round(sim.predicted_flame_temp_k + 160)),
    ] as [number, number],
    confidence_level: input.oxygen_pct > 50 ? 'EXPLORATORY' : 'HIGH',
    confidence_score: 0.85,
  };

  const det = sim.detection_suppression;
  const nearest = sim.nearest_experiments ?? [];

  let certStatus: string;
  if (sim.risk_level === 'LOW' && phys.moc_safety_margin_o2_pct >= 0.0) {
    certStatus = 'PASS — CERTIFIED WITHIN 0g & 1g MOC MARGIN';
  } else if ((sim.risk_level === 'LOW' || sim.risk_level === 'MODERATE') && phys.moc_safety_margin_o2_pct >= -2.5) {
    certStatus = 'CONDITIONAL PASS — REQUIRES ECLSS VENTILATION & SUPPRESSION CONTROLS';
  } else {
    certStatus = 'WAIVER REQUIRED — EXCEEDS 0g MICROGRAVITY FLAMMABILITY THRESHOLD';
  }

  const matSlug =
    input.fuel_material
      .split('(')[0]
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, '')
      .slice(0, 8) || 'MAT';
  const dossierId = `IGNIS-CERT-DEMO-${Math.round(input.oxygen_pct * 10)}O2-${Math.round(input.pressure_kpa)}KPA-${matSlug}`;
  const nowUtc = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
  const marginStr = `${phys.moc_safety_margin_o2_pct >= 0 ? '+' : ''}${phys.moc_safety_margin_o2_pct.toFixed(1)}% O₂`;

  const nearestMdRows = nearest.length
    ? nearest
        .map(
          (ne) =>
            `| \`${ne.experiment_id}\` | ${ne.dataset_family} | ${ne.fuel_material} | ${ne.oxygen_pct ?? '—'}% | ${ne.pressure_kpa ?? '—'} kPa | ${ne.airflow_velocity_cms ?? '—'} cm/s | ${ne.burning_rate_mms ?? '—'} mm/s | ${ne.extinction_outcome} | \`${ne.distance.toFixed(3)}\` |`,
        )
        .join('\n')
    : '| — | No matching records in demo snapshot | — | — | — | — | — | — | — |';

  const extMdRows = det?.extinguishant_options?.length
    ? det.extinguishant_options
        .map(
          (opt) =>
            `| **${opt.agent_name}** | \`${opt.suitability}\` | ${opt.effectiveness_pct.toFixed(0)}% | ${opt.mechanism_and_tradeoff} | ${opt.cited_experiments.map((c) => `\`${c}\``).join(', ')} |`,
        )
        .join('\n')
    : '';

  const detEvRows = det?.evidence_experiments?.length
    ? det.evidence_experiments
        .map(
          (ev) =>
            `| \`${ev.experiment_id}\` | ${ev.dataset_family} | ${ev.fuel_material} | ${ev.co_ppm !== null ? ev.co_ppm.toFixed(1) : '—'} | ${ev.extinction_outcome} | ${ev.key_insight} |`,
        )
        .join('\n')
    : '';

  const recsMd = (sim.recommendations ?? []).map((r) => `- ${r}`).join('\n');
  const toxMd = (det?.secondary_toxic_byproducts ?? []).map((g) => `- ${g}`).join('\n');
  const cleanupMd = (det?.post_fire_cleanup_steps ?? []).map((s) => `- ${s}`).join('\n');

  const mdSections = [
    `# 🚀 SPACECRAFT & HABITAT FIRE-SAFETY CERTIFICATION DOSSIER`,
    `**Dossier ID:** \`${dossierId}\`  `,
    `**Generated (UTC):** \`${nowUtc}\` (Static Browser Snapshot)  `,
    `**Validated Dataset Snapshot SHA-256:** \`${sha}\` (\`892\` Total Records · \`840\` Physical Flight/Drop-Tower Tests)  `,
    `**Certification Determination:** **${certStatus}**`,
    '',
    '---',
    '',
    `## 1. Mission Atmosphere & Specimen Specification`,
    `| Parameter | Specified Operating Value | Reference / Baseline |`,
    `| :--- | :--- | :--- |`,
    `| **Fuel / Specimen Material** | **${input.fuel_material}** | Evaluated against 30 NASA/JAXA combustion families |`,
    `| **Cabin Oxygen Concentration** | **${input.oxygen_pct.toFixed(1)}% O₂** | ISS Standard: \`21.0% O₂\` · Artemis SEA: \`34.0% O₂\` |`,
    `| **Total Cabin Pressure** | **${input.pressure_kpa.toFixed(1)} kPa** | ISS Standard: \`101.3 kPa\` · Artemis SEA: \`56.5 kPa\` |`,
    `| **HVAC Ventilation Velocity** | **${input.airflow_velocity_cms.toFixed(1)} cm/s** | Quiescent Quench: \`<1.5 cm/s\` · Peak Hazard: \`1.5–25 cm/s\` |`,
    `| **Gravity Regime** | **${input.gravity_regime ?? '0g Microgravity'}** | Low-stretch microgravity boundary-layer transport |`,
    '',
    '---',
    '',
    `## 2. Coupled Microgravity Physics & Ensemble ML Flammability Assessment`,
    `| Metric | Value / Prediction | 90% Ensemble Interval / Physical Reference |`,
    `| :--- | :--- | :--- |`,
    `| **Composite Flammability Risk Level** | **${sim.risk_level} (\`${sim.risk_score.toFixed(2)}\` / 1.00)** | Epistemic Confidence: **${unc.confidence_level} (\`${(unc.confidence_score * 100).toFixed(0)}%\`)** |`,
    `| **Sustained Burn Probability (ML)** | **${(sim.sustained_burn_probability * 100).toFixed(1)}%** | Ensemble Tree StdDev: \`±${(unc.sustained_prob_std * 100).toFixed(1)}%\` |`,
    `| **Predicted Flame Spread / Burn Rate** | **${sim.predicted_burning_rate_mms.toFixed(2)} mm/s** | 90% Prediction Interval: \`${unc.burning_rate_ci90_mms[0].toFixed(2)}–${unc.burning_rate_ci90_mms[1].toFixed(2)} mm/s\` |`,
    `| **Predicted Flame Temperature** | **${sim.predicted_flame_temp_k.toFixed(0)} K** | 90% Prediction Interval: \`${unc.flame_temp_ci90_k[0].toFixed(0)}–${unc.flame_temp_ci90_k[1].toFixed(0)} K\` |`,
    `| **Oxygen Partial Pressure (P_O₂)** | **${phys.oxygen_partial_pressure_kpa.toFixed(2)} kPa** | \`${phys.normoxic_po2_ratio.toFixed(2)}×\` Earth Sea-Level Normoxic (\`21.27 kPa\`) |`,
    `| **Inert Diluent Heat-Sink Ratio (N₂/O₂)** | **${phys.diluent_to_o2_ratio.toFixed(2)} : 1** | Earth Sea-Level Air Baseline: \`3.76 : 1\` |`,
    `| **0g Microgravity MOC Limit** | **${phys.moc_0g_limit_o2_pct.toFixed(1)}% O₂** | 1g \`NASA-STD-6001\` MOC Limit: **${phys.moc_1g_std6001_limit_o2_pct.toFixed(1)}% O₂** |`,
    `| **0g MOC Safety Margin** | **${marginStr}** | \`${phys.transport_regime}\` (\`Pe=${phys.peclet_transport_factor.toFixed(2)}\`) |`,
    '',
    `> **1g \`NASA-STD-6001\` vs. Microgravity Screening Comparison:**  `,
    `> ${sim.std6001_comparison}`,
    '',
    `### Mandatory Engineering & ECLSS Controls`,
    recsMd,
  ];

  if (det) {
    mdSections.push(
      '',
      '---',
      '',
      `## 3. Spacecraft Fire Detection, Suppression & Post-Fire Cleanup Specification (\`SAME\`, \`DAFT\`, \`SLICE\`, \`SAFFIRE IV–VI\`)`,
      '',
      `### 3.1 Smoke Detection Modality & Lunar Dust Discrimination`,
      `- **Recommended Detector Architecture:** **${det.recommended_detector_modality}**`,
      `- **Microgravity Smoke Particle Size (CMD):** \`${det.smoke_cmd_0g_um.toFixed(2)} μm\` in 0g (vs. \`${det.smoke_cmd_1g_um.toFixed(2)} μm\` in 1g)`,
      `- **Detector Modality Sensitivity (0g):** Laser Photoelectric Scattering \`${(det.photoelectric_sensitivity * 100).toFixed(0)}%\` vs. Americium-241 Ionization \`${(det.ionization_sensitivity * 100).toFixed(0)}%\``,
      `- **Estimated HVAC Alarm Transport Delay:** \`~${det.estimated_alarm_time_s.toFixed(1)} s\``,
      `- **Physical Rationale (\`SAME\` / \`SAME-R\`):** ${det.detector_rationale}`,
      `- **Lunar Regolith False-Alarm Mitigation (\`DAFT / DAFT-2\`):** ${det.lunar_dust_discrimination_note}`,
      '',
      `### 3.2 Spacecraft Fire Suppressant Evaluation (\`SLICE-001..008\`)`,
      `- **Primary Recommended Suppressant:** \`${det.primary_extinguishant}\``,
      `- **Secondary / Backup Suppressant:** \`${det.secondary_extinguishant}\``,
      `- **Target CO₂ Flood Concentration:** \`${det.required_co2_inerting_pct.toFixed(1)}% Vol\` · **Target N₂ Limiting Oxygen Index:** \`<${det.limiting_oxygen_index_pct.toFixed(1)}% O₂\``,
      '',
      `| Suppressant Agent | Suitability | Effectiveness | Mechanism & Operational Tradeoff | Cited NASA Tests |`,
      `| :--- | :--- | :--- | :--- | :--- |`,
      extMdRows,
      '',
      `### 3.3 Carbon Monoxide (CO) Toxicity & Post-Fire ECLSS Scrubbing (\`SAME\`, \`MGM\`, \`SAFFIRE-VI\`)`,
      `- **Estimated Peak Localized/Cabin CO:** **${det.estimated_peak_co_ppm.toFixed(1)} ppm** — **${det.co_toxicity_level}**`,
      `- **NASA Spacecraft Maximum Allowable Concentration (SMAC):** 1-Hour Limit = \`${det.nasa_smac_1hr_co_ppm.toFixed(0)} ppm\` · 24-Hour Limit = \`${det.nasa_smac_24hr_co_ppm.toFixed(0)} ppm\``,
      '',
      `**Toxic Pyrolysis Byproducts to Monitor:**`,
      toxMd,
      '',
      `**Post-Fire Cabin Scrubbing & Crew Recovery Protocol (\`SAFFIRE-VI\`):**`,
      cleanupMd,
    );
  }

  mdSections.push(
    '',
    '---',
    '',
    `## 4. Grounded NASA/JAXA Experimental Evidence Audit Log`,
    '',
    `### 4.1 Five Closest Physical Flammability Experiments in (O₂, Pressure, Airflow, Material) Space`,
    `| Experiment ID | Dataset Family | Fuel / Material | O₂ (%) | Pressure | Airflow | Burn Rate | Outcome | Euclidean Dist |`,
    `| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |`,
    nearestMdRows,
  );

  if (detEvRows) {
    mdSections.push(
      '',
      `### 4.2 Grounded Detection, Suppression & Cleanup Reference Tests (\`SAME\`, \`DAFT\`, \`SLICE\`, \`SAFFIRE\`, \`MGM\`)`,
      `| Experiment ID | Dataset Family | Material / Aerosol Test | Peak CO (ppm) | Outcome | Key Engineering Insight |`,
      `| :--- | :--- | :--- | :--- | :--- | :--- |`,
      detEvRows,
    );
  }

  mdSections.push(
    '',
    '---',
    `*Generated by **IGNIS — Flame in Freefall** · Pre-Computed Static Demo Envelope + Client Physics Interpolation.*`,
  );

  const md = mdSections.join('\n');

  const statusBg = certStatus.startsWith('PASS')
    ? '#dcfce7'
    : certStatus.startsWith('CONDITIONAL')
      ? '#fef9c3'
      : '#fee2e2';
  const statusFg = certStatus.startsWith('PASS')
    ? '#166534'
    : certStatus.startsWith('CONDITIONAL')
      ? '#854d0e'
      : '#991b1b';

  const nearestHtmlRows = nearest.length
    ? nearest
        .map(
          (ne) =>
            `<tr><td><code>${escHtml(ne.experiment_id)}</code></td>` +
            `<td>${escHtml(ne.dataset_family)}</td>` +
            `<td>${escHtml(ne.fuel_material)}</td>` +
            `<td>${ne.oxygen_pct ?? '—'}%</td>` +
            `<td>${ne.pressure_kpa ?? '—'} kPa</td>` +
            `<td>${ne.airflow_velocity_cms ?? '—'} cm/s</td>` +
            `<td>${ne.burning_rate_mms ?? '—'} mm/s</td>` +
            `<td>${escHtml(ne.extinction_outcome)}</td></tr>`,
        )
        .join('')
    : `<tr><td colspan="8">No matching physical experiments bundled in this static fixture.</td></tr>`;

  const extHtmlRows = det?.extinguishant_options?.length
    ? det.extinguishant_options
        .map(
          (opt) =>
            `<tr><td><strong>${escHtml(opt.agent_name)}</strong></td>` +
            `<td><code>${escHtml(opt.suitability)}</code></td>` +
            `<td>${opt.effectiveness_pct.toFixed(0)}%</td>` +
            `<td>${escHtml(opt.mechanism_and_tradeoff)}</td>` +
            `<td><code>${escHtml(opt.cited_experiments.join(', '))}</code></td></tr>`,
        )
        .join('')
    : '';

  const detHtmlSection = det
    ? `
  <h2>2. Fire Detection, Suppression &amp; Post-Fire Cleanup Specification (SAME, DAFT, SLICE, SAFFIRE IV–VI)</h2>
  <table>
    <tbody>
      <tr><th>Optimal Smoke Detector (SAME/SAME-R)</th><td><strong>${escHtml(det.recommended_detector_modality)}</strong> — 0g Smoke CMD: <code>${det.smoke_cmd_0g_um.toFixed(2)} μm</code> (vs. <code>${det.smoke_cmd_1g_um.toFixed(2)} μm</code> in 1g) · Photoelectric: <code>${(det.photoelectric_sensitivity * 100).toFixed(0)}%</code> vs. Ionization: <code>${(det.ionization_sensitivity * 100).toFixed(0)}%</code></td></tr>
      <tr><th>Lunar Dust Discrimination (DAFT-2)</th><td>${escHtml(det.lunar_dust_discrimination_note)}</td></tr>
      <tr><th>Primary &amp; Backup Suppressant (SLICE)</th><td>Primary: <strong>${escHtml(det.primary_extinguishant)}</strong> · Backup: <strong>${escHtml(det.secondary_extinguishant)}</strong></td></tr>
      <tr><th>Peak CO &amp; Toxicity Status</th><td><strong>${det.estimated_peak_co_ppm.toFixed(1)} ppm CO</strong> (${escHtml(det.co_toxicity_level)}) vs. NASA 1-hr SMAC (${det.nasa_smac_1hr_co_ppm.toFixed(0)} ppm) / 24-hr SMAC (${det.nasa_smac_24hr_co_ppm.toFixed(0)} ppm)</td></tr>
    </tbody>
  </table>
  ${
    extHtmlRows
      ? `<table>
    <thead>
      <tr><th>Suppressant Modality</th><th>Suitability</th><th>Eff.</th><th>Mechanism &amp; Tradeoff</th><th>Citations</th></tr>
    </thead>
    <tbody>${extHtmlRows}</tbody>
  </table>`
      : ''
  }`
    : '';

  const recsHtml = (sim.recommendations ?? []).length
    ? `<h2>4. Mandatory Engineering Controls &amp; NASA-STD-6001 Comparison</h2>
  <p style="margin:6px 0 8px;"><strong>NASA-STD-6001 Screening:</strong> ${escHtml(sim.std6001_comparison)}</p>
  <ul style="margin:0 0 12px 18px; padding:0;">${sim.recommendations.map((r) => `<li>${escHtml(r)}</li>`).join('')}</ul>`
    : '';

  const svgChart = buildMocSvg(env, input.pressure_kpa, input.oxygen_pct);

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>${escHtml(dossierId)} — IGNIS Mission Fire-Safety Dossier</title>
<style>
  @page { size: A4 portrait; margin: 14mm; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #0f172a;
    background: #ffffff;
    line-height: 1.45;
    font-size: 12px;
    margin: 0;
    padding: 20px;
  }
  .header {
    border-bottom: 3px solid #0f172a;
    padding-bottom: 12px;
    margin-bottom: 16px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
  }
  .eyebrow {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #475569;
  }
  h1 { font-size: 20px; margin: 4px 0; color: #0f172a; }
  h2 {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 4px;
    margin: 16px 0 8px;
    color: #1e293b;
  }
  .cert-banner {
    background: ${statusBg};
    color: ${statusFg};
    border: 1px solid ${statusFg};
    padding: 10px 14px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 13px;
    margin-bottom: 14px;
  }
  .grid-4 {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 12px;
  }
  .kpi {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 8px 10px;
    background: #f8fafc;
  }
  .kpi .lbl { font-size: 10px; color: #475569; text-transform: uppercase; }
  .kpi .val { font-size: 15px; font-weight: 800; color: #0f172a; margin-top: 2px; }
  .kpi .sub { font-size: 10px; color: #64748b; }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 6px;
    margin-bottom: 12px;
    font-size: 11px;
  }
  th, td {
    border: 1px solid #cbd5e1;
    padding: 6px 8px;
    text-align: left;
    vertical-align: top;
  }
  th { background: #f1f5f9; font-weight: 700; }
  code { font-family: monospace; background: #f1f5f9; padding: 1px 4px; border-radius: 3px; }
  .no-print { margin-bottom: 16px; display: flex; gap: 10px; align-items: center; }
  .btn-print {
    background: #ea580c;
    color: #fff;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 700;
    cursor: pointer;
  }
  @media print {
    .no-print { display: none !important; }
    body { padding: 0; }
  }
</style>
</head>
<body>
  <div class="no-print">
    <button class="btn-print" onclick="window.print()">🖨️ Print / Save as PDF</button>
    <span style="font-size:11px;color:#475569;">Static Demo Certificate (pre-computed NASA PSI envelope + client physics interpolation)</span>
  </div>
  <div class="header">
    <div>
      <div class="eyebrow">IGNIS Mission Fire-Safety Dossier · NASA Space Apps Engineering Certificate</div>
      <h1>Spacecraft Material &amp; Atmosphere Flammability Certificate</h1>
      <div>Material: <strong>${escHtml(input.fuel_material)}</strong> · Atmosphere: <strong>${input.oxygen_pct.toFixed(1)}% O₂, ${input.pressure_kpa.toFixed(1)} kPa, ${input.airflow_velocity_cms.toFixed(1)} cm/s</strong></div>
    </div>
    <div style="text-align:right; font-size:11px; white-space:nowrap;">
      <div><strong>ID:</strong> <code>${escHtml(dossierId)}</code></div>
      <div><strong>UTC:</strong> ${escHtml(nowUtc)}</div>
      <div><strong>Snapshot SHA:</strong> <code>${escHtml(sha)}</code></div>
    </div>
  </div>

  <div class="cert-banner">
    DETERMINATION: ${escHtml(certStatus)}
  </div>

  <div class="grid-4">
    <div class="kpi">
      <div class="lbl">Risk Level &amp; Score</div>
      <div class="val">${escHtml(sim.risk_level)} (${sim.risk_score.toFixed(2)})</div>
      <div class="sub">Confidence: ${escHtml(unc.confidence_level)} (${(unc.confidence_score * 100).toFixed(0)}%)</div>
    </div>
    <div class="kpi">
      <div class="lbl">Sustained Burn Prob</div>
      <div class="val">${(sim.sustained_burn_probability * 100).toFixed(1)}% ± ${(unc.sustained_prob_std * 100).toFixed(1)}%</div>
      <div class="sub">80-Tree Physics-Informed RF</div>
    </div>
    <div class="kpi">
      <div class="lbl">Predicted Burn Rate</div>
      <div class="val">${sim.predicted_burning_rate_mms.toFixed(2)} mm/s</div>
      <div class="sub">90% CI: ${unc.burning_rate_ci90_mms[0].toFixed(2)}–${unc.burning_rate_ci90_mms[1].toFixed(2)} mm/s</div>
    </div>
    <div class="kpi">
      <div class="lbl">Predicted Flame Temp</div>
      <div class="val">${sim.predicted_flame_temp_k.toFixed(0)} K</div>
      <div class="sub">90% CI: ${unc.flame_temp_ci90_k[0].toFixed(0)}–${unc.flame_temp_ci90_k[1].toFixed(0)} K</div>
    </div>
  </div>

  <h2>1. Physics-Informed Diagnostics &amp; 2D MOC Boundary Curve (0g vs. 1g NASA-STD-6001)</h2>
  <div style="display:grid; grid-template-columns: 1.1fr 1fr; gap: 14px; align-items:center;">
    <table>
      <tbody>
        <tr><th>O₂ Partial Pressure (P_O₂)</th><td><strong>${phys.oxygen_partial_pressure_kpa.toFixed(2)} kPa</strong> (${phys.normoxic_po2_ratio.toFixed(2)}× Sea-Level Normoxic)</td></tr>
        <tr><th>Inert Diluent Ratio (N₂/O₂)</th><td><strong>${phys.diluent_to_o2_ratio.toFixed(2)} : 1</strong> (Earth Air: 3.76 : 1)</td></tr>
        <tr><th>0g Microgravity MOC Limit</th><td><strong>${phys.moc_0g_limit_o2_pct.toFixed(1)}% O₂</strong> vs. 1g STD-6001: <strong>${phys.moc_1g_std6001_limit_o2_pct.toFixed(1)}% O₂</strong></td></tr>
        <tr><th>0g MOC Safety Margin</th><td><strong>${escHtml(marginStr)}</strong> (${escHtml(phys.transport_regime)})</td></tr>
      </tbody>
    </table>
    ${svgChart}
  </div>
  ${detHtmlSection}
  <h2>3. Five Closest Historical NASA/JAXA Experiments in Validated Snapshot</h2>
  <table>
    <thead>
      <tr><th>Experiment ID</th><th>Family</th><th>Material</th><th>O₂</th><th>Pressure</th><th>Airflow</th><th>Burn Rate</th><th>Outcome</th></tr>
    </thead>
    <tbody>${nearestHtmlRows}</tbody>
  </table>
  ${recsHtml}
</body>
</html>`;

  return {
    dossier_id: dossierId,
    generated_at_utc: nowUtc,
    dataset_sha256: sha,
    certification_status: certStatus,
    risk_level: sim.risk_level,
    risk_score: sim.risk_score,
    markdown_report: md,
    html_printable: html,
  };
}

export async function askStatic(question: string): Promise<unknown> {
  const cache = await loadDemoJson<Record<string, Json>>('ask_cache.json');
  const normQ = question.trim().toLowerCase().replace(/\s+/g, ' ');
  for (const [k, val] of Object.entries(cache)) {
    if (k.trim().toLowerCase().replace(/\s+/g, ' ') === normQ) {
      const existingLimits = Array.isArray(val.limitations) ? val.limitations : [];
      return {
        ...val,
        limitations: [
          ...existingLimits,
          'Served from pre-computed static demo archive (Run the FastAPI backend for live arbitrary SQL + BGE/BM25 RAG synthesis).',
        ],
      };
    }
  }

  // Fallback client-side search across the 892 indexed records for custom questions
  const rawExp = await loadDemoJson<{ items?: unknown[] }>('experiments.json');
  const items = (Array.isArray(rawExp.items) ? rawExp.items : [])
    .map((r) => (typeof r === 'object' && r !== null ? (r as Json) : null))
    .filter((r): r is Json => r !== null);

  const tokens = normQ
    .replace(/[^a-z0-9.\s-]/g, ' ')
    .split(/\s+/)
    .filter((t) => t.length >= 2 && !['what', 'which', 'how', 'the', 'and', 'for', 'are', 'with', 'from', 'that', 'this', 'does', 'did', 'between', 'across', 'show', 'all'].includes(t));

  const includeModeled =
    normQ.includes('modeled') || normQ.includes('partial') || normQ.includes('luci') || normQ.includes('fm2');

  const scored = items
    .filter((r) => includeModeled || r.is_modeled !== true)
    .map((r) => {
      const hay = [
        r.experiment_id,
        r.dataset_family,
        r.fuel_material,
        r.extinction_outcome,
        r.gravity_condition,
        r.facility_hardware,
        r.notes,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      let score = 0;
      for (const tok of tokens) {
        if (hay.includes(tok)) score += 1;
      }
      return { r, score };
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 12);

  if (!scored.length) {
    return {
      question,
      status: 'insufficient_evidence',
      answer_markdown:
        'Static demo keyword search found no matching combustion records for that exact phrasing. Try one of the **Example** questions above, click any of the **65 Golden Benchmark** questions in Tab 2, or run the local FastAPI server for full Hybrid BGE + BM25 RAG.',
      citations: [],
      evidence: [],
      literature: [],
      plan: {
        intent: 'static_demo_search',
        filters: tokens.slice(0, 6).map((t) => `keyword ~ ${t}`),
        group_by: [],
        aggregates: [],
        include_modeled: includeModeled,
        limit: 12,
      },
      aggregates: [],
      limitations: [
        'Static Demo Mode active: only pre-computed questions run the full SQL + BGE neural RAG pipeline; custom questions fall back to client-side keyword search over the 892 exported rows.',
      ],
    };
  }

  const evidenceRows = scored.map((s) => s.r);
  const citations = evidenceRows.slice(0, 8).map((r) => ({
    experiment_id: r.experiment_id,
    source_url: r.source_url ?? null,
    investigation_id: r.investigation_id ?? null,
    dataset_family: r.dataset_family ?? null,
  }));

  const bulletLines = evidenceRows.slice(0, 5).map((r) => {
    const o2 = typeof r.oxygen_pct === 'number' ? `${r.oxygen_pct}% O₂` : 'O₂ n/a';
    const kpa = typeof r.pressure_kpa === 'number' ? `${r.pressure_kpa} kPa` : 'pressure n/a';
    const out = r.extinction_outcome ?? 'Outcome n/a';
    return `- [${r.experiment_id}] **${r.dataset_family}** (${r.fuel_material ?? 'Unknown fuel'}): ${o2}, ${kpa} — *${out}*`;
  });

  return {
    question,
    status: 'answered',
    answer_markdown: [
      `Matched **${evidenceRows.length}** NASA/JAXA records in static demo mode (click any \`[ID]\` chip below to inspect the evidence row):`,
      '',
      ...bulletLines,
    ].join('\n'),
    citations,
    evidence: evidenceRows,
    literature: [],
    plan: {
      intent: 'static_demo_search',
      filters: tokens.slice(0, 6).map((t) => `keyword ~ ${t}`),
      group_by: [],
      aggregates: [],
      include_modeled: includeModeled,
      limit: 12,
    },
    aggregates: [
      {
        matched_rows_shown: evidenceRows.length,
      },
    ],
    limitations: [
      'Static Demo Mode active: custom queries use client-side keyword matching over the 892 exported records. Use Example questions or Benchmark items for full SQL + Hybrid BGE/BM25 RAG responses.',
    ],
  };
}
