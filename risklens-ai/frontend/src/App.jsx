import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { Shield, BarChart3, AlertTriangle, Upload, Settings, FileText, Activity } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import Alerts from './pages/Alerts';
import PortfolioDetail from './pages/PortfolioDetail';
import UploadPage from './pages/Upload';
import RiskConfig from './pages/RiskConfig';
import AuditLogs from './pages/AuditLogs';
import './App.css';

function App() {
  const navItems = [
    { path: '/', icon: BarChart3, label: 'Dashboard' },
    { path: '/alerts', icon: AlertTriangle, label: 'Alerts' },
    { path: '/upload', icon: Upload, label: 'Upload' },
    { path: '/config', icon: Settings, label: 'Risk Config' },
    { path: '/audit', icon: FileText, label: 'Audit Logs' },
  ];

  return (
    <BrowserRouter>
      <div className="app-layout">
        {/* Sidebar Navigation */}
        <aside className="sidebar">
          <div className="sidebar-header">
            <Shield size={28} className="logo-icon" />
            <div>
              <h1 className="logo-text">RiskLens</h1>
              <span className="logo-badge">AI</span>
            </div>
          </div>

          <nav className="sidebar-nav">
            {navItems.map(({ path, icon: Icon, label }) => (
              <NavLink
                key={path}
                to={path}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                end={path === '/'}
              >
                <Icon size={18} />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="sidebar-footer">
            <div className="status-indicator">
              <Activity size={14} className="pulse" />
              <span>System Active</span>
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/portfolio/:id" element={<PortfolioDetail />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/config" element={<RiskConfig />} />
            <Route path="/audit" element={<AuditLogs />} />
          </Routes>
        </main>
      </div>

      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#FFFFFF',
            color: '#1A1A2E',
            border: '2px solid #1A1A2E',
            borderRadius: '6px',
            boxShadow: '4px 4px 0px #1A1A2E',
            fontFamily: "'Space Grotesk', sans-serif",
            fontWeight: 600,
            fontSize: '0.85rem',
          },
        }}
      />
    </BrowserRouter>
  );
}

export default App;
