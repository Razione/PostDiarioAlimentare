# tools/ — dati per la webapp

Strumenti per portare i dati del Diario Alimentare (desktop, SQLite) verso la
webapp (React + Firebase). Vedi il piano nella chat / `WEBAPP_PLAN.md`.

## 1. `export_web_data.py` — estrae i dati

```
python tools/export_web_data.py            # DB predefinito → ./web-export/
python tools/export_web_data.py --db PERCORSO --out CARTELLA
```

Produce due file in `web-export/` (cartella in `.gitignore`):

### `bda.json` — banca dati alimenti (asset statico, sola lettura)
```jsonc
{
  "columns": ["Simbolo", "Codice Alimento", ...],   // ordine colonne BDA
  "skipColumns": [...],                              // colonne non nutrizionali
  "foods": [
    { "id": 3239, "code": "1300_2", "name": "ACCIUGHE o ALICI",
      "data": { "Energia, Ric con fibra (kcal)": 96, ... } }
  ],
  "categories": [
    { "code": "1", "name_it": "...", "macro_code": "1", "macro_name_it": "..." }
  ]
}
```
Uso nel web: servire come asset statico da Netlify, caricarlo una volta e
cercare in memoria (Fuse.js). Le associazioni si legano per **`code`** (Codice
Alimento), stabile tra le versioni BDA.

### `seed.json` — il lavoro attuale (dati personali)
```jsonc
{
  "subjects": [ { "code": "02HX6F", "notes": "" } ],
  "entries":  [ { "userCode": "02HX6F", "day": 1, "meal": "Colazione",
                  "foodName": "Latte di vacca", "quantityG": 250,
                  "bdaCode": "700428_2", "nova": 1,
                  "notes": "...", "ora": "10", "luogo": "Casa", "qtyRaw": "250ml" } ],
  "dayMeta":  [ { "code": "02HX6F", "day": 1, "dateLabel": "19/04/2026" } ],
  "settings": { "mnova_cutoffs": {...}, "percent_config": [...], ... }
}
```

## 2. `firestore_import.mjs` — carica `seed.json` in Firestore

Template Node (`firebase-admin`). Configuralo dopo aver creato il progetto
Firebase (vedi istruzioni nell'intestazione del file). Scrive:

```
teams/{TEAM}/subjects/{code}
teams/{TEAM}/subjects/{code}/entries/{autoId}
teams/{TEAM}/dayMeta/{code}_{day}
teams/{TEAM}/settings/config
```

La BDA **non** va in Firestore: resta `bda.json` statico.
