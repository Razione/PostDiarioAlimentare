import { useState } from "react";
import { useAuth } from "./features/auth/useAuth";
import { TEAM_ID, firebaseConfigured, missingEnv } from "./lib/firebase";

type Tab = "diari" | "bda" | "utenti";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "diari", label: "Diari" },
  { id: "bda", label: "BDA" },
  { id: "utenti", label: "Utenti" },
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
          team: {TEAM_ID} · {user.email}
        </span>
        <button onClick={() => void logout()}>Esci</button>
      </header>

      <main className="content">
        {tab === "diari" && <Placeholder title="Diari" phase="Fasi 2–4" />}
        {tab === "bda" && <Placeholder title="BDA" phase="Fase 1" />}
        {tab === "utenti" && <Placeholder title="Utenti" phase="Fase 2" />}
      </main>
    </div>
  );
}

function LoginForm({
  onLogin,
}: {
  onLogin: (email: string, password: string) => Promise<void>;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await onLogin(email, password);
    } catch {
      setError("Accesso fallito: email o password non validi.");
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
          Email
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
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

function Placeholder({ title, phase }: { title: string; phase: string }) {
  return (
    <div className="card">
      <h2>{title}</h2>
      <p className="muted">
        Sezione in costruzione ({phase}). Lo scaffold (Auth + Firestore +
        motore nutrizionale) è pronto: qui arriveranno griglia, ricerca e
        riepilogo.
      </p>
    </div>
  );
}
