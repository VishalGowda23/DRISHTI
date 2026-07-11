"""
RiskLens AI — Portfolio API Endpoints
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from typing import Optional
from app.services.ingestion_service import IngestionService
from app.infrastructure.database.repositories.portfolio_repo import PortfolioRepository, PositionRepository
from app.infrastructure.database.repositories.assessment_repo import AssessmentRepository

router = APIRouter()


@router.post("/upload", status_code=201)
async def upload_portfolio(
    file: UploadFile = File(...),
    fund_name: str = Form(...),
    fund_type: str = Form(default="Multi-Asset"),
):
    """Upload portfolio holdings from CSV or JSON file."""
    content = await file.read()
    filename = file.filename or ""

    try:
        if filename.endswith(".json"):
            import json
            data = json.loads(content)
            portfolio_id, count = await IngestionService.ingest_from_json(
                data=data, fund_name=fund_name, fund_type=fund_type,
            )
        elif filename.endswith(".csv"):
            portfolio_id, count = await IngestionService.ingest_from_csv(
                file_content=content, fund_name=fund_name, fund_type=fund_type,
            )
        else:
            raise HTTPException(status_code=422, detail="Unsupported file format. Use .csv or .json")

        return {
            "portfolio_id": portfolio_id,
            "fund_name": fund_name,
            "positions_count": count,
            "status": "ingested",
            "message": "Portfolio ingested successfully. Use /risk/analyze to run risk analysis.",
        }

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.get("")
async def list_portfolios(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """List all portfolios."""
    portfolios, total = await PortfolioRepository.list_all(status=status, page=page, limit=limit)
    return {"portfolios": portfolios, "total": total, "page": page, "limit": limit}


@router.get("/{portfolio_id}")
async def get_portfolio(portfolio_id: str):
    """Get portfolio detail with positions and latest assessment."""
    portfolio = await PortfolioRepository.get_by_id(portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    positions = await PositionRepository.get_by_portfolio(portfolio_id)
    latest = await AssessmentRepository.get_latest(portfolio_id)

    return {
        "portfolio": portfolio,
        "positions": positions,
        "latest_assessment": latest,
    }


@router.delete("/{portfolio_id}")
async def delete_portfolio(portfolio_id: str):
    """Delete a portfolio and all its positions."""
    deleted = await PortfolioRepository.delete(portfolio_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return {"message": "Portfolio deleted", "portfolio_id": portfolio_id}
