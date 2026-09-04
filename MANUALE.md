# Analisi Diari Alimentari — Guida utente

Versione applicazione: **1.2.10**

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
3. A ogni avvio l'app parte **pulita** e mostra una finestra iniziale: **Apri progetto…**,
   **Nuovo progetto vuoto** oppure un progetto tra quelli **recenti**. Con «Nuovo progetto vuoto»
   dovrai caricare la BDA e creare/importare gli utenti (vedi §9, «Progetti»).

### Dove vengono salvati i dati
Il tuo lavoro vive in **file di progetto** (`.json.gz`) che salvi dove preferisci: un progetto
contiene utenti, diari, BDA e configurazione. Puoi avere **più progetti** e aprire quello che
ti serve. L'app usa internamente un database temporaneo che viene **azzerato alla chiusura**,
quindi ciò che conta è **salvare il progetto** (le preferenze dell'app, come la dimensione del
testo, restano invece salvate a parte e non si perdono).

| Sistema | Workspace temporaneo (interno) |
|---------|--------------------------------|
| Windows | `%APPDATA%\DiarioAlimentare\food_diary.db` |
| macOS   | `~/Library/Application Support/DiarioAlimentare/food_diary.db` |

Poiché i dati stanno nei file di progetto, per spostarli su un altro computer basta **copiare il
file del progetto** (o usare **File → Salva progetto**, vedi §9).

### Aggiornare l'app
Quando esce una nuova versione (pagina **Releases**), l'aggiornamento è manuale ma semplice e
**non tocca i tuoi progetti** (sono file separati). La versione installata la trovi in
**Aiuto → Informazioni** (ed è mostrata in cima a questa guida, **Aiuto → Guida / Manuale**);
confrontala con quella più recente sulla pagina Releases.

> **Controllo aggiornamenti in-app**: all'avvio l'app verifica se c'è una versione più recente e,
> in caso, te lo segnala; puoi anche farlo a mano da **Aiuto → Controlla aggiornamenti…**. Da lì
> scarichi lo zip giusto; poi segui i passi qui sotto per sostituire l'app.

**Windows**
1. Scarica il nuovo `DiarioAlimentare-Windows.zip` dalla pagina Releases.
2. **Chiudi** l'app se è aperta.
3. Estrai lo zip e **sostituisci** la vecchia cartella (o `DiarioAlimentare.exe`) con la nuova.
4. Riavvia `DiarioAlimentare.exe`: ritrovi tutti i tuoi dati.

**macOS**
1. Scarica il nuovo `DiarioAlimentare-macOS.zip`.
2. **Chiudi** l'app.
3. Estrai e **trascina la nuova `DiarioAlimentare.app`** al posto della vecchia (es. in
   *Applicazioni*), sostituendola.
4. Al primo avvio, se compare l'avviso di sicurezza fai **clic destro sull'app → Apri**.

I tuoi progetti sono file separati, quindi l'aggiornamento non li tocca. Per sicurezza puoi
comunque salvarli prima con **File → Salva progetto** (vedi §9).

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
- **Utenti con questo alimento**: seleziona un alimento nell'elenco e premi il pulsante per
  vedere **quali utenti** hanno quell'alimento BDA associato nel diario (con il numero di voci).

---

## 6. Scheda Diari

### Barra utenti (sinistra)
- **Cerca utente** e **filtro per stato** (Tutti / Da fare / In corso / Completati): i due
  filtri si combinano.
- **Cerca per alimento**: mostra solo gli utenti che hanno un certo alimento, scegliendo se
  cercare per **Diario** (nel testo dell'alimento scritto nel diario **e nelle note**) o per
  **BDA** (nell'alimento della banca dati associato). Aprendo un utente, le **righe che
  corrispondono** vengono **evidenziate** nella griglia, così si individuano subito.
- L'elenco ha **caselle di selezione** (servono per l'export multiplo).
- Il **colore del testo** indica lo stato di associazione dell'utente:
  **verde** = tutte le voci associate · **ambra** = associazione in corso ·
  **default** = nessuna associazione (vedi legenda sotto l'elenco; il tooltip mostra
  «associate/totali»).
- **+ Aggiungi / Elimina** utente.
- **Importa Content Export**: importa il file Excel «Content Export» (4 giorni per utente).
  Chiede se **Sostituisci** (rimpiazza il diario degli utenti presenti nel file) o
  **Unisci** (aggiunge i nuovi; aggiorna quelli senza associazioni; per quelli già
  associati chiede in un elenco quali sovrascrivere).
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

## 9. Progetti, Import / Export

### Progetti (File → Nuovo / Apri / Salva)
Il lavoro vive in **file di progetto** (`.json.gz`, compressi) che contengono **tutto**: utenti,
diari, etichette giorni, configurazione **e BDA**. Puoi avere **più progetti** e passare dall'uno
all'altro.

- **Nuovo progetto vuoto** (Ctrl/⌘+N): parte da zero (dovrai caricare la BDA e gli utenti).
- **Apri progetto…** (Ctrl/⌘+O): apre un file di progetto (sostituisce ciò che è caricato).
- **Salva progetto** (Ctrl/⌘+S): salva sul file aperto; se non ne hai ancora uno, chiede dove.
- **Salva progetto con nome…** (Ctrl/⌘+Maiusc+S): salva una copia in un nuovo file.

All'avvio l'app parte pulita e chiede quale progetto aprire (con l'elenco dei **recenti**).
Se ci sono **modifiche non salvate**, il titolo mostra un `*` e, prima di **chiudere** o di
**aprire un altro progetto**, l'app chiede se salvare (Salva / Non salvare / Annulla).

### Configurazione (File → Esporta/Importa configurazione)
Salva/ripristina solo le **preferenze** (cutoff, formule, percentuali, valori speciali, bevande)
in un file `.json` leggero. Utile per applicare la **stessa configurazione** a più progetti.

### Condividere/unire utenti (File → Esporta progetto (utenti selezionati) / Unisci utenti da progetto)
- **Esporta progetto (utenti selezionati)**: esporta un file `.json.gz` **leggero** con i soli
  utenti **spuntati** nell'elenco (senza BDA né configurazione).
- **Unisci utenti da progetto…**: aggiunge al progetto corrente gli utenti di un altro file,
  **senza toccare** BDA e configurazione attuali:
  - utenti **nuovi** → aggiunti;
  - utenti già presenti **senza associazioni** → aggiornati automaticamente col file;
  - utenti già presenti **con associazioni** → ti viene chiesto, in un elenco con caselle,
    quali **sovrascrivere**; gli altri restano invariati.

> Suggerimento: dopo un'unione, se gli alimenti non risultano associati usa
> **Verifica / riassegna BDA**.

### Lavoro condiviso a due
Per dividere il lavoro su due computer senza confusione:
1. **Partite uguali**: uno carica la BDA e imposta le preferenze, poi esporta la
   **configurazione** e la manda all'altro; entrambi caricano la **stessa BDA** e usano la
   **stessa versione** dell'app.
2. **Dividete i soggetti** in due gruppi disgiunti: lo *stesso utente non si tocca su entrambi i PC*.
3. Ognuno lavora sui propri utenti (lo **stato a colori** e il **filtro** aiutano a seguire i progressi).
4. Alla fine, ognuno fa **Esporta progetto (utenti selezionati)** dei propri e lo invia; l'altro
   fa **Unisci utenti da progetto**: i nuovi utenti vengono aggiunti senza toccare il lavoro esistente.

### Export Excel del riepilogo (Esporta selezionati)
Genera un file con due fogli:
- **Dettaglio giorni**: una riga per utente×giorno con energia, nutrienti, percentuali e la
  ripartizione mNOVA (g, kcal, %Kcal/Kcaltot).
- **Media 4 giorni**: le stesse colonne mediate sui 4 giorni.

---

## 10. Backup e spostamento dati

- **Backup**: *File → Salva progetto* (file `.json.gz`); conserva/copia quel file. Per
  ripristinare, *File → Apri progetto*.
- **Nuovo computer**: installa l'app, poi apri il file di progetto (copiato o inviato).
- Ogni progetto è **autonomo** (include la BDA): per condividerlo basta il singolo file `.json.gz`.

---

## 11. Domande frequenti

**All'avvio l'app è vuota / mi chiede quale progetto aprire.**
È normale: il lavoro sta nei **file di progetto** (§9). Apri un progetto recente, sfoglia con
**Apri progetto…** oppure inizia con **Nuovo progetto vuoto**.

**Ho chiuso l'app: ho perso il lavoro?**
Alla chiusura l'app chiede di **salvare** se ci sono modifiche non salvate (titolo con `*`).
Se scegli «Non salvare» le modifiche vengono scartate. Salva sempre il progetto (Ctrl/⌘+S)
per conservarlo. In caso di chiusura anomala, al riavvio l'app propone di recuperare il lavoro.

**I valori nell'app e nell'Excel hanno decimali diversi.**
Regola **Preferenze → Decimali valori…**: vale sia per l'app sia per l'export.

**Una voce non entra nei calcoli.**
Probabilmente non è **associata** alla BDA (Stato «—») oppure non ha una **quantità in grammi**.

**Ho ricaricato la BDA e alcune voci sono «⚠».**
Usa **Verifica / riassegna BDA**: ricollega per Codice Alimento e segnala i casi da sistemare.
