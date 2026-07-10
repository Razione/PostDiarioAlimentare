import { useCallback, useEffect, useState } from "react";
import { loadBda } from "./bdaStorage";
import type { Bda } from "./bdaTypes";

export function useBda() {
  const [bda, setBda] = useState<Bda | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setBda(await loadBda());
    } catch (e: unknown) {
      setError((e as Error)?.message ?? "Errore nel caricamento della BDA.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { bda, loading, error, reload };
}
