"""
Lance une collecte complète :
lecture du flux SNCF -> enregistrement dans DuckDB -> noms des gares (au premier lancement).

À placer à la racine : retards-sncf/main.py
Lancer :              python main.py
Recharger les gares : python main.py --gares   (à faire de temps en temps, ex. chaque semaine)
"""

import sys

sys.path.append("src")

from api_sncf import telecharger_flux, extraire_retards
from stockage import connecter, enregistrer, resume
from gares import telecharger_gares, charger_gares, gares_deja_chargees, creer_vue


def main():
    con = connecter()

    if "--gares" in sys.argv or not gares_deja_chargees(con):
        nb = charger_gares(con, telecharger_gares())
        print(f"Gares chargées : {nb}")
    creer_vue(con)
    flux = telecharger_flux()
    df = extraire_retards(flux)
    print(f"Flux lu : {len(flux.entity)} trains, {len(df)} lignes")

    ajoutees, mises_a_jour = enregistrer(con, df)
    print(f"Base : {ajoutees} lignes ajoutées, {mises_a_jour} mises à jour\n")
    print(resume(con).to_string(index=False))
    con.close()


if __name__ == "__main__":
    main()