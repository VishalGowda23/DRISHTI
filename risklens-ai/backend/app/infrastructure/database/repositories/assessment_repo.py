"""
RiskLens AI — Assessment, Alert, Audit, and Config Repositories
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from app.infrastructure.database.mongodb import get_collection
from app.core.logger import get_logger

logger = get_logger("repo")


class AssessmentRepository:
    """Repository for risk assessments."""

    @staticmethod
    async def create(assessment: dict) -> str:
        collection = get_collection("assessments")
        result = await collection.insert_one(assessment)
        return str(result.inserted_id)

    @staticmethod
    async def get_by_id(assessment_id: str) -> Optional[dict]:
        collection = get_collection("assessments")
        return await collection.find_one({"_id": assessment_id})

    @staticmethod
    async def list_by_portfolio(
        portfolio_id: str,
        severity: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[List[dict], int]:
        collection = get_collection("assessments")
        query: Dict[str, Any] = {"portfolio_id": portfolio_id}
        if severity:
            query["claude_analysis.severity"] = severity
        total = await collection.count_documents(query)
        cursor = collection.find(query).sort("timestamp", -1).skip((page - 1) * limit).limit(limit)
        return await cursor.to_list(length=limit), total

    @staticmethod
    async def get_latest(portfolio_id: str) -> Optional[dict]:
        collection = get_collection("assessments")
        return await collection.find_one(
            {"portfolio_id": portfolio_id},
            sort=[("timestamp", -1)],
        )


class AlertRepository:
    """Repository for alerts."""

    @staticmethod
    async def create(alert: dict) -> str:
        collection = get_collection("alerts")
        result = await collection.insert_one(alert)
        return str(result.inserted_id)

    @staticmethod
    async def get_by_id(alert_id: str) -> Optional[dict]:
        collection = get_collection("alerts")
        return await collection.find_one({"_id": alert_id})

    @staticmethod
    async def list_alerts(
        portfolio_id: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[List[dict], int]:
        collection = get_collection("alerts")
        query: Dict[str, Any] = {}
        if portfolio_id:
            query["portfolio_id"] = portfolio_id
        if severity:
            query["severity"] = {"$in": severity.split(",")}
        if status:
            query["status"] = status
        total = await collection.count_documents(query)
        cursor = collection.find(query).sort("created_at", -1).skip((page - 1) * limit).limit(limit)
        return await cursor.to_list(length=limit), total

    @staticmethod
    async def acknowledge(alert_id: str, acknowledged_by: str, notes: str = "") -> bool:
        collection = get_collection("alerts")
        result = await collection.update_one(
            {"_id": alert_id},
            {"$set": {
                "status": "acknowledged",
                "acknowledged_by": acknowledged_by,
                "acknowledged_at": datetime.utcnow().isoformat(),
            }},
        )
        return result.modified_count > 0

    @staticmethod
    async def update_notifications(alert_id: str, notification: dict) -> bool:
        collection = get_collection("alerts")
        result = await collection.update_one(
            {"_id": alert_id},
            {"$push": {"notifications_sent": notification}},
        )
        return result.modified_count > 0


class AuditRepository:
    """Repository for audit logs — append-only with cryptographic hash-chaining."""

    @staticmethod
    async def create(log_entry: dict) -> str:
        from app.domain.models.audit import AuditLog
        collection = get_collection("audit_logs")

        # 1. Fetch previous entry to establish previous_hash for the chain
        previous_entry = await collection.find_one(
            sort=[("timestamp", -1)]
        )
        previous_hash = previous_entry.get("entry_hash", "") if previous_entry else ""

        # 2. Hydrate model and compute current hash
        log_entry["previous_hash"] = previous_hash
        
        # Ensure timestamp is a datetime object for validation
        ts = log_entry.get("timestamp")
        if isinstance(ts, str):
            try:
                log_entry["timestamp"] = datetime.fromisoformat(ts)
            except Exception:
                log_entry["timestamp"] = datetime.utcnow()
        elif not ts:
            log_entry["timestamp"] = datetime.utcnow()

        audit_model = AuditLog(**log_entry)
        entry_hash, crypto_signature = audit_model.compute_hash_and_signature()

        # 3. Write back with hashes
        log_entry["entry_hash"] = entry_hash
        log_entry["crypto_signature"] = crypto_signature
        # Normalize timestamp back to isoformat for storage consistency if needed, 
        # or leave as datetime object which PyMongo handles natively.
        result = await collection.insert_one(log_entry)
        return str(result.inserted_id)

    @staticmethod
    async def list_logs(
        portfolio_id: Optional[str] = None,
        action: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[List[dict], int]:
        collection = get_collection("audit_logs")
        query: Dict[str, Any] = {}
        if portfolio_id:
            query["portfolio_id"] = portfolio_id
        if action:
            query["action"] = action
        total = await collection.count_documents(query)
        cursor = collection.find(query).sort("timestamp", -1).skip((page - 1) * limit).limit(limit)
        return await cursor.to_list(length=limit), total


class ConfigRepository:
    """Repository for risk limit configurations."""

    @staticmethod
    async def get_limits(portfolio_id: str) -> Optional[dict]:
        collection = get_collection("risk_limits")
        return await collection.find_one({"portfolio_id": portfolio_id})

    @staticmethod
    async def upsert_limits(portfolio_id: str, config: dict) -> bool:
        collection = get_collection("risk_limits")
        config["portfolio_id"] = portfolio_id
        config["_id"] = f"RL-{portfolio_id}"
        result = await collection.replace_one(
            {"portfolio_id": portfolio_id},
            config,
            upsert=True,
        )
        return result.acknowledged

    @staticmethod
    async def get_or_default(portfolio_id: str) -> dict:
        """Get configured limits or return defaults."""
        from app.core.constants import DEFAULT_RISK_LIMITS, DEFAULT_WARNING_BUFFER_PCT
        config = await ConfigRepository.get_limits(portfolio_id)
        if config:
            return config
        return {
            "_id": f"RL-{portfolio_id}",
            "portfolio_id": portfolio_id,
            "limits": DEFAULT_RISK_LIMITS,
            "warning_buffer_pct": DEFAULT_WARNING_BUFFER_PCT,
            "is_default": True,
        }
