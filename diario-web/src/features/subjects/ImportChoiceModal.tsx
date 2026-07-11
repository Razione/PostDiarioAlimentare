import { useState } from "react";

export interface ImportAnalysis {
  newCodes: string[];
  autoCodes: string[]; // presenti senza associazioni → aggiornati
  conflictCodes: string[]; // presenti e già associati → richiedono conferma
}

/**
 * Scelta all'import: «Sostituisci tutto» sovrascrive anche gli utenti già
 * associati; «Unisci» sovrascrive solo i conflitti selezionati.
 * onApply riceve l'elenco dei conflitti da sovrascrivere.
 */
export function ImportChoiceModal({
  analysis,
  totalEntries,
  onApply,
  onClose,
}: {
  analysis: ImportAnalysis;
  totalEntries: number;
  onApply: (overwriteConflicts: string[]) => void;
  onClose: () => void;
}) {
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const toggle = (c: string) =>
    setChecked((s) => {
      const n = new Set(s);
      n.has(c) ? n.delete(c) : n.add(c);
      return n;
    });
  const setAll = (on: boolean) =>
    setChecked(on ? new Set(analysis.conflictCodes) : new Set());

  const { newCodes, autoCodes, conflictCodes } = analysis;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="row between">
          <h3>Importa Content Export</h3>
          <button onClick={onClose}>✕</button>
        </div>
        <p className="muted">
          {newCodes.length + autoCodes.length + conflictCodes.length} utenti,{" "}
          {totalEntries} voci nel file.
          <br />
          <b>{newCodes.length}</b> nuovi (aggiunti) · <b>{autoCodes.length}</b> senza
          associazioni (aggiornati) · <b>{conflictCodes.length}</b> già associati.
        </p>

        {conflictCodes.length > 0 && (
          <>
            <p className="small">
              Utenti già associati: spunta quelli da <b>sovrascrivere</b> (gli altri
              restano invariati).
            </p>
            <div className="row" style={{ gap: 6, marginBottom: 6 }}>
              <button onClick={() => setAll(true)}>Seleziona tutti</button>
              <button onClick={() => setAll(false)}>Deseleziona tutti</button>
            </div>
            <div className="tablewrap" style={{ maxHeight: "35vh" }}>
              <table className="grid">
                <tbody>
                  {conflictCodes.map((c) => (
                    <tr key={c} className="clickable" onClick={() => toggle(c)}>
                      <td style={{ width: 30 }}>
                        <input type="checkbox" readOnly checked={checked.has(c)} />
                      </td>
                      <td>{c}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        <div className="row between" style={{ marginTop: 12 }}>
          <button onClick={onClose}>Annulla</button>
          <div className="row" style={{ gap: 8 }}>
            {conflictCodes.length > 0 && (
              <button onClick={() => onApply([...checked])}>Unisci</button>
            )}
            <button className="primary" onClick={() => onApply(conflictCodes)}>
              {conflictCodes.length > 0 ? "Sostituisci tutto" : "Importa"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
