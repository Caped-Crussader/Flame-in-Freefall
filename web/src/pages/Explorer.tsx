import { useEffect, useMemo, useState } from 'react';
import { getExperiments } from '../api/client';
import { DetailDrawer } from '../components/DetailDrawer';
import { Val } from '../components/Val';
import type { EvidenceRow, Meta } from '../types';

interface VariableSummary {
  fixed: { label: string; value: string }[];
  varied: { label: string; detail: string }[];
  sensors: { label: string; count: number }[];
}

function summarizeVariables(rows: EvidenceRow[]): VariableSummary {
  const uniq = (vals: (string | null | undefined)[]) =>
    Array.from(new Set(vals.map((v) => (v ?? '').trim()).filter(Boolean)));

  const numRange = (vals: unknown[], unit: string) => {
    const nums = vals.filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
    if (!nums.length) return null;
    const min = Math.min(...nums);
    const max = Math.max(...nums);
    if (Math.abs(max - min) < 1e-6) return { fixed: `${min} ${unit}`, varied: null };
    return { fixed: null, varied: `${min}–${max} ${unit} (${nums.length} runs)` };
  };

  const fixed: { label: string; value: string }[] = [];
  const varied: { label: string; detail: string }[] = [];

  const hw = uniq(rows.map((r) => r.facility_hardware));
  if (hw.length === 1) fixed.push({ label: 'Hardware Rig', value: hw[0] });
  else if (hw.length > 1) varied.push({ label: 'Hardware Rigs', detail: `${hw.length} (${hw.slice(0, 2).join(', ')}…)` });

  const grav = uniq(rows.map((r) => r.gravity_condition));
  if (grav.length === 1) fixed.push({ label: 'Gravity Regime', value: grav[0] });
  else if (grav.length > 1) varied.push({ label: 'Gravity Regimes', detail: grav.join(', ') });

  const fuels = uniq(rows.map((r) => r.fuel_material));
  if (fuels.length === 1) fixed.push({ label: 'Fuel / Specimen', value: fuels[0] });
  else if (fuels.length > 1)
    varied.push({ label: 'Fuels / Specimens', detail: `${fuels.length} distinct (${fuels.slice(0, 3).join(', ')}${fuels.length > 3 ? '…' : ''})` });

  const flowDir = uniq(rows.map((r) => r.raw.flow_direction as string | null | undefined));
  if (flowDir.length === 1) fixed.push({ label: 'Flow Direction', value: flowDir[0] });
  else if (flowDir.length > 1) varied.push({ label: 'Flow Directions', detail: flowDir.join(' vs. ') });

  const checks: [string, unknown[], string][] = [
    ['O₂ Concentration', rows.map((r) => r.oxygen_pct), '% O₂'],
    ['Cabin Pressure', rows.map((r) => r.pressure_kpa), 'kPa'],
    ['Airflow Velocity', rows.map((r) => r.raw.airflow_velocity_cms), 'cm/s'],
    ['Sample / Droplet Diameter', rows.map((r) => r.raw.initial_diameter_mm), 'mm'],
    ['Specimen Thickness', rows.map((r) => r.raw.specimen_thickness_cm), 'cm'],
  ];

  for (const [label, vals, unit] of checks) {
    const res = numRange(vals, unit);
    if (!res) continue;
    if (res.fixed) fixed.push({ label, value: res.fixed });
    else if (res.varied) varied.push({ label, detail: res.varied });
  }

  const sensorDefs: [string, string][] = [
    ['Flame Temp (K)', 'flame_temp_k'],
    ['Burn / Spread Rate (mm/s)', 'burning_rate_mms'],
    ['CO Yield (ppm)', 'co_ppm'],
    ['Extinction Dia. (mm)', 'extinction_diameter_mm'],
    ['Burn Time (s)', 'burn_time_s'],
    ['Ignition Power (W)', 'ignition_power_w'],
  ];
  const sensors = sensorDefs
    .map(([label, key]) => ({
      label,
      count: rows.filter((r) => typeof r.raw[key] === 'number' && Number.isFinite(r.raw[key] as number)).length,
    }))
    .filter((s) => s.count > 0);

  return { fixed, varied, sensors };
}

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

  const filtered = useMemo(
    () =>
      rows.filter((r) => {
        if (!search.trim()) return true;
        const q = search.trim().toLowerCase();
        return (
          String(r.experiment_id ?? '').toLowerCase().includes(q) ||
          String(r.fuel_material ?? '').toLowerCase().includes(q) ||
          String(r.raw.notes ?? '').toLowerCase().includes(q) ||
          String(r.extinction_outcome ?? '').toLowerCase().includes(q)
        );
      }),
    [rows, search],
  );

  const varSummary = useMemo(() => summarizeVariables(filtered), [filtered]);

  return (
    <main className="nx-page" id="main">
      <header className="nx-head nx-rise">
        <p className="nx-eyebrow">892 Validated Records · 44 Provenance Columns</p>
        <h1 className="sm">Experiment & Provenance Explorer</h1>
        <p className="nx-lead">
          Filter across 30 NASA/JAXA microgravity combustion dataset families, inspect fixed vs. varied parameters
          within each investigation, and click any record to open its 44-column provenance dossier.
        </p>
      </header>

      <section className="nx-card" style={{ marginBottom: 20 }}>
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

      {!loading && filtered.length > 0 && (
        <section
          className="nx-card"
          style={{ marginBottom: 20, padding: '16px 20px' }}
          aria-label="Investigation variable matrix"
        >
          <div className="row between" style={{ marginBottom: 12 }}>
            <div className="nx-card-num">
              {family === 'All'
                ? 'CORPUS-WIDE PARAMETER & MEASUREMENT SUMMARY'
                : `${family.toUpperCase()} — FIXED VS. VARIED EXPERIMENTAL VARIABLES`}
            </div>
            <span className="k mono" style={{ fontSize: 11 }}>
              {filtered.length} runs analyzed
            </span>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: 14,
            }}
          >
            <div>
              <div className="k" style={{ fontSize: 12, marginBottom: 6 }}>
                <strong style={{ color: 'var(--electric-cyan)' }}>Fixed / Controlled</strong> (Same across visible runs)
              </div>
              {varSummary.fixed.length > 0 ? (
                <div className="row">
                  {varSummary.fixed.map((item) => (
                    <span key={item.label} className="tag d mono" title={item.label}>
                      {item.label}: {item.value}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="k" style={{ fontSize: 12 }}>
                  Multiple hardware/atmospheres — filter to one family to isolate fixed rig parameters.
                </p>
              )}
            </div>

            <div>
              <div className="k" style={{ fontSize: 12, marginBottom: 6 }}>
                <strong style={{ color: 'var(--solar-orange)' }}>Varied Test Conditions</strong> (Swept across runs)
              </div>
              {varSummary.varied.length > 0 ? (
                <div className="row">
                  {varSummary.varied.map((item) => (
                    <span key={item.label} className="tag i mono">
                      {item.label}: {item.detail}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="k" style={{ fontSize: 12 }}>No varied numerical sweeps detected in current selection.</p>
              )}
            </div>

            <div>
              <div className="k" style={{ fontSize: 12, marginBottom: 6 }}>
                <strong style={{ color: 'var(--ok)' }}>Sensors / Measured Observables</strong>
              </div>
              {varSummary.sensors.length > 0 ? (
                <div className="row">
                  {varSummary.sensors.map((s) => (
                    <span key={s.label} className="tag mono">
                      {s.label} ({s.count})
                    </span>
                  ))}
                </div>
              ) : (
                <p className="k" style={{ fontSize: 12 }}>Categorical extinction outcomes only.</p>
              )}
            </div>
          </div>
        </section>
      )}

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
