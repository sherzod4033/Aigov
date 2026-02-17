import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import Layout from './components/layout/Layout';
import LoginPage from './pages/LoginPage';
import ChatPage from './pages/ChatPage';
import AdminDocumentsPage from './pages/AdminDocumentsPage';
import AdminFAQPage from './pages/AdminFAQPage';
import AdminLogsPage from './pages/AdminLogsPage';
import SettingsPage from './pages/SettingsPage';

import RegisterPage from './pages/RegisterPage';

// Simple auth check
const PrivateRoute = () => {
  const token = localStorage.getItem('token');
  return token ? <Outlet /> : <Navigate to="/login" replace />;
};

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Protected Routes */}
        <Route element={<PrivateRoute />}>
          <Route path="/" element={<Layout />}>
            <Route index element={<ChatPage />} />
            <Route path="admin/documents" element={<AdminDocumentsPage />} />
            <Route path="admin/faq" element={<AdminFAQPage />} />
            <Route path="admin/logs" element={<AdminLogsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
