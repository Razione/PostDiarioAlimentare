// Calcoli nutrizionali (porting da constants.py: _compute_food_nutrients,
// _compute_energy_kcal). Le formule utente sono valutate con mathjs (mai eval).

import { evaluate } from "mathjs";
import { SKIP_BDA_COLS, ENERGY_TERMS, DEFAULT_FORMULA, SPECIAL_CODES } from "./constants";
import type { BdaData, Formulas, SpecialValues } from "./types";

/**
 * Valori sostitutivi per i codici speciali (-2, -3). Applica i default (0)
 * anche se non configurati — indispensabile per risultati identici al desktop.
 * `raw` è il valore della preferenza `special_values`: { "-2": { value }, ... }.
 */
export function loadSpecialValues(
  raw?: Record<string, { value?: number }> | null,
): SpecialValues {
  const out: SpecialValues = {};
  for (const code of SPECIAL_CODES) {
    const v = raw?.[code]?.value;
    out[code] = typeof v === "number" && Number.isFinite(v) ? v : 0;
  }
  return out;
}

function toNumber(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

/** Valuta una formula in sicurezza (variabili: val, qty). */
export function evalFormula(formula: string, val: number, qty: number): number | null {
  try {
    const r = evaluate(formula, { val, qty });
    return typeof r === "number" && Number.isFinite(r) ? r : null;
  } catch {
    return null;
  }
}

/**
 * Valori nutrizionali di un singolo alimento.
 * Ritorna { per100, perQty } (per100 con i codici speciali -2/-3 sostituiti).
 * Coerente con _compute_food_nutrients: la somma dei perQty = totali del giorno.
 */
export function computeFoodNutrients(
  bdaData: BdaData,
  qty: number | null,
  formulas: Formulas = {},
  special: SpecialValues = loadSpecialValues(),
): { per100: Record<string, number>; perQty: Record<string, number | null> } {
  const q = qty === null || qty === undefined ? 100 : qty;
  const per100: Record<string, number> = {};
  const perQty: Record<string, number | null> = {};

  for (const [col, val] of Object.entries(bdaData)) {
    if (col === "id" || col === "name" || SKIP_BDA_COLS.has(col) || val === null) continue;
    let f = toNumber(val);
    if (f === null) continue;
    const sub = special[String(f)];
    if (sub !== undefined) f = sub; // rimpiazza -2/-3 col valore scelto
    per100[col] = f;
    const formula = formulas[col] ?? DEFAULT_FORMULA;
    perQty[col] = evalFormula(formula, f, q);
  }
  return { per100, perQty };
}

/** Energia (kcal) da un dizionario di totali per nutriente. */
export function computeEnergyKcal(dayTotals: Record<string, number>): number {
  let energy = 0;
  for (const [names, coeff] of ENERGY_TERMS) {
    for (const name of names) {
      if (name in dayTotals) {
        energy += dayTotals[name] * coeff;
        break;
      }
    }
  }
  return energy;
}
