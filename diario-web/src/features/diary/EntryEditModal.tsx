import { useState } from "react";
import { MEALS, DAYS } from "../../lib/nutrition";
import type { DiaryEntry } from "../../lib/db";

export function EntryEditModal({
  entry,
  onSave,
  onClose,
}: {
  entry: DiaryEntry;
  onSave: (patch: Partial<DiaryEntry>) => void;
  onClose: () => void;
}) {
  const [meal, setMeal] = useState(entry.meal);
  const [day, setDay] = useState(entry.day);
  const [foodName, setFoodName] = useState(entry.foodName);
  const [qty, setQty] = useState(entry.quantityG?.toString() ?? "");
  const [notes, setNotes] = useState(entry.notes);
  const [ora, setOra] = useState(entry.ora);
  const [luogo, setLuogo] = useState(entry.luogo);

  function save() {
    if (!foodName.trim()) return;
    onSave({
      meal,
      day,
      foodName: foodName.trim(),
      quantityG: qty.trim() === "" ? null : Number(qty.replace(",", ".")),
      notes,
      ora,
      luogo,
    });
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="row between">
          <h3>Modifica voce</h3>
          <button onClick={onClose}>✕</button>
        </div>
        <div className="form">
          <label>
            Alimento
            <input value={foodName} onChange={(e) => setFoodName(e.target.value)} />
          </label>
          <div className="row" style={{ gap: 8 }}>
            <label style={{ flex: 1 }}>
              Pasto
              <select value={meal} onChange={(e) => setMeal(e.target.value)}>
                {MEALS.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </label>
            <label style={{ width: 90 }}>
              Giorno
              <select value={day} onChange={(e) => setDay(Number(e.target.value))}>
                {DAYS.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </label>
            <label style={{ width: 110 }}>
              Qtà (g)
              <input type="number" value={qty} onChange={(e) => setQty(e.target.value)} />
            </label>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <label style={{ width: 120 }}>
              Ora
              <input value={ora} onChange={(e) => setOra(e.target.value)} />
            </label>
            <label style={{ flex: 1 }}>
              Luogo
              <input value={luogo} onChange={(e) => setLuogo(e.target.value)} />
            </label>
          </div>
          <label>
            Note
            <input value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
        </div>
        <div className="row between" style={{ marginTop: 12 }}>
          <span />
          <div className="row" style={{ gap: 8 }}>
            <button onClick={onClose}>Annulla</button>
            <button className="primary" onClick={save}>Salva</button>
          </div>
        </div>
      </div>
    </div>
  );
}
