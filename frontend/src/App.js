import React, { useState } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import "./App.css";
import { AuthProvider } from "./context/AuthContext";
import Login from "./components/auth/Login";
import Register from "./components/auth/Register";
import ProtectedRoute from "./components/auth/ProtectedRoute";
import Sidebar from "./components/Sidebar";
import TopNavbar from "./components/TopNavbar";
import Dashboard from "./components/Dashboard";
import JobPostings from "./components/JobPostings";
import CandidatePipeline from "./components/CandidatePipeline";
import Profile from "./components/Profile";
import Settings from "./components/Settings";
import Interviews from "./components/Interviews";
import QAPage from "./components/QAPage";
import { Toaster } from "./components/ui/toaster";

// Main App Layout for authenticated users
function AppLayout() {
  const [activeView, setActiveView] = useState('dashboard');
  const [selectedJob, setSelectedJob] = useState(null);
  const [selectedCandidate, setSelectedCandidate] = useState(null);

  const handleViewCandidates = (job) => {
    setSelectedJob(job);
    setActiveView('pipeline');
  };

  const handleBackToJobs = () => {
    setSelectedJob(null);
    setActiveView('jobs');
  };

  const renderMainContent = () => {
    switch (activeView) {
      case 'dashboard':
        return <Dashboard onViewCandidates={handleViewCandidates} />;
      case 'jobs':
        return <JobPostings onViewCandidates={handleViewCandidates} />;
      case 'pipeline':
        return selectedJob ? (
          <CandidatePipeline
            job={selectedJob}
            onBack={handleBackToJobs}
          />
        ) : <JobPostings onViewCandidates={handleViewCandidates} />;
      case 'interviews':
        return (
          <Interviews
            onTakeInterview={(candidate, job) => {
              setSelectedCandidate(candidate);
              setSelectedJob(job);
              setActiveView('qa');
            }}
          />
        );
      case 'qa':
        return selectedCandidate ? (
          <QAPage
            candidate={selectedCandidate}
            job={selectedJob}
            onBack={() => {
              setSelectedCandidate(null);
              setActiveView('interviews');
            }}
          />
        ) : (
          <Interviews
            onTakeInterview={(candidate, job) => {
              setSelectedCandidate(candidate);
              setSelectedJob(job);
              setActiveView('qa');
            }}
          />
        );
      case 'profile':
        return <Profile />;
      case 'settings':
        return <Settings />;
      default:
        return <Dashboard onViewCandidates={handleViewCandidates} />;
    }
  };

  return (
    <div className="flex flex-col-reverse md:flex-row h-screen" style={{ background: '#f1f3f9' }}>
      <Sidebar activeView={activeView} setActiveView={setActiveView} />
      <div className="flex-1 flex flex-col overflow-hidden relative">
        <TopNavbar activeView={activeView} setActiveView={setActiveView} />
        <main className="flex-1 overflow-y-auto">
          {renderMainContent()}
        </main>
      </div>
      <Toaster />
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Public Routes */}
          <Route path="/login"    element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected Routes */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          />

          {/* Redirect root to dashboard */}
          <Route path="/"  element={<Navigate to="/dashboard" replace />} />
          <Route path="*"  element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
