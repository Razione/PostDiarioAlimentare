# Webapp Diari Alimentari — Piano di implementazione

Versione web del Diario Alimentare (attualmente desktop Python/PyQt6).
Obiettivo principale: **lavoro condiviso in tempo reale** tra più persone,
eliminando lo scambio manuale di file di progetto.

## Vincoli decisi
- **Convivenza**: desktop e web coesistono all'inizio; il desktop resta la
  fonte "ufficiale" finché la web non è pronta. Ponte: l'export progetto JSON.
- **Scala**: ~2 persone (un team).
- **Offline**: basta la **persistenza offline di Firestore** (no offline "serio").

## Stack
- **Frontend**: React + Vite + TypeScript; griglia **TanStack Table**; ricerca BDA con **Fuse.js**.
- **Auth**: Firebase Auth (Google/email), 2 account membri di un "team".
- **Dati**: **Firestore** con `enableIndexedDbPersistence()` (realtime + offline).
- **BDA**: **asset JSON statico** su Netlify (sola lettura, ricerca in memoria).
- **Hosting**: **Netlify** (frontend). Firebase solo Auth + Firestore.
- **Excel**: **SheetJS** lato client. **Formule**: **mathjs** (mai `eval`).

## Struttura repo (nuovo repo `diario-web`)
```
diario-web/
  src/
    lib/nutrition/     porting di constants.py (calcoli, mNOVA, energia, %…)
    lib/firebase.ts    init Auth + Firestore
    data/bda.json      BDA esportata dal desktop (tools/export_web_data.py)
    features/
      auth/  subjects/  diary/  bda/  summary/  settings/  io/
    components/        griglia, tabelle, dialog
  netlify.toml
```

## Modello dati Firestore
```
teams/{teamId}                          { name, members: [uid…] }
teams/{teamId}/subjects/{code}          { notes, updatedAt }
teams/{teamId}/subjects/{code}/entries/{id}
      { day, meal, foodName, notes, ora, luogo, qtyRaw, quantityG, bdaCode, nova }
teams/{teamId}/dayMeta/{code}_{day}     { code, day, dateLabel }
teams/{teamId}/settings/config          { mnova_cutoffs, nutri_formulas,
                                          percent_config, special_values,
                                          beverage_categories, display_decimals }
```
Le associazioni si legano per **bdaCode** (Codice Alimento), stabile tra versioni BDA.

**Security rules (schematiche):**
```
match /teams/{t}/{document=**} {
  allow read, write: if request.auth != null
    && request.auth.uid in get(/databases/$(database)/documents/teams/$(t)).data.members;
}
```
Con 2 persone su soggetti disgiunti non ci sono conflitti; sullo stesso campo
vince l'ultima scrittura.

## Fasi (ognuna incrementale, testabile, deployabile)

- **Fase 0 — Setup**: progetto Firebase, Netlify collegato al repo, scaffold
  Vite+TS, login Google, guscio con sezioni Diari/BDA/Utenti + routing.
- **Fase 1 — BDA (sola lettura)**: `bda.json` come asset; tab BDA con ricerca
  (Fuse) e filtro categoria.
- **Fase 2 — Soggetti + diario (Firestore realtime)**: CRUD soggetti/voci,
  griglia 4 giorni, editing celle (qtà/nova), sync live tra utenti.
- **Fase 3 — Associazione BDA + stato**: dialog ricerca alimento (doppio click),
  colori/filtro stato utenti, "Verifica/riassegna" per Codice Alimento.
- **Fase 4 — Motore nutrizionale**: porting `lib/nutrition` (energia ricalcolata,
  mNOVA cibo/bevanda, sale dal sodio, valori speciali, %); tabelle riepilogo +
  ripartizione mNOVA.
- **Fase 5 — Preferenze**: cutoff, **formula con mathjs**, percentuali, valori
  speciali, bevande, decimali.
- **Fase 6 — I/O e migrazione**: import del progetto (`seed.json`) in Firestore;
  export Excel (SheetJS); export "utenti selezionati" (comodità).
- **Fase 7 — Rifinitura**: persistenza offline, hardening rules, dominio Netlify,
  PWA opzionale.

Fasi 0–3 → app già usabile a due in tempo reale. Fasi 4–6 → parità col desktop.

## Migrazione / convivenza (concreta)
1. Genera i dati: `python tools/export_web_data.py` → `web-export/bda.json` + `seed.json`.
2. `bda.json` → asset statico del web. `seed.json` → Firestore con
   `tools/firestore_import.mjs` (una tantum, seme iniziale).
3. Durante la transizione lavori su **uno** dei due per evitare doppia verità.
   Quando la web copre le operazioni quotidiane, passi lì; il desktop resta per
   export/archivio. La BDA si aggiorna rigenerando `bda.json` (raro).

## Rischi / attenzioni
- **Formula `eval`** → mathjs (sicurezza sul web).
- **Costi**: BDA statica + 2 utenti → free tier Firebase/Netlify abbondante.
- **Ricerca BDA** in memoria: ok fino a decine di migliaia di righe (caso attuale: ~1300).

## Strumenti già pronti (in questo repo)
- `tools/export_web_data.py` — genera `bda.json` e `seed.json`.
- `tools/firestore_import.mjs` — carica `seed.json` in Firestore.
- `tools/README.md` — forma dei dati e uso.

## Prossimo passo
Creato il progetto Firebase, si parte con lo **scaffold** (Fase 0): React+Vite+TS
con Firebase cablato + `lib/nutrition` con le prime funzioni portate (energia + mNOVA).
