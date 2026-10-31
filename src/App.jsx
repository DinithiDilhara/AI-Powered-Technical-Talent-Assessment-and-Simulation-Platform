
import React from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { CheckCircle2, X } from 'lucide-react';

import { PublicLayout, AppLayout } from './components/Layout.jsx';
import { useStore } from './context/useStore.js';

import Home from './pages/Home.jsx';
import Auth from './pages/Auth.jsx';
import Dashboard from './pages/Dashboard.jsx';
import { AssessmentList, AssessmentDetails } from './pages/Assessments.jsx';
import CreateAssessment from './pages/CreateAssessment.jsx';
import { CandidateDirectory, CandidateDetails, Invitations } from './pages/Candidates.jsx';
import { CandidateWelcome, CandidateAssessment, CandidateSuccess } from './pages/CandidateFlow.jsx';
import { Privacy, Settings } from './pages/Settings.jsx';

function Toast() {
  const { toast, setToast } = useStore();

  if (!toast) return null;

  return (
    <div role="status" className="toast">
      <CheckCircle2 size={18} />
      <span>{toast}</span>
      <button
        aria-label="Dismiss notification"
        onClick={() => setToast('')}
      >
        <X size={16} />
      </button>
    </div>
  );
}

function ScrollTop() {
  const { pathname } = useLocation();

  React.useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return null;
}

export default function App() {
  return (
    <>
      <ScrollTop />

      <Routes>
        <Route element={<PublicLayout />}>
          <Route index element={<Home />} />
          <Route path="privacy" element={<Privacy />} />
        </Route>

        <Route path="login" element={<Auth />} />
        <Route path="signup" element={<Auth signup />} />

        <Route element={<AppLayout />}>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="assessments" element={<AssessmentList />} />
          <Route path="assessments/new" element={<CreateAssessment />} />
          <Route path="assessments/:id" element={<AssessmentDetails />} />
          <Route path="invitations" element={<Invitations />} />
          <Route path="candidates" element={<CandidateDirectory />} />
          <Route path="candidates/:id" element={<CandidateDetails />} />
          <Route path="settings" element={<Settings />} />
        </Route>

        <Route path="candidate/welcome/:id" element={<CandidateWelcome />} />
        <Route path="candidate/assessment/:id" element={<CandidateAssessment />} />
        <Route path="candidate/success/:id" element={<CandidateSuccess />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      <Toast />
    </>
  );
}
