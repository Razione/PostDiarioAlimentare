// Costanti del dominio (porting da constants.py).

export const MEALS = [
  "Colazione",
  "Spuntino mattina",
  "Pranzo",
  "Spuntino pomeriggio",
  "Cena",
] as const;

export const DAYS = [1, 2, 3, 4] as const;

// Colonne BDA non nutrizionali (escluse dai calcoli).
export const SKIP_BDA_COLS = new Set<string>([
  "Simbolo",
  "Codice Alimento",
  "Nome Alimento ENG",
  "Nome Scientifico",
  "Categoria Merceologica",
  "parte edibile",
]);

// Energia ricalcolata: [nomi-colonna accettati, coefficiente kcal/g].
export const ENERGY_TERMS: Array<[string[], number]> = [
  [["Total protein", "Proteine totali"], 4.0],
  [["Total fat", "Lipidi totali"], 9.0],
  [["Available carbohydrates (MSE)", "Carboidrati disponibili (MSE)"], 3.75],
  [["Dietary total fibre", "Dietary total fiber", "Fibra alimentare totale"], 2.0],
  [["Alcohol", "Alcol"], 7.0],
];

export const ENERGY_LABEL = "Energia totale RICALCOLATA (kcal)";

// Colonne della ripartizione mNOVA.
export const MNOVA_COLS = ["1", "2", "3a", "3b", "3a+3b", "4a", "4b", "4a+4b"];

// Sale derivato dal sodio.
export const SALT_LABEL = "Sale (g)";
export const SALT_SOURCE = ["Sodium", "Sodio"];
export const SALT_FACTOR = 2.5 / 1000.0;

// Nutrienti selezionabili come cutoff mNOVA (una tupla = colonna diretta).
export const CUTOFF_ORDER: Array<string[] | string> = [
  ["Total fat", "Lipidi totali"],
  ["Total saturated fatty acids", "Acidi grassi saturi totali"],
  ["Soluble carbohydrates (MSE)", "Carboidrati solubili (MSE)"],
  SALT_LABEL,
];

export const DEFAULT_FORMULA = "val * qty / 100";
export const DEFAULT_DECIMALS = 2;

// Codici speciali BDA: -2 = tracce, -3 = dato mancante (default sostitutivo: 0).
export const SPECIAL_CODES = ["-2", "-3"] as const;
