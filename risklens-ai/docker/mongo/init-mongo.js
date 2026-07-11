// MongoDB initialization script
// Creates the risklens database and collections with indexes

db = db.getSiblingDB('risklens');

// ---- Collections ----
db.createCollection('portfolios');
db.createCollection('positions');
db.createCollection('risk_limits');
db.createCollection('assessments');
db.createCollection('alerts');
db.createCollection('audit_logs');
db.createCollection('market_data');
db.createCollection('notifications');

// ---- Indexes ----
db.portfolios.createIndex({ "status": 1 });
db.portfolios.createIndex({ "fund_name": 1 });
db.portfolios.createIndex({ "created_at": -1 });

db.positions.createIndex({ "portfolio_id": 1 });
db.positions.createIndex({ "symbol": 1 });
db.positions.createIndex({ "sector": 1 });
db.positions.createIndex({ "country": 1 });
db.positions.createIndex({ "portfolio_id": 1, "symbol": 1 }, { unique: true });

db.risk_limits.createIndex({ "portfolio_id": 1 }, { unique: true });

db.assessments.createIndex({ "portfolio_id": 1, "timestamp": -1 });
db.assessments.createIndex({ "claude_analysis.severity": 1 });
db.assessments.createIndex({ "status": 1 });

db.alerts.createIndex({ "portfolio_id": 1 });
db.alerts.createIndex({ "severity": 1 });
db.alerts.createIndex({ "status": 1 });
db.alerts.createIndex({ "created_at": -1 });

db.audit_logs.createIndex({ "timestamp": -1 });
db.audit_logs.createIndex({ "action": 1 });
db.audit_logs.createIndex({ "portfolio_id": 1 });

db.market_data.createIndex({ "symbol": 1, "timestamp": -1 });
db.market_data.createIndex({ "timestamp": -1 }, { expireAfterSeconds: 86400 }); // TTL: 24h

db.notifications.createIndex({ "alert_id": 1 });
db.notifications.createIndex({ "status": 1 });
db.notifications.createIndex({ "created_at": -1 });

print('✅ RiskLens AI database initialized with collections and indexes');
