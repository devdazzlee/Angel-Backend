from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
from db.supabase import supabase
from middlewares.auth import verify_auth_token

router = APIRouter(
    tags=["Budget"],
    dependencies=[Depends(verify_auth_token)]
)


class BudgetItemCreate(BaseModel):
    name: str
    category: str  # 'expense' or 'revenue'
    estimated_amount: float
    actual_amount: Optional[float] = None
    description: Optional[str] = None
    is_custom: Optional[bool] = True


class BudgetCreate(BaseModel):
    session_id: str
    initial_investment: float
    total_estimated_expenses: float
    total_estimated_revenue: float
    items: List[Dict[str, Any]]


class BudgetUpdate(BaseModel):
    initial_investment: Optional[float] = None
    total_estimated_expenses: Optional[float] = None
    total_estimated_revenue: Optional[float] = None
    total_actual_expenses: Optional[float] = None
    total_actual_revenue: Optional[float] = None


@router.get("/sessions/{session_id}/budget")
async def get_budget(session_id: str, request: Request):
    """Get budget for a session"""
    user_id = request.state.user["id"]
    
    try:
        # Get session to verify ownership
        session_response = supabase.table("chat_sessions").select("id, user_id").eq("id", session_id).eq("user_id", user_id).execute()
        
        if not session_response.data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get budget
        budget_response = supabase.table("budgets").select("*").eq("session_id", session_id).execute()
        
        if not budget_response.data:
            # Return empty budget structure
            return {
                "success": True,
                "result": {
                    "id": "",
                    "session_id": session_id,
                    "initial_investment": 0,
                    "total_estimated_expenses": 0,
                    "total_estimated_revenue": 0,
                    "total_actual_expenses": 0,
                    "total_actual_revenue": 0,
                    "items": [],
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
            }
        
        budget = budget_response.data[0]
        
        # Get budget items
        items_response = supabase.table("budget_items").select("*").eq("budget_id", budget["id"]).order("created_at").execute()
        budget["items"] = items_response.data if items_response.data else []
        
        return {
            "success": True,
            "result": budget
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting budget: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get budget: {str(e)}")


@router.post("/sessions/{session_id}/budget")
async def create_or_update_budget(session_id: str, request: Request, budget_data: BudgetCreate):
    """Create or update budget for a session"""
    user_id = request.state.user["id"]
    
    try:
        # Verify session ownership
        session_response = supabase.table("chat_sessions").select("id, user_id").eq("id", session_id).eq("user_id", user_id).execute()
        
        if not session_response.data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Check if budget exists
        existing_budget = supabase.table("budgets").select("id").eq("session_id", session_id).execute()
        
        budget_payload = {
            "session_id": session_id,
            "user_id": user_id,
            "initial_investment": budget_data.initial_investment,
            "total_estimated_expenses": budget_data.total_estimated_expenses,
            "total_estimated_revenue": budget_data.total_estimated_revenue,
            "total_actual_expenses": 0,
            "total_actual_revenue": 0,
            "updated_at": datetime.now().isoformat()
        }
        
        if existing_budget.data:
            # Update existing budget
            budget_id = existing_budget.data[0]["id"]
            supabase.table("budgets").update(budget_payload).eq("id", budget_id).execute()
            
            # Delete old items
            supabase.table("budget_items").delete().eq("budget_id", budget_id).execute()
        else:
            # Create new budget
            budget_payload["created_at"] = datetime.now().isoformat()
            budget_response = supabase.table("budgets").insert(budget_payload).execute()
            budget_id = budget_response.data[0]["id"]
        
        # Insert budget items
        items_to_insert = []
        for item in budget_data.items:
            items_to_insert.append({
                "budget_id": budget_id,
                "name": item.get("name", ""),
                "category": item.get("category", "expense"),
                "estimated_amount": item.get("estimated_amount", 0),
                "actual_amount": item.get("actual_amount"),
                "description": item.get("description"),
                "is_custom": item.get("is_custom", True),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            })
        
        if items_to_insert:
            supabase.table("budget_items").insert(items_to_insert).execute()
        
        # Get updated budget
        budget_response = supabase.table("budgets").select("*").eq("id", budget_id).execute()
        budget = budget_response.data[0]
        
        items_response = supabase.table("budget_items").select("*").eq("budget_id", budget_id).order("created_at").execute()
        budget["items"] = items_response.data if items_response.data else []
        
        return {
            "success": True,
            "result": budget
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error saving budget: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save budget: {str(e)}")


@router.post("/sessions/{session_id}/budget/items")
async def add_budget_item(session_id: str, request: Request, item: BudgetItemCreate):
    """Add a new budget item"""
    user_id = request.state.user["id"]
    
    try:
        # Get budget
        budget_response = supabase.table("budgets").select("id").eq("session_id", session_id).eq("user_id", user_id).execute()
        
        if not budget_response.data:
            raise HTTPException(status_code=404, detail="Budget not found")
        
        budget_id = budget_response.data[0]["id"]
        
        # Insert item
        item_data = {
            "budget_id": budget_id,
            "name": item.name,
            "category": item.category,
            "estimated_amount": item.estimated_amount,
            "actual_amount": item.actual_amount,
            "description": item.description,
            "is_custom": item.is_custom,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        item_response = supabase.table("budget_items").insert(item_data).execute()
        new_item = item_response.data[0]
        
        # Update budget totals
        items_response = supabase.table("budget_items").select("estimated_amount, actual_amount, category").eq("budget_id", budget_id).execute()
        items = items_response.data if items_response.data else []
        
        total_estimated_expenses = sum(i["estimated_amount"] for i in items if i["category"] == "expense")
        total_estimated_revenue = sum(i["estimated_amount"] for i in items if i["category"] == "revenue")
        total_actual_expenses = sum(i.get("actual_amount", 0) or 0 for i in items if i["category"] == "expense")
        total_actual_revenue = sum(i.get("actual_amount", 0) or 0 for i in items if i["category"] == "revenue")
        
        supabase.table("budgets").update({
            "total_estimated_expenses": total_estimated_expenses,
            "total_estimated_revenue": total_estimated_revenue,
            "total_actual_expenses": total_actual_expenses,
            "total_actual_revenue": total_actual_revenue,
            "updated_at": datetime.now().isoformat()
        }).eq("id", budget_id).execute()
        
        # Get updated budget
        budget_response = supabase.table("budgets").select("*").eq("id", budget_id).execute()
        budget = budget_response.data[0]
        
        items_response = supabase.table("budget_items").select("*").eq("budget_id", budget_id).order("created_at").execute()
        budget["items"] = items_response.data if items_response.data else []
        
        return {
            "success": True,
            "result": budget
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error adding budget item: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add budget item: {str(e)}")


@router.put("/sessions/{session_id}/budget/items/{item_id}")
async def update_budget_item(session_id: str, item_id: str, request: Request, updates: Dict[str, Any]):
    """Update a budget item"""
    user_id = request.state.user["id"]
    
    try:
        # Verify budget ownership
        budget_response = supabase.table("budgets").select("id").eq("session_id", session_id).eq("user_id", user_id).execute()
        
        if not budget_response.data:
            raise HTTPException(status_code=404, detail="Budget not found")
        
        budget_id = budget_response.data[0]["id"]
        
        # Update item
        updates["updated_at"] = datetime.now().isoformat()
        supabase.table("budget_items").update(updates).eq("id", item_id).eq("budget_id", budget_id).execute()
        
        # Update budget totals
        items_response = supabase.table("budget_items").select("estimated_amount, actual_amount, category").eq("budget_id", budget_id).execute()
        items = items_response.data if items_response.data else []
        
        total_estimated_expenses = sum(i["estimated_amount"] for i in items if i["category"] == "expense")
        total_estimated_revenue = sum(i["estimated_amount"] for i in items if i["category"] == "revenue")
        total_actual_expenses = sum(i.get("actual_amount", 0) or 0 for i in items if i["category"] == "expense")
        total_actual_revenue = sum(i.get("actual_amount", 0) or 0 for i in items if i["category"] == "revenue")
        
        supabase.table("budgets").update({
            "total_estimated_expenses": total_estimated_expenses,
            "total_estimated_revenue": total_estimated_revenue,
            "total_actual_expenses": total_actual_expenses,
            "total_actual_revenue": total_actual_revenue,
            "updated_at": datetime.now().isoformat()
        }).eq("id", budget_id).execute()
        
        # Get updated budget
        budget_response = supabase.table("budgets").select("*").eq("id", budget_id).execute()
        budget = budget_response.data[0]
        
        items_response = supabase.table("budget_items").select("*").eq("budget_id", budget_id).order("created_at").execute()
        budget["items"] = items_response.data if items_response.data else []
        
        return {
            "success": True,
            "result": budget
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating budget item: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update budget item: {str(e)}")


@router.delete("/sessions/{session_id}/budget/items/{item_id}")
async def delete_budget_item(session_id: str, item_id: str, request: Request):
    """Delete a budget item"""
    user_id = request.state.user["id"]
    
    try:
        # Verify budget ownership
        budget_response = supabase.table("budgets").select("id").eq("session_id", session_id).eq("user_id", user_id).execute()
        
        if not budget_response.data:
            raise HTTPException(status_code=404, detail="Budget not found")
        
        budget_id = budget_response.data[0]["id"]
        
        # Delete item
        supabase.table("budget_items").delete().eq("id", item_id).eq("budget_id", budget_id).execute()
        
        # Update budget totals
        items_response = supabase.table("budget_items").select("estimated_amount, actual_amount, category").eq("budget_id", budget_id).execute()
        items = items_response.data if items_response.data else []
        
        total_estimated_expenses = sum(i["estimated_amount"] for i in items if i["category"] == "expense")
        total_estimated_revenue = sum(i["estimated_amount"] for i in items if i["category"] == "revenue")
        total_actual_expenses = sum(i.get("actual_amount", 0) or 0 for i in items if i["category"] == "expense")
        total_actual_revenue = sum(i.get("actual_amount", 0) or 0 for i in items if i["category"] == "revenue")
        
        supabase.table("budgets").update({
            "total_estimated_expenses": total_estimated_expenses,
            "total_estimated_revenue": total_estimated_revenue,
            "total_actual_expenses": total_actual_expenses,
            "total_actual_revenue": total_actual_revenue,
            "updated_at": datetime.now().isoformat()
        }).eq("id", budget_id).execute()
        
        # Get updated budget
        budget_response = supabase.table("budgets").select("*").eq("id", budget_id).execute()
        budget = budget_response.data[0]
        
        items_response = supabase.table("budget_items").select("*").eq("budget_id", budget_id).order("created_at").execute()
        budget["items"] = items_response.data if items_response.data else []
        
        return {
            "success": True,
            "result": budget
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting budget item: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete budget item: {str(e)}")


@router.post("/sessions/{session_id}/budget/generate-estimates")
async def generate_estimated_expenses(session_id: str, request: Request):
    """Generate estimated expenses based on business plan context"""
    from services.angel_service import generate_estimated_expenses_from_business_plan
    from db.supabase import get_session, fetch_chat_history
    
    user_id = request.state.user["id"]
    
    try:
        # Get session to verify ownership
        session_response = supabase.table("chat_sessions").select("*").eq("id", session_id).eq("user_id", user_id).execute()
        
        if not session_response.data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = session_response.data[0]
        
        # Get chat history
        history_response = supabase.table("chat_messages").select("*").eq("session_id", session_id).order("created_at").execute()
        history = [{"role": msg.get("role"), "content": msg.get("content", "")} for msg in (history_response.data or [])]
        
        # Generate estimated expenses
        estimated_expenses_text = await generate_estimated_expenses_from_business_plan(session, history)
        
        return {
            "success": True,
            "result": {
                "estimated_expenses": estimated_expenses_text,
                "business_context": {
                    "business_name": session.get("business_name") or session.get("business_idea_brief", ""),
                    "industry": session.get("industry", ""),
                    "location": session.get("location", ""),
                    "business_type": session.get("business_type", "")
                }
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating estimated expenses: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate estimated expenses: {str(e)}")


@router.get("/sessions/{session_id}/budget/summary")
async def get_budget_summary(session_id: str, request: Request):
    """Get budget summary statistics"""
    user_id = request.state.user["id"]
    
    try:
        # Get budget
        budget_response = supabase.table("budgets").select("*").eq("session_id", session_id).eq("user_id", user_id).execute()
        
        if not budget_response.data:
            return {
                "success": True,
                "result": {
                    "total_estimated": 0,
                    "total_actual": 0,
                    "estimated_expenses": 0,
                    "estimated_revenue": 0,
                    "actual_expenses": 0,
                    "actual_revenue": 0,
                    "variance": 0
                }
            }
        
        budget = budget_response.data[0]
        
        total_estimated = budget["total_estimated_expenses"] + budget["total_estimated_revenue"]
        total_actual = (budget.get("total_actual_expenses", 0) or 0) + (budget.get("total_actual_revenue", 0) or 0)
        variance = total_actual - total_estimated
        
        return {
            "success": True,
            "result": {
                "total_estimated": total_estimated,
                "total_actual": total_actual,
                "estimated_expenses": budget["total_estimated_expenses"],
                "estimated_revenue": budget["total_estimated_revenue"],
                "actual_expenses": budget.get("total_actual_expenses", 0) or 0,
                "actual_revenue": budget.get("total_actual_revenue", 0) or 0,
                "variance": variance
            }
        }
    except Exception as e:
        print(f"Error getting budget summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get budget summary: {str(e)}")

