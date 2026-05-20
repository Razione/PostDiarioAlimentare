"""Database layer – SQLite backend for the food diary analyzer."""

import sqlite3
import json
import contextlib
import os
import pathlib
import sys


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
                    nova        INTEGER DEFAULT NULL
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
                "ALTER TABLE diary_entries ADD COLUMN qty_raw TEXT    DEFAULT ''",
                "ALTER TABLE diary_entries ADD COLUMN nova    INTEGER DEFAULT NULL",
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
        with self._conn() as conn:
            conn.execute("DELETE FROM bda_foods")
            conn.executemany(
                "INSERT INTO bda_foods (name, data) VALUES (?, ?)",
                [(r["name"], json.dumps(r["data"], ensure_ascii=False)) for r in records],
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
        with self._conn() as conn:
            conn.execute(
                "UPDATE diary_entries SET bda_food_id=? WHERE id=?", (bda_food_id, entry_id)
            )

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

    def count_entries(self, user_code):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as tot, SUM(bda_food_id IS NOT NULL) as assoc "
                "FROM diary_entries WHERE user_code=?",
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
