/**
 * Importatore del progetto (seed.json) in Firestore per la webapp.
 *
 * Template pronto all'uso: si configura una volta creato il progetto Firebase.
 * NON carica la BDA (bda.json resta un asset statico servito da Netlify),
 * ma solo il "lavoro": soggetti, voci di diario, etichette giorni e preferenze.
 *
 * Prerequisiti:
 *   1) npm init -y && npm i firebase-admin
 *   2) Da console Firebase → Impostazioni progetto → Account di servizio →
 *      "Genera nuova chiave privata" → salva come serviceAccount.json
 *   3) Genera seed.json:  python tools/export_web_data.py
 *
 * Uso:
 *   TEAM_ID=default \
 *   GOOGLE_APPLICATION_CREDENTIALS=./serviceAccount.json \
 *   node tools/firestore_import.mjs ./web-export/seed.json
 *
 * Modello scritto (coerente col piano):
 *   teams/{TEAM}/subjects/{code}
 *   teams/{TEAM}/subjects/{code}/entries/{autoId}
 *   teams/{TEAM}/dayMeta/{code}_{day}
 *   teams/{TEAM}/settings/config
 */
import { readFile } from "node:fs/promises";
import admin from "firebase-admin";

const TEAM = process.env.TEAM_ID || "default";
const seedPath = process.argv[2] || "./web-export/seed.json";

// Preferenze desktop-only da NON portare nella config web.
const SKIP_SETTINGS = new Set(["ui_font_pt", "table_font_pt", "bda_path"]);

admin.initializeApp(); // usa GOOGLE_APPLICATION_CREDENTIALS
const db = admin.firestore();

async function commitInChunks(ops) {
  // Firestore: max 500 operazioni per batch.
  for (let i = 0; i < ops.length; i += 450) {
    const batch = db.batch();
    for (const fn of ops.slice(i, i + 450)) fn(batch);
    await batch.commit();
    process.stdout.write(`  scritte ${Math.min(i + 450, ops.length)}/${ops.length}\r`);
  }
  process.stdout.write("\n");
}

async function main() {
  const seed = JSON.parse(await readFile(seedPath, "utf-8"));
  const teamRef = db.collection("teams").doc(TEAM);

  // Soggetti
  const subjOps = seed.subjects.map((s) => (b) =>
    b.set(teamRef.collection("subjects").doc(s.code), { notes: s.notes || "" })
  );
  console.log(`Soggetti: ${subjOps.length}`);
  await commitInChunks(subjOps);

  // Voci di diario
  const entryOps = seed.entries.map((e) => (b) =>
    b.set(teamRef.collection("subjects").doc(e.userCode).collection("entries").doc(), e)
  );
  console.log(`Voci: ${entryOps.length}`);
  await commitInChunks(entryOps);

  // Etichette giorni
  const metaOps = seed.dayMeta.map((m) => (b) =>
    b.set(teamRef.collection("dayMeta").doc(`${m.code}_${m.day}`), m)
  );
  console.log(`Etichette giorno: ${metaOps.length}`);
  await commitInChunks(metaOps);

  // Preferenze (config)
  const config = Object.fromEntries(
    Object.entries(seed.settings).filter(([k]) => !SKIP_SETTINGS.has(k))
  );
  await teamRef.collection("settings").doc("config").set(config, { merge: true });
  console.log(`Config: ${Object.keys(config).length} chiavi`);

  console.log("Import completato.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
