import { initializeApp, type FirebaseApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, type Auth } from "firebase/auth";
import {
  initializeFirestore,
  persistentLocalCache,
  persistentMultipleTabManager,
  type Firestore,
} from "firebase/firestore";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const TEAM_ID = import.meta.env.VITE_TEAM_ID || "default";

/** True solo se la config essenziale è presente (evita il crash a pagina bianca). */
export const firebaseConfigured = Boolean(
  firebaseConfig.apiKey && firebaseConfig.projectId && firebaseConfig.appId,
);

/** Chiavi env mancanti, per mostrare un messaggio utile. */
export const missingEnv = Object.entries({
  VITE_FIREBASE_API_KEY: firebaseConfig.apiKey,
  VITE_FIREBASE_AUTH_DOMAIN: firebaseConfig.authDomain,
  VITE_FIREBASE_PROJECT_ID: firebaseConfig.projectId,
  VITE_FIREBASE_APP_ID: firebaseConfig.appId,
})
  .filter(([, v]) => !v)
  .map(([k]) => k);

let _auth: Auth | null = null;
let _db: Firestore | null = null;
let _provider: GoogleAuthProvider | null = null;

if (firebaseConfigured) {
  const app: FirebaseApp = initializeApp(firebaseConfig);
  _auth = getAuth(app);
  _provider = new GoogleAuthProvider();
  _db = initializeFirestore(app, {
    localCache: persistentLocalCache({ tabManager: persistentMultipleTabManager() }),
  });
}

export const auth = _auth;
export const db = _db;
export const googleProvider = _provider;
