import { ref, getBytes, uploadString } from "firebase/storage";
import { storage, TEAM_ID } from "../../lib/firebase";
import type { Bda } from "./bdaTypes";

function bdaRef() {
  if (!storage) throw new Error("Firebase Storage non disponibile.");
  return ref(storage, `teams/${TEAM_ID}/bda.json`);
}

/** Scarica la BDA da Storage. Ritorna null se non ancora caricata. */
export async function loadBda(): Promise<Bda | null> {
  try {
    const bytes = await getBytes(bdaRef());
    return JSON.parse(new TextDecoder().decode(bytes)) as Bda;
  } catch (e: unknown) {
    if ((e as { code?: string })?.code === "storage/object-not-found") return null;
    throw e;
  }
}

/** Carica (sovrascrive) la BDA su Storage. */
export async function saveBda(bda: Bda): Promise<void> {
  await uploadString(bdaRef(), JSON.stringify(bda), "raw", {
    contentType: "application/json",
  });
}
