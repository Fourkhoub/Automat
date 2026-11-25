import duckdb
con = duckdb.connect("retards.duckdb")
print(con.sql("""
    SELECT type_train, nom_gare, retard_min
    FROM passages_detail
    WHERE retard_min > 5 AND NOT suspect
    ORDER BY retard_min DESC
    LIMIT 15
"""))
print(con.sql("SELECT COUNT(*) AS sans_nom FROM passages_detail WHERE nom_gare IS NULL"))