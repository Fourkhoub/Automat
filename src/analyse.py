
import duckdb

CHEMIN_BASE = "retards.duckdb"

# Types de trains "grandes lignes" : seuil selon la durée du trajet.
# Les autres (TER, Transilien...) : seuil fixe de 5 min.
VUE_TRAJETS = """
CREATE OR REPLACE VIEW trajets AS
WITH par_train AS (
    -- arg_max(x, heure) = la valeur de x à l'heure la plus tardive, donc au terminus.
    -- On lit le terminus d'un seul bloc ({...} = une "structure") : sinon arg_max
    -- ignorerait un retard vide au terminus et prendrait celui d'un arrêt précédent.
    SELECT
        trip_id,
        date_service,
        any_value(type_train)                                   AS type_train,
        arg_min(coalesce(nom_gare, code_uic), heure_reelle)     AS origine,
        arg_max({'gare': coalesce(nom_gare, code_uic),
                 'retard': retard_sec,
                 'supprime': supprime}, heure_reelle)           AS fin,
        min(heure_reelle)                                       AS depart,
        max(heure_reelle)                                       AS arrivee,
        bool_or(suspect)                                        AS suspect,
        count(*)                                                AS nb_arrets
    FROM passages_detail
    WHERE heure_reelle IS NOT NULL
      AND type_train NOT ILIKE 'car%'          -- on écarte les autocars
    GROUP BY trip_id, date_service
),
avec_duree AS (
    SELECT
        * EXCLUDE (fin),
        fin.gare                                    AS terminus,
        fin.retard                                  AS retard_sec,
        coalesce(fin.supprime, false)               AS terminus_supprime,
        date_diff('minute', depart, arrivee)        AS duree_min
    FROM par_train
)
SELECT
    *,
    CASE
        WHEN regexp_matches(type_train, 'TGV|OUIGO|INTERCITES|LYRIA', 'i') THEN
            CASE WHEN duree_min < 90 THEN 5 WHEN duree_min <= 180 THEN 10 ELSE 15 END
        ELSE 5
    END                                                         AS seuil_min,
    ROUND(retard_sec / 60.0, 1)                                 AS retard_min,
    arrivee < now()                                             AS termine
FROM avec_duree
"""

# Filtre commun à toutes les analyses : trajets terminés, fiables, avec un retard connu
FILTRE = "termine AND NOT suspect AND NOT terminus_supprime AND retard_sec IS NOT NULL"


def preparer(con):
    con.execute(VUE_TRAJETS)


def synthese(con):
    return con.sql(f"""
        SELECT
            COUNT(*)                                                   AS trajets_termines,
            ROUND(100.0 * AVG(CASE WHEN retard_min < seuil_min THEN 1 ELSE 0 END), 1)
                                                                       AS pct_a_l_heure,
            ROUND(AVG(retard_min), 1)                                  AS retard_moyen_min,
            ROUND(AVG(retard_min) FILTER (WHERE retard_min >= seuil_min), 1)
                                                                       AS retard_moyen_si_en_retard
        FROM trajets
        WHERE {FILTRE}
    """).df()


def par_type(con):
    return con.sql(f"""
        SELECT
            type_train,
            COUNT(*)                                                   AS trajets,
            ROUND(100.0 * AVG(CASE WHEN retard_min < seuil_min THEN 1 ELSE 0 END), 1)
                                                                       AS pct_a_l_heure,
            ROUND(AVG(retard_min), 1)                                  AS retard_moyen_min
        FROM trajets
        WHERE {FILTRE}
        GROUP BY type_train
        ORDER BY trajets DESC
    """).df()


def par_terminus(con, minimum=3):
    return con.sql(f"""
        SELECT
            terminus,
            COUNT(*)                                                   AS trajets,
            ROUND(100.0 * AVG(CASE WHEN retard_min < seuil_min THEN 1 ELSE 0 END), 1)
                                                                       AS pct_a_l_heure,
            ROUND(AVG(retard_min), 1)                                  AS retard_moyen_min
        FROM trajets
        WHERE {FILTRE}
        GROUP BY terminus
        HAVING COUNT(*) >= {minimum}
        ORDER BY pct_a_l_heure ASC, trajets DESC
        LIMIT 10
    """).df()


def par_heure(con):
    return con.sql(f"""
        SELECT
            hour(arrivee AT TIME ZONE 'Europe/Paris')                  AS heure_arrivee,
            COUNT(*)                                                   AS trajets,
            ROUND(100.0 * AVG(CASE WHEN retard_min < seuil_min THEN 1 ELSE 0 END), 1)
                                                                       AS pct_a_l_heure,
            ROUND(AVG(retard_min), 1)                                  AS retard_moyen_min
        FROM trajets
        WHERE {FILTRE}
        GROUP BY heure_arrivee
        ORDER BY heure_arrivee
    """).df()


def top_retards(con, n=10):
    return con.sql(f"""
        SELECT
            type_train, origine, terminus,
            strftime(arrivee AT TIME ZONE 'Europe/Paris', '%H:%M')     AS arrivee_paris,
            retard_min
        FROM trajets
        WHERE {FILTRE}
        ORDER BY retard_min DESC
        LIMIT {n}
    """).df()


def suppressions(con):
    return con.sql("""
        SELECT type_train, COUNT(*) AS trajets_supprimes_au_terminus
        FROM trajets
        WHERE termine AND terminus_supprime
        GROUP BY type_train
        ORDER BY 2 DESC
    """).df()


if __name__ == "__main__":
    con = duckdb.connect(CHEMIN_BASE)
    preparer(con)
    for titre, fonction in [
        ("SYNTHÈSE", synthese),
        ("PAR TYPE DE TRAIN", par_type),
        ("TERMINUS LES MOINS PONCTUELS (3 trajets minimum)", par_terminus),
        ("PAR HEURE D'ARRIVÉE (heure de Paris)", par_heure),
        ("10 PLUS GROS RETARDS", top_retards),
        ("SUPPRESSIONS AU TERMINUS", suppressions),
    ]:
        print(f"\n=== {titre} ===")
        print(fonction(con).to_string(index=False))
    con.close()