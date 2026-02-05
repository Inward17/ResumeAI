import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

const firebaseConfig = {
    apiKey: "AIzaSyAJUJMe9IZVpbVd0V5O7MhGgk_wI4oY8wk",
    authDomain: "resume-ai-e0fe1.firebaseapp.com",
    projectId: "resume-ai-e0fe1",
    storageBucket: "resume-ai-e0fe1.firebasestorage.app",
    messagingSenderId: "546060992684",
    appId: "1:546060992684:web:20ee6ca7b7564a29b81f09",
    measurementId: "G-NRZR9PBZEF"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Firebase Auth
export const auth = getAuth(app);

// Google Auth Provider
export const googleProvider = new GoogleAuthProvider();

export default app;
