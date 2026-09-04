"""Controllo aggiornamenti via GitHub Releases.

Interroga l'API delle release del repo, confronta con APP_VERSION e, se c'è una
versione più recente, propone di scaricare lo zip per la piattaforma corrente
nella cartella Download. La sostituzione resta manuale (vedi «Aggiornare l'app»
nella guida) — così non si rischia di corrompere l'app in esecuzione.

Usa QtNetwork (nessuna dipendenza esterna, TLS e redirect gestiti da Qt).
"""

import json
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import QMessageBox, QProgressDialog

from constants import APP_VERSION

GITHUB_REPO = "Razione/PostDiarioAlimentare"
API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"
_USER_AGENT = b"DiarioAlimentare-Updater"


def _ver_tuple(v: str) -> tuple:
    """«v1.2.10» -> (1, 2, 10). Ignora eventuali suffissi non numerici."""
    out = []
    for part in (v or "").strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def _is_newer(latest: str, current: str) -> bool:
    return _ver_tuple(latest) > _ver_tuple(current)


def _platform_hint():
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    return None


class UpdateChecker(QObject):
    """Controlla e (opzionale) scarica l'ultima release da GitHub."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._parent = parent

    # ── Controllo versione ────────────────────────────────────────────────
    def check(self, silent: bool = True) -> None:
        """Se silent, in caso di errore o «già aggiornato» non mostra nulla."""
        req = QNetworkRequest(QUrl(API_LATEST))
        req.setRawHeader(b"Accept", b"application/vnd.github+json")
        req.setRawHeader(b"User-Agent", _USER_AGENT)
        reply = self._nam.get(req)
        reply.finished.connect(lambda: self._on_check(reply, silent))

    def _on_check(self, reply: QNetworkReply, silent: bool) -> None:
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                if not silent:
                    QMessageBox.warning(
                        self._parent, "Aggiornamenti",
                        f"Impossibile controllare gli aggiornamenti:\n{reply.errorString()}",
                    )
                return
            try:
                data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as e:
                if not silent:
                    QMessageBox.warning(self._parent, "Aggiornamenti", f"Risposta non valida:\n{e}")
                return
        finally:
            reply.deleteLater()

        tag = data.get("tag_name") or ""
        if not _is_newer(tag, APP_VERSION):
            if not silent:
                QMessageBox.information(
                    self._parent, "Aggiornamenti",
                    f"Hai già l'ultima versione ({APP_VERSION}).",
                )
            return
        self._prompt(tag, data)

    def _prompt(self, tag: str, data: dict) -> None:
        notes = (data.get("body") or "").strip()
        if len(notes) > 1500:
            notes = notes[:1500] + "…"
        asset = self._pick_asset(data.get("assets") or [])

        box = QMessageBox(self._parent)
        box.setWindowTitle("Aggiornamento disponibile")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(f"È disponibile la versione <b>{tag}</b> (hai la {APP_VERSION}).")
        if notes:
            box.setInformativeText(notes)
        dl_btn = box.addButton("Scarica", QMessageBox.ButtonRole.AcceptRole) if asset else None
        page_btn = box.addButton("Apri pagina Releases", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Chiudi", QMessageBox.ButtonRole.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if dl_btn is not None and clicked is dl_btn:
            self._download(asset)
        elif clicked is page_btn:
            QDesktopServices.openUrl(QUrl(data.get("html_url") or RELEASES_PAGE))

    def _pick_asset(self, assets: list):
        hint = _platform_hint()
        if not hint:
            return None
        # Windows: exe singolo (o zip di ripiego). macOS: zip dell'app.
        exts = (".exe", ".zip") if hint == "windows" else (".zip",)
        for a in assets:
            name = (a.get("name") or "").lower()
            if hint in name and name.endswith(exts):
                return a
        return None

    # ── Download ──────────────────────────────────────────────────────────
    def _download(self, asset: dict) -> None:
        url = asset.get("browser_download_url")
        name = asset.get("name") or "DiarioAlimentare.zip"
        if not url:
            return
        dest = Path.home() / "Downloads" / name
        dest.parent.mkdir(parents=True, exist_ok=True)

        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"User-Agent", _USER_AGENT)
        req.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        reply = self._nam.get(req)

        dlg = QProgressDialog("Scaricamento aggiornamento…", "Annulla", 0, 100, self._parent)
        dlg.setWindowTitle("Aggiornamento")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)

        def on_progress(received: int, total: int) -> None:
            if total > 0:
                dlg.setMaximum(100)
                dlg.setValue(int(received * 100 / total))
            else:
                dlg.setMaximum(0)  # barra indeterminata

        reply.downloadProgress.connect(on_progress)
        dlg.canceled.connect(reply.abort)
        reply.finished.connect(lambda: self._on_downloaded(reply, dest, dlg))

    def _on_downloaded(self, reply: QNetworkReply, dest: Path, dlg: QProgressDialog) -> None:
        dlg.close()
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                if reply.error() != QNetworkReply.NetworkError.OperationCanceledError:
                    QMessageBox.warning(
                        self._parent, "Aggiornamento",
                        f"Download non riuscito:\n{reply.errorString()}",
                    )
                return
            try:
                dest.write_bytes(bytes(reply.readAll()))
            except OSError as e:
                QMessageBox.warning(self._parent, "Aggiornamento", f"Impossibile salvare il file:\n{e}")
                return
        finally:
            reply.deleteLater()

        if dest.suffix.lower() == ".exe":
            info = ("Chiudi questa app e avvia il file scaricato per usare la nuova "
                    "versione (puoi sostituire il vecchio .exe con questo). "
                    "I tuoi progetti non vengono toccati.")
        else:
            info = ("Chiudi l'app, estrai lo zip e sostituisci la versione attuale "
                    "(vedi «Aggiornare l'app» nella guida). I tuoi progetti non vengono toccati.")
        msg = QMessageBox(self._parent)
        msg.setWindowTitle("Download completato")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(f"Scaricato in:\n{dest}")
        msg.setInformativeText(info)
        open_btn = msg.addButton("Apri cartella", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("Chiudi", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        if msg.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(dest.parent)))
