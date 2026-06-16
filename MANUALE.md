# Analisi Diari Alimentari — Guida utente

Versione applicazione: **1.2.7**

Applicazione desktop (Windows e macOS) per analizzare diari alimentari su **4 giorni**:
si associa ogni alimento del diario a una voce della **Banca Dati di composizione
degli Alimenti (BDA)** e si ottengono i valori nutrizionali per giorno e in media,
inclusa la classificazione **NOVA / mNOVA** del grado di processazione.

---

## 1. Installazione e primo avvio

1. Scarica lo zip per il tuo sistema dalla pagina **Releases**:
   - Windows → `DiarioAlimentare-Windows.zip` → estrai ed esegui `DiarioAlimentare.exe`
   - macOS → `DiarioAlimentare-macOS.zip` → estrai e apri `DiarioAlimentare.app`
2. **macOS**: se compare l'avviso di sicurezza, fai **clic destro sull'app → Apri** la prima volta.
3. Al primo avvio l'app è **vuota**: dovrai caricare la BDA e creare/importare gli utenti.

### Dove vengono salvati i dati
Tutti i dati (utenti, diari, BDA, preferenze) stanno in un singolo database, **per utente del computer**:

| Sistema | Percorso |
|---------|----------|
| Windows | `%APPDATA%\DiarioAlimentare\food_diary.db` |
| macOS   | `~/Library/Application Support/DiarioAlimentare/food_diary.db` |

I dati **persistono** tra un aggiornamento dell'app e l'altro. Per spostarli su un altro
computer usa **File → Esporta/Importa progetto** (vedi §9).

---

## 2. Concetti chiave

- **BDA**: la banca dati degli alimenti con i valori nutrizionali per 100 g. Va caricata da Excel.
- **Utente** (o soggetto): chi compila il diario, identificato da un **codice**.
- **4 giorni × 5 pasti**: Colazione, Spuntino mattina, Pranzo, Spuntino pomeriggio, Cena.
- **Associazione**: il legame tra una voce del diario (es. «Pasta») e l'alimento BDA corrispondente.
  Solo le voci **associate** entrano nei calcoli nutrizionali.
- **NOVA** (1–4): grado di processazione, inserito manualmente per ogni voce.
- **mNOVA**: NOVA «raffinato». NOVA 1 e 2 restano invariati; NOVA 3 e 4 diventano
  **3a/3b** e **4a/4b** in base a soglie (cutoff) sui nutrienti (vedi §8).

---

## 3. Le tre schede principali

All'apertura trovi tre schede: **Diari**, **BDA**, **Utenti**.

### Diari
Il cuore dell'app. A sinistra l'elenco utenti, a destra i 4 giorni + il riepilogo nutrizionale.

### BDA
Caricamento e consultazione della banca dati alimenti.

### Utenti
Gestione anagrafica dei soggetti e relative note.

---

## 4. Flusso di lavoro tipico

1. **Carica la BDA** (scheda BDA → *Carica BDA da Excel*).
2. **Crea o importa gli utenti** (scheda Diari, pulsanti a sinistra; oppure *Importa Content Export*).
3. **Compila il diario** di ogni utente nei 4 giorni (o importalo).
4. **Associa** ogni voce all'alimento BDA (doppio clic sulla riga o *Associa BDA*).
5. Inserisci il **NOVA** di ogni voce dove serve.
6. Controlla il **Riepilogo nutrizionale** ed eventualmente **esporta** in Excel.

---

## 5. Scheda BDA

- **Carica BDA da Excel**: seleziona il file della banca dati. L'app riconosce il foglio
  «BDA» e, se presente, il foglio delle **categorie merceologiche**.
- **Ricerca** per nome e **filtro per categoria**.
- Gli **id degli alimenti sono stabili** (basati sul «Codice Alimento»): ricaricando una
  BDA aggiornata, le associazioni già fatte **non si rompono**.

---

## 6. Scheda Diari

### Barra utenti (sinistra)
- **Cerca utente**, elenco con **caselle di selezione** (servono per l'export multiplo).
- **+ Aggiungi / Elimina** utente.
- **Importa Content Export**: importa il file Excel «Content Export» (4 giorni per utente).
- **Seleziona tutti / Deseleziona tutti** e **Esporta selezionati** (export Excel del riepilogo).
- Pulsante **◀ Nascondi utenti** (in alto a destra): comprime la barra per avere più spazio.

### Griglia dei giorni (destra)
Ogni giorno è una scheda con la lista delle voci. Colonne:

| Colonna | Significato |
|---------|-------------|
| Pasto / Ora / Luogo | dati della voce |
| Alimento (diario) | come scritto nel diario |
| Note | annotazioni |
| **Qtà rif.** | quantità come riportata nel diario (testo libero, es. «1 tazzina») |
| **Qtà (g)** | quantità in grammi usata per i calcoli |
| Alimento BDA | alimento associato |
| **Stato** | ✓ associato · ⚠ associazione da rifare (BDA cambiata) · — non associato |
| NOVA | valore NOVA (1–4), modificabile |
| mNOVA | classe calcolata (es. 3a, 4b) |

**Modifica rapida**: doppio clic sulle colonne *Qtà (g)* e *NOVA* per editarle al volo.

### Pulsanti barra giorni
- **+ Aggiungi / Modifica / Elimina** voce.
- **Associa BDA**: apre la ricerca alimenti; **doppio clic** su un alimento lo associa subito.
- **Rimuovi assoc.**
- **Valori nutrizionali**: per la voce selezionata mostra una finestra con alimento, quantità,
  NOVA/mNOVA, energia ricalcolata e la tabella **per 100 g | per quantità** di tutti i nutrienti.
- **Verifica / riassegna BDA** (in alto): ricontrolla le associazioni dell'utente, le ricollega
  per «Codice Alimento» e segnala gli alimenti spariti dalla BDA o con valori modificati.

---

## 7. Riepilogo nutrizionale

Scheda all'interno dei giorni. Mostra, per **ogni giorno** e in **media (4 giorni)**:

- **Energia totale RICALCOLATA (kcal)**: calcolata dai macronutrienti come
  `proteine×4 + grassi×9 + carboidrati disponibili×3,75 + fibra×2 + alcol×7`.
- **Valore** di ogni nutriente e, se configurata, la **% giornaliera** (vedi §8).
- **Ripartizione per categoria mNOVA**: per ciascuna classe (1, 2, 3a, 3b, 3a+3b, 4a, 4b, 4a+4b)
  i **grammi**, le **kcal** e la **%Kcal/Kcaltot**.
- Avviso sulle **voci senza BDA** (non incluse nei calcoli).

---

## 8. Preferenze

- **Cutoff mNOVA…**: definisce le soglie che trasformano NOVA 3/4 in 3a/3b e 4a/4b.
  *Se almeno un nutriente supera (`>`) la soglia → variante «b», altrimenti «a».*
  Soglie **distinte per cibo e bevanda**. Il «Sale (g)» è derivato dal sodio
  (`Sodio mg × 2,5 / 1000`).
- **Bevande (categorie)…**: indica quali categorie merceologiche sono bevande (per applicare
  i cutoff «bevanda»). Si può cercare per **codice** o nome.
- **Formula nutrizionale…**: la formula con cui si calcola ogni nutriente
  (default `val * qty / 100`, dove `val` = valore per 100 g e `qty` = grammi).
- **Valori speciali (-2 / -3)…**: nella BDA `-2` = «tracce», `-3` = «dato mancante».
  Qui scegli con quale numero sostituirli nei calcoli (default 0).
- **Percentuali…**: nutrienti per cui mostrare una colonna %, con fattore e denominatore
  (denominatore vuoto = energia totale del giorno). Con fattore = kcal/g ottieni la
  ripartizione energetica.
- **Decimali valori…**: quanti decimali mostrare (0–6) nel riepilogo, nella ripartizione mNOVA
  e **nell'export Excel**.

### Menu Visualizza
- **Dimensione testo…**: due valori separati, uno per l'**interfaccia** (menu, pulsanti, liste)
  e uno per le **tabelle** dati (diario, riepilogo, BDA). Anche scorciatoie Aumenta/Riduci/Reimposta.

---

## 9. Import / Export

### Configurazione (File → Esporta/Importa configurazione)
Salva/ripristina solo le **preferenze** (cutoff, formule, percentuali, valori speciali, bevande)
in un file `.json` leggero.

### Progetto (File → Esporta/Importa progetto)
Salva/ripristina **tutto** il lavoro (utenti, diari, etichette giorni, configurazione **e BDA**)
in un unico file `.json.gz` (compresso). All'**import** scegli:

- **Sostituisci tutto**: rimpiazza i dati attuali con quelli del file (BDA e config comprese).
- **Unisci**:
  - utenti **nuovi** → aggiunti;
  - utenti già presenti **senza associazioni** → aggiornati automaticamente col file;
  - utenti già presenti **con associazioni** → ti viene chiesto, in un elenco con caselle,
    quali **sovrascrivere**; gli altri restano invariati.

> Suggerimento: dopo un'unione, se gli alimenti non risultano associati usa
> **Verifica / riassegna BDA**.

### Export Excel del riepilogo (Esporta selezionati)
Genera un file con due fogli:
- **Dettaglio giorni**: una riga per utente×giorno con energia, nutrienti, percentuali e la
  ripartizione mNOVA (g, kcal, %Kcal/Kcaltot).
- **Media 4 giorni**: le stesse colonne mediate sui 4 giorni.

---

## 10. Backup e spostamento dati

- **Backup**: *File → Esporta progetto* (file `.json.gz`); per ripristinare, *Importa progetto →
  Sostituisci tutto*.
- **Nuovo computer**: installa l'app, poi importa il progetto esportato.
- Il database vero e proprio è il file `food_diary.db` indicato in §1 (puoi anche copiarlo a mano).

---

## 11. Domande frequenti

**L'app si apre con dati già dentro.**
Sono i *tuoi* dati salvati in precedenza sul computer (vedi §1): è normale. Un computer nuovo
parte vuoto.

**I valori nell'app e nell'Excel hanno decimali diversi.**
Regola **Preferenze → Decimali valori…**: vale sia per l'app sia per l'export.

**Una voce non entra nei calcoli.**
Probabilmente non è **associata** alla BDA (Stato «—») oppure non ha una **quantità in grammi**.

**Ho ricaricato la BDA e alcune voci sono «⚠».**
Usa **Verifica / riassegna BDA**: ricollega per Codice Alimento e segnala i casi da sistemare.
