from openai import AsyncOpenAI
import os
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from utils.constant import ANGEL_SYSTEM_PROMPT
from supabase import create_client, Client

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Supabase client for fetching business plan
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# Helper function to fetch business plan context
async def fetch_business_plan_context(session_id: str) -> Dict:
    """Fetch business plan data for context validation"""
    try:
        if not supabase:
            return {}
            
        # Fetch business plan from database
        response = supabase.from_("business_plans").select("*").eq("session_id", session_id).order("created_at", desc=True).limit(1).execute()
        
        if response.data and len(response.data) > 0:
            plan = response.data[0]
            return {
                "executive_summary": plan.get("executive_summary", ""),
                "market_analysis": plan.get("market_analysis", ""),
                "target_market": plan.get("target_market", ""),
                "competitive_analysis": plan.get("competitive_analysis", ""),
                "marketing_strategy": plan.get("marketing_strategy", ""),
                "financial_projections": plan.get("financial_projections", ""),
                "full_plan": plan.get("full_plan", "")
            }
    except Exception as e:
        print(f"Error fetching business plan context: {e}")
    
    return {}

# Context validation loop
async def validate_response_context(response: str, task: Dict, business_context: Dict, business_plan: Dict) -> str:
    """Validate that AI response is contextually accurate and specific to the user's business"""
    
    validation_prompt = f"""
    Review the following AI response and verify it is SPECIFIC and CONTEXTUALLY ACCURATE for this business:

    BUSINESS CONTEXT:
    - Business Name: {business_context.get('business_name', 'N/A')}
    - Industry: {business_context.get('industry', 'N/A')}
    - Location: {business_context.get('location', 'N/A')}
    - Business Type: {business_context.get('business_type', 'N/A')}

    CURRENT TASK:
    - Task: {task.get('title', 'N/A')}
    - Phase: {task.get('phase_name', 'N/A')}
    - Purpose: {task.get('purpose', 'N/A')}

    BUSINESS PLAN SUMMARY:
    {business_plan.get('executive_summary', 'No business plan available')[:500]}

    AI RESPONSE TO VALIDATE:
    {response}

    VALIDATION REQUIREMENTS:
    1. Check if response mentions the SPECIFIC business name, industry, and location
    2. Verify advice is tailored to their SPECIFIC industry and business type
    3. Ensure recommendations are relevant to their LOCATION (local regulations, resources)
    4. Confirm response aligns with their business plan goals
    5. Check that it addresses the SPECIFIC task they're working on

    If the response is TOO GENERIC or lacks business-specific context, rewrite it to be MORE SPECIFIC and PERSONALIZED.
    
    Return ONLY the validated/improved response (no explanations):
    """
    
    try:
        validation_response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a context validation expert. Ensure all responses are specific and personalized to the user's business."},
                {"role": "user", "content": validation_prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        
        validated_response = validation_response.choices[0].message.content
        print(f"✅ Response validated and enhanced with business context")
        return validated_response
        
    except Exception as e:
        print(f"Error in context validation: {e}")
        return response  # Return original if validation fails

# Implementation task structure
IMPLEMENTATION_TASKS = {
    "LEGAL_FORMATION": {
        "phase": "Legal Formation & Compliance",
        "tasks": [
            {
                "id": "LEGAL_01",
                "title": "Choose Business Structure",
                "description": "Decide on the appropriate legal structure for your business (LLC, Corporation, Partnership, etc.)",
                "purpose": "Establish the legal foundation of your business with proper protections and tax benefits",
                "options": ["LLC", "Corporation (C-Corp)", "S-Corporation", "Partnership", "Sole Proprietorship"],
                "angel_actions": [
                    "Draft business structure comparison document",
                    "Research state-specific requirements",
                    "Generate legal structure decision matrix",
                    "Create registration checklist"
                ],
                "estimated_time": "1-2 days",
                "priority": "High"
            },
            {
                "id": "LEGAL_02", 
                "title": "Register Business Name",
                "description": "Register your business name with the appropriate state and federal agencies",
                "purpose": "Secure your business name and establish legal identity",
                "options": ["State Registration", "Federal Trademark", "DBA Registration", "Domain Registration"],
                "angel_actions": [
                    "Check name availability across platforms",
                    "Draft registration applications",
                    "Generate domain name suggestions",
                    "Create trademark research report"
                ],
                "estimated_time": "2-3 days",
                "priority": "High"
            },
            {
                "id": "LEGAL_03",
                "title": "Obtain Required Licenses",
                "description": "Research and obtain all necessary business licenses and permits",
                "purpose": "Ensure legal compliance and authorization to operate",
                "options": ["Business License", "Professional License", "Industry-Specific Permit", "Sales Tax Permit"],
                "angel_actions": [
                    "Research licensing requirements by location",
                    "Generate license application checklist",
                    "Draft license applications",
                    "Create compliance calendar"
                ],
                "estimated_time": "1-2 weeks",
                "priority": "High"
            }
        ]
    },
    "FINANCIAL_SETUP": {
        "phase": "Financial Planning & Setup",
        "tasks": [
            {
                "id": "FINANCIAL_01",
                "title": "Set Up Business Banking",
                "description": "Open business bank accounts and establish financial infrastructure",
                "purpose": "Separate business finances and establish professional banking relationships",
                "options": ["Business Checking", "Business Savings", "Business Credit Card", "Merchant Account"],
                "angel_actions": [
                    "Research bank options and requirements",
                    "Draft bank application documents",
                    "Generate banking setup checklist",
                    "Create financial tracking templates"
                ],
                "estimated_time": "3-5 days",
                "priority": "High"
            },
            {
                "id": "FINANCIAL_02",
                "title": "Implement Accounting System",
                "description": "Set up accounting software and financial tracking systems",
                "purpose": "Maintain accurate financial records and enable informed decision-making",
                "options": ["QuickBooks", "Xero", "FreshBooks", "Wave Accounting"],
                "angel_actions": [
                    "Compare accounting software options",
                    "Set up chart of accounts",
                    "Create financial reporting templates",
                    "Generate accounting procedures manual"
                ],
                "estimated_time": "1 week",
                "priority": "High"
            }
        ]
    },
    "PRODUCT_OPERATIONS": {
        "phase": "Product & Operations Development",
        "tasks": [
            {
                "id": "OPS_01",
                "title": "Establish Supply Chain",
                "description": "Identify and establish relationships with suppliers and vendors",
                "purpose": "Secure reliable sources for products, materials, or services",
                "options": ["Local Suppliers", "National Distributors", "International Suppliers", "Dropshipping Partners"],
                "angel_actions": [
                    "Research supplier options",
                    "Draft supplier evaluation criteria",
                    "Generate supplier agreement templates",
                    "Create supply chain risk assessment"
                ],
                "estimated_time": "2-3 weeks",
                "priority": "Medium"
            }
        ]
    },
    "MARKETING_SALES": {
        "phase": "Marketing & Sales Strategy",
        "tasks": [
            {
                "id": "MARKETING_01",
                "title": "Develop Brand Identity",
                "description": "Create comprehensive brand identity including logo, colors, and messaging",
                "purpose": "Establish consistent brand presence and professional image",
                "options": ["Logo Design", "Brand Guidelines", "Website Design", "Marketing Materials"],
                "angel_actions": [
                    "Generate brand identity brief",
                    "Research design trends",
                    "Draft brand guidelines document",
                    "Create marketing material templates"
                ],
                "estimated_time": "1-2 weeks",
                "priority": "Medium"
            }
        ]
    },
    "LAUNCH_SCALING": {
        "phase": "Full Launch & Scaling",
        "tasks": [
            {
                "id": "LAUNCH_01",
                "title": "Execute Go-to-Market Strategy",
                "description": "Launch marketing campaigns and begin customer acquisition",
                "purpose": "Generate initial revenue and establish market presence",
                "options": ["Digital Marketing", "Content Marketing", "Partnership Marketing", "Direct Sales"],
                "angel_actions": [
                    "Draft marketing campaign plans",
                    "Generate content calendar",
                    "Create partnership outreach templates",
                    "Develop sales process documentation"
                ],
                "estimated_time": "2-4 weeks",
                "priority": "High"
            }
        ]
    }
}

async def get_implementation_task(task_id: str, session_data: Dict) -> Optional[Dict]:
    """Get a specific implementation task with personalized details"""
    for phase_key, phase_data in IMPLEMENTATION_TASKS.items():
        for task in phase_data["tasks"]:
            if task["id"] == task_id:
                # Personalize task based on session data
                personalized_task = task.copy()
                personalized_task["phase_name"] = phase_data["phase"]
                personalized_task["business_context"] = {
                    "business_name": session_data.get("business_name", "Your Business"),
                    "industry": session_data.get("industry", "general business"),
                    "location": session_data.get("location", "United States"),
                    "business_type": session_data.get("business_type", "startup")
                }
                return personalized_task
    return None

async def get_next_implementation_task(session_data: Dict, completed_tasks: List[str]) -> Optional[Dict]:
    """Get the next implementation task based on priority and completion status"""
    all_tasks = []
    for phase_key, phase_data in IMPLEMENTATION_TASKS.items():
        for task in phase_data["tasks"]:
            if task["id"] not in completed_tasks:
                all_tasks.append(task)
    
    # Sort by priority (High first) and then by phase order
    priority_order = {"High": 1, "Medium": 2, "Low": 3}
    all_tasks.sort(key=lambda x: (priority_order.get(x["priority"], 3), x["id"]))
    
    if all_tasks:
        return await get_implementation_task(all_tasks[0]["id"], session_data)
    return None

async def generate_task_guidance(task: Dict, session_data: Dict, session_id: str = None) -> str:
    """Generate personalized guidance for a specific task with business plan context and validation"""
    
    business_context = task["business_context"]
    
    # Fetch business plan for additional context
    business_plan = {}
    if session_id:
        business_plan = await fetch_business_plan_context(session_id)
    
    business_plan_context = ""
    if business_plan.get("executive_summary"):
        business_plan_context = f"""
    
    BUSINESS PLAN CONTEXT:
    {business_plan.get('executive_summary', '')[:500]}
    
    Target Market: {business_plan.get('target_market', 'Not specified')[:200]}
    """
    
    guidance_prompt = f"""
    Generate comprehensive, personalized guidance for {business_context['business_name']} - a {business_context['business_type']} in the {business_context['industry']} industry, located in {business_context['location']}.
    
    CURRENT IMPLEMENTATION TASK:
    - Title: {task['title']}
    - Description: {task['description']}
    - Purpose: {task['purpose']}
    - Phase: {task.get('phase_name', 'Implementation')}
    - Options: {', '.join(task['options'])}
    - Angel Actions: {', '.join(task['angel_actions'])}
    - Estimated Time: {task['estimated_time']}
    - Priority: {task['priority']}
    {business_plan_context}
    
    CRITICAL REQUIREMENTS:
    1. ALL guidance MUST be SPECIFIC to {business_context['business_name']}
    2. ALL recommendations MUST be relevant to {business_context['location']} (local laws, regulations, resources)
    3. ALL advice MUST be tailored to the {business_context['industry']} industry
    4. Reference their business plan context when relevant
    5. Include location-specific service providers, legal requirements, and resources
    
    Provide:
    1. Why this task is critical FOR THEIR SPECIFIC BUSINESS
    2. Step-by-step guidance tailored to THEIR INDUSTRY and LOCATION
    3. Specific recommendations based on THEIR BUSINESS CONTEXT
    4. Common pitfalls to avoid IN THEIR INDUSTRY and LOCATION
    5. Success metrics for THEIR SPECIFIC BUSINESS
    6. Local resources and contacts in {business_context['location']}
    
    Make every sentence specific to their business, industry, and location. Avoid generic advice.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": ANGEL_SYSTEM_PROMPT},
                {"role": "user", "content": guidance_prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        initial_response = response.choices[0].message.content
        
        # Validate and enhance response with business context
        validated_response = await validate_response_context(
            initial_response,
            task,
            business_context,
            business_plan
        )
        
        return validated_response
        
    except Exception as e:
        print(f"Error generating task guidance: {e}")
        return "Guidance generation in progress..."

async def generate_service_providers(task: Dict, session_data: Dict) -> List[Dict]:
    """Generate service provider recommendations for a specific task"""
    
    business_context = task["business_context"]
    location = business_context["location"]
    industry = business_context["industry"]
    
    # This would typically integrate with a service provider database
    # For now, we'll generate recommendations based on task type
    providers = []
    
    if "LEGAL" in task["id"]:
        providers = [
            {
                "name": "LegalZoom",
                "type": "Online Legal Services",
                "description": "Comprehensive online legal services for business formation",
                "pricing": "$79-$299",
                "local": False,
                "website": "https://www.legalzoom.com",
                "rating": 4.2,
                "specialties": ["Business Formation", "Trademark Registration", "Legal Documents"]
            },
            {
                "name": f"Local Business Attorney - {location}",
                "type": "Local Legal Services",
                "description": "Personalized legal guidance for business formation and compliance",
                "pricing": "$200-$400/hour",
                "local": True,
                "website": "Contact local bar association",
                "rating": 4.5,
                "specialties": ["Business Law", "Compliance", "Contract Review"]
            },
            {
                "name": "Rocket Lawyer",
                "type": "Online Legal Platform",
                "description": "Affordable legal services and document templates",
                "pricing": "$39.99/month",
                "local": False,
                "website": "https://www.rocketlawyer.com",
                "rating": 4.0,
                "specialties": ["Legal Documents", "Business Formation", "Legal Advice"]
            }
        ]
    elif "FINANCIAL" in task["id"]:
        providers = [
            {
                "name": "Chase Business Banking",
                "type": "Business Banking",
                "description": "Comprehensive business banking solutions",
                "pricing": "Varies by account type",
                "local": True,
                "website": "https://www.chase.com/business",
                "rating": 4.1,
                "specialties": ["Business Checking", "Credit Cards", "Merchant Services"]
            },
            {
                "name": "QuickBooks",
                "type": "Accounting Software",
                "description": "Leading accounting software for small businesses",
                "pricing": "$15-$200/month",
                "local": False,
                "website": "https://quickbooks.intuit.com",
                "rating": 4.3,
                "specialties": ["Accounting", "Invoicing", "Financial Reporting"]
            },
            {
                "name": f"Local CPA - {location}",
                "type": "Local Accounting Services",
                "description": "Personalized accounting and tax services",
                "pricing": "$150-$300/hour",
                "local": True,
                "website": "Contact local CPA association",
                "rating": 4.4,
                "specialties": ["Tax Preparation", "Bookkeeping", "Financial Planning"]
            }
        ]
    
    return providers

async def generate_kickstart_plan(task: Dict, session_data: Dict, session_id: str = None) -> Dict:
    """Generate a detailed kickstart plan for a specific task with business plan context and validation"""
    
    business_context = task["business_context"]
    
    # Fetch business plan for additional context
    business_plan = {}
    if session_id:
        business_plan = await fetch_business_plan_context(session_id)
    
    business_plan_context = ""
    if business_plan.get("executive_summary"):
        business_plan_context = f"""
    
    BUSINESS PLAN CONTEXT:
    {business_plan.get('executive_summary', '')[:500]}
    
    Marketing Strategy: {business_plan.get('marketing_strategy', 'Not specified')[:200]}
    """
    
    kickstart_prompt = f"""
    Generate a detailed kickstart plan for {business_context['business_name']} - a {business_context['business_type']} in the {business_context['industry']} industry, located in {business_context['location']}.
    
    CURRENT IMPLEMENTATION TASK:
    - Title: {task['title']}
    - Description: {task['description']}
    - Purpose: {task['purpose']}
    - Phase: {task.get('phase_name', 'Implementation')}
    - Options: {', '.join(task['options'])}
    - Angel Actions: {', '.join(task['angel_actions'])}
    {business_plan_context}
    
    CRITICAL REQUIREMENTS:
    1. ALL action steps MUST be SPECIFIC to {business_context['business_name']} and their {business_context['industry']} industry
    2. ALL resources MUST be relevant to {business_context['location']}
    3. Include SPECIFIC local contacts, services, and resources in {business_context['location']}
    4. Reference their business plan goals and align with their strategy
    5. Provide industry-specific tools and platforms for {business_context['industry']}
    
    Create a detailed mini-plan that includes:
    1. Sub-tasks with specific actions Angel can perform FOR THIS SPECIFIC BUSINESS
    2. Templates and documents Angel can create TAILORED to their industry
    3. Research Angel can conduct SPECIFIC to their location and industry
    4. Timeline and milestones REALISTIC for their business type
    5. Success criteria MEASURABLE for their specific goals
    6. Local service providers and contacts in {business_context['location']}
    
    Make EVERY recommendation specific to their business name, industry, and location. No generic advice.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": ANGEL_SYSTEM_PROMPT},
                {"role": "user", "content": kickstart_prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        plan_content = response.choices[0].message.content
        
        # Validate and enhance response with business context
        validated_plan = await validate_response_context(
            plan_content,
            task,
            business_context,
            business_plan
        )
        
        return {
            "plan": validated_plan,
            "sub_tasks": task["angel_actions"],
            "estimated_time": task["estimated_time"],
            "priority": task["priority"]
        }
    except Exception as e:
        print(f"Error generating kickstart plan: {e}")
        return {
            "plan": "Kickstart plan generation in progress...",
            "sub_tasks": task["angel_actions"],
            "estimated_time": task["estimated_time"],
            "priority": task["priority"]
        }

async def handle_task_completion(task_id: str, completion_data: Dict, session_data: Dict) -> Dict:
    """Handle task completion with verification and next steps"""
    
    task = await get_implementation_task(task_id, session_data)
    if not task:
        return {"error": "Task not found"}
    
    # Generate completion verification
    verification_prompt = f"""
    Verify the completion of implementation task: {task['title']}
    
    Completion Data:
    - Decision Made: {completion_data.get('decision', 'Not specified')}
    - Actions Taken: {completion_data.get('actions', 'Not specified')}
    - Documents Uploaded: {completion_data.get('documents', 'None')}
    - Additional Notes: {completion_data.get('notes', 'None')}
    
    Task Requirements:
    - Purpose: {task['purpose']}
    - Options: {', '.join(task['options'])}
    
    Provide:
    1. Verification that the task is complete
    2. Confirmation of the decision/action taken
    3. Next steps or follow-up actions needed
    4. Any additional recommendations
    
    Be encouraging and supportive while ensuring completeness.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": ANGEL_SYSTEM_PROMPT},
                {"role": "user", "content": verification_prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        
        return {
            "verification": response.choices[0].message.content,
            "task_completed": True,
            "next_task": await get_next_implementation_task(session_data, [task_id])
        }
    except Exception as e:
        print(f"Error handling task completion: {e}")
        return {
            "verification": "Task completion verification in progress...",
            "task_completed": True,
            "next_task": await get_next_implementation_task(session_data, [task_id])
        }

def get_implementation_progress(completed_tasks: List[str]) -> Dict:
    """Calculate implementation progress"""
    total_tasks = sum(len(phase["tasks"]) for phase in IMPLEMENTATION_TASKS.values())
    completed_count = len(completed_tasks)
    
    progress_percent = round((completed_count / total_tasks) * 100) if total_tasks > 0 else 0
    
    return {
        "completed": completed_count,
        "total": total_tasks,
        "percent": progress_percent,
        "phases_completed": len([phase for phase in IMPLEMENTATION_TASKS.values() 
                               if all(task["id"] in completed_tasks for task in phase["tasks"])])
    }
