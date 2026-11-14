"""Multi-document NASA PSI Investigation Dossiers & NTRS Technical Literature Retriever.

Indexes:
1. All 24 combustion investigations from `data/raw/psi/search_combustion.json` (plus deep dossiers
   from `data/raw/psi/investigations/PSI-10.json`, `PSI-22.json`, and `data/raw/psi_26_detail.json`).
2. Core NASA microgravity combustion technical literature from the 2026 NASA Space Apps Challenge
   resources (NASA Researcher's Guide to ISS Combustion Science, NTRS Saffire/SoFIE & MOC papers,
   NASA SMA Apollo 1 / Apollo 13 / Mir 1997 incident dossiers, and NASA Spinoff / SAME smoke detection).

Uses the cached `SentenceTransformer("BAAI/bge-small-en-v1.5")` 384-d neural embeddings + Okapi BM25
with Reciprocal Rank Fusion (RRF, k=60) for sub-50ms offline retrieval.
"""

from __future__ import annotations

import json
import logging
import math
from collections import Counter
from typing import Any

import joblib
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from flame.config import PROJECT_ROOT, Settings, get_settings
from flame.retrieval.semantic import _load_sentence_transformer, _tokenize
from flame.schemas.query_plan import QueryPlan

logger = logging.getLogger("flame.retrieval.literature")

LITERATURE_INDEX_FILE = "literature_hybrid_index.joblib"

# Mapping from PSI Accession IDs to our canonical dataset_family names
_PSI_TO_FAMILIES: dict[str, list[str]] = {
    "PSI-10": ["ACME (CIR)", "ACME-CFI", "ACME-CLD"],
    "PSI-20": ["ACME-BRE", "ACME (CIR)"],
    "PSI-21": ["ACME-CLD", "ACME (CIR)"],
    "PSI-22": ["ACME-EFIELD", "Partial-g Bounded (0g+1g / E-FIELD)", "ACME (CIR)"],
    "PSI-23": ["ACME (CIR)", "ACME-CFI-G"],
    "PSI-25": ["BASS-II"],
    "PSI-26": ["BASS-I", "BASS-II"],
    "PSI-39": ["FLEX", "FLEX-2", "ACME-CFI"],
    "PSI-47": ["DAFT / DAFT-2", "SAME (Aerosol)"],
    "PSI-60": ["SPICE"],
    "PSI-62": ["BASS-I", "BASS-II"],
    "PSI-68": ["FLEX-2", "FLEX"],
    "PSI-69": ["FLEX", "FLEX-2"],
    "PSI-98": ["SAFFIRE-I", "SAFFIRE-II", "SAFFIRE-III", "SAFFIRE-IV", "SAFFIRE-V", "SAFFIRE-VI"],
    "PSI-99": ["SAFFIRE-II", "SAFFIRE-I"],
    "PSI-100": ["SAFFIRE-III", "SAFFIRE-IV", "SAFFIRE-V", "SAFFIRE-VI"],
    "PSI-101": ["SAME-R", "SAME (Aerosol)"],
    "PSI-102": ["SAME (Aerosol)", "SAME-R"],
    "PSI-106": ["SLICE"],
    "PSI-107": ["SPICE"],
    "PSI-115": ["SAME (Aerosol)", "SAME-R"],
    "PSI-117": ["FLEX-2", "ACME-CFI-G"],
    "PSI-142": ["ACME-CFI-G", "FLEX-2"],
    "PSI-159": ["ACME-CFI-G", "ACME (CIR)"],
}

# Non-combustion studies that appear in PSI keyword search due to heating/furnace terms
_EXCLUDED_PSI_IDS = {"PSI-181", "PSI-108"}


def _curated_nasa_literature() -> list[dict[str, Any]]:
    """Return curated NASA technical reports, researcher guides, and SMA case studies."""
    return [
        {
            "doc_id": "LIT-GUIDE-2015",
            "title": "A Researcher's Guide to International Space Station Combustion Science (NASA NP-2015-03-015-JSC)",
            "doc_type": "NASA Researcher's Guide",
            "authors": "Daniel L. Dietrich, Gary A. Ruff, David L. Urban, Paul V. Ferkul",
            "platform": "International Space Station (ISS) — CIR & MSG",
            "related_families": [
                "FLEX",
                "FLEX-2",
                "BASS-I",
                "BASS-II",
                "ACME (CIR)",
                "SOFIE",
                "SLICE",
                "SPICE",
            ],
            "source_url": "https://www.nasa.gov/missions/station/a-researchers-guide-to-combustion-science/",
            "excerpt": (
                "In microgravity (0g), buoyant natural convection vanishes (~10^-6 g on the ISS), transforming "
                "teardrop flames into spherical diffusion flames governed by molecular diffusion, radiative heat "
                "loss, and low-velocity forced ventilation (1–25 cm/s). Droplet combustion experiments (FLEX, "
                "FLEX-2) revealed two-stage burning: high-temperature hot-flame radiative extinction followed by "
                "sustained low-temperature (~600–750 K) cool flames stabilized by alkylperoxy (RO2) chemistry in "
                "n-heptane and n-decane. Solid fuel tests in BASS and BASS-II proved that gentle cabin ventilation "
                "supplies fresh oxidizer without buoyant cooling, allowing materials to burn at lower oxygen "
                "concentrations than on Earth."
            ),
        },
        {
            "doc_id": "LIT-NTRS-20120015928",
            "title": "Low-Velocity Microgravity Flame Spread and Minimum Oxygen Concentration (MOC) vs. NASA-STD-6001 Test 1",
            "doc_type": "NASA Technical Report (NTRS)",
            "authors": "Sandra L. Olson, Fletcher J. Miller, Indrek S. Wichman, Paul V. Ferkul",
            "platform": "ISS Microgravity Science Glovebox (MSG) & GRC Drop Tower",
            "related_families": [
                "BASS-I",
                "BASS-II",
                "NASA-STD-6001",
                "SOFIE",
                "GRC Drop Tower",
                "FLARE (JAXA/Kibo)",
            ],
            "source_url": "https://ntrs.nasa.gov/citations/20120015928",
            "excerpt": (
                "Standard spacecraft material qualification relies on terrestrial 1g upward flame spread testing "
                "(NASA-STD-6001 Test 1), where buoyant flow (~30–50 cm/s) convectively cools the flame zone. In "
                "microgravity at low spacecraft HVAC velocities (1.5–15 cm/s), convective heat loss drops while "
                "oxygen transport to the pyrolysis front remains active. Consequently, the 0g Minimum Oxygen "
                "Concentration (MOC) boundary is 2.5% to 4.0% O2 lower than in 1g, meaning materials certified as "
                "self-extinguishing on Earth (e.g., thin PMMA, Nomex, cotton-fiberglass SIBAL) can sustain flame "
                "spread in orbit unless ventilation fans are shut off (<1.0 cm/s diffusive starvation)."
            ),
        },
        {
            "doc_id": "LIT-NTRS-20240002981",
            "title": "Spacecraft Fire Safety: Saffire I–VI Large-Scale Cygnus Flight Experiments & SoFIE Exploration Atmospheres",
            "doc_type": "NASA Technical Report (NTRS)",
            "authors": "David L. Urban, Gary A. Ruff, Paul V. Ferkul, Justin T. Niehaus",
            "platform": "Northrop Grumman Cygnus Spacecraft & ISS CIR (SoFIE)",
            "related_families": [
                "SAFFIRE-I",
                "SAFFIRE-II",
                "SAFFIRE-III",
                "SAFFIRE-IV",
                "SAFFIRE-V",
                "SAFFIRE-VI",
                "SOFIE",
                "LUCI / FM2 (Future Partial-g)",
            ],
            "source_url": "https://ntrs.nasa.gov/citations/20240002981",
            "excerpt": (
                "Saffire I–VI conducted full-scale (up to 0.4 m x 1.0 m) cotton-fiberglass (SIBAL) and ribbed/flat "
                "PMMA burns inside uncrewed Cygnus cargo vehicles after ISS departure across normoxic (21% O2, "
                "101.3 kPa) and Artemis Space Exploration Atmospheres (SEA: 34% O2 at 56.5 kPa / 8.2 psia). "
                "Findings demonstrate that in finite cabin volumes, large fires couple strongly with vehicle "
                "pressure rise and oxygen depletion, while elevated O2 mole fraction (34% O2) significantly "
                "increases flame spread rate and CO/soot yields despite reduced total cabin pressure. SoFIE "
                "(MIST, GEL, SMuRF) extends these measurements inside the ISS Combustion Integrated Rack."
            ),
        },
        {
            "doc_id": "LIT-SMA-APOLLO1",
            "title": "Apollo 1 (AS-204) Plugs-Out Pad Test Cabin Fire Investigation & High-O2 Flammability Lessons",
            "doc_type": "NASA Safety & Mission Assurance",
            "authors": "NASA Office of Safety and Mission Assurance (OSMA) / Apollo 204 Review Board",
            "platform": "Apollo Command Module CM-012 (Launch Complex 34)",
            "related_families": ["NASA-STD-6001", "SOFIE", "SAFFIRE-IV", "SAFFIRE-V", "SAFFIRE-VI"],
            "source_url": "https://sma.nasa.gov/sma-disciplines/accllp/apollo-1",
            "excerpt": (
                "On January 27, 1967, a cabin fire in Apollo 1 (CM-012) during a pre-launch plugs-out test in a "
                "100% O2, 16.7 psia (115 kPa) atmosphere resulted in the loss of the three-person crew. Pure "
                "oxygen at elevated partial pressure drastically lowered the ignition energy and accelerated "
                "flame propagation across exposed Nylon netting, Velcro hooks, and polyurethane foam. Apollo 1 "
                "established strict material flammability controls (NHB 8060.1 / NASA-STD-6001), restricted "
                "exposed Velcro/polymer fuel paths, and motivated dual-gas N2/O2 cabin atmospheres."
            ),
        },
        {
            "doc_id": "LIT-SMA-APOLLO13",
            "title": "Apollo 13 Service Module Oxygen Tank No. 2 PTFE Insulation Ignition & Cryogenic O2 Hazard",
            "doc_type": "NASA Safety & Mission Assurance",
            "authors": "NASA Office of Safety and Mission Assurance (OSMA) / Cortright Review Board",
            "platform": "Apollo 13 Service Module (SM-109)",
            "related_families": ["NASA-STD-6001", "ACME-EFIELD", "MGM (Smoldering)"],
            "source_url": "https://sma.nasa.gov/sma-disciplines/accllp/apollo-13",
            "excerpt": (
                "During Apollo 13 in April 1970, damaged 28V/65V thermostatic switches inside supercritical "
                "Oxygen Tank No. 2 overheated (>500 °C during pre-flight detanking) and ignited fluoropolymer "
                "(PTFE / Teflon) wire insulation in high-pressure pure oxygen upon fan stirring. Even materials "
                "classified as non-flammable in normal air (PTFE) undergo rapid exothermic combustion in "
                "high-pressure pure O2 without buoyant heat dissipation."
            ),
        },
        {
            "doc_id": "LIT-HIST-MIR1997",
            "title": "1997 Fire Aboard Space Station Mir: Solid-Fuel Oxygen Generator (Vika/TGK) Blowtorch & Smoke Response",
            "doc_type": "NASA History & Flight Safety",
            "authors": "NASA History Office / ISS Joint Safety Review",
            "platform": "Mir Space Station (Kvant-1 Module)",
            "related_families": ["SAME (Aerosol)", "SAME-R", "DAFT / DAFT-2", "SAFFIRE-IV", "SLICE"],
            "source_url": "https://www.nasa.gov/history/25-years-ago-fire-aboard-space-station-mir/",
            "excerpt": (
                "On February 23, 1997, a lithium perchlorate solid-fuel oxygen generator (SFOG / Vika / TGK) "
                "cartridge ruptured aboard Mir's Kvant-1 module, producing a self-oxidizing ~60 cm blowtorch "
                "flame for ~14 minutes and filling the station with dense metallic-oxide and organic smoke. "
                "Water-foam extinguishers failed to quench the self-oxidizing reaction directly, highlighting "
                "the critical need for non-blocking fire suppression access, immediate ventilation cutoff, and "
                "post-fire particulate/CO scrubbing."
            ),
        },
        {
            "doc_id": "LIT-SPINOFF-9407",
            "title": "Spacecraft Smoke Detection & Aerosol Signatures in Microgravity (SAME / DAFT / Shuttle Spinoff)",
            "doc_type": "NASA Spinoff & Fire Detection",
            "authors": "David L. Urban, Marit E. Meyer, Gary A. Ruff, Paul D. Mudgett",
            "platform": "Space Shuttle & ISS Microgravity Science Glovebox (SAME / DAFT)",
            "related_families": ["SAME (Aerosol)", "SAME-R", "DAFT / DAFT-2", "MGM (Smoldering)"],
            "source_url": "https://spinoff.nasa.gov/node/9407",
            "excerpt": (
                "In microgravity, the absence of buoyant plumes causes pyrolysis and smoldering smoke aerosols "
                "(from Kapton, Teflon, Silicone, Cellulose, and Lamp Wick tested in SAME PSI-102 and SAME-R "
                "PSI-101) to remain in the flame/heater zone longer, growing into larger agglomerated particles "
                "(0.2–1.5 micrometers count median diameter) than in 1g. ISS photoelectric laser-scattering "
                "detectors are tuned differently from shuttle ionization detectors; understanding particle size "
                "distributions and dust discrimination (DAFT PSI-47) prevents nuisance alarms while ensuring "
                "rapid detection of pre-flaming pyrolysis."
            ),
        },
    ]


def load_literature_corpus() -> list[dict[str, Any]]:
    """Build the unified literature corpus from NASA PSI JSON files and curated NASA reports."""
    corpus: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # 1. Load deep PSI dossiers if available (PSI-10, PSI-22, PSI-26)
    deep_dossiers: dict[str, dict[str, Any]] = {}
    for p_path in [
        PROJECT_ROOT / "data" / "raw" / "psi" / "investigations" / "PSI-10.json",
        PROJECT_ROOT / "data" / "raw" / "psi" / "investigations" / "PSI-22.json",
        PROJECT_ROOT / "data" / "raw" / "psi" / "investigations" / "PSI-26.json",
    ]:
        if p_path.exists():
            try:
                d = json.loads(p_path.read_text(encoding="utf-8"))
                acc = str(d.get("accession") or "").strip()
                if acc:
                    deep_dossiers[acc] = d
            except Exception as err:
                logger.warning("Could not parse deep PSI dossier %s: %s", p_path, err)

    # 2. Load all combustion PSI investigations from search_combustion.json
    search_path = PROJECT_ROOT / "data" / "raw" / "psi" / "search_combustion.json"

    if search_path.exists():
        try:
            raw = json.loads(search_path.read_text(encoding="utf-8"))
            hits = raw.get("hits", {}).get("hits", [])
            for hit in hits:
                src = hit.get("_source", {})
                acc = str(src.get("Accession") or "").strip()
                if not acc or acc in _EXCLUDED_PSI_IDS or acc in seen_ids:
                    continue
                seen_ids.add(acc)

                title = str(src.get("Title") or acc).strip()
                acronym = str(src.get("Acronym") or "").strip()
                platform = str(src.get("Flight Platform") or "International Space Station (ISS)").strip()
                sub_area = str(src.get("SubResearch Area") or "Combustion Science").strip()

                person = src.get("Person") or {}
                if isinstance(person, dict):
                    first = str(person.get("First Name") or "").strip()
                    last = str(person.get("Last Name") or "").strip()
                    authors = f"{first} {last}".strip() or "NASA GRC Principal Investigators"
                else:
                    authors = str(person)

                obj = str(src.get("Objectives") or "").strip()
                app = str(src.get("Approach") or "").strip()
                hyp = str(src.get("Hypothesis") or "").strip()
                imp = str(src.get("Research Impacts/Earth Benefits") or "").strip()
                pubs = str(src.get("Publication Title") or "").strip()
                kw = str(src.get("Keywords") or "").strip()

                # Enrich with deep dossier fields if present
                deep = deep_dossiers.get(acc, {})
                doi = str(deep.get("doi") or "").strip()
                if deep.get("objective"):
                    obj = str(deep["objective"]).strip()
                if deep.get("researchImpacts"):
                    imp = str(deep["researchImpacts"]).strip()

                parts = []
                if acronym:
                    parts.append(f"Investigation {acc} ({acronym}): {title}.")
                else:
                    parts.append(f"Investigation {acc}: {title}.")
                if obj:
                    parts.append(f"Objectives: {obj}")
                if app:
                    parts.append(f"Approach: {app}")
                if hyp:
                    parts.append(f"Hypothesis: {hyp}")
                if imp:
                    parts.append(f"Spacecraft Fire-Safety Impact: {imp}")
                if pubs:
                    parts.append(f"Key Publications: {' | '.join(pubs.split('     ')[:3])}.")
                if doi:
                    parts.append(f"DOI: {doi}.")

                excerpt = " ".join(parts)
                corpus.append(
                    {
                        "doc_id": acc,
                        "title": f"{acc} ({acronym}) — {title}" if acronym else f"{acc} — {title}",
                        "doc_type": f"NASA PSI Investigation ({sub_area})",
                        "authors": authors,
                        "platform": platform,
                        "related_families": _PSI_TO_FAMILIES.get(acc, []),
                        "source_url": f"https://psi.nasa.gov/physci/repo/data/investigations/{acc}",
                        "keywords": kw,
                        "excerpt": excerpt[:1400],
                    }
                )
        except Exception as err:
            logger.warning("Failed loading PSI search_combustion.json: %s", err)

    # 3. Append curated NASA NTRS / Researcher's Guide / SMA / Spinoff literature
    for item in _curated_nasa_literature():
        if item["doc_id"] not in seen_ids:
            seen_ids.add(item["doc_id"])
            corpus.append(item)

    return corpus


def build_literature_index(
    model_name: str = "BAAI/bge-small-en-v1.5",
    allow_download: bool = False,
) -> dict[str, Any]:
    """Build hybrid SentenceTransformer (384-d) + TF-IDF/SVD + Okapi BM25 index over literature corpus."""
    corpus = load_literature_corpus()
    docs = [
        f"{item['doc_id']} {item['title']} {item['doc_type']} "
        f"Families: {', '.join(item.get('related_families', []))}. "
        f"Keywords: {item.get('keywords', '')}. {item['excerpt']}"
        for item in corpus
    ]
    tokenized = [_tokenize(d) for d in docs]
    doc_lens = [len(t) for t in tokenized]
    avgdl = sum(doc_lens) / max(1, len(doc_lens))

    df_counts: Counter[str] = Counter()
    tf_list: list[Counter[str]] = []
    for toks in tokenized:
        c = Counter(toks)
        tf_list.append(c)
        for term in c:
            df_counts[term] += 1

    tfidf = TfidfVectorizer(ngram_range=(1, 2), max_features=8000, sublinear_tf=True, stop_words="english")
    tfidf_mat = tfidf.fit_transform(docs)
    n_comp = max(2, min(24, tfidf_mat.shape[0] - 1, tfidf_mat.shape[1] - 1))
    svd = TruncatedSVD(n_components=n_comp, random_state=42)
    dense_vecs = normalize(svd.fit_transform(tfidf_mat))

    st_model = _load_sentence_transformer(model_name, allow_download=allow_download)
    st_vecs: np.ndarray | None = None
    if st_model is not None:
        try:
            st_vecs = np.asarray(
                st_model.encode(docs, normalize_embeddings=True, show_progress_bar=False),
                dtype=np.float32,
            )
        except Exception as err:
            logger.warning("Literature SentenceTransformer encode failed: %s", err)
            st_vecs = None

    return {
        "corpus": corpus,
        "docs": docs,
        "tf_list": tf_list,
        "doc_lens": doc_lens,
        "avgdl": avgdl,
        "df_counts": df_counts,
        "n_docs": len(docs),
        "tfidf": tfidf,
        "svd": svd,
        "tfidf_mat": tfidf_mat,
        "dense_vecs": dense_vecs,
        "st_vecs": st_vecs,
        "embedding_model": model_name,
    }


class LiteratureRetriever:
    """Retrieves grounded NASA PSI investigation dossiers and technical literature via Hybrid RRF."""

    _cached_index: dict[str, Any] | None = None

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _get_index(self) -> dict[str, Any]:
        if LiteratureRetriever._cached_index is None:
            idx_path = self.settings.qdrant_path / LITERATURE_INDEX_FILE
            if idx_path.exists():
                try:
                    LiteratureRetriever._cached_index = joblib.load(idx_path)
                except Exception:
                    LiteratureRetriever._cached_index = None
            if LiteratureRetriever._cached_index is None:
                LiteratureRetriever._cached_index = build_literature_index(
                    model_name=self.settings.embedding_model,
                    allow_download=False,
                )
                try:
                    self.settings.qdrant_path.mkdir(parents=True, exist_ok=True)
                    joblib.dump(LiteratureRetriever._cached_index, idx_path)
                except Exception:
                    pass
        return LiteratureRetriever._cached_index

    def list_all(self) -> list[dict[str, Any]]:
        """Return all indexed PSI investigation dossiers and NASA technical literature records."""
        idx = self._get_index()
        return list(idx["corpus"])

    def search(
        self,
        question: str,
        plan: QueryPlan | None = None,
        evidence_rows: list[dict[str, Any]] | None = None,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        """Rank literature passages using Hybrid RRF (BGE-small-en-v1.5 + BM25 + family boost)."""
        idx = self._get_index()
        corpus: list[dict[str, Any]] = idx["corpus"]
        if not corpus:
            return []

        n_docs = idx["n_docs"]
        avgdl = idx["avgdl"]
        df_counts: Counter[str] = idx["df_counts"]
        tf_list: list[Counter[str]] = idx["tf_list"]
        doc_lens: list[int] = idx["doc_lens"]

        # Collect active dataset families and PSI investigation IDs from plan + retrieved evidence rows
        active_families: set[str] = set()
        active_inv_ids: set[str] = set()
        if evidence_rows:
            for r in evidence_rows[:25]:
                fam = r.get("dataset_family")
                inv = r.get("investigation_id")
                if fam:
                    active_families.add(str(fam))
                if inv:
                    active_inv_ids.add(str(inv))
        if plan and plan.filters:
            for f in plan.filters:
                if f.field == "dataset_family" and isinstance(f.value, str):
                    active_families.add(f.value)
                elif f.field == "dataset_family" and isinstance(f.value, (list, tuple)):
                    active_families.update(str(x) for x in f.value)

        # 1. Okapi BM25
        q_tokens = _tokenize(question)
        k1 = 1.5
        b = 0.75
        bm25_scores: dict[int, float] = {}
        for i in range(n_docs):
            score = 0.0
            dl = doc_lens[i]
            tfs = tf_list[i]
            for qt in q_tokens:
                tf = tfs.get(qt, 0)
                if tf == 0:
                    continue
                df_q = df_counts.get(qt, 0)
                idf = math.log(1.0 + (n_docs - df_q + 0.5) / (df_q + 0.5))
                denom = tf + k1 * (1.0 - b + b * (dl / avgdl))
                score += idf * (tf * (k1 + 1.0)) / denom
            bm25_scores[i] = score

        # 2. Dense similarity (SentenceTransformer 384-d + TF-IDF/SVD)
        tfidf: TfidfVectorizer = idx["tfidf"]
        svd: TruncatedSVD = idx["svd"]
        tfidf_mat = idx["tfidf_mat"]
        dense_vecs: np.ndarray = idx["dense_vecs"]
        st_vecs: np.ndarray | None = idx.get("st_vecs")
        emb_model_name = str(idx.get("embedding_model") or self.settings.embedding_model)

        q_tfidf = tfidf.transform([question])
        q_dense = normalize(svd.transform(q_tfidf))[0]
        lexical_cos = (tfidf_mat @ q_tfidf.T).toarray().ravel()
        semantic_cos = dense_vecs @ q_dense

        st_cos: np.ndarray | None = None
        if st_vecs is not None:
            st_model = _load_sentence_transformer(emb_model_name, allow_download=False)
            if st_model is not None:
                try:
                    q_st = np.asarray(
                        st_model.encode([question], normalize_embeddings=True, show_progress_bar=False)[0],
                        dtype=np.float32,
                    )
                    st_cos = st_vecs @ q_st
                except Exception:
                    st_cos = None

        dense_scores: dict[int, float] = {}
        for i in range(n_docs):
            if st_cos is not None:
                base = float(0.55 * st_cos[i] + 0.30 * lexical_cos[i] + 0.15 * semantic_cos[i])
            else:
                base = float(0.60 * lexical_cos[i] + 0.40 * semantic_cos[i])

            # Contextual family / investigation alignment boost
            item = corpus[i]
            doc_id = str(item.get("doc_id", ""))
            rel_fams = set(item.get("related_families", []))
            boost = 0.0
            if doc_id in active_inv_ids:
                boost += 0.25
            if active_families and (rel_fams & active_families):
                boost += 0.15
            dense_scores[i] = base + boost

        # 3. RRF Fusion (k=60)
        indices = list(range(n_docs))
        bm25_ranked = sorted(indices, key=lambda i: bm25_scores[i], reverse=True)
        dense_ranked = sorted(indices, key=lambda i: dense_scores[i], reverse=True)

        rrf_k = 60.0
        rrf_scores: dict[int, float] = {i: 0.0 for i in indices}
        for rank, doc_idx in enumerate(bm25_ranked, start=1):
            if bm25_scores[doc_idx] > 0:
                rrf_scores[doc_idx] += 1.0 / (rrf_k + rank)
        for rank, doc_idx in enumerate(dense_ranked, start=1):
            if dense_scores[doc_idx] > 0:
                rrf_scores[doc_idx] += 1.0 / (rrf_k + rank)

        ranked = sorted(
            indices,
            key=lambda i: (rrf_scores[i], dense_scores[i], bm25_scores[i]),
            reverse=True,
        )[:limit]

        results: list[dict[str, Any]] = []
        for i in ranked:
            entry = dict(corpus[i])
            entry["relevance_score"] = round(float(dense_scores[i]), 3)
            results.append(entry)
        return results


__all__ = [
    "LITERATURE_INDEX_FILE",
    "LiteratureRetriever",
    "build_literature_index",
    "load_literature_corpus",
]
