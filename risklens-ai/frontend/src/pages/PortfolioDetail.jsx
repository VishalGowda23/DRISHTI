import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Shield, RefreshCw, TrendingUp, AlertTriangle, Cpu } from 'lucide-react';
import { portfolioApi, riskApi } from '../services/api';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import toast from 'react-hot-toast';

const CHART_COLORS = ['#3B82F6', '#DC2626', '#059669', '#D97706', '#7C3AED', '#0D9488', '#6366F1', '#EA580C'];
const SEVERITY_COLORS = { CRITICAL: '#DC2626', HIGH: '#EA580C', MEDIUM: '#D97706', LOW: '#059669' };

export default function PortfolioDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [portfolio, setPortfolio] = useState(null);
  const [positions, setPositions] = useState([]);
  const [latestAssessment, setLatestAssessment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => { fetchPortfolio(); }, [id]);

  const fetchPortfolio = async () => {
    try {
      const res = await portfolioApi.getById(id);
      setPortfolio(res.portfolio);
      setPositions(res.positions || []);
      setLatestAssessment(res.latest_assessment);
    } catch (err) {
      toast.error('Portfolio not found');
      navigate('/');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      await riskApi.analyze(id);
      toast.success('Analysis complete');
      fetchPortfolio();
    } catch (err) {
      toast.error(`Analysis failed: ${err.message}`);
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) {
    return (
      <div className="loading-center">
        <RefreshCw size={32} className="pulse" style={{ color: 'var(--accent-primary)' }} />
      </div>
    );
  }

  if (!portfolio) return null;

  // Prepare chart data
  const sectorData = positions.reduce((acc, p) => {
    const existing = acc.find(s => s.name === p.sector);
    if (existing) existing.value += p.market_value || 0;
    else acc.push({ name: p.sector, value: p.market_value || 0 });
    return acc;
  }, []).sort((a, b) => b.value - a.value);

  const topHoldings = positions
    .sort((a, b) => (b.nav_percentage || 0) - (a.nav_percentage || 0))
    .slice(0, 10)
    .map(p => ({ name: p.name?.substring(0, 15) || p.symbol, pct: p.nav_percentage || 0 }));

  const assessment = latestAssessment;
  const claude = assessment?.claude_analysis;

  return (
    <div className="fade-in">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', marginBottom: 'var(--space-xl)', paddingBottom: 'var(--space-md)', borderBottom: 'var(--border-default)' }}>
        <button className="btn" onClick={() => navigate('/')}>
          <ArrowLeft size={16} />
        </button>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontFamily: 'var(--font-heading)', fontWeight: 700, fontSize: '1.6rem', letterSpacing: '-0.02em' }}>
            {portfolio.fund_name}
          </h2>
          <p className="mono text-muted" style={{ marginTop: 2 }}>
            {portfolio.fund_type} · {portfolio._id}
          </p>
        </div>
        <button className="btn btn-primary" onClick={handleAnalyze} disabled={analyzing}>
          {analyzing ? <RefreshCw size={14} className="pulse" /> : <Shield size={14} />}
          {analyzing ? 'Analyzing...' : 'Run Analysis'}
        </button>
      </div>

      {/* Stats */}
      <div className="grid-4 mb-xl">
        <div className="stat-card" style={{ '--stat-accent': 'var(--accent-primary)' }}>
          <p className="stat-label">Total NAV</p>
          <p className="stat-value" style={{ fontSize: '1.75rem' }}>₹{(portfolio.total_nav / 10000000).toFixed(2)} Cr</p>
        </div>
        <div className="stat-card" style={{ '--stat-accent': 'var(--accent-secondary)' }}>
          <p className="stat-label">Positions</p>
          <p className="stat-value" style={{ fontSize: '1.75rem' }}>{portfolio.positions_count}</p>
        </div>
        <div className="stat-card" style={{ '--stat-accent': claude?.severity ? SEVERITY_COLORS[claude.severity] : 'var(--text-muted)' }}>
          <p className="stat-label">Risk Level</p>
          <p className="stat-value" style={{
            fontSize: '1.75rem',
            color: SEVERITY_COLORS[claude?.severity] || 'var(--text-muted)',
          }}>
            {claude?.severity || 'N/A'}
          </p>
        </div>
        <div className="stat-card" style={{ '--stat-accent': 'var(--accent-purple)' }}>
          <p className="stat-label">AI Confidence</p>
          <p className="stat-value" style={{ fontSize: '1.75rem' }}>
            {claude?.confidence ? `${(claude.confidence * 100).toFixed(0)}%` : 'N/A'}
          </p>
        </div>
      </div>

      {/* Claude Analysis */}
      {claude && (
        <div className="card mb-xl" style={{ borderLeftWidth: 5, borderLeftColor: SEVERITY_COLORS[claude.severity] || '#666' }}>
          <h3 className="section-title">
            <Cpu size={18} style={{ color: 'var(--accent-purple)' }} />
            AI Risk Analysis
          </h3>

          <p style={{ color: 'var(--text-secondary)', marginBottom: 'var(--space-md)', lineHeight: 1.6 }}>
            {claude.rationale}
          </p>

          <div style={{
            background: 'var(--bg-subtle)',
            border: 'var(--border-light)',
            borderRadius: 'var(--radius-sm)',
            padding: 'var(--space-md)',
            marginBottom: 'var(--space-md)',
          }}>
            <p style={{ fontFamily: 'var(--font-heading)', fontWeight: 700, fontSize: '0.9rem' }}>
              Verdict: {claude.overall_verdict}
            </p>
          </div>

          {claude.recommended_actions?.length > 0 && (
            <div style={{ marginBottom: 'var(--space-md)' }}>
              <p className="heading-sm" style={{ marginBottom: 8 }}>Recommended Actions</p>
              <ul style={{ paddingLeft: 20, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                {claude.recommended_actions.map((action, i) => (
                  <li key={i} style={{ marginBottom: 6, lineHeight: 1.5 }}>{action}</li>
                ))}
              </ul>
            </div>
          )}

          {/* AI Proposed Trades */}
          {claude.proposed_trades?.length > 0 && (
            <div style={{
              marginTop: 'var(--space-lg)',
              padding: 'var(--space-lg)',
              background: 'var(--accent-purple-bg)',
              border: '2px solid var(--accent-purple)',
              borderRadius: 'var(--radius-md)',
              boxShadow: 'var(--shadow-sm)',
            }}>
              <h4 className="section-title" style={{ borderColor: 'var(--accent-purple)', color: 'var(--accent-purple)' }}>
                <TrendingUp size={16} />
                AI Hedging Strategy
              </h4>
              <table style={{ marginBottom: 'var(--space-md)' }}>
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>Symbol</th>
                    <th>% NAV</th>
                    <th>Rationale</th>
                  </tr>
                </thead>
                <tbody>
                  {claude.proposed_trades.map((trade, i) => (
                    <tr key={i}>
                      <td style={{
                        fontFamily: 'var(--font-heading)',
                        fontWeight: 700,
                        color: trade.action === 'SELL' ? 'var(--color-critical)' : 'var(--accent-green)',
                      }}>
                        {trade.action}
                      </td>
                      <td className="mono" style={{ fontWeight: 600 }}>{trade.symbol}</td>
                      <td style={{ fontWeight: 600 }}>{trade.amount_pct}%</td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{trade.rationale}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <button
                className="btn btn-purple"
                onClick={async () => {
                  try {
                    const { agentApi } = await import('../services/api');
                    await agentApi.executeRebalance({
                      portfolio_id: id,
                      assessment_id: assessment._id,
                      trades: claude.proposed_trades
                    });
                    toast.success('Agentic rebalance executed successfully!');
                    fetchPortfolio();
                  } catch (err) {
                    toast.error(`Execution failed: ${err.message}`);
                  }
                }}
              >
                <TrendingUp size={14} /> Execute AI Hedging Strategy
              </button>
            </div>
          )}
        </div>
      )}

      {/* Charts */}
      <div className="grid-2 mb-xl">
        <div className="card">
          <h3 className="section-title">Sector Allocation</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={sectorData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={95}
                strokeWidth={2}
                stroke="#1A1A2E"
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}
              >
                {sectorData.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: '#FFFFFF',
                  border: '2px solid #1A1A2E',
                  borderRadius: 6,
                  boxShadow: '3px 3px 0px #1A1A2E',
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontWeight: 600,
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3 className="section-title">Top Holdings (% NAV)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={topHoldings} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color-light)" />
              <XAxis type="number" tick={{ fill: '#4A4A5A', fontSize: 11, fontFamily: "'JetBrains Mono'" }} />
              <YAxis dataKey="name" type="category" width={105} tick={{ fill: '#1A1A2E', fontSize: 11, fontFamily: "'JetBrains Mono'" }} />
              <Tooltip
                contentStyle={{
                  background: '#FFFFFF',
                  border: '2px solid #1A1A2E',
                  borderRadius: 6,
                  boxShadow: '3px 3px 0px #1A1A2E',
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontWeight: 600,
                }}
              />
              <Bar dataKey="pct" fill="var(--accent-primary)" radius={[0, 3, 3, 0]} stroke="#1A1A2E" strokeWidth={1} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Positions Table */}
      <div className="card">
        <h3 className="section-title">Positions</h3>
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Name</th>
              <th>Asset Class</th>
              <th>Sector</th>
              <th>Qty</th>
              <th>Price</th>
              <th>Market Value</th>
              <th>% NAV</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((pos) => (
              <tr key={pos._id}>
                <td className="mono" style={{ fontWeight: 700 }}>{pos.symbol}</td>
                <td style={{ fontWeight: 500 }}>{pos.name}</td>
                <td><span className="badge badge-ok">{pos.asset_class}</span></td>
                <td style={{ color: 'var(--text-secondary)' }}>{pos.sector}</td>
                <td className="mono">{pos.quantity?.toLocaleString()}</td>
                <td className="mono">₹{pos.current_price?.toLocaleString()}</td>
                <td className="mono" style={{ fontWeight: 600 }}>₹{(pos.market_value / 10000000)?.toFixed(2)} Cr</td>
                <td style={{
                  fontWeight: 700,
                  fontFamily: 'var(--font-heading)',
                  color: pos.nav_percentage > 10 ? 'var(--color-critical)' : 'var(--text-primary)',
                }}>
                  {pos.nav_percentage?.toFixed(2)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
