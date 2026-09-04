"""
Costanti globali, helper puri e calcoli condivisi.
"""

import re
import json
import pandas as pd


# ── Constants ───────────────────────────────────────────

MEALS = ["Colazione", "Spuntino mattina", "Pranzo", "Spuntino pomeriggio", "Cena"]
MEAL_ORDER = {m: i for i, m in enumerate(MEALS)}
DAYS = [1, 2, 3, 4]
APP_TITLE = "Analisi Diari Alimentari"
APP_VERSION = "1.2.10"

# Marcatore dei file di export/import (configurazione e progetto)
EXPORT_FORMAT = "diario-alimentare"
EXPORT_VERSION = 1

# Estensione dei file di progetto (JSON gzippato con un'estensione dedicata).
# I vecchi .json.gz / .json restano leggibili (il gzip si riconosce dai magic byte).
PROJECT_EXT = ".diario"
PROJECT_FILTER = (
    f"Progetto Diario Alimentare (*{PROJECT_EXT});;"
    "JSON compresso (*.json.gz);;JSON (*.json)"
)
PROJECT_OPEN_FILTER = (
    f"Progetti Diario Alimentare (*{PROJECT_EXT} *.json.gz *.json);;Tutti i file (*.*)"
)

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

# Energia totale (kcal) calcolata dai totali giornalieri dei macronutrienti.
# Per ciascun termine: (nomi-colonna BDA accettati, coefficiente kcal/g).
ENERGY_LABEL = "Energia totale RICALCOLATA (kcal)"
_ENERGY_TERMS = [
    (("Total protein", "Proteine totali"),                              4.0),
    (("Total fat", "Lipidi totali"),                                    9.0),
    (("Available carbohydrates (MSE)", "Carboidrati disponibili (MSE)"), 3.75),
    (("Dietary total fibre", "Dietary total fiber", "Fibra alimentare totale"), 2.0),
    (("Alcohol", "Alcol"),                                              7.0),
]


# ── Helper puri ─────────────────────────────────────────

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


DEFAULT_DECIMALS = 2


def _display_decimals(db) -> int:
    """Numero di decimali per i valori nutrizionali (preferenza, 0–6)."""
    try:
        n = int(db.get_setting("display_decimals", DEFAULT_DECIMALS))
    except (TypeError, ValueError):
        n = DEFAULT_DECIMALS
    return max(0, min(6, n))


def _open_excel(path):
    """Apre un file Excel in modo robusto (anche .xlsx con estensione errata)."""
    try:
        return pd.ExcelFile(path)
    except Exception:
        return pd.ExcelFile(path, engine="openpyxl")


def _parse_bda_categories(xl) -> list:
    """Legge il foglio delle categorie merceologiche dall'Excel BDA.

    Struttura attesa: Codice | Categoria Merceologica (IT) | Food Categories (EN).
    Le macro-categorie (codici < 1000, nomi maiuscoli) raggruppano le
    sotto-categorie che le seguono nell'elenco. Ritorna lista di record o [].
    """
    sheet = next(
        (s for s in xl.sheet_names
         if "CATMERCEOL" in str(s).upper() or "CATEGOR" in str(s).upper()),
        None,
    )
    if not sheet:
        return []
    df = pd.read_excel(xl, sheet_name=sheet)
    if df.shape[1] < 2:
        return []
    out, macro = [], None
    for _, r in df.iterrows():
        code = r.iloc[0]
        if pd.isna(code):
            continue
        try:
            c = str(int(float(code)))
        except (TypeError, ValueError):
            continue
        name_it = "" if pd.isna(r.iloc[1]) else str(r.iloc[1]).strip()
        name_en = "" if (df.shape[1] < 3 or pd.isna(r.iloc[2])) else str(r.iloc[2]).strip()
        if int(c) < 1000:  # macro-categoria
            macro = (c, name_it, name_en)
            out.append({"code": c, "name_it": name_it, "name_en": name_en,
                        "macro_code": c, "macro_name_it": name_it, "macro_name_en": name_en})
        else:              # sotto-categoria → eredita la macro precedente
            out.append({"code": c, "name_it": name_it, "name_en": name_en,
                        "macro_code": macro[0] if macro else None,
                        "macro_name_it": macro[1] if macro else None,
                        "macro_name_en": macro[2] if macro else None})
    return out


def _category_code(cm_value) -> str:
    """Normalizza il valore 'Categoria Merceologica' di un alimento a codice stringa."""
    if cm_value is None:
        return ""
    try:
        return str(int(float(cm_value)))
    except (TypeError, ValueError):
        return str(cm_value).strip()


def _food_category_name(cat_map: dict, cm_value) -> str:
    """Nome (IT) della categoria di un alimento, da 'Categoria Merceologica'."""
    rec = cat_map.get(_category_code(cm_value))
    return rec["name_it"] if rec else ""


def _load_mnova_config(db) -> dict:
    """Configurazione mNOVA: cutoff distinti per cibo e bevanda + categorie bevanda.

    Returns {'food': [...], 'beverage': [...], 'beverage_cats': set,
             'code_to_macro': {code: macro_code}}.
    Compatibile col vecchio formato (lista semplice = cutoff del cibo).
    """
    try:
        data = json.loads(db.get_setting("mnova_cutoffs", "[]"))
    except Exception:
        data = []
    if isinstance(data, list):           # vecchio formato → solo cibo
        food, beverage = data, []
    else:
        food = data.get("food", [])
        beverage = data.get("beverage", [])
    try:
        bev_cats = {str(c) for c in json.loads(db.get_setting("beverage_categories", "[]"))}
    except Exception:
        bev_cats = set()
    code_to_macro = {}
    if bev_cats:
        try:
            code_to_macro = {c: r.get("macro_code")
                             for c, r in db.get_categories_map().items()}
        except Exception:
            code_to_macro = {}
    return {"food": food, "beverage": beverage,
            "beverage_cats": bev_cats, "code_to_macro": code_to_macro}


def _is_beverage(bda_data: dict, config: dict) -> bool:
    """True se l'alimento appartiene a una categoria marcata come bevanda."""
    cats = config.get("beverage_cats")
    if not cats or not bda_data:
        return False
    code = _category_code(bda_data.get("Categoria Merceologica"))
    if code in cats:
        return True
    return config.get("code_to_macro", {}).get(code) in cats


_SALT_LABEL = "Sale (g)"
_SALT_SOURCE = ("Sodium", "Sodio")
_SALT_FACTOR = 2.5 / 1000.0  # sodio (mg/100 g) → sale (g/100 g)

# Nutrienti ammessi come cutoff mNOVA, nell'ordine di visualizzazione (per 100 g).
# Una tupla = colonna BDA diretta (nomi accettati); _SALT_LABEL = derivato dal sodio.
_CUTOFF_ORDER = [
    ("Total fat", "Lipidi totali"),
    ("Total saturated fatty acids", "Acidi grassi saturi totali"),
    ("Soluble carbohydrates (MSE)", "Carboidrati solubili (MSE)"),
    _SALT_LABEL,
]


def _cutoff_options(db) -> list:
    """Nutrienti selezionabili come cutoff mNOVA, adattati ai nomi BDA presenti."""
    cols = set(db.get_bda_columns() or [])
    opts = []
    for entry in _CUTOFF_ORDER:
        if entry == _SALT_LABEL:
            if any(n in cols for n in _SALT_SOURCE):
                opts.append(_SALT_LABEL)
        else:
            col = next((n for n in entry if n in cols), None)
            if col:
                opts.append(col)
    return opts


def _cutoff_value(label, bda_data: dict):
    """Valore del nutriente-cutoff (per 100 g) dalla riga BDA, o None."""
    if not bda_data:
        return None
    if label == _SALT_LABEL:
        src = next((bda_data[n] for n in _SALT_SOURCE if bda_data.get(n) is not None), None)
        try:
            return float(src) * _SALT_FACTOR if src is not None else None
        except (TypeError, ValueError):
            return None
    v = bda_data.get(label)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# Configurazione percentuali di default: (nomi-colonna accettati, fattore).
# Denominatore di default = energia totale del giorno.
_PERCENT_DEFAULT_TERMS = [
    (("Total protein", "Proteine totali"),                              4.0),
    (("Total fat", "Lipidi totali"),                                    9.0),
    (("Available carbohydrates (MSE)", "Carboidrati disponibili (MSE)"), 3.75),
    (("Dietary total fibre", "Dietary total fiber", "Fibra alimentare totale"), 2.0),
    (("Alcohol", "Alcol"),                                              7.0),
    (("Soluble carbohydrates (MSE)", "Carboidrati solubili (MSE)"),     3.75),
]


def _default_percent_config(db) -> list:
    """Config % di default, adattata ai nomi-colonna effettivi della BDA."""
    cols = set(db.get_bda_columns() or [])
    out = []
    for names, factor in _PERCENT_DEFAULT_TERMS:
        col = next((n for n in names if n in cols), None)
        if col:
            out.append({"col": col, "factor": factor, "denom": ""})
    return out


def _load_percent_config(db) -> list:
    """Nutrienti con colonna percentuale.

    Lista di {'col': str, 'factor': float, 'denom': str}. 'denom' vuoto = energia
    totale del giorno, altrimenti il nome di una colonna BDA. Se mai configurata,
    ritorna la configurazione di default.
    """
    raw = db.get_setting("percent_config")
    if raw is None:
        return _default_percent_config(db)
    try:
        return json.loads(raw)
    except Exception:
        return []


# Codici speciali BDA: -2 = tracce (concentrazione molto bassa), -3 = dato mancante
_SPECIAL_CODES = [
    ("-2", "Tracce", "Concentrazione del componente molto bassa."),
    ("-3", "Missing (dato mancante)",
     "Componente non disponibile al momento nei dati di composizione."),
]
_SPECIAL_DEFAULTS = {code: {"value": 0.0, "desc": desc} for code, _name, desc in _SPECIAL_CODES}


def _load_special_values(db) -> dict:
    """Mappa i codici speciali BDA al valore sostitutivo scelto dall'utente.

    Returns {'-2': {'value': float, 'desc': str}, '-3': {...}}.
    """
    try:
        saved = json.loads(db.get_setting("special_values") or "{}")
    except Exception:
        saved = {}
    out = {}
    for code, default in _SPECIAL_DEFAULTS.items():
        s = saved.get(code, {})
        try:
            value = float(s.get("value", default["value"]))
        except (TypeError, ValueError):
            value = default["value"]
        out[code] = {"value": value, "desc": s.get("desc", default["desc"])}
    return out


def _compute_mnova(nova, bda_data: dict | None, config: dict) -> str:
    """Calcola l'etichetta mNOVA.

    NOVA 1/2 → uguale a NOVA; NOVA 3/4 → 'a' o 'b' in base ai cutoff.
    Usa i cutoff 'beverage' se l'alimento è in una categoria-bevanda,
    altrimenti quelli 'food'. `config` = output di _load_mnova_config.
    """
    if nova is None:
        return ""
    if nova in (1, 2):
        return str(nova)
    if not bda_data or not config:
        return str(nova)

    cutoffs = config["beverage"] if _is_beverage(bda_data, config) else config["food"]
    if not cutoffs:
        return str(nova)

    def _exceeds(c):
        if not c.get("col") or c.get("threshold") is None:
            return False
        val = _cutoff_value(c["col"], bda_data)
        return val is not None and val > float(c["threshold"])

    is_b = any(_exceeds(c) for c in cutoffs)
    return f"{nova}b" if is_b else f"{nova}a"


# ── Calcoli riepilogo ─────────────────────────────────────

def _compute_energy_kcal(day_totals: dict) -> float:
    """Energia (kcal) di un giorno dai totali dei macronutrienti.

    (proteine*4) + (grassi*9) + (carboidrati disponibili*3,75)
    + (fibra*2) + (alcol*7).
    """
    energy = 0.0
    for names, coeff in _ENERGY_TERMS:
        for name in names:
            if name in day_totals:
                energy += day_totals[name] * coeff
                break
    return energy


def _compute_user_totals(db: "Database", user_code: str):
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
    # Sostituzioni per i codici speciali BDA (-2 tracce, -3 missing)
    special = {float(k): v["value"] for k, v in _load_special_values(db).items()}
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
                fval = float(val)
                fval = special.get(fval, fval)  # rimpiazza -2/-3 col valore scelto
                formula = formulas.get(col, _default)
                result = eval(formula, _safe, {"val": fval, "qty": qty})
                totals[day][col] = totals[day].get(col, 0.0) + result
            except (TypeError, ValueError, ZeroDivisionError, NameError, SyntaxError):
                pass

    return totals, missing


# Colonne della tabella di ripartizione mNOVA.
_MNOVA_COLS = ["1", "2", "3a", "3b", "3a+3b", "4a", "4b", "4a+4b"]


def _compute_mnova_breakdown(db: "Database", user_code: str):
    """Ripartizione per categoria mNOVA: grammi e kcal per giorno e in media.

    Le voci senza BDA o senza valore NOVA sono escluse.

    Returns:
        per_day – dict {day: (grams, kcal)}, con grams/kcal dict {colonna mNOVA: float}
        media   – (grams, kcal): media giorno per giorno (somma ÷ numero di giorni)
    """
    try:
        formulas = json.loads(db.get_setting("nutri_formulas") or "{}")
    except Exception:
        formulas = {}
    _default = "val * qty / 100"
    _safe = {"__builtins__": {}, "abs": abs, "max": max, "min": min, "round": round}
    special = {float(k): v["value"] for k, v in _load_special_values(db).items()}
    mnova_cfg = _load_mnova_config(db)

    grams = {d: {c: 0.0 for c in _MNOVA_COLS} for d in DAYS}
    kcal = {d: {c: 0.0 for c in _MNOVA_COLS} for d in DAYS}

    entries = db.get_entries(user_code)
    bda_ids = {e["bda_food_id"] for e in entries if e.get("bda_food_id")}
    bda_cache = db.get_bda_foods_by_ids(bda_ids) if bda_ids else {}

    for e in entries:
        if not e["bda_food_id"] or e.get("nova") is None:
            continue
        bda = bda_cache.get(e["bda_food_id"])
        if not bda:
            continue
        day = e["day"]
        mnova = _compute_mnova(e["nova"], bda, mnova_cfg)  # "1".."4b" (o "3"/"4")
        if not mnova:
            continue
        qty = float(e["quantity_g"]) if e["quantity_g"] is not None else 100.0

        # Grammi nutrizionali della singola voce → energia (kcal) della voce.
        food_totals = {}
        for col, val in bda.items():
            if col in ("id", "name") or col in _SKIP_BDA_COLS or val is None:
                continue
            try:
                fval = float(val)
                fval = special.get(fval, fval)
                food_totals[col] = eval(formulas.get(col, _default), _safe,
                                        {"val": fval, "qty": qty})
            except (TypeError, ValueError, ZeroDivisionError, NameError, SyntaxError):
                pass
        e_kcal = _compute_energy_kcal(food_totals)

        def _add(cat):
            grams[day][cat] += qty
            kcal[day][cat] += e_kcal

        if mnova in _MNOVA_COLS:           # colonna esatta (1, 2, 3a, 3b, 4a, 4b)
            _add(mnova)
        if mnova.startswith("3"):          # colonna somma 3a+3b
            _add("3a+3b")
        elif mnova.startswith("4"):        # colonna somma 4a+4b
            _add("4a+4b")

    per_day = {d: (grams[d], kcal[d]) for d in DAYS}
    n = len(DAYS)
    media_g = {c: sum(grams[d][c] for d in DAYS) / n for c in _MNOVA_COLS}
    media_k = {c: sum(kcal[d][c] for d in DAYS) / n for c in _MNOVA_COLS}
    return per_day, (media_g, media_k)


def _compute_food_nutrients(db, bda_data: dict, qty):
    """Valori nutrizionali di un singolo alimento.

    Ritorna (per100, perqty): due dict {colonna: valore}.
    - per100  – valore per 100 g (con i codici speciali -2/-3 sostituiti);
    - perqty  – valore per la quantità data, applicando la formula del nutriente.
    Coerente con _compute_user_totals (la somma dei perqty = totali del giorno).
    """
    try:
        formulas = json.loads(db.get_setting("nutri_formulas") or "{}")
    except Exception:
        formulas = {}
    _default = "val * qty / 100"
    _safe = {"__builtins__": {}, "abs": abs, "max": max, "min": min, "round": round}
    special = {float(k): v["value"] for k, v in _load_special_values(db).items()}
    q = float(qty) if qty is not None else 100.0
    per100, perqty = {}, {}
    for col, val in bda_data.items():
        if col in ("id", "name") or col in _SKIP_BDA_COLS or val is None:
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            continue
        fval = special.get(fval, fval)
        per100[col] = fval
        try:
            perqty[col] = eval(formulas.get(col, _default), _safe, {"val": fval, "qty": q})
        except (TypeError, ValueError, ZeroDivisionError, NameError, SyntaxError):
            perqty[col] = None
    return per100, perqty
