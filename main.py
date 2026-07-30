#!/usr/bin/env python3
"""
Analisi Diari Alimentari
Lancia con:  python main.py
"""

import os
import sys
import json
import gzip
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
from PyQt6.QtGui import QColor, QBrush, QFont, QAction, QIcon, QKeySequence

from database import Database


def resource_path(rel: str) -> str:
    """Path di una risorsa, sia in sviluppo sia dentro il bundle PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# Dimensioni testo di default (punti). Due valori distinti, regolabili da
# «Visualizza → Dimensione testo»: uno per l'interfaccia (menu, pulsanti,
# liste) e uno per le tabelle dati (diario, riepilogo, BDA). Su macOS più
# grande, perché il rendering risulta piccolo.
_DEFAULT_UI_PT = 14 if sys.platform == "darwin" else 10
_DEFAULT_TABLE_PT = _DEFAULT_UI_PT      # font delle tabelle dati, regolabile a parte
_MIN_UI_PT, _MAX_UI_PT = 8, 28

from constants import (
    MEALS, MEAL_ORDER, DAYS, APP_TITLE, APP_VERSION, EXPORT_FORMAT, EXPORT_VERSION,
    ENERGY_LABEL, _MNOVA_COLS,
    _SKIP_BDA_COLS, _CONTENT_EXPORT_MEALS, _CONTENT_EXPORT_DAY_COLS,
    _parse_qty_grams, _qty_display, _open_excel, _parse_bda_categories,
    _category_code, _load_mnova_config, _compute_mnova,
    _compute_energy_kcal, _compute_user_totals, _compute_mnova_breakdown,
    _load_percent_config, _display_decimals,
)
from delegates import _DayFrameDelegate
from dialogs import (
    BDASearchDialog, AddEditEntryDialog, BDAImportDialog,
    PreferencesDialog, FormulaDialog, SpecialValuesDialog,
    PercentDialog, BeverageCategoriesDialog, TextSizeDialog,
    MergeConflictsDialog, FoodNutrientsDialog, GuideDialog,
)


# ── Tabs / Widgets ─────────────────────────────────────


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
        btn_users = QPushButton("Utenti con questo alimento")
        btn_users.setToolTip("Elenca gli utenti che hanno l'alimento selezionato associato nel diario.")
        btn_users.clicked.connect(self._show_users_with_food)
        tb.addWidget(btn_users)
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
        search_row.addWidget(QLabel("Categoria:"))
        self.cat_filter = QComboBox()
        self.cat_filter.setMinimumWidth(240)
        self._cat_codes_loaded = None
        self.cat_filter.currentIndexChanged.connect(self._refresh_view)
        search_row.addWidget(self.cat_filter)
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
            xl = _open_excel(path)
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

        # Importa anche le categorie merceologiche, se presenti nel file.
        cat_records = []
        try:
            cat_records = _parse_bda_categories(xl)
            if cat_records:
                self.db.import_bda_categories(cat_records)
        except Exception:
            cat_records = []

        self._refresh_view()
        progress.reset()
        cat_msg = (f"\n{len(cat_records)} categorie merceologiche importate."
                   if cat_records else
                   "\n(Nessun foglio categorie trovato nel file.)")
        QMessageBox.information(
            self, "BDA caricata",
            f"Importati {len(records):,} alimenti dal foglio '{bda_sheet}'.{cat_msg}",
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

        cat_map = self.db.get_categories_map()
        has_cats = bool(cat_map)
        self._populate_cat_filter(cat_map)
        sel_code = self.cat_filter.currentData() if has_cats else ""

        nutrient_cols = self.db.get_bda_columns()
        extra = ["Categoria"] if has_cats else []
        headers = ["Alimento"] + extra + [str(c) for c in nutrient_cols]
        self.tree.setColumnCount(len(headers))
        self.tree.setHeaderLabels(headers)
        hdr = self.tree.header()
        assert hdr is not None
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hdr.setStretchLastSection(False)
        self.tree.setColumnWidth(0, 260)
        if has_cats:
            self.tree.setColumnWidth(1, 200)
        for i in range(1 + len(extra), len(headers)):
            self.tree.setColumnWidth(i, 90)

        foods = self.db.search_bda(self.search_edit.text(), limit=100000)
        self.tree.clear()
        shown = 0
        for f in foods:
            code = _category_code(f.get("Categoria Merceologica"))
            if sel_code and code != sel_code:
                continue
            cat_cells = [(cat_map.get(code, {}).get("name_it") or "")] if has_cats else []
            vals = [f["name"]] + cat_cells + [
                ("" if f.get(c) is None else str(f[c])) for c in nutrient_cols
            ]
            item = QTreeWidgetItem(vals)
            item.setData(0, Qt.ItemDataRole.UserRole, f["id"])
            self.tree.addTopLevelItem(item)
            shown += 1

        if sel_code:
            self.status_lbl.setText(
                f"{shown:,} alimenti · {self.cat_filter.currentText()}"
            )

    def _show_users_with_food(self):
        items = self.tree.selectedItems()
        if not items:
            QMessageBox.information(self, "Utenti con alimento",
                                    "Seleziona un alimento nella lista BDA.")
            return
        fid = items[0].data(0, Qt.ItemDataRole.UserRole)
        if fid is None:
            return
        name = items[0].text(0)
        rows = self.db.users_with_bda(fid)
        if not rows:
            QMessageBox.information(self, "Utenti con alimento",
                                    f"Nessun utente ha «{name}» associato.")
            return
        lines = [f"{code}  ({n} voci)" for code, n in rows]
        box = QMessageBox(self)
        box.setWindowTitle("Utenti con alimento")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(f"{len(rows)} utenti hanno «{name}» associato.")
        box.setDetailedText("\n".join(lines))
        box.exec()

    def _populate_cat_filter(self, cat_map):
        """Popola il combo del filtro categoria (solo sotto-categorie), una volta."""
        codes = tuple(sorted(c for c, r in cat_map.items() if r.get("macro_code") != c))
        if self._cat_codes_loaded == codes:
            return
        self._cat_codes_loaded = codes
        self.cat_filter.blockSignals(True)
        self.cat_filter.clear()
        if codes:
            self.cat_filter.addItem("Tutte le categorie", "")
            for c in sorted(codes, key=lambda c: cat_map[c].get("name_it") or ""):
                self.cat_filter.addItem(cat_map[c].get("name_it") or c, c)
        self.cat_filter.blockSignals(False)


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
        self.code_lbl.setStyleSheet("font-weight: bold;")
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
    def __init__(self, db: Database, day: int, on_change=None):
        super().__init__()
        self.db = db
        self.day = day
        self.on_change = on_change
        self.user_code = None
        self._build()

    def _notify(self):
        if self.on_change:
            self.on_change()

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

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        tb.addWidget(sep2)

        btn_nutr = QPushButton("Valori nutrizionali")
        btn_nutr.setToolTip("Mostra i valori nutrizionali calcolati per la voce selezionata.")
        btn_nutr.clicked.connect(self._show_food_nutrients)
        tb.addWidget(btn_nutr)
        tb.addStretch()
        layout.addLayout(tb)

        # 0=Pasto 1=Ora 2=Luogo 3=Alimento 4=Note 5=Qtà rif. 6=Qtà(g) 7=BDA 8=Stato 9=NOVA 10=mNOVA
        self._qty_col   = 6
        self._nova_col  = 9
        self._mnova_col = 10
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            "Pasto", "Ora", "Luogo", "Alimento (diario)", "Note",
            "Qtà rif.", "Qtà (g)", "Alimento BDA", "Stato", "NOVA", "mNOVA",
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
        mnova_cfg = _load_mnova_config(self.db)

        for e in entries:
            nova = e.get("nova")
            bda_data = bda_cache.get(e["bda_food_id"]) if e.get("bda_food_id") else None
            resolved = bda_data is not None                 # associazione valida
            orphaned = bool(e.get("bda_food_id")) and not resolved  # link rotto
            mnova = _compute_mnova(nova, bda_data, mnova_cfg)
            item = QTreeWidgetItem([
                e["meal"],
                e.get("ora") or "",
                e.get("luogo") or "",
                e["food_name"],
                e.get("notes") or "",
                e.get("qty_raw") or "",
                _qty_display(e.get("quantity_g")),
                e.get("bda_name") or "—",
                "✓" if resolved else ("⚠" if orphaned else "—"),
                str(nova) if nova is not None else "—",
                mnova or "—",
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, e["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            if resolved:
                color = QColor("#6dbf6d")
            elif orphaned:
                color = QColor("#d08a00")  # arancione: era associato, link da rifare
            else:
                color = QColor("#ffffff")
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
        self._notify()

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
        self._notify()

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
            self._notify()

    def _remove_bda(self):
        eid = self._selected_id()
        if eid is None:
            return
        self.db.associate_bda(eid, None)
        self._refresh()
        self._notify()

    def _show_food_nutrients(self):
        eid = self._selected_id()
        if eid is None:
            QMessageBox.information(self, "Valori nutrizionali", "Seleziona una voce del diario.")
            return
        entry = next((e for e in self.db.get_entries(self.user_code, day=self.day)
                      if e["id"] == eid), None)
        if entry is None:
            return
        FoodNutrientsDialog(self, self.db, entry).exec()

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
            mnova = _compute_mnova(nova, bda_data, _load_mnova_config(self.db))
            self.tree.blockSignals(True)
            item.setText(self._nova_col, str(nova) if nova is not None else "—")
            item.setText(self._mnova_col, mnova or "—")
            self.tree.blockSignals(False)


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

        # Una scheda per giorno (1-4) e una per la media sui 4.
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._scopes = list(DAYS) + ["media"]
        self.nutri_tables = {}   # scope → QTableWidget nutrienti
        self.mnova_tables = {}   # scope → QTableWidget mNOVA
        for scope in self._scopes:
            page = QWidget()
            pl = QVBoxLayout(page)
            pl.setContentsMargins(6, 6, 6, 6)

            nt = QTableWidget()
            nt.setAlternatingRowColors(True)
            nt.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            nt.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            nthdr = nt.horizontalHeader()
            assert nthdr is not None
            nthdr.setStretchLastSection(False)
            self.nutri_tables[scope] = nt
            pl.addWidget(nt, 1)

            mlbl = QLabel("Ripartizione per categoria mNOVA")
            mlbl.setStyleSheet("font-weight: bold; margin-top: 4px;")
            pl.addWidget(mlbl)
            pl.addWidget(self._make_mnova_table(scope))

            title = "Media 4 giorni" if scope == "media" else f"Giorno {scope}"
            self.tabs.addTab(page, title)

        self.warn_lbl = QLabel("")
        self.warn_lbl.setStyleSheet("color: darkorange;")
        self.warn_lbl.setWordWrap(True)
        layout.addWidget(self.warn_lbl)

    def _make_mnova_table(self, key):
        """Crea una tabella mNOVA (3 righe × categorie) per un giorno o la media."""
        t = QTableWidget(3, len(_MNOVA_COLS) + 1)
        t.setHorizontalHeaderLabels([""] + _MNOVA_COLS)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        t.setFixedHeight(118)
        vh = t.verticalHeader()
        if vh is not None:
            vh.setVisible(False)
        hdr = t.horizontalHeader()
        assert hdr is not None
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(1, len(_MNOVA_COLS) + 1):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        self.mnova_tables[key] = t
        return t

    def load_user(self, user_code):
        self.user_code = user_code
        self._refresh()

    def _refresh(self):
        for t in self.nutri_tables.values():
            t.clearContents()
            t.setRowCount(0)
        for t in self.mnova_tables.values():
            t.clearContents()
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

        # Valori per scheda: ogni giorno e la media sui 4 (somma ÷ numero giorni).
        n = len(DAYS)
        scope_values = {d: totals[d] for d in DAYS}
        scope_values["media"] = {
            c: sum(totals[d].get(c, 0.0) for d in DAYS) / n for c in nutrient_cols
        }

        dec = _display_decimals(self.db)
        for scope in self._scopes:
            self._fill_nutri_table(self.nutri_tables[scope], scope_values[scope],
                                   nutrient_cols, percent_cfg, show_pct, dec)

        self._fill_mnova_table(dec)

        warn_parts = [
            f"Giorno {d}: {missing[d]} voci senza BDA"
            for d in DAYS if missing[d] > 0
        ]
        if warn_parts:
            self.warn_lbl.setText("⚠ Non calcolate — " + ", ".join(warn_parts))

    def _fill_nutri_table(self, table, values, nutrient_cols, percent_cfg, show_pct, dec=2):
        """Popola una tabella nutrienti (Nutriente | Valore | %) per uno scope."""
        headers = ["Nutriente", "Valore"] + (["%"] if show_pct else [])
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        hdr = table.horizontalHeader()
        assert hdr is not None
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, len(headers)):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)

        energy = _compute_energy_kcal(values)
        rows_data = [(ENERGY_LABEL, energy, None, True)]
        rows_data += [(col, values.get(col, 0.0), percent_cfg.get(col), False)
                      for col in nutrient_cols]

        def _num_item(text, bold):
            it = QTableWidgetItem(text)
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if bold:
                f = QFont(table.font())
                f.setBold(True)
                it.setFont(f)
            return it

        table.setRowCount(len(rows_data))
        for row, (label, val, cfg, bold) in enumerate(rows_data):
            # % = valore * fattore / denominatore * 100 (denom vuoto → energia)
            factor, denom = cfg if cfg else (None, "")
            den = energy if not denom else values.get(denom, 0.0)
            pct = (val * factor / den * 100.0) if (factor is not None and den) else None

            name_item = QTableWidgetItem(str(label))
            if bold:
                f = QFont(table.font())
                f.setBold(True)
                name_item.setFont(f)
            table.setItem(row, 0, name_item)
            table.setItem(row, 1, _num_item(f"{val:.{dec}f}", bold))
            if show_pct:
                table.setItem(row, 2, _num_item("" if pct is None else f"{pct:.{dec}f}%", bold))

    def _fill_mnova_table(self, dec=2):
        """Popola le tabelle di ripartizione mNOVA (un giorno per tabella + media)."""
        per_day, media = _compute_mnova_breakdown(self.db, self.user_code)
        data = {d: per_day[d] for d in DAYS}
        data["media"] = media
        for key, (grams, kcal) in data.items():
            self._fill_one_mnova(self.mnova_tables[key], grams, kcal, dec)

    def _fill_one_mnova(self, table, grams, kcal, dec=2):
        total_kcal = kcal["1"] + kcal["2"] + kcal["3a+3b"] + kcal["4a+4b"]

        def _cell(text, bold=False, align_right=True):
            it = QTableWidgetItem(text)
            if align_right:
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if bold:
                f = QFont(table.font())
                f.setBold(True)
                it.setFont(f)
            return it

        row_defs = [
            ("g/day",          lambda c: f"{grams[c]:.{dec}f}"),
            ("Kcal/day",       lambda c: f"{kcal[c]:.{dec}f}"),
            ("%Kcal/Kcaltot",  lambda c: f"{(kcal[c] / total_kcal * 100):.{dec}f}%" if total_kcal else f"{0:.{dec}f}%"),
        ]
        for r, (label, fmt) in enumerate(row_defs):
            table.setItem(r, 0, _cell(label, bold=True, align_right=False))
            for i, col in enumerate(_MNOVA_COLS, start=1):
                table.setItem(r, i, _cell(fmt(col)))

    def _compute_totals(self):
        assert self.user_code is not None
        return _compute_user_totals(self.db, self.user_code)


# Colore del testo per lo stato di associazione di un utente nella lista.
# (Il giallo puro come testo è illeggibile: per "in corso" si usa un ambra scuro.)
_ASSOC_FG_PARTIAL = QColor("#b8860b")  # in corso (ambra/giallo scuro)
_ASSOC_FG_FULL = QColor("#2e7d32")     # tutte associate (verde)


def _status_class(tot, assoc):
    """Classe di stato: 'none' (da fare), 'partial' (in corso), 'full' (fatto)."""
    if tot == 0 or assoc == 0:
        return "none"
    return "partial" if assoc < tot else "full"


def _assoc_fg(tot, assoc):
    """Pennello per il colore del testo in base allo stato (default se 'none')."""
    cls = _status_class(tot, assoc)
    if cls == "full":
        return QBrush(_ASSOC_FG_FULL)
    if cls == "partial":
        return QBrush(_ASSOC_FG_PARTIAL)
    return QBrush()


class DiaryTab(QWidget):
    def __init__(self, db: Database, on_change=None):
        super().__init__()
        self.db = db
        self.on_change = on_change
        self.current_user = None
        self._users = []
        self._status: dict = {}          # code → (tot, assoc)
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

        self.status_filter = QComboBox()
        self.status_filter.addItem("Tutti gli stati", None)
        self.status_filter.addItem("Da fare", "none")
        self.status_filter.addItem("In corso", "partial")
        self.status_filter.addItem("Completati", "full")
        self.status_filter.currentIndexChanged.connect(self._filter_users)
        left_layout.addWidget(self.status_filter)

        self.user_list = QListWidget()
        self.user_list.currentRowChanged.connect(self._on_user_change)
        self.user_list.itemChanged.connect(self._on_check_changed)
        left_layout.addWidget(self.user_list)

        legend = QLabel(
            '<span style="color:#2e7d32">■ associato</span> &nbsp; '
            '<span style="color:#b8860b">■ in corso</span> &nbsp; '
            '<span style="color:gray">■ non assoc.</span>'
        )
        legend.setStyleSheet("font-size: 11px;")
        left_layout.addWidget(legend)

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

        right_top = QHBoxLayout()
        self.btn_toggle_users = QPushButton("◀ Nascondi utenti")
        self.btn_toggle_users.setToolTip("Mostra/nascondi la barra degli utenti")
        self.btn_toggle_users.clicked.connect(self._toggle_users_panel)
        right_top.addWidget(self.btn_toggle_users)
        right_top.addStretch()
        btn_verify = QPushButton("Verifica / riassegna BDA")
        btn_verify.setToolTip(
            "Ricontrolla le associazioni dell'utente aperto: ricollega per Codice "
            "Alimento e segnala alimenti non più in BDA o con valori modificati."
        )
        btn_verify.clicked.connect(self._verify_bda)
        right_top.addWidget(btn_verify)
        right_layout.addLayout(right_top)

        self.day_nb = QTabWidget()
        self.day_frames = []
        for d in DAYS:
            frm = DayFrame(self.db, d, on_change=self._update_user_color)
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
        self.splitter = splitter
        self._saved_sizes = None

        layout.addWidget(splitter)

    def _toggle_users_panel(self):
        """Comprime/espande la barra utenti (alternativa al trascinamento)."""
        if self.users_group.isVisible():
            self._saved_sizes = self.splitter.sizes()
            self.users_group.setVisible(False)
            self.btn_toggle_users.setText("▶ Mostra utenti")
        else:
            self.users_group.setVisible(True)
            if self._saved_sizes:
                self.splitter.setSizes(self._saved_sizes)
            self.btn_toggle_users.setText("◀ Nascondi utenti")

    def _filter_users(self, *_):
        q = self.search_user.text().strip().lower()
        sel = self.status_filter.currentData()   # None | 'none' | 'partial' | 'full'
        for i, u in enumerate(self._users):
            item = self.user_list.item(i)
            if not item:
                continue
            code = u["code"]
            hidden = bool(q) and q not in code.lower()
            if sel and _status_class(*self._status.get(code, (0, 0))) != sel:
                hidden = True
            item.setHidden(hidden)

    def refresh_users(self):
        self._users = self.db.get_users()
        self.users_group.setTitle(f"Utenti ({len(self._users)})")
        current_code = self.current_user
        self._status = self.db.count_entries_all()
        self.user_list.blockSignals(True)
        self.user_list.clear()
        for u in self._users:
            item = QListWidgetItem(u["code"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            state = Qt.CheckState.Checked if u["code"] in self._checked_users else Qt.CheckState.Unchecked
            item.setCheckState(state)
            tot, assoc = self._status.get(u["code"], (0, 0))
            item.setForeground(_assoc_fg(tot, assoc))
            item.setToolTip(f"Voci associate: {assoc}/{tot}")
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

    def _update_user_color(self):
        """Ricolora l'utente corrente in base allo stato di associazione."""
        if not self.current_user:
            return
        item = self.user_list.item(self.user_list.currentRow())
        if item is None or item.text() != self.current_user:
            return
        tot, assoc = self.db.count_entries(self.current_user)
        self._status[self.current_user] = (tot, assoc)
        item.setForeground(_assoc_fg(tot, assoc))
        item.setToolTip(f"Voci associate: {assoc}/{tot}")

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

    def _verify_bda(self):
        if not self.current_user:
            QMessageBox.information(self, "Verifica BDA", "Seleziona prima un utente.")
            return
        if self.db.count_bda() == 0:
            QMessageBox.warning(self, "Verifica BDA", "Nessuna BDA caricata.")
            return

        rep = self.db.reassign_user_bda(self.current_user)
        for frm in self.day_frames:
            frm._refresh()
        self.nutri_frame._refresh()
        if self.on_change:
            self.on_change()

        summary = (
            f"Utente: {self.current_user}\n\n"
            f"✓ Già corrette:        {rep['ok']}\n"
            f"🔗 Ri-collegate:        {len(rep['relinked'])}\n"
            f"✎ Valori modificati:   {len(rep['changed'])}\n"
            f"⚠ Non più in BDA:      {len(rep['missing'])}"
        )
        box = QMessageBox(self)
        box.setWindowTitle("Verifica / riassegna BDA")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(summary)
        detail = []
        if rep["relinked"]:
            detail.append("RI-COLLEGATE (id aggiornato):\n  " + "\n  ".join(rep["relinked"]))
        if rep["changed"]:
            detail.append("VALORI MODIFICATI dall'associazione:\n  " + "\n  ".join(rep["changed"]))
        if rep["missing"]:
            detail.append("NON PIÙ IN BDA (da ri-associare a mano):\n  " + "\n  ".join(rep["missing"]))
        if detail:
            box.setDetailedText("\n\n".join(detail))
        box.exec()

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

        # Colonne della ripartizione mNOVA (grammi, kcal e %Kcal/Kcaltot per
        # categoria), aggiunte di seguito ai valori dei nutrienti.
        mnova_g_cols = [f"mNOVA {c} (g)" for c in _MNOVA_COLS]
        mnova_k_cols = [f"mNOVA {c} (kcal)" for c in _MNOVA_COLS]
        mnova_p_cols = [f"mNOVA {c} (%Kcal/Kcaltot)" for c in _MNOVA_COLS]
        mnova_cols = mnova_g_cols + mnova_k_cols + mnova_p_cols

        # Colonne con valori decimali: ricevono il formato "almeno 2 cifre".
        float_cols = {ENERGY_LABEL}
        float_cols.update(nutrient_cols)
        float_cols.update(_pct_label(c) for c in nutrient_cols if c in percent_cfg)
        float_cols.update(mnova_cols)

        rows = []
        for user_code in sorted(self._checked_users):
            totals, missing = _compute_user_totals(self.db, user_code)
            mnova_per_day, _ = _compute_mnova_breakdown(self.db, user_code)
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
                grams, kcal = mnova_per_day[day]
                tot_kcal = kcal["1"] + kcal["2"] + kcal["3a+3b"] + kcal["4a+4b"]
                for c in _MNOVA_COLS:
                    row[f"mNOVA {c} (g)"] = round(grams[c], 4)
                for c in _MNOVA_COLS:
                    row[f"mNOVA {c} (kcal)"] = round(kcal[c], 4)
                for c in _MNOVA_COLS:
                    row[f"mNOVA {c} (%Kcal/Kcaltot)"] = (
                        round(kcal[c] / tot_kcal * 100, 4) if tot_kcal else None
                    )
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
        avg_value_cols += mnova_cols
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

        dec = _display_decimals(self.db)
        num_fmt = "0." + "0" * dec if dec > 0 else "0"

        def _apply_decimals(worksheet, columns, float_names):
            """Formato celle coerente coi decimali scelti nelle preferenze."""
            for ci, cname in enumerate(columns, start=1):
                if cname not in float_names:
                    continue
                for r in range(2, worksheet.max_row + 1):
                    worksheet.cell(row=r, column=ci).number_format = num_fmt

        try:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Dettaglio giorni", index=False)
                df_avg.to_excel(writer, sheet_name="Media 4 giorni", index=False)
                _apply_decimals(writer.sheets["Dettaglio giorni"], list(df.columns), float_cols)
                _apply_decimals(writer.sheets["Media 4 giorni"], list(df_avg.columns), float_cols_avg)
            QMessageBox.information(self, "Esporta", f"Esportazione completata:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Errore", f"Impossibile salvare il file:\n{exc}")

    def _import_content_export(self):
        """Importa il file Content_Export (6 fogli concatenati, una riga per
        utente, 4 giorni per riga) e chiede se sostituire o unire gli utenti."""
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
        data_rows = df_full.iloc[4:].reset_index(drop=True)
        ncols = df_full.shape[1]

        notes_map = {u["code"]: u.get("notes", "") for u in self.db.get_users()}
        users_order, seen = [], set()
        entries, day_meta = [], []
        total = len(data_rows)

        progress = QProgressDialog("Lettura Content Export in corso…", None, 0, total, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        for row_idx, (_, row) in enumerate(data_rows.iterrows()):
            user_code = str(row.iloc[0]).strip()
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

                if user_code not in seen:
                    seen.add(user_code)
                    users_order.append(user_code)
                day_meta.append({"user_code": user_code, "day": day_num,
                                 "date_label": date_str})

                for meal_name, food_offset, max_items in _CONTENT_EXPORT_MEALS:
                    ora_col = day_col + food_offset - 2
                    luogo_col = day_col + food_offset - 1
                    meal_ora = meal_luogo = ""
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

                        entries.append({
                            "user_code": user_code, "day": day_num, "meal": meal_name,
                            "food_name": food_name,
                            "quantity_g": _parse_qty_grams(qty_raw),
                            "notes": desc, "ora": meal_ora, "luogo": meal_luogo,
                            "qty_raw": qty_raw,
                        })

            if row_idx % 10 == 0:
                progress.setValue(row_idx)
                QApplication.processEvents()
        progress.setValue(total)

        if not users_order:
            QMessageBox.information(self, "Content Export",
                                   "Nessun utente valido trovato nel file.")
            return

        data = {
            "users": [{"code": c, "notes": notes_map.get(c, "")} for c in users_order],
            "diary_entries": entries,
            "diary_day_meta": day_meta,
        }

        box = QMessageBox(self)
        box.setWindowTitle("Importa Content Export")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"Il file contiene {len(users_order)} utenti e "
                    f"{len(entries)} voci di diario.")
        box.setInformativeText(
            "<b>Sostituisci</b>: rimpiazza il diario degli utenti presenti nel file "
            "(gli altri utenti restano invariati).<br>"
            "<b>Unisci</b>: aggiunge i nuovi; quelli già presenti senza associazioni "
            "vengono aggiornati, per quelli già associati chiede conferma."
        )
        btn_replace = box.addButton("Sostituisci", QMessageBox.ButtonRole.DestructiveRole)
        btn_merge = box.addButton("Unisci", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Annulla", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()

        if clicked is btn_replace:
            overwrite = list(users_order)   # sostituisci tutti gli utenti del file
        elif clicked is btn_merge:
            analysis = self.db.merge_analysis(data)
            overwrite = []
            if analysis["conflict"]:
                cdlg = MergeConflictsDialog(
                    self, analysis["conflict"],
                    n_new=len(analysis["new"]),
                    n_auto=len(analysis["auto_update"]),
                )
                if cdlg.exec() != QDialog.DialogCode.Accepted:
                    return
                overwrite = cdlg.selected
        else:
            return

        rep = self.db.apply_merge_project(data, overwrite)
        self.refresh_users()
        if self.on_change:
            self.on_change()
        if self.current_user:
            self._on_user_change(self.user_list.currentRow())

        applied = set(rep["added"]) | set(rep["updated"])
        n_voci = sum(1 for e in entries if e["user_code"] in applied)
        n_add, n_upd, n_kept = len(rep["added"]), len(rep["updated"]), len(rep["kept"])
        msg = ("Aggiunti: %d\nAggiornati: %d\nMantenuti invariati: %d\n\n"
               "Voci importate: %d" % (n_add, n_upd, n_kept, n_voci))
        if rep["kept"]:
            msg += "\n\nMantenuti (non sovrascritti):\n  " + "\n  ".join(rep["kept"])
        QMessageBox.information(self, "Content Export importato", msg)

# ── Main window ───────────────────────────────────────────────────────────────

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1150, 700)
        self.setMinimumSize(850, 520)

        self.db = Database()
        self._load_font_prefs()
        self._apply_interface_font()     # font interfaccia (globale) prima di costruire
        self._build_menu()
        self._build_ui()
        self._apply_table_font()         # font tabelle dati (dopo aver creato le viste)
        self.diary_tab.refresh_users()

    def _build_menu(self):
        mb = self.menuBar()
        assert mb is not None

        file_m = mb.addMenu("File")
        assert file_m is not None
        act_bda = QAction("Carica BDA da Excel", self)
        act_bda.triggered.connect(lambda: (self.nb.setCurrentWidget(self.bda_tab), self.bda_tab._load_bda()))
        file_m.addAction(act_bda)
        file_m.addSeparator()

        act_exp_cfg = QAction("Esporta configurazione…", self)
        act_exp_cfg.triggered.connect(self._export_config)
        file_m.addAction(act_exp_cfg)
        act_imp_cfg = QAction("Importa configurazione…", self)
        act_imp_cfg.triggered.connect(self._import_config)
        file_m.addAction(act_imp_cfg)
        file_m.addSeparator()

        act_exp_prj = QAction("Esporta progetto…", self)
        act_exp_prj.triggered.connect(self._export_project)
        file_m.addAction(act_exp_prj)
        act_exp_sel = QAction("Esporta progetto (utenti selezionati)…", self)
        act_exp_sel.triggered.connect(self._export_selected_project)
        file_m.addAction(act_exp_sel)
        act_imp_prj = QAction("Importa progetto…", self)
        act_imp_prj.triggered.connect(self._import_project)
        file_m.addAction(act_imp_prj)
        file_m.addSeparator()

        act_exit = QAction("Esci", self)
        act_exit.triggered.connect(self.close)
        file_m.addAction(act_exit)

        pref_m = mb.addMenu("Preferenze")
        assert pref_m is not None
        act_mnova = QAction("Cutoff mNOVA…", self)
        act_mnova.triggered.connect(self._open_preferences)
        pref_m.addAction(act_mnova)
        act_bev = QAction("Bevande (categorie)…", self)
        act_bev.triggered.connect(self._open_beverages)
        pref_m.addAction(act_bev)
        act_formula = QAction("Formula nutrizionale…", self)
        act_formula.triggered.connect(self._open_formula)
        pref_m.addAction(act_formula)
        act_special = QAction("Valori speciali (-2 / -3)…", self)
        act_special.triggered.connect(self._open_special_values)
        pref_m.addAction(act_special)
        act_percent = QAction("Percentuali…", self)
        act_percent.triggered.connect(self._open_percent)
        pref_m.addAction(act_percent)
        act_decimals = QAction("Decimali valori…", self)
        act_decimals.triggered.connect(self._open_decimals)
        pref_m.addAction(act_decimals)

        view_m = mb.addMenu("Visualizza")
        assert view_m is not None
        act_text_size = QAction("Dimensione testo…", self)
        act_text_size.triggered.connect(self._open_text_size)
        view_m.addAction(act_text_size)
        view_m.addSeparator()
        act_bigger = QAction("Aumenta testo", self)
        act_bigger.setShortcut(QKeySequence.StandardKey.ZoomIn)
        act_bigger.triggered.connect(lambda: self._change_text_size(+1))
        view_m.addAction(act_bigger)
        act_smaller = QAction("Riduci testo", self)
        act_smaller.setShortcut(QKeySequence.StandardKey.ZoomOut)
        act_smaller.triggered.connect(lambda: self._change_text_size(-1))
        view_m.addAction(act_smaller)
        act_reset_text = QAction("Reimposta dimensione testo", self)
        act_reset_text.triggered.connect(self._reset_text_size)
        view_m.addAction(act_reset_text)

        help_m = mb.addMenu("Aiuto")
        assert help_m is not None
        act_guide = QAction("Guida / Manuale", self)
        act_guide.triggered.connect(self._show_guide)
        help_m.addAction(act_guide)
        act_about = QAction("Informazioni", self)
        act_about.triggered.connect(self._about)
        help_m.addAction(act_about)

    # ── Dimensione testo: interfaccia e tabelle, separate ─────────────────

    @staticmethod
    def _clamp_pt(pt):
        return max(_MIN_UI_PT, min(_MAX_UI_PT, int(pt)))

    def _read_pt(self, key, default):
        raw = self.db.get_setting(key)
        try:
            return self._clamp_pt(raw) if raw else default
        except (TypeError, ValueError):
            return default

    def _load_font_prefs(self):
        self._ui_font_pt = self._read_pt("ui_font_pt", _DEFAULT_UI_PT)
        self._table_font_pt = self._read_pt("table_font_pt", _DEFAULT_TABLE_PT)

    def _data_view_widgets(self):
        """Le tabelle/alberi dei dati (diario, riepilogo, BDA)."""
        views = []
        if getattr(self, "bda_tab", None):
            views.append(self.bda_tab.tree)
        dt = getattr(self, "diary_tab", None)
        if dt:
            views += [frm.tree for frm in dt.day_frames]
            nf = dt.nutri_frame
            views += list(nf.nutri_tables.values()) + list(nf.mnova_tables.values())
        return views

    def _apply_interface_font(self):
        """Font dell'interfaccia: default app + propagazione a tutti i widget."""
        pt = self._ui_font_pt
        f = QApplication.font()
        f.setPointSize(pt)
        QApplication.setFont(f)
        # setFont() a runtime non ripropaga ai widget esistenti: forziamo.
        for w in QApplication.allWidgets():
            wf = w.font()
            if wf.pointSize() != pt:
                wf.setPointSize(pt)
                w.setFont(wf)

    def _apply_table_font(self):
        """Font delle sole tabelle dati (sovrascrive quello d'interfaccia)."""
        pt = self._table_font_pt
        for v in self._data_view_widgets():
            wf = v.font()
            if wf.pointSize() != pt:
                wf.setPointSize(pt)
                v.setFont(wf)

    def _reload_current_user(self):
        """Ricarica l'utente corrente per rigenerare le celle con font esplicito."""
        dt = getattr(self, "diary_tab", None)
        if dt and dt.current_user:
            dt._on_user_change(dt.user_list.currentRow())

    def _set_ui_font_pt(self, pt, persist=True):
        self._ui_font_pt = self._clamp_pt(pt)
        self._apply_interface_font()
        self._apply_table_font()       # ripristina la misura tabelle dopo la propagazione
        self._reload_current_user()
        if persist:
            self.db.set_setting("ui_font_pt", self._ui_font_pt)

    def _set_table_font_pt(self, pt, persist=True):
        self._table_font_pt = self._clamp_pt(pt)
        self._apply_table_font()
        self._reload_current_user()
        if persist:
            self.db.set_setting("table_font_pt", self._table_font_pt)

    def _change_text_size(self, delta):
        self._set_ui_font_pt(self._ui_font_pt + delta)
        self._set_table_font_pt(self._table_font_pt + delta)

    def _reset_text_size(self):
        self._set_ui_font_pt(_DEFAULT_UI_PT)
        self._set_table_font_pt(_DEFAULT_TABLE_PT)

    def _open_text_size(self):
        orig_ui, orig_table = self._ui_font_pt, self._table_font_pt
        dlg = TextSizeDialog(
            self, orig_ui, orig_table, _DEFAULT_UI_PT, _DEFAULT_TABLE_PT,
            min_pt=_MIN_UI_PT, max_pt=_MAX_UI_PT,
            on_ui=lambda pt: self._set_ui_font_pt(pt, persist=False),
            on_table=lambda pt: self._set_table_font_pt(pt, persist=False),
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._set_ui_font_pt(dlg.value_ui, persist=True)
            self._set_table_font_pt(dlg.value_table, persist=True)
        else:
            self._set_ui_font_pt(orig_ui, persist=False)
            self._set_table_font_pt(orig_table, persist=False)

    def _build_ui(self):
        self.nb = QTabWidget()
        self.setCentralWidget(self.nb)

        self.bda_tab = BDATab(self.db)
        self.users_tab = UsersTab(
            self.db,
            on_change=lambda: self.diary_tab.refresh_users() if hasattr(self, "diary_tab") else None,
        )
        self.diary_tab = DiaryTab(
            self.db,
            on_change=lambda: self.users_tab._refresh(notify=False),
        )

        # Ordine schede: Diari, BDA, Utenti
        self.nb.addTab(self.diary_tab, "  Diari  ")
        self.nb.addTab(self.bda_tab, "  BDA  ")
        self.nb.addTab(self.users_tab, "  Utenti  ")

    def _open_preferences(self):
        dlg = PreferencesDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted and self.diary_tab.current_user:
            row = self.diary_tab.user_list.currentRow()
            self.diary_tab._on_user_change(row)

    def _open_beverages(self):
        dlg = BeverageCategoriesDialog(self, self.db)
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

    def _open_decimals(self):
        current = _display_decimals(self.db)
        n, ok = QInputDialog.getInt(
            self, "Decimali valori",
            "Numero di decimali per i valori nutrizionali\n(riepilogo e ripartizione mNOVA):",
            current, 0, 6, 1,
        )
        if ok:
            self.db.set_setting("display_decimals", n)
            self.diary_tab.nutri_frame._refresh()

    # ── Import / Export ───────────────────────────────────────────────────

    def _refresh_all(self):
        """Ricarica tutte le tab dopo un import."""
        self.bda_tab._refresh_view()
        self.users_tab._refresh(notify=False)
        self.diary_tab.refresh_users()

    def _read_export_file(self, path):
        """Legge e valida un file di export (.json o .json.gz, auto-rilevato).
        Ritorna il dict o None (con avviso)."""
        try:
            with open(path, "rb") as f:
                raw = f.read()
            if raw[:2] == b"\x1f\x8b":          # magic gzip
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Errore lettura file", str(exc))
            return None
        if not isinstance(data, dict) or data.get("format") != EXPORT_FORMAT:
            QMessageBox.warning(
                self, "File non valido",
                "Il file selezionato non è un export di Diario Alimentare.",
            )
            return None
        return data

    def _write_json(self, path, payload):
        """Salva il payload come JSON; se il path finisce per .gz, comprime con gzip."""
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            text = json.dumps(payload, ensure_ascii=False, indent=2)
            if path.lower().endswith(".gz"):
                with gzip.open(path, "wt", encoding="utf-8") as f:
                    f.write(text)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
        except OSError as exc:
            QMessageBox.critical(self, "Errore salvataggio", str(exc))
            return False
        finally:
            QApplication.restoreOverrideCursor()
        return True

    def _export_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Esporta configurazione", "configurazione.json", "JSON (*.json)")
        if not path:
            return
        settings = self.db.get_all_settings()
        payload = {"format": EXPORT_FORMAT, "kind": "config",
                   "version": EXPORT_VERSION, "settings": settings}
        if self._write_json(path, payload):
            QMessageBox.information(
                self, "Configurazione esportata",
                f"{len(settings)} preferenze salvate in:\n{path}")

    def _import_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importa configurazione", "",
            "JSON (*.json *.json.gz);;Tutti i file (*.*)")
        if not path:
            return
        data = self._read_export_file(path)
        if data is None:
            return
        settings = data.get("settings")
        if not isinstance(settings, dict) or not settings:
            QMessageBox.warning(self, "Niente da importare",
                                "Il file non contiene una configurazione.")
            return
        self.db.import_settings(settings)
        self._refresh_all()
        QMessageBox.information(self, "Configurazione importata",
                                f"{len(settings)} preferenze applicate.")

    def _export_project(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Esporta progetto", "progetto.json.gz",
            "JSON compresso (*.json.gz);;JSON (*.json)")
        if not path:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            data = self.db.export_data(include_work=True, include_settings=True,
                                       include_bda=True)
        finally:
            QApplication.restoreOverrideCursor()
        payload = {"format": EXPORT_FORMAT, "kind": "project",
                   "version": EXPORT_VERSION, **data}
        if self._write_json(path, payload):
            QMessageBox.information(
                self, "Progetto esportato",
                f"Esportati {len(data.get('users', [])):,} utenti, "
                f"{len(data.get('diary_entries', [])):,} voci di diario e "
                f"{len(data.get('bda_foods', [])):,} alimenti BDA in:\n{path}")

    def _export_selected_project(self):
        codes = sorted(self.diary_tab._checked_users)
        if not codes:
            QMessageBox.information(
                self, "Esporta progetto (selezionati)",
                "Nessun utente selezionato.\nSpunta gli utenti da esportare "
                "nell'elenco della scheda Diari.")
            return
        default = f"progetto_{len(codes)}_utenti.json.gz"
        path, _ = QFileDialog.getSaveFileName(
            self, "Esporta progetto (utenti selezionati)", default,
            "JSON compresso (*.json.gz);;JSON (*.json)")
        if not path:
            return
        data = self.db.export_users(codes)
        payload = {"format": EXPORT_FORMAT, "kind": "project",
                   "version": EXPORT_VERSION, **data}
        if self._write_json(path, payload):
            QMessageBox.information(
                self, "Progetto esportato",
                f"Esportati {len(data['users'])} utenti selezionati e "
                f"{len(data['diary_entries'])} voci di diario in:\n{path}\n\n"
                "File 'leggero' (senza BDA né configurazione), pensato per l'unione "
                "sull'altro computer con «Importa progetto → Unisci».")

    def _import_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importa progetto", "",
            "JSON (*.json *.json.gz);;Tutti i file (*.*)")
        if not path:
            return
        data = self._read_export_file(path)
        if data is None:
            return

        n_users = len(data.get("users", []))
        n_entries = len(data.get("diary_entries", []))
        has_bda = "bda_foods" in data
        has_cfg = "settings" in data
        parts = [f"{n_users} utenti", f"{n_entries} voci di diario"]
        if has_bda:
            parts.append(f"{len(data['bda_foods']):,} alimenti BDA")
        if has_cfg:
            parts.append("la configurazione")

        box = QMessageBox(self)
        box.setWindowTitle("Importa progetto")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("Il file contiene " + ", ".join(parts) + ".")
        box.setInformativeText(
            "<b>Sostituisci tutto</b>: rimpiazza i dati attuali con quelli del file"
            + (" (BDA e configurazione comprese)." if has_bda or has_cfg else ".")
            + "<br><b>Unisci</b>: aggiunge i nuovi utenti; quelli già presenti senza "
            "associazioni vengono aggiornati, per quelli già associati chiede conferma. "
            "Non tocca BDA né configurazione."
        )
        btn_replace = box.addButton("Sostituisci tutto", QMessageBox.ButtonRole.DestructiveRole)
        btn_merge = box.addButton("Unisci", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Annulla", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()

        if clicked is btn_replace:
            self.db.replace_project(data)
            self._refresh_all()
            QMessageBox.information(self, "Progetto importato",
                                    "I dati attuali sono stati sostituiti.")
        elif clicked is btn_merge:
            analysis = self.db.merge_analysis(data)
            overwrite = []
            if analysis["conflict"]:
                cdlg = MergeConflictsDialog(
                    self, analysis["conflict"],
                    n_new=len(analysis["new"]),
                    n_auto=len(analysis["auto_update"]),
                )
                if cdlg.exec() != QDialog.DialogCode.Accepted:
                    return  # annullato → nessuna modifica
                overwrite = cdlg.selected

            rep = self.db.apply_merge_project(data, overwrite)
            self._refresh_all()
            msg = (f"Aggiunti: {len(rep['added'])}\n"
                   f"Aggiornati: {len(rep['updated'])}\n"
                   f"Mantenuti invariati: {len(rep['kept'])}")
            if rep["kept"]:
                msg += "\n\nMantenuti (non sovrascritti):\n  " + "\n  ".join(rep["kept"])
            msg += ("\n\nSe gli alimenti non risultano associati, usa "
                    "«Verifica / riassegna BDA».")
            QMessageBox.information(self, "Progetto unito", msg)

    def _show_guide(self):
        path = resource_path("MANUALE.md")
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            QMessageBox.warning(self, "Guida", "File della guida (MANUALE.md) non trovato.")
            return
        GuideDialog(self, text).exec()

    def _about(self):
        QMessageBox.information(
            self, "Informazioni",
            f"{APP_TITLE}\n\nVersione {APP_VERSION}\n\n"
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
        icon_path = resource_path("icon.png")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
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
