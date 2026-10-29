/**
 * Authenticated fetch wrapper.
 *
 * Every backend route requires an OAuth 2.0 bearer token. We send the
 * signed-in user's Firebase ID token (Google OAuth / email sign-in); the
 * Firebase SDK refreshes it automatically before it expires.
 */
import { signOut } from 'firebase/auth';
import { auth } from '../firebase';

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiFetch = async (path, options = {}) => {
    const user = auth?.currentUser;
    const token = user ? await user.getIdToken() : null;

    const headers = new Headers(options.headers || {});
    if (token) headers.set('Authorization', `Bearer ${token}`);

    const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

    if (response.status === 401 && auth) {
        // Token revoked/invalid — end the session; ProtectedRoute redirects to /login
        await signOut(auth).catch(() => {});
    }
    return response;
};
