import re
import pandas as pd


def map_bez_to_type(bez: str) -> str | None:
    """Übersetzt die BKG-Spalte 'BEZ' in einen einheitlichen Gebietstyp."""
    if pd.isna(bez):
        return None
    b = str(bez).lower().strip()
    if b in {"kreisfreie stadt", "stadtkreis"}:
        return "stadtkreis"
    if b in {"landkreis", "kreis"}:
        return "landkreis"
    return None


def normalize_name(text: str) -> tuple[str, str | None]:
    """
    Bereinigt einen Orts-, Kreis- oder Landesnamen und extrahiert einen
    eventuellen Hinweis auf Stadtkreis vs. Landkreis.

    Rückgabe: (bereinigter_name, gebietstyp)
    Beispiel: "Lkr. Karlsruhe" -> ("karlsruhe", "landkreis")
    """
    if pd.isna(text):
        return "", None

    t = str(text).lower().strip()

    # 1. Hinweis auf Stadtkreis oder Landkreis erkennen, bevor Zusätze entfernt werden
    admin_type = None
    if re.search(r"\b(stadtkreis|kreisfreie stadt|krfr\.?\s*stadt|sk)\b", t):
        admin_type = "stadtkreis"
    elif re.search(r"\b(landkreis|lkr\.?|kreis)\b", t):
        admin_type = "landkreis"
    elif re.search(r"\bstadt\b", t):
        # Standalone "Stadt" (z. B. "Karlsruhe, Stadt"), trifft nicht auf "Darmstadt" o. Ä. zu
        admin_type = "stadtkreis"

    # 2. Typische geografische Abkürzungen ausschreiben
    abbreviations = [
        (r"\ba\.\s*d\.\b", "an der"),
        (r"\ba\.\s*m\.\b", "am"),
        (r"\bi\.\s*br\.\b", "im breisgau"),
        (r"\bi\.\s*d\.\s*opf\.\b", "in der oberpfalz"),
        (r"\bv\.\s*d\.\b", "vor der"),
        (r"\bb\.\b", "bei"),
    ]
    for pattern, replacement in abbreviations:
        t = re.sub(pattern, replacement, t)

    # 3. Behörden- und Titelzusätze entfernen
    noise_patterns = [
        r"\bkreisfreie stadt\b",
        r"\bkrfr\.?\s*stadt\b",
        r"\bstadtkreis\b",
        r"\blandkreis\b",
        r"\blkr\.?\b",
        r"\bkreis\b",
        r"\bstadt\b",
        r"\bgemeinde\b",
        r"\bhansestadt\b",
        r"\bwissenschaftsstadt\b",
        r"\buniversitaetsstadt\b",
        r"\buniversitätsstadt\b",
    ]
    for pattern in noise_patterns:
        t = re.sub(pattern, " ", t)

    # 4. Deutsche Umlaute und ß vereinheitlichen
    umlaut_map = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    for char, repl in umlaut_map.items():
        t = t.replace(char, repl)

    # 5. Sonderzeichen (Bindestriche, Kommas, Klammern) durch Leerzeichen ersetzen
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    clean_name = re.sub(r"\s+", " ", t).strip()

    return clean_name, admin_type