import { useEffect, useRef, useState } from "react";
import { listenConfig, setConfig } from "../../lib/db";

// Chiavi le cui preferenze sono JSON serializzato nel file del desktop.
const JSON_KEYS = new Set([
  "mnova_cutoffs",
  "nutri_formulas",
  "percent_config",
  "special_values",
  "beverage_categories",
]);
// Preferenze desktop-only da non importare.
const SKIP_KEYS = new Set(["ui_font_pt", "table_font_pt", "bda_path"]);

function normalize(settings: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(settings)) {
    if (SKIP_KEYS.has(k)) continue;
    if (JSON_KEYS.has(k) && typeof v === "string") {
      try {
        out[k] = JSON.parse(v);
      } catch {
        out[k] = v;
      }
    } else {
      out[k] = v;
    }
  }
  return out;
}

export function PreferenzeTab() {
  const [config, setLocalConfig] = useState<Record<string, unknown>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let unsub = () => {};
    try {
      unsub = listenConfig(setLocalConfig);
    } catch {
      /* config non disponibile */
    }
    return () => unsub();
  }, []);

  async function handleFile(file: File) {
    setBusy(true);
    setMsg(null);
    try {
      const data = JSON.parse(await file.text());
      const settings = data?.settings ?? data;
      if (!settings || typeof settings !== "object") {
        setMsg("Errore: il file non contiene una configurazione.");
        return;
      }
      const cfg = normalize(settings as Record<string, unknown>);
      await setConfig(cfg);
      setMsg(`Configurazione importata: ${Object.keys(cfg).length} preferenze.`);
    } catch (e: unknown) {
      setMsg("Errore: " + ((e as Error)?.message ?? "file non valido."));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const keys = Object.keys(config).sort();

  return (
    <div className="card">
      <div className="row between">
        <h2>Preferenze</h2>
        <div className="row">
          <input
            ref={fileRef}
            type="file"
            accept=".json,.gz"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void handleFile(f);
            }}
          />
          <button className="primary" disabled={busy} onClick={() => fileRef.current?.click()}>
            {busy ? "Importazione…" : "Importa configurazione"}
          </button>
        </div>
      </div>

      {msg && <p className={msg.startsWith("Errore") ? "error" : "muted"}>{msg}</p>}

      <p className="muted small">
        Importa il file <code>.json</code> esportato dal desktop (menu File →
        Esporta configurazione): cutoff mNOVA, formule, percentuali, valori
        speciali, categorie bevanda, decimali. L'editor completo delle preferenze
        arriverà (Fase 5).
      </p>

      <h3>Configurazione attuale del team</h3>
      {keys.length === 0 ? (
        <p className="muted">Nessuna preferenza impostata.</p>
      ) : (
        <div className="tablewrap" style={{ maxHeight: "45vh" }}>
          <table className="grid">
            <thead>
              <tr>
                <th>Chiave</th>
                <th>Valore</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k}>
                  <td>{k}</td>
                  <td className="muted" style={{ maxWidth: 520, overflow: "hidden", textOverflow: "ellipsis" }}>
                    {JSON.stringify(config[k])}
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
