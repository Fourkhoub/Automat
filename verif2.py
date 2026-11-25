import duckdb
con = duckdb.connect("retards.duckdb")

# 1. Les stop_id dont le type n'a pas été reconnu
print(con.sql("""
    SELECT stop_id, COUNT(*) AS lignes
    FROM passages_detail
    WHERE type_train IS NULL OR type_train = ''
    GROUP BY stop_id ORDER BY lignes DESC LIMIT 10
"""))

# 2. Les retards sont-ils arrondis à 5 min ?
print(con.sql("""
    SELECT retard_sec % 300 = 0 AS multiple_de_5_min, COUNT(*) AS lignes
    FROM passages
    WHERE retard_sec IS NOT NULL
    GROUP BY 1
"""))