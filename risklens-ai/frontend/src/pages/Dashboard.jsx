import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart3, AlertTriangle, Shield, TrendingUp, Activity, RefreshCw } from 'lucide-react';
import { portfolioApi, riskApi, alertApi } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';
import toast from 'react-hot-toast';

const SEVERITY_COLORS = {
  CRITICAL: 'var(--color-critical)',
  HIGH: 'var(--color-high)',
  MEDIUM: 'var(--color-medium)',
  LOW: 'var(--color-low)',
};

export default function Dashboard() {
  const [portfolios, setPortfolios] = useState([]);
  const [activeAlerts, setActiveAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(null);
  const navigate = useNavigate();
  const { alerts: wsAlerts, isConnected } = useWebSocket();

  useEffect(() => {
    fetchData();
  }, []);

  // Show toast for new WebSocket alerts
  useEffect(() => {
    if (wsAlerts.length > 0) {
      const latest = wsAlerts[0];
      toast(`🚨 ${latest.severity}: ${latest.title}`, {
        duration: 5000,
        style: {
          borderLeft: `5px solid ${SEVERITY_COLORS[latest.severity] || '#666'}`,
        },
      });
      fetchData();
    }
  }, [wsAlerts]);

  const fetchData = async () => {
    try {
      const [portfolioRes, alertRes] = await Promise.all([
        portfolioApi.list({ status: 'active' }),
        alertApi.list({ status: 'active', limit: 10 }),
      ]);
      setPortfolios(portfolioRes.portfolios || []);
      setActiveAlerts(alertRes.alerts || []);
    } catch (err) {
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async (portfolioId) => {
    setAnalyzing(portfolioId);
    try {
      const result = await riskApi.analyze(portfolioId);
      toast.success(`Analysis complete: ${result.severity} (${(result.confidence * 100).toFixed(0)}% confidence)`);
      fetchData();
    } catch (err) {
      toast.error(`Analysis failed: ${err.message}`);
    } finally {
      setAnalyzing(null);
    }
  };

  const criticalCount = activeAlerts.filter((a) => a.severity === 'CRITICAL').length;
  const highCount = activeAlerts.filter((a) => a.severity === 'HIGH').length;
  const mediumCount = activeAlerts.filter((a) => a.severity === 'MEDIUM').length;

  if (loading) {
    return (
      <div className="loading-center">
        <RefreshCw size={32} className="pulse" style={{ color: 'var(--accent-primary)' }} />
      </div>
    );
  }

  return (
    <div className="fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <h2>Risk Dashboard</h2>
          <p>Real-time portfolio risk monitoring & concentration alerts</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            className="status-indicator"
            style={{
              color: isConnected ? 'var(--accent-green)' : 'var(--color-critical)',
              background: isConnected ? 'var(--accent-green-bg)' : 'var(--color-critical-bg)',
              padding: '4px 14px',
              border: 'var(--border-default)',
              borderRadius: 'var(--radius-sm)',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <Activity size={12} className={isConnected ? 'pulse' : ''} />
            <span>{isConnected ? 'LIVE' : 'OFFLINE'}</span>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid-4 mb-xl">
        <div className="stat-card bounce-in stagger-1" style={{ '--stat-accent': 'var(--accent-primary)' }}>
          <div className="stat-icon"><BarChart3 size={40} /></div>
          <p className="stat-label">Portfolios</p>
          <p className="stat-value">{portfolios.length}</p>
        </div>

        <div className="stat-card bounce-in stagger-2" style={{ '--stat-accent': 'var(--color-critical)' }}>
          <div className="stat-icon"><AlertTriangle size={40} /></div>
          <p className="stat-label">Critical Alerts</p>
          <p className="stat-value" style={{ color: criticalCount > 0 ? 'var(--color-critical)' : undefined }}>
            {criticalCount}
          </p>
        </div>

        <div className="stat-card bounce-in stagger-3" style={{ '--stat-accent': 'var(--color-high)' }}>
          <div className="stat-icon"><Shield size={40} /></div>
          <p className="stat-label">High Alerts</p>
          <p className="stat-value" style={{ color: highCount > 0 ? 'var(--color-high)' : undefined }}>
            {highCount}
          </p>
        </div>

        <div className="stat-card bounce-in stagger-4" style={{ '--stat-accent': 'var(--color-medium)' }}>
          <div className="stat-icon"><TrendingUp size={40} /></div>
          <p className="stat-label">Warnings</p>
          <p className="stat-value">{mediumCount}</p>
        </div>
      </div>

      {/* Portfolios Table */}
      <div className="card mb-xl">
        <h3 className="section-title">
          <BarChart3 size={18} />
          Active Portfolios
        </h3>
        <table>
          <thead>
            <tr>
              <th>Portfolio ID</th>
              <th>Fund Name</th>
              <th>Type</th>
              <th>NAV</th>
              <th>Positions</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {portfolios.map((p) => (
              <tr key={p._id}>
                <td className="mono">{p._id}</td>
                <td style={{ fontWeight: 600 }}>{p.fund_name}</td>
                <td>
                  <span className="badge badge-info">{p.fund_type}</span>
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  ₹{(p.total_nav / 10000000).toFixed(2)} Cr
                </td>
                <td style={{ fontWeight: 600 }}>{p.positions_count}</td>
                <td>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn" onClick={() => navigate(`/portfolio/${p._id}`)}>
                      View
                    </button>
                    <button
                      className="btn btn-primary"
                      onClick={() => handleAnalyze(p._id)}
                      disabled={analyzing === p._id}
                    >
                      {analyzing === p._id ? (
                        <RefreshCw size={14} className="pulse" />
                      ) : (
                        <Shield size={14} />
                      )}
                      {analyzing === p._id ? 'Analyzing...' : 'Analyze'}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {portfolios.length === 0 && (
              <tr>
                <td colSpan={6} className="empty-state" style={{ padding: 'var(--space-2xl)' }}>
                  No portfolios found. Upload one to get started.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Recent Alerts */}
      <div className="card">
        <h3 className="section-title">
          <AlertTriangle size={18} />
          Recent Alerts
        </h3>
        {activeAlerts.length === 0 ? (
          <div className="empty-state">
            <Shield size={48} style={{ color: 'var(--accent-green)' }} />
            <p>All clear — no active alerts. All portfolios within limits.</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            {activeAlerts.map((alert) => (
              <div
                key={alert._id}
                className="alert-card"
                style={{
                  borderLeftColor: SEVERITY_COLORS[alert.severity] || '#666',
                  cursor: 'pointer',
                }}
                onClick={() => navigate('/alerts')}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                    <span className={`badge badge-${alert.severity?.toLowerCase()}`}>{alert.severity}</span>
                    <span style={{ fontWeight: 600, fontFamily: 'var(--font-heading)' }}>{alert.title}</span>
                  </div>
                  <span className="mono text-muted">{alert.portfolio_id}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
