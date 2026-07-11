"""
RiskLens AI — Autonomous Agent API Endpoints
Endpoints for Agentic Auto-Hedging and rebalancing execution.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from datetime import datetime
from pydantic import BaseModel
from app.infrastructure.database.repositories.portfolio_repo import PortfolioRepository, PositionRepository
from app.infrastructure.database.repositories.assessment_repo import AssessmentRepository, AuditRepository
from app.domain.models.risk import ProposedTrade
from app.api.dependencies import verify_cro_role
from app.core.logger import get_logger

logger = get_logger("api.agent")
router = APIRouter()


class RebalanceRequest(BaseModel):
    portfolio_id: str
    assessment_id: str
    trades: List[ProposedTrade]


@router.post("/execute")
async def execute_rebalance(
    request: RebalanceRequest,
    role: str = Depends(verify_cro_role),
):
    """
    Execute AI-proposed trades to rebalance an over-concentrated portfolio.
    This acts as the 'Agentic Auto-Hedger', mutating the portfolio state.
    """
    logger.info(f"Agentic rebalance requested for {request.portfolio_id} by {role}")

    # 1. Fetch Portfolio
    portfolio = await PortfolioRepository.get_by_id(request.portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # 2. Fetch current positions
    positions = await PositionRepository.get_by_portfolio(request.portfolio_id)
    if not positions:
        raise HTTPException(status_code=400, detail="Portfolio has no positions")

    total_nav = portfolio.get("total_nav", 0.0)
    if total_nav <= 0:
        raise HTTPException(status_code=400, detail="Invalid portfolio NAV")

    # Create a quick lookup for positions
    pos_map = {p["symbol"]: p for p in positions}

    trades_executed = []
    
    # 3. Apply trades
    for trade in request.trades:
        symbol = trade.symbol.upper()
        action = trade.action.upper()
        trade_value = total_nav * (trade.amount_pct / 100.0)

        if symbol in pos_map:
            pos = pos_map[symbol]
            current_val = pos.get("market_value", 0.0)
            
            if action == "SELL":
                # Ensure we don't oversell (for simplicity, cap at current value for long positions)
                if str(pos.get("position_type", "long")).lower() == "long":
                    actual_trade_val = min(trade_value, current_val)
                    pos["market_value"] -= actual_trade_val
                else:
                    pos["market_value"] -= trade_value
                    actual_trade_val = trade_value
                
                logger.info(f"Executed SELL of {symbol}: {actual_trade_val}")
                trades_executed.append({"symbol": symbol, "action": "SELL", "value": actual_trade_val})
            elif action == "BUY":
                pos["market_value"] += trade_value
                logger.info(f"Executed BUY of {symbol}: {trade_value}")
                trades_executed.append({"symbol": symbol, "action": "BUY", "value": trade_value})
        else:
            # If buying a new symbol, we would ideally need more info (sector, etc.)
            # For hackathon purposes, we mock the addition
            if action == "BUY":
                new_pos = {
                    "portfolio_id": request.portfolio_id,
                    "symbol": symbol,
                    "name": symbol,
                    "asset_class": "equity",
                    "sector": "unknown",
                    "country": "unknown",
                    "market_value": trade_value,
                    "position_type": "long"
                }
                pos_map[symbol] = new_pos
                positions.append(new_pos)
                logger.info(f"Executed BUY (New Position) of {symbol}: {trade_value}")
                trades_executed.append({"symbol": symbol, "action": "BUY", "value": trade_value})

    # 4. Recalculate NAV
    new_total_nav = sum(p.get("market_value", 0.0) for p in positions)
    
    # 5. Save positions back
    await PositionRepository.delete_by_portfolio(request.portfolio_id)
    await PositionRepository.insert_many(positions)
    
    # 6. Update portfolio NAV and timestamp
    await PortfolioRepository.update(request.portfolio_id, {
        "total_nav": new_total_nav,
        "position_count": len(positions),
        "last_updated": datetime.utcnow().isoformat()
    })

    # 7. Log in Audit Repository
    import uuid
    audit_entry = {
        "_id": f"AUDIT-{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.utcnow().isoformat(),
        "action": "agentic_rebalance_executed",
        "actor": f"api:{role.lower()}",
        "portfolio_id": request.portfolio_id,
        "assessment_id": request.assessment_id,
        "details": {
            "trades_requested": len(request.trades),
            "trades_executed": len(trades_executed),
            "previous_nav": total_nav,
            "new_nav": new_total_nav,
            "executed_trade_list": trades_executed,
        },
    }
    await AuditRepository.create(audit_entry)

    return {
        "message": "Agentic rebalance executed successfully",
        "portfolio_id": request.portfolio_id,
        "previous_nav": total_nav,
        "new_nav": new_total_nav,
        "trades_executed": trades_executed
    }
