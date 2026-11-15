# AGS Schlüssel-Matching für GIS-Tabellen

Ein Python-CLI-Tool, um CSV-Tabellen mit deutschen Orts-, Kreis- oder Landesnamen um den offiziellen **Amtlichen Gemeindeschlüssel (AGS)** zu ergänzen. 

Das Programm löst das typische Problem beim Joinen externer Statistiktabellen in GIS-Systemen (QGIS, ArcGIS), bei denen Ortsbezeichnungen leicht voneinander abweichen (z. B. *„Halle an der Saale“* vs. *„Halle (Saale)“*, *„Lkr. Karlsruhe“* vs. *„Karlsruhe“* oder fehlende Bindestriche).

---

## Funktionen

- **Flexible Verwaltungsebenen:** Vergibt wahlweise 2-stellige (Bundesland), 5-stellige (Landkreis / Kreisfreie Stadt) oder 8-stellige AGS-Codes (Stadt / Gemeinde).
- **Automatisches CSV-Einlesen:** Erkennt Trennzeichen (`;` oder `,`) und Zeichenkodierung (`UTF-8`, `Windows-1252`, `Latin-1`) selbstständig.
- **Mehrstufiges Matching:**
  1. Bekannte Schreibweisen-Varianten aus `Schlüsseltabelle/aliases.json`
  2. Regelbasierte Text-Normalisierung (Umlaute, Präpositionen wie *a. d.* / *an der*, Unterscheidung zwischen *Stadtkreis* und *Landkreis*)
  3. Unscharfer Textvergleich über `RapidFuzz` bei Tippfehlern
- **Interaktive Konfliktlösung:** Mehrdeutige Ortsnamen (Homonyme wie *Hamm* oder *Münster*) und unsichere Treffer werden im Terminal abgefragt, bevor ein falscher Schlüssel vergeben wird.
- **Lernfähige Alias-Liste:** Aufgelöste Schreibweisen-Varianten lassen sich dauerhaft in `aliases.json` speichern (echte Homonyme bleiben bewusst ausgeschlossen).
- **GIS-sicherer Export:** Speichert das Ergebnis als `<dateiname>_ags.csv` und bewahrt führende Nullen (z. B. `08215`).

---

## Voraussetzungen & Installation

- **Python 3.10 oder neuer**
- **Externe Python-Pakete:** `pandas` und `rapidfuzz` 

```bash
# Repository klonen
git clone https://github.com/donar96/ags-matching.git
cd ags-matching

# Abhängigkeiten installieren
pip install pandas rapidfuzz
```


---

## Projektstruktur

```text
Schlüssel-Matching/
├── data/
│   └── vg25.utm32s.gpkg/          # BKG Verwaltungsgebiete 1:25.000 (DE_VG25.gpkg)
├── matcher/
│   ├── __init__.py
│   ├── normalizer.py              # Bereinigung von Ortsnamen & Erkennung Stadt-/Landkreis
│   └── engine.py                  # Mehrstufige Matching-Logik & Alias-Verwaltung
├── Schlüsseltabelle/
│   ├── ref_ags.csv                # Extrahierte BKG-Referenztabelle (AGS, Name, Typ, Ebene)
│   └── aliases.json               # Dauerhaft gespeicherte Schreibweisen-Zuordnungen
├── build_reference.py             # Hilfsskript zum Erzeugen der ref_ags.csv aus dem GPKG
├── main.py                        # Hauptprogramm (interaktive CLI)
└── README.md
```

---

## Verwendung

### 1. Referenztabelle aufbauen (einmalig)
Falls `Schlüsseltabelle/ref_ags.csv` noch nicht existiert oder auf einen neuen BKG-Gebietsstand aktualisiert werden soll:

```bash
python3 build_reference.py
```

### 2. CSV-Datei mit AGS anreichern
Starte `main.py` mit dem Pfad zu deiner CSV-Datei (oder ohne Argument, um den Pfad interaktiv einzugeben):

```bash
python3 main.py pfad/zu/deiner_datei.csv
```

Das Programm führt dich durch drei Schritte:
1. **Spalte wählen**, in der die Orts-, Kreis- oder Bundeslandnamen stehen.
2. **Verwaltungsebene wählen** (`1` = Bundesland, `2` = Landkreis/Kreisfreie Stadt, `3` = Stadt/Gemeinde).
3. **Offene Treffer prüfen:** Falls Orte mehrfach existieren (`AMBIGUOUS`) oder unsicher sind (`REVIEW` / `UNMATCHED`), kannst du im Terminal per Nummer auswählen, nach einem Namen suchen oder direkt einen AGS eintippen.

Die fertige Datei wird im selben Ordner unter `<dateiname>_ags.csv` gespeichert.

---

## Ausgabespalten & Statuswerte

| Spalte | Bedeutung |
| :--- | :--- |
| `AGS` | Zugeordneter Amtlicher Gemeindeschlüssel (2-, 5- oder 8-stellig) |
| `AGS_Name` | Offizieller Name laut BKG-Referenz |
| `AGS_Typ` | Verwaltungstyp (z. B. *Stadt*, *Gemeinde*, *Landkreis*, *Kreisfreie Stadt*) |
| `Match_Score` | Ähnlichkeitswert in Prozent (`0.0` bis `100.0`) |
| `Match_Status` | `EXACT`, `ALIAS`, `FUZZY_OK`, `REVIEW`, `MANUAL`, `AMBIGUOUS` oder `UNMATCHED` |

---

## Hinweise für den Import ins GIS (QGIS / ArcGIS)

- **Führende Nullen erhalten:** Beim Laden der `*_ags.csv` in QGIS (*Layer → Layer hinzufügen → Getrennte Textdatei hinzufügen*) sollte die Spalte `AGS` explizit als **Text (String)** interpretiert werden, damit Schlüssel in Schleswig-Holstein, Niedersachsen, NRW oder Baden-Württemberg (beginnend mit `01` bis `09`) nicht ihre führende `0` verlieren.
- **Datenquelle & Lizenz:** Die zugrundeliegenden Verwaltungsgebiete stammen vom Bundesamt für Kartographie und Geodäsie (`VG25`, Gebietsstand 31.12.2025, Lizenz `dl-de/by-2-0`). Bei Veröffentlichung von Karten oder Datensätzen den Quellenvermerk `© GeoBasis-DE / BKG (2026)` angeben.