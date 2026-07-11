import { useState, useEffect } from 'react';
import { FileText, RefreshCw, Filter } from 'lucide-react';
import { auditApi } from '../services/api';
import toast from 'react-hot-toast';

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

  const ACTION_COLORS = {
    risk_assessment_completed: 'var(--accent-primary)',
    alert_created: 'var(--color-critical)',
    alert_acknowledged: 'var(--accent-green)',
    portfolio_created: 'var(--accent-purple)',
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>📋 Audit Trail</h2>
          <p>{total} total log entries — immutable compliance record</p>
        </div>
        <button className="btn" onClick={fetchLogs}><RefreshCw size={14} /> Refresh</button>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: 'var(--space-lg)', display: 'flex', gap: 'var(--space-md)', alignItems: 'center', padding: 'var(--space-md)' }}>
        <Filter size={16} style={{ color: 'var(--text-muted)' }} />
        <select value={filters.action} onChange={(e) => setFilters({ ...filters, action: e.target.value, page: 1 })} style={{ width: 'auto' }}>
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
          <div style={{ textAlign: 'center', padding: 'var(--space-xl)' }}><RefreshCw size={32} className="pulse" style={{ color: 'var(--accent-primary)' }} /></div>
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
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                    {new Date(log.timestamp).toLocaleString()}
                  </td>
                  <td>
                    <span style={{
                      color: ACTION_COLORS[log.action] || 'var(--text-secondary)',
                      fontWeight: 500,
                      fontSize: '0.85rem',
                    }}>
                      {log.action?.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-muted)' }}>{log.actor}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>{log.portfolio_id || '—'}</td>
                  <td style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    {JSON.stringify(log.details || {})}
                  </td>
                </tr>
              ))}
              {logs.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: 'var(--space-xl)', color: 'var(--text-muted)' }}>No audit logs found</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
