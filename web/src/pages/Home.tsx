import { useEffect, useState } from 'react';
import { getExperiments } from '../api/client';
import { DetailDrawer } from '../components/DetailDrawer';
import type { EvidenceRow, Meta } from '../types';
import { StatStrip } from './StatStrip';

const PROBLEMS = [
  {
    ico: '01',
    title: 'Fragmented NASA PSI archives',
    body: 'Decades of ISS, Space Shuttle, and parabolic flight combustion campaigns (BASS, Saffire, FLEX, ACME, Confined Combustion) are scattered across heterogeneous tables and PDFs.',
  },
  {
    ico: '02',
    title: 'Mixed schemas & unit systems',
    body: 'Raw experimental logs mix kPa and atm, mm/s and cm/s, K and °C. IGNIS standardizes every record into a canonical 44-column SI schema before indexing.',
  },
  {
    ico: '03',
    title: 'Zero tolerance for hallucination',
    body: 'In spacecraft fire safety, fabricated numbers are unacceptable. Every claim is grounded to a row citation [exp_id] and NASA PSI investigation dossier.',
  },
];

const STEPS = [
  {
    title: 'Ingest & Normalize',
    body: '892 experiments across 24 NASA PSI combustion investigations standardized into SI units with explicit measured vs. modeled provenance flags.',
  },
  {
    title: 'Hybrid SQL + Dense/BM25 RAG',
    body: 'Structured questions compile to validated read-only SQLite queries while hybrid BAAI/bge-small-en-v1.5 + BM25 RRF retrieves 31 NASA PSI & NTRS dossiers.',
  },
  {
    title: 'Coupled 7D Physics & ML Engine',
    body: 'Evaluates Damköhler, Peclet, and Lewis transport numbers alongside Gradient Boosting + Random Forest ensembles with 90% prediction intervals.',
  },
  {
    title: 'Audit & Safety Dossier Export',
    body: 'Validates citations, flags modeled rows, recommends ISS fire-detection/cleanup protocols (SAME, DAFT, SAFFIRE), and exports print-ready A4 safety certificates.',
  },
];

const TRUST = [
  {
    k: '01 · Measured by default',
    t: 'Synthetic or physics-augmented rows are quarantined from aggregation unless the operator explicitly opts in.',
  },
  {
    k: '02 · Double-keyed citations',
    t: 'Every inline [exp_id] badge is verified against both the retrieved context window and the SQL result set.',
  },
  {
    k: '03 · Zero silent unit coercion',
    t: 'Comparisons across incompatible measurement fields or unrecorded environmental conditions are refused with an explicit diagnostic.',
  },
  {
    k: '04 · Deterministic local fallback',
    t: 'Full SQL aggregation, physics regime diagnostics, and dossier generation operate even when external LLM APIs are offline.',
  },
];

export function Home({ meta }: { meta: Meta | null }) {
  const [sample, setSample] = useState<EvidenceRow[]>([]);
  const [selected, setSelected] = useState<EvidenceRow | null>(null);

  useEffect(() => {
    const ctl = new AbortController();
    getExperiments({ limit: 6, include_modeled: false }, ctl.signal)
      .then((r) => setSample(r.items))
      .catch(() => {});
    return () => ctl.abort();
  }, []);

  return (
    <main id="main" className="nx-page">
      {/* HERO */}
      <section className="nx-hero">
        <div className="nx-rise">
          <span className="nx-pill">
            <span className="nx-dot" />
            NASA SPACE APPS 2026 · FLAME IN FREEFALL · IGNIS v2.4
          </span>
          <h1 className="nx-h1">
            FIRE SCIENCE.
            <br />
            <span className="nx-grad">BEYOND GRAVITY.</span>
          </h1>
          <p className="nx-lead">
            In microgravity, buoyancy vanishes—flames curl into luminous diffusion
            spheres, propagate upstream against slow ventilation drafts, and
            stabilize low-temperature cool flames invisible to naked eyes.{' '}
            <strong style={{ color: 'var(--ink)' }}>IGNIS</strong> unifies 892
            standardized NASA Physical Sciences Informatics (PSI) records, 31
            mission dossiers, coupled transport physics, and citation-locked AI.
          </p>
          <div className="nx-cta-row">
            <a className="btn" href="#/simulator">
              Launch 0g Risk Simulator →
            </a>
            <a className="btn alt" href="#/insights">
              Physics &amp; ML Lab
            </a>
            <a className="btn alt" href="#/ask">
              Ask IGNIS Assistant
            </a>
          </div>
        </div>

        <div className="nx-orb-wrap nx-rise d2" aria-hidden="true">
          <div className="nx-orb" />
          <span className="nx-orb-tag t1">0g SPHERICAL DIFFUSION FLAME</span>
          <span className="nx-orb-tag t2">T_flame · 740 K (cool) – 2150 K</span>
          <span className="nx-orb-tag t3">MOC_0g &lt; MOC_1g · Pe = uL / α</span>
        </div>
      </section>

      {/* LIVE TELEMETRY COUNTERS */}
      <StatStrip meta={meta} />

      {/* 1g vs 0g INTERACTIVE REGIME STRIP */}
      <section className="nx-sec" aria-label="Gravity regime comparison">
        <div className="nx-regime-strip">
          <div className="nx-regime-card">
            <div className="nx-flame-demo" aria-hidden="true">
              <div className="nx-flame-1g" />
            </div>
            <div>
              <div className="nx-card-num" style={{ color: 'var(--solar-orange)' }}>
                EARTH · 1g BUOYANT CONVECTIVE REGIME
              </div>
              <h3 style={{ margin: '4px 0 6px', fontSize: 17 }}>
                Natural Buoyancy Teardrop Plume (~50–100 cm/s)
              </h3>
              <p className="k" style={{ margin: 0, lineHeight: 1.55 }}>
                Hot combustion products rise rapidly, drawing fresh oxidizer from
                below while convective strain quenches weak near-limit flames
                (higher Minimum Oxygen Concentration).
              </p>
            </div>
          </div>

          <div className="nx-regime-card">
            <div className="nx-flame-demo" aria-hidden="true">
              <div className="nx-flame-0g" />
            </div>
            <div>
              <div className="nx-card-num">
                ORBITAL · 0g DIFFUSIVE &amp; LOW-VELOCITY VENTILATION REGIME
              </div>
              <h3 style={{ margin: '4px 0 6px', fontSize: 17 }}>
                Spherical Diffusion &amp; Oxygen-Starved Quenching
              </h3>
              <p className="k" style={{ margin: 0, lineHeight: 1.55 }}>
                Without buoyant lift, transport relies on molecular diffusion and
                HVAC drafts (2–15 cm/s)—lowering MOC by 1.5–2.5% O₂ and shifting
                smoke aerosols to larger 0.35–0.85 μm aggregates.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* PROBLEM */}
      <section className="nx-sec" aria-labelledby="s-prob">
        <div className="nx-sec-head">
          <div>
            <div className="nx-eyebrow">Why This Matters</div>
            <h2 id="s-prob" className="nx-h2">
              Three bottlenecks between raw orbital telemetry and engineering decisions
            </h2>
          </div>
        </div>
        <div className="nx-grid-3">
          {PROBLEMS.map((p, i) => (
            <article key={p.title} className={`nx-card nx-rise d${i + 1}`}>
              <div className="nx-ico">{p.ico}</div>
              <h3>{p.title}</h3>
              <p>{p.body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="nx-sec" aria-labelledby="s-how">
        <div className="nx-sec-head">
          <div>
            <div className="nx-eyebrow">Architecture Pipeline</div>
            <h2 id="s-how" className="nx-h2">
              From raw NASA PSI experimental logs to audited mission dossiers
            </h2>
          </div>
          <a className="btn alt" href="#/dashboard">
            Inspect Corpus Coverage →
          </a>
        </div>
        <div className="nx-steps">
          {STEPS.map((s) => (
            <div key={s.title} className="nx-step">
              <h3 style={{ margin: '0 0 8px' }}>{s.title}</h3>
              <p className="k" style={{ margin: 0, lineHeight: 1.55 }}>
                {s.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* LIVE SAMPLE PREVIEW */}
      {sample.length > 0 && (
        <section className="nx-sec" aria-labelledby="s-live">
          <div className="nx-sec-head">
            <div>
              <div className="nx-eyebrow">Live Corpus Telemetry</div>
              <h2 id="s-live" className="nx-h2">
                Measured NASA microgravity experiments from the indexed store
              </h2>
            </div>
            <a className="btn alt" href="#/explorer">
              Browse Full Provenance Explorer →
            </a>
          </div>
          <div className="nx-grid-3">
            {sample.map((r) => {
              const id = String(r.experiment_id ?? '');
              const burnRate = r.raw.burning_rate_mms as number | null | undefined;
              const flameTemp = r.raw.flame_temp_k as number | null | undefined;
              const notes = String(r.raw.notes ?? r.extinction_outcome ?? 'Click to inspect 44-column provenance dossier.');
              return (
                <button
                  key={id}
                  type="button"
                  className="nx-card nx-exp-card"
                  onClick={() => setSelected(r)}
                >
                  <div>
                    <div className="row between">
                      <span className="nx-card-num">{id}</span>
                      <span className="tag d">{r.gravity_condition ?? '0g'}</span>
                    </div>
                    <h3>
                      {r.fuel_material ?? 'Fuel Specimen'} · {r.dataset_family ?? 'PSI'}
                    </h3>
                    <p>{notes}</p>
                  </div>
                  <div className="nx-exp-meta">
                    <div>
                      <span className="k">O₂</span>
                      <b>{r.oxygen_pct != null ? `${r.oxygen_pct}%` : '—'}</b>
                    </div>
                    <div>
                      <span className="k">Burn rate</span>
                      <b>{burnRate != null ? `${burnRate} mm/s` : '—'}</b>
                    </div>
                    <div>
                      <span className="k">Temp</span>
                      <b>{flameTemp != null ? `${flameTemp} K` : '—'}</b>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* TRUST */}
      <section className="nx-sec" aria-labelledby="s-trust">
        <div className="nx-sec-head">
          <div>
            <div className="nx-eyebrow">Epistemic Integrity</div>
            <h2 id="s-trust" className="nx-h2">
              Engineered to refuse before it fabricates
            </h2>
          </div>
        </div>
        <div className="nx-grid-4">
          {TRUST.map((g) => (
            <div key={g.k} className="nx-card">
              <div className="nx-card-num">{g.k}</div>
              <p style={{ marginTop: 10, color: 'var(--ink)' }}>{g.t}</p>
            </div>
          ))}
        </div>
      </section>

      {selected && <DetailDrawer row={selected} onClose={() => setSelected(null)} />}
    </main>
  );
}
