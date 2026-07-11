import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Shield, RefreshCw, TrendingUp, AlertTriangle } from 'lucide-react';
import { portfolioApi, riskApi } from '../services/api';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import toast from 'react-hot-toast';

const CHART_COLORS = ['#89b4fa', '#f38ba8', '#a6e3a1', '#fab387', '#cba6f7', '#f9e2af', '#94e2d5', '#b4befe'];
const SEVERITY_COLORS = { CRITICAL: '#f38ba8', HIGH: '#ef4444', MEDIUM: '#fab387', LOW: '#a6e3a1' };

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
    return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}><RefreshCw size={32} className="pulse" style={{ color: 'var(--accent-primary)' }} /></div>;
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
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', marginBottom: 'var(--space-xl)' }}>
        <button className="btn" onClick={() => navigate('/')}><ArrowLeft size={16} /></button>
        <div style={{ flex: 1 }}>
          <h2>{portfolio.fund_name}</h2>
          <p style={{ color: 'var(--text-muted)' }}>{portfolio.fund_type} · {portfolio._id}</p>
        </div>
        <button className="btn btn-primary" onClick={handleAnalyze} disabled={analyzing}>
          {analyzing ? <RefreshCw size={14} className="pulse" /> : <Shield size={14} />}
          {analyzing ? 'Analyzing...' : 'Run Analysis'}
        </button>
      </div>

      {/* Stats */}
      <div className="grid-4" style={{ marginBottom: 'var(--space-xl)' }}>
        <div className="card">
          <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>Total NAV</p>
          <p style={{ fontSize: '1.5rem', fontWeight: 700 }}>₹{(portfolio.total_nav / 10000000).toFixed(2)} Cr</p>
        </div>
        <div className="card">
          <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>Positions</p>
          <p style={{ fontSize: '1.5rem', fontWeight: 700 }}>{portfolio.positions_count}</p>
        </div>
        <div className="card">
          <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>Risk Level</p>
          <p style={{ fontSize: '1.5rem', fontWeight: 700, color: SEVERITY_COLORS[claude?.severity] || 'var(--text-primary)' }}>
            {claude?.severity || 'Not Assessed'}
          </p>
        </div>
        <div className="card">
          <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>Confidence</p>
          <p style={{ fontSize: '1.5rem', fontWeight: 700 }}>{claude?.confidence ? `${(claude.confidence * 100).toFixed(0)}%` : 'N/A'}</p>
        </div>
      </div>

      {/* Claude Analysis */}
      {claude && (
        <div className="card" style={{ marginBottom: 'var(--space-xl)', borderLeft: `3px solid ${SEVERITY_COLORS[claude.severity] || '#666'}` }}>
          <h3 style={{ fontWeight: 600, marginBottom: 'var(--space-sm)' }}>🤖 AI Analysis</h3>
          <p style={{ color: 'var(--text-secondary)', marginBottom: 'var(--space-md)' }}>{claude.rationale}</p>
          <p style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: 8 }}>Verdict: {claude.overall_verdict}</p>
          {claude.recommended_actions?.length > 0 && (
            <div>
              <p style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 4 }}>Recommended Actions:</p>
              <ul style={{ paddingLeft: 20, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                {claude.recommended_actions.map((action, i) => <li key={i} style={{ marginBottom: 4 }}>{action}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Charts */}
      <div className="grid-2" style={{ marginBottom: 'var(--space-xl)' }}>
        <div className="card">
          <h3 style={{ fontWeight: 600, marginBottom: 'var(--space-md)' }}>Sector Allocation</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={sectorData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}>
                {sectorData.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3 style={{ fontWeight: 600, marginBottom: 'var(--space-md)' }}>Top Holdings (% NAV)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={topHoldings} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
              <XAxis type="number" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
              <YAxis dataKey="name" type="category" width={100} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8 }} />
              <Bar dataKey="pct" fill="var(--accent-primary)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Positions Table */}
      <div className="card">
        <h3 style={{ fontWeight: 600, marginBottom: 'var(--space-md)' }}>Positions</h3>
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
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', fontWeight: 600 }}>{pos.symbol}</td>
                <td>{pos.name}</td>
                <td><span className="badge badge-ok">{pos.asset_class}</span></td>
                <td style={{ color: 'var(--text-secondary)' }}>{pos.sector}</td>
                <td>{pos.quantity?.toLocaleString()}</td>
                <td>₹{pos.current_price?.toLocaleString()}</td>
                <td>₹{(pos.market_value / 10000000)?.toFixed(2)} Cr</td>
                <td style={{ fontWeight: 600, color: pos.nav_percentage > 10 ? 'var(--color-critical)' : 'var(--text-primary)' }}>
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
