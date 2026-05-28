"""
isolation_forest_detector.py — Détection d'anomalies multivariées
Dashboard 360 Novec | Phase 3 — ML

Domaines couverts :
  🔴 Priorité 1 : Infrastructure (CPU + RAM + Latence + Disk + Dispo)
  🔴 Priorité 1 : ITSM          (Volume + Backlog + MTTR + P1)
  🟡 Priorité 2 : Cybersécurité (Incidents + MTTD + Vulns)
  🟡 Priorité 2 : Applications  (Réponse + Bugs + Dispo)

Étapes clés :
  1. Chargement des données Silver depuis SQL Server
  2. Sélection des features multivariées par domaine
  3. Standardisation (StandardScaler) — obligatoire avant IF
  4. Entraînement Isolation Forest par serveur / par domaine
  5. Calcul du score de confiance normalisé [0,1]
  6. Sauvegarde des résultats dans Gold.anomalies_detected

Usage :
  python ml/anomaly_detection/isolation_forest_detector.py
  python ml/anomaly_detection/isolation_forest_detector.py --csv  # mode CSV sans SQL
"""
import os
import sys
import argparse
import warnings
from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ── Résolution des chemins ────────────────────────────────────
_HERE     = os.path.dirname(os.path.abspath(__file__))          # ml/anomaly_detection
_ROOT     = os.path.dirname(os.path.dirname(_HERE))             # dashboard360_novec
_DATA_SIM = os.path.join(_ROOT, "data_simulation")

for _p in [_DATA_SIM]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import get_db_engine

# ── Hyperparamètres globaux ───────────────────────────────────
# contamination : % estimé d'anomalies dans les données
# Calibré sur Taux_Anomalie_Pct observé (~4%) + marge
CONTAMINATION    = 0.05
RANDOM_STATE     = 42
N_ESTIMATORS     = 100   # nombre d'arbres — 100 est le standard
MAX_SAMPLES      = "auto"


# ════════════════════════════════════════════════════════════
# CHARGEMENT DES DONNÉES
# ════════════════════════════════════════════════════════════

def load_from_sql(engine):
    """Charge les 4 tables Silver depuis SQL Server."""
    print("  → Chargement depuis SQL Server...")
    return {
        "infra":  pd.read_sql("SELECT * FROM Silver.silver_infrastructure", engine),
        "itsm":   pd.read_sql("SELECT * FROM Silver.silver_itsm",           engine),
        "cyber":  pd.read_sql("SELECT * FROM Silver.silver_cybersecurity",  engine),
        "apps":   pd.read_sql("SELECT * FROM Silver.silver_applications",   engine),
    }

def load_from_csv():
    """Charge les données depuis les CSV Silver (mode sans SQL)."""
    print("  → Chargement depuis CSV...")
    base = os.path.join(_ROOT, "silver_dataset")
    return {
        "infra":  pd.read_csv(os.path.join(base, "silver_infra.csv")),
        "itsm":   pd.read_csv(os.path.join(base, "silver_itsm.csv")),
        "cyber":  pd.read_csv(os.path.join(base, "silver_cybersec.csv")),
        "apps":   pd.read_csv(os.path.join(base, "silver_apps.csv")),
    }


# ════════════════════════════════════════════════════════════
# MOTEUR DE DÉTECTION
# ════════════════════════════════════════════════════════════

class IsolationForestDetector:
    """
    Détecteur d'anomalies basé sur Isolation Forest.

    Principe : Isolation Forest isole les points aberrants en
    construisant des arbres de décision aléatoires. Un point
    est une anomalie s'il est isolé rapidement (chemin court
    dans l'arbre) car il est rare et différent des autres.

    Un modèle est entraîné PAR groupe (serveur, domaine) pour
    capturer le profil normal de chaque entité séparément.
    """

    def __init__(self, contamination=CONTAMINATION, random_state=RANDOM_STATE):
        self.contamination = contamination
        self.random_state  = random_state
        self.results       = []   # liste de DataFrames résultats

    def _run(self, df: pd.DataFrame, features: list,
             group_col: str = None, domain: str = "",
             date_col: str = "DateKey") -> pd.DataFrame:
        """
        Moteur générique d'Isolation Forest.

        Paramètres :
          df        : DataFrame Silver
          features  : colonnes utilisées comme features
          group_col : colonne de groupage (ex: "ServerName") — None = pas de groupage
          domain    : nom du domaine (pour les logs et le résultat)
          date_col  : colonne de date

        Retourne un DataFrame avec les colonnes :
          DateKey, group (si applicable), Anomalie_IF (0/1),
          Score_IF (score brut), Score_Confiance (0→1),
          Features_utilisees, Domaine
        """
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col])

        # Nettoyage : supprimer les lignes avec NaN sur les features
        df_clean = df.dropna(subset=features).copy()
        if len(df_clean) < 10:
            print(f"    ⚠️  [{domain}] Pas assez de données ({len(df_clean)} lignes) — ignoré")
            return pd.DataFrame()

        groups = [None] if group_col is None else df_clean[group_col].unique()
        all_results = []

        for group in groups:
            if group is None:
                subset = df_clean
                label  = domain
            else:
                subset = df_clean[df_clean[group_col] == group].copy()
                label  = f"{domain} / {group}"

            if len(subset) < 10:
                print(f"    ⚠️  [{label}] Groupe trop petit ({len(subset)} lignes) — ignoré")
                continue

            # ── Étape 3 : Standardisation ─────────────────────
            # Obligatoire : CPU (0-100%) et Latence (0-2000ms) ont
            # des échelles très différentes. Sans StandardScaler,
            # la latence dominerait le calcul de distance.
            X = subset[features].values
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # ── Étape 4 : Entraînement Isolation Forest ────────
            # contamination : proportion attendue d'anomalies
            # n_estimators  : 100 arbres = bon compromis vitesse/précision
            # random_state  : reproductibilité des résultats
            model = IsolationForest(
                contamination  = self.contamination,
                n_estimators   = N_ESTIMATORS,
                max_samples    = MAX_SAMPLES,
                random_state   = self.random_state,
            )
            model.fit(X_scaled)

            # ── Étape 5 : Prédiction et score de confiance ─────
            # predict()          : -1 = anomalie, 1 = normal
            # decision_function(): score de distance
            #   → très négatif = point très isolé = anomalie certaine
            #   → proche de 0  = point normal
            preds  = model.predict(X_scaled)          # -1 ou 1
            scores = model.decision_function(X_scaled) # scores bruts

            # Normalisation du score en [0,1]
            # Score_Confiance proche de 1 → très probablement une anomalie
            score_min, score_max = scores.min(), scores.max()
            if score_max > score_min:
                scores_norm = 1 - (scores - score_min) / (score_max - score_min)
            else:
                scores_norm = np.zeros(len(scores))

            result = subset[[date_col]].copy()
            if group_col:
                result[group_col] = group
            result["Anomalie_IF"]       = (preds == -1).astype(int)
            result["Score_IF"]          = scores.round(4)
            result["Score_Confiance"]   = scores_norm.round(4)
            result["Features"]          = ", ".join(features)
            result["Domaine"]           = domain

            nb_anomalies = result["Anomalie_IF"].sum()
            pct = nb_anomalies / len(result) * 100
            print(f"    [{label}] {nb_anomalies} anomalie(s) / {len(result)} lignes ({pct:.1f}%)")

            all_results.append(result)

        return pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()

    # ── Domaine 1 : Infrastructure (Priorité 🔴 1) ───────────
    def detect_infrastructure(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Features multivariées :
          - CPU_Moyen_Pct    : charge processeur moyenne
          - RAM_Moyen_Pct    : charge mémoire moyenne
          - Latence_Moyenne_ms : latence réseau
          - Disk_Moyen_Pct   : utilisation disque
          - Disponibilite_Pct : uptime du serveur

        Un modèle est entraîné PAR SERVEUR pour que chaque
        serveur ait son propre profil de normalité.
        Ex: SRV-ERP-01 a un CPU naturellement > SRV-WEB-PME.
        """
        print("  [Infra] Détection anomalies infrastructure...")
        features = [
            "CPU_Moyen_Pct", "RAM_Moyen_Pct",
            "Latence_Moyenne_ms", "Disk_Moyen_Pct",
            "Disponibilite_Pct",
        ]
        return self._run(df, features, group_col="ServerName", domain="Infrastructure")

    # ── Domaine 2 : ITSM (Priorité 🔴 1) ─────────────────────
    def detect_itsm(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Features : explosion de charge du Service Desk.
        Volume élevé + Backlog qui gonfle + MTTR long + % P1 élevé
        → signature d'une journée de crise ITSM.
        """
        print("  [ITSM] Détection anomalies service desk...")
        features = [
            "Volume_Total", "Backlog_Total",
            "MTTR_Moyen_Hours", "Pct_Tickets_P1",
        ]
        return self._run(df, features, group_col=None, domain="ITSM")

    # ── Domaine 3 : Cybersécurité (Priorité 🟡 2) ────────────
    def detect_cybersecurity(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Features : signature d'une brèche ou d'une dégradation
        de posture sécurité.
        Nb élevé d'incidents + MTTD long + vulnérabilités non patchées.
        """
        print("  [Cyber] Détection anomalies cybersécurité...")
        features = [
            "Nb_Incidents_Critiques", "MTTD_Moyen_Hours",
            "Total_Vuln_Non_Patchees",
        ]
        return self._run(df, features, group_col=None, domain="Cybersécurité")

    # ── Domaine 4 : Applications (Priorité 🟡 2) ─────────────
    def detect_applications(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Features : cascade infra → dégradation applicative.
        Temps de réponse élevé + bugs critiques + disponibilité basse.
        Un modèle PAR APPLICATION pour capturer les profils distincts.
        (App_SIRH vs App_Compta vs App_Core_Metier)
        """
        print("  [Apps] Détection anomalies applications...")
        features = [
            "Temps_Reponse_Moyen_ms", "Nb_Bugs_Critiques",
            "Disponibilite_Pct",
        ]
        return self._run(df, features, group_col="Application_Name", domain="Applications")

    def run_all(self, data: dict) -> pd.DataFrame:
        """Lance la détection sur tous les domaines et concatène les résultats."""
        results = []
        for name, fn, key in [
            ("Infrastructure", self.detect_infrastructure, "infra"),
            ("ITSM",           self.detect_itsm,           "itsm"),
            ("Cybersécurité",  self.detect_cybersecurity,  "cyber"),
            ("Applications",   self.detect_applications,   "apps"),
        ]:
            if key in data and not data[key].empty:
                r = fn(data[key])
                if not r.empty:
                    results.append(r)

        return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


# ════════════════════════════════════════════════════════════
# SAUVEGARDE DES RÉSULTATS
# ════════════════════════════════════════════════════════════

def save_results(df: pd.DataFrame, engine=None, output_dir: str = None):
    """
    Sauvegarde les anomalies détectées :
      - Dans Gold.anomalies_detected si SQL disponible
      - Sinon dans un CSV dans output_dir

    Stratégie cyclique : if_exists="append" pour conserver l'historique.
    Chaque run ajoute ses lignes avec Date_Calcul pour traçabilité.
    """
    if df.empty:
        print("  ⚠️  Aucun résultat à sauvegarder")
        return

    anomalies_only = df[df["Anomalie_IF"] == 1].copy()
    print(f"\n  📊 Résumé global : {len(anomalies_only)} anomalies / {len(df)} observations")

    # ── MODIFICATION : ajout Date_Calcul pour distinguer les runs ──
    now = datetime.utcnow()
    df = df.copy()
    df["Date_Calcul"] = now
    anomalies_only = anomalies_only.copy()
    anomalies_only["Date_Calcul"] = now

    if engine is not None:
        try:
            # ── MODIFICATION : replace → append (historique préservé) ──
            df.to_sql("anomalies_if_details",  con=engine, schema="Gold",
                      if_exists="append", index=False)
            anomalies_only.to_sql("anomalies_detected", con=engine, schema="Gold",
                                  if_exists="append", index=False)
            print("  ✅ Sauvegardé dans Gold.anomalies_if_details et Gold.anomalies_detected")
            return
        except Exception as e:
            print(f"  ⚠️  SQL échoué ({e}) — fallback CSV")

    # Fallback CSV
    out = output_dir or os.path.join(_ROOT, "ml", "outputs")
    os.makedirs(out, exist_ok=True)
    df.to_csv(os.path.join(out, "anomalies_if_details.csv"), index=False)
    anomalies_only.to_csv(os.path.join(out, "anomalies_detected.csv"), index=False)
    print(f"  ✅ CSV sauvegardés dans {out}/")


# ════════════════════════════════════════════════════════════
# RAPPORT SYNTHÉTIQUE
# ════════════════════════════════════════════════════════════

def print_report(df: pd.DataFrame):
    if df.empty:
        return
    print()
    print("=" * 60)
    print("  RAPPORT ANOMALIES — Isolation Forest")
    print("=" * 60)
    summary = (
        df.groupby("Domaine")
        .agg(
            Total_Observations = ("Anomalie_IF", "count"),
            Anomalies_Detectees= ("Anomalie_IF", "sum"),
            Score_Confiance_Max= ("Score_Confiance", "max"),
        )
        .assign(Taux_Pct=lambda x: (
            x["Anomalies_Detectees"] / x["Total_Observations"] * 100
        ).round(1))
    )
    for domaine, row in summary.iterrows():
        rag = "🔴" if row["Taux_Pct"] > 8 else ("🟡" if row["Taux_Pct"] > 4 else "🟢")
        print(f"  {rag} {domaine:20s} | {int(row['Anomalies_Detectees']):>3} anomalies"
              f" / {int(row['Total_Observations']):>4} obs"
              f" ({row['Taux_Pct']}%)"
              f" | confiance max : {row['Score_Confiance_Max']:.2f}")
    print("=" * 60)


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

def main(use_csv: bool = False):
    print("=" * 60)
    print("  ISOLATION FOREST — Dashboard 360 Novec")
    print("=" * 60)

    engine = None
    if not use_csv:
        engine = get_db_engine()
        if engine is None:
            print("  ⚠️  SQL Server non disponible — basculement sur CSV")
            use_csv = True

    data = load_from_csv() if use_csv else load_from_sql(engine)

    detector = IsolationForestDetector(contamination=CONTAMINATION)
    results  = detector.run_all(data)

    print_report(results)
    save_results(results, engine=engine if not use_csv else None)

    print()
    print("✅ Détection Isolation Forest terminée.")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", action="store_true",
                        help="Charger depuis CSV au lieu de SQL Server")
    args = parser.parse_args()
    main(use_csv=args.csv)