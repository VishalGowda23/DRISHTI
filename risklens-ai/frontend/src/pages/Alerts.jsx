import { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle, Filter, RefreshCw } from 'lucide-react';
import { alertApi } from '../services/api';
import toast from 'react-hot-toast';

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

  const SEVERITY_COLORS = { CRITICAL: 'var(--color-critical)', HIGH: 'var(--color-high)', MEDIUM: 'var(--color-medium)', LOW: 'var(--color-low)' };

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>🚨 Alert Center</h2>
          <p>{total} alerts found</p>
        </div>
        <button className="btn" onClick={fetchAlerts}><RefreshCw size={14} /> Refresh</button>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: 'var(--space-lg)', display: 'flex', gap: 'var(--space-md)', alignItems: 'center', padding: 'var(--space-md)' }}>
        <Filter size={16} style={{ color: 'var(--text-muted)' }} />
        <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value, page: 1 })} style={{ width: 'auto' }}>
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option>
        </select>
        <select value={filters.severity} onChange={(e) => setFilters({ ...filters, severity: e.target.value, page: 1 })} style={{ width: 'auto' }}>
          <option value="">All Severity</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
      </div>

      {/* Alert List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 'var(--space-2xl)' }}>
          <RefreshCw size={32} className="pulse" style={{ color: 'var(--accent-primary)' }} />
        </div>
      ) : alerts.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 'var(--space-2xl)' }}>
          <CheckCircle size={48} style={{ color: 'var(--accent-green)', marginBottom: 12 }} />
          <p style={{ color: 'var(--text-muted)' }}>No alerts matching your filters</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {alerts.map((alert) => (
            <div key={alert._id} className="card" style={{ borderLeft: `3px solid ${SEVERITY_COLORS[alert.severity] || '#666'}`, padding: 'var(--space-md)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 8 }}>
                    <span className={`badge badge-${alert.severity?.toLowerCase()}`}>{alert.severity}</span>
                    <span className={`badge ${alert.status === 'active' ? 'badge-critical' : 'badge-ok'}`}>{alert.status}</span>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>{alert._id}</span>
                  </div>
                  <h4 style={{ fontWeight: 600, marginBottom: 4 }}>{alert.title}</h4>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{alert.summary}</p>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: 8 }}>
                    Portfolio: {alert.portfolio_id} · {alert.created_at}
                  </p>
                </div>
                {alert.status === 'active' && (
                  <button className="btn" onClick={() => handleAcknowledge(alert._id)} style={{ flexShrink: 0 }}>
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
