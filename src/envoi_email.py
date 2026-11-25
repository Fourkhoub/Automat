
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from analyse import FILTRE, preparer

load_dotenv()

PERIODE = "arrivee >= now() - INTERVAL 24 HOURS"


def calculer_bilan(con):
    """Renvoie les chiffres et les tableaux du bilan des dernières 24 h."""
    preparer(con)
    filtre = f"{FILTRE} AND {PERIODE}"

    chiffres = con.sql(f"""
        SELECT
            COUNT(*)                                                             AS trajets,
            ROUND(100.0 * AVG(CASE WHEN retard_min < seuil_min THEN 1 ELSE 0 END), 1) AS pct_a_l_heure,
            ROUND(AVG(retard_min), 1)                                            AS retard_moyen
        FROM trajets WHERE {filtre}
    """).fetchall()[0]

    supprimes = con.sql(f"""
        SELECT COUNT(*) FROM trajets WHERE termine AND terminus_supprime AND {PERIODE}
    """).fetchall()[0][0]

    par_type = con.sql(f"""
        SELECT type_train AS "Type", COUNT(*) AS "Trajets",
               ROUND(100.0 * AVG(CASE WHEN retard_min < seuil_min THEN 1 ELSE 0 END), 1) AS "% à l'heure"
        FROM trajets WHERE {filtre}
        GROUP BY type_train HAVING COUNT(*) >= 5
        ORDER BY "Trajets" DESC
    """).df()

    top = con.sql(f"""
        SELECT type_train AS "Type", origine AS "Origine", terminus AS "Terminus",
               strftime(arrivee AT TIME ZONE 'Europe/Paris', '%H:%M') AS "Arrivée",
               CAST(retard_min AS INTEGER) AS "Retard (min)"
        FROM trajets WHERE {filtre}
        ORDER BY retard_min DESC LIMIT 5
    """).df()

    return {
        "trajets": chiffres[0],
        "pct_a_l_heure": chiffres[1],
        "retard_moyen": chiffres[2],
        "supprimes": supprimes,
        "par_type": par_type,
        "top": top,
    }


def construire_message(bilan):
    """Fabrique l'email : une version texte (de secours) et une version HTML."""
    date_jour = datetime.now(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y")
    sujet = (f"Retards SNCF du {date_jour} : {bilan['pct_a_l_heure']} % à l'heure "
             f"sur {bilan['trajets']} trajets")

    texte = (
        f"Bilan des dernières 24 h ({date_jour})\n\n"
        f"Trajets analysés : {bilan['trajets']}\n"
        f"À l'heure : {bilan['pct_a_l_heure']} %\n"
        f"Retard moyen : {bilan['retard_moyen']} min\n"
        f"Trains supprimés au terminus : {bilan['supprimes']}\n\n"
        f"Plus gros retards :\n{bilan['top'].to_string(index=False)}\n"
    )

    html = f"""
    <h2>Retards SNCF : bilan des dernières 24 h</h2>
    <p><b>{bilan['trajets']}</b> trajets analysés,
       <b>{bilan['pct_a_l_heure']} %</b> à l'heure,
       retard moyen <b>{bilan['retard_moyen']} min</b>,
       <b>{bilan['supprimes']}</b> trains supprimés au terminus.</p>
    <h3>Par type de train (5 trajets minimum)</h3>
    {bilan['par_type'].to_html(index=False, border=0)}
    <h3>Les 5 plus gros retards</h3>
    {bilan['top'].to_html(index=False, border=0)}
    <p style="color:#777;font-size:12px">Source : flux GTFS-RT SNCF Voyageurs (transport.data.gouv.fr).
       Retards publiés par tranches de 5 min ; trajets suspects (+180 min) exclus.</p>
    """

    msg = EmailMessage()
    msg["Subject"] = sujet
    msg["From"] = os.getenv("EMAIL_EXPEDITEUR", "")
    msg["To"] = os.getenv("EMAIL_DESTINATAIRE", "")
    msg.set_content(texte)
    msg.add_alternative(html, subtype="html")
    return msg


def envoyer(msg):
    """Envoie l'email via le serveur de Gmail."""
    expediteur = os.getenv("EMAIL_EXPEDITEUR")
    mot_de_passe = os.getenv("EMAIL_MOT_DE_PASSE")
    if not expediteur or not mot_de_passe or not msg["To"]:
        raise RuntimeError("Identifiants manquants dans le fichier .env")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as serveur:
        serveur.login(expediteur, mot_de_passe)
        serveur.send_message(msg)