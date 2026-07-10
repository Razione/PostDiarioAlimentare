import { useMemo, useState } from "react";
import Fuse from "fuse.js";
import type { Bda } from "../bda/bdaTypes";

/** Modale di ricerca alimento BDA. onPick(code) associa, onPick(null) rimuove. */
export function BdaPicker({
  bda,
  onPick,
  onClose,
}: {
  bda: Bda;
  onPick: (code: string | null) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const fuse = useMemo(
    () => new Fuse(bda.foods, { keys: ["name"], threshold: 0.35, ignoreLocation: true }),
    [bda],
  );
  const results = useMemo(
    () => (query.trim() ? fuse.search(query).slice(0, 200).map((r) => r.item) : bda.foods.slice(0, 200)),
    [query, fuse, bda],
  );

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="row between">
          <h3>Cerca alimento BDA</h3>
          <button onClick={onClose}>✕</button>
        </div>
        <input
          autoFocus
          placeholder="Cerca alimento…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="tablewrap" style={{ maxHeight: "50vh", marginTop: 8 }}>
          <table className="grid">
            <tbody>
              {results.map((f) => (
                <tr
                  key={f.id}
                  className="clickable"
                  onClick={() => f.code && onPick(f.code)}
                >
                  <td>{f.name}</td>
                  <td className="muted">{f.code}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="row between" style={{ marginTop: 8 }}>
          <button onClick={() => onPick(null)}>Rimuovi associazione</button>
          <button onClick={onClose}>Annulla</button>
        </div>
      </div>
    </div>
  );
}
