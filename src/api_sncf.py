from datetime import timezone, datetime

import pandas as pd
import requests
from google.transit import gtfs_realtime_pb2

URL_FLUX="https://proxy.transport.data.gouv.fr/resource/sncf-gtfs-rt-trip-updates"

def telecharger_flux():
    """Télécharge le flux et le décode. Le format est binaire (Protobuf), pas du JSON."""
    r = requests.get(URL_FLUX, timeout=30)
    r.raise_for_status()
    flux = gtfs_realtime_pb2.FeedMessage()
    flux.ParseFromString(r.content)
    return flux

def extraire_retards(flux):
    """Transforme le flux en tableau : une ligne par arrêt d'un train."""
    date_collecte = datetime.now(timezone.utc)
    lignes = []
    for entite in flux.entity:
        if not entite.HasField("trip_update"):
            continue
        tu = entite.trip_update
        for arret in tu.stop_time_update:
            # On prend l'arrivée si elle existe, sinon le départ
            evt = arret.arrival if arret.HasField("arrival") else arret.departure
            lignes.append({
                "trip_id": tu.trip.trip_id,           # identifiant de la circulation
                "date_service": tu.trip.start_date,   # AAAAMMJJ
                "stop_id": arret.stop_id,             # identifiant de la gare
                "retard_sec": evt.delay if evt.HasField("delay") else None,
                "heure_reelle": (
                    datetime.fromtimestamp(evt.time, timezone.utc) if evt.time else None
                ),
                "supprime": arret.schedule_relationship == arret.SKIPPED,
                "date_collecte": date_collecte,
            })
    return pd.DataFrame(lignes)


if __name__ == "__main__":
    flux = telecharger_flux()
    print(f"{len(flux.entity)} trains dans le flux")

    df = extraire_retards(flux)
    print(f"{len(df)} lignes (train x arrêt)\n")
    print(df.head(10).to_string())

    if df["retard_sec"].notna().any():
        print("\nRetard moyen (minutes) :", round(df["retard_sec"].mean() / 60, 1))