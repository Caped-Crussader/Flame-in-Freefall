import { ApiError, type AskResult, type EvidenceRow, type Meta } from '../types';
import { isObj, normalizeAsk, normalizeMeta, normalizeRow } from './normalize';
import {
  askStatic,
  generateStaticDossier,
  getStaticEvaluation,
  getStaticExperimentDetail,
  getStaticExperiments,
  getStaticInsightsRanking,
  getStaticMeta,
  isStaticDemoMode,
  markStaticDemoMode,
  simulateStaticRisk,
} from './staticDemo';

const BASE = '/api/v1';

async function toApiError(res: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON error body */
  }
  let message = `${res.status} ${res.statusText}`.trim();
  let requestId = res.headers.get('x-request-id');
  if (isObj(body)) {
    if (typeof body.request_id === 'string') requestId = body.request_id;
    const d = body.detail ?? body.message ?? body.error;
    if (typeof d === 'string') message = d;
    else if (isObj(d) && typeof d.message === 'string') message = d.message;
  }
  return new ApiError(message, requestId, res.status);
}

class StaticBackendUnavailableError extends Error {}

function isJsonContentType(res: Response): boolean {
  const ct = (res.headers.get('content-type') || '').toLowerCase();
  return ct.includes('application/json');
}

async function request(path: string, init?: RequestInit): Promise<{ json: unknown; requestId: string | null }> {
  if (isStaticDemoMode()) {
    throw new StaticBackendUnavailableError('Static demo mode active');
  }
  let res: Response;
  try {
    res = await fetch(BASE + path, init);
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e;
    throw new StaticBackendUnavailableError('Could not reach the server. Check that the backend is running.');
  }
  if (res.status === 404 || res.status === 405 || !isJsonContentType(res)) {
    throw new StaticBackendUnavailableError(`API endpoint unavailable (${res.status || 'non-JSON'})`);
  }
  if (!res.ok) throw await toApiError(res);
  return { json: await res.json(), requestId: res.headers.get('x-request-id') };
}

async function withStaticFallback<T>(
  liveCall: () => Promise<T>,
  staticCall: () => Promise<T>,
): Promise<T> {
  try {
    return await liveCall();
  } catch (err) {
    if (err instanceof StaticBackendUnavailableError) {
      try {
        const res = await staticCall();
        markStaticDemoMode();
        return res;
      } catch {
        throw new ApiError(err.message);
      }
    }
    throw err;
  }
}

export async function getMeta(signal?: AbortSignal): Promise<Meta> {
  const json = await withStaticFallback(
    async () => (await request('/meta', { signal })).json,
    () => getStaticMeta(),
  );
  return normalizeMeta(json);
}

/** One request, one response. No streaming. */
export async function ask(question: string, signal?: AbortSignal): Promise<AskResult> {
  const { json, requestId } = await withStaticFallback(
    () =>
      request('/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
        signal,
      }),
    async () => ({ json: await askStatic(question), requestId: 'static-demo' }),
  );
  return normalizeAsk(json, requestId);
}

export interface PaginatedExperiments {
  total: number;
  limit: number;
  offset: number;
  items: EvidenceRow[];
}

export async function getExperiments(
  params: {
    dataset_family?: string;
    fuel_material?: string;
    gravity_condition?: string;
    include_modeled?: boolean;
    limit?: number;
    offset?: number;
  },
  signal?: AbortSignal,
): Promise<PaginatedExperiments> {
  return withStaticFallback(
    async () => {
      const qs = new URLSearchParams();
      if (params.dataset_family && params.dataset_family !== 'All') qs.set('dataset_family', params.dataset_family);
      if (params.fuel_material && params.fuel_material !== 'All') qs.set('fuel_material', params.fuel_material);
      if (params.gravity_condition && params.gravity_condition !== 'All') qs.set('gravity_condition', params.gravity_condition);
      if (params.include_modeled !== undefined) qs.set('include_modeled', String(params.include_modeled));
      qs.set('limit', String(params.limit ?? 100));
      qs.set('offset', String(params.offset ?? 0));
      const { json } = await request(`/experiments?${qs.toString()}`, { signal });
      const raw = json as { total?: number; limit?: number; offset?: number; items?: unknown[] };
      const items = (Array.isArray(raw.items) ? raw.items : [])
        .map(normalizeRow)
        .filter((r): r is EvidenceRow => r !== null);
      return {
        total: typeof raw.total === 'number' ? raw.total : items.length,
        limit: typeof raw.limit === 'number' ? raw.limit : 100,
        offset: typeof raw.offset === 'number' ? raw.offset : 0,
        items,
      };
    },
    () => getStaticExperiments(params),
  );
}

export async function getExperimentDetail(id: string, signal?: AbortSignal): Promise<EvidenceRow> {
  return withStaticFallback(
    async () => {
      const { json } = await request(`/experiments/${encodeURIComponent(id)}`, { signal });
      return json as EvidenceRow;
    },
    () => getStaticExperimentDetail(id),
  );
}

export interface InsightsPayload {
  findings: {
    rank: number;
    title: string;
    severity: string;
    score: number;
    families: string[];
    key_citations: string[];
    summary: string;
    actionable_recommendation: string;
  }[];
  family_rankings: {
    dataset_family: string;
    experiments_count: number;
    criticality_score: number;
    sustained_burn_rate_pct: number;
    mean_oxygen_pct: number;
    max_oxygen_pct: number;
    min_pressure_kpa: number;
    mean_burning_rate_mms: number | null;
    mean_flame_temp_k: number | null;
    sample_id: string;
  }[];
  historical_incidents: {
    incident_id: string;
    name: string;
    date: string;
    mission: string;
    severity: string;
    atmosphere_o2_pct: number;
    pressure_kpa: number;
    gravity_regime: string;
    ignition_source_and_fuel: string;
    what_happened: string;
    microgravity_physics_insight: string;
    matched_dataset_families: string[];
    matched_experiment_ids: string[];
    official_nasa_url: string;
  }[];
  psi_dossiers: {
    accession: string;
    acronym: string;
    title: string;
    doi: string;
    release_date: string;
    flight_program: string;
    hardware: string;
    sub_research_area: string;
    investigators: string[];
    publications_count: number;
    top_publications: { title: string; authors: string; doi: string }[];
    repo_files_count: number;
    experimental_table_files: string[];
    research_impacts: string;
  }[];
  psi_experimental_tables: {
    accession: string;
    file_name: string;
    relative_path: string;
    row_count: number;
    column_count: number;
    columns: string[];
    preview_rows: Record<string, unknown>[];
  }[];
  psi_investigations: {
    accession: string;
    acronym: string;
    title: string;
    sub_area: string;
    platform: string;
    hardware: string;
    objectives: string;
  }[];
}

export async function getInsightsRanking(signal?: AbortSignal): Promise<InsightsPayload> {
  return withStaticFallback(
    async () => {
      const { json } = await request('/insights/ranking', { signal });
      return json as InsightsPayload;
    },
    () => getStaticInsightsRanking(),
  );
}

export interface RiskSimulationInput {
  oxygen_pct: number;
  pressure_kpa: number;
  airflow_velocity_cms: number;
  fuel_material: string;
  gravity_regime?: string;
}

export interface FlammabilityEnvelope {
  pressure_grid_kpa: number[];
  oxygen_grid_pct: number[];
  risk_matrix: number[][];
  moc_0g_o2_pct: number[];
  moc_1g_std6001_o2_pct: number[];
  airflow_grid_cms: number[];
  airflow_risk_matrix: number[][];
  material_experiments: {
    experiment_id: string;
    dataset_family: string;
    fuel_material: string;
    oxygen_pct: number;
    pressure_kpa: number;
    airflow_velocity_cms: number;
    extinction_outcome: string;
    sustained: boolean;
  }[];
}

export interface PhysicsDiagnostics {
  oxygen_partial_pressure_kpa: number;
  normoxic_po2_ratio: number;
  diluent_to_o2_ratio: number;
  peclet_transport_factor: number;
  moc_0g_limit_o2_pct: number;
  moc_1g_std6001_limit_o2_pct: number;
  moc_safety_margin_o2_pct: number;
  transport_regime: string;
}

export interface UncertaintyBounds {
  sustained_prob_std: number;
  burning_rate_ci90_mms: [number, number];
  flame_temp_ci90_k: [number, number];
  confidence_level: string;
  confidence_score: number;
}

export interface ExtinguishantOption {
  agent_name: string;
  suitability: string;
  effectiveness_pct: number;
  mechanism_and_tradeoff: string;
  cited_experiments: string[];
}

export interface DetectionEvidenceRow {
  experiment_id: string;
  dataset_family: string;
  fuel_material: string;
  co_ppm: number | null;
  extinction_outcome: string;
  key_insight: string;
}

export interface DetectionSuppressionAdvisor {
  recommended_detector_modality: string;
  smoke_cmd_0g_um: number;
  smoke_cmd_1g_um: number;
  photoelectric_sensitivity: number;
  ionization_sensitivity: number;
  estimated_alarm_time_s: number;
  detector_rationale: string;
  lunar_dust_discrimination_note: string;
  primary_extinguishant: string;
  secondary_extinguishant: string;
  required_co2_inerting_pct: number;
  limiting_oxygen_index_pct: number;
  extinguishant_options: ExtinguishantOption[];
  estimated_peak_co_ppm: number;
  nasa_smac_1hr_co_ppm: number;
  nasa_smac_24hr_co_ppm: number;
  co_toxicity_level: string;
  secondary_toxic_byproducts: string[];
  post_fire_cleanup_steps: string[];
  evidence_experiments: DetectionEvidenceRow[];
}

export interface RiskSimulationResult {
  risk_score: number;
  risk_level: string;
  sustained_burn_probability: number;
  predicted_burning_rate_mms: number;
  predicted_flame_temp_k: number;
  physics_diagnostics?: PhysicsDiagnostics;
  uncertainty?: UncertaintyBounds;
  detection_suppression?: DetectionSuppressionAdvisor;
  std6001_comparison: string;
  recommendations: string[];
  nearest_experiments: {
    experiment_id: string;
    dataset_family: string;
    investigation_id: string;
    fuel_material: string;
    oxygen_pct: number | null;
    pressure_kpa: number | null;
    airflow_velocity_cms: number | null;
    burning_rate_mms: number | null;
    flame_temp_k: number | null;
    extinction_outcome: string;
    gravity_condition: string;
    distance: number;
    source_url: string;
  }[];
  envelope: FlammabilityEnvelope;
}

export async function simulateRisk(
  input: RiskSimulationInput,
  signal?: AbortSignal,
): Promise<RiskSimulationResult> {
  return withStaticFallback(
    async () => {
      const { json } = await request('/insights/risk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
        signal,
      });
      return json as RiskSimulationResult;
    },
    () => simulateStaticRisk(input),
  );
}

export interface MissionSafetyDossier {
  dossier_id: string;
  generated_at_utc: string;
  dataset_sha256: string;
  certification_status: string;
  risk_level: string;
  risk_score: number;
  markdown_report: string;
  html_printable: string;
}

export async function generateSafetyDossier(
  input: RiskSimulationInput,
  signal?: AbortSignal,
): Promise<MissionSafetyDossier> {
  return withStaticFallback(
    async () => {
      const { json } = await request('/insights/dossier', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
        signal,
      });
      return json as MissionSafetyDossier;
    },
    () => generateStaticDossier(input),
  );
}

export interface EvaluationScorecard {
  evaluated_at: string;
  parquet_sha256: string;
  planner_mode: string;
  overall_evaluated: number;
  overall_passed: number;
  overall_pass_rate: number;
  deterministic_evaluated: number;
  deterministic_passed: number;
  deterministic_pass_rate: number;
  qualitative_evaluated: number;
  qualitative_passed: number;
  qualitative_recall_at_5: number;
  qualitative_recall_at_10: number;
  plan_structural_accuracy: number;
  plan_exact_match_accuracy: number;
  category_breakdown: Record<
    string,
    { total: number; passed: number; failed: number; pass_rate: number }
  >;
  results: {
    id: string;
    category: string;
    intent: string;
    question: string;
    passed: boolean;
    plan_structural_match: boolean;
    expected_row_count: number;
    actual_row_count: number;
    recall_at_5: number | null;
    recall_at_10: number | null;
    errors: string[];
  }[];
}

export async function getEvaluation(signal?: AbortSignal): Promise<EvaluationScorecard> {
  return withStaticFallback(
    async () => {
      const { json } = await request('/evaluation', { signal });
      return json as EvaluationScorecard;
    },
    () => getStaticEvaluation(),
  );
}

export async function runEvaluation(signal?: AbortSignal): Promise<EvaluationScorecard> {
  return withStaticFallback(
    async () => {
      const { json } = await request('/evaluation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
        signal,
      });
      return json as EvaluationScorecard;
    },
    () => getStaticEvaluation(),
  );
}
