import React, { Suspense, lazy, useEffect, useRef } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { AuthProvider } from "./context/AuthContext";
import { isFirebaseConfigured } from "./firebase";
import Login from "./components/auth/Login";
import Register from "./components/auth/Register";
import ProtectedRoute, { PublicOnlyRoute } from "./components/auth/ProtectedRoute";
import ConfigMissing from "./components/ConfigMissing";
import Sidebar from "./components/Sidebar";
import TopNavbar from "./components/TopNavbar";
import { Toaster } from "./components/ui/toaster";

// Pages load on demand to keep the first download small
const Dashboard = lazy(() => import("./components/Dashboard"));
const JobPostings = lazy(() => import("./components/JobPostings"));
const CandidatePipeline = lazy(() => import("./components/CandidatePipeline"));
const Profile = lazy(() => import("./components/Profile"));
const Settings = lazy(() => import("./components/Settings"));
const Interviews = lazy(() => import("./components/Interviews"));
const QAPage = lazy(() => import("./components/QAPage"));
const JoinOrg = lazy(() => import("./components/JoinOrg"));

const PageLoader = () => (
  <div className="flex h-full items-center justify-center p-10" role="status">
    <Loader2 className="h-5 w-5 animate-spin text-ink-3" aria-label="Loading page" />
  </div>
);

// Layout for signed-in pages: sidebar (desktop) or header + bottom nav (phone)
function AppLayout() {
  const { pathname } = useLocation();
  const mainRef = useRef(null);

  // The page scrolls inside <main>, so reset it on navigation
  useEffect(() => {
    mainRef.current?.scrollTo(0, 0);
  }, [pathname]);

  return (
    <div className="flex h-[100dvh] flex-col bg-canvas md:flex-row">
      <a href="#main" className="sr-only z-50 rounded-lg bg-surface px-3 py-2 text-sm font-medium focus:not-sr-only focus:absolute focus:left-3 focus:top-3">
        Skip to content
      </a>
      <Sidebar />
      <div className="relative order-first flex min-h-0 min-w-0 flex-1 flex-col md:order-none">
        <TopNavbar />
        <main id="main" ref={mainRef} className="flex-1 overflow-y-auto">
          <Suspense fallback={<PageLoader />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}

function App() {
  if (!isFirebaseConfigured) return <ConfigMissing />;

  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route element={<PublicOnlyRoute />}>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
          </Route>

          {/* Signed-in routes */}
          <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/jobs" element={<JobPostings />} />
            <Route path="/jobs/:jobId" element={<CandidatePipeline />} />
            <Route path="/jobs/:jobId/candidates/:candidateId/interview" element={<QAPage />} />
            <Route path="/interviews" element={<Interviews />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/join/:token" element={<JoinOrg />} />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </AuthProvider>
  );
}

export default App;
