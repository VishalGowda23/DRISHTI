import { useState, useEffect } from 'react';
import { Settings, Save, RefreshCw } from 'lucide-react';
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
    { key: 'single_issuer_max', label: 'Single Issuer Max (%)', desc: 'Maximum exposure to any single issuer as % of NAV' },
    { key: 'sector_max', label: 'Sector Max (%)', desc: 'Maximum exposure to any single sector' },
    { key: 'geography_max', label: 'Geography Max (%)', desc: 'Maximum exposure to any single country' },
    { key: 'asset_class_max', label: 'Asset Class Max (%)', desc: 'Maximum exposure to any asset class' },
    { key: 'correlation_threshold', label: 'Correlation Threshold', desc: 'Minimum correlation to flag as correlated cluster' },
    { key: 'min_holdings', label: 'Minimum Holdings', desc: 'Minimum number of positions required' },
    { key: 'max_cash_percentage', label: 'Max Cash (%)', desc: 'Maximum allowed cash position as % of NAV' },
  ];

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>⚙️ Risk Configuration</h2>
          <p>Configure concentration limits for each portfolio</p>
        </div>
      </div>

      {/* Portfolio Selector */}
      <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
        <label>Select Portfolio</label>
        <select value={selectedPortfolio} onChange={(e) => setSelectedPortfolio(e.target.value)}>
          <option value="">Choose a portfolio...</option>
          {portfolios.map(p => <option key={p._id} value={p._id}>{p.fund_name} ({p._id})</option>)}
        </select>
      </div>

      {/* Limits Form */}
      {selectedPortfolio && (
        <div className="card">
          {loading ? (
            <div style={{ textAlign: 'center', padding: 'var(--space-xl)' }}><RefreshCw size={24} className="pulse" /></div>
          ) : (
            <>
              <div className="grid-2" style={{ gap: 'var(--space-lg)' }}>
                {limitFields.map(({ key, label, desc }) => (
                  <div key={key}>
                    <label>{label}</label>
                    <input
                      type="number"
                      step={key === 'correlation_threshold' ? 0.05 : key === 'min_holdings' ? 1 : 1}
                      value={limits[key]}
                      onChange={(e) => setLimits({ ...limits, [key]: parseFloat(e.target.value) || 0 })}
                    />
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginTop: 2 }}>{desc}</p>
                  </div>
                ))}
                <div>
                  <label>Warning Buffer (%)</label>
                  <input type="number" step={0.5} value={warningBuffer} onChange={(e) => setWarningBuffer(parseFloat(e.target.value) || 0)} />
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginTop: 2 }}>Triggers WARNING when within this distance of a limit</p>
                </div>
              </div>
              <div style={{ marginTop: 'var(--space-xl)', textAlign: 'right' }}>
                <button className="btn btn-primary" onClick={handleSave}><Save size={14} /> Save Configuration</button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
