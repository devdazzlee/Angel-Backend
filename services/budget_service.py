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


# ── Pydantic Models ──────────────────────────────────────────────────────────

class BudgetItemCreate(BaseModel):
    id: Optional[str] = None
    name: str
    category: str  # 'expense' or 'revenue'
    subcategory: Optional[str] = None  # 'startup_cost', 'operating_expense', 'payroll', 'cogs', 'revenue'
    estimated_amount: float = 0
    actual_amount: Optional[float] = None
    estimated_price: Optional[float] = None  # revenue items: unit price
    estimated_volume: Optional[int] = None    # revenue items: unit count
    description: Optional[str] = None
    is_custom: Optional[bool] = True
    is_selected: Optional[bool] = True


class RevenueStreamSave(BaseModel):
    id: Optional[str] = None
    name: str
    estimatedPrice: float
    estimatedVolume: int
    revenueProjection: float
    isSelected: bool
    isCustom: bool
    category: str = "revenue"
    description: Optional[str] = None


class BudgetCreate(BaseModel):
    session_id: str
    initial_investment: float
    total_estimated_expenses: float = 0
    total_estimated_revenue: float = 0
    items: List[Dict[str, Any]] = []


class BudgetUpdate(BaseModel):
    initial_investment: Optional[float] = None
    total_estimated_expenses: Optional[float] = None
    total_estimated_revenue: Optional[float] = None
    total_actual_expenses: Optional[float] = None
    total_actual_revenue: Optional[float] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _recalculate_and_update_totals(budget_id: str):
    """Recalculate totals from budget_items and update the budgets row."""
    items_response = supabase.table("budget_items").select(
        "estimated_amount, actual_amount, category"
    ).eq("budget_id", budget_id).execute()
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


def _get_full_budget(budget_id: str) -> Dict[str, Any]:
    """Return a full budget dict with its items."""
    budget_response = supabase.table("budgets").select("*").eq("id", budget_id).execute()
    budget = budget_response.data[0]
    items_response = supabase.table("budget_items").select("*").eq("budget_id", budget_id).order("created_at").execute()
    budget["items"] = items_response.data if items_response.data else []
    return budget


def _ensure_budget_exists(user_id: str, session_id: str, initial_investment: float = 0) -> str:
    """
    Return the budget_id for a session, creating the budget row if needed.
    
    Strategy:
    1. Look for ANY budget for this session_id (regardless of user_id)
    2. If found → adopt it (set user_id) and return its id
    3. If not found → create a new one
    
    This guarantees exactly ONE budget per session. The UNIQUE constraint
    on session_id in the DB prevents duplicates.
    """
    # Step 1: Find any budget for this session (don't filter by user_id to avoid duplicates)
    budget_response = supabase.table("budgets").select("id, user_id").eq(
        "session_id", session_id
    ).execute()

    if budget_response.data:
        budget_row = budget_response.data[0]
        budget_id = budget_row["id"]

        # If user_id is missing or different, adopt it
        if budget_row.get("user_id") != user_id:
            print(f"⚠️ _ensure_budget_exists: Adopting budget_id={budget_id} (old user_id={budget_row.get('user_id')}) for user={user_id}")
            supabase.table("budgets").update({
                "user_id": user_id,
                "updated_at": datetime.now().isoformat()
            }).eq("id", budget_id).execute()
        else:
            print(f"🔍 _ensure_budget_exists: FOUND budget_id={budget_id} for session={session_id}")

        return budget_id

    # Step 2: No budget exists at all — create one
    print(f"🆕 _ensure_budget_exists: Creating NEW budget for session={session_id}, user={user_id}")
    new_budget = supabase.table("budgets").insert({
        "session_id": session_id,
        "user_id": user_id,
        "initial_investment": initial_investment,
        "total_estimated_expenses": 0,
        "total_estimated_revenue": 0,
        "total_actual_expenses": 0,
        "total_actual_revenue": 0,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }).execute()
    budget_id = new_budget.data[0]["id"]
    print(f"   → Created budget_id={budget_id}")
    return budget_id


# ── Service ──────────────────────────────────────────────────────────────────

class BudgetService:

    # ── READ ────────────────────────────────────────────────────────────────

    @staticmethod
    async def get_budget_data(user_id: str, session_id: str) -> Dict[str, Any]:
        """
        Get the budget for a session.  Uses _ensure_budget_exists so the
        exact same budget_id is used everywhere (get, add, update, delete).
        This prevents the "duplicate budget" bug where items are saved to one
        budget row but a different (older) row is returned on page refresh.
        """
        try:
            session_response = supabase.table("chat_sessions").select("id, user_id").eq(
                "id", session_id
            ).eq("user_id", user_id).execute()
            if not session_response.data:
                raise HTTPException(status_code=404, detail="Session not found")

            # Always use _ensure_budget_exists — same function used by add/update/delete.
            # This guarantees we read the SAME budget that items are written to.
            budget_id = _ensure_budget_exists(user_id, session_id)
            result = _get_full_budget(budget_id)
            print(f"📊 get_budget_data: session={session_id}, budget_id={budget_id}, items_count={len(result.get('items', []))}")
            return result
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error getting budget: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get budget: {str(e)}")

    # ── CREATE / FULL SAVE ──────────────────────────────────────────────────

    @staticmethod
    async def create_or_update_budget(user_id: str, session_id: str, budget_data: BudgetCreate) -> Dict[str, Any]:
        try:
            session_response = supabase.table("chat_sessions").select("id, user_id").eq(
                "id", session_id
            ).eq("user_id", user_id).execute()
            if not session_response.data:
                raise HTTPException(status_code=404, detail="Session not found")

            budget_id = _ensure_budget_exists(user_id, session_id, budget_data.initial_investment)

            # Update the budget header
            supabase.table("budgets").update({
                "initial_investment": budget_data.initial_investment,
                "updated_at": datetime.now().isoformat()
            }).eq("id", budget_id).execute()

            # NON-DESTRUCTIVE item sync — insert new items, update known items.
            # NEVER delete items here. Deletion only happens via the explicit
            # DELETE /budget/items/{item_id} endpoint. This prevents race conditions
            # where a stale frontend state could accidentally remove recently-added items.
            existing_items_response = supabase.table("budget_items").select("*").eq("budget_id", budget_id).execute()
            existing_items = {item["id"]: item for item in existing_items_response.data}

            items_to_insert = []
            items_to_update = []

            for item_data in budget_data.items:
                item_id = item_data.get("id")
                prepared = {
                    "budget_id": budget_id,
                    "name": item_data.get("name", ""),
                    "category": item_data.get("category", "expense"),
                    "subcategory": item_data.get("subcategory"),
                    "estimated_amount": item_data.get("estimated_amount", 0),
                    "actual_amount": item_data.get("actual_amount"),
                    "estimated_price": item_data.get("estimated_price"),
                    "estimated_volume": item_data.get("estimated_volume"),
                    "description": item_data.get("description"),
                    "is_custom": item_data.get("is_custom", True),
                    "is_selected": item_data.get("is_selected", True),
                    "updated_at": datetime.now().isoformat()
                }

                if item_id and item_id in existing_items:
                    items_to_update.append({"id": item_id, **prepared})
                else:
                    items_to_insert.append({
                        "created_at": datetime.now().isoformat(),
                        **prepared
                    })

            if items_to_insert:
                supabase.table("budget_items").insert(items_to_insert).execute()
            for upd in items_to_update:
                uid = upd.pop("id")
                supabase.table("budget_items").update(upd).eq("id", uid).execute()

            _recalculate_and_update_totals(budget_id)
            return _get_full_budget(budget_id)
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error saving budget: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save budget: {str(e)}")

    # ── ADD ITEM ────────────────────────────────────────────────────────────

    @staticmethod
    async def add_budget_item(user_id: str, session_id: str, item: BudgetItemCreate) -> Dict[str, Any]:
        try:
            budget_id = _ensure_budget_exists(user_id, session_id)

            item_data = {
                "budget_id": budget_id,
                "name": item.name,
                "category": item.category,
                "subcategory": item.subcategory,
                "estimated_amount": item.estimated_amount,
                "actual_amount": item.actual_amount,
                "estimated_price": item.estimated_price,
                "estimated_volume": item.estimated_volume,
                "description": item.description,
                "is_custom": item.is_custom,
                "is_selected": item.is_selected if item.is_selected is not None else True,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

            insert_response = supabase.table("budget_items").insert(item_data).execute()
            print(f"✅ add_budget_item: budget_id={budget_id}, item_name={item.name}, inserted_id={insert_response.data[0]['id'] if insert_response.data else 'NONE'}")
            _recalculate_and_update_totals(budget_id)
            full = _get_full_budget(budget_id)
            print(f"   → Returning budget with {len(full.get('items', []))} items")
            return full
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error adding budget item: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to add budget item: {str(e)}")

    # ── UPDATE ITEM ─────────────────────────────────────────────────────────

    @staticmethod
    async def update_budget_item(user_id: str, session_id: str, item_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        try:
            budget_id = _ensure_budget_exists(user_id, session_id)

            allowed_fields = {
                "name", "category", "subcategory",
                "estimated_amount", "actual_amount",
                "estimated_price", "estimated_volume",
                "description", "is_custom", "is_selected"
            }
            safe_updates = {k: v for k, v in updates.items() if k in allowed_fields}
            safe_updates["updated_at"] = datetime.now().isoformat()

            supabase.table("budget_items").update(safe_updates).eq(
                "id", item_id
            ).eq("budget_id", budget_id).execute()

            _recalculate_and_update_totals(budget_id)
            return _get_full_budget(budget_id)
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error updating budget item: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update budget item: {str(e)}")

    # ── DELETE ITEM ─────────────────────────────────────────────────────────

    @staticmethod
    async def delete_budget_item(user_id: str, session_id: str, item_id: str) -> Dict[str, Any]:
        try:
            budget_id = _ensure_budget_exists(user_id, session_id)

            supabase.table("budget_items").delete().eq(
                "id", item_id
            ).eq("budget_id", budget_id).execute()

            _recalculate_and_update_totals(budget_id)
            return _get_full_budget(budget_id)
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error deleting budget item: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete budget item: {str(e)}")

    # ── UPDATE BUDGET HEADER (initial_investment etc.) ──────────────────────

    @staticmethod
    async def update_budget_header(user_id: str, session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        try:
            budget_id = _ensure_budget_exists(user_id, session_id)

            allowed = {"initial_investment"}
            safe = {k: v for k, v in updates.items() if k in allowed}
            safe["updated_at"] = datetime.now().isoformat()

            supabase.table("budgets").update(safe).eq("id", budget_id).execute()
            return _get_full_budget(budget_id)
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error updating budget header: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update budget: {str(e)}")

    # ── SAVE REVENUE STREAMS ───────────────────────────────────────────────

    @staticmethod
    async def save_revenue_streams(user_id: str, session_id: str, revenue_streams: List[RevenueStreamSave]):
        try:
            budget_id = _ensure_budget_exists(user_id, session_id)

            # Get existing revenue items
            existing_response = supabase.table("budget_items").select("id, name").eq(
                "budget_id", budget_id
            ).eq("category", "revenue").execute()
            existing = {item["id"]: item for item in existing_response.data}

            items_to_insert = []
            items_to_update = []
            processed_ids = set()

            for stream in revenue_streams:
                item_payload = {
                    "name": stream.name,
                    "category": "revenue",
                    "subcategory": "revenue",
                    "estimated_amount": stream.revenueProjection,
                    "estimated_price": stream.estimatedPrice,
                    "estimated_volume": stream.estimatedVolume,
                    "actual_amount": None,
                    "description": stream.description or "Revenue stream",
                    "is_custom": stream.isCustom,
                    "is_selected": stream.isSelected,
                    "updated_at": datetime.now().isoformat()
                }

                if stream.id and stream.id in existing:
                    items_to_update.append({"id": stream.id, **item_payload})
                    processed_ids.add(stream.id)
                else:
                    items_to_insert.append({
                        "budget_id": budget_id,
                        "created_at": datetime.now().isoformat(),
                        **item_payload
                    })

            # Delete revenue items no longer present
            ids_to_delete = [k for k in existing if k not in processed_ids]

            if items_to_insert:
                supabase.table("budget_items").insert(items_to_insert).execute()
            for upd in items_to_update:
                uid = upd.pop("id")
                supabase.table("budget_items").update(upd).eq("id", uid).execute()
            if ids_to_delete:
                supabase.table("budget_items").delete().in_("id", ids_to_delete).execute()

            _recalculate_and_update_totals(budget_id)

            # Return saved items so frontend can sync IDs
            saved_items = supabase.table("budget_items").select("*").eq(
                "budget_id", budget_id
            ).eq("category", "revenue").order("created_at").execute()

            return {
                "success": True, 
                "message": "Revenue streams saved successfully.",
                "result": saved_items.data if saved_items.data else []
            }

        except HTTPException:
            raise
        except Exception as e:
            print(f"Error saving revenue streams: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save revenue streams: {str(e)}")

    # ── GET REVENUE STREAMS (from DB) ──────────────────────────────────────

    @staticmethod
    async def get_revenue_streams(user_id: str, session_id: str) -> List[Dict[str, Any]]:
        try:
            # Use _ensure_budget_exists for consistency — same budget_id everywhere
            budget_id = _ensure_budget_exists(user_id, session_id)
            items_response = supabase.table("budget_items").select("*").eq(
                "budget_id", budget_id
            ).eq("category", "revenue").order("created_at").execute()

            return items_response.data if items_response.data else []
        except Exception as e:
            print(f"Error getting revenue streams: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get revenue streams: {str(e)}")

    # ── BUDGET SUMMARY ─────────────────────────────────────────────────────

    @staticmethod
    async def get_budget_summary(user_id: str, session_id: str) -> Dict[str, Any]:
        try:
            # Use _ensure_budget_exists for consistency — same budget_id everywhere
            budget_id = _ensure_budget_exists(user_id, session_id)
            budget_response = supabase.table("budgets").select("*").eq("id", budget_id).execute()

            if not budget_response.data:
                return {
                    "total_estimated": 0, "total_actual": 0,
                    "estimated_expenses": 0, "estimated_revenue": 0,
                    "actual_expenses": 0, "actual_revenue": 0,
                    "variance": 0
                }

            b = budget_response.data[0]
            total_estimated = b["total_estimated_expenses"] + b["total_estimated_revenue"]
            total_actual = (b.get("total_actual_expenses", 0) or 0) + (b.get("total_actual_revenue", 0) or 0)

            return {
                "total_estimated": total_estimated,
                "total_actual": total_actual,
                "estimated_expenses": b["total_estimated_expenses"],
                "estimated_revenue": b["total_estimated_revenue"],
                "actual_expenses": b.get("total_actual_expenses", 0) or 0,
                "actual_revenue": b.get("total_actual_revenue", 0) or 0,
                "variance": total_actual - total_estimated
            }
        except Exception as e:
            print(f"Error getting budget summary: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get budget summary: {str(e)}")

    # ── AI GENERATION ──────────────────────────────────────────────────────

    @staticmethod
    def parse_estimated_expenses(estimated_expenses_text: str) -> List[BudgetItemCreate]:
        items: List[BudgetItemCreate] = []
        lines = estimated_expenses_text.split('\n')

        # Map header keywords to (category, subcategory)
        category_map = {
            'startup costs': ('expense', 'startup_cost'),
            'monthly operating expenses': ('expense', 'operating_expense'),
            'monthly payroll': ('expense', 'payroll'),
            'monthly cogs': ('expense', 'cogs'),
        }

        current_cat = 'expense'
        current_sub: Optional[str] = None

        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue

            matched = None
            for key, (cat, sub) in category_map.items():
                if trimmed.lower().startswith(f'**{key}**'):
                    matched = key
                    current_cat = cat
                    current_sub = sub
                    break
            if matched:
                continue

            match = re.match(r'^-?\s*(.+?):\s*\$([\d,.]+)(?:\s*\((.+?)\))?$', trimmed)
            if match and current_sub:
                name = match.group(1).strip()
                try:
                    amount = float(match.group(2).replace(',', ''))
                except ValueError:
                    amount = 0.0
                description = match.group(3).strip() if match.group(3) else None

                items.append(BudgetItemCreate(
                    id=str(uuid.uuid4()),
                    name=name,
                    category=current_cat,
                    subcategory=current_sub,
                    estimated_amount=amount,
                    actual_amount=None,
                    description=description,
                    is_custom=False,
                ))
        return items

    @staticmethod
    async def generate_initial_expenses(user_id: str, session_id: str) -> List[BudgetItemCreate]:
        try:
            session_response = supabase.table("chat_sessions").select("*").eq(
                "id", session_id
            ).eq("user_id", user_id).execute()
            if not session_response.data:
                raise HTTPException(status_code=404, detail="Session not found")

            session = session_response.data[0]
            history_response = supabase.table("chat_messages").select("*").eq(
                "session_id", session_id
            ).order("created_at").execute()
            history = [{"role": m.get("role"), "content": m.get("content", "")} for m in (history_response.data or [])]

            estimated_text = await generate_estimated_expenses_from_business_plan(session, history)
            return BudgetService.parse_estimated_expenses(estimated_text)
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error generating estimated expenses: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate estimated expenses: {str(e)}")

    @staticmethod
    async def generate_initial_revenue_streams(user_id: str, session_id: str) -> List[RevenueStreamInitial]:
        try:
            session_data = await get_session(session_id, user_id)
            if not session_data:
                raise HTTPException(status_code=404, detail="Session not found")

            business_type = (session_data.get("business_context") or {}).get("business_type") or session_data.get("business_type", "Startup")
            return await generate_initial_revenue_streams(business_type)
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error generating revenue streams: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate revenue streams: {str(e)}")
