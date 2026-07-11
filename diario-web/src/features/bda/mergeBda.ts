import type { Bda } from "./bdaTypes";
import type { BdaFood, CategoryRow } from "../../lib/nutrition";

/**
 * Unisce due BDA: gli alimenti si deduplicano per Codice Alimento (l'incoming
 * sovrascrive l'esistente); categorie e colonne sono l'unione. Utile quando la
 * banca dati è divisa in più file Excel (es. BDA standard + alimenti UPF).
 */
export function mergeBda(current: Bda | null, incoming: Bda): Bda {
  if (!current) return incoming;

  const byCode = new Map<string, BdaFood>();
  const noCode: BdaFood[] = [];
  for (const f of current.foods) (f.code ? byCode.set(f.code, f) : noCode.push(f));
  for (const f of incoming.foods) (f.code ? byCode.set(f.code, f) : noCode.push(f));

  let id = 1;
  const foods = [...byCode.values(), ...noCode]
    .map((f) => ({ ...f, id: id++ }))
    .sort((a, b) => a.name.localeCompare(b.name));

  const catMap = new Map<string, CategoryRow>();
  for (const c of current.categories) catMap.set(c.code, c);
  for (const c of incoming.categories) catMap.set(c.code, c);

  const cols = new Set(current.columns);
  for (const c of incoming.columns) cols.add(c);

  return {
    columns: [...cols],
    foods,
    categories: [...catMap.values()],
    updatedAt: new Date().toISOString(),
  };
}
