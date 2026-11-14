import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from '../src/App';
import { ErrorState } from '../src/components/States';
import { Simulator } from '../src/pages/Simulator';
import { ApiError } from '../src/types';
import { RAW_ASK, RAW_META } from './fixtures';

const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });

afterEach(() => vi.unstubAllGlobals());

function stubFetch(askResponse: () => Response) {
  const calls: { url: string; body?: Record<string, unknown> }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      return url.endsWith('/meta') ? json(RAW_META) : askResponse();
    }),
  );
  return calls;
}

describe('ErrorState', () => {
  it('shows message, request id and a working Retry button', () => {
    const retry = vi.fn();
    render(<ErrorState error={new ApiError('boom', 'req-9', 500)} onRetry={retry} />);
    expect(screen.getByRole('alert')).toBeTruthy();
    expect(screen.getByText('boom')).toBeTruthy();
    expect(screen.getByText('req-9')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(retry).toHaveBeenCalledOnce();
  });
});

describe('App', () => {
  it('shows dataset info from /meta in the footer', async () => {
    stubFetch(() => json(RAW_ASK));
    render(<App />);
    expect(await screen.findByText('4b3139dc')).toBeTruthy();
    expect(screen.getByText('892')).toBeTruthy();
    expect(screen.getByText('52')).toBeTruthy();
  });

  it('sends only {question}, renders a resolving chip and flags the unresolved one', async () => {
    const calls = stubFetch(() => json(RAW_ASK, 200, { 'x-request-id': 'req-ok' }));
    render(<App />);
    await screen.findByText('4b3139dc');
    fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'What about PMMA?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(await screen.findByRole('button', { name: /Citation ACME-BRE-003/ })).toBeTruthy();
    const post = calls.find((c) => c.url.endsWith('/ask'));
    expect(post?.url).toBe('/api/v1/ask');
    expect(post?.body).toEqual({ question: 'What about PMMA?' });
    expect(screen.getByText('unresolved citation')).toBeTruthy();
    expect(screen.getByTestId('limitations')).toBeTruthy();
    expect(screen.getByTestId('modeled-banner')).toBeTruthy();
    expect(screen.getByText('req-ok')).toBeTruthy();
  });

  it('shows the modeled toggle as disabled because the API cannot accept it', async () => {
    stubFetch(() => json(RAW_ASK));
    render(<App />);
    await screen.findByText('4b3139dc');
    expect((screen.getByLabelText('Include modeled rows') as HTMLInputElement).disabled).toBe(true);
  });

  it('submits on Enter but not on Shift+Enter', async () => {
    const calls = stubFetch(() => json(RAW_ASK));
    render(<App />);
    await screen.findByText('4b3139dc');
    const box = screen.getByLabelText('Your question');
    fireEvent.change(box, { target: { value: 'hello' } });
    fireEvent.keyDown(box, { key: 'Enter', shiftKey: true });
    expect(calls.filter((c) => c.url.endsWith('/ask'))).toHaveLength(0);
    fireEvent.keyDown(box, { key: 'Enter' });
    await waitFor(() => expect(calls.filter((c) => c.url.endsWith('/ask'))).toHaveLength(1));
  });

  it('shows the request id on a server error and retries', async () => {
    let n = 0;
    const calls = stubFetch(() => (n++ === 0 ? json({ error_code: 'INTERNAL_SERVER_ERROR', message: 'pipeline failed', request_id: 'req-err' }, 500) : json(RAW_ASK)));
    render(<App />);
    await screen.findByText('4b3139dc');
    fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'q' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(await screen.findByText('req-err')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByRole('button', { name: /Citation ACME-BRE-003/ })).toBeTruthy();
    expect(calls.filter((c) => c.url.endsWith('/ask'))).toHaveLength(2);
  });

  it('labels the static questions as examples', async () => {
    stubFetch(() => json(RAW_ASK));
    render(<App />);
    expect(await screen.findByText('Example')).toBeTruthy();
  });

  it('renders the Grounded NASA PSI Dossiers & NTRS Literature Context panel when literature is returned', async () => {
    stubFetch(() =>
      json({
        ...RAW_ASK,
        literature: [
          {
            doc_id: 'PSI-10',
            source_type: 'NASA_PSI_DOSSIER',
            title: 'Flame Extinguishment Experiment (FLEX)',
            accession: 'PSI-10',
            acronym: 'FLEX',
            doi: '10.25966/d74a-fd73',
            url: 'https://psi.nasa.gov/investigations/PSI-10',
            authors: ['Forman A. Williams'],
            platform: 'International Space Station (ISS)',
            hardware: 'CIR-MDCA',
            related_families: ['FLEX'],
            snippet: 'Cool flames observed around 740 K in microgravity.',
            score: 0.0328,
          },
        ],
      }),
    );
    render(<App />);
    await screen.findByText('4b3139dc');
    fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'Cool flames?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(await screen.findByText(/Grounded NASA PSI Dossiers & NTRS Literature Context/)).toBeTruthy();
    expect(screen.getByText(/Flame Extinguishment Experiment \(FLEX\)/)).toBeTruthy();
    expect(screen.getByText(/Cool flames observed around 740 K in microgravity/)).toBeTruthy();
  });
});

describe('Simulator (Priority 2 & Priority 3 UI Verification)', () => {
  it('renders Physics-Informed Diagnostics, 90% CI bounds, and Detection & Suppression Advisor', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        json({
          risk_score: 0.78,
          risk_level: 'HIGH',
          sustained_burn_probability: 0.84,
          predicted_burning_rate_mms: 2.35,
          predicted_flame_temp_k: 1320,
          std6001_comparison: 'Exceeds 1g NASA-STD-6001 threshold.',
          recommendations: ['Shut off cabin ventilation fans (<1.5 cm/s).'],
          nearest_experiments: [],
          envelope: {
            pressure_grid_kpa: [30, 100],
            oxygen_grid_pct: [15, 40],
            risk_matrix: [
              [0.1, 0.2],
              [0.7, 0.8],
            ],
            moc_0g_o2_pct: [18.5, 16.2],
            moc_1g_std6001_o2_pct: [21.5, 19.2],
            airflow_grid_cms: [0, 50],
            airflow_risk_matrix: [
              [0.1, 0.2],
              [0.7, 0.8],
            ],
            material_experiments: [],
          },
          physics_diagnostics: {
            oxygen_partial_pressure_kpa: 19.21,
            normoxic_po2_ratio: 0.9,
            diluent_to_o2_ratio: 1.94,
            peclet_transport_factor: 0.83,
            moc_0g_limit_o2_pct: 18.4,
            moc_1g_std6001_limit_o2_pct: 21.6,
            moc_safety_margin_o2_pct: -15.6,
            transport_regime: 'Peak Microgravity Ventilation Hazard (1.5–25 cm/s)',
          },
          uncertainty: {
            burning_rate_ci90_mms: [1.45, 3.65],
            flame_temp_ci90_k: [1120, 1540],
            sustained_prob_std: 0.12,
            confidence_score: 0.85,
            confidence_level: 'HIGH',
          },
          detection_suppression: {
            recommended_detector_modality:
              'Dual-Wavelength Laser Scattering Photoelectric + CO Sensor (ISS / Orion Multi-Angle)',
            smoke_cmd_0g_um: 0.42,
            smoke_cmd_1g_um: 0.14,
            photoelectric_sensitivity: 0.91,
            ionization_sensitivity: 0.64,
            estimated_alarm_time_s: 16.1,
            detector_rationale:
              'Overheated Kapton wire pyrolysis in microgravity yields larger aerosol Count Median Diameter (CMD ~0.42 μm).',
            lunar_dust_discrimination_note:
              'Use DAFT M₁/M₀ aerosol moment-ratio discrimination to separate coarse regolith (>1.0 μm) from smoke.',
            primary_extinguishant: 'Portable Fine Water Mist Extinguisher (ISS USOS / Orion PFE)',
            secondary_extinguishant: 'Concentrated CO₂ Flood (26.9% Vol Fraction)',
            required_co2_inerting_pct: 26.9,
            limiting_oxygen_index_pct: 12.8,
            extinguishant_options: [
              {
                agent_name: 'Fine Water Mist (ISS USOS / Orion Portable Fire Extinguisher)',
                suitability: 'OPTIMAL',
                effectiveness_pct: 94.0,
                mechanism_and_tradeoff: 'High latent heat of vaporization cools solid pyrolysis surfaces.',
                cited_experiments: ['SLICE-007', 'SLICE-008'],
              },
            ],
            estimated_peak_co_ppm: 182.6,
            nasa_smac_1hr_co_ppm: 55.0,
            nasa_smac_24hr_co_ppm: 20.0,
            co_toxicity_level: 'CRITICAL (>2× 1-hr NASA SMAC)',
            secondary_toxic_byproducts: ['Carbon Monoxide (CO) from pyrolysis'],
            post_fire_cleanup_steps: ['1. Immediate Crew & Ventilation Action: Shut down HVAC fans.'],
            evidence_experiments: [
              {
                experiment_id: 'SAME-AERO-001',
                dataset_family: 'SAME (Aerosol)',
                fuel_material: 'Overheated Kapton-Insulated Wire',
                co_ppm: 68.1,
                extinction_outcome: 'Pyrolysis Extinction',
                key_insight: 'SAME investigation of smoke particulate size distribution.',
              },
            ],
          },
        }),
      ),
    );

    render(<Simulator />);
    expect(await screen.findByText(/Physics-Informed Nondimensional Diagnostics/)).toBeTruthy();
    expect(screen.getByText(/90% CI: 1\.45–3\.65/)).toBeTruthy();
    expect(screen.getByText(/Spacecraft Fire Detection, Suppression & Post-Fire Cleanup Advisor/)).toBeTruthy();
    expect(screen.getAllByText(/0\.42 μm/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/Est\. Peak CO: 182\.6 ppm/)).toBeTruthy();
    expect(screen.getByText(/SAME-AERO-001/)).toBeTruthy();
    expect(screen.getByText(/Exportable Mission Fire-Safety Dossier/)).toBeTruthy();
  });
});
