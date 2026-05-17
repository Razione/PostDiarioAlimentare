README: Firma e Notarizzazione (sintesi)

Questo file riassume brevemente i passaggi per firmare e notarizzare l'app macOS.

Vedi la documentazione completa: `.github/NOTARIZE_AND_CODESIGN.md`

Secrets GitHub richiesti:
- CERTIFICATE_P12 (base64)
- CERT_PASSWORD
- CODESIGN_IDENTITY (opzionale)
- APPLE_ID
- APPLE_PASSWORD

Passaggi rapidi:
1. Preparare `CERTIFICATE_P12` come base64 (vedi `.github/NOTARIZE_AND_CODESIGN.md`).
2. Aggiungere i secrets al repository (Settings → Secrets → Actions).
3. Taggare una release con `v*` per far partire il workflow (push tag).
4. Controllare gli artifact nella job `combine` su Actions: `DiarioAlimentare-macOS-final`.

Test locale (mac):

```bash
python -m PyInstaller diario_alimentare.spec --clean -y
security import cert.p12 -k login.keychain -P "P12PASSWORD" -T /usr/bin/codesign
codesign --force --deep --options runtime --sign "Developer ID Application: ..." dist/DiarioAlimentare.app
xcrun notarytool submit dist/DiarioAlimentare.zip --apple-id you@apple.com --password "APP_SPECIFIC_PASSWORD" --wait
xcrun stapler staple dist/DiarioAlimentare.app
```

Se vuoi, posso aggiungere istruzioni per testare su runner self-hosted macOS 26.
