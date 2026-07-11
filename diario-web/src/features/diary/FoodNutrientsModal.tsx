import {
  computeFoodNutrients,
  computeEnergyKcal,
  computeMnova,
  loadSpecialValues,
  type BdaFood,
  type Formulas,
  type MnovaConfig,
} from "../../lib/nutrition";
import type { DiaryEntry } from "../../lib/db";

export function FoodNutrientsModal({
  entry,
  food,
  mnovaConfig,
  config,
  onClose,
}: {
  entry: DiaryEntry;
  food: BdaFood;
  mnovaConfig: MnovaConfig;
  config: Record<string, unknown>;
  onClose: () => void;
}) {
  const formulas = (config["nutri_formulas"] as Formulas) ?? {};
  const special = loadSpecialValues(
    config["special_values"] as Record<string, { value?: number }> | undefined,
  );
  const dec = Number(config["display_decimals"] ?? 2) || 2;
  const fmt = (n: number) => n.toFixed(dec);

  const qty = entry.quantityG ?? 100;
  const { per100, perQty } = computeFoodNutrients(food.data, entry.quantityG, formulas, special);
  const energy = computeEnergyKcal(
    Object.fromEntries(Object.entries(perQty).filter(([, v]) => v !== null)) as Record<string, number>,
  );
  const mnova = computeMnova(entry.nova, food.data, mnovaConfig);
  const cols = Object.keys(per100);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="row between">
          <h3>Valori nutrizionali — {entry.foodName}</h3>
          <button onClick={onClose}>✕</button>
        </div>
        <p className="muted small">
          BDA: <b>{food.name}</b> · Quantità: {entry.quantityG == null ? "100 (default)" : qty} g ·
          NOVA: {entry.nova ?? "—"} · mNOVA: {mnova || "—"} · Energia (ric.):{" "}
          <b>{fmt(energy)} kcal</b>
        </p>
        <div className="tablewrap" style={{ maxHeight: "55vh" }}>
          <table className="grid">
            <thead>
              <tr>
                <th>Nutriente</th>
                <th style={{ textAlign: "right" }}>per 100 g</th>
                <th style={{ textAlign: "right" }}>per {qty} g</th>
              </tr>
            </thead>
            <tbody>
              {cols.map((c) => (
                <tr key={c}>
                  <td>{c}</td>
                  <td style={{ textAlign: "right" }}>{fmt(per100[c])}</td>
                  <td style={{ textAlign: "right" }}>
                    {perQty[c] === null ? "" : fmt(perQty[c] as number)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="row between" style={{ marginTop: 8 }}>
          <span />
          <button className="primary" onClick={onClose}>Chiudi</button>
        </div>
      </div>
    </div>
  );
}
