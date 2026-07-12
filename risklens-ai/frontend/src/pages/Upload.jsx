import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload as UploadIcon, FileText, CheckCircle, ArrowRight } from 'lucide-react';
import { portfolioApi } from '../services/api';
import toast from 'react-hot-toast';

export default function Upload() {
  const [file, setFile] = useState(null);
  const [fundName, setFundName] = useState('');
  const [fundType, setFundType] = useState('Multi-Asset');
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
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
          <h2>Upload Portfolio</h2>
          <p>Import holdings from CSV or JSON files for risk analysis</p>
        </div>
      </div>

      <div className="grid-2">
        {/* Upload Form */}
        <div className="card">
          <h3 className="section-title">
            <UploadIcon size={18} />
            Portfolio Data
          </h3>
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 'var(--space-lg)' }}>
              <label>Fund Name *</label>
              <input
                type="text"
                value={fundName}
                onChange={(e) => setFundName(e.target.value)}
                placeholder="e.g., Alpha Growth Opportunities Fund"
                required
              />
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
                  border: isDragging ? '3px solid var(--accent-primary)' : '3px dashed var(--border-color)',
                  borderRadius: 'var(--radius-md)',
                  padding: 'var(--space-xl)',
                  textAlign: 'center',
                  cursor: 'pointer',
                  background: isDragging ? 'var(--accent-primary-bg)' : 'var(--bg-subtle)',
                  transition: 'all var(--transition-fast)',
                  boxShadow: isDragging ? '4px 4px 0px var(--accent-primary)' : 'none',
                }}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => { e.preventDefault(); setIsDragging(false); setFile(e.dataTransfer.files[0]); }}
              >
                {file ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
                    <FileText size={22} style={{ color: 'var(--accent-green)' }} />
                    <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 700 }}>{file.name}</span>
                    <span className="badge badge-ok">Ready</span>
                  </div>
                ) : (
                  <div>
                    <UploadIcon size={36} style={{ color: 'var(--text-muted)', marginBottom: 10 }} />
                    <p style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, color: 'var(--text-primary)' }}>
                      Click or drag to upload
                    </p>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: 4 }}>
                      Supports .csv and .json files
                    </p>
                  </div>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.json"
                onChange={(e) => setFile(e.target.files[0])}
                style={{ display: 'none' }}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={uploading}
              style={{ width: '100%', justifyContent: 'center', padding: '14px' }}
            >
              {uploading ? 'Uploading...' : 'Upload Portfolio'}
              {!uploading && <ArrowRight size={14} />}
            </button>
          </form>
        </div>

        {/* Result / Instructions */}
        <div className="card">
          {result ? (
            <div style={{ textAlign: 'center', padding: 'var(--space-lg)' }}>
              <CheckCircle size={52} style={{ color: 'var(--accent-green)', marginBottom: 16 }} />
              <h3 style={{ fontFamily: 'var(--font-heading)', fontWeight: 700, fontSize: '1.25rem' }}>
                Upload Successful!
              </h3>
              <div style={{
                marginTop: 'var(--space-md)',
                padding: 'var(--space-md)',
                background: 'var(--bg-subtle)',
                border: 'var(--border-default)',
                borderRadius: 'var(--radius-sm)',
                display: 'inline-block',
              }}>
                <p className="mono" style={{ color: 'var(--accent-primary)', fontWeight: 600 }}>
                  ID: {result.portfolio_id}
                </p>
                <p style={{ color: 'var(--text-secondary)', marginTop: 4 }}>
                  {result.positions_count} positions loaded
                </p>
              </div>
              <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 'var(--space-xl)' }}>
                <button className="btn btn-primary" onClick={() => navigate(`/portfolio/${result.portfolio_id}`)}>
                  View Portfolio <ArrowRight size={14} />
                </button>
                <button className="btn" onClick={() => { setResult(null); setFile(null); setFundName(''); }}>
                  Upload Another
                </button>
              </div>
            </div>
          ) : (
            <div>
              <h3 className="section-title">
                <FileText size={18} />
                CSV Format Guide
              </h3>
              <div className="code-block" style={{ marginBottom: 'var(--space-lg)' }}>
                <pre>{`symbol,name,asset_class,sector,country,quantity,current_price
RELIANCE.NS,Reliance Industries,equity,Energy,India,50000,1960.00
TCS.NS,Tata Consultancy,equity,IT,India,15000,4333.00`}</pre>
              </div>

              <h4 className="heading-sm" style={{ marginBottom: 10 }}>Required Columns</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  { col: 'symbol', desc: 'Ticker symbol (e.g., RELIANCE.NS)' },
                  { col: 'name', desc: 'Full company name' },
                  { col: 'asset_class', desc: 'equity, bond, derivative, cash' },
                  { col: 'sector', desc: 'Sector classification' },
                  { col: 'country', desc: 'Country of listing' },
                  { col: 'quantity', desc: 'Number of units held' },
                ].map(({ col, desc }) => (
                  <div key={col} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <code style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      background: 'var(--bg-subtle)',
                      border: 'var(--border-light)',
                      padding: '2px 8px',
                      borderRadius: 'var(--radius-sm)',
                      minWidth: 100,
                      textAlign: 'center',
                    }}>{col}</code>
                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
