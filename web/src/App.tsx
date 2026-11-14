import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ask, getEvaluation, getMeta, runEvaluation, type EvaluationScorecard } from './api/client';
import { AnswerPanel } from './components/AnswerPanel';
import { DatasetFooter } from './components/DatasetFooter';
import { DetailDrawer } from './components/DetailDrawer';
import { EvidenceTable } from './components/EvidenceTable';
import { LimitationsBanner } from './components/LimitationsBanner';
import { ModeledToggle } from './components/ModeledToggle';
import { PlanPanel } from './components/PlanPanel';
import { QuestionInput } from './components/QuestionInput';
import { EmptyState, ErrorState, Loading } from './components/States';
import { EXAMPLE_QUESTIONS } from './lib/examples';
import { ApiError, MAX_QUESTION_LENGTH, type AskResult, type EvidenceRow, type Meta } from './types';

type Phase = 'idle' | 'loading' | 'done' | 'error';
type AskTab = 'qa' | 'benchmark';

interface HistoryItem {
  question: string;
  result: AskResult;
}

const MAX_HISTORY = 5;

export default function App() {
  const [activeTab, setActiveTab] = useState<AskTab>('qa');
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState<ApiError | null>(null);
  const [question, setQuestion] = useState('');
  const [phase, setPhase] = useState<Phase>('idle');
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [highlight, setHighlight] = useState<{ id: string; n: number } | null>(null);
  const [open, setOpen] = useState<EvidenceRow | null>(null);
  const last = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  // Benchmark scorecard state
  const [scorecard, setScorecard] = useState<EvaluationScorecard | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [evalCategoryFilter, setEvalCategoryFilter] = useState('ALL');

  const [metaTry, setMetaTry] = useState(0);
  const loadMeta = useCallback(() => setMetaTry((n) => n + 1), []);

  useEffect(() => {
    const ctl = new AbortController();
    getMeta(ctl.signal)
      .then((m) => {
        setMeta(m);
        setMetaError(null);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === 'AbortError') return;
        setMetaError(e instanceof ApiError ? e : new ApiError(String(e)));
      });
    return () => ctl.abort();
  }, [metaTry]);

  useEffect(() => {
    if (activeTab !== 'benchmark' || scorecard) return;
    const ctl = new AbortController();
    getEvaluation(ctl.signal)
      .then((sc) => {
        setScorecard(sc);
        setEvalError(null);
      })
      .catch(() => {
        // Optional until benchmark tab opened
      });
    return () => ctl.abort();
  }, [activeTab, scorecard]);

  useEffect(() => () => abort.current?.abort(), []);

  useEffect(() => {
    if (!highlight) return;
    const t = window.setTimeout(() => setHighlight(null), 4000);
    return () => window.clearTimeout(t);
  }, [highlight]);

  const run = useCallback(async (q: string) => {
    abort.current?.abort();
    const ctl = new AbortController();
    abort.current = ctl;
    last.current = q;
    setPhase('loading');
    setError(null);
    setHighlight(null);
    setOpen(null);
    try {
      const r = await ask(q, ctl.signal);
      setResult(r);
      setPhase('done');
      setHistory((h) => [{ question: q, result: r }, ...h].slice(0, MAX_HISTORY));
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      setError(e instanceof ApiError ? e : new ApiError(String(e)));
      setPhase('error');
    }
  }, []);

  const handleRunLiveEval = async () => {
    setEvalLoading(true);
    setEvalError(null);
    try {
      const sc = await runEvaluation();
      setScorecard(sc);
    } catch (e) {
      setEvalError(e instanceof Error ? e.message : String(e));
    } finally {
      setEvalLoading(false);
    }
  };

  const maxLen = meta?.max_question_length ?? MAX_QUESTION_LENGTH;
  const submit = () => {
    const q = question.trim();
    if (q && q.length <= maxLen) void run(q);
  };

  const evidenceIds = useMemo(() => new Set(result?.evidence.map((r) => r.experiment_id) ?? []), [result]);
  const onCite = useCallback((id: string) => setHighlight({ id, n: Date.now() }), []);

  const examples = meta && meta.examples.length > 0 ? meta.examples : EXAMPLE_QUESTIONS;
  const examplesLabel = meta && meta.examples.length > 0 ? 'Suggested' : 'Example';

  const restore = (h: HistoryItem) => {
    setQuestion(h.question);
    setResult(h.result);
    setPhase('done');
    setError(null);
    setHighlight(null);
  };

  const filteredQuestions = useMemo(() => {
    if (!scorecard) return [];
    if (evalCategoryFilter === 'ALL') return scorecard.results;
    return scorecard.results.filter((q) => q.category === evalCategoryFilter);
  }, [scorecard, evalCategoryFilter]);

  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <main id="main" className="main">
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 12,
            marginBottom: 16,
          }}
        >
          <div>
            <p className="nx-eyebrow" style={{ margin: 0 }}>
              BGE-small-en-v1.5 (384-d Neural) + BM25 Lexical + RRF + Deterministic SQL
            </p>
            <h1 style={{ margin: '4px 0 0', fontSize: 26 }}>Ask IGNIS & Golden Benchmark</h1>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              type="button"
              className={activeTab === 'qa' ? 'nx-btn' : 'nx-btn ghost'}
              onClick={() => setActiveTab('qa')}
              style={{ cursor: 'pointer', padding: '8px 16px', fontSize: 13 }}
            >
              💬 Grounded Q&A
            </button>
            <button
              type="button"
              className={activeTab === 'benchmark' ? 'nx-btn' : 'nx-btn ghost'}
              onClick={() => setActiveTab('benchmark')}
              style={{ cursor: 'pointer', padding: '8px 16px', fontSize: 13 }}
            >
              📊 65-Question Benchmark{' '}
              {scorecard
                ? `(${scorecard.overall_passed}/${scorecard.overall_evaluated} · ${(scorecard.overall_pass_rate * 100).toFixed(0)}%)`
                : ''}
            </button>
          </div>
        </div>

        {activeTab === 'qa' ? (
          <>
            <QuestionInput
              value={question}
              onChange={setQuestion}
              onSubmit={submit}
              disabled={phase === 'loading'}
              maxLength={maxLen}
              examples={examples}
              examplesLabel={examplesLabel}
            />
            <ModeledToggle
              checked={phase === 'done' && result?.plan?.include_modeled === true}
              modeledRows={meta?.modeled_rows ?? null}
            />

            <div className="results" aria-live="polite" aria-busy={phase === 'loading'}>
              {phase === 'idle' && <EmptyState />}
              {phase === 'loading' && <Loading />}
              {phase === 'error' && error && (
                <ErrorState
                  error={error}
                  onRetry={() => last.current && void run(last.current)}
                />
              )}
              {phase === 'done' && result && (
                <>
                  <LimitationsBanner
                    status={result.status}
                    limitations={result.limitations}
                    modeledIncluded={result.modeled_included}
                    warnings={result.warnings}
                  />
                  {(result.status === 'answered' || result.answer) && (
                    <AnswerPanel answer={result.answer} evidenceIds={evidenceIds} onCite={onCite} />
                  )}
                  <PlanPanel
                    plan={result.plan}
                    evidenceCount={result.evidence.length}
                    exclusions={result.exclusions}
                    aggregateCount={result.aggregates.length}
                  />
                  <EvidenceTable rows={result.evidence} highlight={highlight} onOpen={setOpen} />
                  {result.literature && result.literature.length > 0 && (
                    <section className="card" aria-label="Grounded NASA Literature and PSI Dossiers">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                        <h2 style={{ margin: 0 }}>📚 Grounded NASA PSI Dossiers & NTRS Literature Context</h2>
                        <span className="tag mono">
                          Multi-Doc Hybrid RAG ({result.literature.length} Passages)
                        </span>
                      </div>
                      <p className="k" style={{ marginTop: 4, marginBottom: 12 }}>
                        Retrieved in parallel from 24 official NASA Physical Sciences Informatics (PSI) investigation
                        dossiers and 7 curated NASA Technical Reports Server (NTRS) & Researcher&apos;s Guide documents.
                      </p>
                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))',
                          gap: 12,
                        }}
                      >
                        {result.literature.map((lit) => (
                          <article
                            key={lit.doc_id}
                            className="nx-card"
                            style={{
                              padding: 14,
                              display: 'flex',
                              flexDirection: 'column',
                              justifyContent: 'space-between',
                              gap: 8,
                            }}
                          >
                            <div>
                              <div
                                style={{
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                  gap: 6,
                                  marginBottom: 6,
                                }}
                              >
                                <span className="tag mono" style={{ color: '#fb923c' }}>
                                  {lit.accession ?? lit.doc_id}
                                  {lit.acronym ? ` · ${lit.acronym}` : ''}
                                </span>
                                <span className="k mono" style={{ fontSize: 11 }}>
                                  RRF {lit.score.toFixed(3)}
                                </span>
                              </div>
                              <h3 style={{ fontSize: 14, margin: '0 0 6px', lineHeight: 1.35 }}>
                                {lit.url ? (
                                  <a
                                    href={lit.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="link-btn"
                                    style={{ fontWeight: 700 }}
                                  >
                                    {lit.title} ↗
                                  </a>
                                ) : (
                                  lit.title
                                )}
                              </h3>
                              <p
                                className="k"
                                style={{
                                  margin: 0,
                                  fontSize: 12.5,
                                  lineHeight: 1.45,
                                  color: '#cbd5e1',
                                }}
                              >
                                {lit.snippet}
                              </p>
                            </div>
                            <div
                              style={{
                                display: 'flex',
                                flexWrap: 'wrap',
                                gap: 6,
                                marginTop: 6,
                                paddingTop: 6,
                                borderTop: '1px solid rgba(255,255,255,0.07)',
                                fontSize: 11,
                              }}
                            >
                              {lit.platform && <span className="tag">{lit.platform}</span>}
                              {lit.doi && <span className="tag mono">DOI: {lit.doi}</span>}
                              {lit.related_families.slice(0, 3).map((fam) => (
                                <span key={fam} className="tag mono" style={{ color: '#38bdf8' }}>
                                  {fam}
                                </span>
                              ))}
                            </div>
                          </article>
                        ))}
                      </div>
                    </section>
                  )}
                  {result.request_id && (
                    <p className="k">
                      Request ID: <span className="mono">{result.request_id}</span>
                    </p>
                  )}
                </>
              )}
            </div>

            {history.length > 0 && (
              <nav className="card" aria-label="Session history">
                <h2>This session</h2>
                <ul className="plain hist">
                  {history.map((h, i) => (
                    <li key={`${i}-${h.question}`}>
                      <button type="button" className="sug" onClick={() => restore(h)}>
                        {h.question} <span className="tag mono">{h.result.status}</span>
                      </button>
                    </li>
                  ))}
                </ul>
                <p className="k">Kept in memory only. Cleared when you reload.</p>
              </nav>
            )}
          </>
        ) : (
          <section className="card" style={{ padding: 22 }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 12,
                marginBottom: 18,
              }}
            >
              <div>
                <h2 style={{ margin: 0 }}>65-Question Golden Evaluation Benchmark</h2>
                <p className="k" style={{ margin: '4px 0 0' }}>
                  Tests Single-Filter, Multi-Filter, Aggregation, Ranking, Qualitative Hybrid RRF, Guardrail Refusal,
                  and Adversarial SQL/Prompt Injection resilience against{' '}
                  <code>evaluation/golden_questions.json</code>.
                </p>
              </div>
              <button
                type="button"
                className="nx-btn"
                disabled={evalLoading}
                onClick={handleRunLiveEval}
                style={{ cursor: 'pointer', padding: '9px 18px', fontSize: 13 }}
              >
                {evalLoading ? 'Running 65 Questions…' : '▶ Run Live 65-Question Evaluation'}
              </button>
            </div>

            {evalError && <p style={{ color: '#f85149' }}>Evaluation error: {evalError}</p>}

            {scorecard && (
              <>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
                    gap: 14,
                    marginBottom: 22,
                  }}
                >
                  <div className="nx-card" style={{ padding: 16 }}>
                    <span className="k">Overall Pass Rate</span>
                    <div style={{ fontSize: 28, fontWeight: 800, color: '#3fb950', marginTop: 4 }}>
                      {(scorecard.overall_pass_rate * 100).toFixed(1)}%
                    </div>
                    <div className="k">
                      {scorecard.overall_passed} / {scorecard.overall_evaluated} Golden Questions Passed
                    </div>
                  </div>
                  <div className="nx-card" style={{ padding: 16 }}>
                    <span className="k">Hybrid RRF Recall@10</span>
                    <div style={{ fontSize: 28, fontWeight: 800, color: '#38bdf8', marginTop: 4 }}>
                      {(scorecard.qualitative_recall_at_10 * 100).toFixed(1)}%
                    </div>
                    <div className="k">BGE-small-en-v1.5 + BM25 RRF</div>
                  </div>
                  <div className="nx-card" style={{ padding: 16 }}>
                    <span className="k">Planner Mode</span>
                    <div style={{ fontSize: 20, fontWeight: 700, color: '#fb923c', marginTop: 6 }}>
                      {scorecard.planner_mode}
                    </div>
                    <div className="k">Timestamp: {scorecard.evaluated_at.slice(0, 19)} UTC</div>
                  </div>
                </div>

                <h3 style={{ fontSize: 15, marginBottom: 10 }}>Accuracy by Benchmark Category</h3>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                    gap: 10,
                    marginBottom: 22,
                  }}
                >
                  {Object.entries(scorecard.category_breakdown).map(([cat, stats]) => (
                    <button
                      type="button"
                      key={cat}
                      onClick={() => setEvalCategoryFilter(evalCategoryFilter === cat ? 'ALL' : cat)}
                      className="nx-card"
                      style={{
                        padding: 12,
                        textAlign: 'left',
                        cursor: 'pointer',
                        borderColor:
                          evalCategoryFilter === cat ? 'rgba(255,106,26,0.75)' : 'rgba(255,255,255,0.08)',
                      }}
                    >
                      <div style={{ fontSize: 12, textTransform: 'uppercase', color: '#94a3b8' }}>
                        {cat.replace('_', ' ')}
                      </div>
                      <div style={{ fontSize: 20, fontWeight: 700, color: '#3fb950', marginTop: 4 }}>
                        {stats.passed}/{stats.total} ({(stats.pass_rate * 100).toFixed(0)}%)
                      </div>
                    </button>
                  ))}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <h3 style={{ fontSize: 15, margin: 0 }}>
                    Per-Question Verification Log ({filteredQuestions.length} shown)
                  </h3>
                  {evalCategoryFilter !== 'ALL' && (
                    <button
                      type="button"
                      className="sug"
                      onClick={() => setEvalCategoryFilter('ALL')}
                    >
                      Show All Categories
                    </button>
                  )}
                </div>

                <div className="tscroll" style={{ maxHeight: 460 }}>
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Status</th>
                        <th>Category</th>
                        <th>Route</th>
                        <th>Question</th>
                        <th>Rows</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredQuestions.map((q) => (
                        <tr
                          key={q.id}
                          style={{ cursor: 'pointer' }}
                          onClick={() => {
                            setQuestion(q.question);
                            setActiveTab('qa');
                            void run(q.question);
                          }}
                          title="Click to run this question in Interactive Q&A"
                        >
                          <td className="mono">{q.id}</td>
                          <td>
                            <span
                              className="tag mono"
                              style={{
                                color: q.passed ? '#3fb950' : '#f85149',
                                borderColor: q.passed ? 'rgba(63,185,80,0.4)' : 'rgba(248,81,73,0.4)',
                              }}
                            >
                              {q.passed ? 'PASS' : 'FAIL'}
                            </span>
                          </td>
                          <td className="mono">{q.category}</td>
                          <td className="mono">{q.intent}</td>
                          <td>{q.question}</td>
                          <td className="num">{q.actual_row_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>
        )}
      </main>
      <DatasetFooter meta={meta} error={metaError} onRetry={loadMeta} />
      {open && <DetailDrawer row={open} onClose={() => setOpen(null)} />}
    </>
  );
}
