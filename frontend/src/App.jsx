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

const PageLoader = () => (
  <div className="flex h-full items-center justify-center p-10" role="status">
    <Loader2 className="h-6 w-6 animate-spin text-brand" aria-label="Loading page" />
  </div>
);

// Layout for signed-in pages: sidebar + top bar + routed page
function AppLayout() {
  const { pathname } = useLocation();
  const mainRef = useRef(null);

  // The page scrolls inside <main>, so reset it on navigation
  useEffect(() => {
    mainRef.current?.scrollTo(0, 0);
  }, [pathname]);

  return (
    <div className="flex h-screen flex-col-reverse bg-page md:flex-row">
      <Sidebar />
      <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        <TopNavbar />
        <main ref={mainRef} className="flex-1 overflow-y-auto">
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
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </AuthProvider>
  );
}

export default App;
