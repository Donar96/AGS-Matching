######
# Hier werden aus der .gpkg eine CSV mit den Tabellen von den verschiedenen Layern.
#####

import sqlite3
from pathlib import Path
import pandas as pd

gpkg_path = Path("data/vg25.utm32s.gpkg/vg25_ebenen/DE_VG25.gpkg")
out_csv = Path("Schlüsseltabelle/ref_ags.csv")

layer_map = {
    "vg25_lan": "bundesland",
    "vg25_krs": "kreis",
    "vg25_gem": "gemeinde",
}

with sqlite3.connect(gpkg_path) as conn:
    tables = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table';", conn
    )["name"].tolist()
    table_lookup = {t.lower(): t for t in tables}

    dfs = []
    for layer_key, ebene in layer_map.items():
        actual_table = table_lookup.get(layer_key)
        if not actual_table:
            print(f"Warnung: Tabelle '{layer_key}' nicht gefunden.")
            continue

        # GF = 9 filtert auf reguläre Gebiete, AGS NOT LIKE '00%' schließt Kondominien aus
        query = f"""
            SELECT AGS AS ags, GEN AS name, BEZ AS bez
            FROM "{actual_table}"
            WHERE CAST(GF AS INTEGER) = 9
              AND AGS NOT LIKE '00%'
        """
        df = pd.read_sql(query, conn)
        df["ags"] = df["ags"].astype(str).str.strip()
        df["ebene"] = ebene
        dfs.append(df)

        query = f"""
            SELECT AGS AS ags, GEN AS name, BEZ AS bez
            FROM "{actual_table}"
            WHERE CAST(GF AS INTEGER) = 9
              AND AGS NOT LIKE '00%'
              AND (BEZ IS NULL OR BEZ != 'Küstenmeer')
        """
        df = pd.read_sql(query, conn)
        df["ags"] = df["ags"].astype(str).str.strip()
        df["ebene"] = ebene
        dfs.append(df)

ref_df = pd.concat(dfs, ignore_index=True).drop_duplicates(subset=["ags", "ebene"])

ref_df = pd.concat(dfs, ignore_index=True).drop_duplicates()
ref_df.to_csv(out_csv, index=False, encoding="utf-8")

print(f"Erfolgreich gespeichert: {out_csv} ({len(ref_df)} Einträge)\n")
print(ref_df["ebene"].value_counts())
print("\nVorschau:")
print(ref_df.head(5))