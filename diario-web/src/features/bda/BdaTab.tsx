import { useMemo, useRef, useState } from "react";
import Fuse from "fuse.js";
import { useBda } from "./useBda";
import { parseBdaWorkbook } from "./parseExcel";
import { saveBda } from "./bdaStorage";
import { categoryCode } from "../../lib/nutrition";
import type { CategoryRow } from "../../lib/nutrition";

const MAX_ROWS = 500;

export function BdaTab() {
  const { bda, loading, error, reload } = useBda();
  const [query, setQuery] = useState("");
  const [catCode, setCatCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const catMap = useMemo(() => {
    const m: Record<string, CategoryRow> = {};
    for (const c of bda?.categories ?? []) m[c.code] = c;
    return m;
  }, [bda]);

  const subCats = useMemo(
    () =>
      (bda?.categories ?? [])
        .filter((c) => c.macro_code !== c.code)
        .sort((a, b) => (a.name_it ?? "").localeCompare(b.name_it ?? "")),
    [bda],
  );

  const fuse = useMemo(
    () =>
      bda
        ? new Fuse(bda.foods, { keys: ["name"], threshold: 0.35, ignoreLocation: true })
        : null,
    [bda],
  );

  const results = useMemo(() => {
    if (!bda) return [];
    let list =
      query.trim() && fuse ? fuse.search(query).map((r) => r.item) : bda.foods;
    if (catCode) {
      list = list.filter(
        (f) => categoryCode(f.data["Categoria Merceologica"]) === catCode,
      );
    }
    return list;
  }, [bda, fuse, query, catCode]);

  async function handleFile(file: File) {
    setBusy(true);
    setMsg(null);
    try {
      const parsed = await parseBdaWorkbook(file);
      await saveBda(parsed);
      setMsg(
        `BDA aggiornata: ${parsed.foods.length} alimenti, ${parsed.categories.length} categorie.`,
      );
      await reload();
    } catch (e: unknown) {
      setMsg("Errore: " + ((e as Error)?.message ?? "impossibile leggere il file."));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="card">
      <div className="row between">
        <h2>Banca Dati Alimenti</h2>
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
            className="primary"
            disabled={busy}
            onClick={() => fileRef.current?.click()}
          >
            {busy ? "Caricamento…" : "Carica BDA da Excel"}
          </button>
        </div>
      </div>

      {msg && <p className={msg.startsWith("Errore") ? "error" : "muted"}>{msg}</p>}
      {error && <p className="error">{error}</p>}

      {loading ? (
        <p className="muted">Caricamento BDA…</p>
      ) : !bda ? (
        <p className="muted">
          Nessuna BDA caricata. Usa «Carica BDA da Excel» per importarla (viene
          salvata su Firebase Storage e condivisa con tutto il team).
        </p>
      ) : (
        <>
          <div className="row search">
            <input
              placeholder="Cerca alimento…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select value={catCode} onChange={(e) => setCatCode(e.target.value)}>
              <option value="">Tutte le categorie</option>
              {subCats.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name_it || c.code}
                </option>
              ))}
            </select>
          </div>

          <p className="muted small">
            {results.length} alimenti
            {results.length > MAX_ROWS ? ` (mostrati i primi ${MAX_ROWS})` : ""}
          </p>

          <div className="tablewrap">
            <table className="grid">
              <thead>
                <tr>
                  <th>Alimento</th>
                  <th>Categoria</th>
                  <th>Codice</th>
                </tr>
              </thead>
              <tbody>
                {results.slice(0, MAX_ROWS).map((f) => {
                  const cc = categoryCode(f.data["Categoria Merceologica"]);
                  return (
                    <tr key={f.id}>
                      <td>{f.name}</td>
                      <td>{catMap[cc]?.name_it ?? ""}</td>
                      <td className="muted">{f.code ?? ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
