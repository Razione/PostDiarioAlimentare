# Firma e Notarizzazione automatiche (GitHub Actions)

Questo file spiega come preparare i segreti GitHub usati dal workflow `.github/workflows/build-mac.yaml` per la firma e la notarizzazione su macOS.

Secrets richiesti (nomi esatti):
- `CERTIFICATE_P12` — contenuto del file `.p12` codificato in base64 (certificato di firma + chiave privata).
- `CERT_PASSWORD` — password del file `.p12` (se presente).
- `CODESIGN_IDENTITY` — (opzionale) nome comune (Common Name) dell'identità di firma, es. "Developer ID Application: Nome Cognome (TEAMID)". Usato come fallback se l'identità non viene estratta dal `.p12`.
- `APPLE_ID` — Apple ID per la notarizzazione (es. email developer).
- `APPLE_PASSWORD` — app-specific password per `xcrun notarytool` (consigliato) o password dell'account (meno sicuro).

Suggerimenti per creare il `.p12` e ottenere il valore base64 (su macOS locale):

1. Esporta il certificato p12 da Keychain Access (seleziona il certificato -> Export -> .p12).
2. Codifica in base64:

```bash
base64 -i cert.p12 -o cert.p12.b64
cat cert.p12.b64
```

3. Copia l'output e incollalo come valore del secret `CERTIFICATE_P12` (GitHub repo -> Settings -> Secrets -> Actions).

Creare un'app-specific password per notarization (consigliato):

1. Vai su https://appleid.apple.com/ -> Security -> App-Specific Passwords -> Create.
2. Usa la password risultante come `APPLE_PASSWORD`.

Come ottenere il `CODESIGN_IDENTITY` (se serve manualmente):

```bash
# mostra le identità disponibili
security find-identity -v -p codesigning
```

Note sul workflow:
- Il workflow importa `CERTIFICATE_P12` (se presente) in un keychain temporaneo e prova ad estrarre l'identità. Se non presente, usa `CODESIGN_IDENTITY`.
- La notarizzazione è eseguita solo se `APPLE_ID` e `APPLE_PASSWORD` sono impostati.
- Per distribuire pubblicamente su macOS 26 è necessario usare un certificato Developer ID valido e notarizzare l'app (firma con runtime hardened e stapler).

Consigli per sicurezza:
- Usa i Secrets di GitHub per memorizzare i valori, non salvarli nel repo.
- Limita i permessi del workflow (se possibile) e usa un runner self-hosted per testare build con SDK locali specifici.

Esempio rapido di test locale (mac):

```bash
# esporta p12 e prova a firmare localmente
python -m PyInstaller diario_alimentare.spec --clean -y
security import cert.p12 -k login.keychain -P "P12PASSWORD" -T /usr/bin/codesign
codesign --force --deep --options runtime --sign "Developer ID Application: ..." dist/DiarioAlimentare.app
xcrun notarytool submit dist/DiarioAlimentare.zip --apple-id you@apple.com --password "APP_SPECIFIC_PASSWORD" --wait
xcrun stapler staple dist/DiarioAlimentare.app
```

Se vuoi, posso aggiungere anche un piccolo README nella root che riassume questi passaggi per i collaboratori.
