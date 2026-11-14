"""Spacecraft fire-safety insights, family rankings, and ML flammability risk predictor.

Trained on the 840 physical (non-modeled) experiments in `data/processed/experiments.parquet`
and enriched with PSI metadata from `data/raw/psi/`.
"""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from flame.config import PROJECT_ROOT
from flame.retrieval.store import ExperimentStore


class RiskSimulationRequest(BaseModel):
    """Input cabin atmosphere and material conditions for flammability simulation."""

    model_config = ConfigDict(extra="forbid")

    oxygen_pct: float = Field(default=21.0, ge=0.0, le=100.0)
    pressure_kpa: float = Field(default=101.3, ge=0.0, le=300.0)
    airflow_velocity_cms: float = Field(default=10.0, ge=0.0, le=500.0)
    fuel_material: str = Field(default="PMMA (Acrylic)")
    gravity_regime: str = Field(default="Microgravity (~0g)")


class NearestExperiment(BaseModel):
    """Closest historical experiment from the validated snapshot."""

    experiment_id: str
    dataset_family: str
    investigation_id: str
    fuel_material: str
    oxygen_pct: float | None
    pressure_kpa: float | None
    airflow_velocity_cms: float | None
    burning_rate_mms: float | None
    flame_temp_k: float | None
    extinction_outcome: str
    gravity_condition: str
    distance: float
    source_url: str


class RiskSimulationResponse(BaseModel):
    """Predicted flammability risk and closest real microgravity experiments."""

    risk_score: float = Field(description="Normalized 0.0 to 1.0 fire hazard score.")
    risk_level: str = Field(description="LOW, MODERATE, HIGH, or CRITICAL.")
    sustained_burn_probability: float = Field(
        description="ML probability of sustained combustion vs. self-extinction/quenching."
    )
    predicted_burning_rate_mms: float = Field(
        description="Predicted burning/spread rate (mm/s) based on physical family peers."
    )
    predicted_flame_temp_k: float = Field(
        description="Predicted flame temperature (K)."
    )
    std6001_comparison: str = Field(
        description="Comparison against 1g NASA-STD-6001 upward screening at similar O2/pressure."
    )
    recommendations: list[str]
    nearest_experiments: list[NearestExperiment]


def _is_sustained_outcome(outcome: str) -> int:
    low = str(outcome).lower()
    if any(
        w in low
        for w in (
            "self-extinguish",
            "self-extinction",
            "quench",
            "no ignition",
            "pass (",
            "conditional pass",
        )
    ):
        return 0
    if any(
        w in low
        for w in (
            "sustained",
            "completion",
            "complete",
            "disruption",
            "flame spread",
            "steady",
            "transition to flaming",
            "burnout",
            "incomplete burn",
            "alarm triggered",
            "fail",
            "re-ignit",
            "propagat",
        )
    ):
        return 1
    return 0


class FlammabilityEngine:
    """Cached ML models and nearest-neighbor index over physical microgravity experiments."""

    def __init__(self, store: ExperimentStore) -> None:
        self.store = store
        self.df = pd.read_parquet(store.parquet_path)
        self.phys_df = self.df[~self.df["is_modeled"]].copy()
        self._fit_models()

    def _fit_models(self) -> None:
        df = self.phys_df.copy()
        df["o2"] = pd.to_numeric(df["oxygen_pct"], errors="coerce").fillna(21.0)
        df["kpa"] = pd.to_numeric(df["pressure_kpa"], errors="coerce").fillna(101.3)
        df["flow"] = pd.to_numeric(df["airflow_velocity_cms"], errors="coerce").fillna(5.0)
        df["y_sustained"] = df["extinction_outcome"].apply(_is_sustained_outcome)

        # Material category encoding (mean sustained rate per material/category)
        mat_means = df.groupby("fuel_material")["y_sustained"].mean().to_dict()
        self._mat_hazard: dict[str, float] = {str(k): float(v) for k, v in mat_means.items()}
        df["mat_score"] = df["fuel_material"].map(self._mat_hazard).fillna(0.5)

        X = df[["o2", "kpa", "flow", "mat_score"]].to_numpy(dtype=float)

        # 1. Sustained combustion classifier
        self._clf = RandomForestClassifier(n_estimators=80, max_depth=6, random_state=42)
        self._clf.fit(X, df["y_sustained"].to_numpy(dtype=int))

        # 2. Burning rate regressor (on non-null physical rows)
        br_mask = df["burning_rate_mms"].notna() & (df["burning_rate_mms"] > 0)
        if br_mask.sum() >= 10:
            self._br_reg = RandomForestRegressor(n_estimators=80, max_depth=6, random_state=42)
            self._br_reg.fit(
                X[br_mask], df.loc[br_mask, "burning_rate_mms"].to_numpy(dtype=float)
            )
        else:
            self._br_reg = None

        # 3. Flame temp regressor
        ft_mask = df["flame_temp_k"].notna() & (df["flame_temp_k"] > 250)
        if ft_mask.sum() >= 10:
            self._ft_reg = RandomForestRegressor(n_estimators=60, max_depth=5, random_state=42)
            self._ft_reg.fit(X[ft_mask], df.loc[ft_mask, "flame_temp_k"].to_numpy(dtype=float))
        else:
            self._ft_reg = None

        # 4. Nearest-neighbors index in scaled (O2, kPa, flow, mat_score) space
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)
        self._nn = NearestNeighbors(n_neighbors=12, metric="euclidean")
        self._nn.fit(X_scaled)
        self._nn_df = df.reset_index(drop=True)

    def simulate(self, req: RiskSimulationRequest) -> RiskSimulationResponse:
        mat_h = self._mat_hazard.get(req.fuel_material)
        if mat_h is None:
            # Substring lookup
            matches = [
                v for k, v in self._mat_hazard.items() if req.fuel_material.lower() in k.lower()
            ]
            mat_h = float(np.mean(matches)) if matches else 0.5

        x_vec = np.array(
            [[req.oxygen_pct, req.pressure_kpa, req.airflow_velocity_cms, mat_h]], dtype=float
        )
        proba = float(self._clf.predict_proba(x_vec)[0][1])

        pred_br = float(self._br_reg.predict(x_vec)[0]) if self._br_reg is not None else 1.2
        pred_ft = float(self._ft_reg.predict(x_vec)[0]) if self._ft_reg is not None else 1450.0

        # Physics-informed composite risk score combining ML sustained probability,
        # oxygen enrichment factor (above 21% O2), and ventilation assist (2-25 cm/s peak in 0g)
        o2_factor = min(1.0, max(0.0, (req.oxygen_pct - 15.0) / 25.0))
        flow_assist = (
            1.0
            if 1.5 <= req.airflow_velocity_cms <= 30.0
            else (0.6 if req.airflow_velocity_cms == 0 else 0.75)
        )
        risk_score = round(
            min(1.0, max(0.02, 0.50 * proba + 0.35 * o2_factor + 0.15 * flow_assist * mat_h)), 3
        )

        if risk_score >= 0.75:
            level = "CRITICAL"
        elif risk_score >= 0.52:
            level = "HIGH"
        elif risk_score >= 0.30:
            level = "MODERATE"
        else:
            level = "LOW"

        # Nearest historical experiments (boost exact material matches)
        x_scaled = self._scaler.transform(x_vec)
        dists, indices = self._nn.kneighbors(x_scaled, n_neighbors=20)
        candidates: list[tuple[float, pd.Series]] = []
        for d, idx_val in zip(dists[0], indices[0], strict=False):
            row = self._nn_df.iloc[int(idx_val)]
            bonus = -0.6 if req.fuel_material.lower() in str(row["fuel_material"]).lower() else 0.0
            candidates.append((float(d) + bonus, row))
        candidates.sort(key=lambda t: t[0])

        nearest: list[NearestExperiment] = []
        for dist_val, row in candidates[:5]:
            br = row.get("burning_rate_mms")
            ft = row.get("flame_temp_k")
            af = row.get("airflow_velocity_cms")
            nearest.append(
                NearestExperiment(
                    experiment_id=str(row["experiment_id"]),
                    dataset_family=str(row["dataset_family"]),
                    investigation_id=str(row["investigation_id"]),
                    fuel_material=str(row["fuel_material"]),
                    oxygen_pct=float(row["oxygen_pct"]) if pd.notna(row["oxygen_pct"]) else None,
                    pressure_kpa=float(row["pressure_kpa"]) if pd.notna(row["pressure_kpa"]) else None,
                    airflow_velocity_cms=(
                        float(af) if pd.notna(af) and not math.isnan(float(af)) else None
                    ),
                    burning_rate_mms=(
                        float(br) if pd.notna(br) and not math.isnan(float(br)) else None
                    ),
                    flame_temp_k=(
                        float(ft) if pd.notna(ft) and not math.isnan(float(ft)) else None
                    ),
                    extinction_outcome=str(row["extinction_outcome"]),
                    gravity_condition=str(row["gravity_condition"]),
                    distance=round(max(0.0, dist_val), 3),
                    source_url=str(row["source_url"]),
                )
            )

        # Compare against 1g NASA-STD-6001
        if req.oxygen_pct >= 30.0 and req.pressure_kpa <= 65.0:
            std_comp = (
                "Artemis / Lunar Exploration Atmosphere regime (~34% O2, ~56.5 kPa): "
                "SOFIE and BASS-II show significantly lower Minimum Oxygen Concentration (MOC) "
                "extinction limits in low-velocity microgravity flow (3–15 cm/s) than 1g upward "
                "NASA-STD-6001 screening."
            )
        elif 1.0 <= req.airflow_velocity_cms <= 20.0:
            std_comp = (
                f"At {req.airflow_velocity_cms:.1f} cm/s forced ventilation in microgravity, "
                "buoyant convective cooling is absent while oxidizer transport to the flame front "
                "remains active — materials that self-extinguish in 1g NASA-STD-6001 Test 1 can "
                "sustain spread (verified in BASS / BASS-II)."
            )
        else:
            std_comp = (
                "Quiescent or high-flow regime: without forced ventilation (0 cm/s) spherical/surface "
                "flames become diffusion-limited; at very high flow (>40 cm/s) convective blowoff "
                "can occur if heat loss exceeds reaction rate."
            )

        recs = [
            f"Immediately shut off cabin ventilation fans upon smoke detection (reduces flow from {req.airflow_velocity_cms:.1f} cm/s to ~0 cm/s to starve microgravity diffusion flames).",
        ]
        if req.oxygen_pct >= 26.0:
            recs.append(
                f"Elevated oxygen ({req.oxygen_pct:.1f}% O2) accelerates flame spread and lowers ignition energy; restrict exposed thin polymer/fabric geometries (PMMA, Cotton, Velcro)."
            )
        if "heptane" in req.fuel_material.lower() or "droplet" in req.fuel_material.lower():
            recs.append(
                "Account for two-stage cool-flame chemistry (~650–750 K, observed in FLEX-2 / ACME CFI-G): visible flame extinction may be followed by invisible cool-flame vapor accumulation and re-ignition."
            )
        else:
            recs.append(
                "Verify thickness and concurrent vs. opposed flow orientation against SAFFIRE I–VI and SOFIE data before qualifying cabin materials."
            )

        return RiskSimulationResponse(
            risk_score=risk_score,
            risk_level=level,
            sustained_burn_probability=round(proba, 3),
            predicted_burning_rate_mms=round(max(0.05, pred_br), 3),
            predicted_flame_temp_k=round(pred_ft, 1),
            std6001_comparison=std_comp,
            recommendations=recs,
            nearest_experiments=nearest,
        )

    def get_ranked_insights(self) -> dict[str, Any]:
        """Compute ranked fire-safety findings and dataset family criticality scores."""
        df = self.phys_df.copy()

        # Load PSI search catalog if available to link PSI accessions
        psi_search_path = PROJECT_ROOT / "data" / "raw" / "psi_combustion_search.json"
        psi_catalog: list[dict[str, Any]] = []
        if psi_search_path.exists():
            try:
                raw_psi = json.loads(psi_search_path.read_text(encoding="utf-8"))
                for h in raw_psi.get("hits", {}).get("hits", []):
                    src = h.get("_source", {})
                    psi_catalog.append(
                        {
                            "accession": src.get("Accession"),
                            "acronym": src.get("Acronym"),
                            "title": src.get("Title"),
                            "sub_area": src.get("SubResearch Area"),
                            "platform": src.get("Flight Platform"),
                            "hardware": (src.get("Experiment Hardware") or {}).get("Name", ""),
                            "objectives": src.get("Objectives", ""),
                        }
                    )
            except Exception:
                pass

        # Aggregate family stats
        family_rankings: list[dict[str, Any]] = []
        for fam, grp in df.groupby("dataset_family"):
            n_rows = len(grp)
            mean_o2 = float(grp["oxygen_pct"].dropna().mean()) if grp["oxygen_pct"].notna().any() else 21.0
            max_o2 = float(grp["oxygen_pct"].dropna().max()) if grp["oxygen_pct"].notna().any() else 21.0
            min_kpa = float(grp["pressure_kpa"].dropna().min()) if grp["pressure_kpa"].notna().any() else 101.3
            mean_br = (
                float(grp["burning_rate_mms"].dropna().mean())
                if grp["burning_rate_mms"].notna().any()
                else None
            )
            mean_temp = (
                float(grp["flame_temp_k"].dropna().mean())
                if grp["flame_temp_k"].notna().any()
                else None
            )
            sustained_frac = float(grp["extinction_outcome"].apply(_is_sustained_outcome).mean())

            # Criticality score: weights exploration-atmosphere coverage (high O2 / low kPa),
            # sample size, and sustained flammability evidence
            o2_span_score = min(1.0, max(0.0, (max_o2 - 21.0) / 20.0))
            low_p_score = min(1.0, max(0.0, (101.3 - min_kpa) / 60.0))
            vol_score = min(1.0, math.log10(n_rows + 1) / 2.5)
            criticality = round(
                100.0 * (0.35 * sustained_frac + 0.30 * o2_span_score + 0.20 * low_p_score + 0.15 * vol_score),
                1,
            )

            family_rankings.append(
                {
                    "dataset_family": str(fam),
                    "experiments_count": n_rows,
                    "criticality_score": criticality,
                    "sustained_burn_rate_pct": round(sustained_frac * 100.0, 1),
                    "mean_oxygen_pct": round(mean_o2, 1),
                    "max_oxygen_pct": round(max_o2, 1),
                    "min_pressure_kpa": round(min_kpa, 1),
                    "mean_burning_rate_mms": round(mean_br, 3) if mean_br is not None else None,
                    "mean_flame_temp_k": round(mean_temp, 0) if mean_temp is not None else None,
                    "sample_id": str(grp["experiment_id"].iloc[0]),
                }
            )

        family_rankings.sort(key=lambda r: r["criticality_score"], reverse=True)

        curated_findings = [
            {
                "rank": 1,
                "title": "Low-Velocity Microgravity Ventilation Enables Flame Spread Below 1g Limits",
                "severity": "CRITICAL",
                "score": 96.5,
                "families": ["BASS-II", "BASS-I", "SOFIE", "NASA-STD-6001"],
                "key_citations": ["BASS-B1", "BASS1-001", "SOFIE-001", "STD6001-001"],
                "summary": (
                    "In 1g (NASA-STD-6001 Test 1), buoyant plume flow (~20–30 cm/s) can cool thin fuels or induce blowoff. "
                    "In microgravity (BASS & BASS-II, 137 experiments), gentle cabin ventilation (2–15 cm/s) continuously "
                    "supplies oxygen without buoyant heat loss, allowing Cotton/Fiberglass (SIBAL), Nomex blends, and PMMA "
                    "to sustain combustion at lower oxygen concentrations than on Earth."
                ),
                "actionable_recommendation": (
                    "Immediately cut HVAC / ventilation airflow upon smoke detection and qualify Moon/Mars habitat materials "
                    "under low-speed forced microgravity flow rather than relying solely on 1g upward screening."
                ),
            },
            {
                "rank": 2,
                "title": "Exploration Atmosphere (34% O2, 56.5 kPa) Accelerates Large-Scale Flame Growth",
                "severity": "CRITICAL",
                "score": 94.0,
                "families": ["SAFFIRE-I", "SAFFIRE-II", "SAFFIRE-III", "SAFFIRE-IV", "SAFFIRE-V", "SAFFIRE-VI", "SOFIE"],
                "key_citations": ["SAF1-F1C1/F1C2", "SAF2-01", "SAF4-01", "SOFIE-003"],
                "summary": (
                    "Large-scale Cygnus spacecraft fire experiments (SAFFIRE I–VI, 19 tests up to 1 m length) and SOFIE "
                    "demonstrate that elevated oxygen (26.5%–34% O2) at reduced cabin pressure significantly increases "
                    "flame spread rate, cabin pressure rise, and CO/CO2 hazard compared to ISS 21% O2 / 101.3 kPa."
                ),
                "actionable_recommendation": (
                    "Enforce strict firebreaks, limit contiguous exposed polymer surface areas (< 30 cm), and size "
                    "post-fire cabin scrubbers for rapid CO and acid-gas removal in 34% O2 lunar habitats."
                ),
            },
            {
                "rank": 3,
                "title": "Two-Stage Cool Flames Persist Invisibly After Hot-Flame Extinction (~650–750 K)",
                "severity": "HIGH",
                "score": 89.2,
                "families": ["FLEX-2", "FLEX", "ACME-CFI", "ACME-CFI-G"],
                "key_citations": ["FLEX2-F2-01", "ACME-CFIG-001", "ACME-CFI-001", "FLEX-001"],
                "summary": (
                    "Spherical droplet (FLEX / FLEX-2) and gaseous counterflow/diffusion experiments (ACME CFI / CFI-G) "
                    "revealed that heavy hydrocarbons (n-Heptane, n-Decane, n-Butane) transition after radiative hot-flame "
                    "extinction (~1400 K) into self-sustaining low-temperature 'cool flames' (~650–750 K) that produce "
                    "partial oxidation intermediates (CO, formaldehyde) and can trigger explosive re-ignition."
                ),
                "actionable_recommendation": (
                    "Pair optical flame detectors with CO and multi-wavelength aerosol sensors (SAME) so crews do not "
                    "prematurely re-energize ventilation while cool-flame vapor pockets remain active."
                ),
            },
            {
                "rank": 4,
                "title": "Smoldering & Porous Foam Combustion Persists Hours at Very Low Oxygen Flux",
                "severity": "HIGH",
                "score": 84.5,
                "families": ["MGM (Smoldering)", "SAME (Aerosol)", "SAME-R"],
                "key_citations": ["MGM-001", "SAME-001", "SAMER-001"],
                "summary": (
                    "Microgravity Smoldering Combustion (MGM, 65 tests) shows that polyurethane foam insulation and "
                    "porous media sustain non-flaming exothermic oxidation at low airflow, generating dense toxic CO "
                    "and sub-micron smoke aerosols characterized by SAME / SAME-R."
                ),
                "actionable_recommendation": (
                    "Monitor enclosed avionics bays with ionization + photoelectric aerosol discriminators and thermal "
                    "sensors capable of detecting slow smolder fronts before flaming transition."
                ),
            },
            {
                "rank": 5,
                "title": "Electric-Field & Geometric Quenching Provide Non-Chemical Suppression Pathways",
                "severity": "MODERATE",
                "score": 78.0,
                "families": ["ACME-EFIELD", "GRC Drop Tower", "SLICE", "FLARE (JAXA/Kibo)"],
                "key_citations": ["ACME-EF-001", "GRC-DT-001", "SLICE-001", "FLARE-001"],
                "summary": (
                    "ACME E-FIELD (12 tests) demonstrates that high-voltage chemi-ion drift can manipulate soot and "
                    "destabilize laminar diffusion flames, while GRC Drop Tower (95 tests) quantifies exact quenching "
                    "distances and minimum droplet extinction diameters in 10^-5 g."
                ),
                "actionable_recommendation": (
                    "Incorporate narrow quenching-gap mesh screens in avionics cooling ducts and evaluate localized "
                    "electrostatic/acoustic suppression to reduce reliance on consumable gas suppressants."
                ),
            },
        ]

        return {
            "findings": curated_findings,
            "family_rankings": family_rankings,
            "psi_investigations": psi_catalog,
        }
