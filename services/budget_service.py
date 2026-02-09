from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import HTTPException
from pydantic import BaseModel
from db.supabase import create_supabase_client
from services.session_service import get_session
from services.chat_service import fetch_chat_history
from services.angel_service import generate_estimated_expenses_from_business_plan, generate_initial_revenue_streams
from schemas.budget_schemas import RevenueStreamInitial
import re
import uuid

supabase = create_supabase_client()

# Pydantic models for budget items (copied from budget_router.py)
class BudgetItemCreate(BaseModel):
    id: Optional[str] = None # Added for non-destructive updates
    name: str
    category: str  # 'expense' or 'revenue'
    estimated_amount: float
    actual_amount: Optional[float] = None
    description: Optional[str] = None
    is_custom: Optional[bool] = True

class RevenueStreamSave(BaseModel):
    id: str
    name: str
    estimatedPrice: float
    estimatedVolume: int
    revenueProjection: float
    isSelected: bool
    isCustom: bool
    category: str = "revenue"

class BudgetItemFromRevenue(BaseModel):
    name: str
    category: str = "revenue"
    estimated_amount: float
    is_custom: Optional[bool] = False

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

class BudgetService:
    @staticmethod
    async def get_budget_data(user_id: str, session_id: str) -> Dict[str, Any]:
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
            
            budget = budget_response.data[0]
            
            # Get budget items
            items_response = supabase.table("budget_items").select("*").eq("budget_id", budget["id"]).order("created_at").execute()
            budget["items"] = items_response.data if items_response.data else []
            
            return budget
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error getting budget: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get budget: {str(e)}")

    @staticmethod
    async def create_or_update_budget(user_id: str, session_id: str, budget_data: BudgetCreate) -> Dict[str, Any]:
        try:
            # Verify session ownership
            session_response = supabase.table("chat_sessions").select("id, user_id").eq("id", session_id).eq("user_id", user_id).execute()
            
            if not session_response.data:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Check if budget exists
            existing_budget_response = supabase.table("budgets").select("id").eq("session_id", session_id).execute()
            
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
            
            if existing_budget_response.data:
                # Update existing budget
                budget_id = existing_budget_response.data[0]["id"]
                supabase.table("budgets").update(budget_payload).eq("id", budget_id).execute()
            else:
                # Create new budget
                budget_payload["created_at"] = datetime.now().isoformat()
                budget_response = supabase.table("budgets").insert(budget_payload).execute()
                budget_id = budget_response.data[0]["id"]

            # Handle budget items non-destructively
            existing_budget_items_response = supabase.table("budget_items").select("id, name, category, estimated_amount, actual_amount, description, is_custom").eq("budget_id", budget_id).execute()
            existing_budget_items = {item["id"]: item for item in existing_budget_items_response.data}

            incoming_item_ids = {item["id"] for item in budget_data.items if item.get("id")} # IDs of items sent from frontend

            items_to_insert = []
            items_to_update = []
            all_current_items_for_totals = [] # To store all items after CUD for total recalculation

            for item_data_from_frontend in budget_data.items:
                item_id = item_data_from_frontend.get("id")
                prepared_item_data = {
                    "budget_id": budget_id,
                    "name": item_data_from_frontend.get("name", ""),
                    "category": item_data_from_frontend.get("category", "expense"),
                    "estimated_amount": item_data_from_frontend.get("estimated_amount", 0),
                    "actual_amount": item_data_from_frontend.get("actual_amount"),
                    "description": item_data_from_frontend.get("description"),
                    "is_custom": item_data_from_frontend.get("is_custom", True),
                    "updated_at": datetime.now().isoformat()
                }

                if item_id and item_id in existing_budget_items:
                    # Item exists, prepare for update
                    items_to_update.append({"id": item_id, **prepared_item_data})
                    # Add to all_current_items_for_totals with its ID
                    all_current_items_for_totals.append({"id": item_id, **prepared_item_data})
                    del existing_budget_items[item_id] # Mark as processed
                else:
                    # New item, prepare for insert
                    items_to_insert.append({
                        "created_at": datetime.now().isoformat(),
                        **prepared_item_data
                    })
                    # New items will get an ID after insert, for now include them for total recalculation
                    all_current_items_for_totals.append(prepared_item_data)
            
            # Items remaining in existing_budget_items were not in the incoming items, so they should be deleted
            items_to_delete_ids = list(existing_budget_items.keys())

            # Perform database operations
            if items_to_insert:
                inserted_items_response = supabase.table("budget_items").insert(items_to_insert).execute()
                # Add newly inserted items (with their generated IDs) to all_current_items_for_totals
                if inserted_items_response.data:
                    for item in inserted_items_response.data:
                        # Find the corresponding item in all_current_items_for_totals and update its ID
                        for i, current_item in enumerate(all_current_items_for_totals):
                            # This assumes that the order of insertion response matches the request if no ID was provided.
                            # A more robust solution might involve matching by name/other fields if IDs aren't returned in order.
                            if not current_item.get("id"):
                                all_current_items_for_totals[i]["id"] = item["id"]
                                break

            for update_item in items_to_update:
                item_id = update_item.pop("id")
                supabase.table("budget_items").update(update_item).eq("id", item_id).execute()

            if items_to_delete_ids:
                supabase.table("budget_items").delete().in_("id", items_to_delete_ids).execute()
            
            # Recalculate totals based on all_current_items_for_totals
            total_estimated_expenses = sum(i["estimated_amount"] for i in all_current_items_for_totals if i["category"] == "expense")
            total_estimated_revenue = sum(i["estimated_amount"] for i in all_current_items_for_totals if i["category"] == "revenue")
            total_actual_expenses = sum(i.get("actual_amount", 0) or 0 for i in all_current_items_for_totals if i["category"] == "expense")
            total_actual_revenue = sum(i.get("actual_amount", 0) or 0 for i in all_current_items_for_totals if i["category"] == "revenue")

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
            
            return budget
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error saving budget: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save budget: {str(e)}")

    @staticmethod
    async def add_budget_item(user_id: str, session_id: str, item: BudgetItemCreate) -> Dict[str, Any]:
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
            
            return budget
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error adding budget item: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to add budget item: {str(e)}")

    @staticmethod
    async def update_budget_item(user_id: str, session_id: str, item_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
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
            
            return budget
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error updating budget item: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update budget item: {str(e)}")

    @staticmethod
    async def delete_budget_item(user_id: str, session_id: str, item_id: str) -> Dict[str, Any]:
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
            
            return budget
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error deleting budget item: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete budget item: {str(e)}")

    @staticmethod
    async def get_budget_summary(user_id: str, session_id: str) -> Dict[str, Any]:
        try:
            # Get budget
            budget_response = supabase.table("budgets").select("*").eq("session_id", session_id).eq("user_id", user_id).execute()
            
            if not budget_response.data:
                return {
                    "total_estimated": 0,
                    "total_actual": 0,
                    "estimated_expenses": 0,
                    "estimated_revenue": 0,
                    "actual_expenses": 0,
                    "actual_revenue": 0,
                    "variance": 0
                }
            
            budget = budget_response.data[0]
            
            total_estimated = budget["total_estimated_expenses"] + budget["total_estimated_revenue"]
            total_actual = (budget.get("total_actual_expenses", 0) or 0) + (budget.get("total_actual_revenue", 0) or 0)
            variance = total_actual - total_estimated
            
            return {
                "total_estimated": total_estimated,
                "total_actual": total_actual,
                "estimated_expenses": budget["total_estimated_expenses"],
                "estimated_revenue": budget["total_estimated_revenue"],
                "actual_expenses": budget.get("actual_expenses", 0) or 0,
                "actual_revenue": budget.get("actual_revenue", 0) or 0,
                "variance": variance
            }
        except Exception as e:
            print(f"Error getting budget summary: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get budget summary: {str(e)}")

    @staticmethod
    def parse_estimated_expenses(estimated_expenses_text: str) -> List[BudgetItemCreate]:
        items: List[BudgetItemCreate] = []
        lines = estimated_expenses_text.split('\n')
        expense_category_map = {
            'startup costs': 'expense',  # Frontend used 'startup_cost', but backend BudgetItemCreate category is 'expense'
            'monthly operating expenses': 'expense', # and is classified as 'operating_expense' in the frontend.
            'monthly payroll': 'expense', # and is classified as 'payroll' in the frontend.
            'monthly cogs': 'expense' # and is classified as 'cogs' in the frontend.
        }

        current_category_key: Optional[str] = None
        for line in lines:
            trimmed_line = line.strip()
            if not trimmed_line:
                continue

            # Check for category headers
            matched_category = None
            for key in expense_category_map.keys():
                if trimmed_line.lower().startswith(f'**{key}**'):
                    matched_category = key
                    break
            
            if matched_category:
                current_category_key = matched_category
                continue

            # Attempt to parse line as a budget item
            # Example format: "- Item Name: $Amount (Description)" or "- Item Name: $Amount"
            match = re.match(r'^-?\s*(.+?):\s*\$([\d,.]+)(?:\s*\((.+?)\))?$', trimmed_line)
            if match and current_category_key:
                name = match.group(1).strip()
                try:
                    amount = float(match.group(2).replace(',', ''))
                except ValueError:
                    amount = 0.0
                description = match.group(3).strip() if match.group(3) else None
                
                # Assign actual category based on parsed header, but `BudgetItemCreate` only uses 'expense' or 'revenue'
                # The more granular classification (startup_cost, operating_expense, etc.) happens on the frontend
                # based on derived IDs or item names. Here, we just set 'expense'.
                category = expense_category_map[current_category_key]

                items.append(
                    BudgetItemCreate(
                        id=str(uuid.uuid4()), # Generate a UUID for the item ID
                        name=name,
                        category=category,
                        estimated_amount=amount,
                        actual_amount=None,
                        description=description,
                        is_custom=False, # AI generated
                    )
                )
        return items

    @staticmethod
    async def generate_initial_expenses(user_id: str, session_id: str) -> List[BudgetItemCreate]:
        try:
            # Get session to verify ownership
            session_response = supabase.table("chat_sessions").select("*").eq("id", session_id).eq("user_id", user_id).execute()
            
            if not session_response.data:
                raise HTTPException(status_code=404, detail="Session not found")
            
            session = session_response.data[0]
            
            # Get chat history
            history_response = supabase.table("chat_messages").select("*").eq("session_id", session_id).order("created_at").execute()
            history = [{"role": msg.get("role"), "content": msg.get("content", "")} for msg in (history_response.data or [])]
            
            # Generate estimated expenses raw text
            estimated_expenses_text = await generate_estimated_expenses_from_business_plan(session, history)
            
            # Parse the raw text into structured BudgetItemCreate objects
            parsed_items = BudgetService.parse_estimated_expenses(estimated_expenses_text)
            
            return parsed_items
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error generating estimated expenses: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate estimated expenses: {str(e)}")

    @staticmethod
    async def generate_initial_revenue_streams(user_id: str, session_id: str) -> List[RevenueStreamInitial]:
        try:
            # Get session to extract business_type
            session_data = await get_session(session_id, user_id)
            if not session_data:
                raise HTTPException(status_code=404, detail="Session not found")
            
            business_type = (session_data.get("business_context") or {}).get("business_type") or session_data.get("business_type", "Startup")

            # Generate revenue streams based on business_type
            initial_streams = await generate_initial_revenue_streams(business_type)
            
            return initial_streams
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error generating revenue streams: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate revenue streams: {str(e)}")

    @staticmethod
    async def save_revenue_streams(user_id: str, session_id: str, revenue_streams: List[RevenueStreamSave]):
        try:
            # 1. Verify session ownership and get budget_id
            budget_response = supabase.table("budgets").select("id").eq("session_id", session_id).eq("user_id", user_id).execute()
            if not budget_response.data:
                raise HTTPException(status_code=404, detail="Budget not found for this session.")
            budget_id = budget_response.data[0]["id"]

            # Get existing revenue items
            existing_revenue_items_response = supabase.table("budget_items").select("id, name, estimated_amount").eq("budget_id", budget_id).eq("category", "revenue").execute()
            existing_revenue_items = {item["id"]: item for item in existing_revenue_items_response.data}

            incoming_stream_ids = {stream.id for stream in revenue_streams if stream.isSelected}

            items_to_insert = []
            items_to_update = []
            
            total_estimated_revenue = 0.0

            for stream in revenue_streams:
                if stream.isSelected:
                    # Prepare item data
                    item_data = {
                        "name": stream.name,
                        "category": "revenue",
                        "estimated_amount": stream.revenueProjection,
                        "actual_amount": None, # No actuals for estimated streams yet
                        "description": "Generated revenue stream",
                        "is_custom": stream.isCustom,
                        "updated_at": datetime.now().isoformat()
                    }

                    if stream.id and stream.id in existing_revenue_items:
                        # Item exists, prepare for update
                        items_to_update.append({"id": stream.id, **item_data})
                        del existing_revenue_items[stream.id] # Mark as processed
                    else:
                        # New item, prepare for insert
                        items_to_insert.append({
                            "budget_id": budget_id,
                            "created_at": datetime.now().isoformat(),
                            **item_data
                        })
                    total_estimated_revenue += stream.revenueProjection
            
            # Items remaining in existing_revenue_items were not in the incoming selected streams, so they should be deleted
            items_to_delete_ids = list(existing_revenue_items.keys())

            # Perform database operations
            if items_to_insert:
                supabase.table("budget_items").insert(items_to_insert).execute()
            
            for update_item in items_to_update:
                item_id = update_item.pop("id")
                supabase.table("budget_items").update(update_item).eq("id", item_id).execute()

            if items_to_delete_ids:
                supabase.table("budget_items").delete().in_("id", items_to_delete_ids).execute()
            
            # 5. Update the total_estimated_revenue in the main budget entry
            supabase.table("budgets").update({
                "total_estimated_revenue": total_estimated_revenue,
                "updated_at": datetime.now().isoformat()
            }).eq("id", budget_id).execute()

            return {
                "success": True,
                "message": "Revenue streams and budget updated successfully."
            }

        except HTTPException:
            raise
        except Exception as e:
            print(f"Error saving revenue streams: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save revenue streams: {str(e)}")