import { useMemo } from "react";
import {
  computeUserTotals,
  computeMnovaBreakdown,
  computeEnergyKcal,
  loadSpecialValues,
  ENERGY_LABEL,
  MNOVA_COLS,
  DAYS,
  type BdaData,
  type Formulas,
  type MnovaConfig,
} from "../../lib/nutrition";
import type { DiaryEntry } from "../../lib/db";

export function Summary({
  entries,
  resolve,
  nutrientCols,
  mnovaConfig,
  config,
}: {
  entries: DiaryEntry[];
  resolve: (code: string) => BdaData | null;
  nutrientCols: string[];
  mnovaConfig: MnovaConfig;
  config: Record<string, unknown>;
}) {
  const formulas = (config["nutri_formulas"] as Formulas) ?? {};
  const special = loadSpecialValues(
    config["special_values"] as Record<string, { value?: number }> | undefined,
  );
  const dec = Number(config["display_decimals"] ?? 2) || 2;
  const fmt = (n: number) => n.toFixed(dec);

  const agg = useMemo(
    () =>
      entries.map((e) => ({
        day: e.day,
        bdaCode: e.bdaCode,
        quantityG: e.quantityG,
        nova: e.nova,
      })),
    [entries],
  );

  const { totals, missing } = useMemo(
    () => computeUserTotals(agg, resolve, formulas, special),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [agg, resolve],
  );

  const breakdown = useMemo(
    () => computeMnovaBreakdown(agg, resolve, mnovaConfig, formulas, special),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [agg, resolve, mnovaConfig],
  );

  // Valori per scope: ogni giorno + media (somma ÷ n giorni).
  const scopes = [...DAYS.map((d) => ({ key: String(d), label: `G${d}` })), { key: "media", label: "Media" }];
  const scopeValues: Record<string, Record<string, number>> = {};
  for (const d of DAYS) scopeValues[String(d)] = totals[d];
  scopeValues["media"] = {};
  for (const col of nutrientCols) {
    scopeValues["media"][col] =
      DAYS.reduce((s, d) => s + (totals[d][col] ?? 0), 0) / DAYS.length;
  }

  const missingParts = DAYS.filter((d) => missing[d] > 0).map(
    (d) => `G${d}: ${missing[d]}`,
  );

  const mediaBreak = breakdown.media;
  const totKcal =
    mediaBreak.kcal["1"] + mediaBreak.kcal["2"] + mediaBreak.kcal["3a+3b"] + mediaBreak.kcal["4a+4b"];

  return (
    <div>
      {missingParts.length > 0 && (
        <p className="error">⚠ Voci senza BDA — {missingParts.join(", ")}</p>
      )}

      <h3>Valori nutrizionali</h3>
      <div className="tablewrap" style={{ maxHeight: "45vh" }}>
        <table className="grid">
          <thead>
            <tr>
              <th>Nutriente</th>
              {scopes.map((s) => (
                <th key={s.key} style={{ textAlign: "right" }}>{s.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><b>{ENERGY_LABEL}</b></td>
              {scopes.map((s) => (
                <td key={s.key} style={{ textAlign: "right" }}>
                  <b>{fmt(computeEnergyKcal(scopeValues[s.key]))}</b>
                </td>
              ))}
            </tr>
            {nutrientCols.map((col) => (
              <tr key={col}>
                <td>{col}</td>
                {scopes.map((s) => (
                  <td key={s.key} style={{ textAlign: "right" }}>
                    {fmt(scopeValues[s.key][col] ?? 0)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 style={{ marginTop: 16 }}>Ripartizione per categoria mNOVA (media)</h3>
      <div className="tablewrap">
        <table className="grid">
          <thead>
            <tr>
              <th></th>
              {MNOVA_COLS.map((c) => (
                <th key={c} style={{ textAlign: "right" }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><b>g/day</b></td>
              {MNOVA_COLS.map((c) => (
                <td key={c} style={{ textAlign: "right" }}>{fmt(mediaBreak.grams[c])}</td>
              ))}
            </tr>
            <tr>
              <td><b>Kcal/day</b></td>
              {MNOVA_COLS.map((c) => (
                <td key={c} style={{ textAlign: "right" }}>{fmt(mediaBreak.kcal[c])}</td>
              ))}
            </tr>
            <tr>
              <td><b>%Kcal/Kcaltot</b></td>
              {MNOVA_COLS.map((c) => (
                <td key={c} style={{ textAlign: "right" }}>
                  {totKcal ? fmt((mediaBreak.kcal[c] / totKcal) * 100) : fmt(0)}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
