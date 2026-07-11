// Accesso a Firestore per soggetti, voci di diario, etichette giorni.
import {
  collection,
  doc,
  addDoc,
  updateDoc,
  deleteDoc,
  getDocs,
  onSnapshot,
  query,
  orderBy,
  writeBatch,
  setDoc,
  increment,
  type Firestore,
} from "firebase/firestore";
import { db, TEAM_ID } from "./firebase";

export interface Subject {
  code: string;
  notes: string;
  total: number; // voci totali
  assoc: number; // voci con associazione BDA
}

export interface DiaryEntry {
  id?: string;
  userCode: string;
  day: number;
  meal: string;
  foodName: string;
  quantityG: number | null;
  bdaCode: string | null;
  nova: number | null;
  notes: string;
  ora: string;
  luogo: string;
  qtyRaw: string;
}

export interface DayMeta {
  code: string;
  day: number;
  dateLabel: string;
}

function requireDb(): Firestore {
  if (!db) throw new Error("Firestore non disponibile (config mancante).");
  return db;
}

export const subjectsCol = () =>
  collection(requireDb(), "teams", TEAM_ID, "subjects");
export const entriesCol = (code: string) =>
  collection(requireDb(), "teams", TEAM_ID, "subjects", code, "entries");
export const dayMetaCol = () =>
  collection(requireDb(), "teams", TEAM_ID, "dayMeta");

/** Ascolta la lista soggetti in tempo reale. Ritorna la funzione di unsubscribe. */
export function listenSubjects(cb: (subjects: Subject[]) => void): () => void {
  const q = query(subjectsCol(), orderBy("__name__"));
  return onSnapshot(q, (snap) => {
    cb(
      snap.docs.map((d) => {
        const data = d.data();
        return {
          code: d.id,
          notes: data.notes ?? "",
          total: data.total ?? 0,
          assoc: data.assoc ?? 0,
        };
      }),
    );
  });
}

/** Aggiorna i contatori (total/assoc) del soggetto in modo incrementale. */
async function bumpCounts(code: string, dTotal: number, dAssoc: number): Promise<void> {
  await setDoc(
    doc(subjectsCol(), code),
    { total: increment(dTotal), assoc: increment(dAssoc) },
    { merge: true },
  );
}

/** Ascolta le voci di un soggetto in tempo reale. */
export function listenEntries(
  code: string,
  cb: (entries: DiaryEntry[]) => void,
): () => void {
  return onSnapshot(entriesCol(code), (snap) => {
    cb(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<DiaryEntry, "id">) })));
  });
}

/** Legge una volta tutte le voci di un soggetto. */
export async function getEntries(code: string): Promise<DiaryEntry[]> {
  const snap = await getDocs(entriesCol(code));
  return snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<DiaryEntry, "id">) }));
}

/** Ascolta le preferenze del team (cutoff, formule, ecc.). */
export function listenConfig(cb: (config: Record<string, unknown>) => void): () => void {
  const ref = doc(requireDb(), "teams", TEAM_ID, "settings", "config");
  return onSnapshot(ref, (s) => cb(s.exists() ? (s.data() as Record<string, unknown>) : {}));
}

export async function addEntry(code: string, entry: Omit<DiaryEntry, "id">): Promise<void> {
  await addDoc(entriesCol(code), entry);
  await bumpCounts(code, 1, entry.bdaCode ? 1 : 0);
}
export async function updateEntry(
  code: string,
  id: string,
  patch: Partial<DiaryEntry>,
): Promise<void> {
  await updateDoc(doc(entriesCol(code), id), patch);
}
export async function deleteEntry(
  code: string,
  id: string,
  wasAssoc = false,
): Promise<void> {
  await deleteDoc(doc(entriesCol(code), id));
  await bumpCounts(code, -1, wasAssoc ? -1 : 0);
}
/** Associa/disassocia una voce, aggiornando i contatori. */
export async function setEntryBda(
  code: string,
  id: string,
  oldCode: string | null,
  newCode: string | null,
): Promise<void> {
  await updateDoc(doc(entriesCol(code), id), { bdaCode: newCode });
  const dAssoc = (newCode ? 1 : 0) - (oldCode ? 1 : 0);
  if (dAssoc !== 0) await bumpCounts(code, 0, dAssoc);
}
export async function addSubject(code: string, notes = ""): Promise<void> {
  await setDoc(doc(subjectsCol(), code), { notes });
}

export async function updateSubjectNotes(code: string, notes: string): Promise<void> {
  await setDoc(doc(subjectsCol(), code), { notes }, { merge: true });
}

/** Imposta i conteggi assoluti (usato per auto-correggere dati preesistenti). */
export async function setSubjectCounts(
  code: string,
  total: number,
  assoc: number,
): Promise<void> {
  await setDoc(doc(subjectsCol(), code), { total, assoc }, { merge: true });
}

/** Elimina un soggetto con tutte le sue voci ed etichette giorni. */
export async function deleteSubject(code: string): Promise<void> {
  const database = requireDb();
  const snap = await getDocs(entriesCol(code));
  await commitBatches(snap.docs.map((d) => (b: ReturnType<typeof writeBatch>) => b.delete(d.ref)));
  const batch = writeBatch(database);
  for (const day of [1, 2, 3, 4]) batch.delete(doc(dayMetaCol(), `${code}_${day}`));
  batch.delete(doc(subjectsCol(), code));
  await batch.commit();
}

export async function setConfig(config: Record<string, unknown>): Promise<void> {
  await setDoc(doc(requireDb(), "teams", TEAM_ID, "settings", "config"), config, {
    merge: true,
  });
}

async function commitBatches(ops: Array<(b: ReturnType<typeof writeBatch>) => void>) {
  const database = requireDb();
  for (let i = 0; i < ops.length; i += 400) {
    const batch = writeBatch(database);
    for (const fn of ops.slice(i, i + 400)) fn(batch);
    await batch.commit();
  }
}

export interface DiaryImport {
  subjects: Subject[];
  entries: DiaryEntry[];
  dayMeta: DayMeta[];
}

/**
 * Importa diari sostituendo il contenuto degli utenti presenti nel file.
 * Per ogni soggetto del file: crea/aggiorna il soggetto, cancella le sue voci
 * esistenti e reinserisce quelle importate (+ etichette giorni).
 * Gli altri soggetti non vengono toccati.
 */
export async function importDiaries(
  data: DiaryImport,
  onProgress?: (done: number, total: number) => void,
): Promise<void> {
  const database = requireDb();
  const byUser = new Map<string, DiaryEntry[]>();
  for (const e of data.entries) {
    if (!byUser.has(e.userCode)) byUser.set(e.userCode, []);
    byUser.get(e.userCode)!.push(e);
  }
  const metaByUser = new Map<string, DayMeta[]>();
  for (const m of data.dayMeta) {
    if (!metaByUser.has(m.code)) metaByUser.set(m.code, []);
    metaByUser.get(m.code)!.push(m);
  }

  let done = 0;
  const total = data.subjects.length;
  for (const s of data.subjects) {
    const subjEntries = byUser.get(s.code) ?? [];
    const assoc = subjEntries.filter((e) => e.bdaCode).length;
    await setDoc(doc(subjectsCol(), s.code), {
      notes: s.notes ?? "",
      total: subjEntries.length,
      assoc,
    });

    // Cancella le voci esistenti del soggetto.
    const existing = await getDocs(entriesCol(s.code));
    const delOps = existing.docs.map((d) => (b: ReturnType<typeof writeBatch>) => b.delete(d.ref));
    await commitBatches(delOps);

    // Inserisce voci + etichette giorni.
    const addOps: Array<(b: ReturnType<typeof writeBatch>) => void> = [];
    for (const e of byUser.get(s.code) ?? []) {
      const ref = doc(entriesCol(s.code));
      const { id: _omit, ...payload } = e;
      void _omit;
      addOps.push((b) => b.set(ref, payload));
    }
    for (const m of metaByUser.get(s.code) ?? []) {
      const ref = doc(dayMetaCol(), `${m.code}_${m.day}`);
      addOps.push((b) => b.set(ref, m));
    }
    await commitBatches(addOps);

    onProgress?.(++done, total);
  }
  void database;
}
