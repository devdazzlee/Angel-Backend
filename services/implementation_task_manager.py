from openai import AsyncOpenAI
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from services.specialized_agents_service import agents_manager
from services.rag_service import conduct_rag_research, validate_with_rag, generate_rag_insights
from services.service_provider_tables_service import generate_provider_table, get_task_providers

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class ImplementationTaskManager:
    """Manages implementation tasks with RAG-powered guidance and service providers"""
    
    def __init__(self):
        self.task_phases = {
            "legal_formation": {
                "name": "Legal Formation & Compliance",
                "tasks": [
                    "business_structure_selection",
                    "business_registration",
                    "tax_id_application",
                    "permits_licenses",
                    "insurance_requirements"
                ]
            },
            "financial_setup": {
                "name": "Financial Planning & Setup",
                "tasks": [
                    "business_bank_account",
                    "accounting_system",
                    "budget_planning",
                    "funding_strategy",
                    "financial_tracking"
                ]
            },
            "operations_development": {
                "name": "Product & Operations Development",
                "tasks": [
                    "supply_chain_setup",
                    "equipment_procurement",
                    "operational_processes",
                    "quality_control",
                    "inventory_management"
                ]
            },
            "marketing_sales": {
                "name": "Marketing & Sales Strategy",
                "tasks": [
                    "brand_development",
                    "marketing_strategy",
                    "sales_process",
                    "customer_acquisition",
                    "digital_presence"
                ]
            },
            "launch_scaling": {
                "name": "Full Launch & Scaling",
                "tasks": [
                    "go_to_market",
                    "team_building",
                    "performance_monitoring",
                    "growth_strategies",
                    "customer_feedback"
                ]
            }
        }
    
    async def get_next_implementation_task(self, session_data: Dict[str, Any], completed_tasks: List[str]) -> Dict[str, Any]:
        """Get the next implementation task based on progress"""
        
        # Determine current phase and next task
        current_phase, next_task_id = self._determine_next_task(completed_tasks)
        
        if not next_task_id:
            return {"status": "completed", "message": "All implementation tasks completed"}
        
        # Generate task details (use fast mode to avoid web search loops)
        task_details = await self._generate_task_details_fast(next_task_id, session_data)
        
        # Get service providers for this task (use predefined providers for speed)
        service_providers = self._get_predefined_service_providers(next_task_id, session_data)
        
        # Generate mentor insights
        mentor_insights = await self._generate_mentor_insights(next_task_id, session_data)
        
        return {
            "task_id": next_task_id,
            "phase": current_phase,
            "task_details": task_details,
            "service_providers": service_providers,
            "mentor_insights": mentor_insights,
            "angel_actions": self._get_angel_actions(next_task_id),
            "estimated_time": self._get_estimated_time(next_task_id),
            "priority": self._get_priority(next_task_id)
        }
    
    def _determine_next_task(self, completed_tasks: List[str]) -> tuple[str, str]:
        """Determine the next task based on completed tasks"""
        
        for phase_key, phase_data in self.task_phases.items():
            for task_id in phase_data["tasks"]:
                if task_id not in completed_tasks:
                    return phase_key, task_id
        
        return None, None
    
    async def _generate_task_details(self, task_id: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed task information using RAG research"""
        
        # Get task name and description
        task_name = task_id.replace('_', ' ').title()
        task_description = f"Complete the {task_name} process for your business"
        
        # Conduct fast RAG research for implementation phase
        research_query = f"{task_name} business setup {session_data.get('industry', '')} {session_data.get('location', '')}"
        rag_research = await conduct_rag_research(research_query, session_data, "implementation_fast")
        
        # Use predefined options for faster response
        options = self._get_predefined_options(task_id)
        
        return {
            "title": task_name,
            "description": task_description,
            "purpose": f"Establish proper {task_name.lower()} for business compliance and operations",
            "options": options[:4],  # Limit to 4 options
            "research_insights": rag_research.get('analysis', 'Research insights available'),
            "estimated_time": self._get_estimated_time(task_id),
            "priority": self._get_priority(task_id)
        }
    
    async def _get_task_service_providers(self, task_id: str, session_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get service providers for a specific task"""
        
        try:
            providers = await get_task_providers(task_id, f"implementation task {task_id}", session_data)
            return providers.get('provider_table', {}).get('providers', [])
        except:
            return []
    
    async def _generate_mentor_insights(self, task_id: str, session_data: Dict[str, Any]) -> str:
        """Generate mentor insights for the task using predefined insights for speed"""
        
        # Use predefined insights for faster response
        insights_map = {
            "business_structure_selection": "Choose the structure that best fits your growth plans and liability needs. LLC is popular for startups, while C-Corp is better for seeking investment.",
            "business_registration": "Complete registration early to establish your business legally. Consider using professional services for complex requirements.",
            "tax_id_application": "Apply for EIN immediately after choosing your business structure. It's free and required for most business activities.",
            "business_bank_account": "Separate personal and business finances from day one. This is crucial for legal protection and tax purposes.",
            "accounting_system": "Set up proper accounting systems early to avoid complications later. Choose software that scales with your business."
        }
        
        return insights_map.get(task_id, "Focus on getting this task done right the first time. Take your time to research your options and choose the approach that best fits your business needs and budget.")
    
    async def _generate_task_details_fast(self, task_id: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate task details without RAG research for faster response"""
        
        # Get task name and description
        task_name = task_id.replace('_', ' ').title()
        task_description = f"Complete the {task_name} process for your business"
        
        # Use predefined options for faster response
        options = self._get_predefined_options(task_id)
        
        # Use predefined research insights
        research_insights = self._get_predefined_research_insights(task_id)
        
        return {
            "title": task_name,
            "description": task_description,
            "purpose": f"Establish proper {task_name.lower()} for business compliance and operations",
            "options": options,
            "research_insights": research_insights,
            "estimated_time": self._get_estimated_time(task_id),
            "priority": self._get_priority(task_id)
        }
    
    def _get_predefined_research_insights(self, task_id: str) -> str:
        """Get predefined research insights for faster response"""
        
        insights_map = {
            "business_structure_selection": "Based on current business best practices, choosing the right legal structure is crucial for liability protection, tax benefits, and future growth. LLC is popular for startups due to flexibility and protection.",
            "business_registration": "Business registration establishes your legal entity and is required for most business activities. Early registration helps establish credibility and legal protection.",
            "tax_id_application": "An EIN (Employer Identification Number) is required for most business activities including opening bank accounts, hiring employees, and filing taxes. It's free to obtain from the IRS.",
            "business_bank_account": "Separating personal and business finances is essential for legal protection, tax purposes, and professional credibility. Most banks require business registration documents.",
            "accounting_system": "Proper accounting systems help track finances, ensure compliance, and provide insights for business decisions. Choose software that scales with your business needs."
        }
        
        return insights_map.get(task_id, "Based on current business best practices and regulatory requirements, here are the key considerations for this implementation task.")
    
    def _get_angel_actions(self, task_id: str) -> List[str]:
        """Get Angel AI actions for a task"""
        
        action_map = {
            "business_structure_selection": [
                "Generate business structure comparison chart",
                "Research state-specific requirements",
                "Create decision matrix for structure selection"
            ],
            "business_registration": [
                "Draft registration documents",
                "Generate registration checklist",
                "Research filing requirements"
            ],
            "business_bank_account": [
                "Compare bank options and requirements",
                "Generate application documents checklist",
                "Create banking setup timeline"
            ],
            "accounting_system": [
                "Compare accounting software options",
                "Generate chart of accounts template",
                "Create financial tracking procedures"
            ]
        }
        
        return action_map.get(task_id, [
            "Research best practices for this task",
            "Generate implementation checklist",
            "Create timeline and milestones"
        ])
    
    def _get_estimated_time(self, task_id: str) -> str:
        """Get estimated time for task completion"""
        
        time_map = {
            "business_structure_selection": "1-2 days",
            "business_registration": "1-2 weeks", 
            "tax_id_application": "1-3 days",
            "permits_licenses": "2-4 weeks",
            "business_bank_account": "3-5 days",
            "accounting_system": "1 week"
        }
        
        return time_map.get(task_id, "1-2 weeks")
    
    def _get_priority(self, task_id: str) -> str:
        """Get priority level for task"""
        
        high_priority_tasks = [
            "business_structure_selection",
            "business_registration", 
            "tax_id_application",
            "business_bank_account"
        ]
        
        return "High" if task_id in high_priority_tasks else "Medium"
    
    def _get_predefined_options(self, task_id: str) -> List[str]:
        """Get predefined options for faster response"""
        
        options_map = {
            "business_structure_selection": [
                "LLC (Limited Liability Company)",
                "C-Corporation", 
                "S-Corporation",
                "Partnership"
            ],
            "business_registration": [
                "Online Registration (DIY)",
                "Professional Service Provider",
                "Legal Service Package",
                "Hybrid Approach"
            ],
            "tax_id_application": [
                "Online EIN Application (Free)",
                "Professional Tax Service",
                "Business Formation Package",
                "Accountant Assistance"
            ],
            "business_bank_account": [
                "Local Bank Branch",
                "Online Business Banking",
                "Credit Union",
                "Business Banking Consultant"
            ],
            "accounting_system": [
                "QuickBooks Online",
                "Xero Accounting",
                "Wave (Free)",
                "Professional Bookkeeper"
            ]
        }
        
        return options_map.get(task_id, [
            "Professional Service Provider",
            "DIY with Online Resources", 
            "Hybrid Approach (Partial DIY + Consultation)",
            "Full Service Package"
        ])
    
    def _get_predefined_service_providers(self, task_id: str, session_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get predefined service providers for faster response"""
        
        providers_map = {
            "business_structure_selection": [
                {
                    "name": "Local Business Attorney",
                    "type": "Legal Professional",
                    "local": True,
                    "description": "Local attorney specializing in business formation and legal structure selection",
                    "estimated_cost": "$200-500/hour",
                    "contact_method": "Phone or email consultation",
                    "specialties": "Business formation, legal structure, compliance"
                },
                {
                    "name": "Online Legal Services",
                    "type": "Legal Service Provider",
                    "local": False,
                    "description": "Online legal services for business formation and structure selection",
                    "estimated_cost": "$100-300",
                    "contact_method": "Online platform",
                    "specialties": "Business formation, legal documents, compliance"
                },
                {
                    "name": "Business Formation Service",
                    "type": "Business Services",
                    "local": True,
                    "description": "Local business formation service for startups and small businesses",
                    "estimated_cost": "$150-400",
                    "contact_method": "Phone or in-person consultation",
                    "specialties": "Business formation, registration, compliance"
                }
            ],
            "business_registration": [
                {
                    "name": "State Business Registration Service",
                    "type": "Government Service",
                    "local": False,
                    "description": "Official state business registration service",
                    "estimated_cost": "$50-200 (filing fees)",
                    "contact_method": "Online or mail",
                    "specialties": "Business registration, state compliance"
                },
                {
                    "name": "Local Business Consultant",
                    "type": "Business Consultant",
                    "local": True,
                    "description": "Local consultant specializing in business registration and setup",
                    "estimated_cost": "$100-300/hour",
                    "contact_method": "Phone or in-person consultation",
                    "specialties": "Business registration, compliance, setup"
                },
                {
                    "name": "Online Business Formation Platform",
                    "type": "Online Service",
                    "local": False,
                    "description": "Online platform for business registration and formation",
                    "estimated_cost": "$100-500",
                    "contact_method": "Online platform",
                    "specialties": "Business registration, formation, compliance"
                }
            ],
            "tax_id_application": [
                {
                    "name": "IRS EIN Application",
                    "type": "Government Service",
                    "local": False,
                    "description": "Free online EIN application through IRS website",
                    "estimated_cost": "Free",
                    "contact_method": "Online application",
                    "specialties": "EIN application, tax ID, business registration"
                },
                {
                    "name": "Local Tax Professional",
                    "type": "Tax Professional",
                    "local": True,
                    "description": "Local tax professional for EIN application and tax setup",
                    "estimated_cost": "$100-250",
                    "contact_method": "Phone or in-person consultation",
                    "specialties": "EIN application, tax setup, compliance"
                },
                {
                    "name": "Business Tax Service",
                    "type": "Tax Service",
                    "local": True,
                    "description": "Local business tax service for startups and small businesses",
                    "estimated_cost": "$150-300",
                    "contact_method": "Phone or in-person consultation",
                    "specialties": "Tax setup, EIN application, compliance"
                }
            ]
        }
        
        return providers_map.get(task_id, [
            {
                "name": "Local Business Professional",
                "type": "Business Services",
                "local": True,
                "description": "Local business professional for general business setup and compliance",
                "estimated_cost": "$100-300/hour",
                "contact_method": "Phone or in-person consultation",
                "specialties": "Business setup, compliance, general business services"
            },
            {
                "name": "Online Business Service",
                "type": "Online Service",
                "local": False,
                "description": "Online business service platform for various business needs",
                "estimated_cost": "$50-200",
                "contact_method": "Online platform",
                "specialties": "Business services, compliance, setup"
            },
            {
                "name": "Business Consultant",
                "type": "Business Consultant",
                "local": True,
                "description": "Local business consultant for startup and small business guidance",
                "estimated_cost": "$150-400/hour",
                "contact_method": "Phone or in-person consultation",
                "specialties": "Business strategy, setup, compliance"
            }
        ])