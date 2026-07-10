// Parsing del file Content Export in-browser (porting di main.py _import_content_export).
// I 6 fogli sono concatenati orizzontalmente; una riga per utente, 4 giorni per riga.
import type { WorkBook, WorkSheet } from "xlsx";
import type { DiaryImport, DiaryEntry, DayMeta, Subject } from "../../lib/db";

type XLSXModule = typeof import("xlsx");
type Cell = string | number | boolean | Date | null;

// (nome pasto, offset del primo alimento rispetto alla colonna "Data", n. max alimenti)
const CONTENT_EXPORT_MEALS: Array<[string, number, number]> = [
  ["Colazione", 4, 20],
  ["Spuntino mattina", 66, 15],
  ["Pranzo", 113, 30],
  ["Spuntino pomeriggio", 205, 15],
  ["Cena", 252, 30],
];
// Colonne "Data" dove inizia ognuno dei 4 giorni nel foglio concatenato.
const CONTENT_EXPORT_DAY_COLS = [1, 343, 685, 1027];

/** Estrae i grammi da una stringa libera (porting di _parse_qty_grams). */
export function parseQtyGrams(raw: string): number | null {
  if (!raw || raw.toLowerCase() === "nan") return null;
  const m = raw.match(/(\d+(?:[.,]\d+)?)\s*(?:gr?(?:amm?[io]?)?)\b/i);
  if (m) {
    const n = parseFloat(m[1].replace(",", "."));
    return Number.isNaN(n) ? null : n;
  }
  return null;
}

/** Legge un foglio in una matrice rettangolare (righe × colonne) secondo il range. */
function sheetMatrix(XLSX: XLSXModule, ws: WorkSheet): { rows: Cell[][]; ncols: number } {
  const refv = ws["!ref"];
  if (!refv) return { rows: [], ncols: 0 };
  const range = XLSX.utils.decode_range(refv);
  const ncols = range.e.c - range.s.c + 1;
  const rows: Cell[][] = [];
  for (let r = range.s.r; r <= range.e.r; r++) {
    const row: Cell[] = new Array(ncols).fill(null);
    for (let c = range.s.c; c <= range.e.c; c++) {
      const cell = ws[XLSX.utils.encode_cell({ r, c })];
      row[c - range.s.c] = cell ? (cell.v as Cell) : null;
    }
    rows.push(row);
  }
  return { rows, ncols };
}

function str(v: Cell): string {
  return v === null || v === undefined ? "" : String(v).trim();
}

function two(n: number): string {
  return String(n).padStart(2, "0");
}

function formatDate(v: Cell): string {
  if (v instanceof Date) {
    return `${two(v.getDate())}/${two(v.getMonth() + 1)}/${v.getFullYear()}`;
  }
  return str(v);
}

/** Legge un Content Export e ritorna { subjects, entries, dayMeta }. */
export async function parseContentExport(file: File): Promise<DiaryImport> {
  const XLSX = await import("xlsx");
  const buf = await file.arrayBuffer();
  const wb: WorkBook = XLSX.read(buf, { type: "array", cellDates: true });

  // Concatena i fogli orizzontalmente.
  const mats = wb.SheetNames.map((n) => sheetMatrix(XLSX, wb.Sheets[n]));
  const nrows = Math.max(0, ...mats.map((m) => m.rows.length));
  const ncols = mats.reduce((s, m) => s + m.ncols, 0);
  const full: Cell[][] = [];
  for (let r = 0; r < nrows; r++) {
    const row: Cell[] = [];
    for (const m of mats) {
      const src = m.rows[r] ?? new Array(m.ncols).fill(null);
      for (let c = 0; c < m.ncols; c++) row.push(src[c] ?? null);
    }
    full.push(row);
  }

  const subjects = new Map<string, Subject>();
  const entries: DiaryEntry[] = [];
  const dayMeta: DayMeta[] = [];

  // I dati iniziano alla riga 4 (0-3 = metadata + header).
  for (let r = 4; r < full.length; r++) {
    const row = full[r];
    const userCode = str(row[0]);
    if (!userCode || userCode.toLowerCase() === "nan") continue;

    CONTENT_EXPORT_DAY_COLS.forEach((dayCol, dayIdx) => {
      if (dayCol >= ncols) return;
      const rawDate = row[dayCol];
      if (rawDate === null || str(rawDate).toLowerCase() === "nan") return;
      const day = dayIdx + 1;

      if (!subjects.has(userCode)) subjects.set(userCode, { code: userCode, notes: "" });
      dayMeta.push({ code: userCode, day, dateLabel: formatDate(rawDate) });

      for (const [meal, foodOffset, maxItems] of CONTENT_EXPORT_MEALS) {
        const oraCol = dayCol + foodOffset - 2;
        const luogoCol = dayCol + foodOffset - 1;
        const ora = oraCol >= 0 && oraCol < ncols ? str(row[oraCol]) : "";
        const luogo = luogoCol >= 0 && luogoCol < ncols ? str(row[luogoCol]) : "";

        let lastFood = "";
        for (let i = 0; i < maxItems; i++) {
          const fc = dayCol + foodOffset + i * 3;
          if (fc >= ncols) break;
          let foodName = str(row[fc]);
          if (foodName.toLowerCase() === "nan") foodName = "";
          const desc = fc + 1 < ncols ? str(row[fc + 1]) : "";
          const qtyRaw = fc + 2 < ncols ? str(row[fc + 2]) : "";
          if (!foodName && !desc && !qtyRaw) continue;
          if (!foodName) foodName = lastFood;
          if (!foodName) continue;
          lastFood = foodName;

          entries.push({
            userCode,
            day,
            meal,
            foodName,
            quantityG: parseQtyGrams(qtyRaw),
            bdaCode: null,
            nova: null,
            notes: desc.toLowerCase() === "nan" ? "" : desc,
            ora: ora.toLowerCase() === "nan" ? "" : ora,
            luogo: luogo.toLowerCase() === "nan" ? "" : luogo,
            qtyRaw,
          });
        }
      }
    });
  }

  return { subjects: [...subjects.values()], entries, dayMeta };
}
