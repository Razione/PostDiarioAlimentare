// Accesso a Firestore per soggetti, voci di diario, etichette giorni.
import {
  collection,
  doc,
  getDocs,
  onSnapshot,
  query,
  orderBy,
  writeBatch,
  setDoc,
  type Firestore,
} from "firebase/firestore";
import { db, TEAM_ID } from "./firebase";

export interface Subject {
  code: string;
  notes: string;
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
    cb(snap.docs.map((d) => ({ code: d.id, notes: d.data().notes ?? "" })));
  });
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
    await setDoc(doc(subjectsCol(), s.code), { notes: s.notes ?? "" });

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
