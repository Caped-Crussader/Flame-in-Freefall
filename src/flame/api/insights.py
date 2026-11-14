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


class FlammabilityEnvelope(BaseModel):
    """2D Flammability Map and Minimum Oxygen Concentration (MOC) boundary curves."""

    pressure_grid_kpa: list[float]
    oxygen_grid_pct: list[float]
    risk_matrix: list[list[float]]
    moc_0g_o2_pct: list[float]
    moc_1g_std6001_o2_pct: list[float]
    airflow_grid_cms: list[float]
    airflow_risk_matrix: list[list[float]]
    material_experiments: list[dict[str, Any]]


class PhysicsDiagnostics(BaseModel):
    """Physics-informed combustion diagnostics for the simulated cabin condition."""

    oxygen_partial_pressure_kpa: float = Field(
        description="Partial pressure of O2 in kPa (P_total * O2% / 100)."
    )
    normoxic_po2_ratio: float = Field(
        description="Ratio of P_O2 relative to ISS sea-level normoxic 21.27 kPa."
    )
    diluent_to_o2_ratio: float = Field(
        description="Inert N2/diluent-to-O2 molar ratio ((100 - O2%) / O2%)."
    )
    peclet_transport_factor: float = Field(
        description="Microgravity convective-diffusive oxidizer transport factor (0.0 to 1.0)."
    )
    moc_0g_limit_o2_pct: float = Field(
        description="Interpolated 0g Microgravity Minimum Oxygen Concentration (MOC) at this pressure."
    )
    moc_1g_std6001_limit_o2_pct: float = Field(
        description="Interpolated 1g NASA-STD-6001 MOC limit at this pressure."
    )
    moc_safety_margin_o2_pct: float = Field(
        description="Safety margin (MOC_0g - O2%); negative means ABOVE the 0g flammability limit."
    )
    transport_regime: str = Field(
        description="Physical flow regime (Diffusive Quenching, Peak Low-Stretch Hazard, or Blowoff)."
    )


class UncertaintyBounds(BaseModel):
    """90% Ensemble prediction intervals and epistemic confidence metrics."""

    burning_rate_ci90_mms: list[float] = Field(
        description="10th to 90th percentile burning rate prediction interval (mm/s) across RF trees."
    )
    flame_temp_ci90_k: list[float] = Field(
        description="10th to 90th percentile flame temperature prediction interval (K) across RF trees."
    )
    sustained_prob_std: float = Field(
        description="Standard deviation of sustained burn probability across ensemble trees."
    )
    confidence_score: float = Field(
        description="0.0 to 1.0 confidence score combining tree agreement and nearest-neighbor distance."
    )
    confidence_level: str = Field(
        description="HIGH, MODERATE, or EXPLORATORY confidence."
    )


class ExtinguishantOption(BaseModel):
    """Evaluation of a spacecraft fire suppressant modality from SLICE & ISS/Orion hardware."""

    agent_name: str
    suitability: str
    effectiveness_pct: float
    mechanism_and_tradeoff: str
    cited_experiments: list[str]


class DetectionEvidenceRow(BaseModel):
    """Real NASA experiment row from SAME, SAME-R, DAFT, SLICE, SAFFIRE, or MGM."""

    experiment_id: str
    dataset_family: str
    fuel_material: str
    co_ppm: float | None
    extinction_outcome: str
    key_insight: str


class DetectionSuppressionAdvisor(BaseModel):
    """Spacecraft Fire Detection, Suppression & Post-Fire Cleanup Advisor (SAME, DAFT, SLICE, SAFFIRE IV-VI)."""

    recommended_detector_modality: str
    smoke_cmd_0g_um: float
    smoke_cmd_1g_um: float
    photoelectric_sensitivity: float
    ionization_sensitivity: float
    estimated_alarm_time_s: float
    detector_rationale: str
    lunar_dust_discrimination_note: str
    primary_extinguishant: str
    secondary_extinguishant: str
    required_co2_inerting_pct: float
    limiting_oxygen_index_pct: float
    extinguishant_options: list[ExtinguishantOption]
    estimated_peak_co_ppm: float
    nasa_smac_1hr_co_ppm: float
    nasa_smac_24hr_co_ppm: float
    co_toxicity_level: str
    secondary_toxic_byproducts: list[str]
    post_fire_cleanup_steps: list[str]
    evidence_experiments: list[DetectionEvidenceRow]


class RiskSimulationResponse(BaseModel):
    """Predicted flammability risk, 2D MOC envelope, physics diagnostics, and closest experiments."""

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
    envelope: FlammabilityEnvelope
    physics_diagnostics: PhysicsDiagnostics
    uncertainty: UncertaintyBounds
    detection_suppression: DetectionSuppressionAdvisor


class MissionSafetyDossierResponse(BaseModel):
    """Exportable NASA-style Mission Fire-Safety Dossier (Markdown + Print/PDF HTML Certificate)."""

    dossier_id: str
    generated_at_utc: str
    dataset_sha256: str
    certification_status: str
    risk_level: str
    risk_score: float
    markdown_report: str
    html_printable: str


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

    @staticmethod
    def _build_feature_matrix(
        o2_arr: np.ndarray,
        kpa_arr: np.ndarray,
        flow_arr: np.ndarray,
        mat_arr: np.ndarray,
    ) -> np.ndarray:
        """Build 7-column physics-informed feature matrix:
        [o2_pct, pressure_kpa, airflow_cms, mat_hazard, po2_kpa, diluent_ratio, peclet_factor]
        """
        po2_kpa = kpa_arr * (o2_arr / 100.0)
        diluent_ratio = np.clip((100.0 - o2_arr) / np.maximum(o2_arr, 1.0), 0.0, 20.0)
        peclet_factor = (flow_arr / (flow_arr + 2.0)) * np.exp(
            -np.maximum(0.0, flow_arr - 22.0) / 40.0
        )
        return np.column_stack(
            [o2_arr, kpa_arr, flow_arr, mat_arr, po2_kpa, diluent_ratio, peclet_factor]
        )

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

        X = self._build_feature_matrix(
            df["o2"].to_numpy(dtype=float),
            df["kpa"].to_numpy(dtype=float),
            df["flow"].to_numpy(dtype=float),
            df["mat_score"].to_numpy(dtype=float),
        )

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

        # 4. Nearest-neighbors index in scaled 7-d physics feature space
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

        x_vec = self._build_feature_matrix(
            np.array([req.oxygen_pct], dtype=float),
            np.array([req.pressure_kpa], dtype=float),
            np.array([req.airflow_velocity_cms], dtype=float),
            np.array([mat_h], dtype=float),
        )
        proba = float(self._clf.predict_proba(x_vec)[0][1])

        pred_br = float(self._br_reg.predict(x_vec)[0]) if self._br_reg is not None else 1.2
        pred_ft = float(self._ft_reg.predict(x_vec)[0]) if self._ft_reg is not None else 1450.0

        # Ensemble tree variance & 90% prediction intervals (10th to 90th percentile across trees)
        clf_tree_preds = np.array(
            [est.predict_proba(x_vec)[0][1] for est in self._clf.estimators_], dtype=float
        )
        prob_std = float(np.std(clf_tree_preds))

        if self._br_reg is not None:
            br_tree_preds = np.array(
                [est.predict(x_vec)[0] for est in self._br_reg.estimators_], dtype=float
            )
            br_p10 = round(max(0.02, float(np.percentile(br_tree_preds, 10))), 3)
            br_p90 = round(max(br_p10 + 0.05, float(np.percentile(br_tree_preds, 90))), 3)
        else:
            br_p10, br_p90 = round(max(0.05, pred_br * 0.7), 3), round(pred_br * 1.3, 3)

        if self._ft_reg is not None:
            ft_tree_preds = np.array(
                [est.predict(x_vec)[0] for est in self._ft_reg.estimators_], dtype=float
            )
            ft_p10 = round(max(500.0, float(np.percentile(ft_tree_preds, 10))), 1)
            ft_p90 = round(max(ft_p10 + 25.0, float(np.percentile(ft_tree_preds, 90))), 1)
        else:
            ft_p10, ft_p90 = 1200.0, 1650.0

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

        envelope = self._compute_envelope(req, mat_h)

        # Physics diagnostics
        po2_kpa = round(req.pressure_kpa * (req.oxygen_pct / 100.0), 2)
        normoxic_ratio = round(po2_kpa / 21.27, 2)
        diluent_ratio = round((100.0 - req.oxygen_pct) / max(1.0, req.oxygen_pct), 2)
        peclet_val = round(
            float(
                (req.airflow_velocity_cms / (req.airflow_velocity_cms + 2.0))
                * math.exp(-max(0.0, req.airflow_velocity_cms - 22.0) / 40.0)
            ),
            3,
        )

        # Interpolate 0g and 1g MOC at req.pressure_kpa
        moc_0g_interp = round(
            float(np.interp(req.pressure_kpa, envelope.pressure_grid_kpa, envelope.moc_0g_o2_pct)),
            2,
        )
        moc_1g_interp = round(
            float(
                np.interp(
                    req.pressure_kpa, envelope.pressure_grid_kpa, envelope.moc_1g_std6001_o2_pct
                )
            ),
            2,
        )
        moc_margin = round(moc_0g_interp - req.oxygen_pct, 2)

        if req.airflow_velocity_cms < 1.5:
            regime_str = "Diffusive Quenching (<1.5 cm/s)"
        elif req.airflow_velocity_cms <= 25.0:
            regime_str = "Peak Microgravity Ventilation Hazard (1.5–25 cm/s)"
        else:
            regime_str = "Convective Blowoff Regime (>25 cm/s)"

        physics_diag = PhysicsDiagnostics(
            oxygen_partial_pressure_kpa=po2_kpa,
            normoxic_po2_ratio=normoxic_ratio,
            diluent_to_o2_ratio=diluent_ratio,
            peclet_transport_factor=peclet_val,
            moc_0g_limit_o2_pct=moc_0g_interp,
            moc_1g_std6001_limit_o2_pct=moc_1g_interp,
            moc_safety_margin_o2_pct=moc_margin,
            transport_regime=regime_str,
        )

        # Epistemic confidence combining tree agreement and nearest-neighbor distance
        min_dist = nearest[0].distance if nearest else 2.5
        dist_conf = math.exp(-max(0.0, min_dist) / 3.5)
        tree_conf = max(0.0, 1.0 - 1.4 * prob_std)
        conf_score = round(min(0.99, max(0.25, 0.55 * dist_conf + 0.45 * tree_conf)), 2)
        if conf_score >= 0.75:
            conf_level = "HIGH"
        elif conf_score >= 0.52:
            conf_level = "MODERATE"
        else:
            conf_level = "EXPLORATORY"

        uncertainty = UncertaintyBounds(
            burning_rate_ci90_mms=[br_p10, br_p90],
            flame_temp_ci90_k=[ft_p10, ft_p90],
            sustained_prob_std=round(prob_std, 3),
            confidence_score=conf_score,
            confidence_level=conf_level,
        )

        det_sup = self._compute_detection_and_suppression(req=req, risk_score=risk_score)

        return RiskSimulationResponse(
            risk_score=risk_score,
            risk_level=level,
            sustained_burn_probability=round(proba, 3),
            predicted_burning_rate_mms=round(max(0.05, pred_br), 3),
            predicted_flame_temp_k=round(pred_ft, 1),
            std6001_comparison=std_comp,
            recommendations=recs,
            nearest_experiments=nearest,
            envelope=envelope,
            physics_diagnostics=physics_diag,
            uncertainty=uncertainty,
            detection_suppression=det_sup,
        )

    def _compute_detection_and_suppression(
        self, req: RiskSimulationRequest, risk_score: float
    ) -> DetectionSuppressionAdvisor:
        """Compute smoke detector modality, SLICE extinguishant selection, CO toxicity, and cleanup protocol."""
        mat_low = req.fuel_material.lower()

        # 1. Aerosol particle size (CMD in um) & detector sensitivity from SAME / SAME-R / DAFT data
        if any(k in mat_low for k in ("kapton", "polyimide", "wire")):
            cmd_0g = 0.42
            cmd_1g = 0.14
            photo_sens = 0.91
            ion_sens = 0.64
            modality = "Dual-Wavelength Laser Scattering Photoelectric + CO Sensor (ISS / Orion Multi-Angle)"
            rationale = (
                "Grounded in SAME-AERO-001..015 and SAMER-MSG-001: Overheated Kapton wire pyrolysis in "
                "microgravity yields larger aerosol Count Median Diameter (CMD ~0.42 μm vs. ~0.14 μm in 1g) "
                "due to prolonged residence time and thermal coagulation in the absence of buoyant plumes, "
                "giving forward-scattering laser photoelectric detectors a 42% higher signal-to-noise ratio "
                "than legacy Shuttle Americium-241 ionization chambers."
            )
            base_co_ppm = 139.4
            tox_gases = [
                "Carbon Monoxide (CO) from aromatic polyimide pyrolysis (SAME mean 139.4 ppm, max 292.3 ppm)",
                "Hydrogen Cyanide (HCN) trace emissions from imide ring cleavage above 550 °C",
            ]
        elif any(k in mat_low for k in ("ptfe", "teflon", "fluoropolymer")):
            cmd_0g = 0.28
            cmd_1g = 0.09
            photo_sens = 0.78
            ion_sens = 0.88
            modality = "Hybrid Ionization + Laser Photoelectric + Acid-Gas (HF/COF₂) Electrochemical Sensor"
            rationale = (
                "Grounded in SAME-AERO-003, SAME-AERO-007, and SAMER-MSG-002: Overheated PTFE/Teflon insulation "
                "initially sheds ultrafine fluoropolymer nuclei (CMD ~0.28 μm in 0g) that trigger high-sensitivity "
                "ionization chambers rapidly, followed by chain-like aggregate coagulation detectable by laser "
                "nephelometry. Pairing with HF/CO gas sensing provides earliest warning before visible flaming."
            )
            base_co_ppm = 142.7
            tox_gases = [
                "Hydrogen Fluoride (HF) & Carbonyl Fluoride (COF₂) — extreme corrosive lung/avionics hazard",
                "Ultrafine PTFE polymer fume particles (<0.3 μm) capable of polymer fume fever",
                "Carbon Monoxide (CO) (SAME PTFE mean 142.7 ppm, max 251.8 ppm)",
            ]
        elif "silicone" in mat_low:
            cmd_0g = 0.58
            cmd_1g = 0.19
            photo_sens = 0.96
            ion_sens = 0.52
            modality = "Forward-Scattering Laser Photoelectric Nephelometer (ISS USOS / Orion Smoke Detector)"
            rationale = (
                "Grounded in SAME-AERO-002, SAME-AERO-005, and SAMER-MSG-002: Silicone elastomer pyrolysis "
                "produces dense chain-like amorphous silica (SiO₂) aggregates (CMD ~0.58 μm in 0g). These "
                "coarse sub-micron chains scatter 650 nm / 405 nm laser light strongly (96% sensitivity) "
                "while poorly reducing ion current in ionization detectors."
            )
            base_co_ppm = 184.8
            tox_gases = [
                "Amorphous Silica (SiO₂) sub-micron ash chains that rapidly foul HEPA & catalytic beds",
                "Carbon Monoxide (CO) (SAME Silicone mean 184.8 ppm, max 309.4 ppm)",
                "Cyclic siloxane vapor condensates",
            ]
        elif any(k in mat_low for k in ("foam", "polyurethane")):
            cmd_0g = 0.62
            cmd_1g = 0.22
            photo_sens = 0.95
            ion_sens = 0.49
            modality = "Dual-Angle Laser Photoelectric + Electrochemical CO Smolder Detector (MGM / ISS)"
            rationale = (
                "Grounded in MGM-ISS-001..065: Open-cell polyurethane foam undergoes low-temperature "
                "self-sustained smoldering (556–712 K) generating large condensed tar droplets (CMD ~0.62 μm) "
                "and extreme Carbon Monoxide surges (157–393 ppm) long before open flaming occurs."
            )
            base_co_ppm = 284.1
            tox_gases = [
                "Severe Carbon Monoxide (CO) accumulation (MGM-ISS mean 284 ppm, peak 393.1 ppm)",
                "Hydrogen Cyanide (HCN) & Isocyanate vapors from urethane bond pyrolysis",
                "TCPP chlorinated phosphate retardant vapors (if flame-retarded foam)",
            ]
        elif any(k in mat_low for k in ("methanol", "ethanol", "heptane", "methane", "ethylene")):
            cmd_0g = 0.14
            cmd_1g = 0.06
            photo_sens = 0.42
            ion_sens = 0.74
            modality = "UV/IR Optical Flame Detector + Tunable Diode Laser CO/CO₂ Absorption (ACME / FLEX)"
            rationale = (
                "Grounded in FLEX, FLEX-2 (PSI-10), and ACME-BRE: Alcohols (Methanol/Ethanol) burn with "
                "virtually soot-free blue spherical flames and radiative cool-flame stages (~740 K), while "
                "n-Heptane forms soot shells only inside low-stretch stagnation halos. Optical UV/IR and "
                "gas-phase CO/CO₂ sensors outperform particulate smoke detectors for liquid/gas leaks."
            )
            base_co_ppm = 55.0
            tox_gases = [
                "Formaldehyde (CH₂O) & Carbon Monoxide (CO) from incomplete cool-flame oxidation (~740 K)",
                "Elevated Carbon Dioxide (CO₂) and localized oxygen depletion",
            ]
        elif any(k in mat_low for k in ("nomex", "velcro", "nylon", "aramid")):
            cmd_0g = 0.46
            cmd_1g = 0.16
            photo_sens = 0.90
            ion_sens = 0.62
            modality = "Dual-Wavelength Laser Scattering Photoelectric (DAFT M₁/M₀ Moment Discriminator)"
            rationale = (
                "Grounded in SAFFIREIII-S3-2, SAFFIREIV-S4-3, and SLICE-008: Nitrogenous textiles (Nomex aramid "
                "and Nylon Velcro) self-extinguish at 21% O₂ but sustain vigorous charring propagation in 26–34% O₂ "
                "exploration atmospheres, emitting 0.46 μm carbonaceous smoke aerosols well suited to laser scattering."
            )
            base_co_ppm = 92.0
            tox_gases = [
                "Hydrogen Cyanide (HCN) & Ammonia (NH₃) from polyamide/aramid nitrogen pyrolysis",
                "Carbon Monoxide (CO) from incomplete char oxidation",
            ]
        else:
            # Default cellulosic / SIBAL / Cotton / Tissue / PMMA solid fuels
            is_pmma = "pmma" in mat_low or "acrylic" in mat_low
            cmd_0g = 0.39 if is_pmma else 0.49
            cmd_1g = 0.13 if is_pmma else 0.17
            photo_sens = 0.92 if is_pmma else 0.94
            ion_sens = 0.66 if is_pmma else 0.61
            modality = "Dual-Wavelength Laser Scattering Photoelectric (ISS / Orion / Artemis Multi-Angle)"
            rationale = (
                "Grounded in SAME-AERO-006 (Cotton Wick Precursor), SOFIE-001..003 (PMMA), and SAFFIREIV-S4-1..S6-2 "
                "(SIBAL & PMMA): Microgravity pyrolysis vapour condenses into 0.39–0.49 μm spherical/chain aerosols "
                "(~3× larger than 1g smoke due to absence of buoyant shear), placing peak Mie scattering efficiency "
                "directly inside laser photoelectric nephelometer bands."
            )
            base_co_ppm = 78.0 if is_pmma else 148.0
            tox_gases = (
                [
                    "Methyl Methacrylate (MMA) monomer vapor from depolymerizing acrylic (SOFIE / SAFFIRE-V)",
                    "Carbon Monoxide (CO) (SOFIE-003 peak 110 ppm; SAFFIRE-VI far-field plume)",
                ]
                if is_pmma
                else [
                    "Carbon Monoxide (CO) & Acrolein aldehydes from cellulosic pyrolysis (SAME mean 184.8 ppm)",
                    "Fine carbonaceous soot & fiberglass char particulates (SAFFIRE-III / V / VI)",
                ]
            )

        # Airflow effect on alarm transport delay
        if req.airflow_velocity_cms < 1.5:
            alarm_delay_s = 145.0
        else:
            alarm_delay_s = round(max(8.0, min(120.0, 180.0 / (req.airflow_velocity_cms + 1.2))), 1)

        dust_note = (
            "Grounded in DAFT-MSG-001 & DAFT2-MSG-002: In Artemis Lunar Surface Habitats & Pressurized Rovers "
            f"({req.oxygen_pct:.1f}% O₂, {req.pressure_kpa:.1f} kPa), suspended lunar regolith dust (JSC-1A / Highlands "
            "simulant >1.2 μm) triggers false alarms in single-channel optical detectors. Use DAFT M₁/M₀ aerosol "
            f"moment-ratio discrimination to separate coarse regolith (>1.0 μm) from {req.fuel_material} pyrolysis "
            f"smoke (0g CMD ~{cmd_0g:.2f} μm)."
        )

        # 2. Extinguishant selection grounded in SLICE-001..008 and SAFFIRE
        o2_excess = max(0.0, req.oxygen_pct - 21.0)
        req_co2_pct = round(min(36.0, 14.5 + 0.95 * o2_excess + (3.5 if risk_score > 0.65 else 0.0)), 1)
        loi_pct = round(max(11.5, 14.2 - 1.8 * risk_score), 1)

        is_liquid_or_gas = any(k in mat_low for k in ("methanol", "ethanol", "heptane", "methane", "ethylene"))
        is_electrical = any(k in mat_low for k in ("wire", "kapton", "ptfe", "cable"))

        if is_liquid_or_gas:
            primary_ext = f"Concentrated CO₂ Inerting Flood ({req_co2_pct:.1f}% Vol Fraction) [SLICE-001 / SLICE-002]"
            secondary_ext = f"Nitrogen (N₂) Dilution below {loi_pct:.1f}% LOI [SLICE-003]"
        elif is_electrical:
            primary_ext = f"De-Energize Bus + Portable CO₂ Flood ({req_co2_pct:.1f}% Vol) [SLICE-001 / SAME-AERO]"
            secondary_ext = "Portable Fine Water Mist (ISS USOS / Orion PFE — safe after bus isolation) [SLICE-007]"
        else:
            primary_ext = "Portable Fine Water Mist Extinguisher (ISS USOS / Orion PFE) [SLICE-007 / SLICE-008]"
            secondary_ext = f"Concentrated CO₂ Flood ({req_co2_pct:.1f}% Vol Fraction) + Cabin Fan Cutoff [SLICE-002]"

        water_eff = 72.0 if is_liquid_or_gas else (86.0 if is_electrical else 94.0)
        co2_eff = 93.0 if req.oxygen_pct <= 26.5 else 82.0
        n2_eff = 91.0 if req.pressure_kpa <= 75.0 else 85.0
        halon_eff = 78.0 if req.oxygen_pct < 28.0 else 58.0

        ext_options = [
            ExtinguishantOption(
                agent_name="Fine Water Mist (ISS USOS / Orion Portable Fire Extinguisher)",
                suitability="OPTIMAL" if not is_liquid_or_gas else "CAUTION",
                effectiveness_pct=water_eff,
                mechanism_and_tradeoff=(
                    "High latent heat of vaporization cools solid pyrolysis surfaces (PMMA, SIBAL, Nomex, Foam) "
                    "without adding toxic cabin gas [SLICE-007, SLICE-008]. Avoid direct spray on unisolated high-voltage "
                    "buses or pool liquid fuels."
                ),
                cited_experiments=["SLICE-007", "SLICE-008"],
            ),
            ExtinguishantOption(
                agent_name=f"Carbon Dioxide (CO₂) Inerting Flood ({req_co2_pct:.1f}% Target Vol)",
                suitability="OPTIMAL" if is_liquid_or_gas or is_electrical else "RECOMMENDED",
                effectiveness_pct=co2_eff,
                mechanism_and_tradeoff=(
                    f"Displaces O₂ and absorbs radiative heat in enclosed avionics racks [SLICE-001: 12.5% CO₂, "
                    f"SLICE-002: 18.0% CO₂]. At {req.oxygen_pct:.1f}% O₂, requires ~{req_co2_pct:.1f}% local CO₂ "
                    "concentration; crew must don O₂ masks to avoid hypercapnia (>2% cabin CO₂)."
                ),
                cited_experiments=["SLICE-001", "SLICE-002"],
            ),
            ExtinguishantOption(
                agent_name=f"Nitrogen (N₂) Dilution / Cabin Depressurization (Target <{loi_pct:.1f}% O₂)",
                suitability="RECOMMENDED",
                effectiveness_pct=n2_eff,
                mechanism_and_tradeoff=(
                    f"Reduces oxygen mole fraction below the {loi_pct:.1f}% Limiting Oxygen Index [SLICE-003: 13.8% LOI] "
                    "and starves convective O₂ transport when paired with HVAC fan shutdown (<1.5 cm/s)."
                ),
                cited_experiments=["SLICE-003", "SLICE-004"],
            ),
            ExtinguishantOption(
                agent_name="Halon Replacement (CF₃I / FK-5-1-12 Chemical Suppressant)",
                suitability="CAUTION" if req.oxygen_pct < 28.0 else "AVOID IN HIGH O₂",
                effectiveness_pct=halon_eff,
                mechanism_and_tradeoff=(
                    "Free-radical scavenging extinguishes 21% O₂ hydrocarbon flames [SLICE-005], but requires "
                    "substantially higher agent concentration in ≥30% O₂ exploration atmospheres [SLICE-006] and "
                    "generates toxic HF/HI acid gas decomposition products that poison ECLSS catalyst beds."
                ),
                cited_experiments=["SLICE-005", "SLICE-006"],
            ),
        ]

        # 3. CO toxicity warning & post-fire cleanup grounded in SAME, MGM, SAFFIRE IV-VI
        o2_co_mult = 1.0 + 0.018 * max(0.0, req.oxygen_pct - 21.0)
        flow_co_mult = 1.28 if req.airflow_velocity_cms < 2.5 else 1.0
        est_co_ppm = round(base_co_ppm * o2_co_mult * flow_co_mult, 1)

        smac_1hr = 55.0
        smac_24hr = 20.0
        if est_co_ppm >= 110.0:
            co_level = "CRITICAL (>2× 1-hr NASA SMAC)"
        elif est_co_ppm >= smac_1hr:
            co_level = "HIGH (Exceeds 55 ppm 1-hr NASA SMAC)"
        elif est_co_ppm >= smac_24hr:
            co_level = "MODERATE (Exceeds 20 ppm 24-hr NASA SMAC)"
        else:
            co_level = "LOW (<20 ppm NASA SMAC)"

        cleanup_steps = [
            (
                "1. Immediate Crew & Ventilation Action: Shut down inter-module HVAC ventilation fans (<1.5 cm/s) "
                "to induce diffusive flame quenching and halt far-field soot/CO migration [SAFFIREVI-S6-1], while "
                "crew dons Quick-Don Masks (QDMs) / Portable Breathing Apparatus (PBA)."
            ),
            (
                f"2. Catalytic CO Oxidation (CatOx): Route cabin air through the Trace Contaminant Control Subassembly "
                f"(TCCS) ambient/high-temp catalytic oxidizer to convert peak ~{est_co_ppm:.0f} ppm CO into CO₂ "
                f"until cabin CO drops below the 20 ppm 24-hr NASA SMAC [SAFFIREVI-S6-2]."
            ),
            (
                f"3. Multi-Stage HEPA + Charcoal Particulate Scrubbing: Engage portable post-fire scrubber beds to "
                f"capture sub-micron pyrolysis aerosols (0g CMD ~{cmd_0g:.2f} μm) before silica/soot chains foul "
                "primary ECLSS heat exchangers [SAME-AERO-004, SAMER-MSG-002]."
            ),
            (
                "4. Acid Gas & Monomer Polishing: Activate LiOH / activated-carbon acid-gas cartridges to strip "
                f"{tox_gases[0].split('(')[0].strip()} prior to crew mask doffing [SAFFIREVI-S6-2]."
            ),
        ]

        # 4. Retrieve 6 grounded experimental records from SAME, SAME-R, DAFT, SLICE, SAFFIRE-IV..VI, MGM
        det_families = [
            "SAME (Aerosol)",
            "SAME-R",
            "DAFT / DAFT-2",
            "SLICE",
            "SAFFIRE-IV",
            "SAFFIRE-V",
            "SAFFIRE-VI",
            "MGM (Smoldering)",
        ]
        sub = self.df[self.df["dataset_family"].isin(det_families)].copy()
        mat_token = req.fuel_material.split("(")[0].strip().lower()

        def _row_priority(r: pd.Series) -> float:
            score = 0.0
            f_mat = str(r.get("fuel_material", "")).lower()
            fam = str(r.get("dataset_family", ""))
            if mat_token and (mat_token in f_mat or any(w in f_mat for w in mat_token.split()[:2])):
                score += 5.0
            if fam in ("DAFT / DAFT-2", "SAME-R", "SAFFIRE-VI", "SLICE"):
                score += 2.5
            r_o2 = r.get("oxygen_pct")
            if pd.notna(r_o2):
                score -= abs(float(r_o2) - req.oxygen_pct) * 0.08
            return score

        sub["_prio"] = sub.apply(_row_priority, axis=1)
        sub = sub.sort_values("_prio", ascending=False)

        # Pick diverse rows across detection (SAME/DAFT), suppression (SLICE), and cleanup (SAFFIRE/MGM)
        picked_rows: list[DetectionEvidenceRow] = []
        seen_ids: set[str] = set()
        for target_fams in [
            {"SAME (Aerosol)", "SAME-R"},
            {"DAFT / DAFT-2"},
            {"SLICE"},
            {"SAFFIRE-IV", "SAFFIRE-V", "SAFFIRE-VI"},
            {"MGM (Smoldering)"},
        ]:
            cand = sub[sub["dataset_family"].isin(target_fams)]
            for _, row in cand.head(2).iterrows():
                eid = str(row["experiment_id"])
                if eid in seen_ids or len(picked_rows) >= 6:
                    continue
                seen_ids.add(eid)
                co_val = row.get("co_ppm")
                picked_rows.append(
                    DetectionEvidenceRow(
                        experiment_id=eid,
                        dataset_family=str(row["dataset_family"]),
                        fuel_material=str(row["fuel_material"]),
                        co_ppm=round(float(co_val), 1) if pd.notna(co_val) else None,
                        extinction_outcome=str(row.get("extinction_outcome") or "N/A"),
                        key_insight=str(row.get("notes") or row.get("extinction_outcome") or ""),
                    )
                )

        return DetectionSuppressionAdvisor(
            recommended_detector_modality=modality,
            smoke_cmd_0g_um=cmd_0g,
            smoke_cmd_1g_um=cmd_1g,
            photoelectric_sensitivity=photo_sens,
            ionization_sensitivity=ion_sens,
            estimated_alarm_time_s=alarm_delay_s,
            detector_rationale=rationale,
            lunar_dust_discrimination_note=dust_note,
            primary_extinguishant=primary_ext,
            secondary_extinguishant=secondary_ext,
            required_co2_inerting_pct=req_co2_pct,
            limiting_oxygen_index_pct=loi_pct,
            extinguishant_options=ext_options,
            estimated_peak_co_ppm=est_co_ppm,
            nasa_smac_1hr_co_ppm=smac_1hr,
            nasa_smac_24hr_co_ppm=smac_24hr,
            co_toxicity_level=co_level,
            secondary_toxic_byproducts=tox_gases,
            post_fire_cleanup_steps=cleanup_steps,
            evidence_experiments=picked_rows,
        )

    def _compute_envelope(self, req: RiskSimulationRequest, mat_h: float) -> FlammabilityEnvelope:
        """Compute 2D (Pressure x O2) and (Airflow x O2) flammability surfaces and MOC curves."""
        p_grid = [round(float(x), 1) for x in np.linspace(25.0, 115.0, 19)]
        o2_grid = [round(float(y), 1) for y in np.linspace(12.0, 48.0, 19)]
        flow_grid = [round(float(v), 1) for v in np.linspace(0.0, 55.0, 19)]

        # 1. Vectorized (O2 x Pressure) grid at selected airflow & material
        grid_o2, grid_p = [], []
        for o2_val in o2_grid:
            for p_val in p_grid:
                grid_o2.append(o2_val)
                grid_p.append(p_val)
        n_pts = len(grid_o2)
        X_grid = self._build_feature_matrix(
            np.asarray(grid_o2, dtype=float),
            np.asarray(grid_p, dtype=float),
            np.full(n_pts, req.airflow_velocity_cms, dtype=float),
            np.full(n_pts, mat_h, dtype=float),
        )
        probas = self._clf.predict_proba(X_grid)[:, 1]

        flow_assist = (
            1.0
            if 1.5 <= req.airflow_velocity_cms <= 30.0
            else (0.55 if req.airflow_velocity_cms < 1.5 else 0.72)
        )
        risk_matrix: list[list[float]] = []
        idx = 0
        for o2_val in o2_grid:
            row_scores: list[float] = []
            o2_f = min(1.0, max(0.0, (o2_val - 15.0) / 25.0))
            for p_val in p_grid:
                # Partial-pressure oxygen density effect at reduced cabin pressure
                p_factor = min(1.08, max(0.72, (p_val / 101.3) ** 0.18))
                r_val = min(
                    1.0,
                    max(
                        0.02,
                        (0.48 * float(probas[idx]) + 0.37 * o2_f + 0.15 * flow_assist * mat_h)
                        * p_factor,
                    ),
                )
                row_scores.append(round(r_val, 3))
                idx += 1
            risk_matrix.append(row_scores)

        # 2. Minimum Oxygen Concentration (MOC) boundary curves across pressure_grid_kpa
        #    In microgravity low-speed flow (BASS-II / SOFIE), MOC decreases as pressure increases
        #    due to higher O2 partial pressure / reduced radiative-to-convective heat loss ratio,
        #    and sits ~2.8% O2 lower than 1g upward NASA-STD-6001 screening.
        base_moc_101 = max(14.5, min(24.0, 21.5 - 5.5 * (mat_h - 0.35)))
        flow_penalty = 0.0 if 1.5 <= req.airflow_velocity_cms <= 25.0 else 2.2
        moc_0g: list[float] = []
        moc_1g: list[float] = []
        for p_val in p_grid:
            # Zeldovich / SOFIE pressure scaling for MOC: MOC(%) ~ MOC_101 * (101.3 / P)^0.22
            m0 = round((base_moc_101 + flow_penalty) * ((101.3 / p_val) ** 0.22), 2)
            m1 = round(m0 + 2.9 + 0.6 * ((p_val / 101.3) ** 0.5), 2)
            moc_0g.append(m0)
            moc_1g.append(m1)

        # 3. Vectorized (O2 x Airflow Velocity) quenching & blowoff map at selected pressure
        af_o2, af_flow = [], []
        for o2_val in o2_grid:
            for af_val in flow_grid:
                af_o2.append(o2_val)
                af_flow.append(af_val)
        n_af = len(af_o2)
        X_af = self._build_feature_matrix(
            np.asarray(af_o2, dtype=float),
            np.full(n_af, req.pressure_kpa, dtype=float),
            np.asarray(af_flow, dtype=float),
            np.full(n_af, mat_h, dtype=float),
        )
        af_probas = self._clf.predict_proba(X_af)[:, 1]

        airflow_risk_matrix: list[list[float]] = []
        af_idx = 0
        p_scale = min(1.08, max(0.72, (req.pressure_kpa / 101.3) ** 0.18))
        for o2_val in o2_grid:
            af_row_scores: list[float] = []
            o2_f = min(1.0, max(0.0, (o2_val - 15.0) / 25.0))
            for af_val in flow_grid:
                # Microgravity U-shaped ventilation curve (Olson / Ferkul BASS & SOFIE):
                # < 1.5 cm/s: diffusive oxygen starvation / radiative quenching
                # 2 - 22 cm/s: optimal oxygen supply without buoyant cooling (peak hazard)
                # > 32 cm/s: convective heat loss / blowoff regime
                if af_val < 1.5:
                    v_factor = 0.52 + 0.25 * (af_val / 1.5)
                elif af_val <= 22.0:
                    v_factor = 1.05
                else:
                    v_factor = max(0.58, 1.05 - 0.014 * (af_val - 22.0))
                r_af = min(
                    1.0,
                    max(
                        0.02,
                        (0.45 * float(af_probas[af_idx]) + 0.40 * o2_f + 0.15 * mat_h)
                        * p_scale
                        * v_factor,
                    ),
                )
                af_row_scores.append(round(r_af, 3))
                af_idx += 1
            airflow_risk_matrix.append(af_row_scores)

        # 4. Real experimental points for this material (or top peer points) to overlay on the 2D map
        df = self._nn_df
        mat_mask = df["fuel_material"].astype(str).str.lower().str.contains(
            req.fuel_material.split("(")[0].strip().lower(), na=False
        )
        sub_df = df[mat_mask] if mat_mask.sum() >= 5 else df
        sub_df = sub_df.dropna(subset=["oxygen_pct", "pressure_kpa"]).head(60)
        exp_points: list[dict[str, Any]] = []
        for _, r in sub_df.iterrows():
            af_v = r.get("airflow_velocity_cms")
            exp_points.append(
                {
                    "experiment_id": str(r["experiment_id"]),
                    "dataset_family": str(r["dataset_family"]),
                    "fuel_material": str(r["fuel_material"]),
                    "oxygen_pct": float(r["oxygen_pct"]),
                    "pressure_kpa": float(r["pressure_kpa"]),
                    "airflow_velocity_cms": (
                        float(af_v) if pd.notna(af_v) and not math.isnan(float(af_v)) else 5.0
                    ),
                    "extinction_outcome": str(r["extinction_outcome"]),
                    "sustained": bool(int(r["y_sustained"]) == 1),
                }
            )

        return FlammabilityEnvelope(
            pressure_grid_kpa=p_grid,
            oxygen_grid_pct=o2_grid,
            risk_matrix=risk_matrix,
            moc_0g_o2_pct=moc_0g,
            moc_1g_std6001_o2_pct=moc_1g,
            airflow_grid_cms=flow_grid,
            airflow_risk_matrix=airflow_risk_matrix,
            material_experiments=exp_points,
        )

    def get_ranked_insights(self) -> dict[str, Any]:
        """Compute ranked fire-safety findings and dataset family criticality scores."""
        df = self.phys_df.copy()

        # Load PSI search catalog if available to link PSI accessions
        psi_search_path = PROJECT_ROOT / "data" / "raw" / "psi" / "search_combustion.json"
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

        # 3. Historical Spacecraft Fire Incidents mapped to validated dataset experiments
        historical_incidents = [
            {
                "incident_id": "apollo-1-1967",
                "name": "Apollo 1 Command Module Cabin Fire (AS-204)",
                "date": "January 27, 1967",
                "mission": "Apollo 1 (Launch Pad 34 Plugs-Out Test)",
                "severity": "CATASTROPHIC",
                "atmosphere_o2_pct": 100.0,
                "pressure_kpa": 115.1,
                "gravity_regime": "1g (Pre-Launch Overpressure Pure O2)",
                "ignition_source_and_fuel": "Electrical arc near lower equipment bay -> Nylon Raschel netting, Velcro hook-and-loop strips, and polyurethane foam pads.",
                "what_happened": (
                    "In a pure 100% O2 cabin pressurized to 115.1 kPa (16.7 psia), an electrical spark ignited "
                    "contiguous Velcro and Nylon netting. Flame spread velocity exceeded 150 mm/s, rupturing the "
                    "inner pressure hull within 17 seconds and causing fatal CO asphyxiation and thermal injury."
                ),
                "microgravity_physics_insight": (
                    "Led directly to NASA-STD-6001 (NHB 8060.1) upward flammability screening, replacement of "
                    "pure O2 pre-launch atmospheres with 60% O2 / 40% N2, removal of contiguous Velcro, and introduction "
                    "of Beta cloth (Teflon-coated fiberglass). Our BASS-II and NASA-STD-6001 datasets show how oxygen "
                    "enrichment drastically lowers the Minimum Oxygen Concentration (MOC) for polymers and fabrics."
                ),
                "matched_dataset_families": ["NASA-STD-6001", "BASS-II", "SOFIE"],
                "matched_experiment_ids": ["STD6001-001", "STD6001-004", "BASS-B1", "SOFIE-001"],
                "official_nasa_url": "https://sma.nasa.gov/sma-disciplines/accllp/apollo-1",
            },
            {
                "incident_id": "apollo-13-1970",
                "name": "Apollo 13 Service Module Oxygen Tank No. 2 Fire & Rupture",
                "date": "April 13, 1970",
                "mission": "Apollo 13 (Translunar Coast, 321,860 km from Earth)",
                "severity": "CRITICAL",
                "atmosphere_o2_pct": 100.0,
                "pressure_kpa": 6200.0,
                "gravity_regime": "Microgravity (~0g, Supercritical O2 Tank)",
                "ignition_source_and_fuel": "Damaged thermostatic switch arc during detanking overheat -> PTFE (Teflon) wire insulation inside supercritical O2.",
                "what_happened": (
                    "During a routine cryo-stir in microgravity, exposed wiring arcs ignited PTFE (Teflon) insulation "
                    "inside supercritical 100% O2 Tank 2. Without buoyant convection, the localized high-pressure metal/fluoropolymer "
                    "combustion front rapidly overpressurized and ruptured the tank dome."
                ),
                "microgravity_physics_insight": (
                    "Demonstrated that even fluoropolymers rated self-extinguishing in 1g air (PTFE, Nomex) become "
                    "vigorously flammable under elevated oxygen partial pressure. SOFIE and NASA-STD-6001 high-O2 "
                    "records quantify the sharp drop in ignition energy and upward/opposed spread thresholds as O2% rises."
                ),
                "matched_dataset_families": ["SOFIE", "NASA-STD-6001", "SAFFIRE-IV"],
                "matched_experiment_ids": ["SOFIE-001", "SOFIE-003", "STD6001-002", "SAF4-01"],
                "official_nasa_url": "https://sma.nasa.gov/sma-disciplines/accllp/apollo-13",
            },
            {
                "incident_id": "mir-1997",
                "name": "Mir Space Station Solid-Fuel Oxygen Generator (Vika / TGK) Fire",
                "date": "February 23, 1997",
                "mission": "Mir EO-22 / NASA-Mir (Kvant-1 Module)",
                "severity": "CRITICAL",
                "atmosphere_o2_pct": 23.0,
                "pressure_kpa": 101.3,
                "gravity_regime": "Microgravity (~0g, Cabin Ventilation Active)",
                "ignition_source_and_fuel": "Contaminated lithium perchlorate (LiClO4) oxygen candle -> 0.5 m blowtorch jet, molten metal droplets, and dense smoke.",
                "what_happened": (
                    "A Vika (TGK) solid-fuel oxygen canister erupted into a self-oxidizing blowtorch in the Kvant-1 "
                    "module for ~90 seconds (with smoke clearing taking 45+ minutes). Three water-foam extinguishers failed "
                    "to stop the oxygen-generating reaction; cabin ventilation rapidly distributed dense metal-oxide smoke "
                    "aerosols across the entire station."
                ),
                "microgravity_physics_insight": (
                    "In microgravity, smoke aerosols do not settle by sedimentation and aggregate into larger fractal chains "
                    "under low shear flow — directly motivating the Smoke Aerosol Measurement Experiment (SAME / SAME-R, 42 tests) "
                    "and SAFFIRE post-burn scrubbers to prevent false alarms while ensuring early sub-micron detection."
                ),
                "matched_dataset_families": ["SAME (Aerosol)", "SAME-R", "BASS-I", "SAFFIRE-I"],
                "matched_experiment_ids": ["SAME-001", "SAMER-001", "BASS1-001", "SAF1-F1C1/F1C2"],
                "official_nasa_url": "https://www.nasa.gov/history/25-years-ago-fire-aboard-space-station-mir/",
            },
            {
                "incident_id": "artemis-sea-transition",
                "name": "ISS (21% O2) to Artemis Exploration Atmosphere (34% O2, 56.5 kPa) Qualification Gap",
                "date": "2016–2026 Flight Campaigns",
                "mission": "Cygnus SAFFIRE I–VI & ISS CIR / SOFIE",
                "severity": "HIGH",
                "atmosphere_o2_pct": 34.0,
                "pressure_kpa": 56.5,
                "gravity_regime": "Microgravity (~0g) & Lunar Partial Gravity (0.16g)",
                "ignition_source_and_fuel": "Large-scale PMMA, SIBAL (Cotton/Fiberglass), and Nomex panels under 3–20 cm/s forced ventilation.",
                "what_happened": (
                    "To eliminate pre-breathe protocols before lunar EVAs, future Artemis habitats and rovers adopt the "
                    "Space Exploration Atmosphere (SEA: 34% O2 at 56.5 kPa / 8.2 psia). Full-scale Cygnus SAFFIRE I–VI "
                    "burns proved that elevated O2 mole fraction outweighs reduced total pressure, doubling flame spread rates."
                ),
                "microgravity_physics_insight": (
                    "Across 19 SAFFIRE tests and 32 SOFIE tests in our dataset, flame growth at 34% O2 / 56.5 kPa produces "
                    "faster pyrolysis, higher flame temperatures (~1500–1750 K), and sustained propagation on thick PMMA rods "
                    "that self-extinguish at 21% O2."
                ),
                "matched_dataset_families": ["SAFFIRE-I", "SAFFIRE-II", "SAFFIRE-III", "SAFFIRE-IV", "SAFFIRE-V", "SAFFIRE-VI", "SOFIE"],
                "matched_experiment_ids": ["SAF1-F1C1/F1C2", "SAF2-01", "SAF3-01", "SAF5-01", "SAF6-01", "SOFIE-003"],
                "official_nasa_url": "https://www.nasa.gov/missions/station/iss-research/saffire/",
            },
        ]

        # 4. Rich PSI Investigation Dossiers & Downloaded Experimental CSV Table Previews
        psi_dossiers = self._load_psi_dossiers()
        psi_experimental_tables = self._load_psi_experimental_tables()

        return {
            "findings": curated_findings,
            "family_rankings": family_rankings,
            "psi_investigations": psi_catalog,
            "historical_incidents": historical_incidents,
            "psi_dossiers": psi_dossiers,
            "psi_experimental_tables": psi_experimental_tables,
        }

    def _load_psi_dossiers(self) -> list[dict[str, Any]]:
        """Parse rich metadata from downloaded PSI investigation JSON manifests."""
        candidates = [
            PROJECT_ROOT / "data" / "raw" / "psi" / "investigations" / "PSI-10.json",
            PROJECT_ROOT / "data" / "raw" / "psi" / "investigations" / "PSI-22.json",
            PROJECT_ROOT / "data" / "raw" / "psi" / "investigations" / "PSI-26.json",
        ]
        dossiers: list[dict[str, Any]] = []
        for path in candidates:
            if not path.exists():
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                contacts = []
                for c in raw.get("contacts") or []:
                    fn = f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
                    if fn and fn not in contacts:
                        contacts.append(fn)
                pubs = []
                for p in (raw.get("publications") or [])[:5]:
                    pubs.append(
                        {
                            "title": p.get("title", ""),
                            "authors": p.get("authorList", ""),
                            "doi": p.get("doi", ""),
                        }
                    )
                exp_tbls = [
                    t.get("file_name", "")
                    for t in (raw.get("experimentalTable") or []) + (raw.get("modelingTable") or [])
                    if t.get("file_name")
                ]
                dossiers.append(
                    {
                        "accession": raw.get("accession", path.stem),
                        "acronym": raw.get("investigationAcronym", ""),
                        "title": raw.get("title", ""),
                        "doi": raw.get("doi", ""),
                        "release_date": raw.get("releaseDate", ""),
                        "flight_program": raw.get("flightProgram", ""),
                        "hardware": raw.get("experimentHardware", ""),
                        "sub_research_area": raw.get("subResearchArea", ""),
                        "investigators": contacts[:6],
                        "publications_count": len(raw.get("publications") or []),
                        "top_publications": pubs,
                        "repo_files_count": len(raw.get("added") or []),
                        "experimental_table_files": exp_tbls,
                        "research_impacts": raw.get("researchImpacts", ""),
                    }
                )
            except Exception:
                continue
        return dossiers

    def _load_psi_experimental_tables(self) -> list[dict[str, Any]]:
        """Load interactive previews of downloaded PSI Experimental CSV tables."""
        tables_root = PROJECT_ROOT / "data" / "raw" / "psi" / "tables"
        if not tables_root.exists():
            return []
        out: list[dict[str, Any]] = []
        for csv_path in sorted(tables_root.rglob("*.csv")):
            try:
                tdf = pd.read_csv(csv_path)
                # Clean column names and convert NaN to None for JSON serialization
                tdf.columns = [str(c).strip() for c in tdf.columns]
                preview_records = json.loads(tdf.head(50).to_json(orient="records"))
                out.append(
                    {
                        "accession": csv_path.parent.name,
                        "file_name": csv_path.name,
                        "relative_path": str(csv_path.relative_to(PROJECT_ROOT)),
                        "row_count": int(len(tdf)),
                        "column_count": int(len(tdf.columns)),
                        "columns": list(tdf.columns),
                        "preview_rows": preview_records,
                    }
                )
            except Exception:
                continue
        return out

    def generate_safety_dossier(self, req: RiskSimulationRequest) -> MissionSafetyDossierResponse:
        """Generate an exportable Mission Fire-Safety Certification Dossier in Markdown and Print-Ready PDF/HTML."""
        from datetime import datetime, timezone
        import html

        sim = self.simulate(req)
        phys = sim.physics_diagnostics
        unc = sim.uncertainty
        det = sim.detection_suppression
        env = sim.envelope

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        v_info = self.store.get_version_info() if hasattr(self.store, "get_version_info") else {}
        sha_short = str(v_info.get("parquet_sha256", "4b3139dc"))[:12]
        mat_slug = (
            "".join(ch for ch in req.fuel_material.split("(")[0].upper() if ch.isalnum())[:8]
            or "MAT"
        )
        dossier_id = (
            f"IGNIS-CERT-{int(round(req.oxygen_pct * 10))}O2-"
            f"{int(round(req.pressure_kpa))}KPA-{mat_slug}"
        )

        if sim.risk_level == "LOW" and phys.moc_safety_margin_o2_pct >= 0.0:
            cert_status = "PASS — CERTIFIED WITHIN 0g & 1g MOC MARGIN"
        elif sim.risk_level in ("LOW", "MODERATE") and phys.moc_safety_margin_o2_pct >= -2.5:
            cert_status = "CONDITIONAL PASS — REQUIRES ECLSS VENTILATION & SUPPRESSION CONTROLS"
        else:
            cert_status = "WAIVER REQUIRED — EXCEEDS 0g MICROGRAVITY FLAMMABILITY THRESHOLD"

        # Build Markdown Report
        nearest_md_rows = "\n".join(
            f"| `{ne.experiment_id}` | {ne.dataset_family} | {ne.fuel_material} | "
            f"{ne.oxygen_pct if ne.oxygen_pct is not None else '—'}% | "
            f"{ne.pressure_kpa if ne.pressure_kpa is not None else '—'} kPa | "
            f"{ne.airflow_velocity_cms if ne.airflow_velocity_cms is not None else '—'} cm/s | "
            f"{ne.burning_rate_mms if ne.burning_rate_mms is not None else '—'} mm/s | "
            f"{ne.extinction_outcome} | `{ne.distance:.3f}` |"
            for ne in sim.nearest_experiments
        )
        ext_md_rows = "\n".join(
            f"| **{opt.agent_name}** | `{opt.suitability}` | {opt.effectiveness_pct:.0f}% | "
            f"{opt.mechanism_and_tradeoff} | {', '.join(f'`{c}`' for c in opt.cited_experiments)} |"
            for opt in det.extinguishant_options
        )
        det_ev_rows = "\n".join(
            f"| `{ev.experiment_id}` | {ev.dataset_family} | {ev.fuel_material} | "
            f"{f'{ev.co_ppm:.1f}' if ev.co_ppm is not None else '—'} | "
            f"{ev.extinction_outcome} | {ev.key_insight} |"
            for ev in det.evidence_experiments
        )
        recs_md = "\n".join(f"- {r}" for r in sim.recommendations)
        tox_md = "\n".join(f"- {g}" for g in det.secondary_toxic_byproducts)
        cleanup_md = "\n".join(f"- {s}" for s in det.post_fire_cleanup_steps)

        md_report = f"""# 🚀 SPACECRAFT & HABITAT FIRE-SAFETY CERTIFICATION DOSSIER
**Dossier ID:** `{dossier_id}`  
**Generated (UTC):** `{now_utc}`  
**Validated Dataset Snapshot SHA-256:** `{sha_short}` (`892` Total Records · `840` Physical Flight/Drop-Tower Tests)  
**Certification Determination:** **{cert_status}**

---

## 1. Mission Atmosphere & Specimen Specification
| Parameter | Specified Operating Value | Reference / Baseline |
| :--- | :--- | :--- |
| **Fuel / Specimen Material** | **{req.fuel_material}** | Evaluated against 30 NASA/JAXA combustion families |
| **Cabin Oxygen Concentration** | **{req.oxygen_pct:.1f}% O₂** | ISS Standard: `21.0% O₂` · Artemis SEA: `34.0% O₂` |
| **Total Cabin Pressure** | **{req.pressure_kpa:.1f} kPa** | ISS Standard: `101.3 kPa` · Artemis SEA: `56.5 kPa` |
| **HVAC Ventilation Velocity** | **{req.airflow_velocity_cms:.1f} cm/s** | Quiescent Quench: `<1.5 cm/s` · Peak Hazard: `1.5–25 cm/s` |
| **Gravity Regime** | **{req.gravity_regime}** | Low-stretch microgravity boundary-layer transport |

---

## 2. Coupled Microgravity Physics & Ensemble ML Flammability Assessment
| Metric | Value / Prediction | 90% Ensemble Interval / Physical Reference |
| :--- | :--- | :--- |
| **Composite Flammability Risk Level** | **{sim.risk_level} (`{sim.risk_score:.2f}` / 1.00)** | Epistemic Confidence: **{unc.confidence_level} (`{unc.confidence_score * 100:.0f}%`)** |
| **Sustained Burn Probability (ML)** | **{sim.sustained_burn_probability * 100:.1f}%** | Ensemble Tree StdDev: `±{unc.sustained_prob_std * 100:.1f}%` |
| **Predicted Flame Spread / Burn Rate** | **{sim.predicted_burning_rate_mms:.2f} mm/s** | 90% Prediction Interval: `{unc.burning_rate_ci90_mms[0]:.2f}–{unc.burning_rate_ci90_mms[1]:.2f} mm/s` |
| **Predicted Flame Temperature** | **{sim.predicted_flame_temp_k:.0f} K** | 90% Prediction Interval: `{unc.flame_temp_ci90_k[0]:.0f}–{unc.flame_temp_ci90_k[1]:.0f} K` |
| **Oxygen Partial Pressure ($P_{{\\text{{O}}_2}}$)** | **{phys.oxygen_partial_pressure_kpa:.2f} kPa** | `{phys.normoxic_po2_ratio:.2f}×` Earth Sea-Level Normoxic (`21.27 kPa`) |
| **Inert Diluent Heat-Sink Ratio ($\\text{{N}}_2/\\text{{O}}_2$)** | **{phys.diluent_to_o2_ratio:.2f} : 1** | Earth Sea-Level Air Baseline: `3.76 : 1` |
| **0g Microgravity MOC Limit** | **{phys.moc_0g_limit_o2_pct:.1f}% O₂** | 1g `NASA-STD-6001` MOC Limit: **{phys.moc_1g_std6001_limit_o2_pct:.1f}% O₂** |
| **0g MOC Safety Margin** | **{phys.moc_safety_margin_o2_pct:+.1f}% O₂** | `{phys.transport_regime}` (`Pe={phys.peclet_transport_factor:.2f}`) |

> **1g `NASA-STD-6001` vs. Microgravity Screening Comparison:**  
> {sim.std6001_comparison}

### Mandatory Engineering & ECLSS Controls
{recs_md}

---

## 3. Spacecraft Fire Detection, Suppression & Post-Fire Cleanup Specification (`SAME`, `DAFT`, `SLICE`, `SAFFIRE IV–VI`)

### 3.1 Smoke Detection Modality & Lunar Dust Discrimination
- **Recommended Detector Architecture:** **{det.recommended_detector_modality}**
- **Microgravity Smoke Particle Size (CMD):** `{det.smoke_cmd_0g_um:.2f} μm` in 0g (vs. `{det.smoke_cmd_1g_um:.2f} μm` in 1g)
- **Detector Modality Sensitivity (0g):** Laser Photoelectric Scattering `{det.photoelectric_sensitivity * 100:.0f}%` vs. Americium-241 Ionization `{det.ionization_sensitivity * 100:.0f}%`
- **Estimated HVAC Alarm Transport Delay:** `~{det.estimated_alarm_time_s:.1f} s`
- **Physical Rationale (`SAME` / `SAME-R`):** {det.detector_rationale}
- **Lunar Regolith False-Alarm Mitigation (`DAFT / DAFT-2`):** {det.lunar_dust_discrimination_note}

### 3.2 Spacecraft Fire Suppressant Evaluation (`SLICE-001..008`)
- **Primary Recommended Suppressant:** `{det.primary_extinguishant}`
- **Secondary / Backup Suppressant:** `{det.secondary_extinguishant}`
- **Target $\\text{{CO}}_2$ Flood Concentration:** `{det.required_co2_inerting_pct:.1f}% Vol` · **Target $\\text{{N}}_2$ Limiting Oxygen Index:** `<{det.limiting_oxygen_index_pct:.1f}% O₂`

| Suppressant Agent | Suitability | Effectiveness | Mechanism & Operational Tradeoff | Cited NASA Tests |
| :--- | :--- | :--- | :--- | :--- |
{ext_md_rows}

### 3.3 Carbon Monoxide ($\\text{{CO}}$) Toxicity & Post-Fire ECLSS Scrubbing (`SAME`, `MGM`, `SAFFIRE-VI`)
- **Estimated Peak Localized/Cabin $\\text{{CO}}$:** **{det.estimated_peak_co_ppm:.1f} ppm** — **{det.co_toxicity_level}**
- **NASA Spacecraft Maximum Allowable Concentration (SMAC):** 1-Hour Limit = `{det.nasa_smac_1hr_co_ppm:.0f} ppm` · 24-Hour Limit = `{det.nasa_smac_24hr_co_ppm:.0f} ppm`

**Toxic Pyrolysis Byproducts to Monitor:**
{tox_md}

**Post-Fire Cabin Scrubbing & Crew Recovery Protocol (`SAFFIRE-VI`):**
{cleanup_md}

---

## 4. Grounded NASA/JAXA Experimental Evidence Audit Log

### 4.1 Five Closest Physical Flammability Experiments in `(O₂, Pressure, Airflow, Material)` Space
| Experiment ID | Dataset Family | Fuel / Material | O₂ (%) | Pressure | Airflow | Burn Rate | Outcome | Euclidean Dist |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{nearest_md_rows}

### 4.2 Grounded Detection, Suppression & Cleanup Reference Tests (`SAME`, `DAFT`, `SLICE`, `SAFFIRE`, `MGM`)
| Experiment ID | Dataset Family | Material / Aerosol Test | Peak CO (ppm) | Outcome | Key Engineering Insight |
| :--- | :--- | :--- | :--- | :--- | :--- |
{det_ev_rows}

---
*Generated by **IGNIS — Flame in Freefall** (2026 NASA Space Apps Challenge) · Deterministic Physics-Informed Hybrid RAG & Ensemble Flammability Engine.*
"""

        # Build embedded SVG for the 2D MOC Boundary Curve (0g vs 1g NASA-STD-6001)
        p_grid = env.pressure_grid_kpa
        moc_0g = env.moc_0g_o2_pct
        moc_1g = env.moc_1g_std6001_o2_pct
        p_min, p_max = p_grid[0], p_grid[-1]
        o2_min, o2_max = 12.0, 48.0

        def _sx(p_val: float) -> float:
            return round(50.0 + ((p_val - p_min) / max(1.0, p_max - p_min)) * 420.0, 1)

        def _sy(o2_val: float) -> float:
            clamped = min(o2_max, max(o2_min, o2_val))
            return round(190.0 - ((clamped - o2_min) / (o2_max - o2_min)) * 160.0, 1)

        pts_0g = " ".join(f"{_sx(p_grid[i])},{_sy(moc_0g[i])}" for i in range(len(p_grid)))
        pts_1g = " ".join(f"{_sx(p_grid[i])},{_sy(moc_1g[i])}" for i in range(len(p_grid)))
        ux, uy = _sx(req.pressure_kpa), _sy(req.oxygen_pct)

        status_bg = (
            "#dcfce7"
            if cert_status.startswith("PASS")
            else ("#fef9c3" if cert_status.startswith("CONDITIONAL") else "#fee2e2")
        )
        status_fg = (
            "#166534"
            if cert_status.startswith("PASS")
            else ("#854d0e" if cert_status.startswith("CONDITIONAL") else "#991b1b")
        )

        nearest_html_rows = "".join(
            f"<tr><td><code>{html.escape(ne.experiment_id)}</code></td>"
            f"<td>{html.escape(ne.dataset_family)}</td>"
            f"<td>{html.escape(ne.fuel_material)}</td>"
            f"<td>{ne.oxygen_pct if ne.oxygen_pct is not None else '—'}%</td>"
            f"<td>{ne.pressure_kpa if ne.pressure_kpa is not None else '—'} kPa</td>"
            f"<td>{ne.airflow_velocity_cms if ne.airflow_velocity_cms is not None else '—'} cm/s</td>"
            f"<td>{ne.burning_rate_mms if ne.burning_rate_mms is not None else '—'} mm/s</td>"
            f"<td>{html.escape(ne.extinction_outcome)}</td></tr>"
            for ne in sim.nearest_experiments
        )
        ext_html_rows = "".join(
            f"<tr><td><strong>{html.escape(opt.agent_name)}</strong></td>"
            f"<td><code>{html.escape(opt.suitability)}</code></td>"
            f"<td>{opt.effectiveness_pct:.0f}%</td>"
            f"<td>{html.escape(opt.mechanism_and_tradeoff)}</td>"
            f"<td><code>{html.escape(', '.join(opt.cited_experiments))}</code></td></tr>"
            for opt in det.extinguishant_options
        )

        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{html.escape(dossier_id)} — NASA Space Apps Mission Fire-Safety Dossier</title>
<style>
  @page {{ size: A4 portrait; margin: 14mm; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #0f172a;
    background: #ffffff;
    line-height: 1.45;
    font-size: 12px;
    margin: 0;
    padding: 20px;
  }}
  .header {{
    border-bottom: 3px solid #0f172a;
    padding-bottom: 12px;
    margin-bottom: 16px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }}
  .eyebrow {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #475569;
  }}
  h1 {{ font-size: 20px; margin: 4px 0; color: #0f172a; }}
  h2 {{
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 4px;
    margin: 16px 0 8px;
    color: #1e293b;
  }}
  .cert-banner {{
    background: {status_bg};
    color: {status_fg};
    border: 1px solid {status_fg};
    padding: 10px 14px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 13px;
    margin-bottom: 14px;
  }}
  .grid-4 {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 12px;
  }}
  .kpi {{
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 8px 10px;
    background: #f8fafc;
  }}
  .kpi .lbl {{ font-size: 10px; color: #475569; text-transform: uppercase; }}
  .kpi .val {{ font-size: 15px; font-weight: 800; color: #0f172a; margin-top: 2px; }}
  .kpi .sub {{ font-size: 10px; color: #64748b; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 6px;
    margin-bottom: 12px;
    font-size: 11px;
  }}
  th, td {{
    border: 1px solid #cbd5e1;
    padding: 6px 8px;
    text-align: left;
    vertical-align: top;
  }}
  th {{ background: #f1f5f9; font-weight: 700; }}
  code {{ font-family: monospace; background: #f1f5f9; padding: 1px 4px; border-radius: 3px; }}
  .no-print {{
    margin-bottom: 16px;
    display: flex;
    gap: 10px;
  }}
  .btn-print {{
    background: #ea580c;
    color: #fff;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 700;
    cursor: pointer;
  }}
  @media print {{
    .no-print {{ display: none !important; }}
    body {{ padding: 0; }}
  }}
</style>
</head>
<body>
  <div class="no-print">
    <button class="btn-print" onclick="window.print()">🖨️ Print / Save as PDF</button>
  </div>
  <div class="header">
    <div>
      <div class="eyebrow">NASA Space Apps · IGNIS Microgravity Fire-Safety Engineering Dossier</div>
      <h1>Spacecraft Material & Atmosphere Flammability Certificate</h1>
      <div>Material: <strong>{html.escape(req.fuel_material)}</strong> · Atmosphere: <strong>{req.oxygen_pct:.1f}% O₂, {req.pressure_kpa:.1f} kPa, {req.airflow_velocity_cms:.1f} cm/s</strong></div>
    </div>
    <div style="text-align:right; font-size:11px;">
      <div><strong>ID:</strong> <code>{html.escape(dossier_id)}</code></div>
      <div><strong>UTC:</strong> {html.escape(now_utc)}</div>
      <div><strong>Snapshot SHA:</strong> <code>{html.escape(sha_short)}</code></div>
    </div>
  </div>

  <div class="cert-banner">
    DETERMINATION: {html.escape(cert_status)}
  </div>

  <div class="grid-4">
    <div class="kpi">
      <div class="lbl">Risk Level & Score</div>
      <div class="val">{html.escape(sim.risk_level)} ({sim.risk_score:.2f})</div>
      <div class="sub">Confidence: {html.escape(unc.confidence_level)} ({unc.confidence_score * 100:.0f}%)</div>
    </div>
    <div class="kpi">
      <div class="lbl">Sustained Burn Prob</div>
      <div class="val">{sim.sustained_burn_probability * 100:.1f}% ± {unc.sustained_prob_std * 100:.1f}%</div>
      <div class="sub">80-Tree Physics-Informed RF</div>
    </div>
    <div class="kpi">
      <div class="lbl">Predicted Burn Rate</div>
      <div class="val">{sim.predicted_burning_rate_mms:.2f} mm/s</div>
      <div class="sub">90% CI: {unc.burning_rate_ci90_mms[0]:.2f}–{unc.burning_rate_ci90_mms[1]:.2f} mm/s</div>
    </div>
    <div class="kpi">
      <div class="lbl">Predicted Flame Temp</div>
      <div class="val">{sim.predicted_flame_temp_k:.0f} K</div>
      <div class="sub">90% CI: {unc.flame_temp_ci90_k[0]:.0f}–{unc.flame_temp_ci90_k[1]:.0f} K</div>
    </div>
  </div>

  <h2>1. Physics-Informed Diagnostics & 2D MOC Boundary Curve (0g vs. 1g NASA-STD-6001)</h2>
  <div style="display:grid; grid-template-columns: 1.1fr 1fr; gap: 14px; align-items:center;">
    <table>
      <tbody>
        <tr><th>O₂ Partial Pressure (P_O₂)</th><td><strong>{phys.oxygen_partial_pressure_kpa:.2f} kPa</strong> ({phys.normoxic_po2_ratio:.2f}× Sea-Level Normoxic)</td></tr>
        <tr><th>Inert Diluent Ratio (N₂/O₂)</th><td><strong>{phys.diluent_to_o2_ratio:.2f} : 1</strong> (Earth Air: 3.76 : 1)</td></tr>
        <tr><th>0g Microgravity MOC Limit</th><td><strong>{phys.moc_0g_limit_o2_pct:.1f}% O₂</strong> vs. 1g STD-6001: <strong>{phys.moc_1g_std6001_limit_o2_pct:.1f}% O₂</strong></td></tr>
        <tr><th>0g MOC Safety Margin</th><td><strong>{phys.moc_safety_margin_o2_pct:+.1f}% O₂</strong> ({html.escape(phys.transport_regime)})</td></tr>
      </tbody>
    </table>
    <svg viewBox="0 0 500 220" style="width:100%; border:1px solid #cbd5e1; border-radius:6px; background:#0f172a;">
      <rect x="50" y="30" width="420" height="160" fill="#1e293b" stroke="#475569" />
      <polyline fill="none" stroke="#4ade80" stroke-width="2.5" stroke-dasharray="5,4" points="{pts_1g}" />
      <polyline fill="none" stroke="#38bdf8" stroke-width="3" points="{pts_0g}" />
      <circle cx="{ux}" cy="{uy}" r="6" fill="#facc15" stroke="#000" stroke-width="1.5" />
      <text x="58" y="46" fill="#38bdf8" font-size="10" font-family="sans-serif">Solid Cyan: 0g Microgravity MOC Boundary</text>
      <text x="58" y="60" fill="#4ade80" font-size="10" font-family="sans-serif">Dashed Green: 1g NASA-STD-6001 MOC</text>
      <text x="150" y="210" fill="#cbd5e1" font-size="10" font-family="monospace">Cabin Pressure ({p_min:.0f}–{p_max:.0f} kPa) · Yellow Dot = Operating Point</text>
    </svg>
  </div>

  <h2>2. Fire Detection, Suppression & Post-Fire Cleanup Specification (SAME, DAFT, SLICE, SAFFIRE IV–VI)</h2>
  <table>
    <tbody>
      <tr><th>Optimal Smoke Detector (SAME/SAME-R)</th><td><strong>{html.escape(det.recommended_detector_modality)}</strong> — 0g Smoke CMD: <code>{det.smoke_cmd_0g_um:.2f} μm</code> (vs. <code>{det.smoke_cmd_1g_um:.2f} μm</code> in 1g) · Photoelectric: <code>{det.photoelectric_sensitivity * 100:.0f}%</code> vs. Ionization: <code>{det.ionization_sensitivity * 100:.0f}%</code></td></tr>
      <tr><th>Lunar Dust Discrimination (DAFT-2)</th><td>{html.escape(det.lunar_dust_discrimination_note)}</td></tr>
      <tr><th>Primary & Backup Suppressant (SLICE)</th><td>Primary: <strong>{html.escape(det.primary_extinguishant)}</strong> · Backup: <strong>{html.escape(det.secondary_extinguishant)}</strong></td></tr>
      <tr><th>Peak CO & Toxicity Status</th><td><strong>{det.estimated_peak_co_ppm:.1f} ppm CO</strong> ({html.escape(det.co_toxicity_level)}) vs. NASA 1-hr SMAC ({det.nasa_smac_1hr_co_ppm:.0f} ppm) / 24-hr SMAC ({det.nasa_smac_24hr_co_ppm:.0f} ppm)</td></tr>
    </tbody>
  </table>

  <table>
    <thead>
      <tr><th>Suppressant Modality</th><th>Suitability</th><th>Eff.</th><th>Mechanism & Tradeoff</th><th>Citations</th></tr>
    </thead>
    <tbody>{ext_html_rows}</tbody>
  </table>

  <h2>3. Five Closest Historical NASA/JAXA Experiments in Validated Snapshot</h2>
  <table>
    <thead>
      <tr><th>Experiment ID</th><th>Family</th><th>Material</th><th>O₂</th><th>Pressure</th><th>Airflow</th><th>Burn Rate</th><th>Outcome</th></tr>
    </thead>
    <tbody>{nearest_html_rows}</tbody>
  </table>
</body>
</html>"""

        return MissionSafetyDossierResponse(
            dossier_id=dossier_id,
            generated_at_utc=now_utc,
            dataset_sha256=sha_short,
            certification_status=cert_status,
            risk_level=sim.risk_level,
            risk_score=sim.risk_score,
            markdown_report=md_report,
            html_printable=html_doc,
        )
