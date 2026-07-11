import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload as UploadIcon, FileText, CheckCircle, AlertTriangle } from 'lucide-react';
import { portfolioApi } from '../services/api';
import toast from 'react-hot-toast';

export default function Upload() {
  const [file, setFile] = useState(null);
  const [fundName, setFundName] = useState('');
  const [fundType, setFundType] = useState('Multi-Asset');
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !fundName.trim()) {
      toast.error('Please provide a file and fund name');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('fund_name', fundName);
      formData.append('fund_type', fundType);

      const res = await portfolioApi.upload(formData);
      setResult(res);
      toast.success('Portfolio uploaded successfully!');
    } catch (err) {
      toast.error(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>📤 Upload Portfolio</h2>
          <p>Import holdings from CSV or JSON files</p>
        </div>
      </div>

      <div className="grid-2">
        {/* Upload Form */}
        <div className="card">
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 'var(--space-lg)' }}>
              <label>Fund Name *</label>
              <input type="text" value={fundName} onChange={(e) => setFundName(e.target.value)} placeholder="e.g., Alpha Growth Opportunities Fund" required />
            </div>

            <div style={{ marginBottom: 'var(--space-lg)' }}>
              <label>Fund Type</label>
              <select value={fundType} onChange={(e) => setFundType(e.target.value)}>
                <option value="Multi-Asset">Multi-Asset</option>
                <option value="Equity – Long Only">Equity – Long Only</option>
                <option value="Equity – Sector Specific">Equity – Sector Specific</option>
                <option value="Fixed Income">Fixed Income</option>
                <option value="Balanced">Balanced</option>
              </select>
            </div>

            <div style={{ marginBottom: 'var(--space-lg)' }}>
              <label>Holdings File (.csv or .json) *</label>
              <div
                onClick={() => fileInputRef.current?.click()}
                style={{
                  border: '2px dashed var(--border-default)',
                  borderRadius: 'var(--radius-md)',
                  padding: 'var(--space-xl)',
                  textAlign: 'center',
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                }}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => { e.preventDefault(); setFile(e.dataTransfer.files[0]); }}
              >
                {file ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                    <FileText size={20} style={{ color: 'var(--accent-green)' }} />
                    <span>{file.name}</span>
                  </div>
                ) : (
                  <div>
                    <UploadIcon size={32} style={{ color: 'var(--text-muted)', marginBottom: 8 }} />
                    <p style={{ color: 'var(--text-muted)' }}>Click or drag to upload</p>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Supports .csv and .json files</p>
                  </div>
                )}
              </div>
              <input ref={fileInputRef} type="file" accept=".csv,.json" onChange={(e) => setFile(e.target.files[0])} style={{ display: 'none' }} />
            </div>

            <button type="submit" className="btn btn-primary" disabled={uploading} style={{ width: '100%', justifyContent: 'center', padding: '12px' }}>
              {uploading ? 'Uploading...' : 'Upload Portfolio'}
            </button>
          </form>
        </div>

        {/* Result / Instructions */}
        <div className="card">
          {result ? (
            <div style={{ textAlign: 'center' }}>
              <CheckCircle size={48} style={{ color: 'var(--accent-green)', marginBottom: 12 }} />
              <h3>Upload Successful!</h3>
              <p style={{ color: 'var(--text-secondary)', marginTop: 8 }}>Portfolio ID: <code style={{ color: 'var(--accent-primary)' }}>{result.portfolio_id}</code></p>
              <p style={{ color: 'var(--text-secondary)' }}>Positions: {result.positions_count}</p>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 'var(--space-lg)' }}>
                <button className="btn btn-primary" onClick={() => navigate(`/portfolio/${result.portfolio_id}`)}>View Portfolio</button>
                <button className="btn" onClick={() => { setResult(null); setFile(null); setFundName(''); }}>Upload Another</button>
              </div>
            </div>
          ) : (
            <div>
              <h3 style={{ marginBottom: 'var(--space-md)', fontWeight: 600 }}>📋 CSV Format</h3>
              <div style={{ background: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-md)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', overflowX: 'auto' }}>
                <pre style={{ color: 'var(--text-secondary)' }}>{`symbol,name,asset_class,sector,country,quantity,current_price
RELIANCE.NS,Reliance Industries,equity,Energy,India,50000,1960.00
TCS.NS,Tata Consultancy,equity,IT,India,15000,4333.00`}</pre>
              </div>
              <h3 style={{ marginTop: 'var(--space-lg)', marginBottom: 'var(--space-sm)', fontWeight: 600 }}>Required Columns</h3>
              <ul style={{ paddingLeft: 20, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                <li><code>symbol</code> — Ticker symbol (e.g., RELIANCE.NS)</li>
                <li><code>name</code> — Full name</li>
                <li><code>asset_class</code> — equity, bond, derivative, cash</li>
                <li><code>sector</code> — Sector classification</li>
                <li><code>country</code> — Country of listing</li>
                <li><code>quantity</code> — Number of units held</li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
