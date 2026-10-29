import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { Loader2 } from 'lucide-react';

const FullPageLoader = () => (
    <div className="flex min-h-screen items-center justify-center bg-canvas" role="status">
        <div className="text-center">
            <Loader2 className="mx-auto h-6 w-6 animate-spin text-ink-3" aria-hidden="true" />
            <p className="mt-2 text-sm text-ink-3">Loading…</p>
        </div>
    </div>
);

/** Signed-in pages; remembers where the user was going */
const ProtectedRoute = ({ children }) => {
    const { user, loading } = useAuth();
    const location = useLocation();

    if (loading) return <FullPageLoader />;
    if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
    return children;
};

/** Login/register: signed-in users go straight to the app */
export const PublicOnlyRoute = () => {
    const { user, loading } = useAuth();
    const location = useLocation();

    if (loading) return <FullPageLoader />;
    if (user) return <Navigate to={location.state?.from?.pathname || '/dashboard'} replace />;
    return <Outlet />;
};

export default ProtectedRoute;
