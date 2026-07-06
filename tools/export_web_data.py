#!/usr/bin/env python3
"""
Estrae dal database SQLite del Diario Alimentare i dati pronti per la webapp:

  bda.json   – banca dati alimenti + categorie (asset statico, sola lettura)
  seed.json  – il lavoro attuale (soggetti, voci, etichette giorni, preferenze),
               rimodellato secondo il modello dati Firestore della webapp.

Uso:
    python tools/export_web_data.py [--db PERCORSO] [--out CARTELLA]

Senza argomenti usa il DB predefinito dell'app e scrive in ./web-export.
seed.json contiene dati personali: la cartella web-export/ è in .gitignore.
"""
import argparse
import json
import os
import sqlite3
import sys

# Riusa la stessa logica del percorso DB dell'app, se disponibile.
try:
    from database import _default_db_path
except Exception:
    def _default_db_path():
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                            "DiarioAlimentare")
        return os.path.join(base, "food_diary.db")

# Colonne BDA non nutrizionali (coerente con constants._SKIP_BDA_COLS).
_SKIP = {"Simbolo", "Codice Alimento", "Nome Alimento ENG",
         "Nome Scientifico", "Categoria Merceologica", "parte edibile"}

# Chiavi di settings che sono JSON serializzato → vanno riparsate.
_JSON_SETTINGS = {"mnova_cutoffs", "nutri_formulas", "percent_config",
                  "special_values", "beverage_categories"}


def _rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def export_bda(conn):
    foods, id2code = [], {}
    columns = []
    for r in conn.execute("SELECT id, name, data FROM bda_foods ORDER BY name"):
        data = json.loads(r["data"])
        if not columns:
            columns = list(data.keys())
        code = data.get("Codice Alimento")
        code = None if code in (None, "") else str(code)
        foods.append({"id": r["id"], "code": code, "name": r["name"], "data": data})
        if code is not None:
            id2code[r["id"]] = code

    categories = []
    try:
        for r in conn.execute("SELECT * FROM bda_categories"):
            categories.append(dict(r))
    except sqlite3.OperationalError:
        pass  # nessuna tabella categorie (BDA senza foglio categorie)

    bda = {
        "columns": columns,
        "skipColumns": sorted(_SKIP),
        "foods": foods,
        "categories": categories,
    }
    return bda, id2code


def export_seed(conn, id2code):
    subjects = _rows(conn, "SELECT code, notes FROM users ORDER BY code")

    entries = []
    for r in conn.execute("SELECT * FROM diary_entries"):
        # Associazione portabile: per Codice Alimento (stabile), non per id locale.
        code = r["bda_code"] or ""
        if not code and r["bda_food_id"]:
            code = id2code.get(r["bda_food_id"], "")
        entries.append({
            "userCode": r["user_code"],
            "day": r["day"],
            "meal": r["meal"],
            "foodName": r["food_name"],
            "quantityG": r["quantity_g"],
            "bdaCode": code or None,
            "nova": r["nova"],
            "notes": r["notes"] or "",
            "ora": r["ora"] or "",
            "luogo": r["luogo"] or "",
            "qtyRaw": r["qty_raw"] or "",
        })

    day_meta = [
        {"code": r["user_code"], "day": r["day"], "dateLabel": r["date_label"] or ""}
        for r in conn.execute("SELECT * FROM diary_day_meta")
    ]

    settings = {}
    for r in conn.execute("SELECT key, value FROM settings"):
        v = r["value"]
        if r["key"] in _JSON_SETTINGS and v is not None:
            try:
                v = json.loads(v)
            except Exception:
                pass
        settings[r["key"]] = v

    return {
        "subjects": subjects,
        "entries": entries,
        "dayMeta": day_meta,
        "settings": settings,
    }


def main():
    ap = argparse.ArgumentParser(description="Export dati per la webapp Diario Alimentare")
    ap.add_argument("--db", default=_default_db_path(), help="percorso del food_diary.db")
    ap.add_argument("--out", default="web-export", help="cartella di destinazione")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        sys.exit(f"DB non trovato: {args.db}")
    os.makedirs(args.out, exist_ok=True)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        bda, id2code = export_bda(conn)
        seed = export_seed(conn, id2code)
    finally:
        conn.close()

    bda_path = os.path.join(args.out, "bda.json")
    seed_path = os.path.join(args.out, "seed.json")
    with open(bda_path, "w", encoding="utf-8") as f:
        json.dump(bda, f, ensure_ascii=False)
    with open(seed_path, "w", encoding="utf-8") as f:
        json.dump(seed, f, ensure_ascii=False, indent=2)

    print(f"DB:        {args.db}")
    print(f"bda.json:  {len(bda['foods'])} alimenti, {len(bda['categories'])} categorie, "
          f"{len(bda['columns'])} colonne  ({os.path.getsize(bda_path)/1_048_576:.2f} MB)")
    print(f"seed.json: {len(seed['subjects'])} soggetti, {len(seed['entries'])} voci, "
          f"{len(seed['dayMeta'])} etichette giorno, {len(seed['settings'])} preferenze")
    assoc = sum(1 for e in seed["entries"] if e["bdaCode"])
    print(f"           voci con associazione (Codice Alimento): {assoc}/{len(seed['entries'])}")


if __name__ == "__main__":
    main()
