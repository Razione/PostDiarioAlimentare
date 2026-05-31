"""
Costanti globali, helper puri e calcoli condivisi.
"""

import re
import json

# ── Constants ─────────────────────────────────────────────────────────────────

MEALS = ["Colazione", "Spuntino mattina", "Pranzo", "Spuntino pomeriggio", "Cena"]
MEAL_ORDER = {m: i for i, m in enumerate(MEALS)}
DAYS = [1, 2, 3, 4]
APP_TITLE = "Analizzatore Diari Alimentari"

# Struttura del Content Export: offset rispetto alla colonna "Data" di ciascun giorno
# (meal_name, offset_primo_alimento, numero_max_alimenti)
_CONTENT_EXPORT_MEALS = [
    ("Colazione",            4,   20),
    ("Spuntino mattina",    66,   15),
    ("Pranzo",             113,   30),
    ("Spuntino pomeriggio", 205,  15),
    ("Cena",               252,   30),
]
# Colonne "Data" dove inizia ognuno dei 4 giorni nel DataFrame concatenato
_CONTENT_EXPORT_DAY_COLS = [1, 343, 685, 1027]

# Colonne BDA che non sono valori nutrizionali (da escludere dal riepilogo)
_SKIP_BDA_COLS = {
    "Simbolo", "Codice Alimento", "Nome Alimento ENG",
    "Nome Scientifico", "Categoria Merceologica", "parte edibile",
}


# ── Helper puri ───────────────────────────────────────────────────────────────

def _parse_qty_grams(raw: str):
    """Estrae i grammi da una stringa libera (es. '250 g', '80gr').
    Ritorna None se non riesce a determinare un peso in grammi."""
    if not raw or raw.lower() == "nan":
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:gr?(?:amm?[io]?)?)\b", raw, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            pass
    return None


def _qty_display(qty) -> str:
    """Formatta quantity_g per la visualizzazione: None → '—', altrimenti numero."""
    return "—" if qty is None else f"{qty:.4g}"


def _load_cutoffs(db) -> list:
    """Carica i cutoff mNOVA dal DB (lista di {'col': str, 'threshold': float})."""
    try:
        return json.loads(db.get_setting("mnova_cutoffs", "[]"))
    except Exception:
        return []


def _compute_mnova(nova, bda_data: dict | None, cutoffs: list) -> str:
    """Calcola l'etichetta mNOVA.
    NOVA 1/2 → uguale a NOVA; NOVA 3/4 → 'a' o 'b' in base ai cutoff."""
    if nova is None:
        return ""
    if nova in (1, 2):
        return str(nova)
    if not bda_data or not cutoffs:
        return str(nova)
    is_b = any(
        c.get("col") and c.get("threshold") is not None
        and bda_data.get(c["col"]) is not None
        and float(bda_data[c["col"]]) > float(c["threshold"])
        for c in cutoffs
    )
    return f"{nova}b" if is_b else f"{nova}a"


def _compute_user_totals(db, user_code: str):
    """Calcola i totali nutrizionali per giorno per un utente.

    Returns:
        totals  – dict {day: {col_name: float}}
        missing – dict {day: int}  (voci senza BDA associata)
    """
    try:
        formulas = json.loads(db.get_setting("nutri_formulas") or "{}")
    except Exception:
        formulas = {}
    _default = "val * qty / 100"
    _safe = {"__builtins__": {}, "abs": abs, "max": max, "min": min, "round": round}
    totals = {d: {} for d in DAYS}
    missing = {d: 0 for d in DAYS}

    entries = db.get_entries(user_code)
    bda_ids = {e["bda_food_id"] for e in entries if e.get("bda_food_id")}
    bda_cache = db.get_bda_foods_by_ids(bda_ids) if bda_ids else {}

    for e in entries:
        day = e["day"]
        if not e["bda_food_id"]:
            missing[day] += 1
            continue
        bda = bda_cache.get(e["bda_food_id"])
        if not bda:
            continue
        qty = float(e["quantity_g"]) if e["quantity_g"] is not None else 100.0
        for col, val in bda.items():
            if col in ("id", "name") or col in _SKIP_BDA_COLS or val is None:
                continue
            try:
                formula = formulas.get(col, _default)
                result = eval(formula, _safe, {"val": float(val), "qty": qty})
                totals[day][col] = totals[day].get(col, 0.0) + result
            except (TypeError, ValueError, ZeroDivisionError, NameError, SyntaxError):
                pass

    return totals, missing
