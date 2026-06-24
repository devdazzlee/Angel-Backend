"""
Business Plan auto-research pipeline — registry-driven queries, synthesis, validation loop.

Each AUTO-RESEARCH question gets a fixed output contract. Before serving research
to the user, we validate relevance to the topline question and venture context;
retry once with corrective feedback if validation fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Callable, Awaitable

from services.business_plan_registry import get_question_meta
from services.questionnaire_grounding import build_questionnaire_venture_context
from utils.business_context import is_meaningful_context_value

# Tags that receive backend-injected research (must match angel_service set).
AUTO_RESEARCH_TAGS: dict[str, str] = {
    "BUSINESS_PLAN.11": "competitors",
    "BUSINESS_PLAN.12": "industry_trends",
    "BUSINESS_PLAN.17": "operational_needs",
    "BUSINESS_PLAN.23": "marketing_needs",
    "BUSINESS_PLAN.26": "permits_licenses",
    "BUSINESS_PLAN.27": "insurance",
    "BUSINESS_PLAN.34": "costs",
    "BUSINESS_PLAN.35": "scaling",
    "BUSINESS_PLAN.42": "contingency",
}

# Generic SaaS/tool vendors — invalid in trends/marketing unless venture is a platform.
GENERIC_VENDOR_NAMES = frozenset({
    "shopify", "square", "hubspot", "zoom", "quickbooks", "wix", "salesforce",
    "microsoft teams", "paypal", "bigcommerce", "ecoenclose",
})

TECH_PLATFORM_SIGNALS = frozenset({
    "saas", "software", "platform", "app", "e-commerce", "ecommerce", "marketplace",
})

# Prior answers that must inform each auto-research question (train of thought).
AUTO_RESEARCH_FOCUS_TAGS: dict[str, tuple[str, ...]] = {
    "BUSINESS_PLAN.11": (
        "BUSINESS_PLAN.01", "BUSINESS_PLAN.02", "BUSINESS_PLAN.08", "BUSINESS_PLAN.10",
    ),
    "BUSINESS_PLAN.12": (
        "BUSINESS_PLAN.01", "BUSINESS_PLAN.02", "BUSINESS_PLAN.06", "BUSINESS_PLAN.08",
    ),
    "BUSINESS_PLAN.17": (
        "BUSINESS_PLAN.01", "BUSINESS_PLAN.02", "BUSINESS_PLAN.05", "BUSINESS_PLAN.06",
        "BUSINESS_PLAN.08", "BUSINESS_PLAN.09", "BUSINESS_PLAN.14", "BUSINESS_PLAN.15",
        "BUSINESS_PLAN.16",
    ),
    "BUSINESS_PLAN.23": (
        "BUSINESS_PLAN.01", "BUSINESS_PLAN.02", "BUSINESS_PLAN.05", "BUSINESS_PLAN.06",
        "BUSINESS_PLAN.08", "BUSINESS_PLAN.18", "BUSINESS_PLAN.19", "BUSINESS_PLAN.20",
        "BUSINESS_PLAN.21", "BUSINESS_PLAN.22",
    ),
    "BUSINESS_PLAN.26": (
        "BUSINESS_PLAN.01", "BUSINESS_PLAN.05", "BUSINESS_PLAN.06", "BUSINESS_PLAN.14",
        "BUSINESS_PLAN.24",
    ),
    "BUSINESS_PLAN.27": (
        "BUSINESS_PLAN.01", "BUSINESS_PLAN.05", "BUSINESS_PLAN.06", "BUSINESS_PLAN.14",
        "BUSINESS_PLAN.15", "BUSINESS_PLAN.24",
    ),
    "BUSINESS_PLAN.34": (
        "BUSINESS_PLAN.01", "BUSINESS_PLAN.02", "BUSINESS_PLAN.05", "BUSINESS_PLAN.06",
        "BUSINESS_PLAN.14", "BUSINESS_PLAN.15", "BUSINESS_PLAN.17",
    ),
    "BUSINESS_PLAN.35": (
        "BUSINESS_PLAN.01", "BUSINESS_PLAN.02", "BUSINESS_PLAN.05", "BUSINESS_PLAN.06",
        "BUSINESS_PLAN.08", "BUSINESS_PLAN.17", "BUSINESS_PLAN.34",
    ),
    "BUSINESS_PLAN.42": (
        "BUSINESS_PLAN.01", "BUSINESS_PLAN.02", "BUSINESS_PLAN.05", "BUSINESS_PLAN.06",
        "BUSINESS_PLAN.14", "BUSINESS_PLAN.15", "BUSINESS_PLAN.17", "BUSINESS_PLAN.35",
    ),
}

HOME_BASED_FACILITY_SIGNALS = frozenset({
    "home", "house", "residence", "garage", "driveway", "my home", "from home",
    "operate out of my", "park at my",
})

OFFICE_RENTAL_SIGNALS = frozenset({
    "wework", "regus", "coworking", "co-working", "office lease", "office space",
    "liquidspace", "flexible workspace", "leasing office", "commercial lease",
    "securing space", "rent office",
})

GENERIC_TECH_STARTUP_SIGNALS = frozenset({
    "startup ecosystem", "tech sector", "fintech", "ai startup", "crunchbase",
    "glassdoor", "ziprecruiter", "hirevue", "startup genome", "tech hub",
    "tech startups", "global startup",
})


@dataclass(frozen=True)
class AutoResearchContext:
    tag: str
    research_kind: str
    business_idea: str
    business_name: str
    industry: str
    location: str
    business_type: str
    product_service: str
    target_customer: str
    problem_solved: str
    prompt_text: str
    grounding_answers: dict[str, str]

    @property
    def facilities_answer(self) -> str:
        return self.grounding_answers.get("BUSINESS_PLAN.15", "")

    @property
    def delivery_method_answer(self) -> str:
        return self.grounding_answers.get("BUSINESS_PLAN.16", "")

    @property
    def location_answer(self) -> str:
        return self.grounding_answers.get("BUSINESS_PLAN.14", "")

    def is_home_based_operation(self) -> bool:
        blob = " ".join(
            [self.facilities_answer, self.location_answer, self.business_idea]
        ).lower()
        return any(sig in blob for sig in HOME_BASED_FACILITY_SIGNALS)

    def venture_label(self) -> str:
        if is_meaningful_context_value(self.business_name):
            return self.business_name
        if is_meaningful_context_value(self.business_idea):
            return self.business_idea[:120]
        return f"a {self.business_type} in {self.industry}"

    def is_tech_platform_venture(self) -> bool:
        blob = " ".join(
            [
                self.business_idea,
                self.product_service,
                self.industry,
                self.business_type,
            ]
        ).lower()
        return any(sig in blob for sig in TECH_PLATFORM_SIGNALS)


async def build_auto_research_context(
    tag: str,
    session_data: dict | None,
    history: list | None,
    *,
    get_answer_for_tag: Callable[[list | None, str], str],
) -> AutoResearchContext | None:
    kind = AUTO_RESEARCH_TAGS.get(tag)
    meta = get_question_meta(tag)
    if not kind or not meta:
        return None

    venture = await build_questionnaire_venture_context(
        session_data,
        history,
        asked_q=tag,
        get_answer_for_tag=get_answer_for_tag,
    )

    focus_tags = AUTO_RESEARCH_FOCUS_TAGS.get(tag, ())
    grounding_answers: dict[str, str] = {}
    for focus_tag in focus_tags:
        answer = get_answer_for_tag(history, focus_tag)
        if is_meaningful_context_value(answer):
            grounding_answers[focus_tag] = answer

    return AutoResearchContext(
        tag=tag,
        research_kind=kind,
        business_idea=venture.business_idea,
        business_name=venture.business_name,
        industry=venture.industry or "the venture's industry",
        location=venture.location,
        business_type=venture.business_type or "small business",
        product_service=get_answer_for_tag(history, "BUSINESS_PLAN.02"),
        target_customer=get_answer_for_tag(history, "BUSINESS_PLAN.08"),
        problem_solved=get_answer_for_tag(history, "BUSINESS_PLAN.10"),
        prompt_text=meta.prompt_text,
        grounding_answers=grounding_answers,
    )


def format_auto_research_context_block(ctx: AutoResearchContext) -> str:
    """Full questionnaire grounding injected into synthesis — not query-only."""
    from services.business_plan_registry import get_question_objective

    lines: list[str] = [
        "AUTHORITATIVE QUESTIONNAIRE CONTEXT (from this founder's answers — do not contradict):",
    ]
    if is_meaningful_context_value(ctx.business_idea):
        lines.append(f'- Business idea (Q1): "{ctx.business_idea}"')
    if is_meaningful_context_value(ctx.business_name):
        lines.append(f'- Business name (Q5): "{ctx.business_name}"')
    if is_meaningful_context_value(ctx.industry):
        lines.append(f'- Industry (Q6): "{ctx.industry}"')
    if is_meaningful_context_value(ctx.location):
        lines.append(f'- Location: "{ctx.location}"')
    if is_meaningful_context_value(ctx.product_service):
        lines.append(f'- Product/service (Q2): "{ctx.product_service}"')
    if is_meaningful_context_value(ctx.target_customer):
        lines.append(f'- Target customer (Q8): "{ctx.target_customer}"')

    for tag, answer in sorted(
        ctx.grounding_answers.items(),
        key=lambda item: int(item[0].split(".")[-1]),
    ):
        if tag in {"BUSINESS_PLAN.01", "BUSINESS_PLAN.02", "BUSINESS_PLAN.05", "BUSINESS_PLAN.06", "BUSINESS_PLAN.08"}:
            continue
        label = get_question_objective(tag) or tag
        q_num = int(tag.split(".")[-1])
        lines.append(f'- Q{q_num} — {label}: "{answer}"')

    if ctx.research_kind == "operational_needs" and is_meaningful_context_value(ctx.facilities_answer):
        lines.append(
            f'\nOPERATIONAL CONSTRAINT: Founder already stated facilities/resources (Q15): '
            f'"{ctx.facilities_answer}". Build launch needs around THIS setup only. '
            f"Do NOT recommend office leases, coworking, or commercial space unless they explicitly asked."
        )
        if ctx.is_home_based_operation():
            lines.append(
                "This is a HOME-BASED operation — do not suggest WeWork, Regus, office rental, "
                "or generic startup workspace advice."
            )

    if ctx.research_kind == "marketing_needs" and is_meaningful_context_value(ctx.delivery_method_answer):
        lines.append(
            f'\nDELIVERY CONSTRAINT (Q16): "{ctx.delivery_method_answer}" — marketing must fit this model.'
        )

    lines.extend(
        [
            "",
            f'Topline question to answer: "{ctx.prompt_text}"',
            "Every section must be bespoke to this venture — not generic tech-startup or small-business advice.",
        ]
    )
    return "\n".join(lines)


def get_research_synthesis_sections(research_kind: str) -> str:
    """Fixed output contract per auto-research kind — prevents Q12 drift into competitor/vendor lists."""
    sections = {
        "competitors": (
            "1. **Direct Competitors (name 3-5 real companies)**: For each competitor write a block — "
            "`**<Company Name>** — <what they do>. *Position:* <market position>. *Strengths:* <2-3>. "
            "*Weaknesses:* <2-3>.` Use REAL companies only.\n"
            "2. **Competitive Position Map**: Where competitors cluster (price, customer, geography).\n"
            "3. **Insights for This Business**: 3-5 actionable insights for the founder's venture (named in the topic), "
            "each referencing a named competitor.\n"
            "4. **What to Watch**: 1-2 emerging or adjacent competitors."
        ),
        "industry_trends": (
            "1. **Industry Trends (3-5 trends)**: For each trend, name it and explain how it affects businesses "
            "like the venture described in the topic. Include data points where known.\n"
            "2. **Impact on This Venture**: 3-5 bullets translating trends into implications for THIS specific "
            "business — not generic small-business software recommendations.\n"
            "3. **What to Monitor**: 2-3 signals the founder should watch in the next 12-24 months.\n\n"
            "STRICT: Do NOT include a 'Competitive Landscape' section. Do NOT profile unrelated generic "
            "business software or tool vendors unless the venture itself is that type of platform."
        ),
        "operational_needs": (
            "1. **Short-Term Operational Needs (first 3-6 months)**: Staffing, equipment, vendors, "
            "permits, and processes — tailored to the founder's stated facilities and delivery model "
            "(see AUTHORITATIVE CONTEXT). Honor Q15/Q16; do not invent office or warehouse needs they did not describe.\n"
            "2. **Priority Sequence**: What to secure first and why for THIS venture.\n"
            "3. **Actionable Next Steps**: Concrete launch checklist items.\n\n"
            "STRICT: No 'Market Data', 'Competitive Landscape', or generic tech-startup sections. "
            "No coworking/office-lease advice for home-based operations. "
            "No unrelated fintech/SaaS/startup-ecosystem content unless this venture is in that sector."
        ),
        "marketing_needs": (
            "1. **Short-Term Marketing Priorities**: Channels and tactics for reaching the target customer "
            "described in the topic.\n"
            "2. **Budget Guidance**: Realistic ranges for a business at this stage.\n"
            "3. **Actionable Next Steps**: First 90-day marketing actions.\n\n"
            "STRICT: Do NOT default to generic SaaS tool stacks unless the venture is a software product."
        ),
        "permits_licenses": (
            "1. **Required Permits & Licenses**: Each permit/license, issuing authority, cost/timeline.\n"
            "2. **Actionable insights**: Step-by-step recommendations.\n"
            "3. **Compliance Resources**: Real platforms or advisors that help obtain permits."
        ),
        "insurance": (
            "1. **Recommended Policies**: Coverage type and estimated annual cost range.\n"
            "2. **Actionable insights**: How to select the right coverage.\n"
            "3. **Providers**: Real insurers or brokers relevant to this business type."
        ),
        "costs": (
            "1. **Startup Costs**: Real dollar ranges by category.\n"
            "2. **Operating Expenses**: Monthly/annual benchmarks.\n"
            "3. **Actionable insights**: Cost management recommendations."
        ),
        "scaling": (
            "1. **Year 1-2 Milestones**: Measurable targets.\n"
            "2. **Year 3-5 Growth Strategy**: Expansion plans.\n"
            "3. **Key Resources Needed**: Hiring, technology, funding.\n"
            "4. **Actionable Next Steps**: Immediate scaling prep."
        ),
        "contingency": (
            "1. **Potential Risks & Challenges**: 4-6 specific risks for this venture.\n"
            "2. **Contingency Plan for Each Risk**: Mitigation and action steps.\n"
            "3. **Early Warning Signs**: Indicators to monitor.\n"
            "4. **Resources & Support**: Tools and advisors."
        ),
    }
    return sections.get(
        research_kind,
        "1. **Specific findings**: Real trends, data points, and recommendations tied to the topic.\n"
        "2. **Impact on This Venture**: Implications for the business named in the topic.\n"
        "3. **Actionable insights**: Practical next steps.",
    )


def build_research_query(ctx: AutoResearchContext) -> str:
    """Grounded search query from venture facts — not generic industry strings."""
    year = datetime.now().year
    prev = year - 1
    label = ctx.venture_label()
    loc = f" in {ctx.location}" if is_meaningful_context_value(ctx.location) else ""

    if ctx.research_kind == "competitors":
        offering = ctx.product_service or ctx.business_idea
        return (
            f"Direct competitors for {label}{loc}: a business that offers {offering[:200]}. "
            f"Target customer context: {ctx.target_customer[:150] if ctx.target_customer else 'see offering'}. "
            f"Name real rival companies (not software vendors unless they are direct competitors). "
            f"Competitive positioning {prev}-{year}."
        )

    if ctx.research_kind == "industry_trends":
        return (
            f"Industry trends {prev}-{year} affecting this specific venture: {ctx.business_idea[:250]}. "
            f"Industry: {ctx.industry}. Product/service: {(ctx.product_service or '')[:150]}. "
            f"Target customer: {(ctx.target_customer or '')[:150]}. "
            f"Focus on market and industry trends — NOT a list of generic business software tools."
        )

    if ctx.research_kind == "operational_needs":
        parts = [
            f"Short-term operational launch needs (first 3-6 months) for: {ctx.business_idea[:200] or label}",
            f"Industry: {ctx.industry}",
            f"Product/service: {(ctx.product_service or '')[:120]}",
        ]
        if is_meaningful_context_value(ctx.facilities_answer):
            parts.append(f"Facilities already stated (Q15): {ctx.facilities_answer[:200]}")
        if is_meaningful_context_value(ctx.delivery_method_answer):
            parts.append(f"Delivery method (Q16): {ctx.delivery_method_answer[:120]}")
        if is_meaningful_context_value(ctx.location_answer):
            parts.append(f"Location (Q14): {ctx.location_answer[:120]}")
        parts.append(
            "Build needs around the founder's stated setup — NOT generic office/coworking or tech-startup advice."
        )
        return " ".join(parts) + f" {prev}-{year}."

    if ctx.research_kind == "marketing_needs":
        return (
            f"Short-term marketing needs and channels for {label}, {ctx.industry}{loc}, "
            f"selling to: {(ctx.target_customer or '')[:150]}. "
            f"NOT generic SaaS tool recommendations unless the venture is a software product. {prev}-{year}."
        )

    if ctx.research_kind == "permits_licenses":
        return (
            f"Permits and licenses to operate {ctx.industry} business {label}{loc}. {prev}-{year}."
        )

    if ctx.research_kind == "insurance":
        return (
            f"Insurance policies for {ctx.industry} {ctx.business_type} business {label}{loc}. {prev}-{year}."
        )

    if ctx.research_kind == "costs":
        return (
            f"Startup and operating costs for {label}, {ctx.industry}{loc}. {prev}-{year}."
        )

    if ctx.research_kind == "scaling":
        return (
            f"Realistic scaling plan years 1-5 for {label}, {ctx.industry}{loc}. {prev}-{year}."
        )

    if ctx.research_kind == "contingency":
        return (
            f"Risks and contingency plans for {label}, {ctx.industry}{loc}. {prev}-{year}."
        )

    return f"Research for {label}, {ctx.industry}{loc}. {prev}-{year}."


def _significant_tokens(text: str, limit: int = 6) -> list[str]:
    words = re.findall(r"[a-zA-Z]{4,}", (text or "").lower())
    stop = {"business", "company", "service", "services", "that", "with", "from", "your", "will", "this"}
    return [w for w in words if w not in stop][:limit]


def validate_research_output(ctx: AutoResearchContext, output: str) -> tuple[bool, str]:
    """
    Due-diligence loop: ensure research matches the topline question before serving.
    Returns (is_valid, corrective_feedback).
    """
    if not (output or "").strip():
        return False, "Output was empty."

    lower = output.lower()
    kind = ctx.research_kind

    if kind == "industry_trends":
        if "competitive landscape" in lower:
            return (
                False,
                "Q12 is INDUSTRY TRENDS only. Remove the entire 'Competitive Landscape' section. "
                "Do not profile software vendors as competitors.",
            )
        if not ctx.is_tech_platform_venture():
            found = [v for v in GENERIC_VENDOR_NAMES if v in lower]
            if found:
                return (
                    False,
                    f"This venture is not a generic tech platform. Remove vendor/tool profiles "
                    f"({', '.join(found[:4])}). Focus on industry trends affecting "
                    f"'{ctx.venture_label()}'.",
                )
        if is_meaningful_context_value(ctx.business_idea):
            tokens = _significant_tokens(ctx.business_idea)
            if tokens and not any(t in lower for t in tokens):
                return (
                    False,
                    f"Research must reference the founder's venture ({ctx.venture_label()[:80]}) "
                    f"in the 'Impact on This Venture' section — not generic small-business advice.",
                )
        if "trend" not in lower:
            return False, "Include clearly labeled industry trends (not only tool/vendor lists)."

    elif kind == "competitors":
        if not any(kw in lower for kw in ("competitor", "rival", "competes", "competing")):
            return False, "Name direct competitors — this is Q11 competitive analysis."
        if not ctx.is_tech_platform_venture():
            found = [v for v in GENERIC_VENDOR_NAMES if v in lower]
            if len(found) >= 3:
                return (
                    False,
                    "Listed generic software vendors instead of direct competitors for this venture. "
                    f"Find rivals that offer similar products/services to: {ctx.product_service or ctx.business_idea[:120]}",
                )

    elif kind == "marketing_needs":
        if not ctx.is_tech_platform_venture():
            found = [v for v in GENERIC_VENDOR_NAMES if v in lower]
            if len(found) >= 2 and "marketing" not in lower[:200]:
                return (
                    False,
                    "Marketing research should recommend channels/tactics for THIS venture, "
                    "not a generic stack of SaaS tools.",
                )

    elif kind == "operational_needs":
        if "competitive landscape" in lower or "market data" in lower:
            return (
                False,
                "Q17 is operational launch needs only. Remove 'Market Data' and 'Competitive Landscape' sections. "
                "Focus on staffing, equipment, vendors, and processes for this specific venture.",
            )
        if not ctx.is_tech_platform_venture():
            tech_hits = [s for s in GENERIC_TECH_STARTUP_SIGNALS if s in lower]
            if tech_hits:
                return (
                    False,
                    f"This is not a generic tech startup ({ctx.venture_label()}). Remove generic startup content "
                    f"({', '.join(tech_hits[:3])}). Use industry-specific operational needs.",
                )
            vendor_hits = [v for v in GENERIC_VENDOR_NAMES if v in lower]
            if vendor_hits:
                return (
                    False,
                    f"Remove generic software vendor profiles ({', '.join(vendor_hits[:3])}). "
                    f"Operational needs must match: {ctx.business_idea[:100] or ctx.industry}.",
                )
        if ctx.is_home_based_operation():
            office_hits = [s for s in OFFICE_RENTAL_SIGNALS if s in lower]
            if office_hits:
                return (
                    False,
                    f"Founder operates from home (Q15: \"{ctx.facilities_answer[:80]}\"). "
                    f"Remove office/coworking recommendations ({', '.join(office_hits[:3])}). "
                    "Focus on truck, equipment, home-base logistics, and local vendors they mentioned.",
                )
        if is_meaningful_context_value(ctx.business_idea):
            tokens = _significant_tokens(ctx.business_idea)
            if tokens and not any(t in lower for t in tokens):
                return (
                    False,
                    f"Operational needs must reference this venture ({ctx.venture_label()[:80]}) — "
                    f"not generic small-business or tech-startup templates.",
                )

    return True, ""


def format_research_footer(ctx: AutoResearchContext) -> str:
    year = datetime.now().year
    prev = year - 1
    footers = {
        "BUSINESS_PLAN.11": (
            f"\n\n*Research based on {ctx.industry} market data ({prev}-{year})*\n\n"
            "Please review these findings. Is there anything you'd like me to adjust or explore further?"
        ),
        "BUSINESS_PLAN.12": (
            f"\n\n*Research based on {prev}-{year} data*\n\n"
            "How do you think these trends will impact your business? "
            "Is there anything you'd like me to explore further?"
        ),
        "BUSINESS_PLAN.17": (
            f"\n\n*Research based on {ctx.industry} industry data ({prev}-{year})*\n\n"
            "Is there anything else you'd like to add or modify?"
        ),
        "BUSINESS_PLAN.23": (
            f"\n\n*Research based on {ctx.industry} marketing data ({prev}-{year})*\n\n"
            "Is there anything else you'd like to add?"
        ),
        "BUSINESS_PLAN.26": (
            f"\n\n*Research based on {ctx.location or ctx.industry} regulatory data ({prev}-{year})*\n\n"
            "Please evaluate to confirm if this looks correct or if you have any questions."
        ),
        "BUSINESS_PLAN.27": (
            f"\n\n*Research based on {ctx.industry} insurance requirements ({prev}-{year})*\n\n"
            "Please evaluate to confirm if this looks correct or if you have any questions."
        ),
        "BUSINESS_PLAN.34": (
            f"\n\n*Research based on {ctx.industry} industry cost data ({prev}-{year})*\n\n"
            "Is there anything else you'd like me to add?"
        ),
        "BUSINESS_PLAN.35": (
            f"\n\n*Research based on {ctx.industry} growth data ({prev}-{year})*\n\n"
            "Please review this suggested plan. You can Accept to use it as your scaling answer "
            "and continue to the next question, or ask me to adjust anything."
        ),
        "BUSINESS_PLAN.42": (
            f"\n\n*Research based on {ctx.industry} risk analysis ({prev}-{year})*\n\n"
            "Please review these suggestions. Is there anything you'd like me to adjust or explore further?"
        ),
    }
    return footers.get(
        ctx.tag,
        f"\n\n*Research based on {ctx.industry} data ({prev}-{year})*\n\nPlease review and let me know if you'd like to adjust anything.",
    )


def format_research_header(ctx: AutoResearchContext) -> str:
    headers = {
        "BUSINESS_PLAN.11": "🔍 **Competitor Research Results:**",
        "BUSINESS_PLAN.12": "🔍 **Industry Trends Research:**",
        "BUSINESS_PLAN.17": f"🔍 **Suggested Short-Term Operational Needs for {ctx.business_name or 'your venture'}:**",
        "BUSINESS_PLAN.23": f"🔍 **Suggested Short-Term Marketing Needs for {ctx.business_name or 'your venture'}:**",
        "BUSINESS_PLAN.26": f"🔍 **Permits & Licenses Research for {ctx.business_name or 'your venture'}:**",
        "BUSINESS_PLAN.27": f"🔍 **Suggested Insurance Policies for {ctx.business_name or 'your venture'}:**",
        "BUSINESS_PLAN.34": f"🔍 **Estimated Costs & Expenses for {ctx.business_name or 'your venture'}:**",
        "BUSINESS_PLAN.35": f"🔍 **Suggested Scaling & Growth Plan for {ctx.business_name or 'your venture'}:**",
        "BUSINESS_PLAN.42": f"🔍 **Suggested Contingency Plans for {ctx.business_name or 'your venture'}:**",
    }
    return f"\n\n{headers.get(ctx.tag, '🔍 **Research Results:**')}\n\n"


def build_auto_research_fallback_instruction(ctx: AutoResearchContext) -> str:
    """
    Venture-grounded fallback prompt — same context contract as primary auto-research.
    No hardcoded industry or vendor examples; uses the founder's questionnaire answers only.
    """
    context_block = format_auto_research_context_block(ctx)
    sections = get_research_synthesis_sections(ctx.research_kind)
    topic = build_research_query(ctx)
    return (
        "You are a senior business analyst. Produce research content for the founder below.\n\n"
        f"{context_block}\n\n"
        f"Research focus: {topic}\n\n"
        f"Required output structure:\n{sections}\n\n"
        "Be specific to THIS venture and industry. Use real scenarios and actionable steps. "
        "Format with clear sections and bullet points."
    )


async def run_auto_research_pipeline(
    tag: str,
    session_data: dict | None,
    history: list | None,
    *,
    get_answer_for_tag: Callable[[list | None, str], str],
    conduct_web_search: Callable[..., Awaitable[str | None]],  # (query, *, research_kind, validation_feedback)
    generate_fallback: Callable[..., Awaitable[str]],
    is_valid_result: Callable[[str | None], bool],
    max_attempts: int = 2,
) -> tuple[str, bool]:
    """
    Search → validate relevance → retry with corrective feedback.
    Returns (appendix_text, success).
    """
    ctx = await build_auto_research_context(
        tag, session_data, history, get_answer_for_tag=get_answer_for_tag
    )
    if not ctx:
        return "", False

    query = build_research_query(ctx)
    context_block = format_auto_research_context_block(ctx)
    feedback = ""
    raw: str | None = None

    for attempt in range(max_attempts):
        search_query = query
        correction = feedback if attempt > 0 else ""
        print(f"🔍 Auto-research attempt {attempt + 1} for {tag}: {search_query[:200]}...")
        raw = await conduct_web_search(
            search_query,
            research_kind=ctx.research_kind,
            validation_feedback=correction,
            venture_context_block=context_block,
        )
        if not is_valid_result(raw):
            continue
        ok, feedback = validate_research_output(ctx, raw or "")
        if ok:
            return format_research_header(ctx) + (raw or "") + format_research_footer(ctx), True
        print(f"⚠️ Auto-research validation failed for {tag}: {feedback}")

    fallback = await generate_fallback(
        tag,
        ctx.business_name,
        ctx.industry,
        ctx.business_type,
        ctx.location,
        session_data,
        history,
    )
    if fallback:
        # Strip header/footer for validation — check body relevance when possible
        ok, _ = validate_research_output(ctx, fallback)
        if ok:
            return fallback, True
        print(f"⚠️ Fallback for {tag} also failed validation — serving anyway as last resort")
        return fallback, True
    return "", False
