"""
RiskLens AI — Application Constants
Centralized constants used across the application.
"""

# --- Risk Severity Levels ---
SEVERITY_LOW = "LOW"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_HIGH = "HIGH"
SEVERITY_CRITICAL = "CRITICAL"

SEVERITY_ORDER = {
    SEVERITY_LOW: 1,
    SEVERITY_MEDIUM: 2,
    SEVERITY_HIGH: 3,
    SEVERITY_CRITICAL: 4,
}

# --- Breach Status ---
STATUS_OK = "OK"
STATUS_WARNING = "WARNING"
STATUS_BREACH = "BREACH"
STATUS_FLAGGED = "FLAGGED"

# --- Alert Status ---
ALERT_ACTIVE = "active"
ALERT_ACKNOWLEDGED = "acknowledged"
ALERT_RESOLVED = "resolved"

# --- Assessment Triggers ---
TRIGGER_MANUAL = "manual"
TRIGGER_SCHEDULED = "scheduled"
TRIGGER_KAFKA_EVENT = "kafka_event"
TRIGGER_PRICE_CHANGE = "price_change"

# --- Default Risk Limits ---
DEFAULT_RISK_LIMITS = {
    "single_issuer_max": 8.0,
    "sector_max": 25.0,
    "geography_max": 70.0,
    "asset_class_max": 60.0,
    "correlation_threshold": 0.85,
    "min_holdings": 5,
    "max_cash_percentage": 40.0,
}

DEFAULT_WARNING_BUFFER_PCT = 3.0

# --- Kafka Topics ---
TOPIC_MARKET_PRICES = "market.prices.realtime"
TOPIC_PORTFOLIO_EVENTS = "portfolio.events"
TOPIC_RISK_ASSESSMENTS = "risk.assessments"
TOPIC_NOTIFICATIONS = "notifications.outbound"

# --- Asset Classes ---
ASSET_CLASS_EQUITY = "equity"
ASSET_CLASS_BOND = "bond"
ASSET_CLASS_DERIVATIVE = "derivative"
ASSET_CLASS_CASH = "cash"
ASSET_CLASS_COMMODITY = "commodity"

VALID_ASSET_CLASSES = [
    ASSET_CLASS_EQUITY,
    ASSET_CLASS_BOND,
    ASSET_CLASS_DERIVATIVE,
    ASSET_CLASS_CASH,
    ASSET_CLASS_COMMODITY,
]

# --- Notification Channels ---
CHANNEL_EMAIL = "email"
CHANNEL_JIRA = "jira"
CHANNEL_WEBSOCKET = "websocket"
CHANNEL_DASHBOARD = "dashboard"

# --- Escalation Rules ---
# Maps severity to which notification channels should fire
ESCALATION_MATRIX = {
    SEVERITY_LOW: [CHANNEL_DASHBOARD],
    SEVERITY_MEDIUM: [CHANNEL_DASHBOARD, CHANNEL_EMAIL],
    SEVERITY_HIGH: [CHANNEL_DASHBOARD, CHANNEL_EMAIL, CHANNEL_JIRA],
    SEVERITY_CRITICAL: [CHANNEL_DASHBOARD, CHANNEL_EMAIL, CHANNEL_JIRA, CHANNEL_WEBSOCKET],
}
