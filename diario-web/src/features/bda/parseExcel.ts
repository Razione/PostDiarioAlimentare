// Parsing dell'Excel BDA in-browser (porting di main.py _load_bda / _parse_bda_categories).
// xlsx (~400 KB) è caricato in modo lazy: entra nel bundle solo all'uso.
import type { WorkBook } from "xlsx";
import type { Bda } from "./bdaTypes";
import type { BdaData, BdaFood, CategoryRow } from "../../lib/nutrition";

type XLSXModule = typeof import("xlsx");
type Cell = string | number | boolean | null;
type Row = Cell[];

const NAME_COL = "Nome Alimento ITA";

function round4(n: number): number {
  return Math.round(n * 1e4) / 1e4;
}

function sheetRows(XLSX: XLSXModule, wb: WorkBook, name: string): Row[] {
  return XLSX.utils.sheet_to_json(wb.Sheets[name], {
    header: 1,
    defval: null,
    raw: true,
  }) as Row[];
}

/** Foglio delle categorie merceologiche: macro (codice < 1000) + sotto-categorie. */
function parseCategories(XLSX: XLSXModule, wb: WorkBook): CategoryRow[] {
  const name = wb.SheetNames.find((s) => {
    const u = String(s).toUpperCase();
    return u.includes("CATMERCEOL") || u.includes("CATEGOR");
  });
  if (!name) return [];
  const rows = sheetRows(XLSX, wb, name);
  const out: CategoryRow[] = [];
  let macro: { code: string; it: string; en: string } | null = null;
  for (const r of rows) {
    const raw = r?.[0];
    if (raw === null || raw === undefined || raw === "") continue;
    const num = Number(raw);
    if (Number.isNaN(num)) continue;
    const code = String(Math.trunc(num));
    const nameIt = r[1] == null ? "" : String(r[1]).trim();
    const nameEn = r[2] == null ? "" : String(r[2]).trim();
    if (Math.trunc(num) < 1000) {
      macro = { code, it: nameIt, en: nameEn };
      out.push({
        code, name_it: nameIt, name_en: nameEn,
        macro_code: code, macro_name_it: nameIt, macro_name_en: nameEn,
      });
    } else {
      out.push({
        code, name_it: nameIt, name_en: nameEn,
        macro_code: macro?.code ?? null,
        macro_name_it: macro?.it ?? null,
        macro_name_en: macro?.en ?? null,
      });
    }
  }
  return out;
}

/** Legge un file Excel BDA e ritorna la struttura {columns, foods, categories}. */
export async function parseBdaWorkbook(file: File): Promise<Bda> {
  const XLSX = await import("xlsx");
  const buf = await file.arrayBuffer();
  const wb = XLSX.read(buf, { type: "array" });

  const bdaSheet =
    wb.SheetNames.find((s) => String(s).toUpperCase().includes("BDA")) ??
    wb.SheetNames[0];
  const rows = sheetRows(XLSX, wb, bdaSheet);
  if (rows.length < 4) throw new Error(`Foglio "${bdaSheet}" troppo corto.`);

  // Riga 0 = intestazioni (IT); righe 1-2 = nomi ENG e unità; dati dalla riga 3.
  const header = (rows[0] ?? []).map((h) => String(h));
  const nameIdx = header.indexOf(NAME_COL);
  if (nameIdx < 0) {
    throw new Error(`Colonna "${NAME_COL}" non trovata nel foglio "${bdaSheet}".`);
  }
  const columns = header.filter((_, i) => i !== nameIdx);

  const foods: BdaFood[] = [];
  let nextId = 1;
  for (let r = 3; r < rows.length; r++) {
    const row = rows[r];
    if (!row) continue;
    const nameRaw = row[nameIdx];
    const name = nameRaw == null ? "" : String(nameRaw).trim();
    if (!name || name.toLowerCase() === "nan") continue;

    const data: BdaData = {};
    for (let i = 0; i < header.length; i++) {
      if (i === nameIdx) continue;
      const v = row[i];
      if (v === null || v === undefined || v === "") data[header[i]] = null;
      else if (typeof v === "number") data[header[i]] = round4(v);
      else data[header[i]] = String(v);
    }
    const codeRaw = data["Codice Alimento"];
    const code = codeRaw == null || codeRaw === "" ? null : String(codeRaw);
    foods.push({ id: nextId++, code, name, data });
  }
  if (!foods.length) throw new Error("Nessun alimento trovato nel file.");

  return {
    columns,
    foods,
    categories: parseCategories(XLSX, wb),
    updatedAt: new Date().toISOString(),
  };
}
