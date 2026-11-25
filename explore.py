import sys
sys.path.append("src")
from api_sncf import telecharger_flux, extraire_retards

df = extraire_retards(telecharger_flux())
minutes = df["retard_sec"] / 60

print("Lignes avec un retard connu :", minutes.notna().sum())
print("À l'heure (0 min)           :", (minutes == 0).sum())
print("Retard entre 1 et 60 min    :", minutes.between(1, 60).sum())
print("Retard > 60 min             :", (minutes > 60).sum())
print("Retard négatif (en avance)  :", (minutes < 0).sum())
print("\nStatistiques (minutes) :")
print(minutes.describe().round(1))
print("\nTrains concernés par un retard > 3 h :", df.loc[minutes > 180, "trip_id"].nunique())