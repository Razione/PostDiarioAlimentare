# diario-web

Versione web di **Analisi Diari Alimentari** (React + Vite + TypeScript + Firebase).
Vedi il piano in `../WEBAPP_PLAN.md`.

## Stato: Fase 0 (scaffold)
Pronti: autenticazione (Firebase Auth/Google), Firestore con persistenza offline,
guscio a schede (Diari/BDA/Utenti) e il **motore nutrizionale** portato da Python
(`src/lib/nutrition`: energia ricalcolata, mNOVA cibo/bevanda, sale dal sodio,
valori speciali, formule via mathjs). Le sezioni UI sono placeholder (Fasi 1–6).

## Avvio in locale
```bash
cd diario-web
npm install
cp .env.example .env.local     # riempi con la config del tuo progetto Firebase
npm run dev
```

### Configurazione Firebase
1. Console Firebase → **Authentication** → abilita **Google**.
2. Console Firebase → **Firestore Database** → crea il database (modalità produzione).
3. Impostazioni progetto → *I tuoi apps* (Web) → copia la config SDK nei valori
   `VITE_FIREBASE_*` di `.env.local`.
4. Regole Firestore (bozza, un solo team):
   ```
   rules_version = '2';
   service cloud.firestore {
     match /databases/{db}/documents {
       match /teams/{t}/{document=**} {
         allow read, write: if request.auth != null
           && request.auth.uid in get(/databases/$(db)/documents/teams/$(t)).data.members;
       }
     }
   }
   ```
   Crea il doc `teams/default` con `members: [<uid1>, <uid2>]`.

## Dati
- **BDA**: asset statico. Genera `src/data/bda.json` con
  `python ../tools/export_web_data.py` (copia `web-export/bda.json`).
- **Seme iniziale**: `python ../tools/export_web_data.py` → `web-export/seed.json`,
  poi `node ../tools/firestore_import.mjs web-export/seed.json`.

## Deploy (Netlify)
Collega il repo, base directory `diario-web`, build `npm run build`, publish `dist`
(vedi `netlify.toml`). Imposta le variabili `VITE_FIREBASE_*` nelle env di Netlify.

## Struttura
```
src/
  lib/firebase.ts        init Auth + Firestore (persistenza)
  lib/nutrition/         motore di calcolo (portato da constants.py)
  features/auth/         login/logout
  App.tsx                guscio a schede
```
