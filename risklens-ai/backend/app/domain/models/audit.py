"""
RiskLens AI — Audit & Configuration Domain Models
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from app.core.constants import DEFAULT_RISK_LIMITS, DEFAULT_WARNING_BUFFER_PCT


class RiskLimits(BaseModel):
    """Configurable risk limits for a portfolio."""
    single_issuer_max: float = DEFAULT_RISK_LIMITS["single_issuer_max"]
    sector_max: float = DEFAULT_RISK_LIMITS["sector_max"]
    geography_max: float = DEFAULT_RISK_LIMITS["geography_max"]
    asset_class_max: float = DEFAULT_RISK_LIMITS["asset_class_max"]
    correlation_threshold: float = DEFAULT_RISK_LIMITS["correlation_threshold"]
    min_holdings: int = DEFAULT_RISK_LIMITS["min_holdings"]
    max_cash_percentage: float = DEFAULT_RISK_LIMITS["max_cash_percentage"]


class RiskLimitConfig(BaseModel):
    """Risk limit configuration for a specific portfolio."""
    id: str = Field(..., alias="_id")
    portfolio_id: str
    limits: RiskLimits = RiskLimits()
    warning_buffer_pct: float = DEFAULT_WARNING_BUFFER_PCT
    is_default: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: str = "system"

    model_config = {"populate_by_name": True}


class AuditLog(BaseModel):
    """Immutable audit log entry."""
    id: str = Field(..., alias="_id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    action: str = Field(..., description="e.g., risk_assessment_completed, alert_created")
    actor: str = Field(default="system", description="User or system that performed the action")
    portfolio_id: Optional[str] = None
    assessment_id: Optional[str] = None
    alert_id: Optional[str] = None
    details: Dict[str, Any] = {}
    request_metadata: Dict[str, Any] = {}
    previous_hash: str = ""
    entry_hash: str = ""
    crypto_signature: str = ""

    def compute_hash_and_signature(self) -> tuple[str, str]:
        """Compute the SHA-256 hash and RSA signature of this audit log entry."""
        import hashlib
        import json
        import base64
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes
        
        # Stabilize JSON structures
        details_str = json.dumps(self.details, sort_keys=True, default=str)
        metadata_str = json.dumps(self.request_metadata, sort_keys=True, default=str)
        
        raw_payload = (
            f"{self.id}|{self.timestamp.isoformat()}|{self.action}|{self.actor}|"
            f"{self.portfolio_id or ''}|{self.assessment_id or ''}|{self.alert_id or ''}|"
            f"{details_str}|{metadata_str}|{self.previous_hash}"
        )
        payload_bytes = raw_payload.encode("utf-8")
        entry_hash = hashlib.sha256(payload_bytes).hexdigest()

        # In a real app, this key would be securely loaded from a KMS/Vault.
        # For the hackathon, we generate an ephemeral signing key to demonstrate SEC 17a-4 immutability.
        if not hasattr(self, "_signing_key"):
            self.__class__._signing_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
        
        signature = self.__class__._signing_key.sign(
            payload_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        return entry_hash, signature_b64

    model_config = {"populate_by_name": True}


class MarketDataPoint(BaseModel):
    """A single market data snapshot for a symbol."""
    id: str = Field(..., alias="_id")
    symbol: str
    price: float
    previous_close: float = 0.0
    day_change_pct: float = 0.0
    volume: int = 0
    volatility_30d: float = 0.0
    volatility_30d_prev_quarter: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "yahoo_finance"

    model_config = {"populate_by_name": True}
