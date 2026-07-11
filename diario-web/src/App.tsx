import { useState } from "react";
import { useAuth } from "./features/auth/useAuth";
import { BdaTab } from "./features/bda/BdaTab";
import { UtentiTab } from "./features/subjects/UtentiTab";
import { DiariTab } from "./features/diary/DiariTab";
import { PreferenzeTab } from "./features/settings/PreferenzeTab";
import { TEAM_ID, firebaseConfigured, missingEnv } from "./lib/firebase";

type Tab = "diari" | "bda" | "utenti" | "preferenze";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "diari", label: "Diari" },
  { id: "bda", label: "BDA" },
  { id: "utenti", label: "Utenti" },
  { id: "preferenze", label: "Preferenze" },
];

export default function App() {
  const { user, loading, login, logout } = useAuth();
  const [tab, setTab] = useState<Tab>("diari");

  if (!firebaseConfigured) {
    return <ConfigNeeded />;
  }

  if (loading) {
    return <div className="center muted">Caricamento…</div>;
  }

  if (!user) {
    return <LoginForm onLogin={login} />;
  }

  return (
    <div className="app">
      <header className="topbar">
        <strong>Analisi Diari Alimentari</strong>
        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={tab === t.id ? "tab active" : "tab"}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="spacer" />
        <span className="muted small">
          team: {TEAM_ID} · {user.email?.split("@")[0] ?? "utente"}
        </span>
        <button onClick={() => void logout()}>Esci</button>
      </header>

      <main className="content">
        {tab === "diari" && <DiariTab />}
        {tab === "bda" && <BdaTab />}
        {tab === "utenti" && <UtentiTab />}
        {tab === "preferenze" && <PreferenzeTab />}
      </main>
    </div>
  );
}

function LoginForm({
  onLogin,
}: {
  onLogin: (username: string, password: string) => Promise<void>;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await onLogin(username, password);
    } catch {
      setError("Accesso fallito: nome utente o password non validi.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="center">
      <form className="card login" onSubmit={submit}>
        <h1>Analisi Diari Alimentari</h1>
        <p className="muted">Accedi per lavorare sui diari condivisi.</p>
        <label>
          Nome utente
          <input
            type="text"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="primary" type="submit" disabled={busy}>
          {busy ? "Accesso…" : "Accedi"}
        </button>
      </form>
    </div>
  );
}

function ConfigNeeded() {
  return (
    <div className="center">
      <div className="card">
        <h1>Configurazione Firebase mancante</h1>
        <p className="muted">
          La app non trova la configurazione del progetto Firebase, per questo la
          pagina restava bianca. Crea il file <code>.env.local</code> nella
          cartella <code>diario-web/</code> (copia da <code>.env.example</code>) e
          incolla i valori dal tuo progetto Firebase → Impostazioni progetto → «I
          tuoi apps» (Web) → Config SDK.
        </p>
        {missingEnv.length > 0 && (
          <p>
            Variabili mancanti:{" "}
            <code>{missingEnv.join(", ")}</code>
          </p>
        )}
        <p className="muted small">
          Dopo aver salvato <code>.env.local</code>, <b>riavvia</b>{" "}
          <code>npm run dev</code> (Vite legge le variabili solo all'avvio).
        </p>
      </div>
    </div>
  );
}

