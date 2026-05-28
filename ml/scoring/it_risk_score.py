# =============================================================================
# ml/scoring/it_risk_score.py
# Dashboard 360° Novec — IT Risk Score composite (Étape C)
# Formule CDC §11.6 : Score_Global = A×40% + K×35% + P×25%
# =============================================================================

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

try:
    from data_simulation.config import get_db_engine
except ImportError:
    get_db_engine = None

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTES
# =============================================================================

# Poids domaines [0, 1] — somme = 1.0
DOMAIN_WEIGHTS: dict[str, float] = {
    "Infrastructure": 0.30,
    "Cybersécurité":  0.25,
    "ITSM":           0.20,
    "Applications":   0.10,
    "ITAM":           0.10,
    "Gouvernance":    0.05,
}

# Domaines couverts par les tables anomalies / forecast
# Clé = valeur dans colonne "Domaine" de Gold
KNOWN_DOMAINS = set(DOMAIN_WEIGHTS.keys())

# Tables forecast Gold (Prophet + ARIMA)
FORECAST_TABLES: list[str] = [
    "Gold.forecast_infra",
    "Gold.forecast_itsm",
    "Gold.forecast_cybersec",
    "Gold.forecast_apps",
    "Gold.forecast_itam",
    "Gold.forecast_gouvernance",
    "Gold.forecast_maintenance",
    "Gold.forecast_parc_auto",
]

# Mapping table forecast → domaine Gold.it_risk_score
FORECAST_TABLE_TO_DOMAIN: dict[str, str] = {
    "Gold.forecast_infra":        "Infrastructure",
    "Gold.forecast_itsm":         "ITSM",
    "Gold.forecast_cybersec":     "Cybersécurité",
    "Gold.forecast_apps":         "Applications",
    "Gold.forecast_itam":         "ITAM",
    "Gold.forecast_gouvernance":  "Gouvernance",
    "Gold.forecast_maintenance":  "Gouvernance",   # rattaché Gouvernance (pas de poids dédié)
    "Gold.forecast_parc_auto":    "Infrastructure", # rattaché Infrastructure
}

# Seuils RAG globaux (sur Score_Global 0-100)
RAG_ROUGE_THRESHOLD = 70.0
RAG_AMBRE_THRESHOLD = 40.0

# Pondération des trois composantes
W_ANOMALIES   = 0.40   # A — Gold.anomalies_detected
W_KPI_ALERTS  = 0.35   # K — Gold.prophet_alerts
W_PREDICTIONS = 0.25   # P — Gold.forecast_* Is_Forecast=1, Statut_RAG != VERT

# Nombre de top contributeurs dans le JSON
TOP_N_CONTRIBUTORS = 3


# =============================================================================
# FONCTIONS DE LECTURE GOLD
# =============================================================================

def _read_table(engine: Engine, query: str, fallback: pd.DataFrame) -> pd.DataFrame:
    """Lit une requête SQL, retourne fallback si échec."""
    try:
        return pd.read_sql(query, engine)
    except Exception as exc:
        logger.warning("[RiskScore] Lecture SQL KO (%s) → fallback vide", exc)
        return fallback


# APRÈS — colonnes alignées sur la table réelle
def _load_anomalies(engine: Engine, date_key: date) -> pd.DataFrame:
    # 1. Essai sur la date du jour
    q = f"""
    SELECT Domaine, ServerName, Application_Name,
           Anomalie_IF, Score_IF, Score_Confiance, Features
    FROM Gold.anomalies_detected
    WHERE CAST(DateKey AS DATE) = '{date_key.isoformat()}'
      AND Anomalie_IF = 1
    """
    df = _read_table(engine, q, pd.DataFrame())

    # 2. Fallback : date la plus récente disponible
    if df.empty:
        logger.info("[RiskScore] Aucune anomalie aujourd'hui → dernière date disponible")
        q_latest = """
        SELECT TOP 1 CAST(DateKey AS DATE) as LatestDate
        FROM Gold.anomalies_detected
        WHERE Anomalie_IF = 1
        ORDER BY DateKey DESC
        """
        latest = _read_table(engine, q_latest, pd.DataFrame())
        if not latest.empty:
            latest_date = latest["LatestDate"].iloc[0]
            q = f"""
            SELECT Domaine, ServerName, Application_Name,
                   Anomalie_IF, Score_IF, Score_Confiance, Features
            FROM Gold.anomalies_detected
            WHERE CAST(DateKey AS DATE) = '{latest_date}'
              AND Anomalie_IF = 1
            """
            df = _read_table(engine, q, pd.DataFrame())
            logger.info("[RiskScore] %d anomalies chargées (date: %s)", len(df), latest_date)

    if df.empty:
        return df

    # Reconstruction des colonnes attendues par _score_anomalies()
    df["Statut_RAG"] = df["Score_Confiance"].apply(
        lambda s: "ROUGE" if pd.notna(s) and s >= 0.80 else "AMBRE"
    )
    df["Source_Detecteur"] = df["Score_IF"].apply(
        lambda s: "ZScore" if pd.isna(s) else "IsolationForest"
    )
    df["GroupKey"] = df.apply(
        lambda r: r["ServerName"] if pd.notna(r.get("ServerName"))
        else (r["Application_Name"] if pd.notna(r.get("Application_Name"))
              else r["Domaine"]),
        axis=1,
    )
    return df


def _load_prophet_alerts(engine: Engine) -> pd.DataFrame:
    """
    Charge Gold.prophet_alerts actives (Est_Active = 1 ou colonne rag_status).
    Gère les deux schémas possibles (prophet_alerts issu de build_alert_summary).
    """
    # Tentative avec Est_Active (schéma Gold complet)
    try:
        q = "SELECT * FROM Gold.prophet_alerts WHERE Est_Active = 1"
        df = pd.read_sql(q, engine)
        if not df.empty:
            return df
    except Exception:
        pass

    # Fallback : toutes les alertes sans filtre Est_Active
    try:
        q = "SELECT * FROM Gold.prophet_alerts"
        df = pd.read_sql(q, engine)
        # Filtrer manuellement sur rag_status si présent
        if "rag_status" in df.columns:
            df = df[df["rag_status"].isin(["AMBRE", "ROUGE"])]
        elif "Statut_RAG" in df.columns:
            df = df[df["Statut_RAG"].isin(["AMBRE", "ROUGE"])]
        return df
    except Exception as exc:
        logger.warning("[RiskScore] prophet_alerts inaccessible : %s", exc)
        return pd.DataFrame()


def _load_forecast_alerts(engine: Engine) -> list[dict]:
    """
    Lit toutes les tables forecast_*, filtre Is_Forecast=1 et Statut_RAG != VERT.
    Retourne une liste de dicts {domain, kpi, risk_score, statut_rag}.
    """
    rows = []
    for table in FORECAST_TABLES:
        try:
            q = f"""
            SELECT KPI, Statut_RAG, Risk_Score
            FROM {table}
            WHERE Is_Forecast = 1 AND Statut_RAG != 'VERT'
            """
            df = pd.read_sql(q, engine)
            domain = FORECAST_TABLE_TO_DOMAIN.get(table, "Gouvernance")
            for _, r in df.iterrows():
                rows.append({
                    "domain":     domain,
                    "kpi":        r["KPI"],
                    "risk_score": float(r.get("Risk_Score", 0.5)),
                    "statut_rag": r["Statut_RAG"],
                })
        except Exception as exc:
            logger.debug("[RiskScore] Forecast table %s inaccessible : %s", table, exc)

    return rows


# =============================================================================
# CALCUL DES SCORES COMPOSANTES
# =============================================================================

def _score_anomalies(anomalies_df: pd.DataFrame) -> tuple[dict[str, float], int, list[dict]]:
    """
    Composante A — score basé sur les anomalies détectées (IF + ZScore).

    Score par domaine [0-100] :
      - ROUGE × 100 + AMBRE × 50 — pondéré par nombre total d'observations
      - Normalisé par le poids du domaine

    Returns
    -------
    domain_scores : {domain: score 0-100}
    nb_anomalies  : nombre total d'anomalies
    contributions : liste [{domaine, source, contribution}]
    """
    domain_scores: dict[str, float] = {d: 0.0 for d in DOMAIN_WEIGHTS}
    contributions: list[dict] = []
    nb_anomalies = 0

    if anomalies_df.empty:
        return domain_scores, 0, contributions

    for domain, weight in DOMAIN_WEIGHTS.items():
        subset = anomalies_df[anomalies_df["Domaine"] == domain]
        if subset.empty:
            continue

        nb_rouge = (subset["Statut_RAG"] == "ROUGE").sum()
        nb_ambre = (subset["Statut_RAG"] == "AMBRE").sum()
        total_obs = max(len(subset), 1)

        raw_score = (nb_rouge * 100 + nb_ambre * 50) / total_obs
        domain_scores[domain] = min(raw_score * 100, 100.0)  # normaliser sur 100
        nb_anomalies += nb_rouge + nb_ambre

        if domain_scores[domain] > 0:
            contributions.append({
                "domaine":      domain,
                "source":       "anomalies",
                "nb_rouge":     int(nb_rouge),
                "nb_ambre":     int(nb_ambre),
                "contribution": round(domain_scores[domain] * weight, 2),
            })

    return domain_scores, int(nb_anomalies), contributions


def _score_kpi_alerts(alerts_df: pd.DataFrame) -> tuple[dict[str, float], int, list[dict]]:
    """
    Composante K — score basé sur les alertes Prophet actives.

    Score par domaine : moyenne des risk_score des alertes actives × 100.
    ROUGE compte double par rapport à AMBRE.
    """
    domain_scores: dict[str, float] = {d: 0.0 for d in DOMAIN_WEIGHTS}
    contributions: list[dict] = []
    nb_alertes_rouge = 0

    if alerts_df.empty:
        return domain_scores, 0, contributions

    # Normaliser les noms de colonnes (prophet_alerts peut avoir snake_case ou PascalCase)
    col_map = {}
    for col in alerts_df.columns:
        col_lower = col.lower()
        if col_lower in ("domain", "domaine"):
            col_map["domain"] = col
        elif col_lower == "rag_status" or col_lower == "statut_rag":
            col_map["rag"] = col
        elif col_lower == "risk_score":
            col_map["risk_score"] = col

    domain_col   = col_map.get("domain")
    rag_col      = col_map.get("rag")
    rscore_col   = col_map.get("risk_score")

    if not domain_col or not rag_col:
        logger.warning("[RiskScore] Colonnes prophet_alerts non reconnues : %s", alerts_df.columns.tolist())
        return domain_scores, 0, contributions

    for domain, weight in DOMAIN_WEIGHTS.items():
        subset = alerts_df[alerts_df[domain_col] == domain]
        if subset.empty:
            continue

        nb_rouge = (subset[rag_col] == "ROUGE").sum()
        nb_ambre = (subset[rag_col] == "AMBRE").sum()
        nb_alertes_rouge += nb_rouge

        if rscore_col and rscore_col in subset.columns:
            # Score = moyenne pondérée des risk_scores (ROUGE compte double)
            scores_rouge = subset[subset[rag_col] == "ROUGE"][rscore_col].fillna(0.8)
            scores_ambre = subset[subset[rag_col] == "AMBRE"][rscore_col].fillna(0.5)
            weighted_sum = scores_rouge.sum() * 2 + scores_ambre.sum()
            weighted_n   = nb_rouge * 2 + nb_ambre
            score = (weighted_sum / max(weighted_n, 1)) * 100
        else:
            score = min((nb_rouge * 100 + nb_ambre * 50) / max(nb_rouge + nb_ambre, 1), 100.0)

        domain_scores[domain] = min(float(score), 100.0)

        if domain_scores[domain] > 0:
            contributions.append({
                "domaine":      domain,
                "source":       "prophet_alerts",
                "nb_rouge":     int(nb_rouge),
                "nb_ambre":     int(nb_ambre),
                "contribution": round(domain_scores[domain] * weight, 2),
            })

    return domain_scores, int(nb_alertes_rouge), contributions


def _score_predictions(forecast_rows: list[dict]) -> tuple[dict[str, float], list[dict]]:
    """
    Composante P — score basé sur les prédictions futures non-VERT.

    Score par domaine : max(risk_score) parmi les prédictions ROUGE/AMBRE × 100.
    """
    domain_scores: dict[str, float] = {d: 0.0 for d in DOMAIN_WEIGHTS}
    contributions: list[dict] = []

    if not forecast_rows:
        return domain_scores, contributions

    # Regrouper par domaine
    from collections import defaultdict
    by_domain: dict[str, list] = defaultdict(list)
    for r in forecast_rows:
        d = r["domain"]
        if d in domain_scores:
            by_domain[d].append(r)

    for domain, rows in by_domain.items():
        if not rows:
            continue
        max_risk = max(r["risk_score"] for r in rows)
        domain_scores[domain] = min(max_risk * 100, 100.0)
        weight = DOMAIN_WEIGHTS[domain]

        contributions.append({
            "domaine":      domain,
            "source":       "forecast",
            "nb_kpis":      len(rows),
            "max_risk":     round(max_risk, 4),
            "contribution": round(domain_scores[domain] * weight, 2),
        })

    return domain_scores, contributions


# =============================================================================
# SCORE GLOBAL
# =============================================================================

def _compute_global_score(
    a_scores: dict[str, float],
    k_scores: dict[str, float],
    p_scores: dict[str, float],
) -> tuple[float, dict[str, float]]:
    """
    Calcule Score_Global et les scores par domaine.

    Formule : Score_Global = A×40% + K×35% + P×25%
    Puis pondéré par DOMAIN_WEIGHTS pour obtenir une contribution normalisée.

    Returns
    -------
    global_score      : float [0, 100]
    per_domain_scores : {domain: score 0-100}
    """
    per_domain: dict[str, float] = {}

    for domain, weight in DOMAIN_WEIGHTS.items():
        a = a_scores.get(domain, 0.0)
        k = k_scores.get(domain, 0.0)
        p = p_scores.get(domain, 0.0)
        domain_composite = a * W_ANOMALIES + k * W_KPI_ALERTS + p * W_PREDICTIONS
        per_domain[domain] = round(min(domain_composite, 100.0), 2)

    # Score global = somme(score_domaine × poids_domaine)
    global_score = sum(
        per_domain[d] * DOMAIN_WEIGHTS[d] for d in DOMAIN_WEIGHTS
    )
    return round(min(global_score, 100.0), 2), per_domain


def _rag_global(score: float) -> str:
    if score >= RAG_ROUGE_THRESHOLD:
        return "ROUGE"
    elif score >= RAG_AMBRE_THRESHOLD:
        return "AMBRE"
    return "VERT"


def _top_contributors(
    a_contribs: list[dict],
    k_contribs: list[dict],
    p_contribs: list[dict],
    n: int = TOP_N_CONTRIBUTORS,
) -> list[dict]:
    """
    Identifie les N domaines/KPIs ayant le plus contribué au score global.

    Format : [{"domaine": "Infrastructure", "source": "anomalies", "contribution": 18.5}]
    """
    all_contribs: list[dict] = a_contribs + k_contribs + p_contribs
    if not all_contribs:
        return []

    # Agrégation par (domaine, source)
    from collections import defaultdict
    agg: dict[tuple, float] = defaultdict(float)
    meta: dict[tuple, dict] = {}
    for c in all_contribs:
        key = (c["domaine"], c["source"])
        agg[key] += c.get("contribution", 0.0)
        meta[key] = {k: v for k, v in c.items() if k not in ("contribution",)}

    top = sorted(agg.items(), key=lambda x: x[1], reverse=True)[:n]
    result = []
    for (domaine, source), contrib in top:
        entry = {"domaine": domaine, "source": source, "contribution": round(contrib, 2)}
        result.append(entry)
    return result


# =============================================================================
# POINT D'ENTRÉE PRINCIPAL
# =============================================================================

def compute_it_risk_score(
    engine: Engine,
    date_key: Optional[date] = None,
    dry_run: bool = False,
) -> dict:
    """
    Calcule le IT Risk Score composite pour une date donnée et l'écrit
    dans Gold.it_risk_score.

    Parameters
    ----------
    engine   : SQLAlchemy engine SQL Server
    date_key : date à calculer (None → aujourd'hui)
    dry_run  : si True, calcule mais n'écrit pas en base

    Returns
    -------
    dict avec toutes les métriques calculées (conforme colonnes Gold.it_risk_score)
    """
    if date_key is None:
        date_key = date.today()

    logger.info("[RiskScore] === Calcul IT Risk Score pour %s ===", date_key)

    # ── 1. Chargement des données Gold ────────────────────────────────────────
    logger.info("[RiskScore] Chargement Gold.anomalies_detected...")
    anomalies_df = _load_anomalies(engine, date_key)
    logger.info("[RiskScore] %d lignes anomalies chargées", len(anomalies_df))

    logger.info("[RiskScore] Chargement Gold.prophet_alerts...")
    alerts_df = _load_prophet_alerts(engine)
    logger.info("[RiskScore] %d alertes Prophet actives", len(alerts_df))

    logger.info("[RiskScore] Chargement forecast tables (Is_Forecast=1)...")
    forecast_rows = _load_forecast_alerts(engine)
    logger.info("[RiskScore] %d prédictions non-VERT trouvées", len(forecast_rows))

    # ── 2. Calcul des trois composantes ───────────────────────────────────────
    a_scores, nb_anomalies, a_contribs = _score_anomalies(anomalies_df)
    k_scores, nb_alertes_rouge, k_contribs = _score_kpi_alerts(alerts_df)
    p_scores, p_contribs = _score_predictions(forecast_rows)

    nb_alertes_ambre = len(alerts_df) - nb_alertes_rouge if not alerts_df.empty else 0

    logger.info(
        "[RiskScore] Composantes → A: %s | K: %s | P: %s",
        {k: round(v, 1) for k, v in a_scores.items()},
        {k: round(v, 1) for k, v in k_scores.items()},
        {k: round(v, 1) for k, v in p_scores.items()},
    )

    # ── 3. Score global ───────────────────────────────────────────────────────
    global_score, per_domain = _compute_global_score(a_scores, k_scores, p_scores)
    statut_rag = _rag_global(global_score)
    top_contribs = _top_contributors(a_contribs, k_contribs, p_contribs)

    logger.info(
        "[RiskScore] Score_Global=%.1f | RAG=%s | Anomalies=%d | Alertes Rouge=%d",
        global_score, statut_rag, nb_anomalies, nb_alertes_rouge,
    )

    # ── 4. Construction de la ligne Gold ──────────────────────────────────────
    now = datetime.utcnow()
    row = {
        "DateKey":              date_key,
        "Score_Infrastructure": per_domain.get("Infrastructure", 0.0),
        "Score_ITSM":           per_domain.get("ITSM", 0.0),
        "Score_Cybersec":       per_domain.get("Cybersécurité", 0.0),
        "Score_Applications":   per_domain.get("Applications", 0.0),
        "Score_ITAM":           per_domain.get("ITAM", 0.0),
        "Score_Gouvernance":    per_domain.get("Gouvernance", 0.0),
        "Score_Global":         global_score,
        "Statut_RAG_Global":    statut_rag,
        "Top_Contributeurs":    json.dumps(top_contribs, ensure_ascii=False),
        "Nb_Anomalies_IF":      nb_anomalies,
        "Nb_Alertes_Rouge":     nb_alertes_rouge,
        "Nb_Alertes_Ambre":     max(nb_alertes_ambre, 0),
        "Source_Pipeline":      "pipeline.py",
        "Date_Calcul":          now,
    }

    if dry_run:
        logger.info("[RiskScore] --dry-run : aucune écriture en base.")
        _print_report(row)
        return row

    # ── 5. Sauvegarde (DELETE WHERE DateKey = today + INSERT) ─────────────────
    _save_risk_score(engine, row, date_key)
    return row


def _save_risk_score(engine: Engine, row: dict, date_key: date) -> None:
    """
    Idempotence : DELETE la ligne du jour puis INSERT.
    Pattern requis par la contrainte UNIQUE sur DateKey.
    """
    df = pd.DataFrame([row])

    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM Gold.it_risk_score WHERE DateKey = :dk"),
                {"dk": date_key.isoformat()},
            )
            logger.info("[RiskScore] DELETE Gold.it_risk_score WHERE DateKey = %s", date_key)

        df.to_sql(
            "it_risk_score",
            engine,
            schema="Gold",
            if_exists="append",
            index=False,
        )
        logger.info("[RiskScore] ✅ Score %s écrit dans Gold.it_risk_score", date_key)

    except Exception as exc:
        logger.error("[RiskScore] SQL KO : %s — fallback CSV", exc)
        from pathlib import Path
        out = Path("ml/outputs")
        out.mkdir(parents=True, exist_ok=True)
        df.to_csv(out / f"it_risk_score_{date_key}.csv", index=False)
        logger.info("[RiskScore] Fallback CSV écrit dans ml/outputs/")


def _print_report(row: dict) -> None:
    print()
    print("=" * 60)
    print("  IT RISK SCORE — Dashboard 360° Novec")
    print("=" * 60)
    rag_icon = {"ROUGE": "🔴", "AMBRE": "🟡", "VERT": "🟢"}.get(row["Statut_RAG_Global"], "⚪")
    print(f"  {rag_icon} Score Global   : {row['Score_Global']:.1f} / 100  [{row['Statut_RAG_Global']}]")
    print(f"  Date             : {row['DateKey']}")
    print()
    for domain_key, col in [
        ("Infrastructure", "Score_Infrastructure"),
        ("ITSM",           "Score_ITSM"),
        ("Cybersécurité",  "Score_Cybersec"),
        ("Applications",   "Score_Applications"),
        ("ITAM",           "Score_ITAM"),
        ("Gouvernance",    "Score_Gouvernance"),
    ]:
        score = row[col]
        icon = "🔴" if score >= 70 else ("🟡" if score >= 40 else "🟢")
        weight = DOMAIN_WEIGHTS.get(domain_key, 0)
        print(f"  {icon} {domain_key:20s} : {score:5.1f}  (poids {weight:.0%})")
    print()
    print(f"  Anomalies détectées  : {row['Nb_Anomalies_IF']}")
    print(f"  Alertes ROUGE        : {row['Nb_Alertes_Rouge']}")
    print(f"  Alertes AMBRE        : {row['Nb_Alertes_Ambre']}")
    print()
    top = json.loads(row["Top_Contributeurs"])
    if top:
        print("  Top contributeurs :")
        for t in top:
            print(f"    • {t['domaine']:20s} [{t['source']:15s}] → {t['contribution']:.1f} pts")
    print("=" * 60)


# =============================================================================
# POINT D'ENTRÉE CLI
# =============================================================================

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(description="Dashboard 360° — IT Risk Score")
    parser.add_argument("--dry-run", action="store_true", help="Calcule sans écrire en base")
    parser.add_argument("--date", default=None, help="Date cible YYYY-MM-DD (défaut : aujourd'hui)")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else date.today()

    engine = get_db_engine() if get_db_engine else None
    if engine is None:
        print("❌ SQL Server non disponible — it_risk_score requiert la base Gold.")
        sys.exit(1)

    result = compute_it_risk_score(engine, date_key=target_date, dry_run=args.dry_run)
    _print_report(result)