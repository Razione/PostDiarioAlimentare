import type { BdaFood, CategoryRow } from "../../lib/nutrition";

/** BDA completa (asset in Firebase Storage). */
export interface Bda {
  columns: string[]; // colonne nutrizionali (nome escluso)
  foods: BdaFood[];
  categories: CategoryRow[];
  updatedAt?: string;
}
