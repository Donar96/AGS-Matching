import json
from pathlib import Path
import pandas as pd
from rapidfuzz import fuzz, process

from matcher.normalizer import map_bez_to_type, normalize_name


class AdminKeyMatcher:
    LEVEL_ALIASES = {
        "bundesland": "bundesland",
        "land": "bundesland",
        "kreis": "kreis",
        "landkreis": "kreis",
        "stadtkreis": "kreis",
        "gemeinde": "gemeinde",
        "stadt": "gemeinde",
        "stadt/gemeinde": "gemeinde",
    }

    def __init__(
        self,
        ref_csv_path: str | Path = "Schlüsseltabelle/ref_ags.csv",
        aliases_path: str | Path = "Schlüsseltabelle/aliases.json",
    ):
        self.ref_df = pd.read_csv(ref_csv_path, dtype={"ags": str})
        self.ref_df["norm_name"] = self.ref_df["name"].apply(
            lambda x: normalize_name(x)[0]
        )
        self.ref_df["ref_type"] = self.ref_df["bez"].apply(map_bez_to_type)

        self.aliases_path = Path(aliases_path)
        self.aliases = self._load_aliases(self.aliases_path)

    @staticmethod
    def _load_aliases(path: Path) -> dict[str, dict[str, str]]:
        default_data: dict[str, dict[str, str]] = {
            "bundesland": {},
            "kreis": {},
            "gemeinde": {},
        }
        if not path.exists():
            return default_data

        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return default_data

        loaded = json.loads(content)
        for level in default_data:
            if isinstance(loaded.get(level), dict):
                default_data[level] = {
                    str(k): str(v) for k, v in loaded[level].items()
                }
        return default_data

    def _resolve_level(self, ebene: str) -> str:
        key = ebene.lower().strip()
        if key not in self.LEVEL_ALIASES:
            erlaubt = ", ".join(sorted(set(self.LEVEL_ALIASES.keys())))
            raise ValueError(f"Unbekannte Ebene '{ebene}'. Erlaubt sind: {erlaubt}")
        return self.LEVEL_ALIASES[key]

    def add_aliases(
        self, new_entries: dict[str, str], ebene: str, persist: bool = True
    ) -> None:
        """Speichert neue Name->AGS-Zuordnungen für die gewählte Ebene in aliases.json."""
        target_level = self._resolve_level(ebene)
        for raw_name, ags in new_entries.items():
            self.aliases[target_level][str(raw_name).strip()] = str(ags).strip()

        if persist:
            self.aliases_path.parent.mkdir(parents=True, exist_ok=True)
            self.aliases_path.write_text(
                json.dumps(self.aliases, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    def match_dataframe(
        self,
        df: pd.DataFrame,
        col_name: str,
        ebene: str,
        threshold: float = 85.0,
    ) -> pd.DataFrame:
        target_level = self._resolve_level(ebene)
        out_df = df.copy()

        ref_sub = (
            self.ref_df[self.ref_df["ebene"] == target_level]
            .drop_duplicates(subset=["ags"])
            .reset_index(drop=True)
        )
        ags_to_row = ref_sub.set_index("ags").to_dict(orient="index")
        level_aliases = self.aliases.get(target_level, {})

        results = []
        for raw_val in out_df[col_name]:
            raw_str = "" if pd.isna(raw_val) else str(raw_val).strip()

            if not raw_str:
                results.append((None, None, None, 0.0, "EMPTY"))
                continue

            # 1. Direkter Alias-Treffer aus aliases.json für diese Ebene
            if raw_str in level_aliases:
                ags = level_aliases[raw_str]
                info = ags_to_row.get(ags)
                if info:
                    results.append((ags, info["name"], info["bez"], 100.0, "ALIAS"))
                    continue

            # 2. Normalisierung von Name und Gebietstyp
            norm_val, admin_type = normalize_name(raw_str)
            candidates = ref_sub[ref_sub["norm_name"] == norm_val]

            if target_level == "kreis" and admin_type and not candidates.empty:
                typed = candidates[candidates["ref_type"] == admin_type]
                if not typed.empty:
                    candidates = typed

            if len(candidates) == 1:
                row = candidates.iloc[0]
                results.append((row["ags"], row["name"], row["bez"], 100.0, "EXACT"))
                continue

            if len(candidates) > 1:
                info_list = [f"{r['ags']} ({r['bez']})" for _, r in candidates.iterrows()]
                results.append((None, None, None, 100.0, f"AMBIGUOUS: {' | '.join(info_list)}"))
                continue

            # 3. Unscharfes Matching mit RapidFuzz
            pool = ref_sub
            if target_level == "kreis" and admin_type:
                typed_pool = ref_sub[ref_sub["ref_type"] == admin_type]
                if not typed_pool.empty:
                    pool = typed_pool

            match = process.extractOne(
                norm_val,
                pool["norm_name"].tolist(),
                scorer=fuzz.WRatio,
            )

            if match and match[1] >= threshold:
                matched_norm, score, pos_idx = match
                same_name = pool[pool["norm_name"] == matched_norm]

                if len(same_name) > 1:
                    info_list = [f"{r['ags']} ({r['bez']})" for _, r in same_name.iterrows()]
                    results.append((None, None, None, round(score, 1), f"AMBIGUOUS: {' | '.join(info_list)}"))
                else:
                    row = pool.iloc[pos_idx]
                    status = "FUZZY_OK" if score >= 92 else "REVIEW"
                    results.append((row["ags"], row["name"], row["bez"], round(score, 1), status))
            else:
                score = round(match[1], 1) if match else 0.0
                results.append((None, None, None, score, "UNMATCHED"))

        res_df = pd.DataFrame(
            results,
            columns=["AGS", "AGS_Name", "AGS_Typ", "Match_Score", "Match_Status"],
            index=out_df.index,
        )
        return pd.concat([out_df, res_df], axis=1)