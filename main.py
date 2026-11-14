import sys
import re
from pathlib import Path
import pandas as pd
from rapidfuzz import fuzz, process

from matcher.engine import AdminKeyMatcher
from matcher.normalizer import normalize_name


def read_csv_smart(file_path: Path) -> tuple[pd.DataFrame, str]:
    """Liest eine CSV-Datei robust ein und erkennt Trennzeichen (; oder ,) sowie Encoding."""
    encodings = ["utf-8-sig", "utf-8", "cp1252", "latin1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                first_line = f.readline()
            sep = ";" if first_line.count(";") >= first_line.count(",") else ","
            df = pd.read_csv(file_path, sep=sep, encoding=enc)
            return df, sep
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Konnte das Encoding von '{file_path}' nicht automatisch erkennen.")


def resolve_uncertain_matches(
    result_df: pd.DataFrame,
    matcher: AdminKeyMatcher,
    col_name: str,
    ebene: str,
) -> pd.DataFrame:
    """Klärt mehrdeutige oder unsichere Treffer im Terminal und speichert sie optional in aliases.json."""
    target_level = matcher._resolve_level(ebene)
    ref_sub = (
        matcher.ref_df[matcher.ref_df["ebene"] == target_level]
        .drop_duplicates(subset=["ags"])
        .reset_index(drop=True)
    )

    mask = result_df["Match_Status"].str.startswith(("AMBIGUOUS", "REVIEW", "UNMATCHED"), na=False)
    offene_werte = result_df.loc[mask, col_name].dropna().astype(str).unique().tolist()

    if not offene_werte:
        return result_df

    print(f"\nEs gibt {len(offene_werte)} eindeutige Einträge mit Klärungsbedarf.")
    antwort = input("Jetzt kurz im Terminal prüfen? [j/n]: ").strip().lower()
    if antwort not in {"j", "ja", "y", "yes", ""}:
        return result_df

    gelernte_aliase: dict[str, str] = {}

    for raw_val in offene_werte:
        norm_val, _ = normalize_name(raw_val)
        exact_hits = ref_sub[ref_sub["norm_name"] == norm_val]

        if not exact_hits.empty:
            kandidaten = exact_hits
        else:
            # Zuerst nach echten Worttreffern suchen (z. B. "Oldenburg" -> "Oldenburg (Oldb)")
            token_hits = ref_sub[
                ref_sub["norm_name"].str.contains(rf"\b{re.escape(norm_val)}\b", regex=True, na=False)
            ]
            if not token_hits.empty:
                kandidaten = token_hits.head(6)
            else:
                top_matches = process.extract(
                    norm_val,
                    ref_sub["norm_name"].tolist(),
                    scorer=fuzz.WRatio,
                    limit=5,
                )
                indizes = [m[2] for m in top_matches]
                kandidaten = ref_sub.iloc[indizes]

        while True:
            print(f"\nEingabe in CSV: '{raw_val}'")
            auswahl_liste = list(kandidaten.iterrows())
            for i, (_, row) in enumerate(auswahl_liste, start=1):
                print(f"  [{i}] {row['ags']} - {row['name']} ({row['bez']})")
            print("  [0] Überspringen (oder Suchbegriff / AGS eintippen)")

            wahl = input("Auswahl: ").strip()
            if wahl in {"0", ""}:
                break
            if wahl.isdigit() and 1 <= int(wahl) <= len(auswahl_liste):
                chosen = auswahl_liste[int(wahl) - 1][1]
                row_mask = result_df[col_name].astype(str) == raw_val

                # Prüfen, ob es ein echtes Homonym (AMBIGUOUS) war
                ist_homonym = (
                    result_df.loc[row_mask, "Match_Status"]
                    .str.startswith("AMBIGUOUS", na=False)
                    .any()
                )

                result_df.loc[row_mask, "AGS"] = chosen["ags"]
                result_df.loc[row_mask, "AGS_Name"] = chosen["name"]
                result_df.loc[row_mask, "AGS_Typ"] = chosen["bez"]
                result_df.loc[row_mask, "Match_Status"] = "MANUAL"

                # Nur eindeutige Schreibweisen-Varianten dauerhaft merken, keine Homonyme
                if not ist_homonym:
                    gelernte_aliase[raw_val.strip()] = str(chosen["ags"]).strip()
                break

            # Direkte AGS-Eingabe oder freie Suche in der Referenztabelle
            by_ags = ref_sub[ref_sub["ags"] == wahl]
            if not by_ags.empty:
                kandidaten = by_ags
            else:
                such_hits = ref_sub[
                    ref_sub["name"].str.contains(re.escape(wahl), case=False, na=False)
                ]
                if not such_hits.empty:
                    kandidaten = such_hits.head(8)
                else:
                    print(f"  -> Keine Treffer für '{wahl}'.")

    if gelernte_aliase:
        speichern = input(
            f"\nSollen diese {len(gelernte_aliase)} Zuordnungen dauerhaft in '{matcher.aliases_path}' gespeichert werden? [j/n]: "
        ).strip().lower()
        if speichern in {"j", "ja", "y", "yes", ""}:
            matcher.add_aliases(gelernte_aliase, ebene=ebene, persist=True)
            print(f"Gespeichert in {matcher.aliases_path}.")

    return result_df


def main():
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])
    else:
        pfad_input = input("Pfad zur CSV-Datei: ").strip().strip("'\"")
        csv_path = Path(pfad_input)

    if not csv_path.exists():
        print(f"Fehler: Datei '{csv_path}' wurde nicht gefunden.")
        sys.exit(1)

    df, sep = read_csv_smart(csv_path)
    print(f"\nDatei geladen: {csv_path.name} ({len(df)} Zeilen, Trennzeichen '{sep}')")

    print("\nVerfügbare Spalten:")
    for idx, col in enumerate(df.columns, start=1):
        beispiel = df[col].dropna().iloc[0] if not df[col].dropna().empty else "leer"
        print(f"  [{idx}] {col} (z. B. '{beispiel}')")

    spalten_wahl = input("\nWelche Spalte enthält die Orts-/Gebietsnamen? (Nummer oder Name): ").strip()
    if spalten_wahl.isdigit() and 1 <= int(spalten_wahl) <= len(df.columns):
        col_name = df.columns[int(spalten_wahl) - 1]
    elif spalten_wahl in df.columns:
        col_name = spalten_wahl
    else:
        print("Ungültige Spaltenauswahl.")
        sys.exit(1)

    print("\nAuf welcher Ebene sollen die AGS-Schlüssel vergeben werden?")
    print("  [1] Bundesland (2-stellig)")
    print("  [2] Landkreis / Kreisfreie Stadt (5-stellig)")
    print("  [3] Stadt / Gemeinde (8-stellig)")

    ebenen_map = {"1": "bundesland", "2": "kreis", "3": "gemeinde"}
    ebenen_wahl = input("Ebene wählen [1/2/3]: ").strip().lower()
    ebene = ebenen_map.get(ebenen_wahl, ebenen_wahl)

    print("\nLade Referenztabelle und starte Matching...")
    matcher = AdminKeyMatcher()
    result_df = matcher.match_dataframe(df, col_name=col_name, ebene=ebene)

    print("\n--- Ergebnis-Übersicht ---")
    print(result_df["Match_Status"].value_counts().to_string())

    result_df = resolve_uncertain_matches(result_df, matcher, col_name=col_name, ebene=ebene)

    out_path = csv_path.with_name(f"{csv_path.stem}_ags.csv")
    result_df.to_csv(out_path, sep=sep, index=False, encoding="utf-8-sig")
    print(f"\nFertig! Datei gespeichert unter: {out_path}")



if __name__ == "__main__":
    main()