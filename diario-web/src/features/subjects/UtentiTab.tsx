import { useRef, useState } from "react";
import { useSubjects } from "./useSubjects";
import { parseContentExport } from "../diary/contentExport";
import { parseProjectFile } from "./projectImport";
import { ImportChoiceModal, type ImportAnalysis } from "./ImportChoiceModal";
import { saveBda } from "../bda/bdaStorage";
import type { Bda } from "../bda/bdaTypes";
import {
  importDiaries,
  addSubject,
  deleteSubject,
  updateSubjectNotes,
  setConfig,
  type DiaryImport,
} from "../../lib/db";

interface ImportExtra {
  config: Record<string, unknown> | null;
  bda: Bda | null;
}

export function UtentiTab() {
  const { subjects, loading } = useSubjects();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [pending, setPending] = useState<
    { data: DiaryImport; analysis: ImportAnalysis; extra?: ImportExtra } | null
  >(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const projRef = useRef<HTMLInputElement>(null);

  function classify(data: DiaryImport): ImportAnalysis {
    const local = new Map(subjects.map((s) => [s.code, s]));
    const analysis: ImportAnalysis = { newCodes: [], autoCodes: [], conflictCodes: [] };
    for (const s of data.subjects) {
      const l = local.get(s.code);
      if (!l) analysis.newCodes.push(s.code);
      else if ((l.assoc ?? 0) === 0) analysis.autoCodes.push(s.code);
      else analysis.conflictCodes.push(s.code);
    }
    return analysis;
  }

  async function handleProjectFile(file: File) {
    setBusy(true);
    setMsg(null);
    try {
      const proj = await parseProjectFile(file);
      if (!proj.diary.subjects.length && !proj.config && !proj.bda) {
        setMsg("Il file non contiene dati importabili.");
        return;
      }
      setPending({
        data: proj.diary,
        analysis: classify(proj.diary),
        extra: { config: proj.config, bda: proj.bda },
      });
    } catch (e: unknown) {
      setMsg("Errore: " + ((e as Error)?.message ?? "file non valido."));
    } finally {
      setBusy(false);
      if (projRef.current) projRef.current.value = "";
    }
  }

  async function handleFile(file: File) {
    setBusy(true);
    setMsg(null);
    try {
      const data = await parseContentExport(file);
      if (!data.subjects.length) {
        setMsg("Nessun utente valido trovato nel file.");
        return;
      }
      setPending({ data, analysis: classify(data) });
    } catch (e: unknown) {
      setMsg("Errore: " + ((e as Error)?.message ?? "impossibile leggere il file."));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function applyImport(overwriteConflicts: string[]) {
    if (!pending) return;
    const { data, analysis } = pending;
    setPending(null);
    const toWrite = new Set([...analysis.newCodes, ...analysis.autoCodes, ...overwriteConflicts]);
    const filtered: DiaryImport = {
      subjects: data.subjects.filter((s) => toWrite.has(s.code)),
      entries: data.entries.filter((e) => toWrite.has(e.userCode)),
      dayMeta: data.dayMeta.filter((m) => toWrite.has(m.code)),
    };
    setBusy(true);
    setProgress({ done: 0, total: filtered.subjects.length });
    try {
      await importDiaries(filtered, (done, total) => setProgress({ done, total }));
      if (pending.extra?.config) await setConfig(pending.extra.config);
      if (pending.extra?.bda) await saveBda(pending.extra.bda);
      const kept = analysis.conflictCodes.length - overwriteConflicts.length;
      const extras = [
        pending.extra?.config ? "configurazione" : "",
        pending.extra?.bda ? "BDA" : "",
      ].filter(Boolean);
      setMsg(
        `Aggiunti ${analysis.newCodes.length}, aggiornati ${
          analysis.autoCodes.length + overwriteConflicts.length
        }, mantenuti ${kept}.` + (extras.length ? ` Importate: ${extras.join(", ")}.` : ""),
      );
    } catch (e: unknown) {
      setMsg("Errore: " + ((e as Error)?.message ?? "import fallito."));
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }

  return (
    <div className="card">
      <div className="row between">
        <h2>Utenti {subjects.length ? `(${subjects.length})` : ""}</h2>
        <div className="row">
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void handleFile(f);
            }}
          />
          <button
            disabled={busy}
            onClick={() => {
              const c = window.prompt("Codice nuovo utente:");
              if (c && c.trim()) void addSubject(c.trim());
            }}
          >
            + Aggiungi utente
          </button>
          <button className="primary" disabled={busy} onClick={() => fileRef.current?.click()}>
            {busy ? "Importazione…" : "Importa Content Export"}
          </button>
          <input
            ref={projRef}
            type="file"
            accept=".json,.gz"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void handleProjectFile(f);
            }}
          />
          <button disabled={busy} onClick={() => projRef.current?.click()}>
            Importa progetto (.json.gz)
          </button>
        </div>
      </div>

      {progress && (
        <p className="muted">
          Importazione: {progress.done}/{progress.total} utenti…
        </p>
      )}
      {msg && <p className={msg.startsWith("Errore") ? "error" : "muted"}>{msg}</p>}

      {pending && (
        <ImportChoiceModal
          analysis={pending.analysis}
          totalEntries={pending.data.entries.length}
          onApply={(overwrite) => void applyImport(overwrite)}
          onClose={() => setPending(null)}
        />
      )}

      {loading ? (
        <p className="muted">Caricamento utenti…</p>
      ) : subjects.length === 0 ? (
        <p className="muted">
          Nessun utente. Usa «Importa Content Export» per caricare i diari (vengono
          salvati su Firestore e condivisi col team).
        </p>
      ) : (
        <div className="tablewrap" style={{ maxHeight: "60vh" }}>
          <table className="grid">
            <thead>
              <tr>
                <th>Codice utente</th>
                <th>Note</th>
                <th>Voci (assoc/tot)</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {subjects.map((s) => (
                <tr key={s.code}>
                  <td>{s.code}</td>
                  <td>
                    <input
                      className="cell"
                      style={{ width: "100%" }}
                      defaultValue={s.notes}
                      onBlur={(e) => {
                        if (e.target.value !== s.notes)
                          void updateSubjectNotes(s.code, e.target.value);
                      }}
                    />
                  </td>
                  <td className="muted">
                    {s.assoc}/{s.total}
                  </td>
                  <td>
                    <button
                      onClick={() => {
                        if (window.confirm(`Eliminare l'utente ${s.code} e tutto il suo diario?`))
                          void deleteSubject(s.code);
                      }}
                    >
                      🗑
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
