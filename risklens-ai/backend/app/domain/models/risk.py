"""
RiskLens AI — Risk Domain Models
Models for risk assessments, breaches, alerts, and scoring.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from app.domain.enums import (
    Severity, BreachStatus, AlertStatus,
    ConcentrationType, AssessmentTrigger,
    NotificationChannel, NotificationStatus,
)


# ---- Rule Engine Results ----

class ConcentrationCheck(BaseModel):
    """Result of a single concentration limit check."""
    entity: str = Field(..., description="Issuer name, sector name, or country")
    concentration_type: ConcentrationType
    nav_pct: float = Field(..., description="Current concentration as % of NAV")
    limit: float = Field(..., description="Configured limit as %")
    status: BreachStatus
    excess_pct: float = Field(default=0.0, description="How much over the limit (negative = under)")
    buffer_pct: float = Field(default=0.0, description="Distance to limit")


class CorrelationCluster(BaseModel):
    """A group of correlated holdings."""
    holdings: List[str]
    avg_correlation: float
    status: BreachStatus


class RuleEngineResults(BaseModel):
    """Complete output from the rule-based risk engine."""
    issuer_checks: List[ConcentrationCheck] = []
    sector_checks: List[ConcentrationCheck] = []
    geography_checks: List[ConcentrationCheck] = []
    asset_class_checks: List[ConcentrationCheck] = []
    correlation_clusters: List[CorrelationCluster] = []
    historical_var_95: float = 0.0
    total_breaches: int = 0
    total_warnings: int = 0


# ---- Claude AI Analysis ----

class BreachAnalysis(BaseModel):
    """Claude's analysis of a specific breach."""
    type: str
    entity: str
    assessment: str
    risk_level: Severity


class ProposedTrade(BaseModel):
    """A proposed trade suggested by the AI to rebalance the portfolio."""
    action: str = Field(..., description="BUY or SELL")
    symbol: str = Field(..., description="Ticker symbol to trade")
    amount_pct: float = Field(..., description="Percentage of NAV to trade")
    rationale: str = Field(..., description="Reason for this trade")


class ClaudeAnalysis(BaseModel):
    """Structured output from Claude AI analysis."""
    severity: Severity
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str = Field(..., description="2-3 sentence executive summary")
    breach_analysis: List[BreachAnalysis] = []
    volatility_context: str = ""
    historical_pattern: str = ""
    recommended_actions: List[str] = []
    proposed_trades: List[ProposedTrade] = []
    estimated_review_time_minutes: int = 15
    overall_verdict: str = ""


class ModelInfo(BaseModel):
    """Metadata about the LLM call."""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost_usd: float = 0.0
    langsmith_trace_id: str = ""


# ---- Assessment ----

class RiskAssessment(BaseModel):
    """Complete risk assessment combining rule engine + Claude analysis."""
    id: str = Field(..., alias="_id")
    portfolio_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trigger: AssessmentTrigger = AssessmentTrigger.MANUAL
    status: str = "completed"
    nav_at_assessment: float = 0.0
    rule_engine_results: RuleEngineResults = RuleEngineResults()
    claude_analysis: Optional[ClaudeAnalysis] = None
    model_info: ModelInfo = ModelInfo()
    processing_time_ms: int = 0

    model_config = {"populate_by_name": True}


# ---- Alert ----

class NotificationRecord(BaseModel):
    """Record of a notification sent for an alert."""
    channel: NotificationChannel
    recipient: str = ""
    sent_at: Optional[datetime] = None
    status: NotificationStatus = NotificationStatus.PENDING
    ticket_id: Optional[str] = None
    error: Optional[str] = None


class Alert(BaseModel):
    """An alert generated from a risk assessment breach."""
    id: str = Field(..., alias="_id")
    assessment_id: str
    portfolio_id: str
    severity: Severity
    title: str
    summary: str
    breach_type: ConcentrationType
    breach_details: dict = {}
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    notifications_sent: List[NotificationRecord] = []

    model_config = {"populate_by_name": True}
