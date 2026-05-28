# =============================================================================
# ml/anomaly_detection/zscore_detector.py
# Dashboard 360° Novec — Détection d'anomalies Z-Score (Étape A)
# Détection univariée KPI par KPI — complément à IsolationForestDetector
# =============================================================================

from __future__ import annotations

import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

# Config DB — pattern identique à isolation_forest_detector.py
try:
    from data_simulation.config import get_db_engine
except ImportError:
    get_db_engine = None  # fallback CSV uniquement en test unitaire

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTES
# =============================================================================

SILVER_TABLES: dict[str, str] = {
    "infra":        "Silver.silver_infrastructure",
    "itsm":         "Silver.silver_itsm",
    "cybersec":     "Silver.silver_cybersecurity",
    "apps":         "Silver.silver_applications",
    "itam":         "Silver.silver_itam",
    "parc_auto":    "Silver.silver_parc_auto",
    "maintenance":  "Silver.silver_maintenance",
    "gouvernance":  "Silver.silver_gouvernance",
}

# Colonnes de groupement par domaine (None = pas de groupement)
GROUP_KEYS: dict[str, Optional[str]] = {
    "infra":        "ServerName",
    "itsm":         None,
    "cybersec":     None,
    "apps":         "Application_Name",
    "itam":         None,
    "parc_auto":    None,
    "maintenance":  None,
    "gouvernance":  "Departement",
}

# Mapping domaine interne → label Gold.Domaine
DOMAIN_LABELS: dict[str, str] = {
    "infra":        "Infrastructure",
    "itsm":         "ITSM",
    "cybersec":     "Cybersécurité",
    "apps":         "Applications",
    "itam":         "ITAM",
    "parc_auto":    "Parc_Auto",
    "maintenance":  "Maintenance",
    "gouvernance":  "Gouvernance",
}

# =============================================================================
# MATRICE DES SEUILS — Section 11.3 CDC
# direction "above"  : alerte si valeur > seuil (ambre) ou > seuil (rouge)
# direction "below"  : alerte si valeur < seuil (ambre) ou < seuil (rouge)
# direction "zscore" : seuil statistique dynamique (|Z| > ambre → AMBRE, > rouge → ROUGE)
# =============================================================================

ZSCORE_THRESHOLDS: dict[str, dict[str, dict]] = {
    "Infrastructure": {
        "CPU_Moyen_Pct":      {"ambre": 80,   "rouge": 95,   "direction": "above"},
        "RAM_Moyen_Pct":      {"ambre": 80,   "rouge": 95,   "direction": "above"},
        "Latence_Moyenne_ms": {"ambre": 100,  "rouge": 200,  "direction": "above"},
        "Disk_Max_Pct":       {"ambre": 85,   "rouge": 95,   "direction": "above"},
        "Disponibilite_Pct":  {"ambre": 98,   "rouge": 95,   "direction": "below"},
    },
    "ITSM": {
        "Volume_Total":       {"ambre": 2.0,  "rouge": 3.0,  "direction": "zscore"},
        "MTTR_Moyen_Hours":   {"ambre": 12,   "rouge": 24,   "direction": "above"},
        "Backlog_Total":      {"ambre": 30,   "rouge": 50,   "direction": "above"},
        "SLA_Moyen_Pct":      {"ambre": 92,   "rouge": 85,   "direction": "below"},
        "CSAT_Moyen":         {"ambre": 3.5,  "rouge": 3.0,  "direction": "below"},
    },
    "Cybersécurité": {
        "Nb_Incidents_Critiques":   {"ambre": 1,   "rouge": 3,   "direction": "above"},
        "Total_Vuln_Non_Patchees":  {"ambre": 5,   "rouge": 15,  "direction": "above"},
        "MTTD_Moyen_Hours":         {"ambre": 1,   "rouge": 4,   "direction": "above"},
        "MFA_Adoption_Pct":         {"ambre": 88,  "rouge": 80,  "direction": "below"},
        "RGPD_Conformite_Pct":      {"ambre": 90,  "rouge": 80,  "direction": "below"},
    },
    "Applications": {
        "Temps_Reponse_Moyen_ms":   {"ambre": 200, "rouge": 300, "direction": "above"},
        "Nb_Bugs_Critiques":        {"ambre": 1,   "rouge": 3,   "direction": "above"},
        "Disponibilite_Pct":        {"ambre": 99.5,"rouge": 99,  "direction": "below"},
    },
    "ITAM": {
        "Vetuste_Moyen_Pct":        {"ambre": 30,  "rouge": 40,  "direction": "above"},
        "CMDB_Couverture_Pct":      {"ambre": 85,  "rouge": 75,  "direction": "below"},
    },
    "Parc_Auto": {
        "Disponibilite_Pct":        {"ambre": 93,  "rouge": 90,  "direction": "below"},
        "Nb_Sinistres":             {"ambre": 1,   "rouge": 3,   "direction": "above"},
    },
    "Maintenance": {
        "Ratio_Preventif_Pct":      {"ambre": 70,  "rouge": 60,  "direction": "below"},
        "Total_Ruptures_Stock":     {"ambre": 2,   "rouge": 4,   "direction": "above"},
    },
    "Gouvernance": {
        "Ecart_Budget_Moyen_Pct":   {"ambre": 10,  "rouge": 20,  "direction": "above"},
        "ROI_Moyen_Pct":            {"ambre": 5,   "rouge": 0,   "direction": "below"},
        "Projets_A_Temps_Pct":      {"ambre": 70,  "rouge": 55,  "direction": "below"},
    },
}

# Mapping clé interne → label Gold.Domaine pour les seuils
_DOMAIN_KEY_TO_THRESHOLD: dict[str, str] = {
    "infra":       "Infrastructure",
    "itsm":        "ITSM",
    "cybersec":    "Cybersécurité",
    "apps":        "Applications",
    "itam":        "ITAM",
    "parc_auto":   "Parc_Auto",
    "maintenance": "Maintenance",
    "gouvernance": "Gouvernance",
}

# Répertoire fallback CSV
CSV_FALLBACK_DIR = Path("silver_dataset")

# =============================================================================
# COLONNES RÉELLES DE Gold.anomalies_detected
# (alignées sur la structure existante créée par IsolationForestDetector)
# DateKey, ServerName, Anomalie_IF, Score_IF, Score_Confiance, Features,
# Domaine, Application_Name
# =============================================================================

GOLD_COLUMNS = [
    "DateKey",
    "Domaine",
    "ServerName",
    "Application_Name",
    "Anomalie_IF",
    "Score_IF",
    "Score_Confiance",
    "Features",
]


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def _compute_rag(value: float, threshold: dict) -> tuple[str, float]:
    """
    Retourne (Statut_RAG, Score_Confiance) pour une valeur donnée.

    Score_Confiance :
    - ROUGE → [0.80, 1.00] proportionnel à l'écart au seuil rouge
    - AMBRE → [0.60, 0.80[
    - VERT  → [0.00, 0.60[
    """
    direction = threshold["direction"]
    ambre_thr = threshold["ambre"]
    rouge_thr = threshold["rouge"]

    if direction == "above":
        if value >= rouge_thr:
            excess = min((value - rouge_thr) / max(rouge_thr * 0.1, 1), 1.0)
            score = 0.80 + excess * 0.20
            return "ROUGE", round(min(score, 1.0), 4)
        elif value >= ambre_thr:
            ratio = (value - ambre_thr) / max(rouge_thr - ambre_thr, 1e-9)
            score = 0.60 + ratio * 0.20
            return "AMBRE", round(min(score, 0.799), 4)
        else:
            ratio = value / max(ambre_thr, 1e-9)
            score = ratio * 0.60
            return "VERT", round(min(score, 0.599), 4)

    elif direction == "below":
        if value <= rouge_thr:
            excess = min((rouge_thr - value) / max(rouge_thr * 0.1, 1), 1.0)
            score = 0.80 + excess * 0.20
            return "ROUGE", round(min(score, 1.0), 4)
        elif value <= ambre_thr:
            ratio = (ambre_thr - value) / max(ambre_thr - rouge_thr, 1e-9)
            score = 0.60 + ratio * 0.20
            return "AMBRE", round(min(score, 0.799), 4)
        else:
            ratio = (ambre_thr - value) / max(ambre_thr, 1e-9)
            score = max(0, ratio) * 0.60
            return "VERT", round(max(score, 0.0), 4)

    else:  # direction == "zscore" — seuil dynamique statistique
        raise ValueError(
            "direction='zscore' nécessite _compute_rag_zscore() — "
            "ne pas appeler _compute_rag() directement."
        )


def _compute_rag_zscore(z: float, ambre_sigma: float, rouge_sigma: float) -> tuple[str, float]:
    """Z-Score dynamique : seuils exprimés en nombre de sigma."""
    abs_z = abs(z)
    if abs_z >= rouge_sigma:
        excess = min((abs_z - rouge_sigma) / max(rouge_sigma * 0.1, 0.1), 1.0)
        score = 0.80 + excess * 0.20
        return "ROUGE", round(min(score, 1.0), 4)
    elif abs_z >= ambre_sigma:
        ratio = (abs_z - ambre_sigma) / max(rouge_sigma - ambre_sigma, 1e-9)
        score = 0.60 + ratio * 0.20
        return "AMBRE", round(min(score, 0.799), 4)
    else:
        score = (abs_z / max(ambre_sigma, 1e-9)) * 0.60
        return "VERT", round(min(score, 0.599), 4)


# =============================================================================
# CLASSE PRINCIPALE
# =============================================================================

class ZScoreDetector:
    """
    Détection d'anomalies univariée par Z-Score pour le Dashboard 360° Novec.

    Détecte les dépassements de seuils absolus (above/below) et statistiques
    (zscore) sur l'ensemble des 8 domaines Silver. Complète IsolationForestDetector
    (multivarié) avec une détection par KPI, plus interprétable métier.

    Colonnes Gold.anomalies_detected utilisées :
        DateKey, Domaine, ServerName, Application_Name,
        Anomalie_IF, Score_IF, Score_Confiance, Features

    Usage :
        engine = get_db_engine()
        detector = ZScoreDetector(engine)
        results = detector.run_all()          # → dict[str, pd.DataFrame]
        detector.save_results(results)
    """

    def __init__(
        self,
        engine: Optional[Engine] = None,
        lookback_days: int = 90,
        min_points: int = 7,
    ):
        """
        Parameters
        ----------
        engine        : SQLAlchemy engine SQL Server (None → fallback CSV)
        lookback_days : fenêtre glissante pour le calcul mu/sigma Z-Score
        min_points    : nombre minimum de points pour calculer un Z-Score fiable
        """
        self.engine = engine
        self.lookback_days = lookback_days
        self.min_points = min_points
        self._results: dict[str, pd.DataFrame] = {}

    # ------------------------------------------------------------------
    # CHARGEMENT DONNÉES SILVER
    # ------------------------------------------------------------------

    def _load_silver(self, domain_key: str) -> pd.DataFrame:
        """Charge la table Silver (SQL Server ou CSV fallback)."""
        table = SILVER_TABLES[domain_key]

        if self.engine is not None:
            try:
                query = f"SELECT * FROM {table}"
                df = pd.read_sql(query, self.engine)
                logger.info("[ZScore] %s chargé depuis SQL Server (%d lignes)", table, len(df))
                return df
            except Exception as exc:
                logger.warning("[ZScore] SQL Server KO (%s) → fallback CSV : %s", table, exc)

        # Fallback CSV
        csv_path = CSV_FALLBACK_DIR / f"silver_{domain_key}.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path, parse_dates=["DateKey"])
            logger.info("[ZScore] %s chargé depuis CSV (%d lignes)", csv_path, len(df))
            return df

        logger.error("[ZScore] Aucune source disponible pour %s", domain_key)
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # DÉTECTION Z-SCORE SUR UN DOMAINE
    # ------------------------------------------------------------------

    def _detect_domain(self, domain_key: str) -> pd.DataFrame:
        """
        Applique la détection Z-Score sur tous les KPIs d'un domaine.

        Returns
        -------
        DataFrame aligné sur les colonnes réelles de Gold.anomalies_detected :
            DateKey, Domaine, ServerName, Application_Name,
            Anomalie_IF, Score_IF, Score_Confiance, Features
        """
        domain_label = _DOMAIN_KEY_TO_THRESHOLD[domain_key]
        thresholds = ZSCORE_THRESHOLDS.get(domain_label, {})
        group_col = GROUP_KEYS.get(domain_key)

        df = self._load_silver(domain_key)
        if df.empty or not thresholds:
            logger.warning("[ZScore] Domaine %s ignoré (données vides ou pas de seuils)", domain_key)
            return pd.DataFrame()

        # Normalise la colonne date
        date_col = "DateKey" if "DateKey" in df.columns else df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

        records = []

        # Groupes d'analyse : par ServerName / Application_Name / Departement si applicable
        if group_col and group_col in df.columns:
            groups = df.groupby(group_col)
        else:
            groups = [("_ALL_", df)]

        for group_value, gdf in groups:
            gdf = gdf.sort_values(date_col).copy()

            for kpi, thr in thresholds.items():
                if kpi not in gdf.columns:
                    logger.debug("[ZScore] KPI %s absent de %s — ignoré", kpi, domain_label)
                    continue

                series: pd.Series = gdf[kpi].dropna()
                if len(series) < self.min_points:
                    logger.debug(
                        "[ZScore] %s/%s : trop peu de points (%d < %d)",
                        domain_label, kpi, len(series), self.min_points,
                    )
                    continue

                # Calcul mu/sigma sur la fenêtre glissante (lookback)
                mu = series.mean()
                sigma = series.std(ddof=1) if len(series) > 1 else 0.0

                direction = thr["direction"]

                # Mapping des colonnes de groupement vers les colonnes Gold réelles
                # ServerName   → domaine infra uniquement
                # Application_Name → domaine apps uniquement
                server_name = (
                    str(group_value)
                    if domain_key == "infra" and group_value != "_ALL_"
                    else None
                )
                app_name = (
                    str(group_value)
                    if domain_key == "apps" and group_value != "_ALL_"
                    else None
                )

                # Itération sur chaque observation pour générer une ligne Gold
                for idx, row in gdf.iterrows():
                    raw_val = row.get(kpi)
                    if pd.isna(raw_val):
                        continue

                    date_key = row[date_col].date() if hasattr(row[date_col], "date") else row[date_col]

                    # --- Calcul RAG selon direction ---
                    if direction == "zscore":
                        z = (raw_val - mu) / max(sigma, 1e-9)
                        statut_rag, score_conf = _compute_rag_zscore(
                            z,
                            ambre_sigma=thr["ambre"],
                            rouge_sigma=thr["rouge"],
                        )
                    else:
                        statut_rag, score_conf = _compute_rag(raw_val, thr)

                    # Anomalie_IF : 1 si ROUGE ou AMBRE, 0 si VERT
                    # (réutilise la sémantique du flag IF pour la cohérence Gold)
                    anomalie_flag = 1 if statut_rag in ("ROUGE", "AMBRE") else 0

                    records.append({
                        "DateKey":          date_key,
                        "Domaine":          domain_label,
                        "ServerName":       server_name,
                        "Application_Name": app_name,
                        "Anomalie_IF":      anomalie_flag,
                        "Score_IF":         np.nan,   # réservé à IsolationForest
                        "Score_Confiance":  score_conf,
                        "Features":         kpi,
                        # Colonnes internes (non persistées en SQL, utiles pour summary())
                        "_Statut_RAG":      statut_rag,
                        "_Valeur_Observee": round(float(raw_val), 4),
                        "_Seuil_Ambre":     thr["ambre"],
                        "_Seuil_Rouge":     thr["rouge"],
                        "_Source":          "ZScore",
                    })

        if not records:
            return pd.DataFrame()

        result = pd.DataFrame(records)
        logger.info(
            "[ZScore] %s → %d observations (%d ROUGE, %d AMBRE, %d VERT)",
            domain_label,
            len(result),
            (result["_Statut_RAG"] == "ROUGE").sum(),
            (result["_Statut_RAG"] == "AMBRE").sum(),
            (result["_Statut_RAG"] == "VERT").sum(),
        )
        return result

    # ------------------------------------------------------------------
    # PIPELINE PRINCIPAL
    # ------------------------------------------------------------------

    def run_all(self) -> dict[str, pd.DataFrame]:
        """
        Lance la détection Z-Score sur tous les domaines.

        Returns
        -------
        dict[str, pd.DataFrame]
            Clés : "infra", "itsm", "cybersec", "apps", "itam",
                   "parc_auto", "maintenance", "gouvernance"
        """
        logger.info("[ZScore] === Démarrage détection tous domaines ===")
        results: dict[str, pd.DataFrame] = {}

        for domain_key in SILVER_TABLES:
            try:
                df = self._detect_domain(domain_key)
                results[domain_key] = df
                logger.info(
                    "[ZScore] ✓ %s : %d lignes générées",
                    domain_key, len(df)
                )
            except Exception as exc:
                logger.error("[ZScore] ✗ %s : erreur non fatale → %s", domain_key, exc, exc_info=True)
                results[domain_key] = pd.DataFrame()

        self._results = results
        logger.info("[ZScore] === Détection terminée ===")
        return results

    # ------------------------------------------------------------------
    # SAUVEGARDE
    # ------------------------------------------------------------------

    def save_results(
        self,
        results: Optional[dict[str, pd.DataFrame]] = None,
        dry_run: bool = False,
    ) -> int:
        """
        Sauvegarde les anomalies ZScore dans Gold.anomalies_detected.

        Colonnes persistées (alignées sur la table existante) :
            DateKey, Domaine, ServerName, Application_Name,
            Anomalie_IF, Score_IF, Score_Confiance, Features

        Seules les lignes ROUGE et AMBRE sont persistées.

        Returns
        -------
        int : nombre total de lignes écrites
        """
        if results is None:
            results = self._results

        # Consolidation tous domaines → une seule DataFrame
        frames = [df for df in results.values() if not df.empty]
        if not frames:
            logger.warning("[ZScore] Aucune donnée à sauvegarder.")
            return 0

        all_data = pd.concat(frames, ignore_index=True)

        # Filtrer : ne persister que les anomalies réelles (ROUGE + AMBRE)
        anomalies = all_data[all_data["_Statut_RAG"].isin(["ROUGE", "AMBRE"])].copy()

        # Sélectionner uniquement les colonnes Gold réelles (sans les colonnes internes _*)
        anomalies = anomalies[GOLD_COLUMNS].copy()

        nb_rows = len(anomalies)
        logger.info("[ZScore] Sauvegarde %d anomalies (ROUGE+AMBRE)", nb_rows)

        if dry_run:
            logger.info("[ZScore] --dry-run activé : aucune écriture SQL/CSV.")
            print(anomalies.head(10).to_string())
            return nb_rows

        # Tentative SQL Server
        if self.engine is not None:
            try:
                anomalies.to_sql(
                    "anomalies_detected",
                    self.engine,
                    schema="Gold",
                    if_exists="append",
                    index=False,
                )
                logger.info("[ZScore] ✅ %d lignes écrites → Gold.anomalies_detected", nb_rows)
                return nb_rows
            except Exception as exc:
                logger.warning("[ZScore] SQL Server KO → fallback CSV : %s", exc)

        # Fallback CSV (ne devrait plus être atteint avec le bon mapping)
        CSV_FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
        csv_path = CSV_FALLBACK_DIR / "zscore_anomalies_detected.csv"
        anomalies.to_csv(csv_path, index=False)
        logger.info("[ZScore] ✅ %d lignes sauvegardées → %s", nb_rows, csv_path)
        return nb_rows

    # ------------------------------------------------------------------
    # RAPPORT SYNTHÈSE
    # ------------------------------------------------------------------

    def summary(self, results: Optional[dict[str, pd.DataFrame]] = None) -> pd.DataFrame:
        """Retourne un tableau récapitulatif par domaine × RAG."""
        if results is None:
            results = self._results

        rows = []
        for key, df in results.items():
            if df.empty:
                continue
            # _Statut_RAG est présent dans les résultats internes (avant filtre Gold)
            rag_col = "_Statut_RAG" if "_Statut_RAG" in df.columns else "Anomalie_IF"
            if rag_col == "_Statut_RAG":
                anom = df[df["_Statut_RAG"].isin(["ROUGE", "AMBRE"])]
                rows.append({
                    "Domaine":       _DOMAIN_KEY_TO_THRESHOLD[key],
                    "Total_Obs":     len(df),
                    "Nb_ROUGE":      (df["_Statut_RAG"] == "ROUGE").sum(),
                    "Nb_AMBRE":      (df["_Statut_RAG"] == "AMBRE").sum(),
                    "Nb_VERT":       (df["_Statut_RAG"] == "VERT").sum(),
                    "Pct_Anomalies": round(len(anom) / max(len(df), 1) * 100, 1),
                })
            else:
                anom = df[df["Anomalie_IF"] == 1]
                rows.append({
                    "Domaine":       _DOMAIN_KEY_TO_THRESHOLD[key],
                    "Total_Obs":     len(df),
                    "Nb_ROUGE":      0,
                    "Nb_AMBRE":      len(anom),
                    "Nb_VERT":       len(df) - len(anom),
                    "Pct_Anomalies": round(len(anom) / max(len(df), 1) * 100, 1),
                })
        return pd.DataFrame(rows)


# =============================================================================
# POINT D'ENTRÉE CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(description="Dashboard 360° — ZScore Detector")
    parser.add_argument("--dry-run", action="store_true", help="Exécute sans écrire en base")
    parser.add_argument("--domain", default=None, help="Domaine unique à analyser (ex: infra)")
    args = parser.parse_args()

    engine = get_db_engine() if get_db_engine else None
    detector = ZScoreDetector(engine=engine)

    if args.domain:
        results = {args.domain: detector._detect_domain(args.domain)}
    else:
        results = detector.run_all()

    print("\n=== RÉSUMÉ ZSCORE ===")
    print(detector.summary(results).to_string(index=False))

    nb = detector.save_results(results, dry_run=args.dry_run)
    print(f"\n✅ Total anomalies (ROUGE+AMBRE) sauvegardées : {nb}")