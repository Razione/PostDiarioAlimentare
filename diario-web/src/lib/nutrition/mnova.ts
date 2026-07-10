// Calcolo NOVA/mNOVA (porting da constants.py: _category_code, _is_beverage,
// _cutoff_value, _compute_mnova, _load_mnova_config).

import { SALT_LABEL, SALT_SOURCE, SALT_FACTOR, CUTOFF_ORDER } from "./constants";
import type {
  BdaData,
  CategoryRow,
  MnovaConfig,
  MnovaCutoff,
} from "./types";

function toNumber(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

/** Normalizza il valore "Categoria Merceologica" a codice stringa. */
export function categoryCode(cm: unknown): string {
  if (cm === null || cm === undefined) return "";
  const n = Number(cm);
  if (!Number.isNaN(n)) return String(Math.trunc(n));
  return String(cm).trim();
}

/** Costruisce la configurazione mNOVA dai dati grezzi (settings + categorie). */
export function buildMnovaConfig(
  mnovaCutoffs: unknown,
  beverageCategories: Array<string | number> = [],
  categoriesMap: Record<string, CategoryRow> = {},
): MnovaConfig {
  let food: MnovaCutoff[] = [];
  let beverage: MnovaCutoff[] = [];
  if (Array.isArray(mnovaCutoffs)) {
    food = mnovaCutoffs as MnovaCutoff[]; // vecchio formato = solo cibo
  } else if (mnovaCutoffs && typeof mnovaCutoffs === "object") {
    const o = mnovaCutoffs as { food?: MnovaCutoff[]; beverage?: MnovaCutoff[] };
    food = o.food ?? [];
    beverage = o.beverage ?? [];
  }
  const beverageCats = new Set((beverageCategories ?? []).map((c) => String(c)));
  const codeToMacro: Record<string, string | null> = {};
  if (beverageCats.size) {
    for (const [code, row] of Object.entries(categoriesMap)) {
      codeToMacro[code] = row.macro_code ?? null;
    }
  }
  return { food, beverage, beverageCats, codeToMacro };
}

/** True se l'alimento è in una categoria marcata come bevanda. */
export function isBeverage(bdaData: BdaData | null, config: MnovaConfig): boolean {
  const cats = config.beverageCats;
  if (!cats || cats.size === 0 || !bdaData) return false;
  const code = categoryCode(bdaData["Categoria Merceologica"]);
  if (cats.has(code)) return true;
  const macro = config.codeToMacro[code];
  return macro != null && cats.has(macro);
}

/** Valore del nutriente-cutoff per 100 g (gestisce il sale dal sodio). */
export function cutoffValue(label: string, bdaData: BdaData | null): number | null {
  if (!bdaData) return null;
  if (label === SALT_LABEL) {
    for (const n of SALT_SOURCE) {
      const src = bdaData[n];
      if (src !== null && src !== undefined) {
        const f = toNumber(src);
        return f === null ? null : f * SALT_FACTOR;
      }
    }
    return null;
  }
  return toNumber(bdaData[label]);
}

/** Etichetta mNOVA: NOVA 1/2 invariati; 3/4 → 'a'/'b' in base ai cutoff. */
export function computeMnova(
  nova: number | null,
  bdaData: BdaData | null,
  config: MnovaConfig | null,
): string {
  if (nova === null || nova === undefined) return "";
  if (nova === 1 || nova === 2) return String(nova);
  if (!bdaData || !config) return String(nova);

  const cutoffs = isBeverage(bdaData, config) ? config.beverage : config.food;
  if (!cutoffs || cutoffs.length === 0) return String(nova);

  const exceeds = (c: MnovaCutoff): boolean => {
    if (!c.col || c.threshold === null || c.threshold === undefined) return false;
    const val = cutoffValue(c.col, bdaData);
    return val !== null && val > Number(c.threshold);
  };
  const isB = cutoffs.some(exceeds);
  return `${nova}${isB ? "b" : "a"}`;
}

/** Nutrienti selezionabili come cutoff, adattati ai nomi BDA presenti. */
export function cutoffOptions(columns: string[]): string[] {
  const cols = new Set(columns);
  const opts: string[] = [];
  for (const entry of CUTOFF_ORDER) {
    if (entry === SALT_LABEL) {
      if (SALT_SOURCE.some((n) => cols.has(n))) opts.push(SALT_LABEL);
    } else {
      const col = (entry as string[]).find((n) => cols.has(n));
      if (col) opts.push(col);
    }
  }
  return opts;
}
