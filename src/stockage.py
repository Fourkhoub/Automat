"""
Étape 2 : enregistrer les retards dans une base DuckDB.

À placer dans : retards-sncf/src/stockage.py

Principe :
- une table `passages` : une ligne par train x arrêt x date de service
- à chaque collecte, une ligne déjà connue est mise à jour avec la valeur
  la plus récente (pas de doublon), une ligne nouvelle est ajoutée
- les retards de plus de 180 min sont marqués comme suspects, pas supprimés
"""

import duckdb
import pandas as pd

CHEMIN_BASE = "retards.duckdb"
SEUIL_SUSPECT_MIN = 180

SCHEMA = """
CREATE TABLE IF NOT EXISTS passages (
    trip_id        VARCHAR,
    date_service   VARCHAR,
    stop_id        VARCHAR,
    retard_sec     INTEGER,
    heure_reelle   TIMESTAMPTZ,
    supprime       BOOLEAN,
    suspect        BOOLEAN,
    premiere_vue   TIMESTAMPTZ,
    derniere_vue   TIMESTAMPTZ,
    PRIMARY KEY (trip_id, date_service, stop_id)
)
"""


def connecter(chemin=CHEMIN_BASE):
    con = duckdb.connect(chemin)
    con.execute(SCHEMA)
    return con


def enregistrer(con, df: pd.DataFrame):
    """Insère les nouvelles lignes et met à jour celles déjà connues."""
    if df.empty:
        return 0, 0

    df = df.copy()
    df["suspect"] = df["retard_sec"].fillna(0) > SEUIL_SUSPECT_MIN * 60
    # Un même arrêt peut apparaître deux fois dans un flux : on garde la dernière ligne
    df = df.drop_duplicates(subset=["trip_id", "date_service", "stop_id"], keep="last")

    avant = con.execute("SELECT COUNT(*) FROM passages").fetchall()[0][0]

    con.register("nouveaux", df)
    con.execute("""
        INSERT INTO passages
        SELECT trip_id, date_service, stop_id,
               CAST(retard_sec AS INTEGER), heure_reelle, supprime, suspect,
               date_collecte, date_collecte
        FROM nouveaux
        ON CONFLICT (trip_id, date_service, stop_id) DO UPDATE SET
            retard_sec   = EXCLUDED.retard_sec,
            heure_reelle = EXCLUDED.heure_reelle,
            supprime     = EXCLUDED.supprime,
            suspect      = EXCLUDED.suspect,
            derniere_vue = EXCLUDED.derniere_vue
    """)
    con.unregister("nouveaux")

    apres = con.execute("SELECT COUNT(*) FROM passages").fetchall()[0][0]
    ajoutees = apres - avant
    mises_a_jour = len(df) - ajoutees
    return ajoutees, mises_a_jour


def resume(con):
    """Quelques chiffres pour vérifier que la base se remplit bien."""
    return con.execute(f"""
        SELECT
            COUNT(*)                                        AS passages,
            COUNT(DISTINCT trip_id)                         AS trains,
            COUNT(DISTINCT date_service)                    AS jours,
            ROUND(AVG(retard_sec) FILTER (WHERE NOT suspect) / 60, 1) AS retard_moyen_min,
            SUM(CASE WHEN suspect THEN 1 ELSE 0 END)        AS lignes_suspectes
        FROM passages
    """).df()
