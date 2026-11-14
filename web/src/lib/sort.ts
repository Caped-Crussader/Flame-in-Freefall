import type { EvidenceRow } from '../types';

export type SortKey =
  | 'experiment_id'
  | 'dataset_family'
  | 'fuel_material'
  | 'conditions'
  | 'extinction_outcome'
  | 'flags';

export type SortDir = 'asc' | 'desc';

function keyValue(row: EvidenceRow, key: SortKey): string | number {
  switch (key) {
    case 'experiment_id':
      return row.experiment_id ?? '';
    case 'dataset_family':
      return row.dataset_family ?? '';
    case 'fuel_material':
      return row.fuel_material ?? '';
    case 'conditions':
      return row.oxygen_pct ?? -1;
    case 'extinction_outcome':
      return row.extinction_outcome ?? '';
    case 'flags':
      return row.flags.length;
  }
}

export function sortRows(rows: EvidenceRow[], key: SortKey, dir: SortDir): EvidenceRow[] {
  const factor = dir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const va = keyValue(a, key);
    const vb = keyValue(b, key);
    if (typeof va === 'number' && typeof vb === 'number') {
      return (va - vb) * factor;
    }
    return String(va).localeCompare(String(vb)) * factor;
  });
}
