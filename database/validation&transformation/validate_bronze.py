"""
validate_bronze.py — Validation de la couche Bronze
Dashboard 360 Novec | Phase 2

Valide les données Bronze AVANT la transformation Silver.
Lance une alerte si un domaine échoue aux règles critiques.

Usage : python database/validate_bronze.py
        python database/validate_bronze.py --verbose
"""
import sys
import argparse
import pandas as pd
import os

# Remonte 3 niveaux : validation&transformation → database → racine
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ajoute data_simulation au path
sys.path.insert(0, os.path.join(ROOT, "data_simulation"))
from config import get_db_engine


# ── Moteur de validation léger (inspiré Great Expectations) ──
class Validator:
    """
    Mini-validateur inspiré de Great Expectations.
    Chaque règle retourne (ok: bool, message: str).
    """
    def __init__(self, df, domain):
        self.df      = df
        self.domain  = domain
        self.results = []

    def _record(self, ok, msg):
        prefix = "✅" if ok else "❌"
        self.results.append((ok, f"  {prefix} [{self.domain}] {msg}"))
        return self

    def expect_no_nulls(self, col):
        n = self.df[col].isna().sum()
        return self._record(n == 0, f"{col} — nulls : {n}")

    def expect_between(self, col, min_val, max_val):
        out = ((self.df[col] < min_val) | (self.df[col] > max_val)).sum()
        return self._record(out == 0, f"{col} ∈ [{min_val}, {max_val}] — hors bornes : {out}")

    def expect_min_rows(self, n):
        return self._record(len(self.df) >= n, f"Lignes ≥ {n} — trouvé : {len(self.df)}")

    def expect_no_future_dates(self, col):
             now = pd.Timestamp.now()                     # ← heure exacte courante
             n = (pd.to_datetime(self.df[col]) > now).sum()
             return self._record(n == 0, f"{col} — dates futures : {n}")

    def expect_unique(self, cols):
        dupes = self.df.duplicated(subset=cols).sum()
        return self._record(dupes == 0, f"Unicité {cols} — doublons : {dupes}")

    def expect_positive(self, col):
        n = (self.df[col] < 0).sum()
        return self._record(n == 0, f"{col} ≥ 0 — négatifs : {n}")

    def expect_values_in(self, col, values):
        invalid = (~self.df[col].isin(values)).sum()
        return self._record(invalid == 0, f"{col} ∈ {values} — invalides : {invalid}")

    def summary(self):
        """Retourne uniquement les règles échouées."""
        return [r for r in self.results if not r[0]]

    def all_results(self):
        return self.results


# ── Règles par domaine ────────────────────────────────────────

def validate_infrastructure(engine):
    df = pd.read_sql("SELECT * FROM Bronze.staging_infrastructure", engine)
    v  = Validator(df, "Infrastructure")
    (v
     .expect_min_rows(8760)
     .expect_no_nulls('Timestamp')
     .expect_no_nulls('ServerName')
     .expect_no_future_dates('Timestamp')
     .expect_between('CPU_Usage_Pct',       0,   100)
     .expect_between('RAM_Usage_Pct',       0,   100)
     .expect_between('Disk_Usage_Pct',      0,   100)
     .expect_between('Network_Latency_ms',  0,  2000)
     .expect_between('Backup_Coverage_Pct', 0,   100)
     .expect_between('MTBF_Hours',          0, 10000)
     .expect_between('MTTR_Infra_Hours',    0,   100)
     .expect_values_in('Is_Anomaly',     [0, 1])
     .expect_values_in('Uptime_Status',  [0, 1])
     .expect_values_in('Backup_Success', [0, 1])
    )
    return v

def validate_itsm(engine):
    df = pd.read_sql("SELECT * FROM Bronze.staging_itsm_tickets", engine)
    v  = Validator(df, "ITSM")
    (v
     .expect_min_rows(300)
     .expect_no_nulls('Date')
     .expect_no_future_dates('Date')
     .expect_positive('Tickets_P1_Critique')
     .expect_positive('Tickets_P2_Majeur')
     .expect_positive('Tickets_P3_Mineur')
     .expect_positive('Volume_Total')
     .expect_positive('Backlog_Non_Resolus')
     .expect_between('SLA_Respect_Pct', 0,   100)
     .expect_between('FCR_Pct',         0,   100)
     .expect_between('MTTR_Hours',      0,   500)
     .expect_between('CSAT_Score',      1,     5)
    )
    return v

def validate_cybersecurity(engine):
    df = pd.read_sql("SELECT * FROM Bronze.staging_cybersecurity", engine)
    v  = Validator(df, "Cybersécurité")
    (v
     .expect_min_rows(300)
     .expect_no_nulls('Date')
     .expect_no_future_dates('Date')
     .expect_positive('Incidents_Critiques')
     .expect_positive('MTTD_Hours')
     .expect_positive('Vulnerabilites_Non_Patchees')
     .expect_between('Systemes_Patches_Pct',   0, 100)
     .expect_between('Taux_Adoption_MFA_Pct',  0, 100)
     .expect_between('Taux_Clic_Phishing_Pct', 0, 100)
     .expect_between('Conformite_RGPD_Pct',    0, 100)
    )
    return v

def validate_applications(engine):
    df = pd.read_sql("SELECT * FROM Bronze.staging_applications", engine)
    v  = Validator(df, "Applications")
    (v
     .expect_min_rows(900)
     .expect_no_nulls('Date')
     .expect_no_nulls('Application_Name')
     .expect_no_future_dates('Date')
     .expect_values_in('Application_Name',
         ['App_SIRH', 'App_Compta', 'App_Core_Metier'])
     .expect_positive('Temps_Reponse_Moyen_ms')
     .expect_between('Disponibilite_App_Pct',     80, 100)
     .expect_positive('Bugs_Critiques_Prod')
     .expect_between('Qualite_Donnees_Score_Pct',  0, 100)
     .expect_between('Adoption_PowerBI_Pct',       0, 100)
    )
    return v

def validate_itam(engine):
    df = pd.read_sql("SELECT * FROM Bronze.staging_itam", engine)
    v  = Validator(df, "ITAM")
    (v
     .expect_min_rows(12)
     .expect_no_nulls('Mois')
     .expect_positive('Total_Postes_Actifs')
     .expect_between('Vetuste_Plus_4ans_Pct',    0, 100)
     .expect_positive('TCO_Annuel_Par_Poste_MAD')
     .expect_between('Conformite_Licences_Pct',  0, 100)
     .expect_positive('Delai_Mise_Dispo_Jours')
     .expect_between('Taux_Inventaire_CMDB_Pct', 0, 100)
     .expect_positive('Licences_Inutilisees')
    )
    return v

def validate_parc_auto(engine):
    df = pd.read_sql("SELECT * FROM Bronze.staging_parc_auto", engine)
    v  = Validator(df, "Parc Auto")
    (v
     .expect_min_rows(300)
     .expect_no_nulls('Date')
     .expect_no_future_dates('Date')
     .expect_positive('Flotte_Totale')
     .expect_positive('Vehicules_Disponibles')
     .expect_between('Disponibilite_Vehicules_Pct', 0,  100)
     .expect_positive('Nbre_Sinistres_Jour')
     .expect_between('Taux_Sinistralite_Pct',       0,  100)
     .expect_positive('Consommation_Carburant_Total_L')
     .expect_between('Conso_L_100km',               0,   50)
     .expect_positive('TCO_Par_Vehicule_MAD')
    )
    return v

def validate_maintenance(engine):
    df = pd.read_sql("SELECT * FROM Bronze.staging_maintenance", engine)
    v  = Validator(df, "Maintenance")
    (v
     .expect_min_rows(12)
     .expect_no_nulls('Mois')
     .expect_positive('Total_Ordres_Travail')
     .expect_positive('Interventions_Preventives')
     .expect_positive('Interventions_Correctives')
     .expect_between('Ratio_Preventif_Pct',            0, 100)
     .expect_between('Taux_Realisation_Preventif_Pct', 0, 100)
     .expect_positive('Ruptures_Stock_Pieces')
    )
    return v

def validate_gouvernance(engine):
    df = pd.read_sql("SELECT * FROM Bronze.staging_gouvernance", engine)
    v  = Validator(df, "Gouvernance")
    (v
     .expect_min_rows(48)
     .expect_no_nulls('Mois')
     .expect_no_nulls('Departement')
     .expect_values_in('Departement',
         ['IT-Operations', 'Cybersecurité', 'Data', 'Projets'])
     .expect_positive('Budget_Alloue_MAD')
     .expect_positive('Budget_Consomme_MAD')
     .expect_between('ROI_Projets_Pct',           -50,  200)
     .expect_between('Projets_Livres_A_Temps_Pct',  0,  100)
     .expect_between('Taux_Adoption_Digital_Pct',   0,  100)
     .expect_between('Satisfaction_Globale_IT',      1,    5)
     .expect_positive('Cout_IT_Par_Employe_MAD')
    )
    return v


# ── MAIN ──────────────────────────────────────────────────────
def main(verbose: bool = False):
    print("=" * 60)
    print("  VALIDATION BRONZE — Dashboard 360 Novec")
    print("=" * 60)

    engine = get_db_engine()
    if engine is None:
        print("❌ Impossible de se connecter à SQL Server. Vérifiez le .env")
        sys.exit(2)

    validators = [
        ("Infrastructure",  validate_infrastructure),
        ("ITSM",            validate_itsm),
        ("Cybersécurité",   validate_cybersecurity),
        ("Applications",    validate_applications),
        ("ITAM",            validate_itam),
        ("Parc Auto",       validate_parc_auto),
        ("Maintenance",     validate_maintenance),
        ("Gouvernance",     validate_gouvernance),
    ]

    all_failures = []
    for name, fn in validators:
        print(f"\n── {name} ──")
        try:
            v = fn(engine)
            failures = v.summary()

            if verbose:
                # En mode verbose : afficher toutes les règles
                for _, msg in v.all_results():
                    print(msg)
            else:
                # Mode normal : afficher seulement les échecs
                if not failures:
                    print(f"  ✅ Toutes les règles OK")
                for _, msg in failures:
                    print(msg)

            all_failures.extend(failures)

        except Exception as e:
            msg = f"  ❌ ERREUR CRITIQUE : {e}"
            print(msg)
            all_failures.append((False, msg))

    print()
    print("=" * 60)
    if all_failures:
        print(f"⚠️  {len(all_failures)} règle(s) échouée(s) — corriger avant Silver.")
        sys.exit(1)
    else:
        print("✅ Toutes les règles passent — Bronze prêt pour Silver.")
        sys.exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Validation couche Bronze")
    parser.add_argument("--verbose", action="store_true",
                        help="Affiche toutes les règles (pas seulement les échecs)")
    args = parser.parse_args()
    main(verbose=args.verbose)