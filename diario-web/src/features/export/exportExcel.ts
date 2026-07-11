// Export Excel del riepilogo (porting di _export_selected): fogli
// "Dettaglio giorni" e "Media 4 giorni". xlsx caricato lazy.
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
import { getEntries, type Subject, type DiaryEntry } from "../../lib/db";

interface PercentTerm {
  col: string;
  factor: number;
  denom?: string;
}

type Row = Record<string, string | number | null>;

export async function exportSummaryXlsx(
  subjects: Subject[],
  resolve: (code: string) => BdaData | null,
  nutrientCols: string[],
  mnovaConfig: MnovaConfig,
  config: Record<string, unknown>,
  onProgress?: (done: number, total: number) => void,
): Promise<void> {
  const XLSX = await import("xlsx");
  const formulas = (config["nutri_formulas"] as Formulas) ?? {};
  const special = loadSpecialValues(
    config["special_values"] as Record<string, { value?: number }> | undefined,
  );
  const percentCfg = (config["percent_config"] as PercentTerm[]) ?? [];
  const pctByCol = new Map(percentCfg.map((p) => [p.col, p]));

  const pctLabel = (c: string) => `${c} (%)`;
  const mnG = MNOVA_COLS.map((c) => `mNOVA ${c} (g)`);
  const mnK = MNOVA_COLS.map((c) => `mNOVA ${c} (kcal)`);
  const mnP = MNOVA_COLS.map((c) => `mNOVA ${c} (%Kcal/Kcaltot)`);

  // Ordine colonne del foglio dettaglio.
  const header: string[] = ["Utente", "Giorno", ENERGY_LABEL];
  for (const c of nutrientCols) {
    header.push(c);
    if (pctByCol.has(c)) header.push(pctLabel(c));
  }
  header.push(...mnG, ...mnK, ...mnP, "Voci senza BDA");
  const avgHeader = header.filter((h) => h !== "Giorno").concat("Voci senza BDA (media)");

  const detail: Row[] = [];
  const avg: Row[] = [];

  let done = 0;
  for (const s of subjects) {
    const entries: DiaryEntry[] = await getEntries(s.code);
    const agg = entries.map((e) => ({
      day: e.day,
      bdaCode: e.bdaCode,
      quantityG: e.quantityG,
      nova: e.nova,
    }));
    const { totals, missing } = computeUserTotals(agg, resolve, formulas, special);
    const bd = computeMnovaBreakdown(agg, resolve, mnovaConfig, formulas, special);

    const userRows: Row[] = [];
    for (const d of DAYS) {
      const dt = totals[d];
      const energy = computeEnergyKcal(dt);
      const row: Row = { Utente: s.code, Giorno: d };
      row[ENERGY_LABEL] = round4(energy);
      for (const c of nutrientCols) {
        const val = dt[c] ?? 0;
        row[c] = round4(val);
        const term = pctByCol.get(c);
        if (term) {
          const den = term.denom ? dt[term.denom] ?? 0 : energy;
          row[pctLabel(c)] = den ? round4((val * term.factor) / den * 100) : null;
        }
      }
      const g = bd.perDay[d].grams;
      const k = bd.perDay[d].kcal;
      const totK = k["1"] + k["2"] + k["3a+3b"] + k["4a+4b"];
      MNOVA_COLS.forEach((c, i) => {
        row[mnG[i]] = round4(g[c]);
        row[mnK[i]] = round4(k[c]);
        row[mnP[i]] = totK ? round4((k[c] / totK) * 100) : null;
      });
      row["Voci senza BDA"] = missing[d];
      userRows.push(row);
    }
    detail.push(...userRows);

    // Riga media dell'utente.
    const avgRow: Row = { Utente: s.code };
    for (const h of avgHeader) {
      if (h === "Utente" || h === "Voci senza BDA (media)") continue;
      const vals = userRows
        .map((r) => r[h])
        .filter((v): v is number => typeof v === "number");
      avgRow[h] = vals.length ? round4(vals.reduce((a, b) => a + b, 0) / vals.length) : null;
    }
    const miss = DAYS.map((d) => missing[d]);
    avgRow["Voci senza BDA (media)"] = round2(miss.reduce((a, b) => a + b, 0) / miss.length);
    avg.push(avgRow);

    onProgress?.(++done, subjects.length);
  }

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(
    wb,
    XLSX.utils.json_to_sheet(detail, { header }),
    "Dettaglio giorni",
  );
  XLSX.utils.book_append_sheet(
    wb,
    XLSX.utils.json_to_sheet(avg, { header: avgHeader }),
    "Media 4 giorni",
  );
  XLSX.writeFile(wb, "riepilogo_nutrizionale.xlsx");
}

function round4(n: number): number {
  return Math.round(n * 1e4) / 1e4;
}
function round2(n: number): number {
  return Math.round(n * 100) / 100;
}
