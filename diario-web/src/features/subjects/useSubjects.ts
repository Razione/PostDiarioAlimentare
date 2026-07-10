import { useEffect, useState } from "react";
import { listenSubjects, type Subject } from "../../lib/db";

export function useSubjects() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let unsub = () => {};
    try {
      unsub = listenSubjects((s) => {
        setSubjects(s);
        setLoading(false);
      });
    } catch {
      setLoading(false);
    }
    return () => unsub();
  }, []);

  return { subjects, loading };
}
