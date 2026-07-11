import { useEffect, useMemo, useRef, useState } from "react";
import { listenConfig, setConfig } from "../../lib/db";
import { useBda } from "../bda/useBda";
import {
  cutoffOptions,
  evalFormula,
  SKIP_BDA_COLS,
  DEFAULT_FORMULA,
  type CategoryRow,
} from "../../lib/nutrition";

const JSON_KEYS = new Set([
  "mnova_cutoffs",
  "nutri_formulas",
  "percent_config",
  "special_values",
  "beverage_categories",
]);
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
    } else out[k] = v;
  }
  return out;
}

export function PreferenzeTab() {
  const [config, setLocalConfig] = useState<Record<string, unknown>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const { bda } = useBda();
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

  async function importFile(file: File) {
    setMsg(null);
    try {
      const data = JSON.parse(await file.text());
      const settings = data?.settings ?? data;
      if (!settings || typeof settings !== "object") {
        setMsg("Errore: il file non contiene una configurazione.");
        return;
      }
      await setConfig(normalize(settings as Record<string, unknown>));
      setMsg("Configurazione importata.");
    } catch (e: unknown) {
      setMsg("Errore: " + ((e as Error)?.message ?? "file non valido."));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const nutrientCols = useMemo(
    () => (bda?.columns ?? []).filter((c) => !SKIP_BDA_COLS.has(c)),
    [bda],
  );

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
              if (f) void importFile(f);
            }}
          />
          <button onClick={() => fileRef.current?.click()}>Importa configurazione</button>
        </div>
      </div>
      {msg && <p className={msg.startsWith("Errore") ? "error" : "muted"}>{msg}</p>}
      {!bda && (
        <p className="muted small">
          Alcune sezioni (cutoff, bevande, percentuali, formule) usano le colonne/categorie
          della BDA: carica prima la BDA.
        </p>
      )}

      <DecimalsSection config={config} />
      <CutoffSection config={config} columns={bda?.columns ?? []} />
      <BeveragesSection config={config} categories={bda?.categories ?? []} />
      <PercentSection config={config} nutrientCols={nutrientCols} />
      <SpecialSection config={config} />
      <FormulaSection config={config} nutrientCols={nutrientCols} />
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginTop: 20, borderTop: "1px solid #eef0f2", paddingTop: 12 }}>
      <h3>{title}</h3>
      {children}
    </section>
  );
}

/* ── Decimali ─────────────────────────────────────────────── */
function DecimalsSection({ config }: { config: Record<string, unknown> }) {
  const current = Number(config["display_decimals"] ?? 2) || 2;
  const [n, setN] = useState(current);
  useEffect(() => setN(current), [current]);
  return (
    <Section title="Decimali valori">
      <div className="row" style={{ gap: 8 }}>
        <input
          type="number"
          min={0}
          max={6}
          value={n}
          style={{ width: 80 }}
          onChange={(e) => setN(Number(e.target.value))}
        />
        <button className="primary" onClick={() => void setConfig({ display_decimals: n })}>
          Salva
        </button>
      </div>
    </Section>
  );
}

/* ── Cutoff mNOVA ─────────────────────────────────────────── */
interface Cutoff {
  col: string;
  threshold: number;
}
function CutoffSection({ config, columns }: { config: Record<string, unknown>; columns: string[] }) {
  const opts = useMemo(() => cutoffOptions(columns), [columns]);
  const raw = config["mnova_cutoffs"];
  const foodMap = useMemo(() => toMap(Array.isArray(raw) ? raw : (raw as { food?: Cutoff[] })?.food), [raw]);
  const bevMap = useMemo(() => toMap((raw as { beverage?: Cutoff[] })?.beverage), [raw]);
  const [food, setFood] = useState<Record<string, string>>({});
  const [bev, setBev] = useState<Record<string, string>>({});
  useEffect(() => {
    const toStr = (m: Record<string, number>) =>
      Object.fromEntries(opts.map((o) => [o, o in m ? String(m[o]) : ""]));
    setFood(toStr(foodMap));
    setBev(toStr(bevMap));
  }, [opts, foodMap, bevMap]);

  function save() {
    const build = (m: Record<string, string>): Cutoff[] =>
      opts
        .filter((o) => m[o]?.toString().trim() !== "")
        .map((o) => ({ col: o, threshold: Number(m[o].toString().replace(",", ".")) }))
        .filter((c) => !Number.isNaN(c.threshold));
    void setConfig({ mnova_cutoffs: { food: build(food), beverage: build(bev) } });
  }

  return (
    <Section title="Cutoff mNOVA (cibo / bevanda)">
      <p className="muted small">
        NOVA 3/4 → «b» se un nutriente supera la soglia (per 100 g), altrimenti «a». Soglia
        vuota = disattivata. «Sale (g)» = Sodio × 2,5/1000.
      </p>
      {opts.length === 0 ? (
        <p className="muted">Carica la BDA per vedere i nutrienti-cutoff.</p>
      ) : (
        <table className="grid" style={{ maxWidth: 560 }}>
          <thead>
            <tr>
              <th>Nutriente</th>
              <th>Soglia cibo</th>
              <th>Soglia bevanda</th>
            </tr>
          </thead>
          <tbody>
            {opts.map((o) => (
              <tr key={o}>
                <td>{o}</td>
                <td>
                  <input
                    className="cell"
                    value={food[o] ?? ""}
                    onChange={(e) => setFood((s) => ({ ...s, [o]: e.target.value }))}
                  />
                </td>
                <td>
                  <input
                    className="cell"
                    value={bev[o] ?? ""}
                    onChange={(e) => setBev((s) => ({ ...s, [o]: e.target.value }))}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <button className="primary" style={{ marginTop: 8 }} onClick={save}>
        Salva cutoff
      </button>
    </Section>
  );
}
function toMap(list?: Cutoff[]): Record<string, number> {
  const m: Record<string, number> = {};
  for (const c of list ?? []) if (c?.col) m[c.col] = c.threshold;
  return m;
}

/* ── Bevande ──────────────────────────────────────────────── */
function BeveragesSection({
  config,
  categories,
}: {
  config: Record<string, unknown>;
  categories: CategoryRow[];
}) {
  const subs = useMemo(
    () =>
      categories
        .filter((c) => c.macro_code !== c.code)
        .sort((a, b) => (a.name_it ?? "").localeCompare(b.name_it ?? "")),
    [categories],
  );
  const saved = useMemo(
    () => new Set(((config["beverage_categories"] as Array<string | number>) ?? []).map(String)),
    [config],
  );
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [q, setQ] = useState("");
  useEffect(() => setChecked(new Set(saved)), [saved]);

  const shown = q.trim()
    ? subs.filter((c) => (c.name_it ?? "").toLowerCase().includes(q.toLowerCase()) || c.code.includes(q))
    : subs;

  return (
    <Section title="Bevande (categorie)">
      <p className="muted small">Le categorie marcate come bevande usano i cutoff «bevanda».</p>
      {subs.length === 0 ? (
        <p className="muted">Carica una BDA con le categorie merceologiche.</p>
      ) : (
        <>
          <input
            placeholder="Filtra categoria…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ marginBottom: 6, padding: "6px 8px", border: "1px solid #d1d5db", borderRadius: 8 }}
          />
          <div className="tablewrap" style={{ maxHeight: "35vh" }}>
            <table className="grid">
              <tbody>
                {shown.map((c) => (
                  <tr
                    key={c.code}
                    className="clickable"
                    onClick={() =>
                      setChecked((s) => {
                        const n = new Set(s);
                        n.has(c.code) ? n.delete(c.code) : n.add(c.code);
                        return n;
                      })
                    }
                  >
                    <td style={{ width: 30 }}>
                      <input type="checkbox" readOnly checked={checked.has(c.code)} />
                    </td>
                    <td>{c.name_it || c.code}</td>
                    <td className="muted">[{c.code}]</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <button
        className="primary"
        style={{ marginTop: 8 }}
        onClick={() => void setConfig({ beverage_categories: [...checked] })}
      >
        Salva bevande
      </button>
    </Section>
  );
}

/* ── Percentuali ──────────────────────────────────────────── */
interface PercentTerm {
  col: string;
  factor: number;
  denom?: string;
}
function PercentSection({
  config,
  nutrientCols,
}: {
  config: Record<string, unknown>;
  nutrientCols: string[];
}) {
  const saved = useMemo(() => (config["percent_config"] as PercentTerm[]) ?? [], [config]);
  const [rows, setRows] = useState<PercentTerm[]>([]);
  useEffect(() => setRows(saved), [saved]);

  const upd = (i: number, patch: Partial<PercentTerm>) =>
    setRows((r) => r.map((x, j) => (j === i ? { ...x, ...patch } : x)));

  return (
    <Section title="Percentuali">
      <p className="muted small">
        % = valore × fattore / denominatore × 100 (denominatore vuoto = energia del giorno).
      </p>
      <table className="grid" style={{ maxWidth: 640 }}>
        <thead>
          <tr>
            <th>Nutriente</th>
            <th>Fattore</th>
            <th>Denominatore</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>
                <select value={r.col} onChange={(e) => upd(i, { col: e.target.value })}>
                  <option value="">—</option>
                  {nutrientCols.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </td>
              <td>
                <input
                  className="cell"
                  value={r.factor ?? ""}
                  onChange={(e) => upd(i, { factor: Number(e.target.value.replace(",", ".")) })}
                />
              </td>
              <td>
                <select value={r.denom ?? ""} onChange={(e) => upd(i, { denom: e.target.value })}>
                  <option value="">Energia totale</option>
                  {nutrientCols.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </td>
              <td>
                <button onClick={() => setRows((rr) => rr.filter((_, j) => j !== i))}>🗑</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="row" style={{ gap: 8, marginTop: 8 }}>
        <button onClick={() => setRows((r) => [...r, { col: "", factor: 0, denom: "" }])}>
          + Aggiungi
        </button>
        <button
          className="primary"
          onClick={() =>
            void setConfig({
              percent_config: rows.filter((r) => r.col && !Number.isNaN(r.factor)),
            })
          }
        >
          Salva percentuali
        </button>
      </div>
    </Section>
  );
}

/* ── Valori speciali ──────────────────────────────────────── */
function SpecialSection({ config }: { config: Record<string, unknown> }) {
  const saved = (config["special_values"] as Record<string, { value?: number; desc?: string }>) ?? {};
  const [v2, setV2] = useState("0");
  const [v3, setV3] = useState("0");
  useEffect(() => {
    setV2(String(saved["-2"]?.value ?? 0));
    setV3(String(saved["-3"]?.value ?? 0));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config]);
  return (
    <Section title="Valori speciali (-2 tracce / -3 mancante)">
      <div className="form" style={{ maxWidth: 320 }}>
        <label>
          -2 (tracce) → valore sostitutivo
          <input value={v2} onChange={(e) => setV2(e.target.value)} />
        </label>
        <label>
          -3 (mancante) → valore sostitutivo
          <input value={v3} onChange={(e) => setV3(e.target.value)} />
        </label>
      </div>
      <button
        className="primary"
        style={{ marginTop: 8 }}
        onClick={() =>
          void setConfig({
            special_values: {
              "-2": { value: Number(v2.replace(",", ".")) || 0, desc: "Tracce" },
              "-3": { value: Number(v3.replace(",", ".")) || 0, desc: "Missing" },
            },
          })
        }
      >
        Salva valori speciali
      </button>
    </Section>
  );
}

/* ── Formule ──────────────────────────────────────────────── */
function FormulaSection({
  config,
  nutrientCols,
}: {
  config: Record<string, unknown>;
  nutrientCols: string[];
}) {
  const saved = useMemo(
    () => (config["nutri_formulas"] as Record<string, string>) ?? {},
    [config],
  );
  const [formulas, setFormulas] = useState<Record<string, string>>({});
  const [q, setQ] = useState("");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setFormulas(Object.fromEntries(nutrientCols.map((c) => [c, saved[c] ?? DEFAULT_FORMULA])));
  }, [nutrientCols, saved]);

  const shown = q.trim() ? nutrientCols.filter((c) => c.toLowerCase().includes(q.toLowerCase())) : nutrientCols;

  function save() {
    const out: Record<string, string> = {};
    for (const c of nutrientCols) {
      const f = (formulas[c] ?? DEFAULT_FORMULA).trim() || DEFAULT_FORMULA;
      if (evalFormula(f, 1, 100) === null) {
        setErr(`Formula non valida per «${c}»`);
        return;
      }
      if (f !== DEFAULT_FORMULA) out[c] = f;
    }
    setErr(null);
    void setConfig({ nutri_formulas: out });
  }

  return (
    <Section title="Formula nutrizionale">
      <p className="muted small">
        Variabili: <b>val</b> (per 100 g) · <b>qty</b> (grammi). Default:{" "}
        <code>{DEFAULT_FORMULA}</code>.
      </p>
      {err && <p className="error">{err}</p>}
      <input
        placeholder="Filtra nutriente…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        style={{ marginBottom: 6, padding: "6px 8px", border: "1px solid #d1d5db", borderRadius: 8 }}
      />
      <div className="tablewrap" style={{ maxHeight: "40vh" }}>
        <table className="grid">
          <thead>
            <tr>
              <th>Nutriente</th>
              <th>Formula</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((c) => (
              <tr key={c}>
                <td>{c}</td>
                <td>
                  <input
                    className="cell"
                    style={{ width: "100%" }}
                    value={formulas[c] ?? ""}
                    onChange={(e) => setFormulas((s) => ({ ...s, [c]: e.target.value }))}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button className="primary" style={{ marginTop: 8 }} onClick={save}>
        Salva formule
      </button>
    </Section>
  );
}
