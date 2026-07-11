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

const SEVERITY_BG = {
  CRITICAL: 'var(--color-critical-bg)',
  HIGH: 'var(--color-high-bg)',
  MEDIUM: 'var(--color-medium-bg)',
  LOW: 'var(--color-low-bg)',
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
        style: { borderLeft: `4px solid ${SEVERITY_COLORS[latest.severity] || '#666'}` },
      });
      fetchData(); // Refresh dashboard
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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <RefreshCw size={32} className="pulse" style={{ color: 'var(--accent-primary)' }} />
      </div>
    );
  }

  return (
    <div className="fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <h2>📊 Risk Dashboard</h2>
          <p>Real-time portfolio risk monitoring</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className="status-indicator" style={{ color: isConnected ? 'var(--accent-green)' : 'var(--color-high)' }}>
            <Activity size={14} className={isConnected ? 'pulse' : ''} />
            <span>{isConnected ? 'Live' : 'Disconnected'}</span>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid-4" style={{ marginBottom: 'var(--space-xl)' }}>
        <div className="card" style={{ borderLeft: '3px solid var(--accent-primary)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
            <div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Portfolios</p>
              <p style={{ fontSize: '2rem', fontWeight: 700, marginTop: 4 }}>{portfolios.length}</p>
            </div>
            <BarChart3 size={24} style={{ color: 'var(--accent-primary)', opacity: 0.7 }} />
          </div>
        </div>

        <div className="card" style={{ borderLeft: `3px solid ${SEVERITY_COLORS.CRITICAL}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
            <div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Critical Alerts</p>
              <p style={{ fontSize: '2rem', fontWeight: 700, marginTop: 4, color: criticalCount > 0 ? SEVERITY_COLORS.CRITICAL : 'var(--text-primary)' }}>{criticalCount}</p>
            </div>
            <AlertTriangle size={24} style={{ color: SEVERITY_COLORS.CRITICAL, opacity: 0.7 }} />
          </div>
        </div>

        <div className="card" style={{ borderLeft: `3px solid ${SEVERITY_COLORS.HIGH}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
            <div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>High Alerts</p>
              <p style={{ fontSize: '2rem', fontWeight: 700, marginTop: 4, color: highCount > 0 ? SEVERITY_COLORS.HIGH : 'var(--text-primary)' }}>{highCount}</p>
            </div>
            <Shield size={24} style={{ color: SEVERITY_COLORS.HIGH, opacity: 0.7 }} />
          </div>
        </div>

        <div className="card" style={{ borderLeft: `3px solid ${SEVERITY_COLORS.MEDIUM}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
            <div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Warnings</p>
              <p style={{ fontSize: '2rem', fontWeight: 700, marginTop: 4 }}>{mediumCount}</p>
            </div>
            <TrendingUp size={24} style={{ color: SEVERITY_COLORS.MEDIUM, opacity: 0.7 }} />
          </div>
        </div>
      </div>

      {/* Portfolios Table */}
      <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
        <h3 style={{ marginBottom: 'var(--space-md)', fontWeight: 600 }}>Active Portfolios</h3>
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
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{p._id}</td>
                <td style={{ fontWeight: 500 }}>{p.fund_name}</td>
                <td style={{ color: 'var(--text-muted)' }}>{p.fund_type}</td>
                <td>₹{(p.total_nav / 10000000).toFixed(2)} Cr</td>
                <td>{p.positions_count}</td>
                <td style={{ display: 'flex', gap: 8 }}>
                  <button className="btn" onClick={() => navigate(`/portfolio/${p._id}`)}>View</button>
                  <button
                    className="btn btn-primary"
                    onClick={() => handleAnalyze(p._id)}
                    disabled={analyzing === p._id}
                  >
                    {analyzing === p._id ? <RefreshCw size={14} className="pulse" /> : <Shield size={14} />}
                    {analyzing === p._id ? 'Analyzing...' : 'Analyze'}
                  </button>
                </td>
              </tr>
            ))}
            {portfolios.length === 0 && (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', padding: 'var(--space-xl)', color: 'var(--text-muted)' }}>
                  No portfolios found. Upload one to get started.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Recent Alerts */}
      <div className="card">
        <h3 style={{ marginBottom: 'var(--space-md)', fontWeight: 600 }}>Recent Alerts</h3>
        {activeAlerts.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 'var(--space-lg)' }}>
            ✅ No active alerts. All portfolios within limits.
          </p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {activeAlerts.map((alert) => (
              <div
                key={alert._id}
                className="card"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: 'var(--space-md)',
                  borderLeft: `3px solid ${SEVERITY_COLORS[alert.severity] || '#666'}`,
                  cursor: 'pointer',
                }}
                onClick={() => navigate('/alerts')}
              >
                <div>
                  <span className={`badge badge-${alert.severity?.toLowerCase()}`}>{alert.severity}</span>
                  <span style={{ marginLeft: 12, fontWeight: 500 }}>{alert.title}</span>
                </div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                  {alert.portfolio_id}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
