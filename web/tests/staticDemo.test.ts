import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  ask,
  generateSafetyDossier,
  getExperiments,
  getMeta,
  simulateRisk,
} from '../src/api/client';
import { resetStaticDemoMode } from '../src/api/staticDemo';
import { RAW_ASK, RAW_META } from './fixtures';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const htmlFallback = () =>
  new Response('<!doctype html><html><body>SPA Fallback</body></html>', {
    status: 200,
    headers: { 'Content-Type': 'text/html' },
  });

afterEach(() => {
  vi.unstubAllGlobals();
  resetStaticDemoMode();
});

describe('Static demo fallback for serverless static hosting (Render / GitHub Pages)', () => {
  it('falls back to /demo/*.json when /api/v1/* returns HTML SPA fallback or 404', async () => {
    const simFixture = {
      materials: {
        'SIBAL (Cotton-Fiberglass Blend)': {
          envelope: {
            pressure_grid_kpa: [30, 100],
            oxygen_grid_pct: [15, 45],
            risk_matrix: [
              [0.2, 0.3],
              [0.8, 0.9],
            ],
            moc_0g_o2_pct: [19.0, 17.0],
            moc_1g_std6001_o2_pct: [22.0, 20.0],
            airflow_grid_cms: [0, 40],
            airflow_risk_matrix: [
              [0.15, 0.25],
              [0.75, 0.85],
            ],
            material_experiments: [],
          },
          presets: {
            '34.0|56.5|10.0': {
              risk_score: 0.78,
              risk_level: 'HIGH',
              sustained_burn_probability: 0.84,
              predicted_burning_rate_mms: 2.4,
              predicted_flame_temp_k: 1350,
              std6001_comparison: 'Exceeds 1g threshold.',
              recommendations: ['Shut off fans below 1.5 cm/s.'],
              nearest_experiments: [],
              uncertainty: {
                sustained_prob_std: 0.1,
                burning_rate_ci90_mms: [1.5, 3.5],
                flame_temp_ci90_k: [1150, 1550],
                confidence_level: 'HIGH',
                confidence_score: 0.86,
              },
            },
          },
        },
      },
    };

    const expFixture = {
      items: [
        {
          experiment_id: 'BASS-II-001',
          dataset_family: 'BASS-II',
          fuel_material: 'SIBAL',
          oxygen_pct: 21,
          pressure_kpa: 101.3,
          gravity_condition: 'Microgravity (~0g)',
          extinction_outcome: 'Sustained Flame',
          is_modeled: false,
        },
        {
          experiment_id: 'MOD-001',
          dataset_family: 'Partial-g Bounded (0g+1g / E-FIELD)',
          fuel_material: 'PMMA',
          oxygen_pct: 25,
          pressure_kpa: 70,
          gravity_condition: 'Lunar (0.16g)',
          extinction_outcome: 'Sustained Flame',
          is_modeled: true,
        },
      ],
    };

    const askFixture = {
      'What about PMMA?': RAW_ASK,
    };

    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.startsWith('/api/v1/')) return htmlFallback();
        if (url.endsWith('demo/meta.json')) return json(RAW_META);
        if (url.endsWith('demo/experiments.json')) return json(expFixture);
        if (url.endsWith('demo/simulator.json')) return json(simFixture);
        if (url.endsWith('demo/ask_cache.json')) return json(askFixture);
        return new Response('Not Found', { status: 404 });
      }),
    );

    const meta = await getMeta();
    expect(meta.dataset_version).toBe('4b3139dc');

    const measuredOnly = await getExperiments({ include_modeled: false });
    expect(measuredOnly.total).toBe(1);
    expect(measuredOnly.items[0].experiment_id).toBe('BASS-II-001');

    const withModeled = await getExperiments({ include_modeled: true });
    expect(withModeled.total).toBe(2);

    const exactSim = await simulateRisk({
      oxygen_pct: 34.0,
      pressure_kpa: 56.5,
      airflow_velocity_cms: 10.0,
      fuel_material: 'SIBAL (Cotton-Fiberglass Blend)',
    });
    expect(exactSim.risk_level).toBe('HIGH');

    const interpSim = await simulateRisk({
      oxygen_pct: 40.0,
      pressure_kpa: 65.0,
      airflow_velocity_cms: 20.0,
      fuel_material: 'SIBAL (Cotton-Fiberglass Blend)',
    });
    expect(interpSim.physics_diagnostics?.oxygen_partial_pressure_kpa).toBeCloseTo(26.0, 1);

    const dossier = await generateSafetyDossier({
      oxygen_pct: 34.0,
      pressure_kpa: 56.5,
      airflow_velocity_cms: 10.0,
      fuel_material: 'SIBAL (Cotton-Fiberglass Blend)',
    });
    expect(dossier.dossier_id).toMatch(/^IGNIS-CERT-DEMO-/);
    expect(dossier.html_printable).toContain('IGNIS Mission Fire-Safety Dossier');

    const cachedAsk = await ask('What about PMMA?');
    expect(cachedAsk.evidence.map((e) => e.experiment_id)).toContain('ACME-BRE-003');

    const customAsk = await ask('Show BASS-II SIBAL flame');
    expect(customAsk.status).toBe('answered');
    expect(customAsk.evidence[0].experiment_id).toBe('BASS-II-001');
  });
});
