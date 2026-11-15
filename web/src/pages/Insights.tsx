import { useEffect, useMemo, useState } from 'react';
import { getInsightsRanking, type InsightsPayload } from '../api/client';

type Tab = 'findings' | 'incidents' | 'families' | 'compare' | 'psi';

type PsiInv = InsightsPayload['psi_investigations'][number];
type FamilyStat = InsightsPayload['family_rankings'][number];

function matchFamilyStats(inv: PsiInv | undefined, rankings: FamilyStat[]): FamilyStat[] {
  if (!inv) return [];
  const acr = (inv.acronym || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  const titleUp = (inv.title || '').toUpperCase();
  return rankings.filter((f) => {
    const famUp = f.dataset_family.toUpperCase();
    const famNorm = famUp.replace(/[^A-Z0-9]/g, '');
    if (acr && (famNorm.includes(acr) || acr.includes(famNorm))) return true;
    if (acr === 'CFI' && famUp.includes('CFI')) return true;
    if (acr === 'EFIELD' && famUp.includes('EFIELD')) return true;
    if (acr === 'SAFFIRE' && famUp.includes('SAFFIRE')) return true;
    if (titleUp.includes('SAME') && famUp.includes('SAME')) return true;
    if (titleUp.includes('DAFT') && famUp.includes('DAFT')) return true;
    if (titleUp.includes('SLICE') && famUp.includes('SLICE')) return true;
    if (titleUp.includes('SPICE') && famUp.includes('SPICE')) return true;
    return false;
  });
}

function InvestigationCompareCard({
  label,
  inv,
  matchedFamilies,
}: {
  label: string;
  inv: PsiInv | undefined;
  matchedFamilies: FamilyStat[];
}) {
  if (!inv) {
    return (
      <article className="nx-card">
        <span className="nx-tag">{label}</span>
        <p className="k">No investigation selected.</p>
      </article>
    );
  }
  const totalRuns = matchedFamilies.reduce((acc, f) => acc + f.experiments_count, 0);
  const maxO2 = matchedFamilies.length
    ? Math.max(...matchedFamilies.map((f) => f.max_oxygen_pct))
    : null;
  const minP = matchedFamilies.length
    ? Math.min(...matchedFamilies.map((f) => f.min_pressure_kpa))
    : null;
  const avgSustained = matchedFamilies.length
    ? matchedFamilies.reduce((acc, f) => acc + f.sustained_burn_rate_pct, 0) / matchedFamilies.length
    : null;

  return (
    <article className="nx-card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <span className="nx-tag">
          {label} · {inv.accession} {inv.acronym ? `· ${inv.acronym}` : ''}
        </span>
        <h3 style={{ fontSize: '1.15rem', marginTop: 4 }}>{inv.title}</h3>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: 10,
          padding: 12,
          borderRadius: 12,
          background: 'rgba(6, 10, 22, 0.58)',
          border: '1px solid rgba(56, 189, 248, 0.2)',
        }}
      >
        <div>
          <span className="k" style={{ fontSize: 11, display: 'block' }}>
            Hardware / Rig
          </span>
          <strong style={{ fontSize: 13 }}>{inv.hardware || 'CIR / MSG Modular Rig'}</strong>
        </div>
        <div>
          <span className="k" style={{ fontSize: 11, display: 'block' }}>
            Flight Platform
          </span>
          <strong style={{ fontSize: 13 }}>{inv.platform || 'ISS'}</strong>
        </div>
        <div>
          <span className="k" style={{ fontSize: 11, display: 'block' }}>
            Sub-Research Area
          </span>
          <strong style={{ fontSize: 13 }}>{inv.sub_area || 'Combustion Science'}</strong>
        </div>
      </div>

      <div>
        <div className="nx-card-num" style={{ marginBottom: 6 }}>
          Experimental Objectives
        </div>
        <p style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--ink)' }}>
          {inv.objectives || 'Objectives recorded in NASA PSI metadata.'}
        </p>
      </div>

      {matchedFamilies.length > 0 && (
        <div
          style={{
            marginTop: 'auto',
            paddingTop: 12,
            borderTop: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          <div className="nx-card-num" style={{ marginBottom: 8 }}>
            Matched Empirical Data ({totalRuns} Indexed Tests)
          </div>
          <div className="row" style={{ marginBottom: 8 }}>
            {matchedFamilies.slice(0, 4).map((mf) => (
              <span key={mf.dataset_family} className="tag d mono">
                {mf.dataset_family} ({mf.experiments_count})
              </span>
            ))}
          </div>
          <div className="nx-exp-meta">
            <div>
              <span className="k">Max O₂ Tested</span>
              <b>{maxO2 !== null ? `${maxO2.toFixed(1)}%` : '—'}</b>
            </div>
            <div>
              <span className="k">Min Pressure</span>
              <b>{minP !== null ? `${minP.toFixed(1)} kPa` : '—'}</b>
            </div>
            <div>
              <span className="k">Avg Sustained</span>
              <b>{avgSustained !== null ? `${avgSustained.toFixed(1)}%` : '—'}</b>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}

export function Insights() {
  const [data, setData] = useState<InsightsPayload | null>(null);
  const [tab, setTab] = useState<Tab>('findings');
  const [tableIdx, setTableIdx] = useState<number>(0);
  const [accA, setAccA] = useState<string>('');
  const [accB, setAccB] = useState<string>('');
  const [invSearch, setInvSearch] = useState<string>('');

  useEffect(() => {
    const ctl = new AbortController();
    getInsightsRanking(ctl.signal)
      .then((res) => {
        setData(res);
        const list = res.psi_investigations ?? [];
        if (list.length >= 2) {
          const same = list.find((p) => p.accession === 'PSI-102') ?? list[0];
          const daft = list.find((p) => p.accession === 'PSI-47') ?? list[1];
          setAccA(same.accession);
          setAccB(daft.accession);
        } else if (list.length === 1) {
          setAccA(list[0].accession);
          setAccB(list[0].accession);
        }
      })
      .catch(() => undefined);
    return () => ctl.abort();
  }, []);

  const findings = data?.findings ?? [];
  const incidents = data?.historical_incidents ?? [];
  const families = data?.family_rankings ?? [];
  const dossiers = data?.psi_dossiers ?? [];
  const psiTables = data?.psi_experimental_tables ?? [];
  const psiInvestigations = useMemo(() => data?.psi_investigations ?? [], [data]);
  const activeTable = psiTables[tableIdx] ?? null;

  const invA = psiInvestigations.find((p) => p.accession === accA) ?? psiInvestigations[0];
  const invB = psiInvestigations.find((p) => p.accession === accB) ?? psiInvestigations[1] ?? psiInvestigations[0];

  const filteredInvestigations = useMemo(() => {
    const q = invSearch.trim().toLowerCase();
    if (!q) return psiInvestigations;
    return psiInvestigations.filter(
      (p) =>
        p.accession.toLowerCase().includes(q) ||
        (p.acronym || '').toLowerCase().includes(q) ||
        (p.title || '').toLowerCase().includes(q) ||
        (p.hardware || '').toLowerCase().includes(q) ||
        (p.objectives || '').toLowerCase().includes(q),
    );
  }, [psiInvestigations, invSearch]);

  const applyComparePair = (idA: string, idB: string) => {
    if (psiInvestigations.some((p) => p.accession === idA)) setAccA(idA);
    if (psiInvestigations.some((p) => p.accession === idB)) setAccB(idB);
  };

  return (
    <main className="nx-page" id="main">
      <header className="nx-head nx-rise">
        <p className="nx-eyebrow">Mission Fire-Safety Synthesis · Live NASA PSI Repository</p>
        <h1 className="sm">Ranked Fire-Safety Insights & Case Studies</h1>
        <p className="nx-lead">
          Synthesized criticality rankings across 30 dataset families, historical spacecraft fire emergencies mapped to
          empirical flight tests, side-by-side PSI investigation objectives, and live CSV tables.
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
          className={'nx-btn ' + (tab === 'compare' ? '' : 'ghost')}
          onClick={() => setTab('compare')}
        >
          🔬 Investigation Objectives & Comparator ({psiInvestigations.length || 24})
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

      {tab === 'compare' && (
        <div className="nx-grid" style={{ gap: 22 }}>
          <section className="nx-card">
            <div className="row between" style={{ marginBottom: 14 }}>
              <div>
                <h3 style={{ margin: 0 }}>⚖️ Side-by-Side PSI Investigation Comparator</h3>
                <p className="k" style={{ marginTop: 4 }}>
                  Compare experimental objectives, shared modular hardware (CIR / MDCA / MSG Flow Duct), flight
                  platforms, and empirical combustion regimes across NASA PSI studies.
                </p>
              </div>
            </div>

            <div className="nx-actions" style={{ marginBottom: 16 }}>
              <button
                type="button"
                className="nx-btn ghost"
                onClick={() => applyComparePair('PSI-102', 'PSI-47')}
              >
                Smoke vs. Dust: SAME (PSI-102) vs. DAFT (PSI-47)
              </button>
              <button
                type="button"
                className="nx-btn ghost"
                onClick={() => applyComparePair('PSI-20', 'PSI-26')}
              >
                CIR Gas vs. MSG Solids: ACME-BRE (PSI-20) vs. BASS-II (PSI-26)
              </button>
              <button
                type="button"
                className="nx-btn ghost"
                onClick={() => applyComparePair('PSI-39', 'PSI-98')}
              >
                MDCA Droplets vs. Cygnus: FLEX (PSI-39) vs. Saffire (PSI-98)
              </button>
              <button
                type="button"
                className="nx-btn ghost"
                onClick={() => applyComparePair('PSI-23', 'PSI-22')}
              >
                85% O₂ Cool Flames vs. Ion Drift: CFI-G (PSI-23) vs. E-FIELD (PSI-22)
              </button>
            </div>

            <div className="nx-grid two" style={{ marginBottom: 18 }}>
              <div>
                <label className="lbl-strong" htmlFor="cmp-inv-a">
                  Investigation A
                </label>
                <select
                  id="cmp-inv-a"
                  value={invA?.accession ?? ''}
                  onChange={(e) => setAccA(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: 10,
                    border: '1px solid rgba(56, 189, 248, 0.35)',
                  }}
                >
                  {psiInvestigations.map((p) => (
                    <option key={p.accession} value={p.accession}>
                      {p.accession} {p.acronym ? `(${p.acronym})` : ''} — {p.title}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="lbl-strong" htmlFor="cmp-inv-b">
                  Investigation B
                </label>
                <select
                  id="cmp-inv-b"
                  value={invB?.accession ?? ''}
                  onChange={(e) => setAccB(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: 10,
                    border: '1px solid rgba(56, 189, 248, 0.35)',
                  }}
                >
                  {psiInvestigations.map((p) => (
                    <option key={p.accession} value={p.accession}>
                      {p.accession} {p.acronym ? `(${p.acronym})` : ''} — {p.title}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="nx-grid two">
              <InvestigationCompareCard
                label="INVESTIGATION A"
                inv={invA}
                matchedFamilies={matchFamilyStats(invA, families)}
              />
              <InvestigationCompareCard
                label="INVESTIGATION B"
                inv={invB}
                matchedFamilies={matchFamilyStats(invB, families)}
              />
            </div>
          </section>

          <section className="nx-card">
            <div className="row between" style={{ marginBottom: 14, gap: 12 }}>
              <div>
                <h3 style={{ margin: 0 }}>
                  📚 All NASA PSI Combustion Investigation Objectives ({filteredInvestigations.length})
                </h3>
                <p className="k" style={{ marginTop: 4 }}>
                  Click any investigation card to load it into Comparator Slot A or B.
                </p>
              </div>
              <input
                type="text"
                aria-label="Filter PSI investigations"
                value={invSearch}
                onChange={(e) => setInvSearch(e.target.value)}
                placeholder="Filter by acronym, CIR, MDCA, MSG, objectives..."
                style={{
                  minWidth: 260,
                  padding: '9px 12px',
                  borderRadius: 10,
                  background: 'rgba(6, 10, 22, 0.78)',
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                }}
              />
            </div>

            <div className="nx-grid three">
              {filteredInvestigations.map((p) => (
                <article
                  key={p.accession}
                  className="nx-card"
                  style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 10 }}
                >
                  <div className="row between">
                    <span className="nx-tag" style={{ marginBottom: 0 }}>
                      {p.accession} {p.acronym ? `· ${p.acronym}` : ''}
                    </span>
                    <span className="k mono" style={{ fontSize: 11 }}>
                      {p.hardware || p.platform || 'ISS'}
                    </span>
                  </div>
                  <h4 style={{ margin: 0, fontSize: 15, lineHeight: 1.35 }}>{p.title}</h4>
                  <p style={{ fontSize: 13, lineHeight: 1.55 }}>
                    {p.objectives
                      ? p.objectives.length > 260
                        ? `${p.objectives.slice(0, 260)}…`
                        : p.objectives
                      : 'No objective abstract provided in PSI metadata.'}
                  </p>
                  <div className="row" style={{ marginTop: 'auto', paddingTop: 6 }}>
                    <button
                      type="button"
                      className="ib"
                      style={{ fontSize: 12 }}
                      onClick={() => setAccA(p.accession)}
                    >
                      Set Slot A
                    </button>
                    <button
                      type="button"
                      className="ib"
                      style={{ fontSize: 12 }}
                      onClick={() => setAccB(p.accession)}
                    >
                      Set Slot B
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>
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
                    border: '1px solid rgba(56, 189, 248, 0.35)',
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
