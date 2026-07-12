import { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle, Filter, RefreshCw, Shield } from 'lucide-react';
import { alertApi } from '../services/api';
import toast from 'react-hot-toast';

const SEVERITY_COLORS = {
  CRITICAL: 'var(--color-critical)',
  HIGH: 'var(--color-high)',
  MEDIUM: 'var(--color-medium)',
  LOW: 'var(--color-low)',
};

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ status: 'active', severity: '', page: 1 });

  useEffect(() => { fetchAlerts(); }, [filters]);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const params = { ...filters, limit: 20 };
      if (!params.severity) delete params.severity;
      const res = await alertApi.list(params);
      setAlerts(res.alerts || []);
      setTotal(res.total || 0);
    } catch (err) {
      toast.error('Failed to load alerts');
    } finally {
      setLoading(false);
    }
  };

  const handleAcknowledge = async (alertId) => {
    try {
      await alertApi.acknowledge(alertId, { acknowledged_by: 'risk-desk', notes: 'Reviewed via dashboard' });
      toast.success('Alert acknowledged');
      fetchAlerts();
    } catch (err) {
      toast.error('Failed to acknowledge');
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>Alert Center</h2>
          <p>{total} alerts found — breach & concentration monitoring</p>
        </div>
        <button className="btn" onClick={fetchAlerts}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <Filter size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
        <select
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value, page: 1 })}
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option>
        </select>
        <select
          value={filters.severity}
          onChange={(e) => setFilters({ ...filters, severity: e.target.value, page: 1 })}
        >
          <option value="">All Severity</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
      </div>

      {/* Alert List */}
      {loading ? (
        <div className="loading-inline">
          <RefreshCw size={32} className="pulse" style={{ color: 'var(--accent-primary)' }} />
        </div>
      ) : alerts.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <Shield size={48} style={{ color: 'var(--accent-green)' }} />
            <p>No alerts matching your filters</p>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {alerts.map((alert, idx) => (
            <div
              key={alert._id}
              className="alert-card slide-up"
              style={{
                borderLeftColor: SEVERITY_COLORS[alert.severity] || '#666',
                animationDelay: `${idx * 0.04}s`,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 10 }}>
                    <span className={`badge badge-${alert.severity?.toLowerCase()}`}>{alert.severity}</span>
                    <span className={`badge ${alert.status === 'active' ? 'badge-critical' : 'badge-ok'}`}>
                      {alert.status}
                    </span>
                    <span className="mono text-muted">{alert._id}</span>
                  </div>
                  <h4 style={{ fontFamily: 'var(--font-heading)', fontWeight: 700, marginBottom: 4, fontSize: '1rem' }}>
                    {alert.title}
                  </h4>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', lineHeight: 1.5 }}>
                    {alert.summary}
                  </p>
                  <p className="mono text-muted" style={{ marginTop: 10, fontSize: '0.75rem' }}>
                    Portfolio: {alert.portfolio_id} · {alert.created_at}
                  </p>
                </div>
                {alert.status === 'active' && (
                  <button className="btn btn-success" onClick={() => handleAcknowledge(alert._id)} style={{ flexShrink: 0 }}>
                    <CheckCircle size={14} /> Acknowledge
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
