"""
RiskLens AI — Domain Enumerations
Shared enums used across the domain layer.
"""

from enum import Enum


class Severity(str, Enum):
    """Risk severity classification levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class BreachStatus(str, Enum):
    """Status of a concentration limit check."""
    OK = "OK"
    WARNING = "WARNING"
    BREACH = "BREACH"
    FLAGGED = "FLAGGED"


class AlertStatus(str, Enum):
    """Lifecycle status of an alert."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AssetClass(str, Enum):
    """Supported asset classes."""
    EQUITY = "equity"
    BOND = "bond"
    DERIVATIVE = "derivative"
    CASH = "cash"
    COMMODITY = "commodity"


class ConcentrationType(str, Enum):
    """Types of concentration risk checks."""
    ISSUER = "issuer_concentration"
    SECTOR = "sector_concentration"
    GEOGRAPHY = "geography_concentration"
    ASSET_CLASS = "asset_class_concentration"
    CORRELATION = "correlation_cluster"


class AssessmentTrigger(str, Enum):
    """What triggered a risk assessment."""
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    KAFKA_EVENT = "kafka_event"
    PRICE_CHANGE = "price_change"


class NotificationChannel(str, Enum):
    """Available notification channels."""
    EMAIL = "email"
    JIRA = "jira"
    WEBSOCKET = "websocket"
    DASHBOARD = "dashboard"


class NotificationStatus(str, Enum):
    """Delivery status of a notification."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class PortfolioStatus(str, Enum):
    """Lifecycle status of a portfolio."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
