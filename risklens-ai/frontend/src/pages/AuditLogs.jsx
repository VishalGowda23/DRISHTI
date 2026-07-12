import { useState, useEffect } from 'react';
import { FileText, RefreshCw, Filter, Lock } from 'lucide-react';
import { auditApi } from '../services/api';
import toast from 'react-hot-toast';

const ACTION_COLORS = {
  risk_assessment_completed: 'var(--accent-primary)',
  alert_created: 'var(--color-critical)',
  alert_acknowledged: 'var(--accent-green)',
  portfolio_created: 'var(--accent-purple)',
};

const ACTION_BADGES = {
  risk_assessment_completed: 'badge-info',
  alert_created: 'badge-critical',
  alert_acknowledged: 'badge-ok',
  portfolio_created: 'badge-purple',
};

export default function AuditLogs() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ page: 1, limit: 25, action: '' });

  useEffect(() => { fetchLogs(); }, [filters]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params = { ...filters };
      if (!params.action) delete params.action;
      const res = await auditApi.getLogs(params);
      setLogs(res.logs || []);
      setTotal(res.total || 0);
    } catch (err) {
      toast.error('Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>Audit Trail</h2>
          <p style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Lock size={12} />
            {total} log entries — cryptographically signed immutable record
          </p>
        </div>
        <button className="btn" onClick={fetchLogs}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <Filter size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
        <select
          value={filters.action}
          onChange={(e) => setFilters({ ...filters, action: e.target.value, page: 1 })}
        >
          <option value="">All Actions</option>
          <option value="risk_assessment_completed">Risk Assessment</option>
          <option value="alert_created">Alert Created</option>
          <option value="alert_acknowledged">Alert Acknowledged</option>
          <option value="portfolio_created">Portfolio Created</option>
        </select>
      </div>

      {/* Logs Table */}
      <div className="card">
        {loading ? (
          <div className="loading-inline">
            <RefreshCw size={32} className="pulse" style={{ color: 'var(--accent-primary)' }} />
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Action</th>
                <th>Actor</th>
                <th>Portfolio</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log._id}>
                  <td className="mono" style={{ whiteSpace: 'nowrap', fontSize: '0.75rem' }}>
                    {new Date(log.timestamp).toLocaleString()}
                  </td>
                  <td>
                    <span className={`badge ${ACTION_BADGES[log.action] || 'badge-info'}`}>
                      {log.action?.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td style={{ fontWeight: 500, color: 'var(--text-secondary)' }}>{log.actor}</td>
                  <td className="mono" style={{ fontSize: '0.75rem' }}>{log.portfolio_id || '—'}</td>
                  <td style={{
                    maxWidth: 280,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    fontSize: '0.78rem',
                    color: 'var(--text-muted)',
                    fontFamily: 'var(--font-mono)',
                  }}>
                    {JSON.stringify(log.details || {})}
                  </td>
                </tr>
              ))}
              {logs.length === 0 && (
                <tr>
                  <td colSpan={5} className="empty-state" style={{ padding: 'var(--space-2xl)' }}>
                    No audit logs found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
