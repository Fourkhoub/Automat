"""
Envoie le bilan quotidien par email.

À placer à la racine : retards-sncf/rapport.py
Tester sans envoyer :  python rapport.py --test   (affiche l'email et crée apercu_email.html)
Envoyer pour de vrai : python rapport.py
"""

import sys

sys.path.append("src")

import duckdb

from envoi_email import calculer_bilan, construire_message, envoyer


def main():
    con = duckdb.connect("retards.duckdb")
    bilan = calculer_bilan(con)
    con.close()

    msg = construire_message(bilan)

    if "--test" in sys.argv:
        print("Sujet :", msg["Subject"], "\n")
        print(msg.get_body(preferencelist=("plain",)).get_content())
        html = msg.get_body(preferencelist=("html",)).get_content()
        with open("apercu_email.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Aperçu HTML enregistré dans apercu_email.html (ouvre-le dans ton navigateur)")
    else:
        envoyer(msg)
        print("Email envoyé :", msg["Subject"])


if __name__ == "__main__":
    main()