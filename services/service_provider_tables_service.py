from openai import AsyncOpenAI
import os
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, TypedDict
from services.rag_service import research_service_providers_rag
from services.specialized_agents_service import agents_manager
from utils.business_context import prompt_labels

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Cache for generated local providers to avoid regenerating
_local_providers_cache = {}


class ProviderIntent(TypedDict):
    search_role: str
    local_provider_types: List[str]
    static_keywords: List[str]
    exclude_consumer_industry: bool
    guidance: str


class ServiceProviderTableGenerator:
    """Generate comprehensive service provider tables with local providers"""
    
    def __init__(self):
        self.provider_categories = {
            "legal": {
                "name": "Legal Services",
                "subcategories": ["Business Formation", "Contract Law", "Intellectual Property", "Compliance"],
                "local_keywords": ["attorney", "lawyer", "law firm", "legal services"]
            },
            "financial": {
                "name": "Financial Services", 
                "subcategories": ["Accounting", "Tax Services", "Banking", "Financial Planning"],
                "local_keywords": ["cpa", "accountant", "bank", "financial advisor"]
            },
            "marketing": {
                "name": "Marketing Services",
                "subcategories": ["Digital Marketing", "Branding", "Content Creation", "Social Media"],
                "local_keywords": ["marketing agency", "digital marketing", "branding", "advertising"]
            },
            "operations": {
                "name": "Operations Services",
                "subcategories": ["Supply Chain", "Logistics", "Equipment", "Facilities"],
                "local_keywords": ["supplier", "vendor", "equipment", "facilities"]
            },
            "technology": {
                "name": "Technology Services",
                "subcategories": ["Software Development", "IT Support", "Web Development", "Cloud Services"],
                "local_keywords": ["software", "IT", "web development", "technology"]
            },
            "consulting": {
                "name": "Business Consulting",
                "subcategories": ["Strategy", "Management", "Industry Expertise", "Growth"],
                "local_keywords": ["consultant", "advisor", "strategist", "expert"]
            }
        }
    
    async def generate_service_provider_table(self, task_context: str, business_context: Dict[str, Any], location: str = None, phase_hint: str = None) -> Dict[str, Any]:
        """Generate a comprehensive service provider table for a specific task.

        ``phase_hint`` is the Implementation phase the user is currently on
        (e.g. ``"Legal Formation & Compliance"`` or ``"legal_formation"``).
        When provided it deterministically constrains the set of provider
        categories returned, instead of relying on free-text keyword
        matching against ``task_context``. This is the right behaviour
        because the only task-context strings the frontend sends today are
        either the implementation task title or a generic placeholder, and
        without a phase hint the keyword inference would frequently miss
        and fan out to *every* category — producing irrelevant marketing /
        IT / media providers for legal-formation tasks, and turning a
        single LLM call into six.
        """

        # Determine relevant service categories for the task
        relevant_categories = self._determine_relevant_categories(task_context, phase_hint)
        
        # Generate providers for each relevant category
        provider_tables = {}
        
        for category in relevant_categories:
            try:
                providers = await self._generate_category_providers(
                    category, business_context, location, task_context=task_context
                )
                provider_tables[category] = providers
            except Exception as e:
                provider_tables[category] = {
                    "error": f"Failed to generate providers for {category}: {str(e)}",
                    "providers": []
                }
        
        # Generate comprehensive table with all providers
        comprehensive_table = await self._generate_comprehensive_table(provider_tables, task_context, business_context)
        
        return {
            "task_context": task_context,
            "business_context": business_context,
            "location": location,
            "relevant_categories": relevant_categories,
            "provider_tables": provider_tables,
            "comprehensive_table": comprehensive_table,
            "timestamp": datetime.now().isoformat()
        }
    
    async def generate_actual_local_providers(
        self,
        provider_type: str,
        category: str,
        business_context: Dict[str, Any],
        location: str,
        count: int = 5,
        task_context: str = "",
        provider_intent: Optional[ProviderIntent] = None,
    ) -> List[Dict[str, Any]]:
        """Generate local provider listings aligned to the active implementation step."""

        intent = provider_intent or self._resolve_provider_intent(task_context, category, business_context)
        fields = self._extract_task_context_fields(task_context)
        labels = prompt_labels(business_context)
        step_title = fields.get("active_step_title") or fields.get("task_title") or "current step"
        step_description = (
            fields.get("active_step_description")
            or fields.get("task_description")
            or task_context
            or step_title
        )

        cache_key = f"{location}_{category}_{provider_type}_{hash(task_context)}"
        if cache_key in _local_providers_cache:
            return _local_providers_cache[cache_key][:count]

        prompt = f"""
        Generate a list of {count} REALISTIC local businesses in {location} that can help a founder complete this implementation step.

        IMPLEMENTATION STEP (what the user is trying to accomplish):
        - Step: {step_title}
        - Details: {step_description}

        Provider type to generate: {provider_type}
        Role: {intent['search_role']}

        Business context (for tailoring only — do NOT recommend consumer-facing competitors):
        - Industry: {labels['industry']}
        - Business type: {labels['business_type']}
        - Venture: {labels['business_name']}

        {intent['guidance']}

        CRITICAL RULES:
        - Recommend VENDORS, SUPPLIERS, WHOLESALERS, PROFESSIONALS, or B2B SERVICES that help the founder complete the step.
        - DO NOT recommend other {labels['industry']} businesses that sell the same product/service directly to consumers (competitors).
        - DO NOT recommend mobile trucks, shops, or brands that operate the same kind of business as the user.
        - Each listing must clearly be a supplier/vendor/partner — not a rival business.

        For each business provide JSON fields: name, type, local (always true), description, specialties,
        estimated_cost, contact_method, key_considerations, address, rating (4.0-5.0)

        Return JSON: {{"providers": [ ... ]}}
        """
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a local business directory expert. Generate realistic local business listings."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            providers = result.get("providers", result.get("businesses", []))

            industry = (labels.get("industry") or "").lower()
            filtered = [
                p for p in providers
                if not self._looks_like_competitor(p, industry, intent)
            ]
            providers = filtered or providers
            
            # Ensure all providers have required fields
            for provider in providers:
                provider["local"] = True
                if "type" not in provider:
                    provider["type"] = f"Local {provider_type}"
                    
            # Cache the results
            _local_providers_cache[cache_key] = providers
            
            return providers
            
        except Exception as e:
            print(f"Error generating local providers: {e}")
            return []
    
    # Map known Implementation phase names (and their normalized internal
    # ids) deterministically to provider categories. The frontend sends the
    # phase name as `category` on the /implementation/service-providers
    # endpoint; this dict is the source of truth for what providers an
    # active step in each phase should surface.
    _PHASE_TO_CATEGORIES = {
        "legal_formation": ["legal"],
        "legal foundation": ["legal"],
        "legal formation & compliance": ["legal"],
        "financial_setup": ["financial"],
        "financial systems": ["financial"],
        "financial planning & setup": ["financial"],
        "operations_development": ["operations"],
        "operations setup": ["operations"],
        "product & operations development": ["operations"],
        "marketing_sales": ["marketing"],
        "marketing & sales": ["marketing"],
        "marketing & sales strategy": ["marketing"],
        "launch_scaling": ["consulting", "marketing"],
        "launch & growth": ["consulting", "marketing"],
        "full launch & scaling": ["consulting", "marketing"],
    }

    def _determine_relevant_categories(self, task_context: str, phase_hint: str = None) -> List[str]:
        """Determine which service categories are relevant for the task.

        Resolution order:
          1. If ``phase_hint`` matches a known Implementation phase, use the
             deterministic mapping. This is the strongest signal — the
             phase the user is on directly determines which provider
             vertical applies.
          2. Otherwise fall back to keyword inference on ``task_context``.
             The keyword sets below intentionally cover the wording used by
             the hand-coded implementation task ids (e.g.
             "business_structure_selection") as well as the LLM-generated
             roadmap step names.
          3. If neither produces a hit, return a single safe default
             (``["consulting"]``) rather than fanning out to every
             category. Returning everything is what was producing
             unrelated providers (marketing / IT / media) on a Legal
             Formation step, and was also responsible for the ~6× LLM
             round-trip slowness on the providers tab.
        """

        if phase_hint:
            normalized_hint = phase_hint.strip().lower()
            mapped = self._PHASE_TO_CATEGORIES.get(normalized_hint)
            if mapped:
                return list(mapped)

        fields = self._extract_task_context_fields(task_context)
        task_lower = self._combined_task_text(task_context, fields)
        relevant_categories: List[str] = []

        # Legal — covers business formation, structure choice, IP, licensing, compliance.
        if any(keyword in task_lower for keyword in [
            'legal', 'compliance', 'license', 'permit', 'regulation', 'contract',
            'incorporation', 'incorporate', 'formation', 'structure', 'entity',
            'llc', 'corporation', 'partnership', 'sole proprietor', 'register',
            'registration', 'trademark', 'patent', 'intellectual property', 'ein',
            'tax id', 'business name', 'naming', 'attorney', 'lawyer',
        ]):
            relevant_categories.append("legal")

        # Financial — accounting, tax, banking, funding.
        if any(keyword in task_lower for keyword in [
            'financial', 'finance', 'accounting', 'bookkeeping', 'tax', 'banking',
            'bank account', 'funding', 'budget', 'revenue', 'cpa', 'invoice',
            'payroll', 'expense', 'cash flow', 'capital',
        ]):
            relevant_categories.append("financial")

        # Marketing.
        if any(keyword in task_lower for keyword in [
            'marketing', 'branding', 'brand', 'advertising', 'ad campaign',
            'social media', 'content', 'promotion', 'seo', 'public relations',
            'pr', 'press', 'campaign', 'audience',
        ]):
            relevant_categories.append("marketing")

        # Operations — supply chain, equipment, facilities.
        if any(keyword in task_lower for keyword in [
            'operations', 'supply', 'supplier', 'vendor', 'equipment', 'facility',
            'facilities', 'logistics', 'production', 'inventory', 'fulfillment',
            'warehouse', 'shipping',
        ]):
            relevant_categories.append("operations")

        # Technology / IT.
        if any(keyword in task_lower for keyword in [
            'technology', 'software', ' it ', 'website', 'digital', 'automation',
            'cloud', 'hosting', 'domain', 'web app', 'mobile app', 'platform',
            'security', 'cybersecurity', 'database',
        ]):
            relevant_categories.append("technology")

        # Consulting — strategy, mentorship, advisory.
        if any(keyword in task_lower for keyword in [
            'consulting', 'consultant', 'strategy', 'advice', 'advisory',
            'guidance', 'expertise', 'planning', 'mentor', 'coach',
        ]):
            relevant_categories.append("consulting")

        if not relevant_categories:
            # Single safe default — generalist business consulting. Surfacing
            # *all* categories here is what produced the irrelevant-providers
            # bug, so we deliberately do not do that anymore.
            relevant_categories = ["consulting"]

        return relevant_categories

    def _extract_task_context_fields(self, task_context: str) -> Dict[str, str]:
        """Parse structured task context from the frontend implementation UI."""
        fields = {
            "task_title": "",
            "task_description": "",
            "task_purpose": "",
            "active_step_title": "",
            "active_step_description": "",
            "raw": task_context or "",
        }
        if not task_context:
            return fields

        patterns = {
            "task_title": r"Current Task:\s*(.+?)(?:\n\n|\Z)",
            "task_description": r"Task Description:\s*(.+?)(?:\n\n|\Z)",
            "task_purpose": r"Task Purpose:\s*(.+?)(?:\n\n|\Z)",
            "active_step_title": r"Active Step \d+:\s*(.+?)(?:\n\n|\Z)",
            "active_step_description": r"Active Step Description:\s*(.+?)(?:\n\n|\Z)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, task_context, re.DOTALL | re.IGNORECASE)
            if match:
                fields[key] = match.group(1).strip()
        return fields

    def _combined_task_text(self, task_context: str, fields: Optional[Dict[str, str]] = None) -> str:
        """Single lowercase blob for keyword/intent resolution."""
        parsed = fields or self._extract_task_context_fields(task_context)
        parts = [
            parsed.get("task_title", ""),
            parsed.get("task_description", ""),
            parsed.get("task_purpose", ""),
            parsed.get("active_step_title", ""),
            parsed.get("active_step_description", ""),
            task_context or "",
        ]
        return " ".join(p for p in parts if p).lower()

    def _resolve_provider_intent(
        self,
        task_context: str,
        category: str,
        business_context: Dict[str, Any],
    ) -> ProviderIntent:
        """Map the active implementation step to the kind of providers to surface."""
        fields = self._extract_task_context_fields(task_context)
        combined = self._combined_task_text(task_context, fields)
        labels = prompt_labels(business_context)
        industry = (labels.get("industry") or "business").strip()

        default: ProviderIntent = {
            "search_role": "Business service provider",
            "local_provider_types": ["Business Consultant"],
            "static_keywords": [],
            "exclude_consumer_industry": False,
            "guidance": "Recommend professionals or services that help complete the step.",
        }

        category_defaults: Dict[str, ProviderIntent] = {
            "legal": {
                "search_role": "Attorney or legal compliance professional",
                "local_provider_types": ["Business Attorney", "Business Formation Lawyer"],
                "static_keywords": ["legal", "attorney", "law", "formation", "compliance"],
                "exclude_consumer_industry": False,
                "guidance": "Recommend law firms or legal services — not unrelated businesses.",
            },
            "financial": {
                "search_role": "CPA, accountant, or financial services firm",
                "local_provider_types": ["CPA/Accountant", "Small Business Banker"],
                "static_keywords": ["accounting", "cpa", "tax", "bookkeeping", "bank"],
                "exclude_consumer_industry": False,
                "guidance": "Recommend accounting, tax, or banking partners.",
            },
            "marketing": {
                "search_role": "Marketing agency or branding professional",
                "local_provider_types": ["Marketing Agency", "Brand Designer"],
                "static_keywords": ["marketing", "advertising", "brand", "seo", "social"],
                "exclude_consumer_industry": True,
                "guidance": "Recommend agencies or freelancers who provide marketing services — not other consumer brands in the same industry.",
            },
            "operations": {
                "search_role": "Supplier, wholesaler, or operations vendor",
                "local_provider_types": [
                    "Restaurant Supply Wholesaler",
                    "Commercial Kitchen Equipment Supplier",
                    "Food Ingredient Distributor",
                ],
                "static_keywords": [
                    "supplier", "wholesale", "distributor", "b2b", "equipment",
                    "inventory", "logistics", "restaurant supply",
                ],
                "exclude_consumer_industry": True,
                "guidance": (
                    f"Recommend wholesalers, distributors, equipment vendors, and B2B supply "
                    f"partners. Never recommend other {industry} businesses that sell to consumers."
                ),
            },
            "technology": {
                "search_role": "IT consultant or software vendor",
                "local_provider_types": ["IT Consultant", "Web Development Agency"],
                "static_keywords": ["software", "it", "technology", "hosting", "cloud"],
                "exclude_consumer_industry": False,
                "guidance": "Recommend technology vendors and IT service providers.",
            },
            "consulting": {
                "search_role": "Business consultant or industry advisor",
                "local_provider_types": ["Business Consultant", "Industry Advisor"],
                "static_keywords": ["consulting", "advisor", "mentor", "sbdc"],
                "exclude_consumer_industry": False,
                "guidance": "Recommend advisors who help execute the step.",
            },
        }

        intent = dict(category_defaults.get(category, default))

        # Step-level overrides beat coarse category defaults.
        if any(k in combined for k in [
            "supplier", "suppliers", "vendor", "vendors", "supply chain",
            "wholesale", "wholesaler", "distributor", "ingredient", "raw material",
            "inventory", "procurement", "sourcing", "restaurant supply",
        ]):
            intent.update({
                "search_role": "Wholesale supplier, vendor, or B2B distributor",
                "local_provider_types": [
                    "Restaurant Food Supply Wholesaler",
                    "Commercial Kitchen Equipment Supplier",
                    "Packaging Supplies Vendor",
                ],
                "static_keywords": [
                    "supplier", "wholesale", "distributor", "b2b", "amazon business",
                    "restaurant depot", "sysco", "webstaurant", "equipment",
                ],
                "exclude_consumer_industry": True,
                "guidance": (
                    f"The user is identifying suppliers/vendors for inputs and equipment. "
                    f"Recommend B2B wholesalers and supply companies — NOT other {industry} "
                    f"operators that compete for the same customers."
                ),
            })

        if any(k in combined for k in [
            "attorney", "lawyer", "legal", "llc", "incorporation", "trademark",
            "compliance", "permit", "license",
        ]):
            intent.update(category_defaults["legal"])

        if any(k in combined for k in [
            "accounting", "bookkeeping", "cpa", "tax", "payroll", "bank account",
        ]):
            intent.update(category_defaults["financial"])

        if any(k in combined for k in [
            "marketing", "branding", "social media", "advertising", "seo", "campaign",
        ]):
            intent.update(category_defaults["marketing"])

        return intent  # type: ignore[return-value]

    def _looks_like_competitor(
        self,
        provider: Dict[str, Any],
        industry: str,
        intent: ProviderIntent,
    ) -> bool:
        """Heuristic filter for consumer-facing businesses in the user's industry."""
        if not intent.get("exclude_consumer_industry") or not industry:
            return False

        blob = " ".join(
            str(provider.get(k, "") or "")
            for k in ("name", "description", "specialties", "type")
        ).lower()
        industry_tokens = [
            t.strip()
            for t in re.split(r"[\s,/]+", industry.lower())
            if len(t.strip()) >= 4
        ]

        vendor_signals = (
            "wholesale", "supplier", "vendor", "distributor", "b2b",
            "restaurant supply", "food service", "equipment", "commercial kitchen",
            "packaging", "logistics", "office depot", "amazon business",
        )
        competitor_signals = (
            "mobile", "food truck", "smoothie", "cafe", "coffee shop",
            "restaurant", "eatery", "bar ", "bistro", "our menu", "order online",
            "walk-in", "dine-in", "franchise location",
        )

        has_vendor_signal = any(s in blob for s in vendor_signals)
        has_competitor_signal = any(s in blob for s in competitor_signals)
        mentions_industry = any(t in blob for t in industry_tokens)

        if has_vendor_signal and not has_competitor_signal:
            return False
        if has_competitor_signal and mentions_industry:
            return True
        if mentions_industry and not has_vendor_signal:
            return True
        return False

    def _filter_static_providers(
        self,
        providers: List[Dict[str, Any]],
        intent: ProviderIntent,
    ) -> List[Dict[str, Any]]:
        keywords = [k.lower() for k in intent.get("static_keywords", []) if k]
        if not keywords:
            return providers

        scored: List[tuple[int, Dict[str, Any]]] = []
        for provider in providers:
            blob = " ".join(
                str(provider.get(k, "") or "")
                for k in ("name", "description", "specialties", "type")
            ).lower()
            score = sum(1 for kw in keywords if kw in blob)
            scored.append((score, provider))

        scored.sort(key=lambda item: item[0], reverse=True)
        matched = [p for score, p in scored if score > 0]
        return matched if matched else providers
    
    async def _generate_category_providers(
        self,
        category: str,
        business_context: Dict[str, Any],
        location: str = None,
        task_context: str = "",
    ) -> Dict[str, Any]:
        """Generate providers for a specific category"""
        
        category_info = self.provider_categories[category]
        
        # Use fast mode for implementation phase - skip RAG research for speed
        rag_results = {
            "service_type": category,
            "providers_found": 0,
            "providers": [],
            "recommendations": f"Consider local {category} providers for personalized service."
        }
        
        # Generate structured provider data including actual local businesses
        providers = await self._get_predefined_providers_with_local(
            category, category_info, business_context, location, task_context=task_context
        )
        
        return {
            "category": category,
            "category_name": category_info["name"],
            "subcategories": category_info["subcategories"],
            "providers": providers,
            "rag_research": rag_results,
            "location": location
        }
    
    async def _get_predefined_providers_with_local(
        self,
        category: str,
        category_info: Dict[str, Any],
        business_context: Dict[str, Any],
        location: str = None,
        task_context: str = "",
    ) -> List[Dict[str, Any]]:
        """Get providers including AI-generated local businesses for the active step."""

        intent = self._resolve_provider_intent(task_context, category, business_context)
        static_providers = self._filter_static_providers(
            self._get_static_providers(category, location),
            intent,
        )

        local_providers: List[Dict[str, Any]] = []
        if location:
            for provider_type in intent["local_provider_types"][:3]:
                try:
                    generated = await self.generate_actual_local_providers(
                        provider_type=provider_type,
                        category=category,
                        business_context=business_context,
                        location=location,
                        count=1,
                        task_context=task_context,
                        provider_intent=intent,
                    )
                    local_providers.extend(generated)
                except Exception as e:
                    print(f"Error generating local providers for {provider_type}: {e}")

        combined = local_providers + static_providers
        industry = (prompt_labels(business_context).get("industry") or "").lower()
        filtered = [
            p for p in combined
            if not self._looks_like_competitor(p, industry, intent)
        ]
        return filtered if filtered else combined
    
    def _get_static_providers(self, category: str, location: str = None) -> List[Dict[str, Any]]:
        """Get static nationwide service providers"""
        
        # Only nationwide services (software, platforms, national companies)
        nationwide_providers = {
            "legal": [
                {
                    "name": "LegalZoom",
                    "type": "Nationwide Service",
                    "local": False,
                    "description": "Online legal services for business formation, document preparation, and compliance.",
                    "key_considerations": "Cost-effective, standardized processes, limited customization",
                    "estimated_cost": "$99-$399 per service",
                    "contact_method": "Website: legalzoom.com",
                    "specialties": "Business formation, document preparation"
                },
                {
                    "name": "Rocket Lawyer",
                    "type": "Nationwide Service",
                    "local": False,
                    "description": "Online legal platform with document templates and attorney consultations.",
                    "key_considerations": "Subscription model, document library, attorney network",
                    "estimated_cost": "$39.99/month",
                    "contact_method": "Website: rocketlawyer.com",
                    "specialties": "Document templates, legal consultations"
                }
            ],
            "financial": [
                {
                    "name": "QuickBooks",
                    "type": "Nationwide Service",
                    "local": False,
                    "description": "Cloud-based accounting software with integrated tax services.",
                    "key_considerations": "User-friendly, integrations, scalability",
                    "estimated_cost": "$15-$200/month",
                    "contact_method": "Website: quickbooks.intuit.com",
                    "specialties": "Accounting software, tax services"
                },
                {
                    "name": "Xero",
                    "type": "Nationwide Service",
                    "local": False,
                    "description": "Cloud accounting platform with third-party integrations.",
                    "key_considerations": "Modern interface, extensive integrations, mobile access",
                    "estimated_cost": "$13-$70/month",
                    "contact_method": "Website: xero.com",
                    "specialties": "Cloud accounting, integrations"
                }
            ],
            "marketing": [
                {
                    "name": "HubSpot",
                    "type": "Nationwide Service",
                    "local": False,
                    "description": "All-in-one marketing, sales, and service platform.",
                    "key_considerations": "Comprehensive platform, automation, analytics",
                    "estimated_cost": "$45-$3,200/month",
                    "contact_method": "Website: hubspot.com",
                    "specialties": "Marketing automation, CRM, analytics"
                },
                {
                    "name": "Google Ads",
                    "type": "Nationwide Service",
                    "local": False,
                    "description": "Pay-per-click advertising platform for search and display ads.",
                    "key_considerations": "Large reach, targeting options, performance tracking",
                    "estimated_cost": "Pay-per-click model",
                    "contact_method": "Website: ads.google.com",
                    "specialties": "Search advertising, display advertising"
                }
            ],
            "operations": [
                {
                    "name": "Amazon Business",
                    "type": "Nationwide Service",
                    "local": False,
                    "description": "B2B marketplace for business supplies, ingredients, packaging, and equipment.",
                    "key_considerations": "Wide selection, bulk pricing, fast delivery",
                    "estimated_cost": "Varies by product",
                    "contact_method": "Website: business.amazon.com",
                    "specialties": "Business supplies, wholesale ingredients, equipment, bulk purchasing"
                },
                {
                    "name": "WebstaurantStore",
                    "type": "Nationwide Service",
                    "local": False,
                    "description": "Online restaurant supply store for food service equipment and disposables.",
                    "key_considerations": "Large catalog, competitive pricing, ships nationwide",
                    "estimated_cost": "Varies by product",
                    "contact_method": "Website: webstaurantstore.com",
                    "specialties": "Restaurant supplies, kitchen equipment, packaging"
                },
                {
                    "name": "Sysco",
                    "type": "Nationwide Service",
                    "local": False,
                    "description": "Food products and supplies wholesaler for restaurants and food businesses.",
                    "key_considerations": "Requires account setup, strong for recurring ingredient orders",
                    "estimated_cost": "Wholesale pricing",
                    "contact_method": "Website: sysco.com",
                    "specialties": "Food wholesale, restaurant supply distribution"
                },
                {
                    "name": "Restaurant Depot",
                    "type": "Mixed",
                    "local": True,
                    "description": "Wholesale cash-and-carry supplier for restaurants and food businesses.",
                    "key_considerations": "Membership may be required, strong for bulk ingredients",
                    "estimated_cost": "Wholesale pricing",
                    "contact_method": "Local warehouse or restaurantdepot.com",
                    "specialties": "Wholesale food, beverages, supplies, equipment"
                },
                {
                    "name": "Office Depot",
                    "type": "Mixed",
                    "local": True,
                    "description": "Office supplies and business services with local stores.",
                    "key_considerations": "Local presence, business services, bulk discounts",
                    "estimated_cost": "Varies by service",
                    "contact_method": "Local store or website",
                    "specialties": "Office supplies, printing, business services"
                }
            ],
            "technology": [
                {
                    "name": "Local IT Consultant",
                    "type": "Local Professional",
                    "local": True,
                    "description": "Local technology consultant for IT setup, maintenance, and support.",
                    "key_considerations": "Local support, personalized service, ongoing relationship",
                    "estimated_cost": "$75-$200/hour",
                    "contact_method": "Local IT directory",
                    "specialties": "IT setup, maintenance, support"
                },
                {
                    "name": "Microsoft 365",
                    "type": "Nationwide Service",
                    "local": False,
                    "description": "Cloud-based productivity suite with business applications.",
                    "key_considerations": "Comprehensive suite, cloud storage, collaboration tools",
                    "estimated_cost": "$6-$22/user/month",
                    "contact_method": "Website: microsoft.com/microsoft-365",
                    "specialties": "Productivity suite, cloud storage, collaboration"
                },
                {
                    "name": "Google Workspace",
                    "type": "Nationwide Service",
                    "local": False,
                    "description": "Cloud-based productivity and collaboration platform.",
                    "key_considerations": "Gmail integration, collaboration tools, cloud storage",
                    "estimated_cost": "$6-$18/user/month",
                    "contact_method": "Website: workspace.google.com",
                    "specialties": "Email, collaboration, cloud storage"
                }
            ],
            "consulting": [
                {
                    "name": "SCORE",
                    "type": "Non-profit",
                    "local": True,
                    "description": "Free business mentoring and education from retired executives.",
                    "key_considerations": "Free service, experienced mentors, local chapters",
                    "estimated_cost": "Free",
                    "contact_method": "Website: score.org",
                    "specialties": "Business mentoring, education, networking"
                },
                {
                    "name": "Small Business Development Center",
                    "type": "Government",
                    "local": True,
                    "description": "Government-funded business consulting and training services.",
                    "key_considerations": "Free/low-cost, government-backed, comprehensive services",
                    "estimated_cost": "Free to low-cost",
                    "contact_method": "Local SBDC office",
                    "specialties": "Business planning, training, funding assistance"
                }
            ]
        }
        
        return nationwide_providers.get(category, [
            {
                "name": "Provider Name",
                "type": "Service Provider",
                "local": False,
                "description": "Service description",
                "key_considerations": "Considerations",
                "estimated_cost": "Contact for pricing",
                "contact_method": "Website or phone",
                "specialties": "General services"
            }
        ])
    
    async def _create_structured_providers(self, category: str, category_info: Dict[str, Any], business_context: Dict[str, Any], location: str, rag_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create structured provider data"""
        
        # Generate providers using AI with RAG research
        from utils.business_context import prompt_labels

        labels = prompt_labels(business_context)
        target_location = location or labels['location']
        provider_prompt = f"""
        Generate a comprehensive list of service providers for {category_info['name']} based on the following context:
        
        Business Context:
        - Industry: {labels['industry']}
        - Location: {labels['location']}
        - Business Type: {labels['business_type']}
        - Business Name: {labels['business_name']}
        
        Target Location: {target_location}
        
        Subcategories: {', '.join(category_info['subcategories'])}
        
        Research Data: {rag_results.get('recommendations', 'No specific research data available')}
        
        Generate at least 5 providers with the following structure for each:
        1. Name: Specific company/service name
        2. Type: Type of service (e.g., "Online Service", "Local Professional", "National Firm")
        3. Local: Boolean indicating if they serve the target location
        4. Description: Detailed description of services offered
        5. Key Considerations: Important factors to consider when choosing this provider
        6. Estimated Cost: Cost range or pricing model
        7. Contact Method: How to reach them
        8. Specialties: Specific areas of expertise
        
        Ensure you include:
        - At least 2 local providers (marked as Local: true)
        - Mix of online and offline services
        - Different price points and service levels
        - Providers suitable for startups/small businesses
        
        Format as JSON array of provider objects.
        """
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": provider_prompt}],
                temperature=0.4,
                max_tokens=2000
            )
            
            # Parse the response as JSON
            providers_text = response.choices[0].message.content
            
            # Extract JSON from the response
            import re
            json_match = re.search(r'\[.*\]', providers_text, re.DOTALL)
            if json_match:
                providers = json.loads(json_match.group())
            else:
                # Fallback: create providers from text
                providers = self._parse_providers_from_text(providers_text, category_info)
            
            # Ensure we have the required structure
            structured_providers = []
            for provider in providers:
                structured_provider = {
                    "name": provider.get("name", "Provider Name"),
                    "type": provider.get("type", "Service Provider"),
                    "local": provider.get("local", False),
                    "description": provider.get("description", "Service description"),
                    "key_considerations": provider.get("key_considerations", "Considerations"),
                    "estimated_cost": provider.get("estimated_cost", "Contact for pricing"),
                    "contact_method": provider.get("contact_method", "Website or phone"),
                    "specialties": provider.get("specialties", "General services")
                }
                structured_providers.append(structured_provider)
            
            return structured_providers
            
        except Exception as e:
            # Fallback: generate basic providers
            return self._generate_fallback_providers(category, category_info, business_context, location)
    
    def _parse_providers_from_text(self, text: str, category_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse providers from text response"""
        
        providers = []
        lines = text.split('\n')
        
        current_provider = {}
        for line in lines:
            line = line.strip()
            if line.startswith('Name:'):
                if current_provider:
                    providers.append(current_provider)
                current_provider = {"name": line.replace('Name:', '').strip()}
            elif line.startswith('Type:'):
                current_provider["type"] = line.replace('Type:', '').strip()
            elif line.startswith('Local:'):
                current_provider["local"] = 'true' in line.lower()
            elif line.startswith('Description:'):
                current_provider["description"] = line.replace('Description:', '').strip()
            elif line.startswith('Key Considerations:'):
                current_provider["key_considerations"] = line.replace('Key Considerations:', '').strip()
            elif line.startswith('Estimated Cost:'):
                current_provider["estimated_cost"] = line.replace('Estimated Cost:', '').strip()
            elif line.startswith('Contact Method:'):
                current_provider["contact_method"] = line.replace('Contact Method:', '').strip()
            elif line.startswith('Specialties:'):
                current_provider["specialties"] = line.replace('Specialties:', '').strip()
        
        if current_provider:
            providers.append(current_provider)
        
        return providers
    
    def _generate_fallback_providers(self, category: str, category_info: Dict[str, Any], business_context: Dict[str, Any], location: str) -> List[Dict[str, Any]]:
        """Generate fallback providers when AI generation fails"""
        labels = prompt_labels(business_context)
        industry_label = labels["industry"]

        fallback_providers = {
            "legal": [
                {
                    "name": "Local Business Attorney",
                    "type": "Legal Professional",
                    "local": True,
                    "description": f"Local attorney specializing in {industry_label} law and business formation",
                    "key_considerations": "Industry experience, local knowledge, cost structure",
                    "estimated_cost": "$200-500/hour",
                    "contact_method": "Local bar association or referrals",
                    "specialties": "Business formation, contracts, compliance"
                },
                {
                    "name": "LegalZoom",
                    "type": "Nationwide Service",
                    "local": False,
                    "description": "Online legal document preparation and business formation services",
                    "key_considerations": "Cost-effective, standardized, limited customization",
                    "estimated_cost": "$99-399",
                    "contact_method": "Online platform",
                    "specialties": "Business formation, document preparation"
                }
            ],
            "financial": [
                {
                    "name": "Local CPA Firm",
                    "type": "Accounting Professional",
                    "local": True,
                    "description": f"Certified Public Accountant specializing in {industry_label} accounting",
                    "key_considerations": "Industry expertise, local tax knowledge, ongoing support",
                    "estimated_cost": "$150-300/hour",
                    "contact_method": "Local CPA directory or referrals",
                    "specialties": "Tax preparation, bookkeeping, financial planning"
                },
                {
                    "name": "QuickBooks ProAdvisor",
                    "type": "Nationwide Service",
                    "local": False,
                    "description": "Certified QuickBooks professionals for accounting setup and training",
                    "key_considerations": "QuickBooks expertise, remote support, cost-effective",
                    "estimated_cost": "$50-150/hour",
                    "contact_method": "QuickBooks ProAdvisor directory",
                    "specialties": "QuickBooks setup, training, bookkeeping"
                }
            ],
            "marketing": [
                {
                    "name": "Local Marketing Agency",
                    "type": "Marketing Professional",
                    "local": True,
                    "description": f"Full-service marketing agency with {industry_label} experience",
                    "key_considerations": "Local market knowledge, full-service capabilities, ongoing support",
                    "estimated_cost": "$2,000-10,000/month",
                    "contact_method": "Local business directory or referrals",
                    "specialties": "Digital marketing, branding, local SEO"
                },
                {
                    "name": "HubSpot Partner",
                    "type": "Nationwide Service",
                    "local": False,
                    "description": "Certified HubSpot partners for inbound marketing and CRM setup",
                    "key_considerations": "HubSpot expertise, inbound marketing, scalable solutions",
                    "estimated_cost": "$1,000-5,000/month",
                    "contact_method": "HubSpot Partner directory",
                    "specialties": "Inbound marketing, CRM, marketing automation"
                }
            ]
        }
        
        return fallback_providers.get(category, [
            {
                "name": f"Local {category_info['name']} Provider",
                "type": "Local Professional",
                "local": True,
                "description": f"Local provider specializing in {category_info['name']}",
                "key_considerations": "Local expertise, personalized service",
                "estimated_cost": "Contact for pricing",
                "contact_method": "Local directory or referrals",
                "specialties": "General services"
            }
        ])
    
    async def _generate_comprehensive_table(self, provider_tables: Dict[str, Any], task_context: str, business_context: Dict[str, Any]) -> str:
        """Generate a comprehensive service provider table"""
        
        # Create comprehensive table using AI
        table_prompt = f"""
        Create a comprehensive service provider table for the following task:
        
        Task Context: {task_context}
        Business Context: {business_context}
        
        Provider Data: {json.dumps(provider_tables, indent=2)}
        
        Generate a well-formatted table that includes:
        1. Provider Name
        2. Type (Local/Online/National)
        3. Description
        4. Key Considerations
        5. Estimated Cost
        6. Contact Method
        7. Specialties
        
        Format as a markdown table with clear headers and organized by service category.
        Include a summary of recommendations and selection criteria.
        """
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": table_prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"Comprehensive table generation failed: {str(e)}"
    
    async def get_task_specific_providers(self, task_id: str, task_description: str, business_context: Dict[str, Any], location: str = None) -> Dict[str, Any]:
        """Get providers specific to a particular implementation task"""
        
        # Use specialized agents to determine the best providers for this task
        agent_guidance = await agents_manager.get_multi_agent_guidance(
            f"Recommend service providers for: {task_description}",
            business_context,
            []
        )
        
        # Generate provider table based on agent recommendations
        provider_table = await self.generate_service_provider_table(
            task_description,
            business_context,
            location
        )
        
        # Combine agent guidance with provider recommendations
        enhanced_table = await self._enhance_table_with_agent_guidance(
            provider_table,
            agent_guidance,
            task_description
        )
        
        return {
            "task_id": task_id,
            "task_description": task_description,
            "agent_guidance": agent_guidance,
            "provider_table": enhanced_table,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _enhance_table_with_agent_guidance(self, provider_table: Dict[str, Any], agent_guidance: Dict[str, Any], task_description: str) -> Dict[str, Any]:
        """Enhance provider table with agent guidance"""
        
        enhancement_prompt = f"""
        Enhance the following service provider table with expert guidance:
        
        Task Description: {task_description}
        
        Provider Table: {json.dumps(provider_table, indent=2)}
        
        Agent Guidance: {json.dumps(agent_guidance, indent=2)}
        
        Enhance the table by:
        1. Adding expert recommendations and insights
        2. Including selection criteria based on agent expertise
        3. Adding risk assessments and considerations
        4. Providing decision-making frameworks
        5. Including questions to ask providers
        
        Format as an enhanced provider table with expert insights.
        """
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": enhancement_prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            
            return {
                "original_table": provider_table,
                "enhanced_table": response.choices[0].message.content,
                "agent_insights": agent_guidance,
                "enhancement_timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "original_table": provider_table,
                "enhanced_table": f"Enhancement failed: {str(e)}",
                "agent_insights": agent_guidance
            }

# Global instance
provider_table_generator = ServiceProviderTableGenerator()

# Convenience functions
async def generate_provider_table(task_context: str, business_context: Dict[str, Any], location: str = None, phase_hint: str = None) -> Dict[str, Any]:
    """Generate a service provider table for a specific task.

    ``phase_hint`` (optional) is the Implementation phase name; when
    provided the categories returned are constrained deterministically.
    """
    return await provider_table_generator.generate_service_provider_table(
        task_context, business_context, location, phase_hint=phase_hint
    )

async def get_task_providers(task_id: str, task_description: str, business_context: Dict[str, Any], location: str = None) -> Dict[str, Any]:
    """Get providers for a specific implementation task"""
    return await provider_table_generator.get_task_specific_providers(task_id, task_description, business_context, location)
