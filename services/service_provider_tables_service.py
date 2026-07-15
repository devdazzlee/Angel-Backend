from openai import AsyncOpenAI
import os
import json
import re
import asyncio
import phonenumbers
from datetime import datetime
from typing import Dict, List, Any, Optional, TypedDict
from urllib.parse import urlparse
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

    # Floor for total providers (local + nationwide) shown per category, so a
    # step never surfaces just the 2 nationwide fallbacks. See
    # _get_predefined_providers_with_local, which distributes the local-side
    # shortfall across the category's provider types.
    MIN_TOTAL_PROVIDERS = 5

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
        """Find REAL local businesses via live web search — grounded, not generated.

        Plain chat completions have no access to real-world data, so asking one to
        "generate realistic local businesses" always produced fabricated names,
        addresses, and phone numbers (e.g. near-identical "Liaquatabad Legal ___"
        listings, or a 555-01XX number — the block reserved for fictional use).

        This uses OpenAI's Responses API with the built-in `web_search_preview`
        tool, so the model is actually searching the live web rather than
        completing a plausible-sounding pattern. As a second, independent check,
        every candidate's claimed website is verified against the URLs the
        search tool actually cited (`url_citation` annotations) — if a result's
        website isn't backed by a real citation the search performed, it's
        dropped rather than trusted. If nothing verifiable turns up, this
        returns an empty list — no placeholder, no invented fallback business.
        """

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
        Search the web for up to {count} REAL, currently operating businesses that could help a
        founder complete this implementation step. The founder's business is in {location}. If
        that names a specific neighborhood or district within a larger city, don't restrict the
        search to that neighborhood alone — a provider anywhere in the surrounding city/metro
        area that can realistically serve a business there counts as local (a business attorney
        or CPA across town is still genuinely usable; use your judgment on what "serves this
        area" reasonably means here). Only include a business if it actually turned up in your
        search results — never invent, guess, or complete a plausible name, address, phone
        number, or email. If you find fewer than {count} genuine matches, return fewer. If you
        find none, return an empty list.

        IMPLEMENTATION STEP (what the user is trying to accomplish):
        - Step: {step_title}
        - Details: {step_description}

        Provider type to search for: {provider_type}
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
        - Every "website" value must be copied exactly from a URL you actually found while searching — do not construct or guess a URL.
        - If you report a "phone", it MUST be in full international format starting with "+"
          and the correct country calling code for where the business is actually located
          (e.g. "+92 21 1234567" for Karachi, Pakistan — NOT a bare local number, and NOT a
          different country's number). If you are not confident of the correct country code,
          leave phone as "" rather than guess or default to a US-style number.
        - Leave email or address as "" if your search results didn't clearly show it — never fabricate a plausible-looking value.

        After searching, respond with ONLY a JSON object — no prose, no markdown fences — in this shape:
        {{"providers": [{{"name": "", "type": "", "description": "", "specialties": "", "estimated_cost": "", "phone": "", "email": "", "website": "", "key_considerations": "", "address": ""}}]}}
        """

        try:
            # "high" search context = the model considers more of what it finds before
            # answering, which reduces false negatives (real businesses that exist but
            # get missed) without changing the no-fabrication rules above.
            web_search_tool: Dict[str, Any] = {
                "type": "web_search_preview",
                "search_context_size": "high",
            }
            if location:
                # This field is a soft geo-bias hint for the search tool, not a hard filter —
                # passing the full "Neighborhood, City" string is fine even though it isn't a
                # bare city name.
                web_search_tool["user_location"] = {"type": "approximate", "city": location}

            response = await client.responses.create(
                model="gpt-4o",
                instructions=(
                    "You are a rigorous local-business researcher. You only report businesses "
                    "you actually find via web search. You never fabricate a name, address, "
                    "phone number, email, or website — an empty result is always better than "
                    "a made-up one."
                ),
                tools=[web_search_tool],
                input=prompt,
                max_output_tokens=2500,
            )

            raw_text = response.output_text or ""
            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if not json_match:
                print(
                    f"⚠️ [providers:{provider_type}] no JSON object found in model output "
                    f"(len={len(raw_text)}); raw tail: {raw_text[-300:]!r}"
                )
                _local_providers_cache[cache_key] = []
                return []

            result = json.loads(json_match.group())
            providers = result.get("providers", result.get("businesses", []))

            # Confirm a real web search actually happened this turn, and collect the domains
            # of any pages the model opened while doing it.
            #
            # NOTE: `url_citation` annotations (the obvious-looking way to verify a claimed
            # website) only attach to inline citations within *written prose* — they never
            # populate when the model's final output is pure JSON with no prose, which is
            # exactly what we require it to output. Relying on that was silently rejecting
            # every real, correctly-grounded result (verified via diagnostic logging: real
            # businesses with real phone numbers/addresses/domains were coming back from
            # search and then getting thrown away because `cited_domains` was always empty).
            # `web_search_call` items are the structurally correct signal — they record
            # whether the tool was actually invoked, independent of prose vs. JSON output.
            search_performed = False
            opened_domains = set()
            for output_item in response.output:
                if getattr(output_item, "type", None) != "web_search_call":
                    continue
                search_performed = True
                action = getattr(output_item, "action", None)
                if getattr(action, "type", None) == "open_page":
                    url = getattr(action, "url", None)
                    if url:
                        opened_domains.add(self._domain(url))

            # A claimed website matching a page the model actually opened is the strongest
            # possible evidence, logged here for visibility. But requiring it as a hard gate
            # isn't viable: the model frequently answers from a search-result snippet without
            # opening the page, and per-URL verification isn't reliably obtainable from this
            # API when the output is JSON. The real, structural safeguard is `search_performed`
            # below — if the tool was never invoked at all, nothing is trustworthy regardless
            # of what the JSON claims.
            if providers and opened_domains:
                confirmed = sum(
                    1 for p in providers
                    if self._domain(str(p.get("website") or "")) in opened_domains
                )
                print(f"    (of these, {confirmed} website(s) match a page the model actually opened)")

            verified = providers if search_performed else []
            if providers and not search_performed:
                print(f"⚠️ [providers:{provider_type}] model returned providers but never called web_search — discarding as ungrounded")

            industry = (labels.get("industry") or "").lower()
            filtered = [
                p for p in verified
                if not self._looks_like_competitor(p, industry, intent)
            ]
            verified = filtered or verified

            # Diagnostics: this pipeline drops candidates at up to two points (search never
            # invoked / competitor filter), and without visibility into which one fired, "why
            # are there so few providers" is unanswerable from outside. This makes the funnel
            # explicit in the logs.
            print(
                f"🔎 [providers:{provider_type}] model returned {len(providers)}, "
                f"search_performed={search_performed}, {len(verified)} passed grounding+competitor filter"
            )
            if providers and not verified:
                print(f"    dropped candidates: {json.dumps(providers, default=str)[:800]}")

            for provider in verified:
                provider["local"] = True
                if not provider.get("type"):
                    provider["type"] = f"Local {provider_type}"
                # A malformed/wrong-country phone number is worse than no phone number —
                # validate and normalize it, or drop it, rather than display it as-is.
                provider["phone"] = self._normalize_phone(provider.get("phone", ""))

            _local_providers_cache[cache_key] = verified
            return verified[:count]

        except Exception as e:
            tail = locals().get("raw_text", "")[-300:]
            print(f"❌ [providers:{provider_type}] error: {e}" + (f"; raw tail: {tail!r}" if tail else ""))
            return []

    @staticmethod
    def _domain(url: str) -> str:
        """Normalize a URL down to a bare, lowercase, www-stripped domain for comparison."""
        try:
            netloc = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
            return netloc[4:] if netloc.startswith("www.") else netloc
        except Exception:
            return url.strip().lower()

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Validate a phone number with libphonenumber and format it with its country code.

        The model is instructed to always include the correct "+<country code>" prefix, but
        instructions alone don't guarantee it — a bare local number, or a number from the
        wrong country, is worse than showing nothing (a founder could try to call it and get
        a wrong number or a dead end). `phonenumbers` (Google's libphonenumber) is a real,
        deterministic validator, not a guess: if the number doesn't parse as a genuine,
        internationally-dialable number, it's dropped instead of shown malformed.
        """
        phone = (phone or "").strip()
        if not phone:
            return ""
        try:
            parsed = phonenumbers.parse(phone, None)  # None: requires the "+" prefix already present
            if not phonenumbers.is_valid_number(parsed):
                return ""
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        except phonenumbers.NumberParseException:
            return ""

    @classmethod
    def _dedupe_providers(cls, providers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Drop repeat listings of the same real business found via different searches."""
        seen_names = set()
        seen_domains = set()
        deduped: List[Dict[str, Any]] = []
        for provider in providers:
            name_key = re.sub(r"\s+", " ", str(provider.get("name") or "")).strip().lower()
            website = str(provider.get("website") or "").strip()
            domain_key = cls._domain(website) if website else ""

            if name_key and name_key in seen_names:
                continue
            if domain_key and domain_key in seen_domains:
                continue

            if name_key:
                seen_names.add(name_key)
            if domain_key:
                seen_domains.add(domain_key)
            deduped.append(provider)
        return deduped

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
            "local_provider_types": ["Business Consultant", "Industry Advisor", "Local Service Provider"],
            "static_keywords": [],
            "exclude_consumer_industry": False,
            "guidance": "Recommend professionals or services that help complete the step.",
        }

        category_defaults: Dict[str, ProviderIntent] = {
            "legal": {
                "search_role": "Attorney or legal compliance professional",
                "local_provider_types": [
                    "Business Attorney", "Business Formation Lawyer", "Registered Agent / Filing Service",
                ],
                "static_keywords": ["legal", "attorney", "law", "formation", "compliance"],
                "exclude_consumer_industry": False,
                "guidance": "Recommend law firms or legal services — not unrelated businesses.",
            },
            "financial": {
                "search_role": "CPA, accountant, or financial services firm",
                "local_provider_types": ["CPA/Accountant", "Small Business Banker", "Bookkeeping Service"],
                "static_keywords": ["accounting", "cpa", "tax", "bookkeeping", "bank"],
                "exclude_consumer_industry": False,
                "guidance": "Recommend accounting, tax, or banking partners.",
            },
            "marketing": {
                "search_role": "Marketing agency or branding professional",
                "local_provider_types": ["Marketing Agency", "Brand Designer", "Local SEO/Social Media Specialist"],
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
                "local_provider_types": ["IT Consultant", "Web Development Agency", "Managed IT Services Provider"],
                "static_keywords": ["software", "it", "technology", "hosting", "cloud"],
                "exclude_consumer_industry": False,
                "guidance": "Recommend technology vendors and IT service providers.",
            },
            "consulting": {
                "search_role": "Business consultant or industry advisor",
                "local_provider_types": ["Business Consultant", "Industry Advisor", "Local Business Coach"],
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
            provider_types = intent["local_provider_types"][:3] or ["Business Consultant"]
            # Distribute the shortfall against MIN_TOTAL_PROVIDERS across the
            # available provider types in a single request per type (never
            # re-request the same type — generate_actual_local_providers caches
            # by (location, category, provider_type), so a second call for the
            # same type would just return the same cached rows instead of more).
            target_local = max(self.MIN_TOTAL_PROVIDERS - len(static_providers), len(provider_types))
            base_count, remainder = divmod(target_local, len(provider_types))

            # Each of these is a real, "high" search-context web search, which can easily take
            # several seconds. Running them one-at-a-time (the old `for ... await` here) serialized
            # up to 3 of them, multiplying the total wait and making the whole request more likely
            # to hit a timeout partway through — which silently truncated the result to whichever
            # provider_type happened to finish first, i.e. "very few local providers." Firing them
            # concurrently cuts total latency roughly 3x for the same real searches.
            search_tasks = []
            for i, provider_type in enumerate(provider_types):
                count_for_type = base_count + (1 if i < remainder else 0)
                count_for_type = max(count_for_type, 1)
                search_tasks.append(self.generate_actual_local_providers(
                    provider_type=provider_type,
                    category=category,
                    business_context=business_context,
                    location=location,
                    count=count_for_type,
                    task_context=task_context,
                    provider_intent=intent,
                ))

            results = await asyncio.gather(*search_tasks, return_exceptions=True)
            for provider_type, result in zip(provider_types, results):
                if isinstance(result, Exception):
                    print(f"Error generating local providers for {provider_type}: {result}")
                else:
                    local_providers.extend(result)

        # Different provider_type searches (e.g. "Business Attorney" and "Legal Advisor")
        # can each independently turn up the same real business — dedupe by name and by
        # website domain before combining, so it isn't listed twice.
        local_providers = self._dedupe_providers(local_providers)

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
