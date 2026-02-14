from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from middlewares.auth import verify_auth_token
from services.budget_service import BudgetService, BudgetItemCreate, BudgetCreate, RevenueStreamSave
from schemas.budget_schemas import RevenueStreamInitial

router = APIRouter(
    tags=["Budget"],
    dependencies=[Depends(verify_auth_token)]
)


@router.get("/sessions/{session_id}/budget")
async def get_budget(session_id: str, request: Request):
    """Get budget for a session"""
    user_id = request.state.user["id"]
    try:
        budget = await BudgetService.get_budget_data(user_id, session_id)
        return {"success": True, "result": budget}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get budget: {str(e)}")


@router.post("/sessions/{session_id}/budget")
async def create_or_update_budget(session_id: str, request: Request, budget_data: BudgetCreate):
    """Create or update budget for a session"""
    user_id = request.state.user["id"]
    try:
        budget = await BudgetService.create_or_update_budget(user_id, session_id, budget_data)
        return {"success": True, "result": budget}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save budget: {str(e)}")


@router.patch("/sessions/{session_id}/budget")
async def update_budget_header(session_id: str, request: Request):
    """Update budget header fields (e.g. initial_investment)"""
    user_id = request.state.user["id"]
    try:
        body = await request.json()
        budget = await BudgetService.update_budget_header(user_id, session_id, body)
        return {"success": True, "result": budget}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update budget: {str(e)}")


@router.post("/sessions/{session_id}/budget/items")
async def add_budget_item(session_id: str, request: Request, item: BudgetItemCreate):
    """Add a new budget item"""
    user_id = request.state.user["id"]
    try:
        budget = await BudgetService.add_budget_item(user_id, session_id, item)
        return {"success": True, "result": budget}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add budget item: {str(e)}")


@router.put("/sessions/{session_id}/budget/items/{item_id}")
async def update_budget_item(session_id: str, item_id: str, request: Request, updates: Dict[str, Any]):
    """Update a budget item"""
    user_id = request.state.user["id"]
    try:
        budget = await BudgetService.update_budget_item(user_id, session_id, item_id, updates)
        return {"success": True, "result": budget}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update budget item: {str(e)}")


@router.delete("/sessions/{session_id}/budget/items/{item_id}")
async def delete_budget_item(session_id: str, item_id: str, request: Request):
    """Delete a budget item"""
    user_id = request.state.user["id"]
    try:
        budget = await BudgetService.delete_budget_item(user_id, session_id, item_id)
        return {"success": True, "result": budget}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete budget item: {str(e)}")


@router.post("/sessions/{session_id}/budget/generate-estimates")
async def generate_estimated_expenses(session_id: str, request: Request):
    """Generate estimated expenses based on business plan context"""
    user_id = request.state.user["id"]
    try:
        budget_items = await BudgetService.generate_initial_expenses(user_id, session_id)
        return {"success": True, "result": budget_items}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate estimated expenses: {str(e)}")


@router.get("/sessions/{session_id}/revenue-streams/generate")
async def generate_revenue_streams(session_id: str, request: Request):
    """Generate initial revenue streams based on the business type"""
    user_id = request.state.user["id"]
    try:
        initial_streams = await BudgetService.generate_initial_revenue_streams(user_id, session_id)
        return {"success": True, "result": initial_streams}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate revenue streams: {str(e)}")


@router.get("/sessions/{session_id}/revenue-streams")
async def get_revenue_streams(session_id: str, request: Request):
    """Get saved revenue streams from DB"""
    user_id = request.state.user["id"]
    try:
        streams = await BudgetService.get_revenue_streams(user_id, session_id)
        return {"success": True, "result": streams}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get revenue streams: {str(e)}")


@router.put("/sessions/{session_id}/revenue-streams")
async def save_revenue_streams(session_id: str, request: Request, revenue_streams: List[RevenueStreamSave]):
    """Saves selected revenue streams, updating budget items and totals"""
    user_id = request.state.user["id"]
    try:
        result = await BudgetService.save_revenue_streams(user_id, session_id, revenue_streams)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save revenue streams: {str(e)}")


@router.get("/sessions/{session_id}/budget/summary")
async def get_budget_summary(session_id: str, request: Request):
    """Get budget summary statistics"""
    user_id = request.state.user["id"]
    try:
        summary = await BudgetService.get_budget_summary(user_id, session_id)
        return {"success": True, "result": summary}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get budget summary: {str(e)}")
