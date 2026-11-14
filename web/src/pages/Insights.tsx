import { useEffect, useState } from 'react';
import { getInsightsRanking, type InsightsPayload } from '../api/client';

type Tab = 'findings' | 'incidents' | 'families' | 'psi';

export function Insights() {
  const [data, setData] = useState<InsightsPayload | null>(null);
  const [tab, setTab] = useState<Tab>('findings');
  const [tableIdx, setTableIdx] = useState<number>(0);

  useEffect(() => {
    const ctl = new AbortController();
    getInsightsRanking(ctl.signal)
      .then(setData)
      .catch(() => undefined);
    return () => ctl.abort();
  }, []);

  const findings = data?.findings ?? [];
  const incidents = data?.historical_incidents ?? [];
  const families = data?.family_rankings ?? [];
  const dossiers = data?.psi_dossiers ?? [];
  const psiTables = data?.psi_experimental_tables ?? [];
  const activeTable = psiTables[tableIdx] ?? null;

  return (
    <main className="nx-page" id="main">
      <header className="nx-head nx-rise">
        <p className="nx-eyebrow">Mission Fire-Safety Synthesis · Live NASA PSI Repository</p>
        <h1 className="sm">Ranked Fire-Safety Insights & Case Studies</h1>
        <p className="nx-lead">
          Synthesized criticality rankings across 30 dataset families, historical spacecraft fire emergencies mapped to
          empirical flight tests, and live NASA PSI experimental CSV tables.
        </p>
      </header>

      <div className="nx-actions" style={{ marginBottom: 24 }}>
        <button
          type="button"
          className={'nx-btn ' + (tab === 'findings' ? '' : 'ghost')}
          onClick={() => setTab('findings')}
        >
          🏆 Top 5 Ranked Findings
        </button>
        <button
          type="button"
          className={'nx-btn ' + (tab === 'incidents' ? '' : 'ghost')}
          onClick={() => setTab('incidents')}
        >
          🚀 Historical Spacecraft Incidents (4)
        </button>
        <button
          type="button"
          className={'nx-btn ' + (tab === 'families' ? '' : 'ghost')}
          onClick={() => setTab('families')}
        >
          📈 Family Criticality Ranking (30)
        </button>
        <button
          type="button"
          className={'nx-btn ' + (tab === 'psi' ? '' : 'ghost')}
          onClick={() => setTab('psi')}
        >
          🛰️ Live NASA PSI Tables & Dossiers
        </button>
      </div>

      {tab === 'findings' && (
        <div className="nx-grid" style={{ gap: 18 }}>
          {findings.map((f) => (
            <article className="nx-card" key={f.rank}>
              <div className="row between" style={{ marginBottom: 8 }}>
                <span className="nx-tag">
                  #{f.rank} · {f.severity}
                </span>
                <span className="mono" style={{ color: '#fdba74', fontWeight: 700 }}>
                  Criticality Score: {f.score} / 100
                </span>
              </div>
              <h3 style={{ fontSize: '1.22rem', marginBottom: 10 }}>{f.title}</h3>
              <p style={{ marginBottom: 12 }}>{f.summary}</p>
              <div
                style={{
                  padding: '12px 16px',
                  borderRadius: 12,
                  background: 'rgba(252, 61, 33, 0.12)',
                  borderLeft: '3px solid #fc3d21',
                  marginBottom: 12,
                }}
              >
                <strong style={{ color: '#fff' }}>Actionable Spacecraft Design & Crew Recommendation: </strong>
                <span style={{ color: '#e2e8f0' }}>{f.actionable_recommendation}</span>
              </div>
              <div className="row">
                <span className="k">Dataset Families:</span>
                {f.families.map((fam) => (
                  <span key={fam} className="tag d mono">
                    {fam}
                  </span>
                ))}
                <span className="k" style={{ marginLeft: 8 }}>
                  Key Citations:
                </span>
                {f.key_citations.map((cid) => (
                  <span key={cid} className="tag i mono">
                    {cid}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}

      {tab === 'incidents' && (
        <div className="nx-grid" style={{ gap: 18 }}>
          {incidents.map((inc) => (
            <article className="nx-card" key={inc.incident_id}>
              <div className="row between" style={{ marginBottom: 10 }}>
                <div>
                  <span className="nx-tag">
                    {inc.severity} · {inc.date}
                  </span>
                  <h3 style={{ fontSize: '1.25rem' }}>{inc.name}</h3>
                </div>
                <a
                  href={inc.official_nasa_url}
                  target="_blank"
                  rel="noreferrer"
                  className="nx-btn ghost"
                  style={{ padding: '8px 16px', fontSize: 13 }}
                >
                  🔗 Official NASA Reference ↗
                </a>
              </div>

              <div className="nx-stats" style={{ marginBottom: 14 }}>
                <div className="nx-stat">
                  <b className="small">{inc.mission}</b>
                  <span>Mission / Vehicle</span>
                </div>
                <div className="nx-stat red">
                  <b>{inc.atmosphere_o2_pct.toFixed(1)}% O₂</b>
                  <span>Oxygen Concentration</span>
                </div>
                <div className="nx-stat">
                  <b>{inc.pressure_kpa.toFixed(1)} kPa</b>
                  <span>Ambient Pressure</span>
                </div>
                <div className="nx-stat">
                  <b className="small">{inc.gravity_regime}</b>
                  <span>Gravity Regime</span>
                </div>
              </div>

              <p style={{ marginBottom: 8 }}>
                <strong style={{ color: '#fff' }}>Ignition Source & Fuel Geometry: </strong>
                {inc.ignition_source_and_fuel}
              </p>
              <p style={{ marginBottom: 12 }}>
                <strong style={{ color: '#fff' }}>Incident Progression: </strong>
                {inc.what_happened}
              </p>
              <div
                style={{
                  padding: '12px 16px',
                  borderRadius: 12,
                  background: 'rgba(54, 217, 255, 0.10)',
                  borderLeft: '3px solid #36d9ff',
                  marginBottom: 12,
                }}
              >
                <strong style={{ color: '#fff' }}>Microgravity Physics & Dataset Insight: </strong>
                <span style={{ color: '#e2e8f0' }}>{inc.microgravity_physics_insight}</span>
              </div>
              <div className="row">
                <span className="k">Matched Families:</span>
                {inc.matched_dataset_families.map((fam) => (
                  <span key={fam} className="tag d mono">
                    {fam}
                  </span>
                ))}
                <span className="k" style={{ marginLeft: 8 }}>
                  Linked Experiment IDs:
                </span>
                {inc.matched_experiment_ids.map((eid) => (
                  <span key={eid} className="tag i mono">
                    {eid}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}

      {tab === 'families' && (
        <section className="nx-card">
          <h3>30 Dataset Families Ranked by Spacecraft Fire-Safety Criticality</h3>
          <p className="k" style={{ marginBottom: 18 }}>
            Weighted index combining sustained flammability fraction, high-O₂ exploration atmosphere coverage, reduced
            pressure testing, and sample volume.
          </p>
          {families.slice(0, 15).map((f) => (
            <div className="nx-bar" key={f.dataset_family}>
              <div className="nx-bar-top">
                <span>
                  <strong>{f.dataset_family}</strong> ({f.experiments_count} tests · max {f.max_oxygen_pct}% O₂)
                </span>
                <span className="mono">
                  Score: <strong>{f.criticality_score}</strong>/100 · Sustained: {f.sustained_burn_rate_pct}%
                </span>
              </div>
              <div className="nx-track">
                <div
                  className={'nx-fill' + (f.criticality_score >= 55 ? ' hot' : '')}
                  style={{ width: `${Math.min(100, f.criticality_score)}%` }}
                />
              </div>
            </div>
          ))}
        </section>
      )}

      {tab === 'psi' && (
        <div className="nx-grid" style={{ gap: 20 }}>
          {psiTables.length > 0 && (
            <section className="nx-card">
              <div className="row between" style={{ marginBottom: 14 }}>
                <div>
                  <h3>🧪 Downloaded Live NASA PSI Experimental CSV Tables</h3>
                  <p className="k">
                    Fetched from <code>https://psi.nasa.gov/geode-py/ws</code> with verified TLS intermediate bundle
                  </p>
                </div>
                <select
                  value={tableIdx}
                  onChange={(e) => setTableIdx(Number(e.target.value))}
                  style={{
                    padding: '9px 14px',
                    borderRadius: 10,
                    background: 'rgba(11, 16, 38, 0.9)',
                    border: '1px solid rgba(106, 168, 255, 0.35)',
                  }}
                >
                  {psiTables.map((t, idx) => (
                    <option key={t.file_name} value={idx}>
                      {t.accession} — {t.file_name} ({t.row_count} rows × {t.column_count} cols)
                    </option>
                  ))}
                </select>
              </div>

              {activeTable && (
                <div className="wrap" style={{ maxHeight: 380 }}>
                  <table>
                    <thead>
                      <tr>
                        {activeTable.columns.map((col) => (
                          <th key={col}>{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {activeTable.preview_rows.slice(0, 35).map((row, rIdx) => (
                        <tr key={rIdx}>
                          {activeTable.columns.map((col) => (
                            <td key={col}>{row[col] !== null && row[col] !== undefined ? String(row[col]) : '—'}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          <div className="nx-grid three">
            {dossiers.map((d) => (
              <article className="nx-card" key={d.accession}>
                <span className="nx-tag">
                  {d.accession} · {d.acronym}
                </span>
                <h3>{d.title}</h3>
                <p className="k" style={{ margin: '8px 0' }}>
                  DOI: <span className="mono">{d.doi || 'N/A'}</span> · Hardware: {d.hardware || 'CIR / MSG'} · Papers:{' '}
                  <strong>{d.publications_count}</strong> · Repo Files: <strong>{d.repo_files_count}</strong>
                </p>
                {d.investigators.length > 0 && (
                  <p style={{ fontSize: 13, marginBottom: 10 }}>
                    <strong style={{ color: '#fff' }}>Investigators:</strong> {d.investigators.join(', ')}
                  </p>
                )}
                {d.top_publications.slice(0, 2).map((p) => (
                  <p key={p.title} style={{ fontSize: 12, marginTop: 6, color: '#cbd5e1' }}>
                    • <em>{p.title}</em> ({p.authors})
                  </p>
                ))}
              </article>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
