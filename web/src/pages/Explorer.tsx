import { useEffect, useState } from 'react';
import { getExperiments } from '../api/client';
import { DetailDrawer } from '../components/DetailDrawer';
import { Val } from '../components/Val';
import type { EvidenceRow, Meta } from '../types';

export function Explorer({ meta }: { meta: Meta | null }) {
  const [family, setFamily] = useState<string>('All');
  const [includeModeled, setIncludeModeled] = useState<boolean>(false);
  const [search, setSearch] = useState<string>('');
  const [rows, setRows] = useState<EvidenceRow[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [selected, setSelected] = useState<EvidenceRow | null>(null);

  useEffect(() => {
    const ctl = new AbortController();
    setLoading(true);
    getExperiments(
      {
        dataset_family: family,
        include_modeled: includeModeled,
        limit: 200,
      },
      ctl.signal,
    )
      .then((res) => {
        setRows(res.items);
        setTotal(res.total);
        setLoading(false);
      })
      .catch(() => setLoading(false));
    return () => ctl.abort();
  }, [family, includeModeled]);

  const families = ['All', ...(meta?.dataset_families ?? [])];

  const filtered = rows.filter((r) => {
    if (!search.trim()) return true;
    const q = search.trim().toLowerCase();
    return (
      String(r.experiment_id ?? '').toLowerCase().includes(q) ||
      String(r.fuel_material ?? '').toLowerCase().includes(q) ||
      String(r.raw.notes ?? '').toLowerCase().includes(q) ||
      String(r.extinction_outcome ?? '').toLowerCase().includes(q)
    );
  });

  return (
    <main className="nx-page" id="main">
      <header className="nx-head nx-rise">
        <p className="nx-eyebrow">892 Validated Records · 44 Provenance Columns</p>
        <h1 className="sm">Experiment & Provenance Explorer</h1>
        <p className="nx-lead">
          Filter across 30 NASA/JAXA microgravity combustion dataset families, inspect quarantined sensor flags, and
          click any record to open its 44-column provenance dossier.
        </p>
      </header>

      <section className="nx-card" style={{ marginBottom: 24 }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
            gap: 16,
            alignItems: 'end',
          }}
        >
          <div>
            <label className="lbl-strong" htmlFor="exp-family">
              Dataset Family ({families.length - 1})
            </label>
            <select
              id="exp-family"
              value={family}
              onChange={(e) => setFamily(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 10,
                border: '1px solid rgba(56, 189, 248, 0.3)',
              }}
            >
              {families.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="lbl-strong" htmlFor="exp-search">
              Search ID / Fuel / Notes / Outcome
            </label>
            <input
              id="exp-search"
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="e.g. BASS-B1, cool flame, PMMA, Heptane..."
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 10,
                background: 'rgba(11, 16, 38, 0.85)',
                border: '1px solid rgba(106, 168, 255, 0.3)',
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingBottom: 6 }}>
            <input
              id="exp-modeled"
              type="checkbox"
              checked={includeModeled}
              onChange={(e) => setIncludeModeled(e.target.checked)}
              style={{ width: 18, height: 18 }}
            />
            <label htmlFor="exp-modeled" style={{ cursor: 'pointer', fontSize: 14 }}>
              Include 52 Modeled Partial-g Rows (<code>is_modeled=True</code>)
            </label>
          </div>
        </div>

        <div className="row between" style={{ marginTop: 16 }}>
          <span className="k">
            Showing <strong className="mono">{filtered.length}</strong> rows (of{' '}
            <strong className="mono">{total}</strong> matching server filter)
          </span>
          <span className="k">Click any Experiment ID to open full 44-column provenance drawer</span>
        </div>
      </section>

      <section className="nx-card">
        {loading ? (
          <p className="k">Loading validated experiments...</p>
        ) : (
          <div className="wrap" style={{ maxHeight: 540 }}>
            <table>
              <thead>
                <tr>
                  <th>Experiment ID</th>
                  <th>Family</th>
                  <th>Fuel / Specimen</th>
                  <th>O₂ (%)</th>
                  <th>Pressure (kPa)</th>
                  <th>Airflow (cm/s)</th>
                  <th>Burn Rate (mm/s)</th>
                  <th>Temp (K)</th>
                  <th>Outcome</th>
                  <th>Gravity</th>
                  <th>Flags</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => {
                  const id = String(r.experiment_id ?? '');
                  const flags = r.flags;
                  return (
                    <tr key={id} onClick={() => setSelected(r)} style={{ cursor: 'pointer' }}>
                      <td>
                        <button
                          type="button"
                          className="link-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelected(r);
                          }}
                        >
                          {id}
                        </button>
                        {Boolean(r.is_modeled) && <span className="tag i">MODELED</span>}
                      </td>
                      <td>
                        <Val v={r.dataset_family} />
                      </td>
                      <td>
                        <Val v={r.fuel_material} />
                      </td>
                      <td>
                        <Val v={r.oxygen_pct} />
                      </td>
                      <td>
                        <Val v={r.pressure_kpa} />
                      </td>
                      <td>
                        <Val v={r.raw.airflow_velocity_cms as number | null} />
                      </td>
                      <td>
                        <Val v={r.raw.burning_rate_mms as number | null} />
                      </td>
                      <td>
                        <Val v={r.raw.flame_temp_k as number | null} />
                      </td>
                      <td>
                        <Val v={r.extinction_outcome} />
                      </td>
                      <td>
                        <Val v={r.gravity_condition} />
                      </td>
                      <td>
                        {flags.length > 0 ? (
                          flags.map((fl: string) => (
                            <span key={String(fl)} className="tag flag">
                              {String(fl)}
                            </span>
                          ))
                        ) : (
                          <span className="na">CLEAN</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selected && <DetailDrawer row={selected} onClose={() => setSelected(null)} />}
    </main>
  );
}
