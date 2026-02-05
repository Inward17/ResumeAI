import React, { useState } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import "./App.css";
import { AuthProvider } from "./context/AuthContext";
import Login from "./components/auth/Login";
import Register from "./components/auth/Register";
import ProtectedRoute from "./components/auth/ProtectedRoute";
import Sidebar from "./components/Sidebar";
import Dashboard from "./components/Dashboard";
import JobPostings from "./components/JobPostings";
import CandidateDetails from "./components/CandidateDetails";
import CandidateModal from "./components/CandidateModal";
import Profile from "./components/Profile";
import Settings from "./components/Settings";
import { Toaster } from "./components/ui/toaster";

// Main App Layout for authenticated users
function AppLayout() {
  const [activeView, setActiveView] = useState('dashboard');
  const [selectedJob, setSelectedJob] = useState(null);
  const [selectedCandidate, setSelectedCandidate] = useState(null);

  const handleViewCandidates = (job) => {
    setSelectedJob(job);
    setActiveView('candidates');
  };

  const handleBackToJobs = () => {
    setSelectedJob(null);
    setActiveView('jobs');
  };

  const handleViewCandidate = (candidate) => {
    setSelectedCandidate(candidate);
  };

  const handleCloseModal = () => {
    setSelectedCandidate(null);
  };

  const renderMainContent = () => {
    switch (activeView) {
      case 'dashboard':
        return <Dashboard />;
      case 'jobs':
        return <JobPostings onViewCandidates={handleViewCandidates} />;
      case 'candidates':
        return selectedJob ? (
          <CandidateDetails
            job={selectedJob}
            onBack={handleBackToJobs}
            onViewCandidate={handleViewCandidate}
          />
        ) : null;
      case 'profile':
        return <Profile />;
      case 'settings':
        return <Settings />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar activeView={activeView} setActiveView={setActiveView} />
      <div className="flex-1 overflow-hidden">
        <main className="h-full overflow-y-auto">
          {renderMainContent()}
        </main>
      </div>

      {selectedCandidate && (
        <CandidateModal
          candidate={selectedCandidate}
          job={selectedJob}
          onClose={handleCloseModal}
        />
      )}

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
          <Route path="/login" element={<Login />} />
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
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          {/* Catch all - redirect to dashboard */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
