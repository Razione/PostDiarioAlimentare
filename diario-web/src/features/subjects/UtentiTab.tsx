import { useRef, useState } from "react";
import { useSubjects } from "./useSubjects";
import { parseContentExport } from "../diary/contentExport";
import {
  importDiaries,
  addSubject,
  deleteSubject,
  updateSubjectNotes,
} from "../../lib/db";

export function UtentiTab() {
  const { subjects, loading } = useSubjects();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setBusy(true);
    setMsg(null);
    setProgress(null);
    try {
      const data = await parseContentExport(file);
      if (!data.subjects.length) {
        setMsg("Nessun utente valido trovato nel file.");
        return;
      }
      const ok = window.confirm(
        `Importare ${data.subjects.length} utenti e ${data.entries.length} voci?\n` +
          "Il diario degli utenti presenti nel file verrà sostituito; gli altri restano invariati.",
      );
      if (!ok) return;
      await importDiaries(data, (done, total) => setProgress({ done, total }));
      setMsg(`Importati ${data.subjects.length} utenti e ${data.entries.length} voci.`);
    } catch (e: unknown) {
      setMsg("Errore: " + ((e as Error)?.message ?? "impossibile importare il file."));
    } finally {
      setBusy(false);
      setProgress(null);
      if (fileRef.current) fileRef.current.value = "";
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
        </div>
      </div>

      {progress && (
        <p className="muted">
          Importazione: {progress.done}/{progress.total} utenti…
        </p>
      )}
      {msg && <p className={msg.startsWith("Errore") ? "error" : "muted"}>{msg}</p>}

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
