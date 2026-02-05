import React, { createContext, useState, useEffect } from 'react';
import {
    signInWithEmailAndPassword,
    createUserWithEmailAndPassword,
    signInWithPopup,
    signOut,
    onAuthStateChanged,
    browserLocalPersistence,
    browserSessionPersistence,
    setPersistence
} from 'firebase/auth';
import { auth, googleProvider } from '../firebase';

export const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    // Listen for auth state changes
    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, (user) => {
            setUser(user);
            setLoading(false);
        });

        return () => unsubscribe();
    }, []);

    // Login with email and password
    const login = async (email, password, rememberMe = false) => {
        try {
            // Set persistence based on remember me
            await setPersistence(auth, rememberMe ? browserLocalPersistence : browserSessionPersistence);
            const result = await signInWithEmailAndPassword(auth, email, password);
            return { success: true, user: result.user };
        } catch (error) {
            return { success: false, error: getErrorMessage(error.code) };
        }
    };

    // Register with email and password
    const register = async (email, password) => {
        try {
            const result = await createUserWithEmailAndPassword(auth, email, password);
            return { success: true, user: result.user };
        } catch (error) {
            return { success: false, error: getErrorMessage(error.code) };
        }
    };

    // Login with Google
    const loginWithGoogle = async () => {
        try {
            // Always use local persistence for Google sign-in
            await setPersistence(auth, browserLocalPersistence);
            const result = await signInWithPopup(auth, googleProvider);
            return { success: true, user: result.user };
        } catch (error) {
            return { success: false, error: getErrorMessage(error.code) };
        }
    };

    // Logout
    const logout = async () => {
        try {
            await signOut(auth);
            return { success: true };
        } catch (error) {
            return { success: false, error: error.message };
        }
    };

    // Helper function to get user-friendly error messages
    const getErrorMessage = (errorCode) => {
        switch (errorCode) {
            case 'auth/email-already-in-use':
                return 'This email is already registered. Please login instead.';
            case 'auth/invalid-email':
                return 'Please enter a valid email address.';
            case 'auth/operation-not-allowed':
                return 'This sign-in method is not enabled.';
            case 'auth/weak-password':
                return 'Password should be at least 6 characters.';
            case 'auth/user-disabled':
                return 'This account has been disabled.';
            case 'auth/user-not-found':
                return 'No account found with this email.';
            case 'auth/wrong-password':
                return 'Incorrect password. Please try again.';
            case 'auth/invalid-credential':
                return 'Invalid email or password. Please try again.';
            case 'auth/too-many-requests':
                return 'Too many failed attempts. Please try again later.';
            case 'auth/popup-closed-by-user':
                return 'Sign-in popup was closed. Please try again.';
            default:
                return 'An error occurred. Please try again.';
        }
    };

    const value = {
        user,
        loading,
        login,
        register,
        loginWithGoogle,
        logout
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};
