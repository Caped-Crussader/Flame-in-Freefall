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

export async function generateStaticDossier(input: RiskSimulationInput): Promise<MissionSafetyDossier> {
  const sim = await simulateStaticRisk(input);
  const meta = (await getStaticMeta().catch(() => ({}))) as Json;
  const versionInfo = (meta.version_info as Json | undefined) ?? {};
  const sha = String(versionInfo.parquet_sha256 ?? meta.dataset_version ?? 'static-demo-snapshot');
  const certStatus =
    sim.risk_level === 'LOW'
      ? 'PASS'
      : sim.risk_level === 'MODERATE'
        ? 'CONDITIONAL PASS'
        : 'WAIVER REQUIRED';
  const idHash = `${Math.round(input.oxygen_pct * 10)}-${Math.round(input.pressure_kpa)}-${Math.round(input.airflow_velocity_cms)}`;
  const dossierId = `IGNIS-CERT-DEMO-${idHash}`;
  const nowUtc = new Date().toISOString();

  const md = [
    `# IGNIS Mission Fire-Safety Certification Dossier (${dossierId})`,
    '',
    `- **Mode:** Static Browser Demo Snapshot (generated locally in browser)`,
    `- **Generated (UTC):** ${nowUtc}`,
    `- **Dataset Fingerprint (SHA-256):** \`${sha}\``,
    `- **Operating Point:** \`${input.oxygen_pct.toFixed(1)}% O₂\`, \`${input.pressure_kpa.toFixed(1)} kPa\`, \`${input.airflow_velocity_cms.toFixed(1)} cm/s\` HVAC flow`,
    `- **Material / Specimen:** ${input.fuel_material}`,
    `- **Determination:** **${certStatus}** — Risk Level: **${sim.risk_level}** (${sim.risk_score.toFixed(2)})`,
    '',
    `## Physics & Flammability Summary`,
    `- Sustained Burn Probability: **${(sim.sustained_burn_probability * 100).toFixed(1)}%**`,
    `- Predicted Burn / Spread Rate: **${sim.predicted_burning_rate_mms.toFixed(2)} mm/s**`,
    `- Predicted Flame Temp: **${sim.predicted_flame_temp_k.toFixed(0)} K**`,
    sim.physics_diagnostics
      ? `- 0g MOC Limit: **${sim.physics_diagnostics.moc_0g_limit_o2_pct.toFixed(1)}% O₂** vs. 1g NASA-STD-6001: **${sim.physics_diagnostics.moc_1g_std6001_limit_o2_pct.toFixed(1)}% O₂**`
      : '',
    '',
    `## NASA-STD-6001 Comparison`,
    sim.std6001_comparison,
    '',
    `## Recommended Controls`,
    ...sim.recommendations.map((r) => `- ${r}`),
  ]
    .filter(Boolean)
    .join('\n');

  const html = `<!doctype html><html><head><meta charset="utf-8"><title>${dossierId}</title>
<style>body{font-family:system-ui,-apple-system,sans-serif;max-width:780px;margin:32px auto;padding:0 20px;color:#0f172a;line-height:1.55}
h1{font-size:20px;border-bottom:2px solid #0284c7;padding-bottom:8px}
.badge{display:inline-block;padding:4px 10px;border-radius:6px;background:#e0f2fe;color:#0369a1;font-weight:700;font-size:13px}
pre{white-space:pre-wrap;background:#f8fafc;padding:16px;border:1px solid #cbd5e1;border-radius:8px}</style></head>
<body><span class="badge">${certStatus} · ${sim.risk_level} (${sim.risk_score.toFixed(2)})</span>
<h1>${dossierId} — IGNIS Mission Fire-Safety Dossier (Static Demo)</h1>
<pre>${md.replace(/&/g, '&amp;').replace(/</g, '&lt;')}</pre>
<script>window.print && setTimeout(() => window.print(), 250);</script></body></html>`;

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
