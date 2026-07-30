import { useMemo, useRef, useState } from "react";
import Fuse from "fuse.js";
import { useBda } from "./useBda";
import { parseBdaWorkbook } from "./parseExcel";
import { mergeBda } from "./mergeBda";
import { saveBda } from "./bdaStorage";
import { usersWithBda } from "../../lib/db";
import { categoryCode } from "../../lib/nutrition";
import type { BdaFood, CategoryRow } from "../../lib/nutrition";

const MAX_ROWS = 500;

export function BdaTab() {
  const { bda, loading, error, reload } = useBda();
  const [query, setQuery] = useState("");
  const [catCode, setCatCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [selected, setSelected] = useState<BdaFood | null>(null);
  const [usersResult, setUsersResult] = useState<
    { name: string; users: Array<{ code: string; count: number }> } | null
  >(null);
  const [searchingUsers, setSearchingUsers] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const addRef = useRef<HTMLInputElement>(null);

  async function findUsers() {
    if (!selected?.code) return;
    setSearchingUsers(true);
    try {
      const users = await usersWithBda(selected.code);
      setUsersResult({ name: selected.name, users });
    } catch (e: unknown) {
      setMsg("Errore ricerca utenti: " + ((e as Error)?.message ?? ""));
    } finally {
      setSearchingUsers(false);
    }
  }

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

  async function processFile(file: File, mode: "replace" | "add") {
    setBusy(true);
    setMsg(null);
    try {
      const parsed = await parseBdaWorkbook(file);
      const toSave = mode === "add" ? mergeBda(bda, parsed) : parsed;
      await saveBda(toSave);
      setMsg(
        `BDA ${mode === "add" ? "aggiornata (alimenti uniti)" : "sostituita"}: ` +
          `${toSave.foods.length} alimenti, ${toSave.categories.length} categorie.`,
      );
      await reload();
    } catch (e: unknown) {
      setMsg("Errore: " + ((e as Error)?.message ?? "impossibile leggere il file."));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
      if (addRef.current) addRef.current.value = "";
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
              if (f) void processFile(f, "replace");
            }}
          />
          <input
            ref={addRef}
            type="file"
            accept=".xlsx,.xls"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void processFile(f, "add");
            }}
          />
          {bda && (
            <button disabled={!selected || searchingUsers} onClick={() => void findUsers()}>
              {searchingUsers ? "Ricerca…" : "Utenti con questo alimento"}
            </button>
          )}
          {bda && (
            <button disabled={busy} onClick={() => addRef.current?.click()}>
              Aggiungi da Excel
            </button>
          )}
          <button
            className="primary"
            disabled={busy}
            onClick={() => {
              if (
                !bda ||
                window.confirm(
                  "Sostituire completamente la BDA esistente? (per unire due BDA usa «Aggiungi da Excel»)",
                )
              )
                fileRef.current?.click();
            }}
          >
            {busy ? "Caricamento…" : bda ? "Sostituisci BDA" : "Carica BDA da Excel"}
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
            {selected ? ` · selezionato: ${selected.name}` : " · (clicca una riga per selezionare)"}
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
                    <tr
                      key={f.id}
                      className={selected?.id === f.id ? "clickable rowsel" : "clickable"}
                      onClick={() => setSelected(f)}
                    >
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

      {usersResult && (
        <div className="modal-backdrop" onClick={() => setUsersResult(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="row between">
              <h3>Utenti con «{usersResult.name}»</h3>
              <button onClick={() => setUsersResult(null)}>✕</button>
            </div>
            {usersResult.users.length === 0 ? (
              <p className="muted">Nessun utente ha questo alimento associato.</p>
            ) : (
              <>
                <p className="muted small">{usersResult.users.length} utenti.</p>
                <div className="tablewrap" style={{ maxHeight: "55vh" }}>
                  <table className="grid">
                    <thead>
                      <tr>
                        <th>Utente</th>
                        <th>Voci</th>
                      </tr>
                    </thead>
                    <tbody>
                      {usersResult.users.map((u) => (
                        <tr key={u.code}>
                          <td>{u.code}</td>
                          <td className="muted">{u.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
            <div className="row between" style={{ marginTop: 8 }}>
              <span />
              <button className="primary" onClick={() => setUsersResult(null)}>Chiudi</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
