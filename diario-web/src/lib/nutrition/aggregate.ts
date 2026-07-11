// Aggregati per utente (porting di _compute_user_totals e _compute_mnova_breakdown).
import { computeFoodNutrients, computeEnergyKcal, loadSpecialValues } from "./nutrition";
import { computeMnova } from "./mnova";
import { MNOVA_COLS, DAYS } from "./constants";
import type { BdaData, Formulas, SpecialValues, MnovaConfig } from "./types";

export interface AggEntry {
  day: number;
  bdaCode: string | null;
  quantityG: number | null;
  nova: number | null;
}

type Resolve = (code: string) => BdaData | null;
type DayMap<T> = Record<number, T>;

/** Totali nutrizionali per giorno + numero di voci senza BDA. */
export function computeUserTotals(
  entries: AggEntry[],
  resolve: Resolve,
  formulas: Formulas = {},
  special: SpecialValues = loadSpecialValues(),
): { totals: DayMap<Record<string, number>>; missing: DayMap<number> } {
  const totals: DayMap<Record<string, number>> = {};
  const missing: DayMap<number> = {};
  for (const d of DAYS) {
    totals[d] = {};
    missing[d] = 0;
  }
  for (const e of entries) {
    const t = totals[e.day];
    if (!t) continue;
    if (!e.bdaCode) {
      missing[e.day] += 1;
      continue;
    }
    const food = resolve(e.bdaCode);
    if (!food) continue; // orfano: escluso ma non contato come "senza BDA"
    const { perQty } = computeFoodNutrients(food, e.quantityG, formulas, special);
    for (const [col, v] of Object.entries(perQty)) {
      if (v !== null) t[col] = (t[col] ?? 0) + v;
    }
  }
  return { totals, missing };
}

export interface MnovaBreakdown {
  perDay: DayMap<{ grams: Record<string, number>; kcal: Record<string, number> }>;
  media: { grams: Record<string, number>; kcal: Record<string, number> };
}

/** Ripartizione per categoria mNOVA: grammi e kcal per giorno e in media. */
export function computeMnovaBreakdown(
  entries: AggEntry[],
  resolve: Resolve,
  mnovaConfig: MnovaConfig,
  formulas: Formulas = {},
  special: SpecialValues = loadSpecialValues(),
): MnovaBreakdown {
  const grams: DayMap<Record<string, number>> = {};
  const kcal: DayMap<Record<string, number>> = {};
  for (const d of DAYS) {
    grams[d] = Object.fromEntries(MNOVA_COLS.map((c) => [c, 0]));
    kcal[d] = Object.fromEntries(MNOVA_COLS.map((c) => [c, 0]));
  }

  for (const e of entries) {
    if (!e.bdaCode || e.nova === null || e.nova === undefined) continue;
    const food = resolve(e.bdaCode);
    if (!food) continue;
    const mnova = computeMnova(e.nova, food, mnovaConfig);
    if (!mnova) continue;
    const qty = e.quantityG ?? 100;
    const { perQty } = computeFoodNutrients(food, e.quantityG, formulas, special);
    const foodTotals: Record<string, number> = {};
    for (const [col, v] of Object.entries(perQty)) if (v !== null) foodTotals[col] = v;
    const eKcal = computeEnergyKcal(foodTotals);

    const add = (cat: string) => {
      grams[e.day][cat] += qty;
      kcal[e.day][cat] += eKcal;
    };
    if (MNOVA_COLS.includes(mnova)) add(mnova);
    if (mnova.startsWith("3")) add("3a+3b");
    else if (mnova.startsWith("4")) add("4a+4b");
  }

  const n = DAYS.length;
  const mediaG: Record<string, number> = {};
  const mediaK: Record<string, number> = {};
  for (const c of MNOVA_COLS) {
    mediaG[c] = DAYS.reduce((s, d) => s + grams[d][c], 0) / n;
    mediaK[c] = DAYS.reduce((s, d) => s + kcal[d][c], 0) / n;
  }

  const perDay: MnovaBreakdown["perDay"] = {};
  for (const d of DAYS) perDay[d] = { grams: grams[d], kcal: kcal[d] };
  return { perDay, media: { grams: mediaG, kcal: mediaK } };
}
