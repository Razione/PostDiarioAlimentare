#!/usr/bin/env python3
"""
Analizzatore Diari Alimentari
Lancia con:  python main.py
"""

import sys
import re
import json
import pandas as pd

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QTabWidget,
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTextEdit,
    QTreeWidget, QTreeWidgetItem, QListWidget,
    QTableWidget, QTableWidgetItem,
    QGroupBox, QFrame, QSplitter, QFileDialog, QInputDialog,
    QMessageBox, QHeaderView, QAbstractItemView, QStyledItemDelegate,
    QListWidgetItem, QProgressDialog, QDialogButtonBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QAction

from database import Database

# ── Constants ─────────────────────────────────────────────────────────────────

MEALS = ["Colazione", "Spuntino mattina", "Pranzo", "Spuntino pomeriggio", "Cena"]
MEAL_ORDER = {m: i for i, m in enumerate(MEALS)}
DAYS = [1, 2, 3, 4]
APP_TITLE = "Analizzatore Diari Alimentari"

# Struttura del Content Export: offset rispetto alla colonna "Data" di ciascun giorno
# (meal_name, offset_primo_alimento, numero_max_alimenti)
_CONTENT_EXPORT_MEALS = [
    ("Colazione",            4,   20),
    ("Spuntino mattina",    66,   15),
    ("Pranzo",             113,   30),
    ("Spuntino pomeriggio", 205,  15),
    ("Cena",               252,   30),
]
# Colonne "Data" dove inizia ognuno dei 4 giorni nel DataFrame concatenato
_CONTENT_EXPORT_DAY_COLS = [1, 343, 685, 1027]


def _parse_qty_grams(raw: str):
    """Estrae i grammi da una stringa libera (es. '250 g', '80gr').
    Ritorna None se non riesce a determinare un peso in grammi."""
    if not raw or raw.lower() == "nan":
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:gr?(?:amm?[io]?)?)\b", raw, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            pass
    return None


# ── Dialogs ───────────────────────────────────────────────────────────────────

class BDASearchDialog(QDialog):
    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        self.value = None

        self.setWindowTitle("Cerca alimento BDA")
        self.resize(720, 480)
        self._build()
        self._do_search()

    def _build(self):
        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Cerca:"))
        self.search_edit = QLineEdit()
        self.search_edit.textChanged.connect(self._do_search)
        search_row.addWidget(self.search_edit)
        layout.addLayout(search_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Alimento"])
        hdr0 = self.tree.header()
        assert hdr0 is not None
        hdr0.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.itemDoubleClicked.connect(lambda _: self._select())
        layout.addWidget(self.tree)

        btn_row = QHBoxLayout()
        btn_clear = QPushButton("Rimuovi associazione")
        btn_clear.clicked.connect(self._clear)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_select = QPushButton("Seleziona")
        btn_select.clicked.connect(self._select)
        btn_select.setDefault(True)
        btn_row.addWidget(btn_select)
        layout.addLayout(btn_row)

    def _do_search(self):
        foods = self.db.search_bda(self.search_edit.text(), limit=400)
        self.tree.clear()
        for f in foods:
            item = QTreeWidgetItem([f["name"]])
            item.setData(0, Qt.ItemDataRole.UserRole, f["id"])
            self.tree.addTopLevelItem(item)

    def _select(self):
        items = self.tree.selectedItems()
        if not items:
            return
        item = items[0]
        self.value = (item.data(0, Qt.ItemDataRole.UserRole), item.text(0))
        self.accept()

    def _clear(self):
        self.value = (None, None)
        self.accept()


class AddEditEntryDialog(QDialog):
    def __init__(self, parent, entry=None, default_day=1):
        super().__init__(parent)
        self.value = None
        editing = entry is not None

        self.setWindowTitle("Modifica voce" if editing else "Nuova voce")
        self.setFixedSize(400, 260)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.food_edit = QLineEdit(entry["food_name"] if editing else "")
        form.addRow("Alimento:", self.food_edit)

        qty_val = entry.get("quantity_g") if editing else None
        qty_str = f"{qty_val:.4g}" if qty_val is not None else ""
        self.qty_edit = QLineEdit(qty_str)
        self.qty_edit.setPlaceholderText("—")
        form.addRow("Quantità (g):", self.qty_edit)

        self.meal_combo = QComboBox()
        self.meal_combo.addItems(MEALS)
        if editing:
            idx = self.meal_combo.findText(entry["meal"])
            if idx >= 0:
                self.meal_combo.setCurrentIndex(idx)
        form.addRow("Pasto:", self.meal_combo)

        self.day_combo = QComboBox()
        self.day_combo.addItems(["1", "2", "3", "4"])
        self.day_combo.setCurrentIndex((entry["day"] if editing else default_day) - 1)
        form.addRow("Giorno:", self.day_combo)

        self.notes_edit = QLineEdit(entry["notes"] if editing else "")
        form.addRow("Note:", self.notes_edit)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self._ok)
        btn_ok.setDefault(True)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _ok(self):
        name = self.food_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Attenzione", "Inserire il nome dell'alimento.")
            return
        qty_txt = self.qty_edit.text().strip()
        if not qty_txt or qty_txt == "—":
            qty = None
        else:
            try:
                qty = float(qty_txt.replace(",", "."))
            except ValueError:
                QMessageBox.warning(self, "Attenzione", "Quantità non valida.")
                return
        self.value = {
            "food_name": name,
            "quantity_g": qty,
            "meal": self.meal_combo.currentText(),
            "day": int(self.day_combo.currentText()),
            "notes": self.notes_edit.text().strip(),
        }
        self.accept()


class BDAImportDialog(QDialog):
    def __init__(self, parent, df: pd.DataFrame):
        super().__init__(parent)
        self.value = None

        self.setWindowTitle("Configura importazione BDA")
        self.setFixedSize(440, 180)

        layout = QVBoxLayout(self)
        cols = list(df.columns)

        lbl = QLabel(
            f"File caricato: {len(df)} righe, {len(cols)} colonne.\n\n"
            "Seleziona la colonna che contiene il nome dell'alimento:"
        )
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.name_combo = QComboBox()
        self.name_combo.addItems(cols)
        layout.addWidget(self.name_combo)

        hint = QLabel("Tutte le altre colonne numeriche verranno importate come valori nutrizionali.")
        hint.setStyleSheet("color: gray;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_import = QPushButton("Importa")
        btn_import.clicked.connect(self._ok)
        btn_import.setDefault(True)
        btn_row.addWidget(btn_import)
        layout.addLayout(btn_row)

    def _ok(self):
        self.value = self.name_combo.currentText()
        self.accept()


class PreferencesDialog(QDialog):
    """Preferenze: configura le coppie nutriente/soglia per il calcolo mNOVA."""

    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Preferenze – Cutoff mNOVA")
        self.resize(520, 380)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        lbl = QLabel(
            "Definisci i cutoff per mNOVA (NOVA 3 → 3a/3b, NOVA 4 → 4a/4b).\n"
            "Se almeno un nutriente supera la soglia → variante 'b', altrimenti 'a'."
        )
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Nutriente (colonna BDA)", "Soglia"])
        hdr = self.table.horizontalHeader()
        assert hdr is not None
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Aggiungi")
        btn_add.clicked.connect(self._add_row)
        btn_row.addWidget(btn_add)
        btn_del = QPushButton("Rimuovi")
        btn_del.clicked.connect(self._remove_row)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        ok_row = QHBoxLayout()
        ok_row.addStretch()
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        ok_row.addWidget(btn_cancel)
        btn_ok = QPushButton("Salva")
        btn_ok.clicked.connect(self._save)
        btn_ok.setDefault(True)
        ok_row.addWidget(btn_ok)
        layout.addLayout(ok_row)

    def _cols(self):
        return self.db.get_bda_columns() or []

    def _add_row(self, col_name="", threshold=""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        cb = QComboBox()
        cb.addItems(self._cols())
        if col_name:
            idx = cb.findText(col_name)
            if idx >= 0:
                cb.setCurrentIndex(idx)
        self.table.setCellWidget(row, 0, cb)
        self.table.setItem(row, 1, QTableWidgetItem(str(threshold)))

    def _remove_row(self):
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        for r in sorted(rows, reverse=True):
            self.table.removeRow(r)

    def _load(self):
        for c in _load_cutoffs(self.db):
            self._add_row(c.get("col", ""), c.get("threshold", ""))

    def _save(self):
        cutoffs = []
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            it = self.table.item(row, 1)
            if not isinstance(cb, QComboBox) or it is None:
                continue
            try:
                cutoffs.append({"col": cb.currentText(), "threshold": float(it.text().replace(",", "."))})
            except ValueError:
                pass
        self.db.set_setting("mnova_cutoffs", json.dumps(cutoffs, ensure_ascii=False))
        self.accept()


class FormulaDialog(QDialog):
    """Preferenze: formula per il calcolo del riepilogo nutrizionale, per ogni nutriente."""

    _SAFE    = {"__builtins__": {}, "abs": abs, "max": max, "min": min, "round": round}
    _DEFAULT = "val * qty / 100"

    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Preferenze – Formula nutrizionale")
        self.resize(620, 520)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Variabili: <b>val</b> = valore BDA per 100 g · <b>qty</b> = quantità in grammi\n"
            "Funzioni: abs · max · min · round · Operatori: + − * / ** ( )"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray;")
        layout.addWidget(hint)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Cerca:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filtra nutriente…")
        self.search_edit.textChanged.connect(self._filter)
        search_row.addWidget(self.search_edit)
        layout.addLayout(search_row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Nutriente", "Formula"])
        hdr = self.table.horizontalHeader()
        assert hdr is not None
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setItemDelegateForColumn(1, _SelectAllDelegate(self.table))
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Reimposta default (selezione)")
        btn_reset.setToolTip("Reimposta le righe selezionate; senza selezione reimposta tutto.")
        btn_reset.clicked.connect(self._reset)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_ok = QPushButton("Salva")
        btn_ok.clicked.connect(self._save)
        btn_ok.setDefault(True)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _load(self):
        try:
            saved = json.loads(self.db.get_setting("nutri_formulas") or "{}")
        except Exception:
            saved = {}
        cols = [c for c in self.db.get_bda_columns() if c not in _SKIP_BDA_COLS]
        self.table.setRowCount(len(cols))
        for i, col in enumerate(cols):
            name_item = QTableWidgetItem(str(col))
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, QTableWidgetItem(saved.get(col, self._DEFAULT)))

    def _filter(self, text):
        q = text.strip().lower()
        for row in range(self.table.rowCount()):
            it = self.table.item(row, 0)
            self.table.setRowHidden(row, bool(q) and (it is None or q not in it.text().lower()))

    def _reset(self):
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        targets = rows if rows else range(self.table.rowCount())
        for row in targets:
            it = self.table.item(row, 1)
            if it:
                it.setText(self._DEFAULT)

    def _save(self):
        formulas, errors = {}, []
        for row in range(self.table.rowCount()):
            ni = self.table.item(row, 0)
            fi = self.table.item(row, 1)
            if ni is None or fi is None:
                continue
            col     = ni.text()
            formula = fi.text().strip() or self._DEFAULT
            try:
                eval(formula, self._SAFE, {"val": 1.0, "qty": 100.0})
            except Exception as exc:
                errors.append(f"• {col}: {exc}")
                continue
            if formula != self._DEFAULT:
                formulas[col] = formula
        if errors:
            QMessageBox.warning(self, "Formule non valide",
                                "Errori nelle seguenti formule:\n" + "\n".join(errors))
            return
        self.db.set_setting("nutri_formulas", json.dumps(formulas, ensure_ascii=False))
        self.accept()


class SpecialValuesDialog(QDialog):
    """Preferenze: valore sostitutivo per i codici speciali BDA (-2 tracce, -3 missing)."""

    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Preferenze – Valori speciali (-2 / -3)")
        self.resize(580, 300)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        lbl = QLabel(
            "Nella BDA il valore <b>-2</b> indica le «tracce» (concentrazione molto bassa) "
            "e <b>-3</b> indica un dato <b>mancante</b>.<br>"
            "Scegli con quale valore numerico sostituirli nel calcolo del riepilogo "
            "nutrizionale, ed eventualmente aggiorna la descrizione."
        )
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.table = QTableWidget(len(_SPECIAL_CODES), 4)
        self.table.setHorizontalHeaderLabels(
            ["Codice", "Significato", "Valore sostitutivo", "Descrizione"]
        )
        hdr = self.table.horizontalHeader()
        assert hdr is not None
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        vh = self.table.verticalHeader()
        if vh is not None:
            vh.setVisible(False)
        layout.addWidget(self.table)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        ok_row = QHBoxLayout()
        ok_row.addStretch()
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        ok_row.addWidget(btn_cancel)
        btn_ok = QPushButton("Salva")
        btn_ok.clicked.connect(self._save)
        btn_ok.setDefault(True)
        ok_row.addWidget(btn_ok)
        layout.addLayout(ok_row)

    def _load(self):
        special = _load_special_values(self.db)
        for row, (code, name, _desc) in enumerate(_SPECIAL_CODES):
            code_item = QTableWidgetItem(code)
            code_item.setFlags(code_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            code_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, code_item)

            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, name_item)

            cfg = special[code]
            val_item = QTableWidgetItem(f"{cfg['value']:g}")
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 2, val_item)

            self.table.setItem(row, 3, QTableWidgetItem(cfg["desc"]))

    def _save(self):
        special, errors = {}, []
        for row, (code, _name, _desc) in enumerate(_SPECIAL_CODES):
            val_item = self.table.item(row, 2)
            desc_item = self.table.item(row, 3)
            raw = (val_item.text() if val_item else "").strip().replace(",", ".")
            try:
                value = float(raw)
            except ValueError:
                errors.append(f"• {code}: «{raw}» non è un numero valido")
                continue
            special[code] = {"value": value, "desc": desc_item.text() if desc_item else ""}
        if errors:
            QMessageBox.warning(self, "Valori non validi",
                                "Correggi i seguenti valori:\n" + "\n".join(errors))
            return
        self.db.set_setting("special_values", json.dumps(special, ensure_ascii=False))
        self.accept()


class PercentDialog(QDialog):
    """Preferenze: nutrienti per cui mostrare la % giornaliera, con fattore moltiplicativo."""

    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Preferenze – Percentuali")
        self.resize(520, 380)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        lbl = QLabel(
            "Scegli i nutrienti per cui mostrare una colonna percentuale per ogni giorno.<br>"
            "La % è calcolata come <b>(valore del giorno × fattore) / energia totale del "
            "giorno × 100</b>.<br>Con fattore = kcal/g (proteine 4, grassi 9, carboidrati "
            "3,75, fibra 2, alcol 7) ottieni la ripartizione energetica."
        )
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            ["Nutriente (colonna BDA)", "Fattore", "Denominatore"]
        )
        hdr = self.table.horizontalHeader()
        assert hdr is not None
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Aggiungi")
        btn_add.clicked.connect(self._add_row)
        btn_row.addWidget(btn_add)
        btn_del = QPushButton("Rimuovi")
        btn_del.clicked.connect(self._remove_row)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        ok_row = QHBoxLayout()
        ok_row.addStretch()
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        ok_row.addWidget(btn_cancel)
        btn_ok = QPushButton("Salva")
        btn_ok.clicked.connect(self._save)
        btn_ok.setDefault(True)
        ok_row.addWidget(btn_ok)
        layout.addLayout(ok_row)

    _ENERGY_DENOM_LABEL = "Energia totale"

    def _cols(self):
        return [c for c in (self.db.get_bda_columns() or []) if c not in _SKIP_BDA_COLS]

    def _add_row(self, col_name="", factor="", denom=""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        cb = QComboBox()
        cb.addItems(self._cols())
        if col_name:
            idx = cb.findText(col_name)
            if idx >= 0:
                cb.setCurrentIndex(idx)
        self.table.setCellWidget(row, 0, cb)
        self.table.setItem(row, 1, QTableWidgetItem(str(factor)))

        dcb = QComboBox()
        dcb.addItem(self._ENERGY_DENOM_LABEL, "")  # data "" = energia totale del giorno
        for c in self._cols():
            dcb.addItem(c, c)
        d_idx = dcb.findData(denom or "")
        dcb.setCurrentIndex(max(d_idx, 0))
        self.table.setCellWidget(row, 2, dcb)

    def _remove_row(self):
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        for r in sorted(rows, reverse=True):
            self.table.removeRow(r)

    def _load(self):
        for c in _load_percent_config(self.db):
            self._add_row(c.get("col", ""), c.get("factor", ""), c.get("denom", ""))

    def _save(self):
        config, errors = [], []
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            it = self.table.item(row, 1)
            dcb = self.table.cellWidget(row, 2)
            if not isinstance(cb, QComboBox) or it is None:
                continue
            raw = it.text().strip().replace(",", ".")
            try:
                factor = float(raw)
            except ValueError:
                errors.append(f"• {cb.currentText()}: «{raw}» non è un numero valido")
                continue
            denom = dcb.currentData() if isinstance(dcb, QComboBox) else ""
            config.append({"col": cb.currentText(), "factor": factor, "denom": denom or ""})
        if errors:
            QMessageBox.warning(self, "Fattori non validi",
                                "Correggi i seguenti fattori:\n" + "\n".join(errors))
            return
        self.db.set_setting("percent_config", json.dumps(config, ensure_ascii=False))
        self.accept()


class DiaryImportDialog(QDialog):
    def __init__(self, parent, df: pd.DataFrame):
        super().__init__(parent)
        self.value = None

        self.setWindowTitle("Importa diario – mappa colonne")
        self.setFixedSize(460, 320)

        layout = QVBoxLayout(self)
        all_cols = list(df.columns)
        opt_cols = [""] + all_cols

        layout.addWidget(QLabel(
            f"File: {len(df)} righe – assegna le colonne ai campi del diario\n(* = obbligatorio):"
        ))

        form = QFormLayout()
        self._combos = {}
        fields = [
            ("user_code",  "Codice utente *", all_cols),
            ("day",        "Giorno (1-4) *",  all_cols),
            ("meal",       "Pasto *",         all_cols),
            ("food_name",  "Alimento *",      all_cols),
            ("quantity_g", "Quantità (g)",    opt_cols),
            ("notes",      "Note",            opt_cols),
        ]
        for key, label, options in fields:
            combo = QComboBox()
            combo.addItems(options)
            self._combos[key] = combo
            form.addRow(label + ":", combo)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_import = QPushButton("Importa")
        btn_import.clicked.connect(self._ok)
        btn_import.setDefault(True)
        btn_row.addWidget(btn_import)
        layout.addLayout(btn_row)

    def _ok(self):
        required = ["user_code", "day", "meal", "food_name"]
        mapping = {}
        for key, combo in self._combos.items():
            val = combo.currentText()
            if key in required and not val:
                QMessageBox.warning(self, "Attenzione", f"Il campo '{key}' è obbligatorio.")
                return
            mapping[key] = val or None
        self.value = mapping
        self.accept()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _qty_display(qty) -> str:
    """Formatta quantity_g per la visualizzazione: None → '—', altrimenti numero."""
    return "—" if qty is None else f"{qty:.4g}"


def _load_cutoffs(db) -> list:
    """Carica i cutoff mNOVA dal DB (lista di {'col': str, 'threshold': float})."""
    try:
        return json.loads(db.get_setting("mnova_cutoffs", "[]"))
    except Exception:
        return []


# Configurazione percentuali di default: (nomi-colonna accettati, fattore).
# Denominatore di default = energia totale del giorno.
_PERCENT_DEFAULT_TERMS = [
    (("Total protein", "Proteine totali"),                              4.0),
    (("Total fat", "Lipidi totali"),                                    9.0),
    (("Available carbohydrates (MSE)", "Carboidrati disponibili (MSE)"), 3.75),
    (("Dietary total fibre", "Dietary total fiber", "Fibra alimentare totale"), 2.0),
    (("Alcohol", "Alcol"),                                              7.0),
    (("Soluble carbohydrates (MSE)", "Carboidrati solubili (MSE)"),     3.75),
]


def _default_percent_config(db) -> list:
    """Config % di default, adattata ai nomi-colonna effettivi della BDA."""
    cols = set(db.get_bda_columns() or [])
    out = []
    for names, factor in _PERCENT_DEFAULT_TERMS:
        col = next((n for n in names if n in cols), None)
        if col:
            out.append({"col": col, "factor": factor, "denom": ""})
    return out


def _load_percent_config(db) -> list:
    """Nutrienti con colonna percentuale.

    Lista di {'col': str, 'factor': float, 'denom': str}. 'denom' vuoto = energia
    totale del giorno, altrimenti il nome di una colonna BDA. Se mai configurata,
    ritorna la configurazione di default.
    """
    raw = db.get_setting("percent_config")
    if raw is None:
        return _default_percent_config(db)
    try:
        return json.loads(raw)
    except Exception:
        return []


# Codici speciali BDA: -2 = tracce (concentrazione molto bassa), -3 = dato mancante
_SPECIAL_CODES = [
    ("-2", "Tracce", "Concentrazione del componente molto bassa."),
    ("-3", "Missing (dato mancante)",
     "Componente non disponibile al momento nei dati di composizione."),
]
_SPECIAL_DEFAULTS = {code: {"value": 0.0, "desc": desc} for code, _name, desc in _SPECIAL_CODES}


def _load_special_values(db) -> dict:
    """Mappa i codici speciali BDA al valore sostitutivo scelto dall'utente.

    Returns {'-2': {'value': float, 'desc': str}, '-3': {...}}.
    """
    try:
        saved = json.loads(db.get_setting("special_values") or "{}")
    except Exception:
        saved = {}
    out = {}
    for code, default in _SPECIAL_DEFAULTS.items():
        s = saved.get(code, {})
        try:
            value = float(s.get("value", default["value"]))
        except (TypeError, ValueError):
            value = default["value"]
        out[code] = {"value": value, "desc": s.get("desc", default["desc"])}
    return out


def _compute_mnova(nova, bda_data: dict | None, cutoffs: list) -> str:
    """Calcola l'etichetta mNOVA.
    NOVA 1/2 → uguale a NOVA; NOVA 3/4 → 'a' o 'b' in base ai cutoff."""
    if nova is None:
        return ""
    if nova in (1, 2):
        return str(nova)
    if not bda_data or not cutoffs:
        return str(nova)
    is_b = any(
        c.get("col") and c.get("threshold") is not None
        and bda_data.get(c["col"]) is not None
        and float(bda_data[c["col"]]) > float(c["threshold"])
        for c in cutoffs
    )
    return f"{nova}b" if is_b else f"{nova}a"


class _SelectAllDelegate(QStyledItemDelegate):
    """Delegate che seleziona tutto il testo quando si apre l'editor."""
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.setAutoFillBackground(True)
        return editor

    def setEditorData(self, editor, index):
        super().setEditorData(editor, index)
        if isinstance(editor, QLineEdit):
            editor.selectAll()


class _DayFrameDelegate(QStyledItemDelegate):
    """Delegate per DayFrame: QLineEdit su Qtà, QComboBox su NOVA."""

    def __init__(self, qty_col: int, nova_col: int, parent=None):
        super().__init__(parent)
        self._qty_col = qty_col
        self._nova_col = nova_col

    def createEditor(self, parent, option, index):
        col = index.column()
        if col == self._qty_col:
            editor = super().createEditor(parent, option, index)
            if isinstance(editor, QLineEdit):
                editor.setAutoFillBackground(True)
            return editor
        if col == self._nova_col:
            cb = QComboBox(parent)
            cb.addItems(["—", "1", "2", "3", "4"])
            cb.setAutoFillBackground(True)
            return cb
        return None

    def setEditorData(self, editor, index):
        if index.column() == self._nova_col and isinstance(editor, QComboBox):
            txt = index.data(Qt.ItemDataRole.DisplayRole) or "—"
            i = editor.findText(txt)
            editor.setCurrentIndex(max(i, 0))
        else:
            super().setEditorData(editor, index)
            if isinstance(editor, QLineEdit):
                editor.selectAll()

    def setModelData(self, editor, model, index):
        if index.column() == self._nova_col and isinstance(editor, QComboBox) and model:
            model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)


# ── Tabs ──────────────────────────────────────────────────────────────────────

class BDATab(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self._build()
        self._refresh_view()

    def _build(self):
        layout = QVBoxLayout(self)

        tb = QHBoxLayout()
        btn_load = QPushButton("Carica BDA da Excel")
        btn_load.clicked.connect(self._load_bda)
        tb.addWidget(btn_load)
        self.status_lbl = QLabel("Nessuna BDA caricata")
        self.status_lbl.setStyleSheet("color: gray;")
        tb.addWidget(self.status_lbl)
        tb.addStretch()
        layout.addLayout(tb)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Cerca:"))
        self.search_edit = QLineEdit()
        self.search_edit.textChanged.connect(self._refresh_view)
        search_row.addWidget(self.search_edit)
        layout.addLayout(search_row)

        self.tree = QTreeWidget()
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setAlternatingRowColors(True)
        layout.addWidget(self.tree)

    def _load_bda(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona file BDA", "",
            "Excel (*.xlsx *.xls);;Tutti i file (*.*)",
        )
        if not path:
            return
        try:
            xl = pd.ExcelFile(path)
            # Trova il foglio BDA (es. "BDA-2022", "BDA 2022", ...)
            bda_sheet = next(
                (s for s in xl.sheet_names if "BDA" in str(s).upper()),
                xl.sheet_names[0],
            )
            df_raw = pd.read_excel(xl, sheet_name=bda_sheet)
            # Riga 0 = nomi inglesi, riga 1 = unità → i dati iniziano dalla riga 2
            df = df_raw.iloc[2:].reset_index(drop=True)
        except Exception as exc:
            QMessageBox.critical(self, "Errore lettura file", str(exc))
            return

        name_col = "Nome Alimento ITA"
        if name_col not in df.columns:
            # Formato non standard: chiedi all'utente
            dlg = BDAImportDialog(self, df)
            if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.value:
                return
            name_col = dlg.value

        total = len(df)
        progress = QProgressDialog("Lettura BDA in corso…", None, 0, total, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        records = []
        for i, (_, row) in enumerate(df.iterrows()):
            name = str(row[name_col]).strip()
            if not name or name.lower() == "nan":
                continue
            data = {}
            for col in df.columns:
                if col == name_col:
                    continue
                val = row[col]
                try:
                    if pd.isna(val):
                        data[col] = None
                    elif isinstance(val, (int, float)):
                        data[col] = round(float(val), 4)
                    else:
                        data[col] = str(val)
                except (TypeError, ValueError):
                    data[col] = str(val)
            records.append({"name": name, "data": data})
            if i % 100 == 0:
                progress.setValue(i)
                QApplication.processEvents()

        progress.setValue(total)

        if not records:
            QMessageBox.warning(self, "Attenzione", "Nessun alimento trovato nel file.")
            return

        progress.setLabelText("Salvataggio nel database…")
        progress.setRange(0, 0)
        QApplication.processEvents()
        self.db.import_bda(records)
        self.db.set_setting("bda_path", path)
        self._refresh_view()
        progress.reset()
        QMessageBox.information(
            self, "BDA caricata",
            f"Importati {len(records):,} alimenti dal foglio '{bda_sheet}'.",
        )

    def _refresh_view(self):
        count = self.db.count_bda()
        if count == 0:
            self.status_lbl.setText("Nessuna BDA caricata")
            self.status_lbl.setStyleSheet("color: gray;")
            self.tree.clear()
            return

        self.status_lbl.setText(f"{count:,} alimenti in BDA")
        self.status_lbl.setStyleSheet("color: green;")

        nutrient_cols = self.db.get_bda_columns()
        display_cols = ["name"] + nutrient_cols
        headers = ["Alimento"] + [str(c) for c in nutrient_cols]
        self.tree.setColumnCount(len(display_cols))
        self.tree.setHeaderLabels(headers)
        hdr = self.tree.header()
        assert hdr is not None
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hdr.setStretchLastSection(False)
        self.tree.setColumnWidth(0, 260)
        for i in range(1, len(display_cols)):
            self.tree.setColumnWidth(i, 90)

        foods = self.db.search_bda(self.search_edit.text(), limit=500)
        self.tree.clear()
        for f in foods:
            vals = [f["name"]] + [
                ("" if f.get(c) is None else str(f[c])) for c in nutrient_cols
            ]
            self.tree.addTopLevelItem(QTreeWidgetItem(vals))


class UsersTab(QWidget):
    def __init__(self, db: Database, on_change=None):
        super().__init__()
        self.db = db
        self.on_change = on_change
        self.users = []
        self._build()
        self._refresh(notify=False)

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.users_group = QGroupBox("Utenti")
        left_layout = QVBoxLayout(self.users_group)
        self.search_user = QLineEdit()
        self.search_user.setPlaceholderText("Cerca utente…")
        self.search_user.textChanged.connect(self._filter_users)
        left_layout.addWidget(self.search_user)
        self.list_widget = QListWidget()
        self.list_widget.setFont(QFont("Segoe UI", 11))
        self.list_widget.currentRowChanged.connect(self._on_select)
        left_layout.addWidget(self.list_widget)
        btn_add = QPushButton("Aggiungi")
        btn_add.clicked.connect(self._add_user)
        left_layout.addWidget(btn_add)
        btn_del = QPushButton("Elimina")
        btn_del.clicked.connect(self._delete_user)
        left_layout.addWidget(btn_del)
        self.users_group.setMaximumWidth(200)
        layout.addWidget(self.users_group)

        right_group = QGroupBox("Dettagli")
        right_vbox = QVBoxLayout(right_group)

        top_form = QFormLayout()
        self.code_lbl = QLabel("—")
        self.code_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        top_form.addRow("Codice:", self.code_lbl)
        self.stats_lbl = QLabel("")
        self.stats_lbl.setStyleSheet("color: gray;")
        top_form.addRow(self.stats_lbl)
        right_vbox.addLayout(top_form)

        right_vbox.addWidget(QLabel("Note:"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setAcceptRichText(False)
        right_vbox.addWidget(self.notes_edit)

        btn_save = QPushButton("Salva note")
        btn_save.clicked.connect(self._save_notes)
        right_vbox.addWidget(btn_save)

        layout.addWidget(right_group)

    def _refresh(self, notify=True):
        self.users = self.db.get_users()
        self.users_group.setTitle(f"Utenti ({len(self.users)})")
        self.list_widget.clear()
        for u in self.users:
            self.list_widget.addItem(u["code"])
        self._filter_users(self.search_user.text())
        if notify and self.on_change:
            self.on_change()

    def _filter_users(self, text=""):
        q = text.strip().lower()
        for i, u in enumerate(self.users):
            item = self.list_widget.item(i)
            if item:
                item.setHidden(bool(q) and q not in u["code"].lower())

    def _on_select(self, row):
        if row < 0 or row >= len(self.users):
            return
        user = self.users[row]
        self.code_lbl.setText(user["code"])
        self.notes_edit.setPlainText(user.get("notes", ""))
        tot, assoc = self.db.count_entries(user["code"])
        self.stats_lbl.setText(f"{tot} voci nel diario – {assoc} associate a BDA")

    def _add_user(self):
        code, ok = QInputDialog.getText(self, "Nuovo utente", "Codice utente:")
        if not ok or not code.strip():
            return
        if not self.db.add_user(code.strip()):
            QMessageBox.warning(self, "Attenzione", f"Il codice '{code.strip()}' esiste già.")
            return
        self._refresh()

    def _delete_user(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        user = self.users[row]
        reply = QMessageBox.question(
            self, "Conferma", f"Eliminare '{user['code']}' e tutto il suo diario?"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_user(user["code"])
        self.code_lbl.setText("—")
        self.notes_edit.clear()
        self.stats_lbl.setText("")
        self._refresh()

    def _save_notes(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        user = self.users[row]
        self.db.update_user_notes(user["code"], self.notes_edit.toPlainText().strip())
        QMessageBox.information(self, "Salvato", "Note aggiornate.")


class DayFrame(QWidget):
    def __init__(self, db: Database, day: int):
        super().__init__()
        self.db = db
        self.day = day
        self.user_code = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 4)

        tb = QHBoxLayout()
        btn_add = QPushButton("+ Aggiungi")
        btn_add.clicked.connect(self._add)
        tb.addWidget(btn_add)
        btn_edit = QPushButton("Modifica")
        btn_edit.clicked.connect(self._edit)
        tb.addWidget(btn_edit)
        btn_del = QPushButton("Elimina")
        btn_del.clicked.connect(self._delete)
        tb.addWidget(btn_del)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        tb.addWidget(sep)

        btn_assoc = QPushButton("Associa BDA")
        btn_assoc.clicked.connect(self._associate_bda)
        tb.addWidget(btn_assoc)
        btn_remove = QPushButton("Rimuovi assoc.")
        btn_remove.clicked.connect(self._remove_bda)
        tb.addWidget(btn_remove)
        tb.addStretch()
        layout.addLayout(tb)

        # 0=Pasto 1=Ora 2=Luogo 3=Alimento 4=Note 5=Qtà org. 6=Qtà(g) 7=BDA 8=Stato 9=NOVA 10=mNOVA
        self._qty_col   = 6
        self._nova_col  = 9
        self._mnova_col = 10
        self.tree = QTreeWidget()
        self.tree.setFont(QFont("Segoe UI", 11))
        self.tree.setHeaderLabels([
            "Pasto", "Ora", "Luogo", "Alimento (diario)", "Note",
            "Qtà org.", "Qtà (g)", "Alimento BDA", "Stato", "NOVA", "mNOVA",
        ])
        self.tree.setColumnWidth(0, 110)
        self.tree.setColumnWidth(1, 60)
        self.tree.setColumnWidth(2, 95)
        self.tree.setColumnWidth(3, 100)
        self.tree.setColumnWidth(4, 180)
        self.tree.setColumnWidth(5, 80)
        self.tree.setColumnWidth(6, 55)
        self.tree.setColumnWidth(7, 170)
        self.tree.setColumnWidth(8, 38)
        self.tree.setColumnWidth(9, 48)
        self.tree.setColumnWidth(10, 55)
        hdr = self.tree.header()
        assert hdr is not None
        hdr.setStretchLastSection(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setAlternatingRowColors(True)
        self.tree.setItemDelegate(_DayFrameDelegate(self._qty_col, self._nova_col, self.tree))
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.tree)

    def load_user(self, user_code):
        self.user_code = user_code
        self._refresh()

    def _refresh(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        if not self.user_code:
            self.tree.blockSignals(False)
            return
        entries = sorted(
            self.db.get_entries(self.user_code, day=self.day),
            key=lambda e: (MEAL_ORDER.get(e["meal"], 99), e["id"]),
        )
        bda_ids = {e["bda_food_id"] for e in entries if e.get("bda_food_id")}
        bda_cache = self.db.get_bda_foods_by_ids(bda_ids) if bda_ids else {}
        cutoffs = _load_cutoffs(self.db)

        for e in entries:
            nova = e.get("nova")
            bda_data = bda_cache.get(e["bda_food_id"]) if e.get("bda_food_id") else None
            mnova = _compute_mnova(nova, bda_data, cutoffs)
            item = QTreeWidgetItem([
                e["meal"],
                e.get("ora") or "",
                e.get("luogo") or "",
                e["food_name"],
                e.get("notes") or "",
                e.get("qty_raw") or "",
                _qty_display(e.get("quantity_g")),
                e.get("bda_name") or "—",
                "✓" if e["bda_food_id"] else "—",
                str(nova) if nova is not None else "—",
                mnova or "—",
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, e["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            color = QColor("#6dbf6d") if e["bda_food_id"] else QColor("#ffffff")
            for col in range(11):
                item.setForeground(col, color)
            self.tree.addTopLevelItem(item)
        self.tree.blockSignals(False)

    def _selected_id(self):
        items = self.tree.selectedItems()
        return items[0].data(0, Qt.ItemDataRole.UserRole) if items else None

    def _add(self):
        if not self.user_code:
            QMessageBox.warning(self, "Attenzione", "Seleziona prima un utente.")
            return
        dlg = AddEditEntryDialog(self, default_day=self.day)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.value:
            return
        r = dlg.value
        self.db.add_entry(self.user_code, r["day"], r["meal"], r["food_name"], r["quantity_g"], r["notes"])
        self._refresh()

    def _edit(self):
        eid = self._selected_id()
        if eid is None:
            return
        entry = next(
            (e for e in self.db.get_entries(self.user_code, day=self.day) if e["id"] == eid),
            None,
        )
        if not entry:
            return
        dlg = AddEditEntryDialog(self, entry=entry)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.value:
            return
        r = dlg.value
        self.db.update_entry(eid, food_name=r["food_name"], quantity_g=r["quantity_g"],
                             meal=r["meal"], day=r["day"], notes=r["notes"])
        self._refresh()

    def _delete(self):
        eid = self._selected_id()
        if eid is None:
            return
        if QMessageBox.question(self, "Conferma", "Eliminare questa voce?") != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_entry(eid)
        self._refresh()

    def _associate_bda(self):
        eid = self._selected_id()
        if eid is None:
            QMessageBox.warning(self, "Attenzione", "Seleziona una voce del diario.")
            return
        if self.db.count_bda() == 0:
            QMessageBox.warning(self, "Attenzione", "Carica prima la BDA dalla scheda 'BDA'.")
            return
        dlg = BDASearchDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.value is not None:
            bda_id, _ = dlg.value
            self.db.associate_bda(eid, bda_id)
            self._refresh()

    def _remove_bda(self):
        eid = self._selected_id()
        if eid is None:
            return
        self.db.associate_bda(eid, None)
        self._refresh()

    def _on_double_click(self, item, column):
        if column in (self._qty_col, self._nova_col):
            self.tree.editItem(item, column)
        else:
            self._associate_bda()

    def _on_item_changed(self, item, column):
        eid = item.data(0, Qt.ItemDataRole.UserRole)
        if eid is None:
            return

        if column == self._qty_col:
            txt = item.text(column).strip()
            qty = None if (not txt or txt == "—") else None
            if txt and txt != "—":
                try:
                    qty = float(txt.replace(",", "."))
                except ValueError:
                    self.tree.blockSignals(True)
                    item.setText(column, _qty_display(None))
                    self.tree.blockSignals(False)
                    return
            self.db.update_entry(eid, quantity_g=qty)
            self.tree.blockSignals(True)
            item.setText(column, _qty_display(qty))
            self.tree.blockSignals(False)

        elif column == self._nova_col:
            txt = item.text(column).strip()
            nova = None if (not txt or txt == "—") else int(txt) if txt in ("1", "2", "3", "4") else None
            if txt and txt not in ("—", "1", "2", "3", "4"):
                self.tree.blockSignals(True)
                item.setText(column, "—")
                self.tree.blockSignals(False)
                return
            self.db.update_entry(eid, nova=nova)
            entry_bda_id = next(
                (e["bda_food_id"] for e in self.db.get_entries(self.user_code, self.day) if e["id"] == eid),
                None,
            )
            bda_data = self.db.get_bda_food(entry_bda_id) if entry_bda_id else None
            mnova = _compute_mnova(nova, bda_data, _load_cutoffs(self.db))
            self.tree.blockSignals(True)
            item.setText(self._nova_col, str(nova) if nova is not None else "—")
            item.setText(self._mnova_col, mnova or "—")
            self.tree.blockSignals(False)


# Colonne BDA che non sono valori nutrizionali (da escludere dal riepilogo)
_SKIP_BDA_COLS = {
    "Simbolo", "Codice Alimento", "Nome Alimento ENG",
    "Nome Scientifico", "Categoria Merceologica", "parte edibile",
}

# Energia totale (kcal) calcolata dai totali giornalieri dei macronutrienti.
# Per ciascun termine: (nomi-colonna BDA accettati, coefficiente kcal/g).
ENERGY_LABEL = "Energia totale RICALCOLATA (kcal)"
_ENERGY_TERMS = [
    (("Total protein", "Proteine totali"),                              4.0),
    (("Total fat", "Lipidi totali"),                                    9.0),
    (("Available carbohydrates (MSE)", "Carboidrati disponibili (MSE)"), 3.75),
    (("Dietary total fibre", "Dietary total fiber", "Fibra alimentare totale"), 2.0),
    (("Alcohol", "Alcol"),                                              7.0),
]


def _compute_energy_kcal(day_totals: dict) -> float:
    """Energia (kcal) di un giorno dai totali dei macronutrienti.

    (proteine*4) + (grassi*9) + (carboidrati disponibili*3,75)
    + (fibra*2) + (alcol*7).
    """
    energy = 0.0
    for names, coeff in _ENERGY_TERMS:
        for name in names:
            if name in day_totals:
                energy += day_totals[name] * coeff
                break
    return energy


def _compute_user_totals(db: "Database", user_code: str):
    """Calcola i totali nutrizionali per giorno per un utente.

    Returns:
        totals  – dict {day: {col_name: float}}
        missing – dict {day: int}  (voci senza BDA associata)
    """
    try:
        formulas = json.loads(db.get_setting("nutri_formulas") or "{}")
    except Exception:
        formulas = {}
    _default = "val * qty / 100"
    _safe = {"__builtins__": {}, "abs": abs, "max": max, "min": min, "round": round}
    # Sostituzioni per i codici speciali BDA (-2 tracce, -3 missing)
    special = {float(k): v["value"] for k, v in _load_special_values(db).items()}
    totals = {d: {} for d in DAYS}
    missing = {d: 0 for d in DAYS}

    entries = db.get_entries(user_code)
    bda_ids = {e["bda_food_id"] for e in entries if e.get("bda_food_id")}
    bda_cache = db.get_bda_foods_by_ids(bda_ids) if bda_ids else {}

    for e in entries:
        day = e["day"]
        if not e["bda_food_id"]:
            missing[day] += 1
            continue
        bda = bda_cache.get(e["bda_food_id"])
        if not bda:
            continue
        qty = float(e["quantity_g"]) if e["quantity_g"] is not None else 100.0
        for col, val in bda.items():
            if col in ("id", "name") or col in _SKIP_BDA_COLS or val is None:
                continue
            try:
                fval = float(val)
                fval = special.get(fval, fval)  # rimpiazza -2/-3 col valore scelto
                formula = formulas.get(col, _default)
                result = eval(formula, _safe, {"val": fval, "qty": qty})
                totals[day][col] = totals[day].get(col, 0.0) + result
            except (TypeError, ValueError, ZeroDivisionError, NameError, SyntaxError):
                pass

    return totals, missing


class NutriSummaryFrame(QWidget):
    """Tab riepilogo: valori nutrizionali calcolati dalla BDA, per giorno."""

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.user_code = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        top = QHBoxLayout()
        self.info_lbl = QLabel("Seleziona un utente per visualizzare il riepilogo nutrizionale.")
        self.info_lbl.setStyleSheet("color: gray;")
        top.addWidget(self.info_lbl)
        top.addStretch()
        btn_refresh = QPushButton("Aggiorna")
        btn_refresh.clicked.connect(self._refresh)
        top.addWidget(btn_refresh)
        layout.addLayout(top)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        hdr = self.table.horizontalHeader()
        assert hdr is not None
        hdr.setStretchLastSection(False)
        layout.addWidget(self.table)

        self.warn_lbl = QLabel("")
        self.warn_lbl.setStyleSheet("color: darkorange;")
        self.warn_lbl.setWordWrap(True)
        layout.addWidget(self.warn_lbl)

    def load_user(self, user_code):
        self.user_code = user_code
        self._refresh()

    def _refresh(self):
        self.table.clearContents()
        self.table.setRowCount(0)
        self.warn_lbl.setText("")

        if not self.user_code:
            self.info_lbl.setText("Seleziona un utente per visualizzare il riepilogo nutrizionale.")
            self.info_lbl.setStyleSheet("color: gray;")
            return

        if self.db.count_bda() == 0:
            self.info_lbl.setText("Nessuna BDA caricata.")
            self.info_lbl.setStyleSheet("color: gray;")
            return

        totals, missing = self._compute_totals()

        # Colonne nutrizionali nell'ordine della BDA, escluse quelle non numeriche
        nutrient_cols = [c for c in self.db.get_bda_columns() if c not in _SKIP_BDA_COLS]

        if not nutrient_cols:
            self.info_lbl.setText(f"Utente: {self.user_code} — nessuna voce associata alla BDA.")
            self.info_lbl.setStyleSheet("color: orange;")
            return

        self.info_lbl.setText(f"Utente: {self.user_code}")
        self.info_lbl.setStyleSheet("")

        # Nutrienti con colonna %: {col: (fattore, denom)}. Mostrate solo se configurate.
        percent_cfg = {c["col"]: (c["factor"], c.get("denom", ""))
                       for c in _load_percent_config(self.db) if c.get("col")}
        show_pct = bool(percent_cfg)

        # Energia (kcal) per giorno: denominatore di default delle percentuali.
        energy_vals = [_compute_energy_kcal(totals[d]) for d in DAYS]

        headers = ["Nutriente"]
        for d in DAYS:
            headers.append(f"Giorno {d}")
            if show_pct:
                headers.append("%")
        headers.append("Media")
        if show_pct:
            headers.append("% media")

        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        hdr = self.table.horizontalHeader()
        assert hdr is not None
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, len(headers)):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        # Riga 0: energia totale (kcal); poi un nutriente per riga.
        rows_data = [(ENERGY_LABEL, energy_vals, None, True)]
        rows_data += [
            (col_name, [totals[d].get(col_name, 0.0) for d in DAYS],
             percent_cfg.get(col_name), False)
            for col_name in nutrient_cols
        ]

        def _num_item(text, bold):
            it = QTableWidgetItem(text)
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if bold:
                f = QFont()
                f.setBold(True)
                it.setFont(f)
            return it

        self.table.setRowCount(len(rows_data))
        for row, (label, day_vals, cfg, bold) in enumerate(rows_data):
            filled = [v for v in day_vals if v != 0.0]
            mean_val = sum(filled) / len(filled) if filled else 0.0

            # % per giorno = valore * fattore / denominatore del giorno * 100.
            # denom vuoto → energia totale del giorno, altrimenti totale di quel nutriente.
            factor, denom = cfg if cfg else (None, "")
            denom_vals = energy_vals if not denom else [totals[d].get(denom, 0.0) for d in DAYS]
            pct_vals = [
                (dv * factor / den * 100.0) if (factor is not None and den) else None
                for dv, den in zip(day_vals, denom_vals)
            ]
            pct_filled = [p for p in pct_vals if p is not None]
            pct_mean = sum(pct_filled) / len(pct_filled) if pct_filled else None

            name_item = QTableWidgetItem(str(label))
            if bold:
                f = QFont()
                f.setBold(True)
                name_item.setFont(f)
            cells = [name_item]
            for val, pct in zip(day_vals, pct_vals):
                cells.append(_num_item(f"{val:.2f}", bold))
                if show_pct:
                    cells.append(_num_item("" if pct is None else f"{pct:.2f}%", bold))
            cells.append(_num_item(f"{mean_val:.2f}", bold))
            if show_pct:
                cells.append(_num_item("" if pct_mean is None else f"{pct_mean:.2f}%", bold))

            for col_idx, it in enumerate(cells):
                self.table.setItem(row, col_idx, it)

        warn_parts = [
            f"Giorno {d}: {missing[d]} voci senza BDA"
            for d in DAYS if missing[d] > 0
        ]
        if warn_parts:
            self.warn_lbl.setText("⚠ Non calcolate — " + ", ".join(warn_parts))

    def _compute_totals(self):
        assert self.user_code is not None
        return _compute_user_totals(self.db, self.user_code)


class DiaryTab(QWidget):
    def __init__(self, db: Database, on_change=None):
        super().__init__()
        self.db = db
        self.on_change = on_change
        self.current_user = None
        self._users = []
        self._checked_users: set = set()
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Pannello sinistro: lista utenti ───────────────────────────────────
        self.users_group = QGroupBox("Utenti")
        left = self.users_group
        left_layout = QVBoxLayout(left)

        self.search_user = QLineEdit()
        self.search_user.setPlaceholderText("Cerca utente…")
        self.search_user.textChanged.connect(self._filter_users)
        left_layout.addWidget(self.search_user)

        self.user_list = QListWidget()
        self.user_list.setFont(QFont("Segoe UI", 11))
        self.user_list.currentRowChanged.connect(self._on_user_change)
        self.user_list.itemChanged.connect(self._on_check_changed)
        left_layout.addWidget(self.user_list)

        btn_add = QPushButton("+ Aggiungi")
        btn_add.clicked.connect(self._add_user)
        left_layout.addWidget(btn_add)
        btn_del = QPushButton("Elimina")
        btn_del.clicked.connect(self._delete_user)
        left_layout.addWidget(btn_del)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        left_layout.addWidget(sep)

        btn_import = QPushButton("Importa da Excel")
        btn_import.clicked.connect(self._import_diary)
        left_layout.addWidget(btn_import)

        btn_import_ce = QPushButton("Importa Content Export")
        btn_import_ce.clicked.connect(self._import_content_export)
        left_layout.addWidget(btn_import_ce)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        left_layout.addWidget(sep2)

        sel_row = QHBoxLayout()
        btn_sel_all = QPushButton("Seleziona tutti")
        btn_sel_all.clicked.connect(lambda: self._set_all_checked(True))
        sel_row.addWidget(btn_sel_all)
        btn_desel_all = QPushButton("Deseleziona tutti")
        btn_desel_all.clicked.connect(lambda: self._set_all_checked(False))
        sel_row.addWidget(btn_desel_all)
        left_layout.addLayout(sel_row)

        btn_export = QPushButton("Esporta selezionati")
        btn_export.clicked.connect(self._export_selected)
        left_layout.addWidget(btn_export)

        splitter.addWidget(left)

        # ── Pannello destro: 4 tab dei giorni ─────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.day_nb = QTabWidget()
        self.day_frames = []
        for d in DAYS:
            frm = DayFrame(self.db, d)
            self.day_nb.addTab(frm, f"  Giorno {d}  ")
            self.day_frames.append(frm)

        self.nutri_frame = NutriSummaryFrame(self.db)
        self.day_nb.addTab(self.nutri_frame, "  Riepilogo nutrizionale  ")
        self.day_nb.currentChanged.connect(self._on_tab_changed)

        right_layout.addWidget(self.day_nb)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([180, 900])

        layout.addWidget(splitter)

    def _filter_users(self, text=""):
        q = text.strip().lower()
        for i, u in enumerate(self._users):
            item = self.user_list.item(i)
            if item:
                item.setHidden(bool(q) and q not in u["code"].lower())

    def refresh_users(self):
        self._users = self.db.get_users()
        self.users_group.setTitle(f"Utenti ({len(self._users)})")
        current_code = self.current_user
        self.user_list.blockSignals(True)
        self.user_list.clear()
        for u in self._users:
            item = QListWidgetItem(u["code"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            state = Qt.CheckState.Checked if u["code"] in self._checked_users else Qt.CheckState.Unchecked
            item.setCheckState(state)
            self.user_list.addItem(item)
        if current_code:
            for i, u in enumerate(self._users):
                if u["code"] == current_code:
                    self.user_list.setCurrentRow(i)
                    break
            else:
                self.current_user = None
        self.user_list.blockSignals(False)
        self._filter_users(self.search_user.text())

    def _on_user_change(self, row):
        if row < 0 or row >= len(self._users):
            return
        code = self._users[row]["code"]
        self.current_user = code
        for d, frm in zip(DAYS, self.day_frames):
            frm.load_user(code)
            date_label = self.db.get_day_meta(code, d)[:-9]
            tab_title = f"  Giorno {d} – {date_label}  " if date_label else f"  Giorno {d}  "
            self.day_nb.setTabText(d - 1, tab_title)
        self.nutri_frame.load_user(code)

    def _on_tab_changed(self, idx):
        # Aggiorna il riepilogo ogni volta che viene selezionato il tab
        if idx == len(DAYS):
            self.nutri_frame._refresh()

    def _add_user(self):
        code, ok = QInputDialog.getText(self, "Nuovo utente", "Codice utente:")
        if not ok or not code.strip():
            return
        if not self.db.add_user(code.strip()):
            QMessageBox.warning(self, "Attenzione", f"Il codice '{code.strip()}' esiste già.")
            return
        self.refresh_users()
        if self.on_change:
            self.on_change()

    def _delete_user(self):
        if not self._checked_users:
            QMessageBox.information(self, "Elimina", "Nessun utente selezionato.")
            return
        codes = sorted(self._checked_users)
        if len(codes) == 1:
            msg = f"Eliminare '{codes[0]}' e tutto il suo diario?"
            if QMessageBox.question(self, "Conferma", msg) != QMessageBox.StandardButton.Yes:
                return
        else:
            dlg = QDialog(self)
            dlg.setWindowTitle("Conferma eliminazione")
            dlg.setMinimumWidth(320)
            lay = QVBoxLayout(dlg)
            lay.addWidget(QLabel(f"Eliminare {len(codes)} utenti e tutti i loro diari?"))
            lst = QListWidget()
            lst.addItems(codes)
            lst.setFixedHeight(min(len(codes), 10) * lst.sizeHintForRow(0) + 4)
            lst.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
            lay.addWidget(lst)
            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
            )
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            lay.addWidget(btns)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
        for code in codes:
            self.db.delete_user(code)
        self._checked_users.clear()
        self.current_user = None
        for frm in self.day_frames:
            frm.load_user(None)
        self.refresh_users()
        if self.on_change:
            self.on_change()

    def _on_check_changed(self, item):
        code = item.text()
        if item.checkState() == Qt.CheckState.Checked:
            self._checked_users.add(code)
        else:
            self._checked_users.discard(code)

    def _set_all_checked(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.user_list.blockSignals(True)
        for i in range(self.user_list.count()):
            item = self.user_list.item(i)
            if item and not item.isHidden():
                item.setCheckState(state)
                code = item.text()
                if checked:
                    self._checked_users.add(code)
                else:
                    self._checked_users.discard(code)
        self.user_list.blockSignals(False)

    def _export_selected(self):
        if not self._checked_users:
            QMessageBox.information(self, "Esporta", "Nessun utente selezionato.")
            return

        if self.db.count_bda() == 0:
            QMessageBox.warning(self, "Esporta", "Nessuna BDA caricata.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Salva esportazione", "riepilogo_nutrizionale.xlsx",
            "Excel (*.xlsx)",
        )
        if not path:
            return

        nutrient_cols = [c for c in self.db.get_bda_columns() if c not in _SKIP_BDA_COLS]
        # Config %: {col: (fattore, denom)}; denom vuoto = energia totale del giorno.
        percent_cfg = {c["col"]: (c["factor"], c.get("denom", ""))
                       for c in _load_percent_config(self.db) if c.get("col")}

        def _pct_label(col):
            return f"{col} (%)"

        # Colonne con valori decimali: ricevono il formato "almeno 2 cifre".
        float_cols = {ENERGY_LABEL}
        float_cols.update(nutrient_cols)
        float_cols.update(_pct_label(c) for c in nutrient_cols if c in percent_cfg)

        rows = []
        for user_code in sorted(self._checked_users):
            totals, missing = _compute_user_totals(self.db, user_code)
            has_any_entry = any(
                bool(totals[d]) or missing[d] > 0 for d in DAYS
            )
            if not has_any_entry:
                continue
            for day in DAYS:
                day_totals = totals[day]
                energy = _compute_energy_kcal(day_totals)
                row: dict = {"Utente": user_code, "Giorno": day}
                row[ENERGY_LABEL] = round(energy, 4)
                for col in nutrient_cols:
                    val = day_totals.get(col, 0.0)
                    row[col] = round(val, 4)
                    if col in percent_cfg:
                        factor, denom = percent_cfg[col]
                        den = energy if not denom else day_totals.get(denom, 0.0)
                        row[_pct_label(col)] = round(val * factor / den * 100, 4) if den else None
                row["Voci senza BDA"] = missing[day]
                rows.append(row)

        if not rows:
            QMessageBox.information(self, "Esporta", "Nessun dato nutrizionale disponibile per gli utenti selezionati.")
            return

        df = pd.DataFrame(rows)

        avg_rows = []
        avg_value_cols = [ENERGY_LABEL]
        for col in nutrient_cols:
            avg_value_cols.append(col)
            if col in percent_cfg:
                avg_value_cols.append(_pct_label(col))
        for user_code in sorted(self._checked_users):
            user_rows = [r for r in rows if r["Utente"] == user_code]
            if not user_rows:
                continue
            avg_row: dict = {"Utente": user_code}
            for col in avg_value_cols:
                vals = [r[col] for r in user_rows if r.get(col) is not None]
                avg_row[col] = round(sum(vals) / len(vals), 4) if vals else None
            missing_vals = [r["Voci senza BDA"] for r in user_rows]
            avg_row["Voci senza BDA (media)"] = round(
                sum(missing_vals) / len(missing_vals), 2
            ) if missing_vals else 0
            avg_rows.append(avg_row)

        df_avg = pd.DataFrame(avg_rows)
        float_cols_avg = float_cols | {"Voci senza BDA (media)"}

        def _apply_decimals(worksheet, columns, float_names):
            """Imposta il formato celle ad almeno 2 cifre decimali (fino a 4)."""
            for ci, cname in enumerate(columns, start=1):
                if cname not in float_names:
                    continue
                for r in range(2, worksheet.max_row + 1):
                    worksheet.cell(row=r, column=ci).number_format = "0.00##"

        try:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Dettaglio giorni", index=False)
                df_avg.to_excel(writer, sheet_name="Media 4 giorni", index=False)
                _apply_decimals(writer.sheets["Dettaglio giorni"], list(df.columns), float_cols)
                _apply_decimals(writer.sheets["Media 4 giorni"], list(df_avg.columns), float_cols_avg)
            QMessageBox.information(self, "Esporta", f"Esportazione completata:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Errore", f"Impossibile salvare il file:\n{exc}")

    def _import_diary(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona file diario", "",
            "Excel (*.xlsx *.xls);;CSV (*.csv);;Tutti i file (*.*)",
        )
        if not path:
            return
        try:
            df = pd.read_csv(path) if path.lower().endswith(".csv") else pd.read_excel(path)
        except Exception as exc:
            QMessageBox.critical(self, "Errore lettura file", str(exc))
            return

        dlg = DiaryImportDialog(self, df)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.value:
            return

        mapping = dlg.value
        imported, skipped = 0, 0
        total = len(df)
        last_food: dict[tuple, str] = {}

        progress = QProgressDialog("Importazione diario in corso…", None, 0, total, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        for i, (_, row) in enumerate(df.iterrows()):
            try:
                user_code = str(row[mapping["user_code"]]).strip()
                day = int(float(str(row[mapping["day"]]).strip()))
                meal = str(row[mapping["meal"]]).strip()
                food = str(row[mapping["food_name"]]).strip()

                if not user_code or user_code.lower() == "nan":
                    continue
                if not food or food.lower() == "nan":
                    food = last_food.get((user_code, day, meal), "")
                if not food:
                    continue
                last_food[(user_code, day, meal)] = food
                if day not in DAYS:
                    skipped += 1
                    continue

                qty = 100.0
                if mapping.get("quantity_g"):
                    try:
                        qty = float(str(row[mapping["quantity_g"]]).replace(",", "."))
                    except (ValueError, TypeError):
                        pass

                notes = ""
                if mapping.get("notes"):
                    notes = str(row[mapping["notes"]]).strip()
                    if notes.lower() == "nan":
                        notes = ""

                self.db.add_user(user_code)
                self.db.add_entry(user_code, day, meal, food, qty, notes)
                imported += 1
            except Exception:
                skipped += 1
            if i % 100 == 0:
                progress.setValue(i)
                QApplication.processEvents()

        progress.setValue(total)

        msg = f"Importate {imported} voci."
        if skipped:
            msg += f"\n{skipped} righe ignorate per errori o dati mancanti."
        QMessageBox.information(self, "Importazione completata", msg)
        self.refresh_users()
        if self.on_change:
            self.on_change()
        if self.current_user:
            self._on_user_change(self.user_list.currentRow())

    def _import_content_export(self):
        """Importa il file Content_Export: 6 fogli concatenati orizzontalmente,
        una riga per utente, 4 giorni di diario codificati in larghezza."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona file Content Export", "",
            "Excel (*.xlsx *.xls);;Tutti i file (*.*)",
        )
        if not path:
            return

        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                xl = pd.ExcelFile(path)
                frames = [pd.read_excel(xl, sheet_name=s, header=None) for s in xl.sheet_names]
            df_full = pd.concat(frames, axis=1, ignore_index=True)
        except Exception as exc:
            QMessageBox.critical(self, "Errore lettura file", str(exc))
            return

        # I dati iniziano alla riga 4 (0-3 = metadata + header)
        data = df_full.iloc[4:].reset_index(drop=True)
        ncols = df_full.shape[1]

        imported, skipped = 0, 0
        total = len(data)

        progress = QProgressDialog("Importazione Content Export in corso…", None, 0, total, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        for row_idx, (_, row) in enumerate(data.iterrows()):
            raw_user = str(row.iloc[0])
            user_code = raw_user.strip().strip("\r\n")
            if not user_code or user_code.lower() == "nan":
                continue

            for day_idx, day_col in enumerate(_CONTENT_EXPORT_DAY_COLS):
                if day_col >= ncols:
                    continue
                raw_date = row.iloc[day_col]
                if pd.isna(raw_date) or str(raw_date).strip().lower() == "nan":
                    continue

                day_num = day_idx + 1

                if isinstance(raw_date, pd.Timestamp):
                    date_str = raw_date.strftime("%d/%m/%Y")
                else:
                    date_str = str(raw_date).strip()
                self.db.add_user(user_code)
                self.db.set_day_meta(user_code, day_num, date_str)

                self.db.delete_entries_for_day(user_code, day_num)

                for meal_name, food_offset, max_items in _CONTENT_EXPORT_MEALS:
                    ora_col = day_col + food_offset - 2
                    luogo_col = day_col + food_offset - 1
                    meal_ora = ""
                    meal_luogo = ""
                    if 0 <= ora_col < ncols:
                        v = str(row.iloc[ora_col]).strip()
                        if v and v.lower() != "nan":
                            meal_ora = v
                    if 0 <= luogo_col < ncols:
                        v = str(row.iloc[luogo_col]).strip()
                        if v and v.lower() != "nan":
                            meal_luogo = v

                    last_food_name = ""
                    for i in range(max_items):
                        fc = day_col + food_offset + i * 3
                        if fc >= ncols:
                            break
                        food_name = str(row.iloc[fc]).strip()
                        if food_name.lower() == "nan":
                            food_name = ""
                        desc = str(row.iloc[fc + 1]).strip() if fc + 1 < ncols else ""
                        if desc.lower() == "nan":
                            desc = ""
                        qty_raw = str(row.iloc[fc + 2]).strip() if fc + 2 < ncols else ""
                        if qty_raw.lower() == "nan":
                            qty_raw = ""

                        if not food_name and not desc and not qty_raw:
                            continue
                        if not food_name:
                            food_name = last_food_name
                        if not food_name:
                            continue
                        last_food_name = food_name

                        qty_g = _parse_qty_grams(qty_raw)
                        notes = desc

                        try:
                            self.db.add_entry(user_code, day_num, meal_name,
                                              food_name, qty_g, notes,
                                              ora=meal_ora, luogo=meal_luogo,
                                              qty_raw=qty_raw)
                            imported += 1
                        except Exception:
                            skipped += 1

            if row_idx % 10 == 0:
                progress.setValue(row_idx)
                QApplication.processEvents()

        progress.setValue(total)

        msg = f"Importate {imported} voci da Content Export."
        if skipped:
            msg += f"\n{skipped} voci ignorate per errori."
        QMessageBox.information(self, "Importazione completata", msg)
        self.refresh_users()
        if self.on_change:
            self.on_change()
        if self.current_user:
            self._on_user_change(self.user_list.currentRow())


# ── Main window ───────────────────────────────────────────────────────────────

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1150, 700)
        self.setMinimumSize(850, 520)

        self.db = Database()
        self._build_menu()
        self._build_ui()
        self.diary_tab.refresh_users()

    def _build_menu(self):
        mb = self.menuBar()
        assert mb is not None

        file_m = mb.addMenu("File")
        assert file_m is not None
        act_bda = QAction("Carica BDA da Excel", self)
        act_bda.triggered.connect(lambda: (self.nb.setCurrentIndex(0), self.bda_tab._load_bda()))
        file_m.addAction(act_bda)
        file_m.addSeparator()
        act_exit = QAction("Esci", self)
        act_exit.triggered.connect(self.close)
        file_m.addAction(act_exit)

        pref_m = mb.addMenu("Preferenze")
        assert pref_m is not None
        act_mnova = QAction("Cutoff mNOVA…", self)
        act_mnova.triggered.connect(self._open_preferences)
        pref_m.addAction(act_mnova)
        act_formula = QAction("Formula nutrizionale…", self)
        act_formula.triggered.connect(self._open_formula)
        pref_m.addAction(act_formula)
        act_special = QAction("Valori speciali (-2 / -3)…", self)
        act_special.triggered.connect(self._open_special_values)
        pref_m.addAction(act_special)
        act_percent = QAction("Percentuali…", self)
        act_percent.triggered.connect(self._open_percent)
        pref_m.addAction(act_percent)

        help_m = mb.addMenu("Aiuto")
        assert help_m is not None
        act_about = QAction("Informazioni", self)
        act_about.triggered.connect(self._about)
        help_m.addAction(act_about)

    def _build_ui(self):
        self.nb = QTabWidget()
        self.setCentralWidget(self.nb)

        self.bda_tab = BDATab(self.db)
        self.nb.addTab(self.bda_tab, "  BDA  ")

        self.users_tab = UsersTab(
            self.db,
            on_change=lambda: self.diary_tab.refresh_users() if hasattr(self, "diary_tab") else None,
        )
        self.nb.addTab(self.users_tab, "  Utenti  ")

        self.diary_tab = DiaryTab(
            self.db,
            on_change=lambda: self.users_tab._refresh(notify=False),
        )
        self.nb.addTab(self.diary_tab, "  Diari  ")

    def _open_preferences(self):
        dlg = PreferencesDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted and self.diary_tab.current_user:
            row = self.diary_tab.user_list.currentRow()
            self.diary_tab._on_user_change(row)

    def _open_formula(self):
        dlg = FormulaDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.diary_tab.nutri_frame._refresh()

    def _open_special_values(self):
        dlg = SpecialValuesDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.diary_tab.nutri_frame._refresh()

    def _open_percent(self):
        dlg = PercentDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.diary_tab.nutri_frame._refresh()

    def _about(self):
        QMessageBox.information(
            self, "Informazioni",
            f"{APP_TITLE}\n\nVersione 1.0\n\n"
            "Analizza diari alimentari su 4 giorni,\n"
            "associa ogni voce a un alimento della BDA\n"
            "e calcola i valori nutrizionali.",
        )


if __name__ == "__main__":
    import traceback
    import pathlib

    _log = pathlib.Path.home() / "DiarioAlimentare_crash.log"

    try:
        app = QApplication(sys.argv)
    except Exception:
        _log.write_text(traceback.format_exc())
        sys.exit(1)

    try:
        app.setStyleSheet("""
        QTreeWidget::item:selected          { background: #0078d4; color: white; }
        QTreeWidget::item:selected:!active  { background: #b8d8f0; color: black; }
        QTreeWidget::item:hover             { background: #e5f1fb; color: black; }
        QListWidget::item:selected          { background: #0078d4; color: white; }
        QListWidget::item:selected:!active  { background: #b8d8f0; color: black; }
        QListWidget::item:hover             { background: #e5f1fb; color: black; }
        QTableWidget::item:selected         { background: #0078d4; color: white; }
        QTableWidget::item:selected:!active { background: #b8d8f0; color: black; }
        QTableWidget::item:hover            { background: #e5f1fb; color: black; }
        QTreeWidget QLineEdit, QTableWidget QLineEdit
                                            { background: palette(base); color: palette(text);
                                              selection-background-color: #0078d4;
                                              selection-color: white; }
        QTreeWidget QComboBox               { background: palette(base); color: palette(text); }
    """)
        window = App()
        window.show()
        sys.exit(app.exec())
    except Exception:
        err = traceback.format_exc()
        try:
            _log.write_text(err)
        except Exception:
            pass
        try:
            QMessageBox.critical(None, "Errore di avvio", err)
        except Exception:
            pass
        sys.exit(1)
