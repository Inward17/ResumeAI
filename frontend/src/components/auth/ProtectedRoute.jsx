import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import BrandMark from '../BrandMark';

const FullPageLoader = () => (
    <div className="flex min-h-[100dvh] items-center justify-center bg-canvas px-4" role="status">
        <div className="flex flex-col items-center">
            <BrandMark className="motion-safe:animate-pulse" />
            <div className="mt-5 h-0.5 w-32 overflow-hidden rounded-full bg-subtle" aria-hidden="true">
                <div className="h-full w-1/3 rounded-full bg-primary motion-safe:animate-[loader-slide_1.2s_ease-in-out_infinite] motion-reduce:w-full motion-reduce:opacity-40" />
            </div>
            <p className="mt-3 text-sm text-ink-3">Loading your workspace…</p>
        </div>
    </div>
);

/** Where to go after signing in: the page that sent the user to /login, query string included */
export const redirectTarget = (location) => {
    const from = location.state?.from;
    return from?.pathname ? `${from.pathname}${from.search || ''}${from.hash || ''}` : '/dashboard';
};

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
    if (user) return <Navigate to={redirectTarget(location)} replace />;
    return <Outlet />;
};

export default ProtectedRoute;
