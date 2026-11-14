export type Route = 'home' | 'explorer' | 'insights' | 'simulator' | 'dashboard' | 'ask' | 'team';

export const ROUTES: Record<string, Route> = {
  '': 'home',
  '#': 'home',
  '#/': 'home',
  '#/home': 'home',
  '#/explorer': 'explorer',
  '#/insights': 'insights',
  '#/simulator': 'simulator',
  '#/dashboard': 'dashboard',
  '#/ask': 'ask',
  '#/team': 'team',
};

export function pick(m: unknown, keys: string[]): string {
  if (!m || typeof m !== 'object') return '—';
  const o = m as Record<string, unknown>;
  for (const k of keys) {
    const v = o[k];
    if (typeof v === 'string' || typeof v === 'number') return String(v);
  }
  return '—';
}

export function num(s: string): number | null {
  const n = Number(s);
  return s !== '—' && Number.isFinite(n) ? n : null;
}