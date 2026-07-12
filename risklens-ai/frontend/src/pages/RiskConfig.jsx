import { useState, useEffect } from 'react';
import { Settings, Save, RefreshCw, Sliders } from 'lucide-react';
import { configApi, portfolioApi } from '../services/api';
import toast from 'react-hot-toast';

export default function RiskConfig() {
  const [portfolios, setPortfolios] = useState([]);
  const [selectedPortfolio, setSelectedPortfolio] = useState('');
  const [limits, setLimits] = useState({
    single_issuer_max: 10, sector_max: 30, geography_max: 45,
    asset_class_max: 40, correlation_threshold: 0.85, min_holdings: 5, max_cash_percentage: 10,
  });
  const [warningBuffer, setWarningBuffer] = useState(3.0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    portfolioApi.list({ status: 'active' }).then(res => setPortfolios(res.portfolios || []));
  }, []);

  useEffect(() => {
    if (selectedPortfolio) {
      setLoading(true);
      configApi.getLimits(selectedPortfolio)
        .then(res => {
          setLimits(res.limits || limits);
          setWarningBuffer(res.warning_buffer_pct || 3.0);
        })
        .finally(() => setLoading(false));
    }
  }, [selectedPortfolio]);

  const handleSave = async () => {
    try {
      await configApi.updateLimits(selectedPortfolio, { limits, warning_buffer_pct: warningBuffer });
      toast.success('Risk limits updated');
    } catch (err) {
      toast.error('Failed to save limits');
    }
  };

  const limitFields = [
    { key: 'single_issuer_max', label: 'Single Issuer Max (%)', desc: 'Maximum exposure to any single issuer as % of NAV', icon: '📊' },
    { key: 'sector_max', label: 'Sector Max (%)', desc: 'Maximum exposure to any single sector', icon: '🏭' },
    { key: 'geography_max', label: 'Geography Max (%)', desc: 'Maximum exposure to any single country', icon: '🌍' },
    { key: 'asset_class_max', label: 'Asset Class Max (%)', desc: 'Maximum exposure to any asset class', icon: '📈' },
    { key: 'correlation_threshold', label: 'Correlation Threshold', desc: 'Minimum correlation to flag as correlated cluster', icon: '🔗' },
    { key: 'min_holdings', label: 'Minimum Holdings', desc: 'Minimum number of positions required', icon: '📋' },
    { key: 'max_cash_percentage', label: 'Max Cash (%)', desc: 'Maximum allowed cash position as % of NAV', icon: '💰' },
  ];

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>Risk Configuration</h2>
          <p>Configure concentration limits and breach thresholds per portfolio</p>
        </div>
      </div>

      {/* Portfolio Selector */}
      <div className="card mb-xl">
        <h3 className="section-title">
          <Settings size={18} />
          Select Portfolio
        </h3>
        <select
          value={selectedPortfolio}
          onChange={(e) => setSelectedPortfolio(e.target.value)}
        >
          <option value="">Choose a portfolio...</option>
          {portfolios.map(p => (
            <option key={p._id} value={p._id}>
              {p.fund_name} ({p._id})
            </option>
          ))}
        </select>
      </div>

      {/* Limits Form */}
      {selectedPortfolio && (
        <div className="card">
          <h3 className="section-title">
            <Sliders size={18} />
            Concentration Limits
          </h3>

          {loading ? (
            <div className="loading-inline">
              <RefreshCw size={24} className="pulse" style={{ color: 'var(--accent-primary)' }} />
            </div>
          ) : (
            <>
              <div className="grid-2" style={{ gap: 'var(--space-lg)' }}>
                {limitFields.map(({ key, label, desc, icon }) => (
                  <div key={key} style={{
                    padding: 'var(--space-md)',
                    background: 'var(--bg-subtle)',
                    border: 'var(--border-light)',
                    borderRadius: 'var(--radius-sm)',
                  }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span>{icon}</span> {label}
                    </label>
                    <input
                      type="number"
                      step={key === 'correlation_threshold' ? 0.05 : key === 'min_holdings' ? 1 : 1}
                      value={limits[key]}
                      onChange={(e) => setLimits({ ...limits, [key]: parseFloat(e.target.value) || 0 })}
                      style={{ background: 'var(--bg-surface)' }}
                    />
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginTop: 4 }}>{desc}</p>
                  </div>
                ))}
                <div style={{
                  padding: 'var(--space-md)',
                  background: 'var(--color-medium-bg)',
                  border: '2px solid var(--color-medium)',
                  borderRadius: 'var(--radius-sm)',
                }}>
                  <label style={{ color: 'var(--color-medium)' }}>⚠️ Warning Buffer (%)</label>
                  <input
                    type="number"
                    step={0.5}
                    value={warningBuffer}
                    onChange={(e) => setWarningBuffer(parseFloat(e.target.value) || 0)}
                    style={{ background: 'var(--bg-surface)' }}
                  />
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginTop: 4 }}>
                    Triggers WARNING when within this distance of a limit
                  </p>
                </div>
              </div>

              <div style={{
                marginTop: 'var(--space-xl)',
                paddingTop: 'var(--space-lg)',
                borderTop: 'var(--border-default)',
                display: 'flex',
                justifyContent: 'flex-end',
              }}>
                <button className="btn btn-primary" onClick={handleSave}>
                  <Save size={14} /> Save Configuration
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
