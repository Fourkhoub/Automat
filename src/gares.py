"""
Étape 3 : traduire les codes de gare en noms lisibles.

À placer dans : retards-sncf/src/gares.py

Source : GTFS "théorique" de SNCF Voyageurs (fichier zip, environ 5 Mo),
publié sur transport.data.gouv.fr (jeu de données "Horaires SNCF").
Le fichier stops.txt qu'il contient donne le nom et la position de chaque gare.

Astuce : un stop_id ressemble à "StopPoint:OCETrain TER-87763003"
  - ce qui suit "OCE" et précède le tiret = le type de train ("Train TER", "TGV INOUI"...)
  - les 8 derniers chiffres = le code UIC de la gare, identique pour tous les types de train
On fait donc la jointure sur le code UIC.
"""

import io
import zipfile

import pandas as pd
import requests

URL_GTFS = "https://eu.ftp.opendatasoft.com/sncf/plandata/export-opendata-sncf-gtfs.zip"


def telecharger_gares():
    """Télécharge le GTFS et renvoie un tableau : code_uic, nom_gare, latitude, longitude."""
    r = requests.get(URL_GTFS, timeout=120)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        with z.open("stops.txt") as f:
            stops = pd.read_csv(f, dtype=str)

    stops["code_uic"] = stops["stop_id"].str.extract(r"(\d{8})$", expand=False)
    gares = (
        stops.dropna(subset=["code_uic"])
        .drop_duplicates(subset="code_uic")
        .rename(columns={"stop_name": "nom_gare", "stop_lat": "latitude", "stop_lon": "longitude"})
        [["code_uic", "nom_gare", "latitude", "longitude"]]
    )
    gares["latitude"] = gares["latitude"].astype(float)
    gares["longitude"] = gares["longitude"].astype(float)
    return gares


def charger_gares(con, gares: pd.DataFrame):
    """Remplace la table `gares` et crée la vue `passages_detail`."""
    con.register("gares_df", gares)
    con.execute("CREATE OR REPLACE TABLE gares AS SELECT * FROM gares_df")
    con.unregister("gares_df")
    creer_vue(con)
    return len(gares)


def creer_vue(con):
    """Vue = requête enregistrée. passages_detail = passages + type de train + nom de gare."""
    con.execute("""
        CREATE OR REPLACE VIEW passages_detail AS
        SELECT
            p.*,
            -- Les stop_id "StopArea:OCE87393009" ne contiennent pas le type de train :
            -- on les range dans "Non précisé" au lieu d'une case vide.
            coalesce(nullif(regexp_extract(p.stop_id, 'OCE(.*)-\\d{8}$', 1), ''),
                     'Non précisé')                    AS type_train,
            regexp_extract(p.stop_id, '(\\d{8})$', 1)       AS code_uic,
            g.nom_gare,
            g.latitude,
            g.longitude,
            ROUND(p.retard_sec / 60.0, 1)                     AS retard_min
        FROM passages p
        LEFT JOIN gares g
          ON g.code_uic = regexp_extract(p.stop_id, '(\\d{8})$', 1)
    """)


def gares_deja_chargees(con):
    existe = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'gares'"
    ).fetchall()[0][0]
    return existe > 0


if __name__ == "__main__":
    # Test : python src/gares.py
    g = telecharger_gares()
    print(f"{len(g)} gares")
    print(g.head(10).to_string(index=False))