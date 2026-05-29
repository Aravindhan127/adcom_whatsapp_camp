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
import SuperAdminDashboard from './pages/SuperAdminDashboard.tsx';
import OrganizationManagement from './pages/OrganizationManagement.tsx';
import UserManagement from './pages/UserManagement.tsx';
import RoleManagement from './pages/RoleManagement.tsx';
import Flows from './pages/Flows.tsx';
import { ThemeProvider } from './components/ThemeProvider';
import { ToastProvider } from './components/Toast';
import { AuthProvider, useAuth } from './context/AuthContext.tsx';
import { Loader2 } from 'lucide-react';
import './index.css';

// Replaces PrivateRoute to support RBAC permission checking
const ProtectedRoute = ({ children, requiredPermission }: { children: React.ReactNode, requiredPermission?: string }) => {
  const { isAuthenticated, isLoading, hasPermission } = useAuth();
  
  if (isLoading) return <div className="h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950"><Loader2 className="animate-spin text-indigo-500" size={32} /></div>;
  if (!isAuthenticated) return <Navigate to="/login" />;
  
  if (requiredPermission && !hasPermission(requiredPermission)) {
    return <Navigate to="/dashboard" />;
  }
  
  return <>{children}</>;
};

// Removed SuperAdminRoute as ProtectedRoute natively handles all UAM logic

function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <Router>
            <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route 
            path="/*" 
            element={
              <ProtectedRoute>
                <Layout>
                  <Routes>
                    <Route path="/" element={
                      (localStorage.getItem('role') === 'super_admin' || localStorage.getItem('role') === 'superadmin') ? (
                        <Navigate to="/admin/dashboard" />
                      ) : (
                        <Navigate to="/dashboard" />
                      )
                    } />
                    <Route path="/dashboard" element={<ProtectedRoute requiredPermission="screen.dashboard"><DashboardV2 /></ProtectedRoute>} />
                    <Route path="/campaigns" element={<ProtectedRoute requiredPermission="screen.campaigns"><Campaigns /></ProtectedRoute>} />
                    <Route path="/contacts" element={<ProtectedRoute requiredPermission="screen.contacts"><Contacts /></ProtectedRoute>} />
                    <Route path="/templates" element={<ProtectedRoute requiredPermission="screen.templates"><Templates /></ProtectedRoute>} />
                    <Route path="/flows" element={<ProtectedRoute requiredPermission="flow.view"><Flows /></ProtectedRoute>} />
                    <Route path="/audit" element={<ProtectedRoute requiredPermission="screen.audit"><AuditLogs /></ProtectedRoute>} />
                    <Route path="/chat" element={<ProtectedRoute requiredPermission="screen.chat"><Chat /></ProtectedRoute>} />
                    <Route path="/settings" element={<ProtectedRoute requiredPermission="screen.organizations"><Settings /></ProtectedRoute>} />
                    <Route path="/users" element={<ProtectedRoute requiredPermission="screen.users"><UserManagement /></ProtectedRoute>} />
                    <Route path="/roles" element={<ProtectedRoute requiredPermission="screen.roles"><RoleManagement /></ProtectedRoute>} />
                    
                    {/* Platform Control Routes (Require system.admin bypass) */}
                    <Route path="/admin/dashboard" element={<ProtectedRoute requiredPermission="system.admin"><SuperAdminDashboard /></ProtectedRoute>} />
                    <Route path="/admin/organizations" element={<ProtectedRoute requiredPermission="system.admin"><OrganizationManagement /></ProtectedRoute>} />
                    <Route path="/admin/organizations/:orgId" element={<ProtectedRoute requiredPermission="system.admin"><OrganizationManagement /></ProtectedRoute>} />
                    
                    {/* Catch all admin duplicates and redirect to UAM unified routes */}
                    <Route path="/admin/users" element={<Navigate to="/users" />} />
                    <Route path="/admin/roles" element={<Navigate to="/roles" />} />
                  </Routes>
                </Layout>
              </ProtectedRoute>
            } 
          />
        </Routes>
      </Router>
      </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

export default App;
