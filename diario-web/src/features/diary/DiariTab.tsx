import { useEffect, useMemo, useState } from "react";
import { useSubjects } from "../subjects/useSubjects";
import { useBda } from "../bda/useBda";
import { useEntries } from "./useEntries";
import {
  addEntry,
  updateEntry,
  deleteEntry,
  setEntryBda,
  listenConfig,
  type DiaryEntry,
  type Subject,
} from "../../lib/db";
import { BdaPicker } from "./BdaPicker";
import { EntryEditModal } from "./EntryEditModal";
import { FoodNutrientsModal } from "./FoodNutrientsModal";
import { Summary } from "../summary/Summary";
import { exportSummaryXlsx } from "../export/exportExcel";
import {
  MEALS,
  DAYS,
  SKIP_BDA_COLS,
  buildMnovaConfig,
  computeMnova,
  type BdaData,
  type BdaFood,
  type CategoryRow,
} from "../../lib/nutrition";

type StatusClass = "none" | "partial" | "full";

function statusOf(s: Subject): StatusClass {
  if (s.total === 0 || s.assoc === 0) return "none";
  return s.assoc < s.total ? "partial" : "full";
}
const STATUS_COLOR: Record<StatusClass, string> = {
  none: "inherit",
  partial: "#b8860b",
  full: "#2e7d32",
};

export function DiariTab() {
  const { subjects } = useSubjects();
  const { bda } = useBda();
  const [code, setCode] = useState<string | null>(null);
  const [day, setDay] = useState(1);
  const [showSummary, setShowSummary] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | StatusClass>("");
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [pickerFor, setPickerFor] = useState<string | null>(null);
  const [editEntry, setEditEntry] = useState<DiaryEntry | null>(null);
  const [nutrientsEntry, setNutrientsEntry] = useState<DiaryEntry | null>(null);
  const [exporting, setExporting] = useState<{ done: number; total: number } | null>(null);

  useEffect(() => {
    let unsub = () => {};
    try {
      unsub = listenConfig(setConfig);
    } catch {
      /* config non disponibile */
    }
    return () => unsub();
  }, []);

  const entries = useEntries(code);

  const bdaByCode = useMemo(() => {
    const m = new Map<string, BdaFood>();
    for (const f of bda?.foods ?? []) if (f.code) m.set(f.code, f);
    return m;
  }, [bda]);

  const mnovaConfig = useMemo(() => {
    const cats: Record<string, CategoryRow> = {};
    for (const c of bda?.categories ?? []) cats[c.code] = c;
    return buildMnovaConfig(
      config["mnova_cutoffs"],
      (config["beverage_categories"] as Array<string | number>) ?? [],
      cats,
    );
  }, [config, bda]);

  const resolve = useMemo(
    () => (c: string): BdaData | null => bdaByCode.get(c)?.data ?? null,
    [bdaByCode],
  );
  const nutrientCols = useMemo(
    () => (bda?.columns ?? []).filter((c) => !SKIP_BDA_COLS.has(c)),
    [bda],
  );

  const dayEntries = useMemo(
    () =>
      entries
        .filter((e) => e.day === day)
        .sort(
          (a, b) =>
            MEALS.indexOf(a.meal as (typeof MEALS)[number]) -
            MEALS.indexOf(b.meal as (typeof MEALS)[number]),
        ),
    [entries, day],
  );

  const filteredSubjects = useMemo(() => {
    const q = search.trim().toLowerCase();
    return subjects.filter(
      (s) =>
        (!q || s.code.toLowerCase().includes(q)) &&
        (!statusFilter || statusOf(s) === statusFilter),
    );
  }, [subjects, search, statusFilter]);

  async function pick(entry: DiaryEntry, bdaCode: string | null) {
    if (code && entry.id) await setEntryBda(code, entry.id, entry.bdaCode, bdaCode);
    setPickerFor(null);
  }

  const pickerTarget = pickerFor ? dayEntries.find((x) => x.id === pickerFor) : undefined;

  async function doExport() {
    if (!bda) return;
    setExporting({ done: 0, total: subjects.length });
    try {
      await exportSummaryXlsx(subjects, resolve, nutrientCols, mnovaConfig, config, (done, total) =>
        setExporting({ done, total }),
      );
    } catch (e: unknown) {
      window.alert("Errore export: " + ((e as Error)?.message ?? ""));
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="diari">
      <aside className="subjects card">
        <input
          placeholder="Cerca utente…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as "" | StatusClass)}
        >
          <option value="">Tutti gli stati</option>
          <option value="none">Da fare</option>
          <option value="partial">In corso</option>
          <option value="full">Completati</option>
        </select>
        <div className="subjlist">
          {filteredSubjects.map((s) => (
            <div
              key={s.code}
              className={s.code === code ? "subj active" : "subj"}
              style={{ color: STATUS_COLOR[statusOf(s)] }}
              title={`Associate: ${s.assoc}/${s.total}`}
              onClick={() => setCode(s.code)}
            >
              {s.code}
            </div>
          ))}
        </div>
        <div className="legend small">
          <span style={{ color: STATUS_COLOR.full }}>■ fatti</span>{" "}
          <span style={{ color: STATUS_COLOR.partial }}>■ in corso</span>{" "}
          <span className="muted">■ da fare</span>
        </div>
        <button
          className="primary"
          style={{ marginTop: 8, width: "100%" }}
          disabled={!bda || !!exporting || subjects.length === 0}
          onClick={() => void doExport()}
        >
          {exporting
            ? `Export ${exporting.done}/${exporting.total}…`
            : "Esporta riepilogo (Excel)"}
        </button>
      </aside>

      <section className="card diarygrid">
        {!code ? (
          <p className="muted">Seleziona un utente a sinistra.</p>
        ) : (
          <>
            <div className="row" style={{ gap: 4, marginBottom: 8 }}>
              {DAYS.map((d) => (
                <button
                  key={d}
                  className={!showSummary && d === day ? "tab active" : "tab"}
                  onClick={() => {
                    setShowSummary(false);
                    setDay(d);
                  }}
                >
                  Giorno {d}
                </button>
              ))}
              <button
                className={showSummary ? "tab active" : "tab"}
                onClick={() => setShowSummary(true)}
              >
                Riepilogo nutrizionale
              </button>
            </div>

            {showSummary ? (
              <Summary
                entries={entries}
                resolve={resolve}
                nutrientCols={nutrientCols}
                mnovaConfig={mnovaConfig}
                config={config}
              />
            ) : (
              <>
                <AddEntryRow code={code} day={day} />

                <div className="tablewrap" style={{ maxHeight: "60vh", marginTop: 8 }}>
                  <table className="grid">
                    <thead>
                      <tr>
                        <th>Pasto</th>
                        <th>Ora</th>
                        <th>Luogo</th>
                        <th>Alimento</th>
                        <th>Note</th>
                        <th>Qtà rif.</th>
                        <th>Qtà (g)</th>
                        <th>Alimento BDA</th>
                        <th>Stato</th>
                        <th>NOVA</th>
                        <th>mNOVA</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {dayEntries.map((e) => {
                        const food = e.bdaCode ? bdaByCode.get(e.bdaCode) : undefined;
                        const resolved = !!food;
                        const orphan = !!e.bdaCode && !food;
                        const mnova = computeMnova(e.nova, food?.data ?? null, mnovaConfig);
                        return (
                          <tr key={e.id}>
                            <td>{e.meal}</td>
                            <td className="muted">{e.ora}</td>
                            <td className="muted">{e.luogo}</td>
                            <td>{e.foodName}</td>
                            <td className="muted">{e.notes}</td>
                            <td className="muted">{e.qtyRaw}</td>
                            <td>
                              <input
                                className="cell"
                                type="number"
                                defaultValue={e.quantityG ?? ""}
                                onBlur={(ev) => {
                                  const v = ev.target.value.trim();
                                  const q = v === "" ? null : Number(v.replace(",", "."));
                                  if (code && e.id) void updateEntry(code, e.id, { quantityG: q });
                                }}
                              />
                            </td>
                            <td>{food?.name ?? (orphan ? e.bdaCode : "—")}</td>
                            <td>{resolved ? "✓" : orphan ? "⚠" : "—"}</td>
                            <td>
                              <select
                                value={e.nova ?? ""}
                                onChange={(ev) => {
                                  const v = ev.target.value;
                                  if (code && e.id)
                                    void updateEntry(code, e.id, {
                                      nova: v === "" ? null : Number(v),
                                    });
                                }}
                              >
                                <option value="">—</option>
                                <option value="1">1</option>
                                <option value="2">2</option>
                                <option value="3">3</option>
                                <option value="4">4</option>
                              </select>
                            </td>
                            <td>{mnova || "—"}</td>
                            <td className="row" style={{ gap: 4 }}>
                              <button onClick={() => setEditEntry(e)}>✎</button>
                              <button disabled={!bda} onClick={() => setPickerFor(e.id ?? null)}>
                                BDA
                              </button>
                              <button
                                disabled={!food}
                                title="Valori nutrizionali"
                                onClick={() => setNutrientsEntry(e)}
                              >
                                ⓘ
                              </button>
                              <button
                                onClick={() => {
                                  if (code && e.id && window.confirm("Eliminare questa voce?"))
                                    void deleteEntry(code, e.id, !!e.bdaCode);
                                }}
                              >
                                🗑
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {pickerTarget && bda && (
                  <BdaPicker
                    bda={bda}
                    onPick={(c) => void pick(pickerTarget, c)}
                    onClose={() => setPickerFor(null)}
                  />
                )}

                {editEntry && (
                  <EntryEditModal
                    entry={editEntry}
                    onSave={(patch) => {
                      if (code && editEntry.id) void updateEntry(code, editEntry.id, patch);
                      setEditEntry(null);
                    }}
                    onClose={() => setEditEntry(null)}
                  />
                )}

                {nutrientsEntry &&
                  (() => {
                    const f = nutrientsEntry.bdaCode
                      ? bdaByCode.get(nutrientsEntry.bdaCode)
                      : undefined;
                    return f ? (
                      <FoodNutrientsModal
                        entry={nutrientsEntry}
                        food={f}
                        mnovaConfig={mnovaConfig}
                        config={config}
                        onClose={() => setNutrientsEntry(null)}
                      />
                    ) : null;
                  })()}
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function AddEntryRow({ code, day }: { code: string; day: number }) {
  const [meal, setMeal] = useState<string>(MEALS[0]);
  const [food, setFood] = useState("");
  const [qty, setQty] = useState("");
  const [busy, setBusy] = useState(false);

  async function add() {
    if (!food.trim()) return;
    setBusy(true);
    try {
      await addEntry(code, {
        userCode: code,
        day,
        meal,
        foodName: food.trim(),
        quantityG: qty.trim() === "" ? null : Number(qty.replace(",", ".")),
        bdaCode: null,
        nova: null,
        notes: "",
        ora: "",
        luogo: "",
        qtyRaw: "",
      });
      setFood("");
      setQty("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="row addrow">
      <select value={meal} onChange={(e) => setMeal(e.target.value)}>
        {MEALS.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
      <input placeholder="Alimento" value={food} onChange={(e) => setFood(e.target.value)} />
      <input
        placeholder="Qtà (g)"
        type="number"
        style={{ width: 90 }}
        value={qty}
        onChange={(e) => setQty(e.target.value)}
      />
      <button className="primary" disabled={busy} onClick={() => void add()}>
        + Aggiungi
      </button>
    </div>
  );
}
