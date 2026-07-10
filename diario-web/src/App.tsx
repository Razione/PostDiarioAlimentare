import { useState } from "react";
import { useAuth } from "./features/auth/useAuth";
import { TEAM_ID } from "./lib/firebase";

type Tab = "diari" | "bda" | "utenti";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "diari", label: "Diari" },
  { id: "bda", label: "BDA" },
  { id: "utenti", label: "Utenti" },
];

export default function App() {
  const { user, loading, login, logout } = useAuth();
  const [tab, setTab] = useState<Tab>("diari");

  if (loading) {
    return <div className="center muted">Caricamento…</div>;
  }

  if (!user) {
    return (
      <div className="center">
        <div className="card">
          <h1>Analisi Diari Alimentari</h1>
          <p className="muted">Accedi per lavorare sui diari condivisi.</p>
          <button className="primary" onClick={() => void login()}>
            Accedi con Google
          </button>
        </div>
      </div>
    );
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
