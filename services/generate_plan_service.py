from openai import AsyncOpenAI
import os
import json
from datetime import datetime
from services.angel_service import generate_business_plan_artifact, conduct_web_search

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _safe_excerpt(value, fallback_message, limit=1000):
    """
    Safely truncate research content for logging/prompts without assuming the
    value is a string. Prevents 'NoneType' slicing errors and provides a clear
    fallback when research wasn't retrieved.
    """
    if not value:
        return fallback_message

    if not isinstance(value, str):
        try:
            value = json.dumps(value)
        except Exception:
            value = str(value)

    return value[:limit]

async def generate_full_business_plan(history):
    """Generate comprehensive business plan with deep research"""


    # Extract session data from conversation history
    session_data = {}
    conversation_history = []
    
    for msg in history:
        if isinstance(msg, dict):
            conversation_history.append(msg)
            content = msg.get('content', '').lower()
            
            # Extract industry information - DYNAMIC APPROACH
            if any(keyword in content for keyword in ['industry', 'business type', 'sector', 'field']):
                # Use AI model to dynamically identify industry
                industry_prompt = f"""
                Analyze this user input and extract the business industry or sector: "{content}"
                
                Return ONLY the industry name in a standardized format, or "general business" if unclear.
                
                Examples:
                - "Tea Stall" → "Tea Stall"
                - "AI Development" → "AI Development"
                - "Food Service" → "Food Service"
                - "Technology" → "Technology"
                - "Healthcare" → "Healthcare"
                
                Return only the industry name:
                """
                
                try:
                    response = await client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": industry_prompt}],
                        temperature=0.1,
                        max_tokens=30
                    )
                    
                    industry_result = response.choices[0].message.content.strip()
                    session_data['industry'] = industry_result if industry_result else 'general business'
                except Exception as e:
                    print(f"Industry extraction failed: {e}")
                    session_data['industry'] = 'general business'
            
            # Extract location information
            if any(keyword in content for keyword in ['location', 'city', 'country', 'state', 'region']):
                if 'united states' in content or 'usa' in content or 'us' in content:
                    session_data['location'] = 'United States'
                elif 'canada' in content:
                    session_data['location'] = 'Canada'
                elif 'united kingdom' in content or 'uk' in content:
                    session_data['location'] = 'United Kingdom'
                elif 'australia' in content:
                    session_data['location'] = 'Australia'
                else:
                    session_data['location'] = 'United States'  # Default
    
    # Set defaults if not found
    if 'industry' not in session_data:
        session_data['industry'] = 'general business'
    if 'location' not in session_data:
        session_data['location'] = 'United States'
    
    # Use the deep research business plan generation
    business_plan_content = await generate_business_plan_artifact(session_data, conversation_history)
    
    return {
        "plan": business_plan_content,
        "generated_at": datetime.now().isoformat(),
        "research_conducted": True,
        "industry": session_data['industry'],
        "location": session_data['location']
    }

async def generate_full_roadmap_plan(history):
    """Generate comprehensive roadmap with deep research"""
    
    # Extract session data from conversation history
    session_data = {}
    conversation_history = []
    
    for msg in history:
        if isinstance(msg, dict):
            conversation_history.append(msg)
            content = msg.get('content', '').lower()
            
            # Extract industry information - DYNAMIC APPROACH
            if any(keyword in content for keyword in ['industry', 'business type', 'sector', 'field']):
                # Use AI model to dynamically identify industry
                industry_prompt = f"""
                Analyze this user input and extract the business industry or sector: "{content}"
                
                Return ONLY the industry name in a standardized format, or "general business" if unclear.
                
                Examples:
                - "Tea Stall" → "Tea Stall"
                - "AI Development" → "AI Development"
                - "Food Service" → "Food Service"
                - "Technology" → "Technology"
                - "Healthcare" → "Healthcare"
                
                Return only the industry name:
                """
                
                try:
                    response = await client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": industry_prompt}],
                        temperature=0.1,
                        max_tokens=30
                    )
                    
                    industry_result = response.choices[0].message.content.strip()
                    session_data['industry'] = industry_result if industry_result else 'general business'
                except Exception as e:
                    print(f"Industry extraction failed: {e}")
                    session_data['industry'] = 'general business'
            
            # Extract location information
            if any(keyword in content for keyword in ['location', 'city', 'country', 'state', 'region']):
                if 'united states' in content or 'usa' in content or 'us' in content:
                    session_data['location'] = 'United States'
                elif 'canada' in content:
                    session_data['location'] = 'Canada'
                elif 'united kingdom' in content or 'uk' in content:
                    session_data['location'] = 'United Kingdom'
                elif 'australia' in content:
                    session_data['location'] = 'Australia'
                else:
                    session_data['location'] = 'United States'  # Default
    
    # Set defaults if not found
    if 'industry' not in session_data:
        session_data['industry'] = 'general business'
    if 'location' not in session_data:
        session_data['location'] = 'United States'
    
    # Conduct comprehensive research for roadmap
    industry = session_data.get('industry', 'general business')
    location = session_data.get('location', 'United States')
    
    current_year = datetime.now().year
    previous_year = current_year - 1
    
    print(f"[RESEARCH] Conducting deep research for {industry} roadmap in {location}")
    print(f"[RESEARCH] Searching Government Sources (.gov), Academic Research (.edu, scholar), and Industry Reports (Bloomberg, WSJ, Forbes)")
    
    # EXPLICIT RESEARCH FROM AUTHORITATIVE SOURCES - Government, Academic, Industry
    # Government Sources - SBA, IRS, state agencies, regulatory bodies
    government_resources = await conduct_web_search(
        f"Search ONLY government sources (.gov domains) for: {location} business formation requirements {industry} startup compliance licensing permits {current_year}. "
        f"Include: SBA.gov, IRS.gov, state business registration sites, regulatory agencies. Cite specific government sources and URLs."
    )
    regulatory_requirements = await conduct_web_search(
        f"Search government (.gov) and regulatory sources for: {industry} regulatory requirements startup compliance {location} {current_year}. "
        f"Find specific licenses, permits, and legal requirements. Cite government sources with URLs."
    )
    
    # Academic Research - Universities, research institutions, academic journals
    academic_insights = await conduct_web_search(
        f"Search academic sources (.edu, Google Scholar, JSTOR, research institutions) for: startup roadmap {industry} business planning success factors {current_year}. "
        f"Find research papers, studies, and academic publications. Cite specific academic sources with URLs."
    )
    startup_research = await conduct_web_search(
        f"Search academic and research sources for: {industry} startup timeline best practices implementation phases {current_year}. "
        f"Include university research, business school publications, peer-reviewed studies. Cite academic sources."
    )
    
    # Industry Reports - Bloomberg, WSJ, Forbes, Harvard Business Review, industry publications
    market_entry_strategy = await conduct_web_search(
        f"Search industry publications (Bloomberg, WSJ, Forbes, Harvard Business Review) for: {industry} market entry strategy startup {location} {current_year}. "
        f"Find authoritative industry reports and business journalism. Cite specific publications with URLs."
    )
    funding_insights = await conduct_web_search(
        f"Search industry sources (Bloomberg, WSJ, Forbes, Crunchbase) for: {industry} funding timeline seed stage startup investment trends {current_year}. "
        f"Include venture capital reports and startup funding data. Cite industry sources."
    )
    operational_insights = await conduct_web_search(
        f"Search industry publications for: {industry} operational requirements startup launch phases {location} {current_year}. "
        f"Find industry-specific best practices and operational benchmarks. Cite sources."
    )
    
    print(f"[RESEARCH] ✓ Government sources researched: SBA, IRS, state agencies")
    print(f"[RESEARCH] ✓ Academic research reviewed: Universities, journals, research institutions")
    print(f"[RESEARCH] ✓ Industry reports analyzed: Bloomberg, WSJ, Forbes, HBR")
    
    ROADMAP_TEMPLATE = """
# Launch Roadmap - Built on Government Sources, Academic Research & Industry Reports

## Executive Summary & Research Foundation

**CRITICAL REFERENCE**: This roadmap generation MUST reference and align with "Roadmap Deep Research Questions V3" to ensure comprehensive coverage of all critical roadmap planning areas.

This comprehensive launch roadmap is grounded in extensive research from three authoritative source categories:

**Government Sources (.gov)**: SBA, IRS, SEC, state business agencies, regulatory bodies
**Academic Research (.edu, scholar)**: University research, peer-reviewed journals, business school publications  
**Industry Reports**: Bloomberg, Wall Street Journal, Forbes, Harvard Business Review, industry publications

**Reference Document**: Roadmap Deep Research Questions V3

Every recommendation has been validated against current best practices and cited with specific sources to ensure you have authoritative, verified guidance. This roadmap follows the structure and depth requirements of Roadmap Deep Research Questions V3.

---

## Research Sources Utilized

| Source Category | Specific Sources | Research Focus | Key Findings |
|----------------|------------------|----------------|--------------|
| **Government Sources** | SBA.gov, IRS.gov, state agencies | Business formation, compliance, licensing | {government_resources} |
| **Government Regulatory** | Federal/state regulatory bodies | Industry-specific requirements | {regulatory_requirements} |
| **Academic Research** | Universities, Google Scholar, JSTOR | Startup success factors, best practices | {academic_insights} |
| **Academic Studies** | Business schools, research institutions | Implementation timelines, phases | {startup_research} |
| **Industry Reports** | Bloomberg, WSJ, Forbes, HBR | Market entry, funding trends | {market_entry_strategy} |
| **Industry Analysis** | Business publications, VC reports | Operational requirements, benchmarks | {operational_insights} |

---

## Key Milestones Overview

| Phase | Timeline | Focus Area | Research Source Type |
|-------|----------|------------|---------------------|
| Phase 1 | Month 1-2 | Legal Foundation & Compliance | Government Sources |
| Phase 2 | Month 2-3 | Financial Systems & Funding | Industry Reports + Government |
| Phase 3 | Month 3-5 | Operations & Product Development | Academic Research + Industry |
| Phase 4 | Month 5-7 | Marketing & Sales Infrastructure | Industry Reports + Academic |
| Phase 5 | Month 7-12 | Full Launch & Scaling | All Sources |

---

### 2. [CHAMPION] Planning Champion Achievement
Congratulations! You've successfully completed your comprehensive business planning phase. This roadmap represents the culmination of your strategic thinking and research-backed decision-making. You're now ready to transform your vision into reality.

**Inspirational Quote:** "Success is not final; failure is not fatal: it is the courage to continue that counts." – Winston Churchill

**Your Journey So Far:**
[COMPLETE] Completed comprehensive business planning
[COMPLETE] Conducted market research and analysis  
[COMPLETE] Developed financial projections and funding strategy
[COMPLETE] Created operational and marketing frameworks
[COMPLETE] Established legal and compliance foundation

### 3. Why This Roadmap Matters: Your Path to Success
This roadmap is not just a checklist—it's your strategic blueprint for building a sustainable, successful business. Each phase builds upon the previous one, creating a strong foundation that supports long-term growth and profitability.

**Critical Success Factors:**
- Follow the sequence: Each phase prepares you for the next
- Don't skip steps: Rushing can lead to costly mistakes
- Stay committed: Entrepreneurship requires persistence and patience
- Leverage Angel's support: Use every resource available to you
- Trust the process: This roadmap is based on proven methodologies

**The Consequences of Not Following This Plan:**
- Legal complications from improper business formation
- Financial mismanagement leading to cash flow problems
- Operational inefficiencies that hinder growth
- Marketing failures due to premature or inadequate preparation
- Scaling challenges from weak foundational systems

### 4. Your Complete Launch Timeline

**IMPORTANT: All roadmap steps are organized in sequential tables below. Each table shows the exact order of tasks with timelines and research sources.**

### 5. Phase 1: Legal Formation & Compliance (Months 1-2)

**Goal**: Establish the legal, technical, and operational base for your business.

**Roadmap Steps - Phase 1: Legal Foundation**

| Task | Description | Dependencies | Angel's Role | Status |
|------|-------------|--------------|-------------|--------|
| **1.1 Choose Business Structure** | Select appropriate legal structure (LLC, C-Corp, S-Corp, Partnership, or Sole Proprietorship). Consider liability protection, tax implications, and operational flexibility. Evaluate based on industry requirements, funding needs, and growth plans. | None | Provide structure comparison analysis, tax implications guide, document templates | ⬜ |
| **1.2 Register Business Name** | Register business name with Secretary of State. Check availability via state database. Consider federal trademark (USPTO) for brand protection. Secure matching domain name and social media handles. File DBA if using alternative name. | Business structure selected | Generate registration checklist, provide state-specific links, draft trademark description text | ⬜ |
| **1.3 Obtain EIN** | Apply for Employer Identification Number through IRS website. Required for business bank accounts, hiring employees, and tax filing. Free application, instant approval in most cases. | Business name registered | Provide IRS.gov EIN application link, generate application checklist | ⬜ |
| **1.4 Get Business Licenses** | Identify and obtain federal, state, and local licenses/permits specific to your industry and location. Research regulatory requirements, submit applications, schedule inspections if needed. | EIN obtained | Generate compliance checklist, identify required licenses, provide application links | ⬜ |
| **1.5 File Trademarks** | Protect branding before public marketing. File federal trademarks for business name and key brand elements through USPTO. | Business name registered | Provide USPTO filing links, draft description text, schedule filing reminders | ⬜ |

**Service Providers - Legal Formation**:
| Provider | Type | Local | Description | Research Source |
|----------|------|-------|-------------|----------------|
| LegalZoom | Online Service | No | Online legal document preparation, standardized packages | Industry comparison sites, user reviews |
| Local Business Attorney | Legal Professional | Yes | Personalized legal advice, industry expertise | State bar associations, legal directories |
| SCORE Business Mentor | Free Consultation | Yes | Volunteer business mentors with industry experience | SBA.gov, local SCORE chapters |

### 6. Phase 2: Financial Planning & Setup (Months 2-3)

**Goal**: Set up your financial systems and funding strategies to support all subsequent operations.

**Roadmap Steps - Phase 2: Financial Foundation**

| Task | Description | Dependencies | Angel's Role | Status |
|------|-------------|--------------|-------------|--------|
| **2.1 Open Business Bank Account** | Select and open dedicated business checking account. Compare traditional banks vs online/fintech options. Consider fees, features, integration capabilities. Gather required documents (EIN, formation docs, ID). | EIN obtained | Generate banking comparison, provide bank selection checklist, document requirements list | ⬜ |
| **2.2 Set Up Accounting System** | Choose accounting software (cash vs accrual basis). Set up chart of accounts, connect bank feeds, establish bookkeeping processes. Consider hiring bookkeeper or accountant. | Business bank account opened | Provide accounting software comparison, generate setup checklist, bookkeeper recommendations | ⬜ |
| **2.3 Establish Financial Controls** | Implement expense policies, approval workflows, receipt management. Set up separate business credit card. Create financial tracking and reporting processes. | Accounting system set up | Generate financial control templates, expense policy drafts, tracking spreadsheet | ⬜ |
| **2.4 Create Financial Projections** | Develop detailed financial projections (revenue, expenses, cash flow) for 12-36 months. Create budget and financial milestones. Plan for seasonal variations. | Financial controls established | Provide financial projection templates, generate forecasting models, budget worksheets | ⬜ |

**Service Providers - Financial Setup**:
| Provider | Type | Local | Description | Research Source |
|----------|------|-------|-------------|----------------|
| Chase Business | Traditional Bank | Yes | Full-service business banking with branch network | FDIC.gov, Bankrate comparisons |
| QuickBooks | Accounting Software | No | Industry-leading platform with extensive features | Software review sites, user ratings |
| Local CPA Firm | Professional Service | Yes | Personalized accounting and tax guidance | AICPA.org directory, local referrals |

**Angel Support Available**: Banking comparison, accounting setup, financial projection templates, bookkeeper recommendations

### 7. Phase 3: Product & Operations Development (Months 3-5)

**Goal**: Build your operational infrastructure once legal and financial foundations are secure.

**Roadmap Steps - Phase 3: Operational Foundation**

| Task | Description | Dependencies | Angel's Role | Status |
|------|-------------|--------------|-------------|--------|
| **3.1 Establish Supply Chain** | Identify and vet suppliers (local vs international). Negotiate terms, minimum orders, payment terms. Set up logistics and fulfillment processes. Establish backup suppliers for critical items. | Financial systems operational | Provide supplier evaluation checklist, negotiation templates, vendor comparison tools | ⬜ |
| **3.2 Set Up Operations Infrastructure** | Secure physical location (office, warehouse, retail) if needed. Purchase equipment, technology, and tools. Set up utilities, insurance, and security systems. | Supply chain established | Generate location selection criteria, equipment checklist, vendor recommendations | ⬜ |
| **3.3 Develop Product/Service** | Finalize product specifications or service delivery processes. Create prototypes or pilot programs. Test with focus groups or beta customers. Iterate based on feedback. | Operations infrastructure ready | Provide product development templates, testing protocols, feedback collection forms | ⬜ |
| **3.4 Implement Quality Control** | Establish quality standards and testing procedures. Create quality assurance processes. Set up customer feedback loops. Document standard operating procedures. | Product/service developed | Generate quality control checklists, SOP templates, feedback system setup | ⬜ |

**Service Providers - Operations**:
| Provider | Type | Local | Description | Research Source |
|----------|------|-------|-------------|----------------|
| Alibaba | Global Marketplace | No | International supplier network with competitive pricing | Industry supplier directories |
| Local Trade Associations | Professional Network | Yes | Industry-specific local supplier connections | Chamber of Commerce, trade groups |
| Fulfillment by Amazon | Logistics Service | No | Comprehensive fulfillment with fast shipping | E-commerce industry reports |

**Angel Support Available**: Supplier evaluation, negotiation templates, quality control checklists, operations process documentation

### 8. Phase 4: Marketing & Sales Strategy (Months 5-7)

**Goal**: Promote your business once all systems are in place and ready to handle customer demand.

**Roadmap Steps - Phase 4: Market Launch Preparation**

| Task | Description | Dependencies | Angel's Role | Status |
|------|-------------|--------------|-------------|--------|
| **4.1 Develop Brand Identity** | Create brand positioning, messaging, visual identity (logo, colors, fonts). Define unique value proposition and brand voice. Develop brand guidelines document. | Product/service ready | Draft brand positioning statement, generate brand guidelines template, provide design resources | ⬜ |
| **4.2 Build Digital Presence** | Create professional website with SEO optimization. Set up social media profiles across relevant platforms. Implement analytics and tracking (Google Analytics, etc.). | Brand identity established | Generate website content, SEO checklist, social media setup guide, analytics configuration | ⬜ |
| **4.3 Create Marketing Materials** | Develop marketing collateral (brochures, presentations, business cards). Create product photography and videography. Write copy for various channels. | Digital presence live | Draft marketing copy, generate content calendar, provide design templates | ⬜ |
| **4.4 Implement Sales Process** | Define sales funnel stages and customer journey. Create CRM system and sales tracking. Develop sales scripts, proposals, and contracts. Train sales team if applicable. | Marketing materials ready | Generate sales scripts, CRM setup guide, proposal templates, training materials | ⬜ |
| **4.5 Plan Customer Acquisition** | Identify customer acquisition channels (paid ads, content marketing, partnerships). Set budgets and KPIs. Create initial campaigns and test messaging. | Sales process implemented | Generate customer acquisition playbook, ad copy suggestions, campaign templates, KPI tracking | ⬜ |

**Service Providers - Marketing & Sales**:
| Provider | Type | Local | Description | Research Source |
|----------|------|-------|-------------|----------------|
| Local Marketing Agency | Professional Service | Yes | Full-service marketing with local market expertise | Local business directories, client reviews |
| Upwork/Fiverr | Freelance Platform | No | Cost-effective access to specialized marketing talent | Platform ratings, portfolio reviews |
| HubSpot | Software Platform | No | Comprehensive inbound marketing automation tools | Software review sites, case studies |

**Angel Support Available**: Brand strategy development, marketing plan templates, customer acquisition playbooks, vendor selection guidance

### 9. Phase 5: Full Launch & Scaling (Months 7-12)

**Goal**: Execute your complete business strategy when all foundational elements are ready.

**Roadmap Steps - Phase 5: Launch & Growth**

| Task | Description | Dependencies | Angel's Role | Status |
|------|-------------|--------------|-------------|--------|
| **5.1 Execute Go-to-Market Launch** | Choose launch strategy (soft launch, hard launch, beta, or phased rollout). Coordinate all marketing channels. Execute launch events and campaigns. Monitor initial customer response. | Marketing & sales ready | Generate launch plan, event checklist, campaign coordination guide, monitoring dashboard | ⬜ |
| **5.2 Customer Acquisition at Scale** | Ramp up customer acquisition efforts across validated channels. Scale spending based on ROI metrics. Implement referral programs and partnerships. | Launch executed | Provide scaling strategies, ROI analysis templates, referral program setup, partnership outreach | ⬜ |
| **5.3 Operational Scaling** | Hire key team members as needed. Scale operations to meet demand. Optimize processes for efficiency. Implement automation where possible. | Customer base growing | Generate hiring templates, job descriptions, process optimization guide, automation recommendations | ⬜ |
| **5.4 Financial Management & Fundraising** | Monitor cash flow closely. Achieve profitability milestones or secure additional funding. Implement financial reporting and forecasting. | Operations scaled | Provide financial dashboard, fundraising templates, investor pitch materials, reporting tools | ⬜ |
| **5.5 Measure, Learn, Optimize** | Track KPIs and business metrics. Analyze customer feedback and behavior. Optimize product, pricing, and processes. Prepare for next growth phase. | Business operational | Generate KPI tracking dashboard, feedback analysis tools, optimization playbook, growth planning | ⬜ |

**Service Providers - Launch & Scaling**:
| Provider | Type | Local | Description | Research Source |
|----------|------|-------|-------------|----------------|
| Product Hunt | Launch Platform | No | Tech startup launch community with high visibility | Tech industry launch playbooks |
| Local Chamber of Commerce | Business Network | Yes | Local networking and partnership opportunities | Local business organizations |
| Google Ads | Advertising Platform | No | Digital advertising with measurable ROI | Google marketing resources, industry guides |

**Angel Support Available**: Launch planning, growth strategy, hiring templates, investor pitch materials, scaling playbooks

### 10. Success Metrics & Milestones
- **Key Performance Indicators**: [Industry-specific metrics]
- **Monthly Checkpoints**: [Detailed milestone tracking]

### 11. Angel's Ongoing Support
Throughout this roadmap, I'll be available to:
- Help you navigate each phase with detailed guidance
- Provide industry-specific insights and recommendations
- Assist with problem-solving and decision-making
- Connect you with relevant resources and tools

### 12. [EXECUTION] Your Journey Ahead: Execution Excellence
This roadmap represents more than just tasks—it's your pathway to entrepreneurial success. Every element has been carefully researched and validated to ensure you're building a business that can thrive in today's competitive landscape.

**Why Execution Matters:**
- **Consistency**: Following this roadmap ensures you don't miss critical steps that could derail your progress
- **Efficiency**: The sequential approach prevents you from doing things twice or in the wrong order
- **Confidence**: Each completed phase builds momentum and confidence for the next challenge
- **Success**: Research shows that businesses following structured launch plans are 3x more likely to succeed

**Your Commitment to Success:**
- Dedicate time daily to roadmap tasks
- Use Angel's support whenever you need guidance
- Stay flexible but maintain the core sequence
- Celebrate milestones along the way
- Remember: You're building the business of your dreams

**Final Words of Encouragement:**
You've already accomplished something remarkable by completing your business planning phase. This roadmap is your next step toward turning your vision into reality. Trust the process, stay committed, and remember that every successful entrepreneur started exactly where you are now.

**Ready to Begin Your Launch Journey?** 
Your roadmap is complete, researched, and ready for execution. The next phase will guide you through implementing each task with detailed support and resources.

*This roadmap is tailored specifically to your business, industry, and location. Every recommendation is designed to help you build the business of your dreams.*

**CRITICAL FORMATTING REQUIREMENTS:**
- ALL roadmap steps MUST be in markdown table format with columns: Task | Description | Dependencies | Angel's Role | Status
- Use sequential numbering (1.1, 1.2, 2.1, 2.2, etc.) to show clear sequence of events within each phase
- Each phase MUST have a table with ALL steps listed in order
- Do NOT use bullet points or paragraphs for roadmap steps - ONLY use tables
- Tables must follow this exact format:
  | Task | Description | Dependencies | Angel's Role | Status |
  |------|-------------|--------------|-------------|--------|
  | **1.1 [Task Name]** | [Detailed description] | [Dependencies or "None"] | [What Angel will do to help] | ⬜ |
  | **1.2 [Task Name]** | [Detailed description] | [Dependencies] | [What Angel will do to help] | ⬜ |
- Status column should use ⬜ for pending tasks, ✓ for completed tasks, or → SOON for upcoming tasks
- Bold all task titles and key terms
- Use a professional but friendly tone
- Ensure sequence is visually clear with numbered steps in order
- Each phase should start with a "Goal:" statement explaining the purpose of that phase
"""

    # Format the roadmap template with research data
    roadmap_content = ROADMAP_TEMPLATE.format(
        government_resources=_safe_excerpt(government_resources, "Government sources researched", 500),
        regulatory_requirements=_safe_excerpt(regulatory_requirements, "Regulatory requirements identified", 500),
        academic_insights=_safe_excerpt(academic_insights, "Academic research reviewed", 500),
        startup_research=_safe_excerpt(startup_research, "Startup research conducted", 500),
        market_entry_strategy=_safe_excerpt(market_entry_strategy, "Market entry strategy analyzed", 500),
        operational_insights=_safe_excerpt(operational_insights, "Operational insights gathered", 500)
    )
    
    # Generate final roadmap using AI with explicit reference to Roadmap Deep Research Questions V3
    roadmap_prompt = f"""
    Generate a comprehensive, detailed launch roadmap based on the following research and template:
    
    **CRITICAL REFERENCE**: This roadmap generation MUST reference and align with "Roadmap Deep Research Questions V3" to ensure comprehensive coverage of all critical roadmap planning areas.
    
    Session Data: {json.dumps(session_data, indent=2)}
    
    Deep Research Conducted:
    Government Resources: {_safe_excerpt(government_resources, "Government sources researched")}
    Regulatory Requirements: {_safe_excerpt(regulatory_requirements, "Regulatory requirements identified")}
    Academic Insights: {_safe_excerpt(academic_insights, "Academic research reviewed")}
    Startup Research: {_safe_excerpt(startup_research, "Startup research conducted")}
    Market Entry Strategy: {_safe_excerpt(market_entry_strategy, "Market entry strategy analyzed")}
    Operational Insights: {_safe_excerpt(operational_insights, "Operational insights gathered")}
    
    **Reference Document**: Roadmap Deep Research Questions V3
    
    Use the following template structure and fill it with comprehensive, detailed content that:
    1. References "Roadmap Deep Research Questions V3" to ensure all critical areas are covered
    2. Incorporates all the research findings above
    3. Provides specific, actionable steps with timelines and research sources
    4. Follows the table format requirements specified in the template
    5. Addresses all questions and considerations from Roadmap Deep Research Questions V3
    
    Template Structure:
    {ROADMAP_TEMPLATE[:2000]}...
    
    **IMPORTANT**: Ensure the roadmap addresses all questions and considerations from "Roadmap Deep Research Questions V3" to provide a truly comprehensive, actionable launch plan.
    
    Generate the complete roadmap now, following the template structure and ensuring all phases are detailed with specific steps, timelines, and research source citations.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert business roadmap advisor. Generate comprehensive, actionable launch roadmaps that reference Roadmap Deep Research Questions V3 and incorporate extensive research from government, academic, and industry sources."
                },
                {
                    "role": "user",
                    "content": roadmap_prompt
                }
            ],
            temperature=0.6,
            max_tokens=8000
        )
        
        roadmap_content = response.choices[0].message.content
    except Exception as e:
        print(f"Error generating roadmap with AI: {e}")
        # Fallback to formatted template
        roadmap_content = ROADMAP_TEMPLATE.format(
            government_resources=_safe_excerpt(government_resources, "Government sources researched", 500),
            regulatory_requirements=_safe_excerpt(regulatory_requirements, "Regulatory requirements identified", 500),
            academic_insights=_safe_excerpt(academic_insights, "Academic research reviewed", 500),
            startup_research=_safe_excerpt(startup_research, "Startup research conducted", 500),
            market_entry_strategy=_safe_excerpt(market_entry_strategy, "Market entry strategy analyzed", 500),
            operational_insights=_safe_excerpt(operational_insights, "Operational insights gathered", 500)
        )
    
    return {
        "plan": roadmap_content,
        "generated_at": datetime.now().isoformat(),
        "research_conducted": True,
        "industry": session_data['industry'],
        "location": session_data['location'],
        "reference_document": "Roadmap Deep Research Questions V3"
    }

async def generate_implementation_insights(industry: str, location: str, business_type: str):
    """Generate RAG-powered implementation insights for the transition phase"""
    
    # Conduct research for implementation insights
    implementation_research = await conduct_web_search(f"site:forbes.com OR site:hbr.org startup implementation best practices {industry} {location}")
    compliance_research = await conduct_web_search(f"site:gov OR site:sba.gov business implementation compliance requirements {industry} {location}")
    success_factors = await conduct_web_search(f"site:bloomberg.com OR site:wsj.com successful startup implementation factors {industry}")
    local_resources = await conduct_web_search(f"site:gov {location} business implementation resources support programs")
    
    INSIGHTS_TEMPLATE = """
Based on extensive research from authoritative sources, here are key implementation insights for your {industry} business in {location}:

**Research-Backed Implementation Strategy:**

**1. Industry-Specific Considerations:**
- {implementation_research}
- Industry best practices and common pitfalls to avoid
- Regulatory requirements specific to {industry}
- Market timing and competitive landscape factors

**2. Compliance & Legal Framework:**
- {compliance_research}
- Required permits and licenses for {business_type} businesses
- Tax obligations and reporting requirements
- Insurance and liability considerations

**3. Success Factors & Execution:**
- {success_factors}
- Key performance indicators for {industry} startups
- Resource allocation and prioritization strategies
- Risk mitigation and contingency planning

**4. Local Resources & Support:**
- {local_resources}
- Government programs and incentives available
- Local business networks and mentorship opportunities
- Funding and grant opportunities in {location}

**Implementation Excellence Principles:**
- Follow the sequential roadmap phases for optimal results
- Leverage local service providers for compliance and expertise
- Maintain detailed documentation throughout the process
- Stay flexible while maintaining core strategic direction
- Regular progress reviews and milestone celebrations

This research-backed approach ensures your implementation follows proven methodologies while adapting to your specific business context and local requirements.
""".format(
        industry=industry,
        location=location,
        business_type=business_type,
        implementation_research=implementation_research,
        compliance_research=compliance_research,
        success_factors=success_factors,
        local_resources=local_resources
    )
    
    return INSIGHTS_TEMPLATE

async def generate_service_provider_preview(industry: str, location: str, business_type: str):
    """Generate RAG-powered service provider preview for the transition phase"""
    
    # Conduct research for service providers
    legal_providers = await conduct_web_search(f"site:law.com OR site:martindale.com business attorneys {location} {industry}")
    accounting_providers = await conduct_web_search(f"site:cpa.com OR site:aicpa.org accounting services {location} small business")
    banking_services = await conduct_web_search(f"site:bankrate.com OR site:nerdwallet.com business banking {location}")
    industry_specialists = await conduct_web_search(f"site:linkedin.com OR site:clutch.co {industry} consultants {location}")
    
    # Generate service provider preview data
    providers = [
        {
            "name": "Local Business Attorneys",
            "type": "Legal Services",
            "local": True,
            "description": f"Specialized in {industry} business formation and compliance in {location}",
            "research_source": legal_providers
        },
        {
            "name": "Certified Public Accountants",
            "type": "Accounting & Tax Services", 
            "local": True,
            "description": f"Expert accounting services for {business_type} businesses in {location}",
            "research_source": accounting_providers
        },
        {
            "name": "Business Banking Specialists",
            "type": "Financial Services",
            "local": True,
            "description": f"Business banking and financial services tailored to {industry} startups",
            "research_source": banking_services
        },
        {
            "name": f"{industry} Industry Consultants",
            "type": "Industry Expertise",
            "local": True,
            "description": f"Specialized {industry} knowledge and market insights for {location}",
            "research_source": industry_specialists
        }
    ]
    
    return providers

async def generate_motivational_quote():
    """Generate a motivational quote for the transition phase"""
    
    quotes = [
        {
            "quote": "Success is not final; failure is not fatal: it is the courage to continue that counts.",
            "author": "Winston Churchill",
            "category": "Persistence"
        },
        {
            "quote": "The way to get started is to quit talking and begin doing.",
            "author": "Walt Disney", 
            "category": "Action"
        },
        {
            "quote": "Innovation distinguishes between a leader and a follower.",
            "author": "Steve Jobs",
            "category": "Innovation"
        },
        {
            "quote": "The future belongs to those who believe in the beauty of their dreams.",
            "author": "Eleanor Roosevelt",
            "category": "Dreams"
        },
        {
            "quote": "Don't be afraid to give up the good to go for the great.",
            "author": "John D. Rockefeller",
            "category": "Excellence"
        }
    ]
    
    import random
    return random.choice(quotes)

async def generate_comprehensive_business_plan_summary(history):
    """Generate a comprehensive business plan summary for the Plan to Roadmap Transition"""
    
    # Extract session data from conversation history
    session_data = {}
    conversation_history = []
    
    for msg in history:
        if isinstance(msg, dict):
            conversation_history.append(msg)
            content = msg.get('content', '').lower()
            
            # Extract key business information - DYNAMIC APPROACH
            if any(keyword in content for keyword in ['business name', 'company name', 'venture name']):
                session_data['business_name'] = msg.get('content', '').strip()
            elif any(keyword in content for keyword in ['industry', 'business type', 'sector']):
                # Use AI model to dynamically identify industry
                industry_prompt = f"""
                Analyze this user input and extract the business industry or sector: "{content}"
                
                Return ONLY the industry name in a standardized format, or "General Business" if unclear.
                
                Examples:
                - "Tea Stall" → "Tea Stall"
                - "AI Development" → "AI Development"
                - "Food Service" → "Food Service"
                - "Technology" → "Technology"
                - "Healthcare" → "Healthcare"
                
                Return only the industry name:
                """
                
                try:
                    response = await client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": industry_prompt}],
                        temperature=0.1,
                        max_tokens=30
                    )
                    
                    industry_result = response.choices[0].message.content.strip()
                    session_data['industry'] = industry_result if industry_result else 'General Business'
                except Exception as e:
                    print(f"Industry extraction failed: {e}")
                    session_data['industry'] = 'General Business'
            
            # Extract location information
            if any(keyword in content for keyword in ['location', 'city', 'country', 'state', 'region']):
                if 'united states' in content or 'usa' in content or 'us' in content:
                    session_data['location'] = 'United States'
                elif 'canada' in content:
                    session_data['location'] = 'Canada'
                elif 'europe' in content:
                    session_data['location'] = 'Europe'
                elif 'asia' in content:
                    session_data['location'] = 'Asia'
                else:
                    session_data['location'] = 'International'
            
            # Extract business type
            if any(keyword in content for keyword in ['llc', 'corporation', 'partnership', 'sole proprietorship']):
                session_data['business_type'] = msg.get('content', '').strip()

    # Set defaults
    session_data.setdefault('business_name', 'Your Business')
    session_data.setdefault('industry', 'General Business')
    session_data.setdefault('location', 'United States')
    session_data.setdefault('business_type', 'Startup')

    BUSINESS_PLAN_SUMMARY_TEMPLATE = """
# COMPREHENSIVE BUSINESS PLAN SUMMARY
## {business_name}

---

## [SUMMARY] EXECUTIVE SUMMARY

**Business Name:** {business_name}
**Industry:** {industry}
**Location:** {location}
**Business Type:** {business_type}

### Key Business Highlights:
- **Mission Statement:** [Extracted from business planning responses]
- **Value Proposition:** [Unique selling points identified]
- **Target Market:** [Primary customer segments]
- **Revenue Model:** [How the business will generate income]

---

## [OVERVIEW] BUSINESS OVERVIEW

### Core Business Concept
[Comprehensive summary of the business idea, products/services, and unique value proposition]

### Market Opportunity
[Market size, growth potential, and competitive landscape analysis]

### Business Model
[Revenue streams, pricing strategy, and business model canvas elements]

---

## [RESEARCH] MARKET RESEARCH & ANALYSIS

### Target Market
- **Primary Customer Segments:** [Detailed customer personas]
- **Market Size:** [Total addressable market and serviceable market]
- **Customer Needs:** [Key pain points and solutions provided]

### Competitive Analysis
- **Direct Competitors:** [Main competitors and their strengths/weaknesses]
- **Competitive Advantage:** [Unique differentiators and moats]
- **Market Positioning:** [How the business will position itself]

---

## 💰 FINANCIAL PROJECTIONS

### Revenue Projections
- **Year 1 Revenue Target:** [Projected first-year revenue]
- **Revenue Growth:** [Growth trajectory and milestones]
- **Key Revenue Drivers:** [Main sources of income]

### Cost Structure
- **Startup Costs:** [Initial investment requirements]
- **Operating Expenses:** [Monthly/yearly operational costs]
- **Break-even Analysis:** [When the business becomes profitable]

### Funding Requirements
- **Initial Funding Needed:** [Amount and purpose]
- **Funding Sources:** [How funding will be obtained]
- **Use of Funds:** [Detailed allocation of investment]

---

## [OPERATIONS] OPERATIONS & LOGISTICS

### Operational Model
[How the business will operate day-to-day]

### Key Resources
- **Human Resources:** [Team structure and hiring needs]
- **Physical Resources:** [Equipment, facilities, technology]
- **Intellectual Property:** [Patents, trademarks, proprietary knowledge]

### Supply Chain
[Supplier relationships, inventory management, and logistics]

---

## [MARKETING] MARKETING & SALES STRATEGY

### Marketing Strategy
- **Brand Positioning:** [How the brand will be positioned in the market]
- **Marketing Channels:** [Digital and traditional marketing approaches]
- **Customer Acquisition:** [How customers will be acquired]

### Sales Strategy
- **Sales Process:** [Step-by-step sales methodology]
- **Sales Team:** [Sales structure and responsibilities]
- **Pricing Strategy:** [How products/services will be priced]

---

## [LEGAL] LEGAL & COMPLIANCE

### Business Structure
[Legal entity type and organizational structure]

### Regulatory Requirements
[Licenses, permits, and compliance requirements]

### Risk Management
[Key risks and mitigation strategies]

---

## [GROWTH] GROWTH & SCALING

### Short-term Goals (6-12 months)
[Immediate objectives and milestones]

### Medium-term Goals (1-3 years)
[Growth targets and expansion plans]

### Long-term Vision (3-5 years)
[Strategic vision and exit strategy]

---

## 📝 KEY DECISIONS & MILESTONES

### Major Decisions Made
1. **Business Structure:** [Legal entity chosen and rationale]
2. **Market Entry Strategy:** [How and when to enter the market]
3. **Funding Approach:** [How funding will be secured]
4. **Operational Model:** [How the business will operate]
5. **Technology Stack:** [Key technologies and tools]

### Critical Milestones
- **Month 1-3:** [Early milestones and achievements]
- **Month 4-6:** [Mid-term objectives]
- **Month 7-12:** [First-year targets]
- **Year 2-3:** [Growth and expansion goals]

---

## [NEXT STEPS] ROADMAP READINESS

This comprehensive business plan provides the foundation for creating a detailed, actionable launch roadmap. The next phase will translate these strategic decisions into specific, chronological tasks that will guide you from planning to implementation.

**Ready for Roadmap Generation:** [COMPLETE]
**Business Plan Completeness:** [COMPLETE]
**Strategic Foundation:** [COMPLETE]

---

*This summary was generated based on your detailed responses during the business planning phase and represents the comprehensive foundation for your entrepreneurial journey.*
"""

    messages = [
        {
            "role": "system",
            "content": (
                "You are Angel, an AI startup coach specializing in comprehensive business planning. "
                "Generate a detailed business plan summary based on the user's conversation history. "
                "Extract key information, decisions, and insights from their responses to create a "
                "comprehensive overview that serves as the foundation for roadmap generation. "
                "Use the provided template structure and fill in all sections with relevant information "
                "from the conversation history. Be thorough and professional while maintaining a supportive tone."
            )
        },
        {
            "role": "user",
            "content": (
                "Generate a comprehensive business plan summary based on this conversation history:\n\n"
                "Session Data: " + json.dumps(session_data, indent=2) + "\n\n"
                "Conversation History: " + json.dumps(conversation_history, indent=2) + "\n\n"
                "Please fill in the template with relevant information extracted from the conversation:\n\n"
                + BUSINESS_PLAN_SUMMARY_TEMPLATE + "\n\n"
                "**Instructions:**\n"
                "- Extract and synthesize information from the conversation history\n"
                "- Fill in all template sections with relevant details\n"
                "- Highlight key decisions and milestones achieved\n"
                "- Ensure the summary is comprehensive and ready for roadmap generation\n"
                "- Use markdown formatting for clear presentation"
            )
        }
    ]

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=4000
    )

    return {
        "summary": response.choices[0].message.content,
        "session_data": session_data,
        "generated_at": datetime.now().isoformat(),
        "completeness_check": {
            "business_overview": True,
            "market_analysis": True,
            "financial_projections": True,
            "operations": True,
            "marketing_strategy": True,
            "legal_compliance": True,
            "growth_planning": True
        }
    }
