#!/usr/bin/env python3
"""
Analizzatore Diari Alimentari
Lancia con:  python main.py
"""

import sys
import pandas as pd

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QTabWidget,
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTextEdit,
    QTreeWidget, QTreeWidgetItem, QListWidget,
    QGroupBox, QFrame, QSplitter, QFileDialog, QInputDialog,
    QMessageBox, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QAction

from database import Database

# ── Constants ─────────────────────────────────────────────────────────────────

MEALS = ["Colazione", "Spuntino mattina", "Pranzo", "Spuntino pomeriggio", "Cena"]
MEAL_ORDER = {m: i for i, m in enumerate(MEALS)}
DAYS = [1, 2, 3, 4]
APP_TITLE = "Analizzatore Diari Alimentari"


# ── Dialogs ───────────────────────────────────────────────────────────────────

class BDASearchDialog(QDialog):
    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        self.result = None

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
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
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
        self.result = (item.data(0, Qt.ItemDataRole.UserRole), item.text(0))
        self.accept()

    def _clear(self):
        self.result = (None, None)
        self.accept()


class AddEditEntryDialog(QDialog):
    def __init__(self, parent, entry=None, default_day=1):
        super().__init__(parent)
        self.result = None
        editing = entry is not None

        self.setWindowTitle("Modifica voce" if editing else "Nuova voce")
        self.setFixedSize(400, 260)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.food_edit = QLineEdit(entry["food_name"] if editing else "")
        form.addRow("Alimento:", self.food_edit)

        self.qty_edit = QLineEdit(str(entry["quantity_g"]) if editing else "100")
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
        try:
            qty = float(self.qty_edit.text().replace(",", "."))
        except ValueError:
            QMessageBox.warning(self, "Attenzione", "Quantità non valida.")
            return
        self.result = {
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
        self.result = None

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
        self.result = self.name_combo.currentText()
        self.accept()


class DiaryImportDialog(QDialog):
    def __init__(self, parent, df: pd.DataFrame):
        super().__init__(parent)
        self.result = None

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
        self.result = mapping
        self.accept()


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
            if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.result:
                return
            name_col = dlg.result

        records = []
        for _, row in df.iterrows():
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

        if not records:
            QMessageBox.warning(self, "Attenzione", "Nessun alimento trovato nel file.")
            return

        self.db.import_bda(records)
        self.db.set_setting("bda_path", path)
        self._refresh_view()
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
        display_cols = ["name"] + nutrient_cols[:9]
        headers = ["Alimento"] + [str(c)[:18] for c in nutrient_cols[:9]]
        self.tree.setColumnCount(len(display_cols))
        self.tree.setHeaderLabels(headers)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(display_cols)):
            self.tree.setColumnWidth(i, 95)

        foods = self.db.search_bda(self.search_edit.text(), limit=500)
        self.tree.clear()
        for f in foods:
            vals = [f["name"]] + [
                ("" if f.get(c) is None else str(f[c])) for c in nutrient_cols[:9]
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

        left_group = QGroupBox("Utenti")
        left_layout = QVBoxLayout(left_group)
        self.list_widget = QListWidget()
        self.list_widget.setFont(QFont("Courier", 11))
        self.list_widget.currentRowChanged.connect(self._on_select)
        left_layout.addWidget(self.list_widget)
        btn_add = QPushButton("Aggiungi")
        btn_add.clicked.connect(self._add_user)
        left_layout.addWidget(btn_add)
        btn_del = QPushButton("Elimina")
        btn_del.clicked.connect(self._delete_user)
        left_layout.addWidget(btn_del)
        left_group.setMaximumWidth(200)
        layout.addWidget(left_group)

        right_group = QGroupBox("Dettagli")
        right_layout = QFormLayout(right_group)
        self.code_lbl = QLabel("—")
        self.code_lbl.setFont(QFont("", 11, QFont.Weight.Bold))
        right_layout.addRow("Codice:", self.code_lbl)
        self.notes_edit = QTextEdit()
        self.notes_edit.setAcceptRichText(False)
        right_layout.addRow("Note:", self.notes_edit)
        btn_save = QPushButton("Salva note")
        btn_save.clicked.connect(self._save_notes)
        right_layout.addRow("", btn_save)
        self.stats_lbl = QLabel("")
        self.stats_lbl.setStyleSheet("color: gray;")
        right_layout.addRow(self.stats_lbl)
        layout.addWidget(right_group)

    def _refresh(self, notify=True):
        self.users = self.db.get_users()
        self.list_widget.clear()
        for u in self.users:
            self.list_widget.addItem(u["code"])
        if notify and self.on_change:
            self.on_change()

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

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Pasto", "Alimento (diario)", "Qtà (g)", "Alimento BDA", "Stato"])
        self.tree.setColumnWidth(0, 140)
        self.tree.setColumnWidth(1, 220)
        self.tree.setColumnWidth(2, 80)
        self.tree.setColumnWidth(3, 220)
        self.tree.setColumnWidth(4, 60)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemDoubleClicked.connect(lambda _: self._associate_bda())
        layout.addWidget(self.tree)

    def load_user(self, user_code):
        self.user_code = user_code
        self._refresh()

    def _refresh(self):
        self.tree.clear()
        if not self.user_code:
            return
        entries = sorted(
            self.db.get_entries(self.user_code, day=self.day),
            key=lambda e: (MEAL_ORDER.get(e["meal"], 99), e["id"]),
        )
        for e in entries:
            item = QTreeWidgetItem([
                e["meal"],
                e["food_name"],
                f"{e['quantity_g']:.0f}",
                e.get("bda_name") or "—",
                "✓" if e["bda_food_id"] else "—",
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, e["id"])
            color = QColor("#1a7a1a") if e["bda_food_id"] else QColor("#b05a00")
            for col in range(5):
                item.setForeground(col, color)
            self.tree.addTopLevelItem(item)

    def _selected_id(self):
        items = self.tree.selectedItems()
        return items[0].data(0, Qt.ItemDataRole.UserRole) if items else None

    def _add(self):
        if not self.user_code:
            QMessageBox.warning(self, "Attenzione", "Seleziona prima un utente.")
            return
        dlg = AddEditEntryDialog(self, default_day=self.day)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.result:
            return
        r = dlg.result
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
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.result:
            return
        r = dlg.result
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
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result is not None:
            bda_id, _ = dlg.result
            self.db.associate_bda(eid, bda_id)
            self._refresh()

    def _remove_bda(self):
        eid = self._selected_id()
        if eid is None:
            return
        self.db.associate_bda(eid, None)
        self._refresh()


class DiaryTab(QWidget):
    def __init__(self, db: Database, on_change=None):
        super().__init__()
        self.db = db
        self.on_change = on_change
        self.current_user = None
        self._users = []
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Pannello sinistro: lista utenti ───────────────────────────────────
        left = QGroupBox("Utenti")
        left_layout = QVBoxLayout(left)

        self.user_list = QListWidget()
        self.user_list.setFont(QFont("Courier", 11))
        self.user_list.currentRowChanged.connect(self._on_user_change)
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
        right_layout.addWidget(self.day_nb)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([180, 900])

        layout.addWidget(splitter)

    def refresh_users(self):
        self._users = self.db.get_users()
        current_code = self.current_user
        self.user_list.blockSignals(True)
        self.user_list.clear()
        for u in self._users:
            self.user_list.addItem(u["code"])
        if current_code:
            for i, u in enumerate(self._users):
                if u["code"] == current_code:
                    self.user_list.setCurrentRow(i)
                    break
            else:
                self.current_user = None
        self.user_list.blockSignals(False)

    def _on_user_change(self, row):
        if row < 0 or row >= len(self._users):
            return
        code = self._users[row]["code"]
        self.current_user = code
        for frm in self.day_frames:
            frm.load_user(code)

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
        row = self.user_list.currentRow()
        if row < 0:
            return
        user = self._users[row]
        reply = QMessageBox.question(
            self, "Conferma", f"Eliminare '{user['code']}' e tutto il suo diario?"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_user(user["code"])
        self.current_user = None
        for frm in self.day_frames:
            frm.load_user(None)
        self.refresh_users()
        if self.on_change:
            self.on_change()

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
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.result:
            return

        mapping = dlg.result
        imported, skipped = 0, 0

        for _, row in df.iterrows():
            try:
                user_code = str(row[mapping["user_code"]]).strip()
                day = int(float(str(row[mapping["day"]]).strip()))
                meal = str(row[mapping["meal"]]).strip()
                food = str(row[mapping["food_name"]]).strip()

                if not user_code or user_code.lower() == "nan":
                    continue
                if not food or food.lower() == "nan":
                    continue
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

        msg = f"Importate {imported} voci."
        if skipped:
            msg += f"\n{skipped} righe ignorate per errori o dati mancanti."
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

        file_m = mb.addMenu("File")
        act_bda = QAction("Carica BDA da Excel", self)
        act_bda.triggered.connect(lambda: (self.nb.setCurrentIndex(0), self.bda_tab._load_bda()))
        file_m.addAction(act_bda)
        file_m.addSeparator()
        act_exit = QAction("Esci", self)
        act_exit.triggered.connect(self.close)
        file_m.addAction(act_exit)

        help_m = mb.addMenu("Aiuto")
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

    def _about(self):
        QMessageBox.information(
            self, "Informazioni",
            f"{APP_TITLE}\n\nVersione 1.0\n\n"
            "Analizza diari alimentari su 4 giorni,\n"
            "associa ogni voce a un alimento della BDA\n"
            "e calcola i valori nutrizionali.",
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())
