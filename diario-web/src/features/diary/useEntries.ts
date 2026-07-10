import { useEffect, useState } from "react";
import { listenEntries, type DiaryEntry } from "../../lib/db";

export function useEntries(code: string | null) {
  const [entries, setEntries] = useState<DiaryEntry[]>([]);

  useEffect(() => {
    if (!code) {
      setEntries([]);
      return;
    }
    return listenEntries(code, setEntries);
  }, [code]);

  return entries;
}
