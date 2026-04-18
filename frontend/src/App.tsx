import React from 'react';
import { jwtDecode } from 'jwt-decode';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout.tsx';
import Login from './pages/Login.tsx';
import DashboardV2 from './pages/Dashboard.tsx';
import Chat from './pages/Chat.tsx';
import Contacts from './pages/Contacts.tsx';
import Campaigns from './pages/Campaigns.tsx';
import Templates from './pages/Templates.tsx';
import AuditLogs from './pages/AuditLogs.tsx';
import Settings from './pages/Settings.tsx';
import ForgotPassword from './pages/ForgotPassword.tsx';
import ResetPassword from './pages/ResetPassword.tsx';
import { ThemeProvider } from './components/ThemeProvider';
import { ToastProvider } from './components/Toast';
import './index.css';

// Simple check for auth (checks presence and expiration)
const PrivateRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('token');
  
  if (!token) return <Navigate to="/login" />;

  try {
    const decoded: any = jwtDecode(token);
    const currentTime = Date.now() / 1000;
    
    // If token is expired, clear it and redirect
    // FE-FIX FE-14: Added 30s clock skew buffer — minor browser/server time differences
    // caused valid tokens to appear expired, kicking users to login unexpectedly.
    const CLOCK_SKEW_TOLERANCE_SECONDS = 30;
    if (decoded.exp && decoded.exp < (currentTime - CLOCK_SKEW_TOLERANCE_SECONDS)) {
      localStorage.removeItem('token');
      return <Navigate to="/login" />;
    }
  } catch (error) {
    // If token is malformed, clear it and redirect
    localStorage.removeItem('token');
    return <Navigate to="/login" />;
  }

  return <>{children}</>;
};

function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route 
            path="/*" 
            element={
              <PrivateRoute>
                <Layout>
                  <Routes>
                    <Route path="/" element={<Navigate to="/dashboard" />} />
                    <Route path="/dashboard" element={<DashboardV2 />} />
                    <Route path="/campaigns" element={<Campaigns />} />
                    <Route path="/contacts" element={<Contacts />} />
                    <Route path="/templates" element={<Templates />} />
                    <Route path="/audit" element={<AuditLogs />} />
                    <Route path="/chat" element={<Chat />} />
                    <Route path="/settings" element={<Settings />} />
                  </Routes>
                </Layout>
              </PrivateRoute>
            } 
          />
        </Routes>
      </Router>
      </ToastProvider>
    </ThemeProvider>
  );
}

export default App;
