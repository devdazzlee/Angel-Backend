from openai import AsyncOpenAI
import os
import re
from datetime import datetime
from utils.business_context import coerce_business_context, prompt_labels, clean_context_value

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _build_stage_6_insurance_row(insurance_detail: str = "") -> str:
    """Canonical insurance task row for Stage 6 — Public Launch."""
    detail = f" {insurance_detail.strip()}" if insurance_detail and insurance_detail.strip() else ""
    return (
        "| Obtain Business Insurance | "
        "Secure and activate required commercial insurance policies identified in the business plan "
        "(e.g., general liability, professional liability, property, workers compensation as applicable). "
        f"Confirm coverage is bound and certificates are on file before full public launch.{detail} | "
        "Legal formation complete; operations scope defined | "
        "Apply business-plan insurance recommendations; compare carriers; store certificates of insurance | "
        "🔜 |"
    )

async def generate_founderport_style_roadmap(session_data, history):
    """
    Generate a roadmap matching the exact Founderport structure with 8 stages:
    - Stage 1: Foundation & Setup
    - Stage 2: Financial Planning & Funding
    - Stage 3: Product Development
    - Stage 4: Marketing Readiness
    - Stage 5: Beta Launch & Feedback
    - Stage 6: Public Launch
    - Stage 7: Scaling & Expansion
    - Stage 8: Long-term Growth & Sustainability
    
    With specific task descriptions like "Form Your California C-Corporation (Founderport, Inc.)"
    """
    
    ctx = coerce_business_context(session_data)
    labels = prompt_labels(ctx)
    business_name = labels["business_name"]
    founder_name = clean_context_value(
        session_data.get("founder_name") or session_data.get("user_name")
    ) or "the founder"
    location = labels["location"]
    industry = labels["industry"]
    business_type = labels["business_type"]
    legal_structure = clean_context_value(
        session_data.get("business_structure") or session_data.get("legal_structure")
    ) or "the chosen legal structure"
    
    # Extract state from location if possible
    state = extract_state_from_location(location)
    
    # Extract all business plan answers for context
    # Handle both list of dicts and string formats
    if isinstance(history, str):
        # If history is a string (from smart_trim_history), extract user messages differently
        lines = history.split('\n')
        user_responses = [line.split(':', 1)[1].strip() for line in lines if line.startswith('USER:')]
        conversation_text = ' '.join(user_responses[-50:])  # Last 50 responses
    elif isinstance(history, list):
        # If history is a list of dicts (from fetch_chat_history)
        user_responses = [msg.get('content', '') for msg in history if isinstance(msg, dict) and msg.get('role') == 'user']
        conversation_text = ' '.join(user_responses[-50:])  # Last 50 responses
    else:
        conversation_text = ''
    
    # Generate roadmap using AI with Founderport structure
    roadmap_prompt = f"""
    Generate a comprehensive Launch Roadmap for "{business_name}" following the EXACT Founderport structure with 8 stages.
    
    **Business Context:**
    - Business Name: {business_name}
    - Founder: {founder_name}
    - Location: {location}
    - State: {state}
    - Legal Structure: {legal_structure}
    - Industry: {industry}
    - Business Type: {business_type}
    
    **User's Business Plan Answers:**
    {conversation_text[:3000]}
    
    Generate a roadmap with these 8 STAGES (not phases):
    
    ---
    
    ## **Founderport Launch Roadmap**
    *(Customized directly from the completed business plan inputs)*
    
    ### **Stage 1 — Foundation & Setup**
    **Goal**: Establish the legal, technical, and operational base for {business_name}.
    
    | Task | Description | Dependencies | Angel's Role | Status |
    |------|-------------|--------------|--------------|--------|
    | 1.1 Incorporate {business_name} | Register as a {state} {legal_structure}. File Articles of Incorporation/Organization. | None | Provide filing links, draft description text | ⏳ |
    | 1.2 File Trademarks for {business_name} | Protect branding before public marketing. USPTO filing. | Legal counsel | Provide USPTO filing links, draft description | ⏳ |
    | 1.3 Create IP & Copyright Plan | Secure intellectual property and written assets. | Formation complete | Schedule copyright filing reminder | ⏳ |
    | 1.4 Confirm Development Infrastructure | Set up cloud hosting, database, and core tech stack. | None | Generate config checklist | ⏳ |
    | 1.5 Implement NDA & Contract Controls | Ensure contracts and IP clauses are in place. | Legal setup | Store executed agreements securely | ⏳ |
    
    ### **Stage 2 — Financial Planning & Funding**
    **Goal**: Establish financial systems and secure necessary funding for {business_name}.
    
    | Task | Description | Dependencies | Angel's Role | Status |
    |------|-------------|--------------|--------------|--------|
    | 2.1 Open Business Bank Account | Set up separate business banking for {business_name}. | Legal formation complete | Provide bank comparison, account setup checklist | ⏳ |
    | 2.2 Set Up Accounting System | Implement accounting software and financial tracking. | Bank account open | Generate accounting setup guide, chart of accounts | ⏳ |
    | 2.3 Create Financial Projections | Develop budget, cash flow, and revenue forecasts. | Business plan complete | Generate financial model templates | ⏳ |
    | 2.4 Secure Initial Funding | Execute funding strategy (investors, loans, grants, or bootstrapping). | Financial projections ready | Draft pitch deck, funding source research | ⏳ |
    | 2.5 Establish Tax Planning | Set up tax structure and quarterly payment system. | Accounting system live | Provide tax planning checklist, estimated tax calculator | ⏳ |
    
    ### **Stage 3 — Product Development**
    **Goal**: Deliver the first functional version of your product/service.
    
    | Task | Description | Dependencies | Angel's Role | Status |
    |------|-------------|--------------|--------------|--------|
    | 3.1 Develop Core Product/Service | Build MVP or beta version of your offering. | Technical requirements defined | Generate specs & workflow map | ⏳ |
    | 3.2 Integrate Key Features | Add essential features and functionality. | Core build complete | Provide feature checklist | ⏳ |
    | 3.3 Test Product Functionality | Conduct thorough testing and quality assurance. | Feature integration done | Generate test scripts | ⏳ |
    | 3.4 Internal QA & Refinement | Team testing and bug fixes. | Product functional | Monitor feedback, prioritize fixes | ⏳ |
    | 3.5 Prepare Beta Launch | Recruit beta testers and prepare onboarding. | QA complete | Generate onboarding script, feedback template | 🔜 |
    
    ### **Stage 4 — Marketing Readiness**
    **Goal**: Drive awareness and generate early interest.
    
    | Task | Description | Dependencies | Angel's Role | Status |
    |------|-------------|--------------|--------------|--------|
    | 4.1 Establish Landing Page | Build website with clear value prop and CTA. | Brand assets ready | Draft copy, CTA text, visuals | ⏳ |
    | 4.2 Launch Marketing Campaign | Start ads in key markets (adjust for your business). | Landing page live | Suggest ad keywords, headlines | 🔜 |
    | 4.3 Short-Form Video Content | Create explainer videos for social media. | Brand complete | Generate scripts, posting calendar | 🔜 |
    | 4.4 Partnership Outreach | Contact potential partners in your industry. | Pitch materials ready | Draft outreach emails, partnership proposals | ⏳ |
    
    ### **Stage 5 — Beta Launch & Feedback**
    **Goal**: Validate product-market fit and refine based on real user feedback.
    
    | Task | Description | Dependencies | Angel's Role | Status |
    |------|-------------|--------------|--------------|--------|
    | 5.1 Launch Beta Program | Deploy to test users, collect structured feedback. | Product ready | Track sessions & sentiment | 🔜 |
    | 5.2 Analyze Beta Data | Identify friction points and most-used features. | Feedback collected | Generate insights & recommendations | 🔜 |
    | 5.3 Implement Refinements | Fix bugs, adjust UX, add missing features. | Analysis complete | Prioritize fixes, assign to team | 🔜 |
    | 5.4 Prepare Marketing Assets | Create success stories and testimonials. | Positive results | Draft case studies, testimonials | 🔜 |
    
    ### **Stage 6 — Public Launch**
    **Goal**: Release to market and begin revenue generation.
    
    | Task | Description | Dependencies | Angel's Role | Status |
    |------|-------------|--------------|--------------|--------|
    | 6.1 Obtain Business Insurance | Secure and activate required commercial insurance (general liability, professional liability, property, workers compensation as applicable). Bind coverage and store certificates before full public launch. Use policies identified in the business plan (Q27). | Legal formation complete; operations scope defined | Compare carriers; confirm coverage limits; file certificates | 🔜 |
    | 6.2 Launch Publicly | Make product/service available to general public. | Beta approved; business insurance active | Manage launch communications | 🔜 |
    | 6.3 Activate Marketing Campaigns | Full marketing push across all channels. | Site live | Monitor conversions, optimize campaigns | 🔜 |
    | 6.4 Build Customer Pipeline | Set up sales processes and customer onboarding. | Marketing active | Create sales templates, onboarding flows | 🔜 |
    | 6.5 Track KPIs | Monitor CAC, LTV, churn, retention, revenue. | Launch active | Build dashboard templates | 🔜 |
    
    ### **Stage 7 — Scaling & Expansion**
    **Goal**: Grow the business and expand offerings.
    
    | Task | Description | Dependencies | Angel's Role | Status |
    |------|-------------|--------------|--------------|--------|
    | 7.1 Expand Product Line | Add new features, products, or services. | Stable core product | Research market needs, feature prioritization | 🔜 |
    | 7.2 Scale Operations | Hire team, increase capacity, optimize processes. | Revenue growth | Provide hiring templates, org charts | 🔜 |
    | 7.3 Enter New Markets | Geographic or demographic expansion. | Product-market fit | Localize content, research new markets | 🔜 |
    | 7.4 Build Strategic Partnerships | Form alliances to accelerate growth. | Market presence | Draft partnership proposals | 🔜 |
    
    ### **Stage 8 — Long-term Growth & Sustainability**
    **Goal**: Ensure sustainable growth and long-term success for {business_name}.
    
    | Task | Description | Dependencies | Angel's Role | Status |
    |------|-------------|--------------|--------------|--------|
    | 8.1 Optimize Operations | Streamline processes, reduce costs, improve efficiency. | Stable operations | Generate process optimization checklist | 🔜 |
    | 8.2 Build Company Culture | Establish values, team culture, and employee retention strategies. | Team growing | Draft culture document, retention strategies | 🔜 |
    | 8.3 Plan for Future Funding | Prepare for Series A/B or additional growth capital. | Revenue milestones met | Generate investor pitch materials | 🔜 |
    | 8.4 Establish Exit Strategy | Plan for acquisition, IPO, or long-term ownership. | Business mature | Provide exit strategy framework | 🔜 |
    
    ---
    
    CRITICAL REQUIREMENTS:
    1. Use "Stage" not "Phase" (Stage 1, Stage 2, etc.)
    2. Make task descriptions SPECIFIC to {business_name}, not generic
    3. Include {location} and {state} in relevant tasks (e.g., "Form Your {state} {legal_structure} ({business_name}, Inc.)")
    4. Use actual business name in task descriptions
    5. Tailor Stage 3 tasks based on whether it's SaaS/Tech, Service, or Product business
    6. Use markdown tables with columns: Task | Description | Dependencies | Angel's Role | Status
    7. Status indicators: ✅ (complete), ⏳ (in progress), 🔜 (upcoming)
    8. Make it look EXACTLY like the Founderport roadmap example
    9. **MANDATORY — Stage 6 (Public Launch)**: MUST include task "Obtain Business Insurance" before "Launch Publicly". Use insurance policies from the business plan (Question 27 / legal & compliance section). Do not omit insurance from the roadmap.
    
    Generate the complete roadmap now with all 8 stages and specific tasks for {business_name}.
    """
    
    insurance_detail = extract_insurance_context_from_history(history, session_data)

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": roadmap_prompt}],
            temperature=0.3,
            max_tokens=4500  # Increased for comprehensive 8-stage roadmap
        )
        roadmap_content = response.choices[0].message.content or ""
        return ensure_public_launch_insurance_task(roadmap_content, insurance_detail)
    except Exception as e:
        print(f"Error generating Founderport-style roadmap: {e}")
        # Fallback to basic structure
        fallback = generate_fallback_roadmap(business_name, founder_name, location, legal_structure, state)
        return ensure_public_launch_insurance_task(fallback, insurance_detail)

def extract_insurance_context_from_history(history, session_data=None) -> str:
    """
    Pull insurance recommendations from Business Plan Q27 discussion so Stage 6
    can reference specific policy types the founder already identified.
    """
    snippets: list[str] = []

    if isinstance(history, list):
        for msg in history:
            if not isinstance(msg, dict):
                continue
            content = (msg.get("content") or "").strip()
            if len(content) < 40:
                continue
            lower = content.lower()
            if "insurance" not in lower:
                continue
            if any(
                kw in lower
                for kw in (
                    "liability",
                    "policy",
                    "policies",
                    "coverage",
                    "workers comp",
                    "property insurance",
                    "professional liability",
                    "general liability",
                )
            ):
                snippets.append(content[:600])

    if isinstance(history, str):
        for line in history.splitlines():
            lower = line.lower()
            if "insurance" in lower and (
                "liability" in lower or "policy" in lower or "coverage" in lower
            ):
                snippets.append(line[:400])

    if session_data and isinstance(session_data.get("business_context"), dict):
        ctx = session_data["business_context"]
        for key in ("insurance_policies", "insurance_summary", "insurance"):
            val = ctx.get(key)
            if isinstance(val, str) and val.strip():
                snippets.append(val.strip()[:400])

    if not snippets:
        return ""

    combined = " ".join(snippets[-2:])
    combined = re.sub(r"\s+", " ", combined).strip()
    if len(combined) > 220:
        combined = combined[:217].rstrip() + "..."
    return f"Policies to confirm: {combined}"


def ensure_public_launch_insurance_task(roadmap_content: str, insurance_detail: str = "") -> str:
    """
    Guarantee Stage 6 — Public Launch includes a business insurance task.
    The LLM occasionally omits it; this enforces the product requirement at the source.
    """
    if not roadmap_content or not roadmap_content.strip():
        return roadmap_content

    stage6_match = re.search(
        r"(###\s*\*\*Stage\s*6\s*[—–-]\s*Public\s*Launch\*\*.*?)"
        r"(?=###\s*\*\*Stage\s*7|\Z)",
        roadmap_content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not stage6_match:
        return roadmap_content

    stage6_block = stage6_match.group(1)
    if re.search(r"insurance", stage6_block, re.IGNORECASE):
        return roadmap_content

    row = _build_stage_6_insurance_row(insurance_detail)

    table_header = re.search(
        r"(\| Task \| Description \| Dependencies \| Angel's Role \| Status \|\n\|[-\s|:]+\|\n)",
        stage6_block,
        flags=re.IGNORECASE,
    )
    if not table_header:
        return roadmap_content

    insert_at = stage6_match.start(1) + table_header.end()
    return roadmap_content[:insert_at] + row + "\n" + roadmap_content[insert_at:]


def extract_state_from_location(location):
    """Extract state from location string"""
    # Common US states
    states = {
        'california': 'California', 'ca': 'California',
        'new york': 'New York', 'ny': 'New York',
        'texas': 'Texas', 'tx': 'Texas',
        'florida': 'Florida', 'fl': 'Florida',
        'illinois': 'Illinois', 'il': 'Illinois',
        'pennsylvania': 'Pennsylvania', 'pa': 'Pennsylvania',
        'ohio': 'Ohio', 'washington': 'Washington', 'wa': 'Washington'
    }
    
    location_lower = location.lower()
    for key, value in states.items():
        if key in location_lower:
            return value
    
    # If location contains comma, assume format is "City, State"
    if ',' in location:
        parts = location.split(',')
        if len(parts) >= 2:
            state_part = parts[-1].strip()
            # Check if it's a known state
            for key, value in states.items():
                if key == state_part.lower():
                    return value
            return state_part  # Return as-is
    
    return location  # Return full location if can't extract state

def generate_fallback_roadmap(business_name, founder_name, location, legal_structure, state):
    """Generate basic roadmap structure as fallback"""
    return f"""
# {business_name} Launch Roadmap

**Founder:** {founder_name}
**Location:** {location}
**Legal Structure:** {legal_structure}

## Stage 1 — Foundation & Setup

| Task | Description | Dependencies | Angel's Role | Status |
|------|-------------|--------------|--------------|--------|
| 1.1 Form Your {state} {legal_structure} | Legally establish {business_name} with state authorities. | None | Provide filing guidance | ⏳ |
| 1.2 File Trademarks | Protect your brand name and logo. | Legal formation | USPTO filing assistance | ⏳ |
| 1.3 Set Up Infrastructure | Establish core business systems and processes. | None | System setup checklist | ⏳ |

## Stage 2 — Financial Planning & Funding
[Additional stages will be generated based on your business plan responses]

## Stage 3 — Product Development
[Additional stages will be generated based on your business plan responses]

## Stage 6 — Public Launch

| Task | Description | Dependencies | Angel's Role | Status |
|------|-------------|--------------|--------------|--------|
| Obtain Business Insurance | Secure required commercial insurance before full public launch. | Legal formation complete | Compare carriers; confirm coverage | ⏳ |
| Launch Publicly | Release to the general public. | Insurance active | Launch communications | 🔜 |

**Note:** Your complete roadmap is being generated with full details for all 8 stages.
"""

async def generate_task_with_service_providers(task_name, business_name, location, industry, founder_name=None):
    """Generate a detailed task page with service provider options like the Founderport example"""
    
    # Extract state
    state = extract_state_from_location(location)
    if founder_name is None:
        founder_name = 'Founder'
    
    task_prompt = f"""
    Generate a detailed task page for: "{task_name}" for {business_name} located in {location}.
    
    Follow this EXACT structure from the Founderport example:
    
    ## Task: [Specific Task Name with Business Name]
    
    🎯 **Objective**
    [2-3 sentences explaining what this task accomplishes and why it's important for {business_name}]
    
    🧾 **Step 1 – Gather Your Required Information**
    You'll need:
    • [List 4-6 specific items needed]
    • [Include actual business name: {business_name}]
    • [Include location specifics: {location}, {state}]
    
    🧩 **Ways to Complete This Task**
    
    **Option 1 – Do-It-Yourself (Direct)**
    • [Detailed steps for DIY approach]
    • [Include specific websites, portals, timelines]
    • [Mention costs and processing times]
    
    **Option 2 – Third-Party Service Provider (Assisted)**
    Use a provider that handles the work for you:
    
    | Service Provider | Cost | What They Do | Notes |
    |------------------|------|--------------|-------|
    | [Provider 1] | $[amount] | [Service description] | [Recommendation] |
    | [Provider 2] | $[amount] | [Service description] | [Recommendation] |
    | [Provider 3] | $[amount] | [Service description] | [Recommendation] |
    | Local Option: {location} [Service] | $[amount] | [Local service] | Fast, personalized support |
    
    ⚙️ **Available Angel Commands for This Task**
    
    | Command | What It Does | Example Use |
    |---------|--------------|-------------|
    | **Kickstart** | Angel prepares documents, forms, or templates for you. | "Kickstart this step." |
    | **Help** | Explains details and guides you through the process. | "What does [term] mean?" |
    | **Who Do I Contact?** | Provides vetted local service providers with ratings. | "Who handles this near me?" |
    | **Advice & Tips** | Shares best practices and insider knowledge. | "Any tips before filing?" |
    
    💡 **Angel's Advice**
    "{founder_name}, at this stage, [personalized advice specific to this task and their situation in {location}]. 
    
    [2-3 sentences of strategic guidance tailored to their industry and location]
    
    After completing this, [what they'll need next or what documents they'll receive]."
    
    **Would you like to:**
    1️⃣ Kickstart the [task process]
    2️⃣ See recommended service providers
    3️⃣ Ask for Help and learn more details first
    
    ---
    
    REQUIREMENTS:
    - Use {business_name} in task titles and descriptions
    - Include {location} and {state} specifics
    - Provide 3-4 service provider options with costs
    - Include a local option for {location}
    - Make Angel's advice personal to {founder_name}
    - Tailor to {industry} industry specifics
    - Be as detailed as the Founderport example
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": task_prompt}],
            temperature=0.4,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating task details: {e}")
        return f"## Task: {task_name}\n\nDetailed information for this task is being generated..."

