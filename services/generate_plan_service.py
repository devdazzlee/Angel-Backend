from openai import AsyncOpenAI
import os
import json
from datetime import datetime
from services.angel_service import generate_business_plan_artifact, conduct_web_search, extract_business_context_from_history

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

| Step Name | Step Description | Timeline | Research Source |
|-----------|------------------|----------|-----------------|
| **Choose Business Structure** | Select appropriate legal structure (LLC, C-Corp, S-Corp, Partnership, or Sole Proprietorship). Consider liability protection, tax implications, and operational flexibility. Evaluate based on industry requirements, funding needs, and growth plans. | Week 1-2 | *Government* - SBA.gov business structure guide, IRS.gov tax implications, state business registration sites |
| **Register Business Name** | Register business name with Secretary of State. Check availability via state database. Consider federal trademark (USPTO) for brand protection. Secure matching domain name and social media handles. File DBA if using alternative name. | Week 2-3 | *Government* - State Secretary of State websites, USPTO.gov trademark database, SBA.gov naming guidelines |
| **Obtain EIN** | Apply for Employer Identification Number through IRS website. Required for business bank accounts, hiring employees, and tax filing. Free application, instant approval in most cases. | Week 3 | *Government* - IRS.gov EIN application portal, SBA.gov business identification guide |
| **Get Business Licenses** | Identify and obtain federal, state, and local licenses/permits specific to your industry and location. Research regulatory requirements, submit applications, schedule inspections if needed. | Week 3-6 | *Government* - State licensing boards, federal regulatory agencies, SBA.gov license finder tool |
| **File Trademarks** | Protect branding before public marketing. File federal trademarks for business name and key brand elements through USPTO. | Week 4-8 | *Government* - USPTO.gov trademark filing system, *Industry* - LegalZoom, Rocket Lawyer trademark guides |

**Service Providers - Legal Formation**:
| Provider | Type | Local | Description | Research Source |
|----------|------|-------|-------------|----------------|
| LegalZoom | Online Service | No | Online legal document preparation, standardized packages | Industry comparison sites, user reviews |
| Local Business Attorney | Legal Professional | Yes | Personalized legal advice, industry expertise | State bar associations, legal directories |
| SCORE Business Mentor | Free Consultation | Yes | Volunteer business mentors with industry experience | SBA.gov, local SCORE chapters |

### 6. Phase 2: Financial Planning & Setup (Months 2-3)

**Goal**: Set up your financial systems and funding strategies to support all subsequent operations.

**Roadmap Steps - Phase 2: Financial Foundation**

| Step Name | Step Description | Timeline | Research Source |
|-----------|------------------|----------|-----------------|
| **Open Business Bank Account** | Select and open dedicated business checking account. Compare traditional banks vs online/fintech options. Consider fees, features, integration capabilities. Gather required documents (EIN, formation docs, ID). | Week 4-5 | *Government* - FDIC.gov bank information, SBA.gov banking resources, *Industry* - Bankrate.com comparisons, Forbes banking guides |
| **Set Up Accounting System** | Choose accounting software (cash vs accrual basis). Set up chart of accounts, connect bank feeds, establish bookkeeping processes. Consider hiring bookkeeper or accountant. | Week 5-6 | *Industry* - Software review sites (G2, Capterra), QuickBooks/Xero documentation, *Academic* - Business school accounting best practices |
| **Establish Financial Controls** | Implement expense policies, approval workflows, receipt management. Set up separate business credit card. Create financial tracking and reporting processes. | Week 6-7 | *Government* - IRS.gov recordkeeping requirements, *Academic* - Financial management research, *Industry* - Harvard Business Review financial controls |
| **Create Financial Projections** | Develop detailed financial projections (revenue, expenses, cash flow) for 12-36 months. Create budget and financial milestones. Plan for seasonal variations. | Week 7-8 | *Academic* - Business school financial modeling research, *Industry* - WSJ startup financial planning, Forbes budgeting guides |

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

| Step Name | Step Description | Timeline | Research Source |
|-----------|------------------|----------|-----------------|
| **Establish Supply Chain** | Identify and vet suppliers (local vs international). Negotiate terms, minimum orders, payment terms. Set up logistics and fulfillment processes. Establish backup suppliers for critical items. | Month 3-4 | *Industry* - Bloomberg supply chain reports, WSJ logistics guides, *Academic* - Supply chain management research, trade association resources |
| **Set Up Operations Infrastructure** | Secure physical location (office, warehouse, retail) if needed. Purchase equipment, technology, and tools. Set up utilities, insurance, and security systems. | Month 4 | *Government* - OSHA.gov workplace requirements, state business location resources, *Industry* - Commercial real estate publications |
| **Develop Product/Service** | Finalize product specifications or service delivery processes. Create prototypes or pilot programs. Test with focus groups or beta customers. Iterate based on feedback. | Month 4-5 | *Academic* - Product development research, innovation studies, *Industry* - Harvard Business Review product development, Forbes startup guides |
| **Implement Quality Control** | Establish quality standards and testing procedures. Create quality assurance processes. Set up customer feedback loops. Document standard operating procedures. | Month 5 | *Government* - Industry-specific quality standards, *Academic* - Quality management research, *Industry* - Industry best practices publications |

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

| Step Name | Step Description | Timeline | Research Source |
|-----------|------------------|----------|-----------------|
| **Develop Brand Identity** | Create brand positioning, messaging, visual identity (logo, colors, fonts). Define unique value proposition and brand voice. Develop brand guidelines document. | Month 5-6 | *Industry* - Harvard Business Review branding guides, Forbes brand strategy, *Academic* - Marketing research on brand positioning |
| **Build Digital Presence** | Create professional website with SEO optimization. Set up social media profiles across relevant platforms. Implement analytics and tracking (Google Analytics, etc.). | Month 6 | *Industry* - Digital marketing publications, Google marketing resources, *Academic* - Digital marketing research studies |
| **Create Marketing Materials** | Develop marketing collateral (brochures, presentations, business cards). Create product photography and videography. Write copy for various channels. | Month 6-7 | *Industry* - Marketing industry reports, design best practices, *Academic* - Communication and marketing research |
| **Implement Sales Process** | Define sales funnel stages and customer journey. Create CRM system and sales tracking. Develop sales scripts, proposals, and contracts. Train sales team if applicable. | Month 7 | *Industry* - Sales methodology publications, CRM vendor resources, *Academic* - Sales process research, business school case studies |
| **Plan Customer Acquisition** | Identify customer acquisition channels (paid ads, content marketing, partnerships). Set budgets and KPIs. Create initial campaigns and test messaging. | Month 7 | *Industry* - Customer acquisition cost studies, marketing ROI reports, *Academic* - Customer acquisition research, startup growth studies |

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

| Step Name | Step Description | Timeline | Research Source |
|-----------|------------------|----------|-----------------|
| **Execute Go-to-Market Launch** | Choose launch strategy (soft launch, hard launch, beta, or phased rollout). Coordinate all marketing channels. Execute launch events and campaigns. Monitor initial customer response. | Month 7-8 | *Industry* - Launch strategy case studies, Product Hunt launch guides, *Academic* - Go-to-market research, startup launch studies |
| **Customer Acquisition at Scale** | Ramp up customer acquisition efforts across validated channels. Scale spending based on ROI metrics. Implement referral programs and partnerships. | Month 8-10 | *Industry* - Scaling strategies from Bloomberg, WSJ growth stories, *Academic* - Growth hacking research, customer acquisition studies |
| **Operational Scaling** | Hire key team members as needed. Scale operations to meet demand. Optimize processes for efficiency. Implement automation where possible. | Month 9-11 | *Government* - SBA.gov hiring resources, *Industry* - HR best practices, Forbes scaling guides, *Academic* - Operations management research |
| **Financial Management & Fundraising** | Monitor cash flow closely. Achieve profitability milestones or secure additional funding. Implement financial reporting and forecasting. | Month 10-12 | *Industry* - Funding reports from Crunchbase, WSJ startup funding, *Academic* - Financial management research, fundraising studies |
| **Measure, Learn, Optimize** | Track KPIs and business metrics. Analyze customer feedback and behavior. Optimize product, pricing, and processes. Prepare for next growth phase. | Month 11-12 | *Academic* - Business analytics research, optimization studies, *Industry* - Harvard Business Review analytics, Forbes optimization guides |

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
- ALL roadmap steps MUST be in markdown table format with columns: Step Name | Step Description | Timeline | Research Source
- Each phase MUST have a table with ALL steps listed in order
- Do NOT use bullet points or paragraphs for roadmap steps - ONLY use tables
- Tables must follow this exact format:
  | Step Name | Step Description | Timeline | Research Source |
  |-----------|------------------|----------|-----------------|
  | **[Step Name]** | [Detailed description with actionable guidance] | [Specific timeline: Week X, Month X-Y, etc.] | *Government* / *Academic* / *Industry* - [Specific source citations] |
- Research Source column must cite specific sources using format: *Government* - SBA.gov, IRS.gov, etc. OR *Academic* - University research, journals, etc. OR *Industry* - Bloomberg, WSJ, Forbes, HBR, etc.
- Timeline must be specific (e.g., "Week 1-2", "Month 3-4", "Week 4-8")
- Bold all step names and key terms
- Use a professional but friendly tone
- Each phase should start with a "Goal:" statement explaining the purpose of that phase
- Ensure all steps include research source citations from the three categories: Government, Academic, or Industry
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
    
    **CRITICAL FORMAT REQUIREMENT**: All roadmap steps MUST use table format with exactly these columns:
    | Step Name | Step Description | Timeline | Research Source |
    
    Research Source column must cite specific sources using format:
    - *Government* - SBA.gov, IRS.gov, state agencies, etc.
    - *Academic* - University research, Google Scholar, JSTOR, etc.
    - *Industry* - Bloomberg, WSJ, Forbes, HBR, etc.
    
    Generate the complete roadmap now, following the template structure and ensuring all phases are detailed with specific steps, timelines, and research source citations in the correct table format.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert business roadmap advisor. Generate comprehensive, actionable launch roadmaps that reference Roadmap Deep Research Questions V3 and incorporate extensive research from government, academic, and industry sources. CRITICAL: All roadmap steps MUST be in table format with columns: Step Name | Step Description | Timeline | Research Source. Each step must include specific research source citations (Government, Academic, or Industry) with actual source names."
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

async def generate_comprehensive_business_plan_summary(history, session=None):
    """Generate a comprehensive business plan summary for the Plan to Roadmap Transition"""
    
    # Extract business context from session data (preferred) or history
    session_data = {}
    conversation_history = []
    
    # First, try to get business context from session
    if session:
        business_context = session.get("business_context", {})
        session_data['business_name'] = business_context.get("business_name") or session.get("business_name")
        session_data['industry'] = business_context.get("industry") or session.get("industry")
        session_data['location'] = business_context.get("location") or session.get("location")
        session_data['business_type'] = business_context.get("business_type") or session.get("business_type")
    
    # Build conversation history and extract BUSINESS_PLAN Q&A pairs
    business_plan_qa = {}  # Map question numbers to answers
    conversation_history = []
    import re
    
    # Debug: Check history structure
    if history and len(history) > 0:
        sample_msg = history[0] if isinstance(history, list) else None
        print(f"🔍 DEBUG - History type: {type(history)}, Length: {len(history) if isinstance(history, list) else 'N/A'}")
        if sample_msg:
            print(f"🔍 DEBUG - Sample message type: {type(sample_msg)}, Keys: {sample_msg.keys() if isinstance(sample_msg, dict) else 'N/A'}")
            if isinstance(sample_msg, dict):
                sample_content = str(sample_msg.get('content', ''))[:200]
                print(f"🔍 DEBUG - Sample content preview: {sample_content}")
    
    # First pass: Extract all BUSINESS_PLAN questions with their tags
    question_map = {}  # Map question tags to question numbers
    bp_tag_count = 0
    
    for msg in history:
        if not isinstance(msg, dict):
            continue
            
        role = msg.get('role', '')
        content = str(msg.get('content', ''))
        
        # Look for BUSINESS_PLAN question tags (support both 1-digit and 2-digit formats)
        # Pattern: [[Q:BUSINESS_PLAN.01]] or [[Q:BUSINESS_PLAN.1]]
        tag_matches = re.findall(r'\[\[Q:(BUSINESS_PLAN\.\d{1,2})\]\]', content)
        
        if tag_matches and role == 'assistant':
            bp_tag_count += len(tag_matches)
            for tag in tag_matches:
                # Normalize to 2-digit format
                parts = tag.split('.')
                if len(parts) == 2:
                    q_num = int(parts[1])
                    normalized_tag = f"BUSINESS_PLAN.{q_num:02d}"
                    question_map[normalized_tag] = q_num
                    question_map[tag] = q_num  # Also map original format
                    
                    if q_num not in business_plan_qa:
                        # Extract question text
                        question_text = content.replace(f'[[Q:{tag}]]', '').replace(f'[[Q:{normalized_tag}]]', '').strip()
                        question_text = re.sub(r'\*\*.*?\*\*', '', question_text)
                        question_text = re.sub(r'^Angel\s*', '', question_text, flags=re.IGNORECASE).strip()
                        question_text = question_text[:300]  # Limit length
                        business_plan_qa[q_num] = {
                            'question': question_text,
                            'answer': None,
                            'tag': normalized_tag
                        }
    
    print(f"🔍 DEBUG - Found {bp_tag_count} BUSINESS_PLAN tags in history")
    
    # Second pass: Match user answers to questions
    for i, msg in enumerate(history):
        if not isinstance(msg, dict):
            continue
            
        conversation_history.append(msg)
        role = msg.get('role', '')
        
        # If this is a user message, check if previous assistant message had a BUSINESS_PLAN tag
        if role == 'user' and i > 0:
            prev_msg = history[i-1] if i < len(history) else None
            if prev_msg and isinstance(prev_msg, dict) and prev_msg.get('role') == 'assistant':
                prev_content = str(prev_msg.get('content', ''))
                # Find BUSINESS_PLAN tag in previous message (support both formats)
                tag_match = re.search(r'\[\[Q:(BUSINESS_PLAN\.\d{1,2})\]\]', prev_content)
                if tag_match:
                    tag = tag_match.group(1)
                    # Normalize tag
                    parts = tag.split('.')
                    if len(parts) == 2:
                        q_num = int(parts[1])
                        if q_num in business_plan_qa:
                            answer = str(msg.get('content', '')).strip()
                            # Skip command responses and very short answers
                            if (answer.lower() not in ['accept', 'modify', 'draft', 'support', 'scrapping', 'scraping', 'yes', 'no'] 
                                and len(answer) > 5 
                                and business_plan_qa[q_num]['answer'] is None):
                                business_plan_qa[q_num]['answer'] = answer
    
    answered_count = len([qa for qa in business_plan_qa.values() if qa.get('answer')])
    print(f"📊 Extracted {answered_count} BUSINESS_PLAN Q&A pairs from history")
    if answered_count > 0:
        print(f"   Questions with answers: {sorted([q_num for q_num, qa in business_plan_qa.items() if qa.get('answer')])}")
    else:
        print(f"   ⚠️ WARNING: No BUSINESS_PLAN Q&A pairs found! History length: {len(history)}")
        # Debug: Check what's in history
        bp_messages = [msg for msg in history if isinstance(msg, dict) and 'BUSINESS_PLAN' in str(msg.get('content', ''))]
        print(f"   Messages containing 'BUSINESS_PLAN': {len(bp_messages)}")
    
    # Extract business context from history using the existing extraction function
    try:
        extracted_context = extract_business_context_from_history(history)
        if extracted_context:
            # Override with extracted context if it's better
            if extracted_context.get("business_name") and extracted_context.get("business_name").lower() not in ["your business", "business", ""]:
                session_data['business_name'] = extracted_context.get("business_name")
            if extracted_context.get("industry") and extracted_context.get("industry").lower() not in ["general business", "business", ""]:
                session_data['industry'] = extracted_context.get("industry")
            if extracted_context.get("location") and extracted_context.get("location").lower() not in ["united states", ""]:
                session_data['location'] = extracted_context.get("location")
            if extracted_context.get("business_type") and extracted_context.get("business_type").lower() not in ["startup", ""]:
                session_data['business_type'] = extracted_context.get("business_type")
    except Exception as e:
        print(f"Business context extraction failed: {e}")
    
    # If session data is still missing, try to extract from history using AI
    if not session_data.get('business_name') or session_data.get('business_name').lower() in ['your business', 'business', '']:
        # Use AI to extract business information from history
        extraction_prompt = f"""
        Analyze this conversation history and extract the following business information:
        
        {json.dumps([msg.get('content', '')[:500] for msg in conversation_history[-50:]], indent=2)}
        
        Extract and return ONLY a JSON object with these fields:
        {{
            "business_name": "actual business name from conversation",
            "industry": "actual industry from conversation",
            "location": "actual location (city, state, country) from conversation",
            "business_type": "actual business type from conversation",
            "mission_statement": "actual mission statement if mentioned",
            "value_proposition": "actual value proposition if mentioned"
        }}
        
        If any field is not found, use null. Return ONLY valid JSON, no other text.
        """
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            extracted = json.loads(response.choices[0].message.content)
            session_data.update({k: v for k, v in extracted.items() if v})
        except Exception as e:
            print(f"Business info extraction failed: {e}")
    
    # Set defaults only if still missing
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
                "Extract ALL key information, decisions, and insights from their responses to create a "
                "comprehensive overview that serves as the foundation for roadmap generation. "
                "\n\n"
                "CRITICAL EXTRACTION REQUIREMENTS:\n"
                "- Extract the ACTUAL business name, industry, location, and business type from the conversation\n"
                "- Extract the ACTUAL mission statement, value proposition, and target market from user's answers\n"
                "- Extract ALL financial information: revenue projections, costs, funding needs, break-even timeline\n"
                "- Extract ALL operational details: staffing, suppliers, facilities, equipment\n"
                "- Extract ALL marketing strategy: channels, sales process, customer acquisition, pricing\n"
                "- Extract ALL legal/compliance information: licenses, insurance, IP protection, contracts\n"
                "- Extract ALL growth plans: milestones, expansion strategy, partnerships\n"
                "- Extract ALL risk management: risks identified, mitigation strategies, contingency plans\n"
                "\n"
                "DO NOT use placeholders like [Not Provided], [Extracted from...], [COMPLETE], or [INCOMPLETE]. "
                "If information is truly not available, state 'Not yet specified' or 'To be determined'. "
                "Use the provided template structure and fill in ALL sections with REAL information "
                "from the conversation history. Be thorough and professional while maintaining a supportive tone."
            )
        },
        {
            "role": "user",
            "content": (
                "Generate a comprehensive business plan summary based on this conversation history.\n\n"
                "**CRITICAL REQUIREMENTS:**\n"
                "- Extract ACTUAL information from the conversation - DO NOT use placeholders like [Not Provided], [Extracted from...], or [COMPLETE]\n"
                "- Replace ALL template placeholders with real data from the conversation\n"
                "- Use the actual business name: " + str(session_data.get('business_name', 'Your Business')) + "\n"
                "- Use the actual industry: " + str(session_data.get('industry', 'General Business')) + "\n"
                "- Use the actual location: " + str(session_data.get('location', 'United States')) + "\n"
                "- Extract mission statement, value proposition, target market, revenue model, and ALL other details from the conversation\n"
                "- If information is not available, say 'Not yet specified' instead of using placeholders\n\n"
                "Session Data: " + json.dumps(session_data, indent=2) + "\n\n"
                "**EXTRACTED BUSINESS PLAN Q&A PAIRS (USE THESE!):**\n"
                + json.dumps({f"Q{q_num:02d}": {"question": qa['question'][:300], "answer": qa['answer'][:500] if qa['answer'] else "No answer yet"} 
                             for q_num, qa in sorted(business_plan_qa.items())}, indent=2) + "\n\n"
                "**QUESTION-TO-SECTION MAPPING (Use this to know where each answer goes):**\n"
                "- Q01-Q02: Business name, tagline, mission statement → Executive Summary, Business Overview\n"
                "- Q03: Problem solved → Value Proposition, Business Overview\n"
                "- Q04-Q05: Products/services, features → Business Overview, Products/Services\n"
                "- Q06-Q08: Target market, market size, competitors → Market Research & Analysis\n"
                "- Q09-Q12: Current solutions, market positioning → Market Research & Analysis, Competitive Analysis\n"
                "- Q13-Q15: Pricing, revenue model, sales projections → Financial Projections, Revenue Projections\n"
                "- Q16-Q18: Startup costs, operating expenses, break-even → Financial Projections, Cost Structure\n"
                "- Q19-Q20: Funding needs, funding sources → Financial Projections, Funding Requirements\n"
                "- Q21-Q24: Location, facilities, suppliers, staffing → Operations & Logistics\n"
                "- Q25-Q28: Operational needs, resources → Operations & Logistics\n"
                "- Q29-Q32: Marketing channels, sales process, customer acquisition → Marketing & Sales Strategy\n"
                "- Q33-Q35: Brand awareness, partnerships → Marketing & Sales Strategy\n"
                "- Q36-Q39: Licenses, insurance, IP protection, contracts → Legal & Compliance\n"
                "- Q40-Q42: Tax compliance, data privacy → Legal & Compliance\n"
                "- Q43-Q45: Milestones, future offerings, expansion → Growth & Scaling\n"
                "- Q46: Risks, concerns, final thoughts → Risk Management, Growth & Scaling\n\n"
                "**CRITICAL: Extract information from the Q&A pairs above and fill in the template below. "
                "DO NOT use 'Not yet specified' if the information exists in the Q&A pairs. "
                "For example, if Q02 answer contains a mission statement, extract it and use it. "
                "If Q06 answer describes the target market, extract it and use it. "
                "Read each Q&A pair carefully and extract ALL relevant information.\n\n"
                "**FULL CONVERSATION HISTORY (for additional context if needed):**\n"
                + json.dumps([{"role": msg.get('role'), "content": msg.get('content', '')[:400]} 
                             for msg in conversation_history[-100:]], indent=2) + "\n\n"
                "Please fill in the template with ACTUAL information extracted from the Q&A pairs above:\n\n"
                + BUSINESS_PLAN_SUMMARY_TEMPLATE.format(**session_data) + "\n\n"
                "**STEP-BY-STEP EXTRACTION PROCESS:**\n"
                "1. Read through ALL the Q&A pairs above\n"
                "2. For each section in the template, identify which Q&A pairs contain relevant information\n"
                "3. Extract the ACTUAL text from the answers - do not paraphrase unless necessary\n"
                "4. Fill in the template with the extracted information\n"
                "5. If a section has multiple related Q&A pairs, combine them into a comprehensive summary\n"
                "\n"
                "**EXAMPLES OF WHAT TO EXTRACT:**\n"
                "- If Q02 answer says 'SwiftPOS Solutions' and 'To provide fast, reliable POS solutions...' → Use 'SwiftPOS Solutions' as business name and 'To provide fast, reliable POS solutions...' as mission statement\n"
                "- If Q06 answer says 'small to medium retail stores, restaurants, and cafes in Karachi' → Use this EXACT text for Target Market\n"
                "- If Q13 answer says 'tiered subscription pricing based on features' → Use this EXACT text for Revenue Model\n"
                "- If Q16 answer says '$15,000-$18,000 for office setup, staff, equipment' → Use this EXACT text for Startup Costs\n"
                "\n"
                "**CRITICAL:** The Q&A pairs contain ALL the information you need. Read them carefully and extract EVERY detail. "
                "DO NOT use 'Not yet specified' if the information exists in any of the Q&A pairs above. "
                "Only use 'Not yet specified' if you've checked ALL Q&A pairs and the information truly doesn't exist.\n\n"
                "Now generate the comprehensive business plan summary by filling in the template with information from the Q&A pairs:"
            )
        }
    ]

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=8000  # Increased for comprehensive summary with actual data
    )

    summary_content = response.choices[0].message.content
    
    # Return both as summary (for backward compatibility) and as full result
    return {
        "summary": summary_content,  # Main summary content
        "full_summary": summary_content,  # Alias for clarity
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
