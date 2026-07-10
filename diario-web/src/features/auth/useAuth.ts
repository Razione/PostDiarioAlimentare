import { useEffect, useState } from "react";
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  type User,
} from "firebase/auth";
import { auth, USERNAME_DOMAIN } from "../../lib/firebase";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!auth) {
      setLoading(false);
      return;
    }
    return onAuthStateChanged(auth, (u) => {
      setUser(u);
      setLoading(false);
    });
  }, []);

  const login = async (username: string, password: string) => {
    if (!auth) throw new Error("Firebase non configurato");
    const id = username.trim();
    // Lo username diventa "<username>@<dominio>"; se già email, si usa così com'è.
    const email = id.includes("@") ? id : `${id}@${USERNAME_DOMAIN}`;
    await signInWithEmailAndPassword(auth, email, password);
  };
  const logout = async () => {
    if (auth) await signOut(auth);
  };

  return { user, loading, login, logout };
}
