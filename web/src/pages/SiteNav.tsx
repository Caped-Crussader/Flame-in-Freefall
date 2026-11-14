import { useEffect, useState } from 'react';
import type { Route } from './util';

const LINKS: { id: Route; idx: string; label: string; cta?: boolean }[] = [
  { id: 'home', idx: '01', label: 'Overview' },
  { id: 'explorer', idx: '02', label: 'Explorer' },
  { id: 'insights', idx: '03', label: 'Physics Lab' },
  { id: 'simulator', idx: '04', label: 'Risk Simulator' },
  { id: 'dashboard', idx: '05', label: 'Analytics' },
  { id: 'ask', idx: 'AI', label: 'Ask IGNIS', cta: true },
];

export function SiteNav({ route }: { route: Route }) {
  const [light, setLight] = useState(
    () => document.documentElement.dataset.theme === 'light',
  );
  useEffect(() => {
    if (light) document.documentElement.dataset.theme = 'light';
    else delete document.documentElement.dataset.theme;
  }, [light]);

  return (
    <header className="nx-nav" role="banner">
      <div className="nx-nav-in">
        <a className="nx-brand" href="#/">
          <span className="nx-brand-mark" aria-hidden="true" />
          <span>IGNIS</span>
          <span className="nx-brand-sub">NASA PSI · 0g FIRE</span>
        </a>
        <nav className="nx-links" aria-label="Primary navigation">
          {LINKS.map((l) => (
            <a
              key={l.id}
              href={`#/${l.id === 'home' ? '' : l.id}`}
              className={`nx-link${route === l.id ? ' on' : ''}${l.cta ? ' cta' : ''}`}
              aria-current={route === l.id ? 'page' : undefined}
            >
              {!l.cta && <span className="nx-link-idx">{l.idx}</span>}
              <span>{l.label}</span>
            </a>
          ))}
          <button
            type="button"
            className="ib"
            style={{ borderRadius: 999, padding: '6px 11px', marginLeft: 4 }}
            onClick={() => setLight((v) => !v)}
            aria-label="Toggle colour theme"
            title="Toggle dark / light mode"
          >
            {light ? '☾' : '☀'}
          </button>
        </nav>
      </div>
    </header>
  );
}
