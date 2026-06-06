"""
Tutti i QDialog dell'applicazione.
"""

import json
import pandas as pd

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem,
    QFrame, QMessageBox, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt

from database import Database
from delegates import _SelectAllDelegate
from constants import (
    MEALS, _SKIP_BDA_COLS, _SPECIAL_CODES,
    _cutoff_options, _load_mnova_config, _load_percent_config,
    _load_special_values,
)


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
            "Definisci i cutoff per mNOVA.\n"
            "valore Nutriente >  soglia → variante 'b' (es. 3b / 4b)\n"
            "valore Nutriente <= soglia → variante 'a' (es. 3a / 4a)\n"
            "Soglie distinte per cibo e bevanda (quali categorie sono "
            "bevande si imposta in «Preferenze → Bevande»). Valori per 100 g · "
            "«Sale (g)» = Sodio(mg) × 2.5 / 1000."
        )
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self._nutrients = _cutoff_options(self.db)
        self.table = QTableWidget(len(self._nutrients), 3)
        self.table.setHorizontalHeaderLabels(
            ["Nutriente", "Soglia cibo", "Soglia bevanda"]
        )
        hdr = self.table.horizontalHeader()
        assert hdr is not None
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        vh = self.table.verticalHeader()
        if vh is not None:
            vh.setVisible(False)
        for row, name in enumerate(self._nutrients):
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(""))
            self.table.setItem(row, 2, QTableWidgetItem(""))
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
        cfg = _load_mnova_config(self.db)
        food = {c.get("col"): c.get("threshold") for c in cfg["food"]}
        bev = {c.get("col"): c.get("threshold") for c in cfg["beverage"]}
        for row, name in enumerate(self._nutrients):
            fv, bv = food.get(name), bev.get(name)
            self.table.item(row, 1).setText("" if fv is None else str(fv))
            self.table.item(row, 2).setText("" if bv is None else str(bv))

    def _save(self):
        food, beverage = [], []
        for row, name in enumerate(self._nutrients):
            for col_idx, bucket in ((1, food), (2, beverage)):
                it = self.table.item(row, col_idx)
                raw = (it.text() if it else "").strip().replace(",", ".")
                if not raw:
                    continue  # soglia vuota → cutoff disattivato per questo nutriente
                try:
                    bucket.append({"col": name, "threshold": float(raw)})
                except ValueError:
                    pass
        self.db.set_setting(
            "mnova_cutoffs",
            json.dumps({"food": food, "beverage": beverage}, ensure_ascii=False),
        )
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
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(2, 170)
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
        # Non lasciare che i nomi lunghi dei nutrienti dilatino la colonna:
        # la combo resta compatta, il menu a tendina mostra comunque il testo intero.
        dcb.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        dcb.setMinimumContentsLength(12)
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


class BeverageCategoriesDialog(QDialog):
    """Preferenze: marca quali categorie merceologiche sono bevande (cutoff mNOVA)."""

    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Preferenze – Bevande")
        self.resize(560, 520)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        lbl = QLabel(
            "Seleziona le categorie merceologiche che sono <b>bevande</b>: a queste "
            "vengono applicati i cutoff mNOVA «bevanda». Tutto il resto è trattato "
            "come cibo."
        )
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self._cat_rows = self._cats()
        if not self._cat_rows:
            warn = QLabel("Nessuna categoria disponibile: carica una BDA che includa "
                          "il foglio delle categorie merceologiche.")
            warn.setWordWrap(True)
            warn.setStyleSheet("color: darkorange;")
            layout.addWidget(warn)
        else:
            search = QLineEdit()
            search.setPlaceholderText("Filtra per codice o nome…")
            search.textChanged.connect(self._filter)
            layout.addWidget(search)

        self.list = QListWidget()
        for code, rec in self._cat_rows:
            macro = rec.get("macro_name_it") or ""
            name = rec.get("name_it") or code
            label = f"[{code}] {macro} › {name}" if macro else f"[{code}] {name}"
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, code)
            self.list.addItem(item)
        layout.addWidget(self.list)

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

    def _cats(self):
        """Sotto-categorie ordinate per macro e nome."""
        m = self.db.get_categories_map()
        subs = [(c, r) for c, r in m.items() if r.get("macro_code") != c]
        subs.sort(key=lambda t: ((t[1].get("macro_name_it") or ""),
                                 (t[1].get("name_it") or "")))
        return subs

    def _filter(self, text):
        q = text.strip().lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(q) and q not in it.text().lower())

    def _load(self):
        try:
            saved = {str(c) for c in json.loads(self.db.get_setting("beverage_categories", "[]"))}
        except Exception:
            saved = set()
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) in saved:
                it.setCheckState(Qt.CheckState.Checked)

    def _save(self):
        codes = [
            self.list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list.count())
            if self.list.item(i).checkState() == Qt.CheckState.Checked
        ]
        self.db.set_setting("beverage_categories", json.dumps(codes, ensure_ascii=False))
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
