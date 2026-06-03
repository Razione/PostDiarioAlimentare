"""Database layer – SQLite backend for the food diary analyzer."""

import sqlite3
import json
import contextlib
import hashlib
import os
import pathlib
import sys


# Colonne BDA non nutrizionali: escluse dalla "fotografia" dei valori.
_SNAPSHOT_SKIP = {"id", "name", "Simbolo", "Codice Alimento", "Nome Alimento ENG",
                  "Nome Scientifico", "Categoria Merceologica", "parte edibile"}


def bda_value_hash(food: dict) -> str:
    """Hash stabile dei soli valori nutrizionali di un alimento BDA."""
    if not food:
        return ""
    items = sorted((k, v) for k, v in food.items() if k not in _SNAPSHOT_SKIP)
    return hashlib.sha1(
        json.dumps(items, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _default_db_path() -> str:
    if sys.platform == "darwin":
        base = pathlib.Path.home() / "Library" / "Application Support" / "DiarioAlimentare"
    elif sys.platform == "win32":
        base = pathlib.Path(os.environ.get("APPDATA", pathlib.Path.home())) / "DiarioAlimentare"
    else:
        base = pathlib.Path.home() / ".diario_alimentare"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "food_diary.db")


DB_FILE = _default_db_path()


class Database:
    def __init__(self, db_path=DB_FILE):
        self.db_path = db_path
        self._bda_columns_cache = None
        self._init_schema()

    @contextlib.contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS bda_foods (
                    id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bda_categories (
                    code          TEXT PRIMARY KEY,
                    name_it       TEXT,
                    name_en       TEXT,
                    macro_code    TEXT,
                    macro_name_it TEXT,
                    macro_name_en TEXT
                );
                CREATE TABLE IF NOT EXISTS users (
                    code  TEXT PRIMARY KEY,
                    notes TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS diary_entries (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_code   TEXT    NOT NULL,
                    day         INTEGER NOT NULL CHECK(day BETWEEN 1 AND 4),
                    meal        TEXT    NOT NULL,
                    food_name   TEXT    NOT NULL,
                    quantity_g  REAL    DEFAULT NULL,
                    bda_food_id INTEGER,
                    notes       TEXT    DEFAULT '',
                    ora         TEXT    DEFAULT '',
                    luogo       TEXT    DEFAULT '',
                    qty_raw     TEXT    DEFAULT '',
                    nova        INTEGER DEFAULT NULL,
                    bda_code    TEXT    DEFAULT '',
                    bda_hash    TEXT    DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );
                CREATE TABLE IF NOT EXISTS diary_day_meta (
                    user_code  TEXT    NOT NULL,
                    day        INTEGER NOT NULL,
                    date_label TEXT    DEFAULT '',
                    PRIMARY KEY (user_code, day)
                );
            """)
        # Migrations: add columns to existing tables if not present
        with self._conn() as conn:
            for stmt in [
                "ALTER TABLE diary_entries ADD COLUMN ora     TEXT    DEFAULT ''",
                "ALTER TABLE diary_entries ADD COLUMN luogo   TEXT    DEFAULT ''",
                "ALTER TABLE diary_entries ADD COLUMN qty_raw  TEXT    DEFAULT ''",
                "ALTER TABLE diary_entries ADD COLUMN nova     INTEGER DEFAULT NULL",
                "ALTER TABLE diary_entries ADD COLUMN bda_code TEXT    DEFAULT ''",
                "ALTER TABLE diary_entries ADD COLUMN bda_hash TEXT    DEFAULT ''",
            ]:
                try:
                    conn.execute(stmt)
                except Exception:
                    pass
        # Migration: make quantity_g nullable (recreate table if currently NOT NULL)
        self._migrate_nullable_qty()

    def _migrate_nullable_qty(self):
        """Recreate diary_entries to allow NULL quantity_g if still NOT NULL."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            col_info = conn.execute("PRAGMA table_info(diary_entries)").fetchall()
            qty_col = next((c for c in col_info if c["name"] == "quantity_g"), None)
            if qty_col is None or qty_col["notnull"] == 0:
                return  # already nullable
            # All new columns already added by ALTER TABLE above
            conn.executescript("""
                PRAGMA foreign_keys=OFF;
                CREATE TABLE diary_entries_new (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_code   TEXT    NOT NULL,
                    day         INTEGER NOT NULL CHECK(day BETWEEN 1 AND 4),
                    meal        TEXT    NOT NULL,
                    food_name   TEXT    NOT NULL,
                    quantity_g  REAL    DEFAULT NULL,
                    bda_food_id INTEGER,
                    notes       TEXT    DEFAULT '',
                    ora         TEXT    DEFAULT '',
                    luogo       TEXT    DEFAULT '',
                    qty_raw     TEXT    DEFAULT ''
                );
                INSERT INTO diary_entries_new
                    SELECT id, user_code, day, meal, food_name,
                           CASE WHEN quantity_g = 100.0 THEN NULL ELSE quantity_g END,
                           bda_food_id, notes, ora, luogo, qty_raw
                    FROM diary_entries;
                DROP TABLE diary_entries;
                ALTER TABLE diary_entries_new RENAME TO diary_entries;
                PRAGMA foreign_keys=ON;
            """)
        finally:
            conn.close()

    # ── BDA ──────────────────────────────────────────────────────────────────

    def import_bda(self, records):
        """Sostituisce la BDA preservando gli id degli alimenti già presenti.

        L'id di ogni alimento viene mantenuto stabile in base al suo
        'Codice Alimento': così le associazioni del diario (diary_entries.
        bda_food_id) non si rompono quando la BDA viene ricaricata.
        """
        with self._conn() as conn:
            # Mappa codice-alimento → id esistente, per riusare gli stessi id.
            existing = {}
            for row in conn.execute("SELECT id, data FROM bda_foods"):
                try:
                    code = json.loads(row["data"]).get("Codice Alimento")
                except Exception:
                    code = None
                if code not in (None, ""):
                    existing[str(code)] = row["id"]

            conn.execute("DELETE FROM bda_foods")

            used = set(existing.values())
            next_id = max(used) if used else 0
            rows = []
            for r in records:
                code = r["data"].get("Codice Alimento")
                code = None if code in (None, "") else str(code)
                if code is not None and code in existing:
                    fid = existing[code]
                else:
                    next_id += 1
                    while next_id in used:
                        next_id += 1
                    fid = next_id
                    used.add(fid)
                rows.append((fid, r["name"], json.dumps(r["data"], ensure_ascii=False)))

            conn.executemany(
                "INSERT INTO bda_foods (id, name, data) VALUES (?, ?, ?)", rows
            )
        self._bda_columns_cache = None

    def search_bda(self, query="", limit=300):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, name, data FROM bda_foods WHERE name LIKE ? ORDER BY name LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        return [{"id": r["id"], "name": r["name"], **json.loads(r["data"])} for r in rows]

    def get_bda_foods_by_ids(self, ids):
        if not ids:
            return {}
        placeholders = ",".join("?" * len(ids))
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT id, name, data FROM bda_foods WHERE id IN ({placeholders})",
                list(ids),
            ).fetchall()
        return {r["id"]: {"id": r["id"], "name": r["name"], **json.loads(r["data"])} for r in rows}

    def get_bda_food(self, food_id):
        with self._conn() as conn:
            r = conn.execute(
                "SELECT id, name, data FROM bda_foods WHERE id=?", (food_id,)
            ).fetchone()
        return {"id": r["id"], "name": r["name"], **json.loads(r["data"])} if r else None

    def get_bda_columns(self):
        if self._bda_columns_cache is None:
            with self._conn() as conn:
                r = conn.execute("SELECT data FROM bda_foods LIMIT 1").fetchone()
            self._bda_columns_cache = list(json.loads(r["data"]).keys()) if r else []
        return self._bda_columns_cache

    def count_bda(self):
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM bda_foods").fetchone()[0]

    # ── BDA categories ────────────────────────────────────────────────────────

    def import_bda_categories(self, records):
        """Sostituisce le categorie merceologiche.

        records: lista di dict con chiavi code, name_it, name_en,
        macro_code, macro_name_it, macro_name_en.
        """
        with self._conn() as conn:
            conn.execute("DELETE FROM bda_categories")
            conn.executemany(
                "INSERT OR REPLACE INTO bda_categories "
                "(code, name_it, name_en, macro_code, macro_name_it, macro_name_en) "
                "VALUES (?,?,?,?,?,?)",
                [(r["code"], r.get("name_it"), r.get("name_en"),
                  r.get("macro_code"), r.get("macro_name_it"), r.get("macro_name_en"))
                 for r in records],
            )

    def get_categories_map(self):
        """Ritorna {code: {name_it, name_en, macro_code, macro_name_it, ...}}."""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM bda_categories").fetchall()
        return {r["code"]: dict(r) for r in rows}

    def count_categories(self):
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM bda_categories").fetchone()[0]

    # ── Users ─────────────────────────────────────────────────────────────────

    def add_user(self, code, notes=""):
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO users (code, notes) VALUES (?,?)", (code.strip(), notes)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def update_user_notes(self, code, notes):
        with self._conn() as conn:
            conn.execute("UPDATE users SET notes=? WHERE code=?", (notes, code))

    def delete_user(self, code):
        with self._conn() as conn:
            conn.execute("DELETE FROM diary_entries WHERE user_code=?", (code,))
            conn.execute("DELETE FROM users WHERE code=?", (code,))

    def get_users(self):
        with self._conn() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY code")]

    # ── Diary entries ─────────────────────────────────────────────────────────

    def add_entry(self, user_code, day, meal, food_name,
                  quantity_g=None, notes="", ora="", luogo="", qty_raw=""):
        qty = float(quantity_g) if quantity_g is not None else None
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO diary_entries "
                "(user_code, day, meal, food_name, quantity_g, notes, ora, luogo, qty_raw) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (user_code, int(day), meal, food_name, qty, notes, ora, luogo, qty_raw),
            )

    def get_entries(self, user_code, day=None):
        sql = """
            SELECT de.id, de.day, de.meal, de.food_name, de.quantity_g,
                   de.bda_food_id, de.notes, de.ora, de.luogo, de.qty_raw, de.nova,
                   de.bda_code, de.bda_hash,
                   bf.name AS bda_name
            FROM diary_entries de
            LEFT JOIN bda_foods bf ON de.bda_food_id = bf.id
            WHERE de.user_code = ?
        """
        params = [user_code]
        if day is not None:
            sql += " AND de.day = ?"
            params.append(int(day))
        sql += " ORDER BY de.day, de.id"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params)]

    def delete_entries_for_day(self, user_code, day):
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM diary_entries WHERE user_code=? AND day=?",
                (user_code, int(day)),
            )

    def associate_bda(self, entry_id, bda_food_id):
        """Associa una voce a un alimento BDA, salvando anche il Codice Alimento
        e una fotografia dei valori (per verificare in seguito link e modifiche)."""
        food = self.get_bda_food(bda_food_id) if bda_food_id is not None else None
        code = "" if not food else str(food.get("Codice Alimento") or "")
        h = bda_value_hash(food) if food else ""
        with self._conn() as conn:
            conn.execute(
                "UPDATE diary_entries SET bda_food_id=?, bda_code=?, bda_hash=? WHERE id=?",
                (bda_food_id, code, h, entry_id),
            )

    def get_bda_code_index(self):
        """Ritorna {Codice Alimento: id} per gli alimenti BDA che hanno un codice."""
        index = {}
        with self._conn() as conn:
            for row in conn.execute("SELECT id, data FROM bda_foods"):
                try:
                    code = json.loads(row["data"]).get("Codice Alimento")
                except Exception:
                    code = None
                if code not in (None, ""):
                    index[str(code)] = row["id"]
        return index

    def reassign_user_bda(self, user_code):
        """Verifica e riaggancia le associazioni BDA dell'utente per Codice Alimento.

        - link con id 'derivato' ma codice ancora in BDA → ri-collegato;
        - codice non più presente in BDA → segnalato come 'mancante';
        - valori dell'alimento cambiati dall'associazione → segnalato come 'cambiato'
          (e la fotografia viene aggiornata).

        Returns dict con liste di descrizioni: relinked, changed, missing, ok.
        """
        index = self.get_bda_code_index()
        report = {"relinked": [], "changed": [], "missing": [], "ok": 0}
        entries = self.get_entries(user_code)
        for e in entries:
            has_link = bool(e.get("bda_food_id")) or bool(e.get("bda_code"))
            if not has_link:
                continue  # mai associato → ignora

            code = e.get("bda_code") or ""
            # Legacy: nessun codice salvato ma id ancora valido → recupero il codice.
            if not code and e.get("bda_food_id"):
                food = self.get_bda_food(e["bda_food_id"])
                if food:
                    code = str(food.get("Codice Alimento") or "")

            label = f"{e['food_name']} (g{e['day']} · {e['meal']})"
            if not code or code not in index:
                report["missing"].append(label)
                continue

            new_id = index[code]
            food = self.get_bda_food(new_id)
            new_hash = bda_value_hash(food)
            if new_id != e.get("bda_food_id"):
                self.associate_bda(e["id"], new_id)   # link derivato → ricollego
                report["relinked"].append(label)
            elif not e.get("bda_code"):
                self.associate_bda(e["id"], new_id)   # era valido: salvo solo codice/hash
                report["ok"] += 1
            elif e.get("bda_hash") and e["bda_hash"] != new_hash:
                # valori cambiati: aggiorno la fotografia e segnalo
                with self._conn() as conn:
                    conn.execute("UPDATE diary_entries SET bda_hash=? WHERE id=?",
                                 (new_hash, e["id"]))
                report["changed"].append(label)
            else:
                report["ok"] += 1
        return report

    def update_entry(self, entry_id, **kwargs):
        allowed = {"food_name", "quantity_g", "meal", "day", "notes", "ora", "luogo", "qty_raw", "nova"}
        fields = [(k, v) for k, v in kwargs.items() if k in allowed]
        if not fields:
            return
        set_clause = ", ".join(f"{k}=?" for k, _ in fields)
        vals = [v for _, v in fields] + [entry_id]
        with self._conn() as conn:
            conn.execute(f"UPDATE diary_entries SET {set_clause} WHERE id=?", vals)

    def delete_entry(self, entry_id):
        with self._conn() as conn:
            conn.execute("DELETE FROM diary_entries WHERE id=?", (entry_id,))

    def count_entries(self, user_code) -> tuple[int, int]:
        # 'assoc' conta solo le associazioni risolvibili (alimento BDA esistente),
        # non i link orfani rimasti da una BDA ricaricata.
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as tot, SUM(bf.id IS NOT NULL) as assoc "
                "FROM diary_entries de "
                "LEFT JOIN bda_foods bf ON de.bda_food_id = bf.id "
                "WHERE de.user_code=?",
                (user_code,),
            ).fetchone()
        return row["tot"] or 0, row["assoc"] or 0

    # ── Diary day meta ────────────────────────────────────────────────────────

    def set_day_meta(self, user_code, day, date_label):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO diary_day_meta (user_code, day, date_label) VALUES (?,?,?)",
                (user_code, int(day), date_label),
            )

    def get_day_meta(self, user_code, day):
        with self._conn() as conn:
            r = conn.execute(
                "SELECT date_label FROM diary_day_meta WHERE user_code=? AND day=?",
                (user_code, int(day)),
            ).fetchone()
        return r["date_label"] if r else ""

    # ── Settings ──────────────────────────────────────────────────────────────

    def set_setting(self, key, value):
        with self._conn() as conn:
            conn.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, str(value)))

    def get_setting(self, key, default=None):
        with self._conn() as conn:
            r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def get_all_settings(self) -> dict:
        with self._conn() as conn:
            return {r["key"]: r["value"]
                    for r in conn.execute("SELECT key, value FROM settings")}

    # ── Import / Export ─────────────────────────────────────────────────────────

    @staticmethod
    def _dump_table(conn, table):
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]

    @staticmethod
    def _insert_rows(conn, table, rows):
        """Inserisce righe-dict preservando le colonne presenti (e gli id)."""
        for row in rows:
            cols = list(row.keys())
            if not cols:
                continue
            conn.execute(
                f"INSERT INTO {table} ({','.join(cols)}) "
                f"VALUES ({','.join('?' * len(cols))})",
                [row[c] for c in cols],
            )

    def export_data(self, include_work=True, include_settings=True,
                    include_bda=False) -> dict:
        """Serializza il contenuto del DB in un dict pronto per JSON.

        include_work     – utenti, voci di diario, etichette dei giorni;
        include_settings – tutte le preferenze (tabella settings);
        include_bda      – banca dati alimenti + categorie merceologiche.
        """
        data = {}
        with self._conn() as conn:
            if include_settings:
                data["settings"] = {
                    r["key"]: r["value"]
                    for r in conn.execute("SELECT key, value FROM settings")
                }
            if include_work:
                data["users"] = self._dump_table(conn, "users")
                data["diary_entries"] = self._dump_table(conn, "diary_entries")
                data["diary_day_meta"] = self._dump_table(conn, "diary_day_meta")
            if include_bda:
                data["bda_foods"] = self._dump_table(conn, "bda_foods")
                data["bda_categories"] = self._dump_table(conn, "bda_categories")
        return data

    def import_settings(self, settings: dict):
        """Applica le preferenze del file (le chiavi presenti sovrascrivono)."""
        with self._conn() as conn:
            for k, v in settings.items():
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
                    (k, None if v is None else str(v)),
                )

    def replace_project(self, data: dict):
        """Sostituisce col contenuto del file ciò che il file contiene.

        Lavoro, settings e BDA vengono rimpiazzati solo se presenti nel file.
        Gli id (diary_entries.id, bda_foods.id) sono preservati così che le
        associazioni del diario restino valide.
        """
        with self._conn() as conn:
            if "users" in data or "diary_entries" in data or "diary_day_meta" in data:
                conn.execute("DELETE FROM diary_entries")
                conn.execute("DELETE FROM diary_day_meta")
                conn.execute("DELETE FROM users")
                self._insert_rows(conn, "users", data.get("users", []))
                self._insert_rows(conn, "diary_day_meta", data.get("diary_day_meta", []))
                self._insert_rows(conn, "diary_entries", data.get("diary_entries", []))
            if "settings" in data:
                conn.execute("DELETE FROM settings")
                for k, v in data["settings"].items():
                    conn.execute(
                        "INSERT INTO settings (key, value) VALUES (?,?)",
                        (k, None if v is None else str(v)),
                    )
            if "bda_foods" in data:
                conn.execute("DELETE FROM bda_foods")
                self._insert_rows(conn, "bda_foods", data["bda_foods"])
            if "bda_categories" in data:
                conn.execute("DELETE FROM bda_categories")
                self._insert_rows(conn, "bda_categories", data["bda_categories"])
        self._bda_columns_cache = None

    def merge_project(self, data: dict) -> dict:
        """Aggiunge gli utenti del file (col loro diario) ai dati esistenti.

        I codici utente già presenti vengono rinominati ('codice (2)', …) per
        non sovrascrivere. Non tocca settings né BDA: per ri-agganciare gli
        alimenti usa poi «Verifica / riassegna BDA».
        Returns {'added': [nuovi codici], 'renamed': {vecchio: nuovo}}.
        """
        report = {"added": [], "renamed": {}}
        with self._conn() as conn:
            existing = {r["code"] for r in conn.execute("SELECT code FROM users")}
            mapping = {}
            for u in data.get("users", []):
                old = u.get("code")
                if old is None:
                    continue
                new, n = old, 2
                while new in existing:
                    new = f"{old} ({n})"
                    n += 1
                existing.add(new)
                mapping[old] = new
                conn.execute("INSERT INTO users (code, notes) VALUES (?,?)",
                             (new, u.get("notes", "")))
                report["added"].append(new)
                if new != old:
                    report["renamed"][old] = new

            for m in data.get("diary_day_meta", []):
                uc = mapping.get(m.get("user_code"))
                if uc is None:
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO diary_day_meta "
                    "(user_code, day, date_label) VALUES (?,?,?)",
                    (uc, m.get("day"), m.get("date_label", "")),
                )

            for e in data.get("diary_entries", []):
                uc = mapping.get(e.get("user_code"))
                if uc is None:
                    continue
                row = {k: v for k, v in e.items() if k != "id"}  # id auto-assegnato
                row["user_code"] = uc
                self._insert_rows(conn, "diary_entries", [row])
        return report
