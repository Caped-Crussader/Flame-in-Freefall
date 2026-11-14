import { ApiError, type AskResult, type EvidenceRow, type Meta } from '../types';
import { isObj, normalizeAsk, normalizeMeta, normalizeRow } from './normalize';

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

async function request(path: string, init?: RequestInit): Promise<{ json: unknown; requestId: string | null }> {
  let res: Response;
  try {
    res = await fetch(BASE + path, init);
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e;
    throw new ApiError('Could not reach the server. Check that the backend is running.');
  }
  if (!res.ok) throw await toApiError(res);
  return { json: await res.json(), requestId: res.headers.get('x-request-id') };
}

export async function getMeta(signal?: AbortSignal): Promise<Meta> {
  return normalizeMeta((await request('/meta', { signal })).json);
}

/** One request, one response. No streaming. */
export async function ask(question: string, signal?: AbortSignal): Promise<AskResult> {
  const { json, requestId } = await request('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
    signal,
  });
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
}

export async function getExperimentDetail(id: string, signal?: AbortSignal): Promise<EvidenceRow> {
  const { json } = await request(`/experiments/${encodeURIComponent(id)}`, { signal });
  return json as EvidenceRow;
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
  const { json } = await request('/insights/ranking', { signal });
  return json as InsightsPayload;
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

export interface RiskSimulationResult {
  risk_score: number;
  risk_level: string;
  sustained_burn_probability: number;
  predicted_burning_rate_mms: number;
  predicted_flame_temp_k: number;
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
  const { json } = await request('/insights/risk', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
    signal,
  });
  return json as RiskSimulationResult;
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
  const { json } = await request('/evaluation', { signal });
  return json as EvaluationScorecard;
}

export async function runEvaluation(signal?: AbortSignal): Promise<EvaluationScorecard> {
  const { json } = await request('/evaluation/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
    signal,
  });
  return json as EvaluationScorecard;
}
