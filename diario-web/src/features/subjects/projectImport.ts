// Import del file "progetto" del desktop (.json o .json.gz).
// Mappa lo schema desktop (snake_case) al modello web e risolve le associazioni.
import type { DiaryImport, DiaryEntry, DayMeta, Subject } from "../../lib/db";
import type { Bda } from "../bda/bdaTypes";
import type { BdaData, BdaFood, CategoryRow } from "../../lib/nutrition";

const JSON_KEYS = new Set([
  "mnova_cutoffs",
  "nutri_formulas",
  "percent_config",
  "special_values",
  "beverage_categories",
]);
const SKIP_KEYS = new Set(["ui_font_pt", "table_font_pt", "bda_path"]);

async function readText(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  const bytes = new Uint8Array(buf);
  const isGzip = bytes.length > 1 && bytes[0] === 0x1f && bytes[1] === 0x8b;
  if (isGzip && "DecompressionStream" in window) {
    const ds = new (window as unknown as { DecompressionStream: typeof DecompressionStream })
      .DecompressionStream("gzip");
    const stream = new Blob([buf]).stream().pipeThrough(ds);
    return await new Response(stream).text();
  }
  return new TextDecoder().decode(buf);
}

function normalizeSettings(settings: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(settings)) {
    if (SKIP_KEYS.has(k)) continue;
    if (JSON_KEYS.has(k) && typeof v === "string") {
      try {
        out[k] = JSON.parse(v);
      } catch {
        out[k] = v;
      }
    } else out[k] = v;
  }
  return out;
}

// L'export desktop salva bda_foods.data come STRINGA JSON grezza: qui la parsa.
function foodData(f: { data: unknown }): BdaData {
  return (typeof f.data === "string" ? JSON.parse(f.data) : f.data) as BdaData;
}

function toBda(foods: Array<{ id: number; name: string; data: unknown }>, cats: CategoryRow[]): Bda {
  const outFoods: BdaFood[] = foods.map((f) => {
    const data = foodData(f);
    const code = data["Codice Alimento"];
    return { id: f.id, code: code == null || code === "" ? null : String(code), name: f.name, data };
  });
  const columns = outFoods.length ? Object.keys(outFoods[0].data) : [];
  return { columns, foods: outFoods, categories: cats ?? [], updatedAt: new Date().toISOString() };
}

export interface ProjectImport {
  diary: DiaryImport;
  config: Record<string, unknown> | null;
  bda: Bda | null;
}

export async function parseProjectFile(file: File): Promise<ProjectImport> {
  const raw = JSON.parse(await readText(file));
  if (!raw || raw.format !== "diario-alimentare") {
    throw new Error("Non è un export di Diario Alimentare.");
  }

  // Mappa id → Codice Alimento (per risolvere associazioni senza bda_code).
  const id2code: Record<number, string> = {};
  for (const f of raw.bda_foods ?? []) {
    const c = foodData(f)["Codice Alimento"];
    if (c != null && c !== "") id2code[f.id] = String(c);
  }

  const subjects: Subject[] = (raw.users ?? []).map((u: { code: string; notes?: string }) => ({
    code: u.code,
    notes: u.notes ?? "",
    total: 0,
    assoc: 0,
  }));

  const entries: DiaryEntry[] = (raw.diary_entries ?? []).map(
    (e: Record<string, unknown>): DiaryEntry => {
      const bdaCodeRaw = (e.bda_code as string) || "";
      const fid = e.bda_food_id as number | null | undefined;
      const bdaCode = bdaCodeRaw || (fid != null ? id2code[fid] ?? "" : "") || null;
      return {
        userCode: e.user_code as string,
        day: e.day as number,
        meal: e.meal as string,
        foodName: e.food_name as string,
        quantityG: (e.quantity_g as number | null) ?? null,
        bdaCode,
        nova: (e.nova as number | null) ?? null,
        notes: (e.notes as string) ?? "",
        ora: (e.ora as string) ?? "",
        luogo: (e.luogo as string) ?? "",
        qtyRaw: (e.qty_raw as string) ?? "",
      };
    },
  );

  const dayMeta: DayMeta[] = (raw.diary_day_meta ?? []).map(
    (m: { user_code: string; day: number; date_label?: string }): DayMeta => ({
      code: m.user_code,
      day: m.day,
      dateLabel: m.date_label ?? "",
    }),
  );

  const config = raw.settings ? normalizeSettings(raw.settings as Record<string, unknown>) : null;
  const bda = (raw.bda_foods ?? []).length ? toBda(raw.bda_foods, raw.bda_categories) : null;

  return { diary: { subjects, entries, dayMeta }, config, bda };
}
