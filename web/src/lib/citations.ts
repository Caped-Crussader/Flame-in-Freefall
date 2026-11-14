export type CitationSegment =
  | { kind: 'text'; text: string }
  | { kind: 'cite'; id: string; resolved: boolean };

const BRACKET_RE = /\[([A-Za-z0-9_.,\s-]+)\]/g;

export function parseCitations(text: string, known: ReadonlySet<string>): CitationSegment[] {
  const out: CitationSegment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  const re = new RegExp(BRACKET_RE.source, 'g');

  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIndex) {
      out.push({ kind: 'text', text: text.slice(lastIndex, match.index) });
    }
    const rawInside = match[1];
    const parts = rawInside
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    for (let i = 0; i < parts.length; i++) {
      const id = parts[i];
      out.push({ kind: 'cite', id, resolved: known.has(id) });
      if (i < parts.length - 1) {
        out.push({ kind: 'text', text: ' ' });
      }
    }
    lastIndex = re.lastIndex;
  }

  if (lastIndex < text.length || out.length === 0) {
    out.push({ kind: 'text', text: text.slice(lastIndex) });
  }
  return out;
}

interface MdNode {
  type: string;
  value?: string;
  children?: MdNode[];
  data?: Record<string, unknown>;
}

function transformNode(node: MdNode, known: ReadonlySet<string>): void {
  if (!node.children || node.type === 'code' || node.type === 'inlineCode') return;
  const nextChildren: MdNode[] = [];

  for (const child of node.children) {
    if (child.type === 'text' && typeof child.value === 'string' && child.value.includes('[')) {
      const segs = parseCitations(child.value, known);
      for (const seg of segs) {
        if (seg.kind === 'text') {
          if (seg.text) nextChildren.push({ type: 'text', value: seg.text });
        } else {
          nextChildren.push({
            type: 'citeChip',
            data: {
              hName: 'cite-chip',
              hProperties: {
                cid: seg.id,
                ok: seg.resolved ? 'true' : 'false',
              },
            },
            children: [{ type: 'text', value: seg.id }],
          });
        }
      }
    } else {
      transformNode(child, known);
      nextChildren.push(child);
    }
  }
  node.children = nextChildren;
}

export function remarkCitations(known: ReadonlySet<string>) {
  return () => (tree: MdNode) => {
    transformNode(tree, known);
  };
}
