// Tipi del dominio nutrizionale (porting da constants.py).

export type BdaValue = number | string | null;
export type BdaData = Record<string, BdaValue>;

export interface BdaFood {
  id: number;
  code: string | null;
  name: string;
  data: BdaData;
}

export interface MnovaCutoff {
  col: string;
  threshold: number;
}

/** Configurazione mNOVA risolta (cutoff cibo/bevanda + categorie bevanda). */
export interface MnovaConfig {
  food: MnovaCutoff[];
  beverage: MnovaCutoff[];
  beverageCats: Set<string>;
  codeToMacro: Record<string, string | null>;
}

/** Valori sostitutivi per i codici speciali BDA (-2 tracce, -3 mancante). */
export type SpecialValues = Record<string, number>; // chiavi "-2", "-3"

/** Formule per nutriente (default: "val * qty / 100"). */
export type Formulas = Record<string, string>;

export interface CategoryRow {
  code: string;
  name_it?: string | null;
  name_en?: string | null;
  macro_code?: string | null;
  macro_name_it?: string | null;
  macro_name_en?: string | null;
}
