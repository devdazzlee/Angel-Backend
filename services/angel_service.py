from openai import AsyncOpenAI
import os
import json
import re
import random
import asyncio
from datetime import datetime
from functools import lru_cache
from typing import Optional, Dict, List, Any
from utils.constant import ANGEL_SYSTEM_PROMPT
import logging
from routers.budget_router import RevenueStreamInitial # Import the new Pydantic model

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# pkpalstan
# Web search throttling
web_search_count = 0
web_search_reset_time = datetime.now()

# ... existing code ...

async def generate_initial_revenue_streams(business_type: str) -> List[RevenueStreamInitial]:
    """
    Generates a list of initial revenue streams based on the business type.
    """
    revenue_streams = []

    # Map business types to their corresponding revenue streams
    # This logic implements the client requirement for dynamic revenue streams
    if business_type.lower() in ["e-commerce", "retail"]:
        revenue_streams.append(RevenueStreamInitial(name="Product Sales"))
    elif business_type.lower() in ["saas", "software"]:
        revenue_streams.append(RevenueStreamInitial(name="Subscriptions"))
        revenue_streams.append(RevenueStreamInitial(name="License Sales"))
    elif business_type.lower() in ["consulting", "services"]:
        revenue_streams.append(RevenueStreamInitial(name="Service Fees"))
        revenue_streams.append(RevenueStreamInitial(name="Hourly Consulting"))
        revenue_streams.append(RevenueStreamInitial(name="Retainer Fees"))
    elif business_type.lower() in ["content creator", "influencer"]:
        revenue_streams.append(RevenueStreamInitial(name="Ad Revenue"))
        revenue_streams.append(RevenueStreamInitial(name="Sponsorships"))
        revenue_streams.append(RevenueStreamInitial(name="Affiliate Income"))
        revenue_streams.append(RevenueStreamInitial(name="Merchandise Sales"))
    elif business_type.lower() in ["coaching", "education"]:
        revenue_streams.append(RevenueStreamInitial(name="Course Sales"))
        revenue_streams.append(RevenueStreamInitial(name="Coaching Sessions"))
        revenue_streams.append(RevenueStreamInitial(name="Workshops"))
    else:
        # Default for other types or if business_type is not recognized
        revenue_streams.append(RevenueStreamInitial(name="General Revenue"))

    return revenue_streams

MOTIVATIONAL_QUOTES = [
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
    },
    {
        "quote": "Opportunities don't happen, you create them.",
        "author": "Chris Grosser",
        "category": "Opportunity"
    },
    {
        "quote": "Dream big. Start small. Act now.",
        "author": "Robin Sharma",
        "category": "Momentum"
    },
    {
        "quote": "The future depends on what you do today.",
        "author": "Mahatma Gandhi",
        "category": "Action"
    },
    {
        "quote": "Your time is limited, don't waste it living someone else's life.",
        "author": "Steve Jobs",
        "category": "Authenticity"
    },
    {
        "quote": "The only way to do great work is to love what you do.",
        "author": "Steve Jobs",
        "category": "Passion"
    },
    {
        "quote": "I have not failed. I've just found 10,000 ways that won't work.",
        "author": "Thomas Edison",
        "category": "Persistence"
    },
    {
        "quote": "If you are not embarrassed by the first version of your product, you've launched too late.",
        "author": "Reid Hoffman",
        "category": "Action"
    },
    {
        "quote": "The biggest risk is not taking any risk. In a world that's changing quickly, the only strategy that is guaranteed to fail is not taking risks.",
        "author": "Mark Zuckerberg",
        "category": "Risk"
    },
    {
        "quote": "Ideas are easy. Implementation is hard.",
        "author": "Guy Kawasaki",
        "category": "Execution"
    },
    {
        "quote": "Build something 100 people love, not something 1 million people kind of like.",
        "author": "Brian Chesky",
        "category": "Focus"
    },
    {
        "quote": "Don't worry about failure; you only have to be right once.",
        "author": "Drew Houston",
        "category": "Persistence"
    },
    {
        "quote": "The secret of change is to focus all of your energy not on fighting the old, but on building the new.",
        "author": "Socrates",
        "category": "Innovation"
    },
    {
        "quote": "Whether you think you can or you think you can't, you're right.",
        "author": "Henry Ford",
        "category": "Mindset"
    },
    {
        "quote": "The best time to plant a tree was 20 years ago. The second best time is now.",
        "author": "Chinese Proverb",
        "category": "Action"
    },
    {
        "quote": "It's not about ideas. It's about making ideas happen.",
        "author": "Scott Belsky",
        "category": "Execution"
    },
    {
        "quote": "Do not be embarrassed by your failures, learn from them and start again.",
        "author": "Richard Branson",
        "category": "Learning"
    },
    {
        "quote": "If you're not a risk taker, you should get the hell out of business.",
        "author": "Ray Kroc",
        "category": "Risk"
    },
    {
        "quote": "The only impossible journey is the one you never begin.",
        "author": "Tony Robbins",
        "category": "Action"
    },
    {
        "quote": "Success is walking from failure to failure with no loss of enthusiasm.",
        "author": "Winston Churchill",
        "category": "Resilience"
    },
    {
        "quote": "An entrepreneur is someone who jumps off a cliff and builds a plane on the way down.",
        "author": "Reid Hoffman",
        "category": "Entrepreneurship"
    }
]


def _get_feedback_intensity_guidance(intensity: int) -> str:
    """
    Get guidance text for Angel's critiquing behavior based on intensity (0-10).
    Returns instructions for Angel's system prompt.
    Delegates to preferences_service for consistency.
    """
    from services.preferences_service import get_feedback_intensity_guidance
    return get_feedback_intensity_guidance(intensity)


def pick_motivational_quote(exclude: Optional[str] = None) -> dict:
    available = [quote for quote in MOTIVATIONAL_QUOTES if quote["quote"] != exclude]
    pool = available if available else MOTIVATIONAL_QUOTES
    return random.choice(pool)

def should_conduct_web_search():
    """Throttle web searches to prevent excessive API calls"""
    global web_search_count, web_search_reset_time
    
    # Reset counter every 10 seconds for faster reset during implementation
    if (datetime.now() - web_search_reset_time).seconds > 10:
        web_search_count = 0
        web_search_reset_time = datetime.now()
    
    # Allow maximum 2 web searches per 10 seconds for better performance
    if web_search_count >= 2:
        return False
    
    web_search_count += 1
    return True

TAG_PROMPT = """CRITICAL: You MUST include a machine-readable tag in EVERY response that contains a question. Use this exact format:
[[Q:<PHASE>.<NN>]] 

Examples:
- [[Q:KYC.01]] What's your name?
- [[Q:KYC.02]] What is your preferred communication style?
- [[Q:BUSINESS_PLAN.01]] What is your business idea?
- [[Q:BUSINESS_PLAN.19]] What is your revenue model?
- [[Q:BUSINESS_PLAN.20]] How will you market your business?

IMPORTANT RULES:
1. The tag must be at the beginning of your question, before any other text
2. Question numbers must be sequential and correct for the current phase
3. For BUSINESS_PLAN phase, questions should be numbered 01 through 45
4. NEVER jump backwards in question numbers (e.g., from 19 to 10)
5. If you're continuing a conversation, increment the question number appropriately

FAILURE TO INCLUDE CORRECT TAGS WILL BREAK THE SYSTEM. ALWAYS include the correct sequential tag before asking any question.

FORMATTING REQUIREMENT: Always use structured format for questions - NEVER paragraph format!"""

WEB_SEARCH_PROMPT = """You have access to web search capabilities, but use them VERY SPARINGLY during Implementation phase.

IMPLEMENTATION PHASE RULES:
• Use web search VERY SPARINGLY - maximum 1 search per response
• Focus on delivering quick, practical implementation steps
• Users expect fast responses during implementation (3-5 seconds max)
• Only search for the most critical information gaps
• AVOID multiple web searches - they cause delays

WEB SEARCH GUIDELINES:
• When web search results are provided, you MUST include them in your response immediately
• Use previous calendar year for search queries (e.g., "2024" instead of "2023")
• Provide comprehensive answers based on the research findings
• Do not ask the user to wait or send another message - deliver results immediately
• Include specific details from the research in your response
• Do not just say "I'm conducting research" - provide the actual research results

To use web search, include in your response: WEBSEARCH_QUERY: [your search query]"""

THOUGHT_STARTERS_BY_TAG = {
    "BUSINESS_PLAN.01": [
        "What core problem does your idea solve, and for whom?",
        "How is your solution different from what currently exists?",
        "What vision do you have for your business in the next 1-3 years?"
    ],
    "BUSINESS_PLAN.02": [
        "What specific features or components will your product/service have?",
        "How will customers acquire or access your offering?",
        "What is the core benefit customers will receive from your product/service?"
    ],
    "BUSINESS_PLAN.03": [
        "What is your unique selling proposition (USP) that no one else can claim?",
        "What specific features, benefits, or experiences set you apart?",
        "Why would a customer choose your offering over a competitor's?"
    ],
    "BUSINESS_PLAN.04": [
        "What key milestones have you achieved so far?",
        "What specific steps are you planning to take next to advance your business?",
        "What is the biggest challenge or unknown at your current stage?"
    ],
    "BUSINESS_PLAN.05": [
        "Does your name reflect your brand's values or mission?",
        "Is it easy to remember, pronounce, and spell?",
        "Check if the name and relevant domain/social media handles are available."
    ],
    "BUSINESS_PLAN.06": [
        "Are there sub-sectors within this industry that you specifically target?",
        "What are the defining characteristics or major trends in this industry?",
        "How does your business fit into the broader industry landscape?"
    ],
    "BUSINESS_PLAN.07": [
        "Think SMART: Specific, Measurable, Achievable, Relevant, Time-bound.",
        "What are 1-3 critical goals you must achieve in the next 6-12 months for success?",
        "How will you measure progress towards these short-term goals?"
    ],
    "BUSINESS_PLAN.08": [
        "Create a customer avatar: give them a name, age, job, and daily challenges.",
        "What are their specific needs, desires, and pain points that your business addresses?",
        "Where do they spend their time (online and offline)?"
    ],
    "BUSINESS_PLAN.09": [
        "Will you sell directly, through partners, or both?",
        "What channels are most convenient and accessible for your target customer?",
        "How will your distribution strategy impact your costs and reach?"
    ],
    "BUSINESS_PLAN.10": [
        "What specific challenge or unmet need drives customers to seek a solution?",
        "How significant is this problem for them (time, money, frustration)?",
        "Why has this problem persisted, and how does your solution uniquely address it?"
    ],
    "BUSINESS_PLAN.11": [
        "What do you already know about your top 3-5 competitors?",
        "How do you think your competitors are currently solving the problem your business addresses?",
        "What gaps or weaknesses do you observe in their offerings or customer service?"
    ],
    "BUSINESS_PLAN.12": [
        "What technological, social, or economic trends are shaping your industry?",
        "How might these trends create new opportunities or pose threats to your business?",
        "Are there any emerging consumer behaviors that could influence your product or strategy?"
    ],
    "BUSINESS_PLAN.13": [
        "Based on the research, what unique value proposition can you highlight?",
        "How can you leverage your strengths or address competitor weaknesses?",
        "What narrative or brand story will make your business memorable?"
    ],
    "BUSINESS_PLAN.14": [
        "Consider the pros and cons of each option for your specific business model.",
        "How does your chosen location impact customer access, operating costs, and market reach?",
        "Are there any legal or logistical considerations for your preferred location type?"
    ],
    "BUSINESS_PLAN.15": [
        "What things do you need to have ready before you can open or start taking customers?",
        "Who can help you handle early tasks like setup, delivery, or accounting?",
        "What daily routines or systems will help your business run smoothly?"
    ],
    "BUSINESS_PLAN.16": [
        "What is the most efficient and cost-effective delivery method for your product/service?",
        "How will your delivery method enhance the customer experience?",
        "Are there any specific logistics or partnerships needed for your chosen delivery approach?"
    ],
    "BUSINESS_PLAN.17": [
        "Are there any immediate operational tasks not listed that are critical for launch?",
        "What human resources (staff, contractors) will you need from day one?",
        "How will you prioritize these operational needs given your current resources?"
    ],
    "BUSINESS_PLAN.18": [
        "What is the fundamental purpose of your business?",
        "What impact do you want your business to have on customers, employees, or the world?",
        "How do your core values guide your decisions and actions?"
    ],
    "BUSINESS_PLAN.19": [
        "Which marketing channels are most effective for reaching your target customer?",
        "What kind of content or messaging will resonate with your audience?",
        "How will you measure the success of your marketing efforts?"
    ],
    "BUSINESS_PLAN.20": [
        "What is your budget for marketing and sales efforts?",
        "What internal skills do you possess, and what external expertise might you need?",
        "How will you ensure consistent messaging across all your marketing and sales activities?"
    ],
    "BUSINESS_PLAN.21": [
        "Can you articulate your USP in a single, compelling sentence?",
        "Does your USP address a specific customer pain point or desire?",
        "Is your USP distinct, defensible, and difficult for competitors to copy?"
    ],
    "BUSINESS_PLAN.22": [
        "What launch activities will generate initial excitement and awareness?",
        "How will you track the effectiveness of your promotions?",
        "What resources (time, money, partnerships) are needed for these strategies?"
    ],
    "BUSINESS_PLAN.23": [
        "Are there any critical marketing efforts for launch not mentioned?",
        "What is your initial budget allocation for these marketing activities?",
        "How will you measure the immediate impact of your short-term marketing?"
    ],
    "BUSINESS_PLAN.24": [
        "Consider the implications of each structure for liability, taxation, and administrative burden.",
        "Does your chosen structure align with your long-term growth plans?",
        "Have you consulted with a legal or tax professional about this decision?"
    ],
    "BUSINESS_PLAN.25": [
        "Why is registering your business name an important first step?",
        "What are the next steps if you haven't registered it yet?",
        "Have you checked for name availability at the state and federal levels (e.g., USPTO)?"
    ],
    "BUSINESS_PLAN.26": [
        "Do these permits/licenses seem accurate for your industry and location?",
        "Are there any permits or licenses you've encountered that are not listed here?",
        "What is your plan for applying and obtaining these necessary permits/licenses?"
    ],
    "BUSINESS_PLAN.27": [
        "Do these insurance types cover the primary risks associated with your business?",
        "Are there any industry-specific insurance requirements not listed here?",
        "What steps will you take to obtain quotes and secure these policies?"
    ],
    "BUSINESS_PLAN.28": [
        "What systems or processes will you put in place to stay updated on regulations?",
        "Who will be responsible for overseeing legal and regulatory compliance?",
        "How will you document your compliance efforts?"
    ],
    "BUSINESS_PLAN.29": [
        "Which revenue streams are most viable given your product/service and target market?",
        "How will each revenue stream contribute to your overall profitability?",
        "Are there any alternative revenue models you've considered?"
    ],
    "BUSINESS_PLAN.30": [
        "Will you use cost-plus, value-based, competitive, or freemium pricing?",
        "How does your pricing align with your brand positioning and target customer's budget?",
        "Have you researched competitor pricing for similar products/services?"
    ],
    "BUSINESS_PLAN.31": [
        "Will you use accounting software, a bookkeeper, or an accountant?",
        "What financial reports will you regularly review (e.g., P&L, balance sheet, cash flow)?",
        "How will you separate business and personal finances?"
    ],
    "BUSINESS_PLAN.32": [
        "How much capital do you need to launch and operate for the first 6-12 months?",
        "What are the pros and cons of your chosen funding source(s)?",
        "What is your backup plan if your primary funding source falls through?"
    ],
    "BUSINESS_PLAN.33": [
        "What specific revenue targets do you aim to achieve?",
        "When do you realistically expect to break even?",
        "How will achieving these goals impact your business's growth and stability?"
    ],
    "BUSINESS_PLAN.34": [
        "Do these cost categories align with your expectations for starting the business?",
        "Are there any significant startup costs missing from this breakdown?",
        "How will you manage and optimize these costs in the early stages?"
    ],
    "BUSINESS_PLAN.35": [
        "What does 'scaling' mean for your specific business (e.g., more customers, new markets, expanded product lines)?",
        "What are the biggest challenges you anticipate in scaling, and how will you address them?",
        "What foundational elements do you need to put in place now to support future growth?"
    ],
    "BUSINESS_PLAN.36": [
        "Where do you envision your business being in terms of market position, revenue, and impact?",
        "What significant achievements define success for your business in the long term?",
        "How will these long-term goals guide your strategic decisions today?"
    ],
    "BUSINESS_PLAN.37": [
        "How will your current operations need to evolve to support your long-term vision?",
        "What infrastructure (physical or digital) will be necessary for future scale?",
        "How will you ensure operational efficiency as your business grows?"
    ],
    "BUSINESS_PLAN.38": [
        "What significant capital investments might be required for your long-term goals?",
        "How will you fund new product development, market expansion, or talent acquisition?",
        "What financial metrics will be key indicators of long-term health and growth?"
    ],
    "BUSINESS_PLAN.39": [
        "How do you plan to evolve your brand presence and market leadership over time?",
        "What new marketing channels or strategies might you explore in the future?",
        "How will you maintain customer loyalty and advocacy as your business scales?"
    ],
    "BUSINESS_PLAN.40": [
        "What new opportunities exist beyond your initial market?",
        "How will you adapt your approach for different markets?",
        "What research will you do before expanding to a new segment?"
    ],
    "BUSINESS_PLAN.41": [
        "How will you ensure ongoing legal and regulatory compliance as your business grows?",
        "What administrative systems will you need for efficient management at scale?",
        "Who will oversee these administrative functions as your business expands?"
    ],
    "BUSINESS_PLAN.42": [
        "What problems could slow your business down — finances, competition, or staffing?",
        "What can you do now to lower those risks?",
        "Who can you reach out to for advice or backup if something goes wrong?"
    ],
    "BUSINESS_PLAN.43": [
        "If your first plan doesn't work, what's your next option?",
        "How could you adjust your prices, audience, or services without starting over?",
        "What signs will tell you it's time to make a change or try a new approach?"
    ],
    "BUSINESS_PLAN.44": [
        "What specific needs would this additional funding address (e.g., R&D, market entry, talent)?",
        "What are potential funding sources (e.g., venture capital, angel investors, grants, debt)?",
        "What milestones would you need to achieve to attract investors or secure loans?"
    ],
    "BUSINESS_PLAN.45": [
        "What lasting impact do you want your business to have?",
        "Where would you like your business to be in 5 years?",
        "What kind of growth or reputation do you want to achieve?"
    ],
}

BUSINESS_PLAN_TAG_PATTERN = re.compile(
    r"\[\[Q:(BUSINESS_PLAN\.\d{2})\]\](.*?)(?=\n\s*\[\[Q:BUSINESS_PLAN|\n\s*---|\Z)",
    re.DOTALL,
)


@lru_cache(maxsize=1)
def load_business_plan_question_objectives() -> dict[str, str]:
    """Parse ANGEL_SYSTEM_PROMPT to extract canonical business plan prompts."""
    objectives: dict[str, str] = {}
    for match in BUSINESS_PLAN_TAG_PATTERN.finditer(ANGEL_SYSTEM_PROMPT):
        tag = match.group(1).strip()
        block = match.group(2)
        if not tag or not block:
            continue
        lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
        if not lines:
            continue
        normalized = transform_question_objective(" ".join(lines))
        objectives[tag] = normalized
    return objectives


def get_question_objective(tag: str) -> Optional[str]:
    if not tag:
        return None
    return load_business_plan_question_objectives().get(tag)

def get_thought_starter_for_tag(question_tag: str) -> Optional[str]:
    if not question_tag:
        return None
    starters = THOUGHT_STARTERS_BY_TAG.get(question_tag)
    if not starters:
        return None
    return starters[0]

def is_draft_or_support_response(response_text: str) -> bool:
    """Check if response is a draft or support command response"""
    # First check if this is a verification/summary (NOT a draft)
    verification_indicators = [
        "Does this look accurate",
        "Does this look correct",
        "Is this accurate",
        "Verification:",
        "Here's what I've captured so far"
    ]
    
    # If it's a verification message, it's NOT a draft
    if any(indicator in response_text for indicator in verification_indicators):
        return False
    
    # Check for actual draft/support indicators
    draft_indicators = [
        "Here's a draft",
        "Here's a research-backed draft",
        "Here's a draft based on",
        "Let's work through this together",
        "Here's a refined version",
        "I'll create additional content"
    ]
    return any(indicator in response_text for indicator in draft_indicators)

def is_moving_to_next_question(response_text: str) -> bool:
    """Check if response is transitioning to next question (should NOT show buttons)"""
    response_lower = response_text.lower()
    
    # FIRST: Check if this is a Draft/Support/Scrapping response
    # These should NEVER be considered as "moving to next question"
    draft_or_support_indicators = [
        "here's a draft",
        "here's a research-backed draft",
        "here's a draft based on",
        "let's work through this together",
        "here's a refined version",
        "i'll create additional content"
    ]
    
    if any(indicator in response_lower for indicator in draft_or_support_indicators):
        # This is a draft/support response - should ALWAYS show buttons
        return False
    
    # Patterns that indicate moving to next question
    transition_patterns = [
        "let's move forward",
        "let's move on",
        "let's move to the next",
        "let's continue",
        "moving on to",
        "ready to move on",
        "let's proceed",
        "moving forward"
    ]
    
    # Check if response has transition pattern
    has_transition = any(pattern in response_lower for pattern in transition_patterns)
    
    # Check if asking a new question (question mark near the end)
    lines = response_text.split('\n')
    last_lines = '\n'.join(lines[-5:])  # Check last 5 lines
    has_question_at_end = "?" in last_lines
    
    # It's moving to next question if has transition AND question at end
    return has_transition and has_question_at_end

async def should_show_accept_modify_buttons(ai_response: str, user_last_input: str = "", session_data: dict = None) -> dict:
    """Determine if Accept/Modify buttons should be shown"""
    user_input_lower = user_last_input.lower().strip()
    
    # Check if user explicitly requested Draft, Support, or Scrapping
    command_keywords = ["draft", "support", "scrapping", "scraping", "draft more"]
    is_command_request = user_input_lower in command_keywords
    
    # Check if response is a draft/support response
    is_draft_response = is_draft_or_support_response(ai_response)
    
    # Check if response is moving to next question
    is_next_question = is_moving_to_next_question(ai_response)
    
    # NEW: Check if user provided an answer in Business Planning phase
    is_business_plan = session_data and session_data.get("current_phase") == "BUSINESS_PLAN"
    is_user_answer = is_business_plan and not user_input_lower in ["accept", "modify", "ok", "okay", "yes", "no"] + command_keywords
    
    # Check if AI is acknowledging/capturing the answer (common patterns)
    acknowledgment_patterns = [
        "thank you",
        "thanks for",
        "great",
        "perfect",
        "excellent",
        "wonderful",
        "i've captured",
        "i've noted",
        "got it",
        "understood",
        "that's helpful",
        "appreciate",
        "makes sense"
    ]
    has_acknowledgment = any(pattern in ai_response.lower()[:200] for pattern in acknowledgment_patterns)
    
    # Check if AI is asking a new question (has [[Q: tag)
    has_question_tag = re.search(r'\[\[Q:[A-Z_]+\.\d+\]\]', ai_response) is not None
    
    # Check if AI explicitly requested Accept/Modify buttons
    has_accept_modify_tag = "[[ACCEPT_MODIFY_BUTTONS]]" in ai_response
    
    # Show buttons if:
        # 1. It's a command response (Draft/Support/Scrapping), OR
    # 2. User provided an answer in Business Plan AND AI acknowledged it AND hasn't moved to next question yet, OR
    # 3. It's a phase completion/transition (KYC completion, Business Plan completion, etc.)
    should_show = False
    
    # Check if this is a phase completion/transition
    is_phase_completion = (
        "congratulations" in ai_response.lower() and 
        ("completed" in ai_response.lower() or "completion" in ai_response.lower()) and
        ("phase" in ai_response.lower() or "profile" in ai_response.lower() or "plan" in ai_response.lower())
    )
    
    if has_accept_modify_tag:
        # AI explicitly requested Accept/Modify buttons (section summary, etc.)
        should_show = True
        reason = "AI requested Accept/Modify buttons"
    elif is_command_request or is_draft_response:
        # Only show buttons for Draft commands, not Support or Scrapping
        if user_input_lower == "draft":
            should_show = not is_next_question
            reason = "Draft command response"
        else:
            # Support and Scrapping commands should not show Accept/Modify buttons
            should_show = False
            reason = f"{user_input_lower.title()} command - guidance provided"
    elif is_phase_completion:
        # Show buttons for phase completions/transitions
        should_show = True
        reason = "Phase completion/transition"
    elif is_user_answer and has_acknowledgment and not has_question_tag:
        # Show when AI acknowledges answer but hasn't asked next question yet
        should_show = True
        reason = "Answer acknowledged in Business Plan"
    elif is_user_answer and len(user_last_input.strip()) > 10 and "[[Q:" in ai_response:
        # If AI immediately asks next question after answer, DON'T show buttons
        # (AI is moving forward - user already provided good answer)
        should_show = False
        reason = "Moving to next question immediately"
    else:
        reason = "Standard response"
    
    print(f"🔍 Button Detection:")
    print(f"  - User input: '{user_last_input[:50]}...'")
    print(f"  - Is command request: {is_command_request}")
    print(f"  - Is draft response: {is_draft_response}")
    print(f"  - Is next question: {is_next_question}")
    print(f"  - Is user answer (BP): {is_user_answer}")
    print(f"  - Has acknowledgment: {has_acknowledgment}")
    print(f"  - Has question tag: {has_question_tag}")
    print(f"  - Has accept/modify tag: {has_accept_modify_tag}")
    print(f"  - Is phase completion: {is_phase_completion}")
    print(f"  - Reason: {reason}")
    print(f"  - Should show buttons: {should_show}")
    
    return {
        "show_buttons": should_show,
        "content_length": len(ai_response)
    }

async def conduct_web_search(query, fast_mode: bool = False):
    """Conduct web search with citations from authoritative sources
    
    Args:
        query: Search query
        fast_mode: If True, use shorter timeout and simpler prompt for faster responses (default: False)
    """
    try:
        print(f"🔍 Conducting comprehensive web search: {query}")
        
        # Limit query length reasonably
        if len(query) > 150:
            query = query[:150] + "..."
        
        # Simplified prompt for fast mode
        if fast_mode:
            search_prompt = f"""Provide a quick, concise answer about: {query}

Include key points and current information (2024-2025). Keep response brief."""
            timeout = 5.0  # Shorter timeout for fast mode
            max_tokens = 400  # Shorter response
        else:
            # Enhanced search prompt with source citations
            search_prompt = f"""Search reputable websites including industry publications, government websites (.gov), 
academic sources (.edu), and authoritative business references for information about: {query}

Provide a comprehensive answer with:
    1. Key findings and data points
2. Current trends and statistics (2024-2025 where available)
3. Cite specific sources with URLs when possible
4. Include quantitative data when available

Format your response with clear sections and citations."""
            timeout = 10.0  # Longer timeout for thorough research
            max_tokens = 800  # Increased for comprehensive research
        
        response = await client.chat.completions.create(
            model="gpt-4o",  # Use full model for better research
            messages=[{
                "role": "user", 
                "content": search_prompt
            }],
            temperature=0.2,  # Lower temperature for factual accuracy
            max_tokens=max_tokens,
            timeout=timeout
        )
        
        # Extract search results from response
        search_results = response.choices[0].message.content
        print(f"✅ Web search completed for: {query[:50]}... (length: {len(search_results)} chars)")
        return search_results
    
    except Exception as e:
        print(f"❌ Web search error: {e}")
        return None

def truncate_to_word_limit(text: str, max_words: int) -> str:
    """
    Truncate text to a maximum number of words, preserving sentence boundaries when possible.
    Returns the truncated text with ellipsis if it was truncated.
    """
    if not text:
        return text
    
    words = text.split()
    if len(words) <= max_words:
        return text
    
    # Truncate to max_words
    truncated_words = words[:max_words]
    truncated_text = ' '.join(truncated_words)
    
    # Try to end on a sentence boundary (period, exclamation, question mark)
    # Look for the last sentence ending in the truncated text
    last_period = truncated_text.rfind('.')
    last_exclamation = truncated_text.rfind('!')
    last_question = truncated_text.rfind('?')
    last_sentence_end = max(last_period, last_exclamation, last_question)
    
    # If we found a sentence ending within the last 20% of the text, use it
    if last_sentence_end > len(truncated_text) * 0.8:
        truncated_text = truncated_text[:last_sentence_end + 1]
    
    # Add ellipsis if text was truncated
    if len(words) > max_words:
        truncated_text += '...'
    
    return truncated_text

def trim_conversation_history(history, max_messages=10):
    """Trim conversation history to prevent context from growing too large"""
    if len(history) <= max_messages:
        return history
    
    # Keep the most recent messages
    return history[-max_messages:]

def format_response_structure(reply):
    """Format AI responses to use proper structured format instead of paragraph form"""
    
    formatted_reply = reply
    
    # Check if this should be a dropdown question (Yes/No or multiple choice)
    is_yes_no_question = ("yes" in formatted_reply.lower() and "no" in formatted_reply.lower() and 
                         any(phrase in formatted_reply.lower() for phrase in ["have you", "do you", "are you", "would you"]))
    
    is_work_situation_question = "work situation" in formatted_reply.lower()
    
    is_multiple_choice_question = ("•" in formatted_reply or "○" in formatted_reply or 
                                  any(option in formatted_reply.lower() for option in ["full-time employed", "part-time", "student", "unemployed"]))
    
    # For dropdown questions, remove the options from the message
    if is_yes_no_question:
        # Remove Yes/No options
        formatted_reply = re.sub(r'\n\n• Yes\n• No', '', formatted_reply)
        formatted_reply = re.sub(r'\n• Yes\n• No', '', formatted_reply)
        formatted_reply = re.sub(r'\n\nYes / No', '', formatted_reply)
        formatted_reply = re.sub(r'\nYes / No', '', formatted_reply)
    
    elif is_work_situation_question:
        # Remove work situation options
        work_options_pattern = r'\n\n• Full-time employed\n• Part-time\n• Student\n• Unemployed\n• Self-employed/freelancer\n• Other'
        formatted_reply = re.sub(work_options_pattern, '', formatted_reply)
        
        # Also handle single-line format
        work_options_single_pattern = r'\n• Full-time employed\n• Part-time\n• Student\n• Unemployed\n• Self-employed/freelancer\n• Other'
        formatted_reply = re.sub(work_options_single_pattern, '', formatted_reply)
    
    elif is_multiple_choice_question and not is_yes_no_question:
        # Remove bullet point options for other multiple choice questions
        # Pattern: "Question?\n\n• Option1\n• Option2\n• Option3"
        multi_choice_pattern = r'([^?]+\?)\s*\n\n(• [^\n]+(?:\n• [^\n]+)*)'
        formatted_reply = re.sub(multi_choice_pattern, r'\1', formatted_reply)
        
        # Also handle single-line format
        multi_choice_single_pattern = r'([^?]+\?)\s*\n(• [^\n]+(?:\n• [^\n]+)*)'
        formatted_reply = re.sub(multi_choice_single_pattern, r'\1', formatted_reply)
        
        # Handle circle bullets (○) - remove these options too
        circle_choice_pattern = r'([^?]+\?)\s*\n\n(○ [^\n]+(?:\n○ [^\n]+)*)'
        formatted_reply = re.sub(circle_choice_pattern, r'\1', formatted_reply)
        
        # Also handle single-line format for circles
        circle_choice_single_pattern = r'([^?]+\?)\s*\n(○ [^\n]+(?:\n○ [^\n]+)*)'
        formatted_reply = re.sub(circle_choice_single_pattern, r'\1', formatted_reply)
    
    # Specific formatting for work situation question (if not already handled)
    if "work situation" in formatted_reply.lower() and "?" in formatted_reply and not is_work_situation_question:
        # Pattern: "What's your current work situation? Full-time employed Part-time Student Unemployed Self-employed/freelancer Other"
        work_pattern = r'([^?]+\?)\s+(Full-time employed\s+Part-time\s+Student\s+Unemployed\s+Self-employed/freelancer\s+Other)'
        formatted_reply = re.sub(work_pattern, 
            r'\1\n\n• Full-time employed\n• Part-time\n• Student\n• Unemployed\n• Self-employed/freelancer\n• Other', 
            formatted_reply)
    
    # Specific formatting for business before question
    if "business before" in formatted_reply.lower() and "?" in formatted_reply:
        # Pattern: "Have you started a business before? Yes / No"
        business_pattern = r'([^?]+\?)\s+(Yes\s*/\s*No)'
        formatted_reply = re.sub(business_pattern, r'\1\n\n• Yes\n• No', formatted_reply)
    
    # General pattern for Yes/No questions (if not already handled)
    if not is_yes_no_question:
        # Pattern: "Question? Yes / No" or "Question? Yes/No"
        yes_no_pattern = r'([^?]+\?)\s+(Yes\s*/\s*No)'
        formatted_reply = re.sub(yes_no_pattern, r'\1\n\n• Yes\n• No', formatted_reply)
    
    # General pattern for multiple choice questions (if not already handled)
    if not is_multiple_choice_question:
        # Pattern: "Question? Option1 Option2 Option3 Option4"
        multi_choice_pattern = r'([^?]+\?)\s+([A-Za-z\s]+(?:employed|time|Student|Unemployed|freelancer|Other)[^?]*)'
        formatted_reply = re.sub(multi_choice_pattern, 
            lambda m: f"{m.group(1)}\n\n• {m.group(2).replace(' ', ' • ')}", 
            formatted_reply)
    
    # Convert circle bullets to regular bullets for consistency
    formatted_reply = re.sub(r'○\s*', '• ', formatted_reply)
    
    # Clean up any double bullet points
    formatted_reply = re.sub(r'•\s*•\s*', '• ', formatted_reply)
    
    # Ensure proper spacing
    formatted_reply = re.sub(r'\n{3,}', '\n\n', formatted_reply)
    
    return formatted_reply

def ensure_question_separation(reply, session_data=None):
    """Ensure questions are properly separated and not combined"""
    
    # Check if this is a business plan question that might be combined
    if session_data and session_data.get("current_phase") == "BUSINESS_PLAN":
        # Look for patterns where multiple questions are combined
        combined_patterns = [
            # Pattern: "Question1? Question2?"
            (r'([^?]+\?)\s+([A-Z][^?]+\?)', r'\1\n\n\2'),
            # Pattern: "Question1. Question2?"
            (r'([^?]+\.)\s+([A-Z][^?]+\?)', r'\1\n\n\2'),
        ]
        
        for pattern, replacement in combined_patterns:
            reply = re.sub(pattern, replacement, reply)
    
    return reply

def validate_business_plan_sequence(reply, session_data=None):
    """Ensure business plan questions follow proper sequence"""
    
    if session_data and session_data.get("current_phase") == "BUSINESS_PLAN":
        asked_q = session_data.get("asked_q", "BUSINESS_PLAN.01")
        answered_count = session_data.get("answered_count", 0)
        
        # Extract current question number from tag
        tag_match = re.search(r'\[\[Q:BUSINESS_PLAN\.(\d+)\]\]', reply)
        if tag_match:
            current_q_num = int(tag_match.group(1))
            
            # Check if we're jumping ahead or backwards
            if "BUSINESS_PLAN." in asked_q:
                last_q_num = int(asked_q.split(".")[1])
                
                print(f"🔍 DEBUG - Question sequence check: last_q={last_q_num}, current_q={current_q_num}")
                
                # Handle jumping ahead (skipping questions)
                if current_q_num > last_q_num + 1:
                    print(f"⚠️ WARNING: Jumping ahead from question {last_q_num} to {current_q_num}")
                    # Force back to next sequential question
                    next_q = f"BUSINESS_PLAN.{last_q_num + 1:02d}"
                    reply = re.sub(r'\[\[Q:BUSINESS_PLAN\.\d+\]\]', f'[[Q:{next_q}]]', reply)
                    print(f"🔧 Corrected to: {next_q}")
                
                # Handle jumping backwards (going to previous questions)
                elif current_q_num < last_q_num:
                    print(f"⚠️ WARNING: Jumping backwards from question {last_q_num} to {current_q_num}")
                    # Force to next sequential question (don't go backwards)
                    next_q = f"BUSINESS_PLAN.{last_q_num + 1:02d}"
                    reply = re.sub(r'\[\[Q:BUSINESS_PLAN\.\d+\]\]', f'[[Q:{next_q}]]', reply)
                    print(f"🔧 Corrected backwards jump to: {next_q}")
                
                # Log normal progression
                elif current_q_num == last_q_num + 1:
                    print(f"✅ Normal progression: {last_q_num} → {current_q_num}")
                
                # Same question number is VALID because session updates before validation
                # This happens when: user answers Q35 → session updates to Q36 → AI generates Q36
                # The validation sees Q36 == Q36, which is correct!
                elif current_q_num == last_q_num:
                    print(f"✅ Correct question sequence: {current_q_num} (session already updated)")
                    # DO NOT force progression - this is correct behavior!

    return reply

def fix_verification_flow(reply, session_data=None):
    """Fix verification flow to separate verification from next question"""
    
    if session_data and session_data.get("current_phase") == "BUSINESS_PLAN":
        # Look for patterns where verification is combined with next question
        verification_patterns = [
            # Pattern: "Here's what I've captured... Does this look accurate? [Next question]"
            (r'(Here\'s what I\'ve captured so far:.*?Does this look accurate to you\?)\s+([A-Z][^?]+\?)', 
             r'\1\n\nPlease respond with "Accept" or "Modify" to continue.'),
            
            # Pattern: "Feel free to refine... What specific products..."
            (r'(Feel free to refine or expand on this as we continue\.)\s+([A-Z][^?]+\?)', 
             r'Does this information look accurate to you? If not, please let me know where you\'d like to modify and we\'ll work through this some more.\n\nPlease respond with "Accept" or "Modify" to continue.'),
        ]
        
        for pattern, replacement in verification_patterns:
            reply = re.sub(pattern, replacement, reply, flags=re.DOTALL)
        
        # Check if this is a verification message that should trigger Accept/Modify buttons
        # Only trigger for specific verification patterns, not general responses
        verification_keywords = [
            "does this look accurate to you",
            "does this look correct to you", 
            "is this accurate to you",
            "is this correct to you",
            "please let me know where you'd like to modify"
        ]
        
        # Only add Accept/Modify if it's explicitly a verification request
        if any(keyword in reply.lower() for keyword in verification_keywords):
            # Ensure it ends with proper instruction
            if "Please respond with \"Accept\" or \"Modify\"" not in reply:
                reply += "\n\nPlease respond with \"Accept\" or \"Modify\" to continue."
    
    return reply

def prevent_ai_molding(reply, session_data=None):
    """Prevent AI from molding user answers into mission, vision, USP without verification"""
    
    if session_data and session_data.get("current_phase") == "BUSINESS_PLAN":
        # Look for patterns where AI molds answers without verification
        molding_patterns = [
            # Pattern: AI creates mission, vision, USP from user input without asking
            (r'(Based on your input, here\'s what I\'ve created for you:.*?Mission:.*?Vision:.*?Unique Selling Proposition:.*?)([A-Z][^?]+\?)', 
             r'Here\'s what I\'ve captured so far: [summary]. Does this look accurate to you? If not, please let me know where you\'d like to modify and we\'ll work through this some more.\n\nPlease respond with "Accept" or "Modify" to continue.'),
            
            # Pattern: AI summarizes and immediately asks next question
            (r'(Great! Based on your answers, here\'s what I understand:.*?)([A-Z][^?]+\?)', 
             r'Here\'s what I\'ve captured so far: [summary]. Does this look accurate to you? If not, please let me know where you\'d like to modify and we\'ll work through this some more.\n\nPlease respond with "Accept" or "Modify" to continue.'),
        ]
        
        for pattern, replacement in molding_patterns:
            reply = re.sub(pattern, replacement, reply, flags=re.DOTALL)
        
        # Check if AI is molding without verification
        molding_keywords = [
            "based on your input, here's what i've created",
            "here's what i understand about your business",
            "let me create a mission statement for you",
            "based on your answers, here's your mission"
        ]
        
        if any(keyword in reply.lower() for keyword in molding_keywords):
            # Replace with proper verification request
            reply = "Here's what I've captured so far: [summary]. Does this look accurate to you? If not, please let me know where you'd like to modify and we'll work through this some more.\n\nPlease respond with \"Accept\" or \"Modify\" to continue."
    
    return reply

def suggest_draft_if_relevant(reply, session_data, user_input, history):
    """Suggest using Draft if user has already provided relevant information"""
    
    if not history or not user_input:
        return reply
    
    # Don't suggest draft in KYC phase
    if session_data and session_data.get("current_phase") == "KYC":
        return reply
    
    # Keywords that indicate the user might have already provided relevant information
    relevant_keywords = {
        'target audience': ['audience', 'customers', 'demographic', 'market', 'millennials', 'gen z', 'generation'],
        'business name': ['name', 'brand', 'company', 'business'],
        'products/services': ['product', 'service', 'offer', 'sell', 'provide'],
        'mission/vision': ['mission', 'vision', 'purpose', 'goal', 'objective'],
        'location': ['location', 'city', 'country', 'area', 'region'],
        'industry': ['industry', 'sector', 'field', 'business type'],
        'resources': ['resources', 'tools', 'equipment', 'staff', 'team', 'budget']
    }
    
    # Check if current question matches any of these categories
    current_question = reply.lower()
    relevant_category = None
    
    for category, keywords in relevant_keywords.items():
        if any(keyword in current_question for keyword in keywords):
            relevant_category = category
            break
    
    if relevant_category:
        # Check if user has provided information in this category before
        user_has_relevant_info = False
        
        # Check conversation history for relevant information
        for msg in history:
            if msg.get('role') == 'user' and len(msg.get('content', '')) > 10:
                user_content = msg['content'].lower()
                if any(keyword in user_content for keyword in relevant_keywords[relevant_category]):
                    user_has_relevant_info = True
                    break
        
        # Check for various tip patterns that might already exist
        tip_patterns = [
            "💡 Quick Tip:",
            "💡 **Quick Tip**:",
            "💡 **Pro Tip**:",
            "💡 Quick tip:",
            "💡 **Quick tip**:",
            "💡 **Pro tip**:",
            "Quick Tip:",
            "**Quick Tip**:",
            "**Pro Tip**:",
            "Quick tip:",
            "**Quick tip**:",
            "**Pro tip**:"
        ]
        
        has_existing_tip = any(pattern in reply for pattern in tip_patterns)
        
        if user_has_relevant_info and not has_existing_tip:
            # Add suggestion to use Draft
            draft_suggestion = f"\n\n💡 **Quick Tip**: Based on some info you've previously entered, you can also select **\"Draft\"** and I'll use that information to create a draft answer for you to review and save you some time."
            reply += draft_suggestion
    
    return reply

def check_for_section_summary(current_tag, session_data, history):
    """Check if we need to provide a section summary based on the current question tag
    
    TIMING: This checks if user just ANSWERED a section-ending question.
    It should trigger AFTER user answers Q4, Q8, Q12, Q17, Q25, Q31, Q37, Q41, or Q45.
    """
    
    if not current_tag or not current_tag.startswith("BUSINESS_PLAN."):
        return None
    
    try:
        question_num = int(current_tag.split(".")[1])
    except (ValueError, IndexError):
        return None
    
    # Define section boundaries - these are the LAST questions in each section
    # When user answers these questions, we show a section summary BEFORE moving to next section
    section_boundaries = {
        4: "SECTION 1 SUMMARY REQUIRED: After BUSINESS_PLAN.04, provide:",
        8: "SECTION 2 SUMMARY REQUIRED: After BUSINESS_PLAN.08, provide:",
        12: "SECTION 3 SUMMARY REQUIRED: After BUSINESS_PLAN.12, provide:",
        17: "SECTION 4 SUMMARY REQUIRED: After BUSINESS_PLAN.17, provide:",
        25: "SECTION 5 SUMMARY REQUIRED: After BUSINESS_PLAN.25, provide:",
        31: "SECTION 6 SUMMARY REQUIRED: After BUSINESS_PLAN.31, provide:",
        37: "SECTION 7 SUMMARY REQUIRED: After BUSINESS_PLAN.37, provide:",
        41: "SECTION 8 SUMMARY REQUIRED: After BUSINESS_PLAN.41, provide:",
        45: "SECTION 9 SUMMARY REQUIRED: After BUSINESS_PLAN.45, provide:"
    }
    
    # Check if we're at a section boundary
    if question_num in section_boundaries:
        print(f"✅ SECTION SUMMARY TRIGGERED: User just answered Q{question_num}, showing {get_section_name(question_num)} section summary")
        return {
            "trigger_question": question_num,
            "summary_type": section_boundaries[question_num],
            "section_name": get_section_name(question_num)
        }
    
    return None

def get_section_name(question_num):
    """Get the section name based on question number"""
    section_names = {
        4: "Business Foundation",
        8: "Product/Service Details", 
        12: "Market Research",
        17: "Location & Operations",
        25: "Financial Planning",
        31: "Marketing & Sales",
        37: "Legal & Compliance",
        41: "Growth & Scaling",
        45: "Risk Management"
    }
    return section_names.get(question_num, "Unknown Section")

async def add_critiquing_insights(reply, session_data=None, user_input=None):
    """Add critiquing insights and coaching based on user's business field (50/50 approach)"""
    
    if not user_input or not session_data:
        return reply
    
    business_keywords = {
        "social media": ["social media", "instagram", "tiktok", "youtube", "influencer", "content creator", "short-form videos"],
        "food": ["restaurant", "food", "cooking", "chef", "culinary", "dining", "beverage"],
        "technology": ["app", "software", "tech", "digital", "online", "platform", "website", "mobile", "saas", "ai", "pos"],
        "retail": ["store", "shop", "retail", "product", "selling", "ecommerce", "marketplace"],
        "services": ["service", "consulting", "coaching", "training", "professional", "agency", "provider"],
        "health": ["health", "fitness", "wellness", "medical", "therapy", "nutrition"],
        "education": ["education", "teaching", "learning", "course", "training", "tutorial"],
        "entertainment": ["entertainment", "music", "art", "creative", "media", "video", "content"]
    }
    
    user_input_lower = user_input.lower()
    identified_field = None
    
    for field, keywords in business_keywords.items():
        if any(keyword in user_input_lower for keyword in keywords):
            identified_field = field
            break
    
    if not identified_field:
        return reply

    insight = await generate_dynamic_critiquing_insight(identified_field, session_data, user_input)
    if not insight:
        return reply

    lines = reply.split('\n')
    for i, line in enumerate(lines):
        if '?' in line and len(line.strip()) > 10:
            lines.insert(i, f"\n{insight.strip()}\n")
            break
    
    enriched = '\n'.join(lines)
    return remove_duplicate_paragraphs(enriched)

def identify_support_areas(session_data, history):
    """Proactively identify areas where the entrepreneur needs the most support based on KYC and business plan answers"""
    
    if not session_data or not history:
        return None
    
    # Analyze conversation history for gaps and areas needing support
    support_areas = []
    
    # Check for common areas that need support
    conversation_text = " ".join([msg.get('content', '') for msg in history if msg.get('role') == 'user'])
    conversation_lower = conversation_text.lower()
    
    # Financial planning support
    if any(keyword in conversation_lower for keyword in ['budget', 'funding', 'money', 'cost', 'price', 'financial']):
        if not any(keyword in conversation_lower for keyword in ['detailed financial', 'financial projections', 'break even', 'revenue model']):
            support_areas.append("Financial Planning & Projections")
    
    # Market research support
    if any(keyword in conversation_lower for keyword in ['market', 'customers', 'competition', 'target']):
        if not any(keyword in conversation_lower for keyword in ['market research', 'competitive analysis', 'customer demographics', 'market size']):
            support_areas.append("Market Research & Competitive Analysis")
    
    # Operations support
    if any(keyword in conversation_lower for keyword in ['business', 'operations', 'process', 'staff']):
        if not any(keyword in conversation_lower for keyword in ['operational plan', 'staffing plan', 'processes', 'systems']):
            support_areas.append("Operations & Process Planning")
    
    # Legal/compliance support
    if any(keyword in conversation_lower for keyword in ['legal', 'license', 'permit', 'regulation', 'compliance']):
        if not any(keyword in conversation_lower for keyword in ['business structure', 'licenses required', 'legal requirements']):
            support_areas.append("Legal Structure & Compliance")
    
    # Marketing support
    if any(keyword in conversation_lower for keyword in ['marketing', 'sales', 'customers', 'brand']):
        if not any(keyword in conversation_lower for keyword in ['marketing strategy', 'sales process', 'brand positioning', 'customer acquisition']):
            support_areas.append("Marketing & Sales Strategy")
    
    # Technology support
    if any(keyword in conversation_lower for keyword in ['technology', 'software', 'website', 'digital', 'online']):
        if not any(keyword in conversation_lower for keyword in ['technology requirements', 'digital tools', 'software needs']):
            support_areas.append("Technology & Digital Tools")
    
    return support_areas

def compact_educational_content(reply):
    """Compact educational content with labels and bullet points"""
    if not reply:
        return reply
    
    # Remove "Areas Where You May Need Additional Support" section completely
    reply = re.sub(r'\n\n\*\*🎯 Areas Where You May Need Additional Support:\*\*\n.*?Consider using \'Support\'.*?\n', '', reply, flags=re.DOTALL)
    reply = re.sub(r'\n\n🎯 Areas Where You May Need Additional Support:.*?Consider using \'Support\'.*?\n', '', reply, flags=re.DOTALL)
    reply = re.sub(r'Based on your responses, I\'ve identified these areas where you might benefit from deeper guidance:.*?Consider using \'Support\'.*?\n', '', reply, flags=re.DOTALL)
    
    # Compact spacing between educational paragraphs (reduce excessive spacing)
    # Replace 3+ newlines with 2, but preserve spacing around Thought Starter and Quick Tip
    lines = reply.split('\n')
    compacted_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip().lower()
        
        # Preserve Thought Starter and Quick Tip sections with proper spacing
        if 'thought starter' in stripped or 'quick tip' in stripped or 'pro tip' in stripped:
            # Ensure blank line before Thought Starter/Quick Tip if not present
            if compacted_lines and compacted_lines[-1].strip():
                compacted_lines.append('')
            compacted_lines.append(line)
            i += 1
            continue
        
        # Skip excessive blank lines (more than 1 consecutive blank line)
        if not line.strip():
            if compacted_lines and not compacted_lines[-1].strip():
                i += 1
                continue
        
        compacted_lines.append(line)
        i += 1
    
    reply = '\n'.join(compacted_lines)
    
    # Clean up remaining excessive spacing (3+ newlines to 2)
    reply = re.sub(r'\n{3,}', '\n\n', reply)
    
    return reply

def add_proactive_support_guidance(reply, session_data, history):
    """Add proactive support guidance based on identified areas needing help"""
    
    # REMOVED: "Areas Where You May Need Additional Support" section per user request
    # Only preserve Thought Starter and Quick Tip sections
    
    # Remove any existing "Areas Where You May Need Additional Support" content
    reply = compact_educational_content(reply)
    
    return reply

def ensure_proper_question_formatting(reply, session_data=None):
    """Ensure questions are properly formatted with line breaks and structure"""
    
    # Look for patterns where questions are not properly formatted
    formatting_patterns = [
        # Pattern: Yes/No questions without proper formatting
        (r'([^?]+\?)\s+(Yes\s*/\s*No)', r'\1\n\n• Yes\n• No'),
        # Pattern: Question without proper line breaks
        (r'([^?]+\?)\s+([A-Z][^?]+)', r'\1\n\n\2'),
        # Pattern: Multiple choice options without proper formatting
        (r'([^?]+\?)\s+([A-Z][^?]+(?:employed|time|Student|Unemployed|freelancer|Other)[^?]*)', 
         r'\1\n\n• \2'),
    ]
    
    for pattern, replacement in formatting_patterns:
        reply = re.sub(pattern, replacement, reply)
    
    # Compact educational content (remove "Areas Where You May Need Additional Support", reduce spacing)
    reply = compact_educational_content(reply)
    
    reply = apply_business_plan_thought_starter(reply, session_data)
    
    return reply

async def personalize_business_question(reply: str, history, session_data=None) -> str:
    """Personalize Business Plan questions with the user's business context while keeping tags and numbering intact"""
    if not reply or "[[Q:" not in reply:
        return reply
    
    tag_match = re.search(r'\[\[Q:(BUSINESS_PLAN\.\d{2})\]\]', reply)
    if not tag_match:
        return reply
    
    question_tag = tag_match.group(1)
    
    lines = reply.split("\n")
    
    # Find first question line after the tag
    question_start_idx = 0
    tag_token = tag_match.group(0)
    for idx, line in enumerate(lines):
        if tag_token in line:
            question_start_idx = idx
            break
    
    REMOVAL_SENTINEL = "__REMOVE_LINE__"
    question_indices = []
    for idx in range(question_start_idx + 1, len(lines)):
        stripped = lines[idx].strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("💡") or lower.startswith("🧠 thought starter") or lower.startswith("💭 thought starter"):
            break
        if "thought starter" in lower and "🧠" in lower:
            break
        if lower.startswith("consider") or lower.startswith("think about") or lower.startswith("note:") or \
           "consider:" in lower or "think about:" in lower or "note:" in lower:
            lines[idx] = REMOVAL_SENTINEL
            continue
        if "[[q:" in lower:
            continue
        if "?" in stripped:
            question_indices.append(idx)
        elif len(question_indices) > 0:
            # Stop once we move past the question block
            break
    
    if not question_indices:
        return "\n".join(line for line in lines if line != REMOVAL_SENTINEL)
    
    primary_question_idx = question_indices[0]
    for extra_idx in question_indices[1:]:
        lines[extra_idx] = REMOVAL_SENTINEL
    
    context_phrase = None
    try:
        business_context = extract_business_context_from_history(history)
    except Exception as exc:
        print(f"⚠️ Failed to extract business context for personalization: {exc}")
        business_context = {}
    
    business_name = business_context.get("business_name")
    industry = business_context.get("industry")
    location = business_context.get("location")
    business_type = business_context.get("business_type")
    
    base_context = business_name or ""
    descriptors = []
    
    if business_type and business_type.lower() not in ["business", "your business"]:
        descriptors.append(business_type)
    if industry and industry.lower() not in ["business", "general"]:
        descriptors.append(f"{industry} industry")
    if location:
        descriptors.append(location)
    
    descriptor_text = ", ".join(descriptors)
    if base_context and descriptor_text:
        context_phrase = f"{base_context} ({descriptor_text})"
    elif base_context:
        context_phrase = base_context
    elif descriptor_text:
        context_phrase = descriptor_text
    
    use_context_prefix = context_phrase and context_phrase.lower() not in ["business", "your business", "general"]
    
    recent_user_answer = extract_recent_user_answer(history)
    
    async def personalize_sentence(sentence: str) -> str:
        sentence_clean = sentence.strip()
        if not sentence_clean:
            return sentence
        
        dynamic_question = await get_dynamic_business_question(question_tag, business_context, recent_user_answer)
        
        if dynamic_question:
            sentence_clean = dynamic_question.strip()
        else:
            if use_context_prefix:
                already_personalized = (
                    context_phrase.lower() in sentence_clean.lower() or
                    sentence_clean.lower().startswith("for ")
                )
                
                if not already_personalized and sentence_clean:
                    lowered_impl = sentence_clean[0].lower() + sentence_clean[1:] if sentence_clean[0].isalpha() else sentence_clean
                    sentence_clean = f"For {context_phrase}, {lowered_impl}"
        
        sentence_clean = sentence_clean.strip()
        sentence_clean = re.sub(r'^\*\*(.+?)\*\*$', r'\1', sentence_clean)
        sentence_clean = re.sub(r'<[^>]+>', '', sentence_clean)
        if not sentence_clean.endswith('?'):
            sentence_clean = f"{sentence_clean.rstrip('.')}?"
        question_text = re.sub(r'\s+', ' ', sentence_clean).strip()
        if not question_text:
            return ""
        return f"\n\n**{question_text}**\n\n"
    
    lines[primary_question_idx] = await personalize_sentence(lines[primary_question_idx])
    
    formatted_lines = []
    for line in lines:
        if line == REMOVAL_SENTINEL:
            continue
        if "<strong>" in line and formatted_lines and formatted_lines[-1].strip():
            formatted_lines.append("")
        formatted_lines.append(line)
    
    return "\n".join(formatted_lines)

async def get_dynamic_business_question(question_tag: str, context: dict, recent_answer: str = "") -> Optional[str]:
    """Return a dynamically phrased question tailored to the business context"""
    if not question_tag:
        return None
    
    def fmt(value: Optional[str], fallback: str) -> str:
        value = (value or "").strip()
        return value if value else fallback
    
    business = fmt(context.get("business_name"), "your business")
    industry_raw = (context.get("industry") or "").strip()
    industry_descriptor = f"{industry_raw} industry" if industry_raw else "your industry"
    
    location_raw = (context.get("location") or "").strip()
    location_phrase = f"in {location_raw}" if location_raw else ""
    location_only = location_raw if location_raw else "your market"
    
    target_market = fmt(context.get("target_market"), "your target market")
    business_type = fmt(context.get("business_type"), "business")
    offering = fmt(context.get("business_idea") or context.get("core_offering"), f"{industry_descriptor} offering")
    
    recent_excerpt = build_recent_answer_excerpt(recent_answer)
    
    launch_context_bits = []
    if location_only and location_only not in {"your market"}:
        launch_context_bits.append(f"in {location_only}")
    if target_market and target_market != "your target market":
        launch_context_bits.append(f"for {target_market}")
    launch_context = " ".join(launch_context_bits).strip()
    
    objective = get_question_objective(question_tag)
    dynamic_question = None
    
    if objective:
        try:
            dynamic_question = await generate_question_with_model(
                question_tag=question_tag,
                objective=objective,
                business=business,
                industry=industry_descriptor,
                location=location_raw,
                target_market=target_market,
                business_type=business_type,
                offering=offering,
                recent_excerpt=recent_excerpt
            )
        except Exception as exc:
            print(f"⚠️ Dynamic question generation failed for {question_tag}: {exc}")
    
    if dynamic_question:
        return dynamic_question
    
    fallback_question = build_fallback_question(
        question_tag,
        objective,
        business,
        industry_descriptor,
        location_phrase,
        location_only,
        target_market,
        business_type,
        offering,
        recent_excerpt,
        launch_context
    )
    return fallback_question

def extract_recent_user_answer(history: list[dict]) -> str:
    if not history:
        return ""
    
    command_words = {"draft", "support", "scrapping", "scraping", "accept", "modify", "draft more", "skip", "next"}
    
    for msg in reversed(history):
        if msg.get("role") != "user":
            continue
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if content.lower() in command_words:
            continue
        return content
    return ""

def build_recent_answer_excerpt(answer: str, max_length: int = 160) -> str:
    if not answer:
        return ""
    cleaned = answer.replace("\n", " ").strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length - 3].rstrip() + "..."
    return cleaned

def apply_business_plan_thought_starter(reply: str, session_data=None) -> str:
    """Inject a single thought starter for Business Plan questions and remove default guidance"""
    if not reply:
        return reply
    
    # Determine question tag
    question_tag = None
    tag_match = re.search(r'\[\[Q:(BUSINESS_PLAN\.\d{2})\]\]', reply)
    if tag_match:
        question_tag = tag_match.group(1)
    elif session_data:
        asked_q = session_data.get("asked_q")
        if asked_q and asked_q.startswith("BUSINESS_PLAN."):
            question_tag = asked_q
    
    if not question_tag:
        return reply
    
    thought_starter = get_thought_starter_for_tag(question_tag)
    if not thought_starter:
        return reply
    
    # Remove existing guidance lines (Catch plain Thought Starter, Consider, Think about)
    cleaned_lines = []
    for line in reply.split('\n'):
        stripped = line.strip().lower()
        # Remove lines with "Consider:" or "Think about:" in any format
        if (stripped.startswith("• consider:") or 
            stripped.startswith("consider:") or
            stripped.startswith("• think about:") or 
            stripped.startswith("think about:") or
            stripped.startswith("• note:") or
            stripped.startswith("thought starter:") or
            " consider:" in stripped or "think about:" in stripped or "thought starter" in stripped):
            continue
        cleaned_lines.append(line)
    
    # Avoid duplicates if already present after cleanup
    if any("🧠 Thought Starter:" in line for line in cleaned_lines):
        return '\n'.join(cleaned_lines)
    
    insertion_line = f"🧠 Thought Starter: {thought_starter}"
    
    # Locate where to insert (before quick tips or end)
    insert_index = len(cleaned_lines)
    for idx, line in enumerate(cleaned_lines):
        if line.strip().startswith("💡"):
            insert_index = idx
            break
    
    # Ensure blank line separation
    if insert_index > 0 and cleaned_lines[insert_index - 1].strip() != "":
        cleaned_lines.insert(insert_index, "")
        insert_index += 1
    
    cleaned_lines.insert(insert_index, insertion_line)
    
    return '\n'.join(cleaned_lines)

def inject_missing_tag(reply, session_data=None):
    """Inject a tag if the AI forgot to include one"""
    # Check if reply already has a tag
    if "[[Q:" in reply:
        return reply
    
    # Check if this is a command response (Draft, Support, Scrapping) - don't inject tags for these
    # Also includes verification messages that should stay on same question
    command_indicators = [
        "Here's a draft for you",
        "Here's a draft based on what you've shared",
        "Let's work through this together",
        "Here's a refined version of your thoughts",
        "I'll create additional content for you",
        "Verification:",
        "Here's what I've captured so far",
        "Does this look accurate",
        "Does this look correct"
    ]
    
    if any(indicator in reply for indicator in command_indicators):
        # This is a command response, don't inject a tag - stay on current question
        return reply
    
    # Check if this is a guidance/reminder message (e.g., "I understand you'd like to move forward")
    # These should get the CURRENT question tag, not the next one
    guidance_indicators = [
        "I understand you'd like to move forward",
        "it's important that we complete each question",
        "We're currently on",
        "Let's continue with the current question",
        "Please provide an answer to the current question"
    ]
    
    is_guidance_message = any(indicator in reply for indicator in guidance_indicators)
    
    # Determine the question number to inject
    current_phase = "KYC"  # Default
    question_num = "01"    # Default
    current_asked_q = "KYC.01"  # Default
    
    if session_data:
        current_phase = session_data.get("current_phase", "KYC")
        current_asked_q = session_data.get("asked_q", "KYC.01")
        if "." in current_asked_q:
            phase, num = current_asked_q.split(".")
            current_phase = phase
            if is_guidance_message:
                # For guidance messages, use CURRENT question (don't increment)
                question_num = num
            else:
                # For new questions, INCREMENT to get the NEXT question number
                try:
                    next_num = int(num) + 1
                    question_num = f"{next_num:02d}"  # Format as 01, 02, 03, etc.
                except (ValueError, TypeError):
                    question_num = num  # Fallback to current if parsing fails
    
    # If this is a guidance message without a question, inject CURRENT question tag at the end
    if is_guidance_message and "?" not in reply:
        tag = f"[[Q:{current_asked_q}]]"
        # Add tag at the end of the reply
        return f"{reply}\n\n{tag}"
    
    # If this looks like a question (contains ?), inject a tag with NEXT question number
    if "?" in reply and len(reply.strip()) > 10:
        tag = f"[[Q:{current_phase}.{question_num}]]"
        # Insert tag at the beginning of the first sentence that contains a question
        lines = reply.split('\n')
        for i, line in enumerate(lines):
            if '?' in line and len(line.strip()) > 10:
                # Clean up the line and add tag
                clean_line = line.strip()
                lines[i] = f"{tag} {clean_line}"
                break
        return '\n'.join(lines)
    
    return reply

async def handle_kyc_completion(session_data, history):
    """
    Handle the transition from KYC completion to Business Planning Exercise
    This is the missing transition that introduces the Business Planning phase
    """
    
    # Generate KYC summary insights
    kyc_summary = await generate_kyc_summary(session_data, history)
    
    # Create the comprehensive transition message based on the DOCX document
    transition_message = f"""🎉 **CONGRATULATIONS! You've officially completed the full Business Planning Phase with Angel inside Founderport!**

You've defined your entrepreneurial profile and shared valuable insights about your experience, goals, and preferences — an incredible milestone in your entrepreneurial journey.

## **🧭 Recap of Your Accomplishments**

{kyc_summary}

Angel now has everything needed to guide you through creating your comprehensive business plan.

## **⚙️ What Happens Next: Business Planning Phase**

Your completed entrepreneurial profile will now be used to create a fully personalized business planning experience. Here's what we'll build together:

**Your business plan will include:**

✅ A fully defined mission and vision statement
✅ Market positioning, customer segments, and competitive differentiation
✅ Clear pricing and financial projections
✅ Comprehensive marketing, legal, and operational frameworks
✅ Scalable growth and risk management strategies

**How Angel Will Help:**

📊 **Background Research** - I'll conduct research automatically to provide you with industry insights, competitive analysis, and market data

💡 **Support** - When you're unsure or want deeper guidance on any question

✍️ **Scrapping** - When you have rough ideas that need polishing

📝 **Draft** - When you want me to create complete responses based on what I've learned about your business

🎯 **Proactive Guidance** - I'll provide both supportive encouragement and constructive coaching at every step

## **🎯 Before We Continue**

The Business Planning phase is comprehensive and detailed. This ensures your final business plan is thorough and provides you with a strong starting point for launching your business. The more detailed answers you provide, the better I can help support you to bring your business to life.

**"The best way to predict the future is to create it."** – Peter Drucker

## **Ready to Move Forward?**

Once you're ready, we'll begin the Business Planning phase where we'll dive deep into every aspect of your business idea — from your product and market to finances and growth strategy.

**Let's build the business of your dreams together!**

*"The way to get started is to quit talking and begin doing."* – Walt Disney"""
    
    # Check if we should show Accept/Modify buttons
    button_detection = await should_show_accept_modify_buttons(
        user_last_input="KYC completion",
        ai_response=transition_message,
        session_data=session_data
    )
    
    return {
        "reply": transition_message,
        "transition_phase": "KYC_TO_BUSINESS_PLAN",
        "patch_session": {
            "current_phase": "BUSINESS_PLAN_INTRO",  # Intermediate phase before actual questions
            "asked_q": "KYC.20_ACK",  # Keep on KYC until user confirms ready
            "answered_count": session_data.get("answered_count", 0)
        },
        "show_accept_modify": button_detection.get("show_buttons", False),
        "awaiting_confirmation": True  # Signal that we need user to confirm before starting questions
    }

async def generate_kyc_summary(session_data, history):
    """Generate a summary of KYC insights for the transition"""
    # Extract key KYC answers from history
    kyc_insights = []
    
    for msg in history:
        if msg.get('role') == 'assistant' and '[[Q:KYC.' in msg.get('content', ''):
            # This is a KYC question - look for the answer
            question_content = msg.get('content', '')
            # Try to find corresponding user answer in history
            for user_msg in history:
                if user_msg.get('role') == 'user':
                    answer = user_msg.get('content', '').strip()
                    if len(answer) > 10 and answer.lower() not in ['support', 'draft', 'scrapping', 'accept', 'modify']:
                        kyc_insights.append(answer[:150])  # Take first 150 chars of each answer
    
    # Generate summary using the last few meaningful insights
    recent_insights = kyc_insights[-5:] if kyc_insights else []
    
    if not recent_insights:
        return """**Your Entrepreneurial Profile Summary:**

✓ You're ready to take a proactive approach to building your business
✓ You've shared valuable insights about your experience, goals, and preferences
✓ You're prepared to dive deep into the business planning process"""
    
    # Create formatted summary
    summary = "**Your Entrepreneurial Profile Summary:**\n\n"
    
    # Add insights
    if session_data.get('business_name'):
        summary += f"✓ **Business Name**: {session_data.get('business_name')}\n"
    if session_data.get('industry'):
        summary += f"✓ **Industry**: {session_data.get('industry')}\n"
    if session_data.get('location'):
        summary += f"✓ **Location**: {session_data.get('location')}\n"
    if session_data.get('business_experience'):
        summary += f"✓ **Experience Level**: {session_data.get('business_experience')}\n"
    
    summary += "✓ You've completed your full entrepreneurial profile with detailed insights\n"
    summary += "✓ You're ready to transform your vision into a comprehensive business plan"
    
    return summary

async def handle_business_plan_completion(session_data, history):
    """Handle the transition from Business Plan completion to Roadmap phase"""
    
    # Generate comprehensive business plan summary FIRST (fast, no web searches)
    print("📋 Generating Business Plan Summary (fast, immediate response)...")
    business_plan_summary = await generate_business_plan_summary(session_data, history)
    
    # Return immediately with summary - generate artifact in background (non-blocking)
    # ✅ PROPER ARCHITECTURE: No background generation
    # Artifact will be generated ON-DEMAND when user clicks "View Full Business Plan"
    # This eliminates race conditions, polling, and provides reliable user experience
    # See endpoint: POST /sessions/{session_id}/generate-business-plan-artifact
    print("✅ Returning summary immediately. Artifact will be generated on-demand.")
    
    # No artifact in initial response - user will request it when needed
    business_plan_artifact = None
    
    # Create the transition message - Show summary first, then budget, then roadmap
    transition_message = f"""🎉 **CONGRATULATIONS! Planning Champion Award** 🎉

You've successfully completed your comprehensive business plan! This is a significant milestone in your entrepreneurial journey.

---

## Business Plan Summary Overview

**Note:** This is a high-level summary of your comprehensive Business Plan. Your complete Business Plan Artifact is being generated in the background and will be available shortly.

{business_plan_summary}

---

## **Ready to Move Forward?**

Please review your business plan summary above. If everything looks accurate and complete, you can:

**Continue** - Proceed to budget planning, then roadmap generation
**Modify** - Adjust any aspects that need refinement

What would you like to do?"""

    # Check if we should show Accept/Modify buttons for Business Plan completion
    button_detection = await should_show_accept_modify_buttons(
        user_last_input="Business Plan completion",
        ai_response=transition_message,
        session_data=session_data
    )

    return {
        "reply": transition_message,
        "web_search_status": {"is_searching": False, "query": None},
        "immediate_response": None,
        "transition_phase": "PLAN_TO_SUMMARY",  # Show summary first, then budget, then roadmap
        "business_plan_summary": business_plan_summary,
        "business_plan_artifact": business_plan_artifact,  # Include the full artifact in the response
        "show_accept_modify": button_detection.get("show_buttons", False),
        "reference_documents": [
            "Business Plan Deep Research Questions V2",
            "Roadmap Deep Research Questions V3"
        ],
        "patch_session": {
            # Don't save artifact in patch_session - it's being generated in background
            # Will be saved when background task completes
        }
    }

async def handle_budget_setup(session_data, history):
    """Handle the transition from Business Plan to Budget phase"""
    
    # Extract business context
    business_name = session_data.get("business_name") or session_data.get("business_idea_brief", "your business")
    industry = session_data.get("industry", "your industry")
    location = session_data.get("location", "your location")
    business_type = session_data.get("business_type", "service")
    
    # Generate estimated expenses based on business plan
    estimated_expenses = await generate_estimated_expenses_from_business_plan(session_data, history)
    
    # Create budget setup message
    budget_message = f"""💰 **Budget Planning Time!** 💰

Great work completing your business plan! Now let's create a comprehensive budget for your business.

Based on your business plan for **{business_name}** in the **{industry}** industry, I've prepared an estimated budget breakdown for Year 1.

---

## 📊 **Initial Investment**

Before we dive into the budget details, I need to know:

**What is the total initial investment you're planning to put into your business?**

This includes all sources of funding:
- Personal savings
- Loans
- Investments from partners
- Grants or other funding sources

---

## 💡 **Estimated Expenses (Based on Your Business Plan)**

I've analyzed your business plan and prepared estimated expenses for Year 1. These are tailored to your **{industry}** business in **{location}**:

{estimated_expenses}

---

## 🎯 **What's Next**

Once you provide your initial investment amount, I'll:
1. Show you a detailed budget breakdown with estimated expenses and revenues
2. Allow you to adjust amounts using sliders
3. Let you add custom expenses or revenue sources
4. Display your budget in a pie chart or table format
5. Save this budget so I can reference it throughout our conversation

**Ready to set up your budget?** Please let me know your total initial investment amount, and we'll proceed with the detailed budget setup!"""

    return {
        "reply": budget_message,
        "transition_phase": "BUDGET_SETUP",
        "estimated_expenses": estimated_expenses,
        "business_context": {
            "business_name": business_name,
            "industry": industry,
            "location": location,
            "business_type": business_type
        }
    }

async def generate_estimated_expenses_from_business_plan(session_data, history):
    """Generate estimated expenses based on business plan context using AI"""
    
    business_name = session_data.get("business_name") or session_data.get("business_idea_brief", "your business")
    industry = session_data.get("industry", "your industry")
    location = session_data.get("location", "your location")
    business_type = session_data.get("business_type", "service")
    
    # Extract relevant business plan information from history
    business_plan_context = ""
    if history:
        # Get last 20 messages for context
        recent_messages = history[-20:] if len(history) > 20 else history
        business_plan_context = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')[:500]}"
            for msg in recent_messages
        ])
    
    prompt = f"""You are a financial planning expert. Based on the following business plan information, generate a realistic list of estimated monthly expenses for Year 1.

BUSINESS CONTEXT:
- Business Name: {business_name}
- Industry: {industry}
- Location: {location}
- Business Type: {business_type}

BUSINESS PLAN INFORMATION:
{business_plan_context[:3000]}

REQUIREMENTS:
1. Generate 6-10 realistic expense categories specific to this {industry} business
2. Provide monthly estimated amounts (in USD) appropriate for {location}
3. Include industry-specific expenses (e.g., inventory for retail, equipment for manufacturing, licenses for regulated industries)
4. Adjust amounts based on location cost of living
5. Format as a clear list with category names and estimated monthly amounts

FORMAT YOUR RESPONSE AS:
- **Category Name 1**: $X,XXX/month - Brief description
- **Category Name 2**: $X,XXX/month - Brief description
- etc.

Be specific to {industry} and realistic for {location}. Include common expenses like:
- Rent/Office Space (if applicable)
- Salaries/Staffing
- Marketing & Advertising
- Utilities
- Software & Technology
- Insurance
- Legal & Accounting
- Inventory/Supplies (if applicable)
- Equipment/Maintenance (if applicable)
- Other industry-specific expenses

Return ONLY the formatted list, no additional text."""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a financial planning expert specializing in startup budgets."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        
        estimated_expenses = response.choices[0].message.content.strip()
        return estimated_expenses
    except Exception as e:
        print(f"Error generating estimated expenses: {e}")
        # Fallback to generic expenses
        return f"""Based on your {industry} business in {location}, here are typical Year 1 monthly expenses:

- **Rent/Office Space**: $1,500-$3,000/month - Office or retail space rental
- **Salaries/Staffing**: $3,000-$8,000/month - Employee wages and benefits
- **Marketing & Advertising**: $500-$2,000/month - Marketing campaigns and promotions
- **Utilities**: $200-$500/month - Electricity, water, internet, phone
- **Software & Technology**: $200-$800/month - Software licenses and tech tools
- **Insurance**: $300-$600/month - Business insurance premiums
- **Legal & Accounting**: $200-$500/month - Legal and accounting services
- **Inventory/Supplies**: $500-$2,000/month - Product inventory or supplies
- **Equipment/Maintenance**: $200-$1,000/month - Equipment purchase and maintenance"""

async def generate_business_plan_summary(session_data, history):
    """Generate a comprehensive summary of the business plan"""
    
    # Extract key information from session data and history
    summary_sections = []
    
    # Business Foundation
    if session_data.get("business_idea_brief"):
        summary_sections.append(f"**Business Idea:** {session_data.get('business_idea_brief')}")
    
    if session_data.get("business_type"):
        summary_sections.append(f"**Business Type:** {session_data.get('business_type')}")
    
    if session_data.get("industry"):
        summary_sections.append(f"**Industry:** {session_data.get('industry')}")
    
    if session_data.get("location"):
        summary_sections.append(f"**Location:** {session_data.get('location')}")
    
    if session_data.get("motivation"):
        summary_sections.append(f"**Motivation:** {session_data.get('motivation')}")
    
    # Extract additional information from conversation history
    user_responses = [msg.get('content', '') for msg in history if msg.get('role') == 'user']
    conversation_text = ' '.join(user_responses)
    
    # Generate AI-powered summary
    summary_prompt = f"""
    Create a comprehensive business plan summary based on the following information:
    
    Session Data: {session_data}
    Conversation History: {conversation_text[:2000]}  # Limit to avoid token limits
    
    Provide a structured summary that includes:
    1. Business Overview
    2. Target Market
    3. Products/Services
    4. Business Model
    5. Key Strategies
    6. Financial Considerations
    7. Next Steps
    
    CRITICAL FORMATTING REQUIREMENTS:
    - Use markdown headers (## or ###) for section headers, NOT bold asterisks
    - Section headers should be formatted as: ## Section Name (not **Section Name**)
    - Numbered sections should be: ### 1. Section Name (not **1. Section Name**)
    - Use **bold** only for emphasis within paragraphs, NOT for section headers
    - Example: ## Business Overview (correct) vs **Business Overview** (incorrect)
    
    Make it professional and comprehensive, highlighting the key decisions and milestones achieved.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.6,
            max_tokens=800  # Reduced for faster generation
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating business plan summary: {e}")
        return "Business plan summary generation in progress..."

def provide_critiquing_feedback(user_msg, session_data, history):
    """
    Provide constructive critique and challenging feedback to push for deeper thinking
    
    ROOT CAUSE FIX: Made critique validation much more intelligent
    - Only triggers on ACTUALLY vague/unrealistic answers
    - Requires multiple indicators, not just one word
    - Checks context to avoid false positives
    - Minimum length requirement increased
    """
    # Don't critique simple yes/no answers or short responses
    if not user_msg or len(user_msg.strip()) < 20:
        return None
    
    user_msg_lower = user_msg.lower()
    
    # Check for GENUINELY vague answers - need multiple indicators AND short length
    vague_indicators = ["maybe", "i think", "not sure", "don't know", "possibly", "i guess"]
    vague_count = sum(1 for indicator in vague_indicators if indicator in user_msg_lower)
    
    # Only critique if MULTIPLE vague indicators AND answer is still short (< 100 chars)
    if vague_count >= 2 and len(user_msg.strip()) < 100:
        return {
            "reply": f"I notice some uncertainty in your response. Let me challenge you to think deeper: What specific research have you done to support this? What are the concrete steps you're considering? What potential obstacles do you foresee, and how would you address them?",
            "web_search_status": {"is_searching": False, "query": None, "completed": False}
        }
    
    # Check for GENUINELY unrealistic assumptions - need context, not just keywords
    # These phrases indicate unrealistic thinking ONLY when used in specific contexts
    unrealistic_phrases = [
        "it will be easy",
        "this is simple",
        "guaranteed success",
        "definitely will work",
        "no competition",
        "everyone will buy",
        "instant profit"
    ]
    
    # Only critique if we find ACTUAL unrealistic claims, not just the word "easy" or "simple"
    if any(phrase in user_msg_lower for phrase in unrealistic_phrases):
        return {
            "reply": f"While I appreciate your confidence, I want to challenge some assumptions here. What data or experience supports this outlook? What's your contingency plan if things don't go as expected? What potential obstacles should we consider?",
            "web_search_status": {"is_searching": False, "query": None, "completed": False}
        }
    
    # No critique needed - answer is substantive
    return None

def validate_question_answer(user_msg, session_data, history):
    """
    Enhanced validation with critiquing behaviors - challenge superficial answers
    and push for deeper thinking and specificity.
    Validate that user is not trying to skip questions in KYC and Business Plan phases
    """
    if not session_data:
        return None
    
    current_phase = session_data.get("current_phase", "")
    asked_q = session_data.get("asked_q", "")
    
    # Don't validate during initial startup (when asked_q is empty or initial)
    if not asked_q or asked_q in ["", "KYC.01", "BUSINESS_PLAN.01"]:
        return None
    
    # Only validate for KYC and Business Plan phases
    if current_phase not in ["KYC", "BUSINESS_PLAN"]:
        return None
    
    # Extract content from user_msg (could be dict or string)
    if isinstance(user_msg, dict):
        user_content = user_msg.get("content", "")
    else:
        user_content = str(user_msg)
    
    # Check if user is trying to use commands to skip questions
    user_msg_lower = user_content.lower().strip()
    
    # Commands that are allowed (these don't skip questions, they help answer them)
    # In KYC phase, disable all helper commands to force direct answers
    if current_phase == "KYC":
        blocked_commands = ["draft", "support", "scrapping:", "kickstart", "who do i contact?"]
        
        # Block these commands in KYC phase
        if any(user_msg_lower.startswith(cmd) for cmd in blocked_commands):
            # CRITICAL: Include the current question tag so the system knows what question to display
            return {
                "reply": f"""I understand you'd like to use helper tools, but during the KYC phase, it's important that you provide direct answers to help me understand your background and goals.

Please provide a direct answer to the current question. This will help me personalize your experience and provide the most relevant guidance for your specific situation.

The helper tools (Draft, Support, Scrapping, Kickstart, Contact) will be available in the Business Planning phase where they can be more helpful for complex business questions.

For now, please share your thoughts directly about the current question.

[[Q:{asked_q}]]""",
                "web_search_status": {"is_searching": False, "query": None, "completed": False}
            }
    else:
        # In Business Planning phase, only allow Draft, Support, and Scrapping
        if current_phase == "BUSINESS_PLAN":
            allowed_commands = ["draft", "support", "scrapping:"]
        # In Implementation phase, allow all commands including Kickstart and Contact
        elif current_phase == "IMPLEMENTATION":
            allowed_commands = ["draft", "support", "scrapping:", "kickstart", "who do i contact?"]
        else:
            allowed_commands = ["draft", "support", "scrapping:"]
        
        # If user is using an allowed command, let them proceed
        if any(user_msg_lower.startswith(cmd) for cmd in allowed_commands):
            return None
    
    # REMOVED: Skip detection validation - let the AI model handle this naturally through its prompts
    # The AI model is trained to handle skip attempts and guide users appropriately
    # Hardcoded validation was blocking valid answers that happened to contain words like "next"
    
    # Check if user is asking clarifying questions about the current question (these are allowed)
    clarifying_questions = [
        "what question", "what is the question", "what do you want to know", "what should i answer",
        "what are you asking", "what is this question about", "can you repeat the question",
        "what do you need to know", "what information do you need", "what should i tell you"
    ]
    
    if any(clarifying_question in user_msg_lower for clarifying_question in clarifying_questions):
        # Allow clarifying questions - these help users understand what to answer
        return None
    
    # Check if user is trying to ask unrelated questions instead of answering
    unrelated_question_indicators = ["what is ai", "tell me about", "explain", "how does", "can you tell me about"]
    
    if user_msg_lower.endswith("?") and any(indicator in user_msg_lower for indicator in unrelated_question_indicators):
        # Create phase-specific message
        if current_phase == "KYC":
            help_message = """Please provide a direct answer to help me understand your situation better."""
        else:
            help_message = """If you need help with the current question, you can use:
- **Support** - for guided help with the question
- **Draft** - for me to help create an answer based on what you've shared so far
- **Scrapping** - to refine and polish your existing text"""
        
        return {
            "reply": f"""I appreciate your question! However, right now we're in the {current_phase} phase where I'm gathering information about you and your business to provide personalized guidance.

I'd be happy to answer your question once we complete the current question. For now, please provide an answer to help me understand your situation better.

{help_message}

Let's focus on answering the current question first.""",
            "web_search_status": {"is_searching": False, "query": None, "completed": False}
        }
    
    # Check if user is providing rating responses to non-rating questions
    if current_phase == "KYC":
        # Check if this looks like a rating response (numbers separated by commas)
        rating_pattern = r'^\d+,\s*\d+,\s*\d+,\s*\d+,\s*\d+,\s*\d+,\s*\d+$'
        if re.match(rating_pattern, user_content.strip()):
            # Only allow rating responses for KYC.07 (skills rating question)
            if asked_q != "KYC.07":
                return {
                    "reply": f"""I see you've provided a rating response, but the current question is asking about something different.

We're currently on question {asked_q.split('.')[1] if '.' in asked_q else 'unknown'} which asks: "{asked_q.replace('KYC.', '')}"

Please provide an answer that directly addresses the current question instead of rating responses.""",
                    "web_search_status": {"is_searching": False, "query": None, "completed": False}
                }
    
    # Check for very short or empty responses that might indicate skipping
    if len(user_content.strip()) < 3 and user_msg_lower not in ["yes", "no", "y", "n", "ok", "okay"]:
        # Different messages for KYC vs other phases
        if current_phase == "KYC":
            return {
                "reply": f"""I need a bit more information to help you effectively. Please provide a more detailed answer to the current question.

The more information you share, the better I can tailor my guidance to your specific situation and needs.

Please provide a more detailed response to continue.""",
                "web_search_status": {"is_searching": False, "query": None, "completed": False}
            }
        else:
            return {
                "reply": f"""I need a bit more information to help you effectively. Please provide a more detailed answer to the current question.

The more information you share, the better I can tailor my guidance to your specific situation and needs.

If you're unsure how to answer, you can use:
- **Support** - for guided help with the question
- **Draft** - for me to help create an answer based on what you've shared so far
- **Scrapping** - to refine and polish your existing text

Please provide a more detailed response to continue.""",
                "web_search_status": {"is_searching": False, "query": None, "completed": False}
            }
    
    return None

def validate_session_state(session_data, history):
    """Validate session state integrity to prevent question skipping"""
    if not session_data:
        return None
    
    current_phase = session_data.get("current_phase", "")
    asked_q = session_data.get("asked_q", "")
    answered_count = session_data.get("answered_count", 0)
    
    # Don't validate during initial startup (when asked_q is empty or initial)
    if not asked_q or asked_q in ["", "KYC.01", "BUSINESS_PLAN.01"]:
        return None
    
    # Only validate for KYC and Business Plan phases
    if current_phase not in ["KYC", "BUSINESS_PLAN"]:
        return None
    
    # Calculate expected answered count based on history
    expected_answered_count = len([pair for pair in history if pair.get("answer", "").strip()])
    
    # Check if answered_count is significantly behind (indicating skipped questions)
    # Only trigger if there's a major discrepancy (more than 2 questions behind)
    if answered_count < expected_answered_count - 2:
        # Create phase-specific message
        if current_phase == "KYC":
            help_message = """Please provide a complete answer to the current question so we can continue building your comprehensive business plan."""
        else:
            help_message = """If you need help with the current question, you can use:
- **Support** - for guided help with the question
- **Draft** - for me to help create an answer based on what you've shared so far
- **Scrapping** - to refine and polish your existing text"""
        
        # CRITICAL: Include the current question tag so the system knows what question to display
        return {
            "reply": f"""I notice there might be a discrepancy in our conversation history. To ensure I can provide you with the most accurate and personalized guidance, we need to make sure we've properly addressed all questions.

We're currently in the {current_phase} phase. Please provide a complete answer to the current question so we can continue building your comprehensive business plan.

Your detailed responses are essential for creating a tailored business strategy that addresses your specific needs and goals.

{help_message}

Let's continue with the current question.

[[Q:{asked_q}]]""",
            "web_search_status": {"is_searching": False, "query": None, "completed": False}
        }
    
    # Validate that asked_q is in the correct format and sequence
    if current_phase == "KYC":
        if not asked_q.startswith("KYC.") and asked_q != "KYC.19_ACK":
            return {
                "reply": f"""I need to ensure we're following the proper KYC sequence. Please provide an answer to the current KYC question so we can continue systematically building your business profile.

Each question in the KYC phase is designed to help me understand your background, experience, and goals. Skipping questions would prevent me from providing you with the most relevant and personalized guidance.

Please provide a detailed answer to the current question. This will help me personalize your experience and provide the most relevant guidance for your specific situation.

Let's continue with the current KYC question.""",
                "web_search_status": {"is_searching": False, "query": None, "completed": False}
            }
    
    elif current_phase == "BUSINESS_PLAN":
        if not asked_q.startswith("BUSINESS_PLAN."):
            return {
                "reply": f"""I need to ensure we're following the proper Business Plan sequence. Please provide an answer to the current business planning question so we can continue systematically developing your business strategy.

Each question in the Business Plan phase is designed to help create a comprehensive and actionable business plan tailored to your specific situation. Skipping questions would result in an incomplete plan that doesn't address all the necessary aspects of your business.

Please provide a detailed answer to the current question.

If you need help, you can use:
- **Support** - for guided help with the question
- **Draft** - for me to help create an answer based on what you've shared so far

Let's continue with the current business planning question.""",
                "web_search_status": {"is_searching": False, "query": None, "completed": False}
            }
    
    return None

async def get_angel_reply(user_msg, history, session_data=None):
    import time
    start_time = time.time()
    
    # Get user name from session data, fallback to generic greeting
    user_name = session_data.get("user_name", "there") if session_data else "there"
    
    # Get user preferences including feedback intensity (0-10)
    feedback_intensity = 5  # Default to moderate
    try:
        if session_data and session_data.get("user_id"):
            from services.preferences_service import get_user_preferences
            user_prefs = await get_user_preferences(session_data.get("user_id"))
            feedback_intensity = user_prefs.get("feedback_intensity", 5)
            print(f"🔍 DEBUG - User feedback intensity: {feedback_intensity}/10")
    except Exception as e:
        logger.warning(f"Could not fetch user preferences for feedback intensity: {e}")
        feedback_intensity = 5  # Default to moderate
    
    # KYC completion check removed - now triggered immediately after final answer
    
    # DISABLED: Question validation - let the AI model handle skip attempts and flow naturally
    # The AI model is trained to guide users appropriately without hardcoded validation blocking
    # validation_result = validate_question_answer(user_msg, session_data, history)
    # if validation_result:
    #     return validation_result
    
    # Debug logging for session state
    if session_data:
        print(f"🔍 DEBUG - Session State: phase={session_data.get('current_phase')}, asked_q={session_data.get('asked_q')}, answered_count={session_data.get('answered_count')}")
    
    # DISABLED: Session state validation - let the AI model handle flow naturally
    # session_validation = validate_session_state(session_data, history)
    # if session_validation:
    #     print(f"🔍 DEBUG - Session validation triggered: {session_validation.get('reply', '')[:100]}...")
    #     return session_validation
    
    # Define formatting instruction at the top to avoid UnboundLocalError
    # Get current phase and question info for Business Plan numbering
    current_phase = session_data.get("current_phase", "KYC") if session_data else "KYC"
    asked_q = session_data.get("asked_q", "KYC.01") if session_data else "KYC.01"
    
    # Get feedback intensity guidance text
    intensity_guidance = _get_feedback_intensity_guidance(feedback_intensity)
    
    # DISABLED: Critiquing feedback was too aggressive and causing false positives
    # Words like "faster" in "scale faster" were triggering unrealistic assumptions check
    # if user_msg and user_msg.get("content"):
    #     critique_feedback = provide_critiquing_feedback(user_msg["content"], session_data, history)
    #     if critique_feedback:
    #         print(f"🔍 DEBUG - Critiquing feedback triggered: {critique_feedback.get('reply', '')[:100]}...")
    #         return critique_feedback
    
    FORMATTING_INSTRUCTION = f"""
CRITICAL FORMATTING RULES - FOLLOW EXACTLY:

1. ALWAYS start with a brief acknowledgment (1-2 sentences max)
2. Add a blank line for visual separation
3. Present the question in a clear, structured format

IMPORTANT: The UI automatically displays "Question X" - DO NOT include question numbers in your response!

For YES/NO questions:
"That's great, {user_name}!

Have you started a business before?"

For multiple choice questions:
"That's perfect, {user_name}!

What's your current work situation?"

NOTE: Do NOT list option bullets in your message. The UI displays clickable option buttons.

For rating questions:
"That's helpful, {user_name}!

How comfortable are you with business planning?"

❌ NEVER LIST OPTIONS IN YOUR MESSAGE: 
"What's your current work situation? • Full-time • Part-time • Student..."
"Will your business be primarily: • Online • Brick-and-mortar • Mix of both"

✅ CORRECT - ASK CLEANLY WITHOUT OPTIONS: 
"What's your current work situation?"
"Will your business be primarily?"

CRITICAL: The UI displays option buttons automatically. Do NOT include option lists in your message text.

BUSINESS PLAN SPECIFIC RULES:
• Ask ONE question at a time in EXACT sequential order
• Each question must be on its own line with proper spacing
• NEVER mold user answers into mission, vision, USP without explicit verification
• Do NOT list option bullets in your message - UI shows clickable buttons for multiple-choice questions
• Start with BUSINESS_PLAN.01 and proceed sequentially
• Do NOT jump to later questions or combine multiple questions
• Do NOT provide section summaries or verification steps - just ask the next question
• When user answers, acknowledge briefly (1-2 sentences) and immediately ask the next question
• NEVER include "Question X" in your response - the UI shows it automatically

CONSTRUCTIVE FEEDBACK SYSTEM (INTENSITY: {feedback_intensity}/10):
Purpose: Reality checks plus actionable guidance to strengthen the user's answer, assumptions, and overall business.

GLOBAL GUARDRAILS (ALWAYS ON):
• Critique assumptions, not the founder
• Pair every risk or weakness with specific improvement guidance
• Frame feedback as optimization, not correction
• Never insult, dismiss, or condescend
• Emphasize learning, validation, and iteration

{intensity_guidance}

KEY DESIGN PRINCIPLE (CRITICAL):
Every critique must end with a way forward. Never leave the user thinking "This won't work" or "I'm doing this wrong." Instead, they should feel "Here's how to make this stronger" or "I know what to do next."

Do NOT include question numbers, progress percentages, or step counts in your response.
"""
    
    # Handle empty input based on context - preserve current phase state
    # BUT FIRST check if this might be a jump request (even if empty, check session metadata)
    if not user_msg.get("content") or user_msg["content"].strip() == "":
        # Check if session has missing questions metadata (from uploaded plan)
        # Get from business_context JSON
        business_context = session_data.get("business_context", {}) or {} if session_data else {}
        uploaded_plan_mode = business_context.get("uploaded_plan_mode", False) if isinstance(business_context, dict) else False
        missing_questions = business_context.get("missing_questions", []) if isinstance(business_context, dict) else []
        
        if session_data and uploaded_plan_mode and session_data.get("current_phase") == "BUSINESS_PLAN":
            try:
                if isinstance(missing_questions, list) and len(missing_questions) > 0:
                    first_missing = min(missing_questions)
                    target_tag = f"BUSINESS_PLAN.{first_missing:02d}"
                    print(f"🎯 Empty message but session has missing questions - jumping to Q{first_missing}")
                    
                    # Generate dynamic question for missing information
                    reply_content = await generate_dynamic_business_question(
                        target_tag, 
                        session_data, 
                        history,
                        is_missing_question=True
                    )
                    
                    # Update business_context
                    business_context["missing_questions"] = missing_questions
                    business_context["uploaded_plan_mode"] = True
                    
                    return {
                        "reply": reply_content,
                        "web_search_status": {"is_searching": False, "query": None},
                        "immediate_response": None,
                        "patch_session": {
                            "current_phase": "BUSINESS_PLAN",
                            "asked_q": target_tag,
                            "business_context": business_context  # Store in business_context JSON
                        }
                    }
            except Exception as e:
                print(f"⚠️ Error checking missing questions from session: {e}")
        
        # Get current phase to maintain state on refresh
        current_phase = session_data.get("current_phase", "KYC") if session_data else "KYC"
        
        # If we're in ROADMAP or PLAN_TO_ROADMAP_TRANSITION phase, maintain that state
        if current_phase in ["ROADMAP", "PLAN_TO_ROADMAP_TRANSITION", "ROADMAP_TO_IMPLEMENTATION_TRANSITION"]:
            # Return a message indicating the user is in the roadmap phase
            return {
                "reply": "🗺️ **Your Launch Roadmap is Ready!**\n\nYour business plan has been completed and your comprehensive 8-stage launch roadmap has been generated. The roadmap modal should open automatically to display your personalized roadmap with all stages and tasks.\n\nIf the roadmap modal doesn't appear, please refresh the page or click the 'View Roadmap' button if available.",
                "web_search_status": {"is_searching": False, "query": None},
                "immediate_response": None,
                "patch_session": None
            }
        
        elif current_phase in ["IMPLEMENTATION", "ROADMAP_GENERATED"]:
            return {
                "reply": "You're already in the implementation workspace. Continue working through your roadmap tasks or use the interface controls to navigate steps—no new questions are needed right now.",
                "web_search_status": {"is_searching": False, "query": None},
                "immediate_response": None,
                "patch_session": None
            }
        
        # If we're in BUSINESS_PLAN phase, continue with current question
        elif current_phase == "BUSINESS_PLAN":
            current_tag = session_data.get("asked_q", "BUSINESS_PLAN.01")
            if current_tag and current_tag.startswith("BUSINESS_PLAN."):
                # Generate dynamic, context-aware question
                return await generate_dynamic_business_question(current_tag, session_data, history)
        
        # Default to "hi" for KYC or initial phases
        user_msg["content"] = "hi"

    user_content = user_msg["content"].strip()
    print(f"🚀 Starting Angel reply generation for: {user_content[:100]}...")
    
    # Check if user wants to start from a specific question (from uploaded plan analysis)
    # This MUST happen early, before any other processing
    # Try multiple patterns to catch variations
    start_from_question_match = None
    patterns = [
        r'start from question (\d+)',
        r'start.*question (\d+)',
        r'jump.*question (\d+)',
        r'begin.*question (\d+)',
        r'skip.*question (\d+)',  # Added for skip functionality
        r'skip to (\d+)',  # Added for skip functionality (simpler pattern)
    ]
    
    for pattern in patterns:
        match = re.search(pattern, user_content.lower())
        if match:
            start_from_question_match = match
            print(f"🔍 Found pattern match: '{pattern}' -> question {match.group(1)}")
            break
    
    if not start_from_question_match:
        print(f"🔍 No 'start from question' pattern found in: '{user_content[:100]}'")
    
    if start_from_question_match and session_data:
        target_question_num = int(start_from_question_match.group(1))
        current_phase = session_data.get("current_phase", "BUSINESS_PLAN")
        
        print(f"🎯 Jump request detected: target_question={target_question_num}, current_phase={current_phase}")
        
        # Force phase to BUSINESS_PLAN if we're jumping to a business plan question
        if 1 <= target_question_num <= 45:
            if current_phase != "BUSINESS_PLAN":
                print(f"⚠️ Phase mismatch - forcing to BUSINESS_PLAN (was {current_phase})")
                session_data["current_phase"] = "BUSINESS_PLAN"
                current_phase = "BUSINESS_PLAN"
        
        if current_phase == "BUSINESS_PLAN" and 1 <= target_question_num <= 45:
            # Extract missing questions list from message
            missing_questions = []
            missing_match = re.search(r'missing questions:\s*([\d,\s]+)', user_content.lower())
            if missing_match:
                missing_str = missing_match.group(1)
                missing_questions = [int(q.strip()) for q in missing_str.split(',') if q.strip().isdigit()]
            else:
                # Fallback: get from business_context JSON
                business_context = session_data.get("business_context", {}) or {}
                if isinstance(business_context, dict):
                    missing_questions = business_context.get("missing_questions", [])
                else:
                    missing_questions = []
            
            # Store missing questions in business_context for tracking
            business_context = session_data.get("business_context", {}) or {}
            if not isinstance(business_context, dict):
                business_context = {}
            business_context["missing_questions"] = missing_questions
            business_context["uploaded_plan_mode"] = True
            session_data["business_context"] = business_context
            
            # Update session to start from this question
            target_tag = f"BUSINESS_PLAN.{target_question_num:02d}"
            session_data["asked_q"] = target_tag
            print(f"🎯 Jump/Skip detected: Starting from question {target_question_num}")
            print(f"📋 Missing questions to answer: {missing_questions if missing_questions else 'None (direct skip for testing)'}")
            
            # Generate dynamic question for missing information
            reply_content = await generate_dynamic_business_question(
                target_tag, 
                session_data, 
                history,
                is_missing_question=True
            )
            
            # Store missing questions in business_context JSON
            business_context = session_data.get("business_context", {}) or {}
            if not isinstance(business_context, dict):
                business_context = {}
            business_context["missing_questions"] = missing_questions
            business_context["uploaded_plan_mode"] = True
            
            return {
                "reply": reply_content,
                "web_search_status": {"is_searching": False, "query": None},
                "immediate_response": None,
                "patch_session": {
                    "current_phase": "BUSINESS_PLAN",  # Ensure phase is set
                    "asked_q": target_tag,
                    "business_context": business_context  # Store in business_context JSON
                }
            }
    
    # Check if user just answered the final KYC question BEFORE generating AI response
    if session_data and session_data.get("current_phase") == "KYC":
        current_tag = session_data.get("asked_q", "")
        if current_tag and current_tag.startswith("KYC."):
            try:
                question_num = int(current_tag.split(".")[1])
                # Check if user just answered the final question (19) with any response
                if (question_num >= 19 and 
                    not current_tag.endswith("_ACK") and
                    len(user_content.strip()) > 0):
                    
                    print(f"🎯 User answered final KYC question ({question_num}) - triggering completion immediately BEFORE AI response")
                    # Trigger completion immediately after acknowledgment
                    return await handle_kyc_completion(session_data, history)
            except (ValueError, IndexError):
                pass
    
    # CRITICAL: Check if Business Plan phase is complete (question 45) BEFORE AI generation
    # This must happen early to prevent AI from generating its own completion message
    if session_data and session_data.get("current_phase") == "BUSINESS_PLAN":
        current_tag = session_data.get("asked_q", "")
        
        # Also check the last assistant message to see if it asked question 45
        last_assistant_tag = None
        for msg in reversed(history[-5:]):
            if msg.get('role') == 'assistant':
                content = msg.get('content', '')
                tag_match = re.search(r'\[\[Q:(BUSINESS_PLAN\.\d+)\]\]', content)
                if tag_match:
                    last_assistant_tag = tag_match.group(1)
                    break
        
        # Also check if we've answered 45 questions based on progress
        answered_count = session_data.get("answered_count", 0)
        business_plan_complete = False
        
        # Check both current_tag and last_assistant_tag to catch question 45
        tags_to_check = [current_tag]
        if last_assistant_tag:
            tags_to_check.append(last_assistant_tag)
        
        for tag in tags_to_check:
            if tag and tag.startswith("BUSINESS_PLAN."):
                try:
                    question_num = int(tag.split(".")[1])
                    # Check if user just answered the final question (45) with any response
                    # Also check if we're at question 45 or beyond (in case of uploaded plans)
                    if question_num >= 45:
                        business_plan_complete = True
                        break
                except (ValueError, IndexError) as e:
                    print(f"⚠️ Error parsing question number from tag {tag}: {e}")
                    pass
        
        # Also check if we've answered enough questions (45 total for business plan)
        # This is a more reliable check than just tag parsing
        if not business_plan_complete:
            # Count business plan questions answered from history
            bp_questions_answered = 0
            for msg in history:
                if msg.get('role') == 'assistant':
                    content = msg.get('content', '')
                    # Count all BUSINESS_PLAN question tags
                    bp_tags = re.findall(r'\[\[Q:(BUSINESS_PLAN\.\d+)\]\]', content)
                    if bp_tags:
                        for bp_tag in bp_tags:
                            try:
                                q_num = int(bp_tag.split(".")[1])
                                if q_num <= 45:
                                    bp_questions_answered = max(bp_questions_answered, q_num)
                            except (ValueError, IndexError):
                                pass
            
            # If we've seen question 45 in history and user is providing input, consider it complete
            if bp_questions_answered >= 45 and len(user_content.strip()) > 0:
                business_plan_complete = True
                print(f"🎯 Detected business plan completion via history: {bp_questions_answered} questions answered")
        
        # Trigger completion if business plan is complete
        if (business_plan_complete and 
            len(user_content.strip()) > 0 and
            user_content.lower().strip() not in ["draft", "support", "scrapping", "scraping", "accept"]):
            
            print(f"🎯 Business Plan completion detected - triggering completion handler IMMEDIATELY (before AI generation)")
            print(f"   Current asked_q: {current_tag}, Last assistant tag: {last_assistant_tag}, Answered count: {answered_count}")
            # Trigger budget transition immediately - this will return the proper transition response
            completion_response = await handle_business_plan_completion(session_data, history)
            print(f"✅ Completion handler returned transition_phase: {completion_response.get('transition_phase')}")
            return completion_response
    
    # Accept command should be handled by AI naturally, not manually
    # Let the system prompt in constant.py guide question progression
    
    # Add instruction for proper question formatting
    
    # Check if web search is needed based on session phase and content
    needs_web_search = False
    web_search_query = None
    competitor_research_requested = False
    
    # CRITICAL: Prevent roadmap generation from chat input
    # Roadmap should ONLY be generated via the /transition-decision endpoint (modal Continue button)
    if session_data and session_data.get("current_phase") == "PLAN_TO_ROADMAP_TRANSITION":
        if user_content.lower().strip() in ["continue", "approve", "yes", "proceed"]:
            return {
                "reply": "Please use the 'Continue' button in the Business Plan Summary modal to proceed to roadmap generation. The modal should be displayed above this chat.",
                "web_search_status": {"is_searching": False, "query": None},
                "immediate_response": None,
                "transition_phase": None
            }
    
    # Check for WEBSEARCH_QUERY trigger from scrapping command
    if "WEBSEARCH_QUERY:" in user_content:
        needs_web_search = True
        web_search_query = user_content.split("WEBSEARCH_QUERY:")[1].strip()
        print(f"🔍 Web search triggered by scrapping command: {web_search_query}")
    
    elif session_data and session_data.get("current_phase") == "BUSINESS_PLAN":
        # Look for competitive analysis, market research, or vendor recommendation needs
        # BUT only trigger if user explicitly asks for research, not for every answer
        business_keywords = ["competitors", "market", "industry", "trends", "pricing", "vendors", "domain", "legal requirements"]
        # Only search if user explicitly mentions these keywords AND it's not just a normal answer
        # Check if it's an explicit request (contains question words or explicit research request)
        is_explicit_request = any(word in user_content.lower() for word in ["find", "research", "search", "look up", "what are", "who are", "tell me about"])
        if any(keyword in user_content.lower() for keyword in business_keywords) and is_explicit_request:
            # Also check throttling to prevent excessive searches
            if should_conduct_web_search():
                needs_web_search = True
            else:
                print(f"⏱️ Skipping web search due to throttling (reducing latency)")
            
            # Extract or generate search query with previous calendar year
            current_year = datetime.now().year
            previous_year = current_year - 1
            
            # ENHANCED COMPETITOR RESEARCH DETECTION
            competitor_keywords = ["competitors", "competition", "main competitors", "who are my competitors", "competing companies", "rival companies"]
            if any(keyword in user_content.lower() for keyword in competitor_keywords):
                competitor_research_requested = True
                web_search_query = f"main competitors in {session_data.get('industry', 'business')} industry {previous_year}"
            elif "market" in user_content.lower() or "trends" in user_content.lower():
                web_search_query = f"market trends {session_data.get('industry', 'business')} {session_data.get('location', '')} {previous_year}"
            elif "domain" in user_content.lower():
                web_search_query = "domain registration availability check websites"
            elif "wine" in user_content.lower() or "influencer" in user_content.lower():
                web_search_query = f"top wine influencers on social media {previous_year}"
    
    # Conduct web search if needed
    search_results = ""
    web_search_status = {"is_searching": False, "query": None}
    immediate_response = None
    
    if needs_web_search and web_search_query:
        # Set web search status for progress indicator
        web_search_status = {"is_searching": True, "query": web_search_query}
        
        # Provide immediate feedback to user
        immediate_response = f"I'm conducting some background research on '{web_search_query}' to provide you with the most current information. This will just take a moment..."
        
        # ENHANCED COMPETITOR RESEARCH HANDLING
        if competitor_research_requested:
            # Extract business context for comprehensive competitor research
            business_context = extract_business_context_from_history(history)
            if session_data:
                business_context.update({
                    "industry": session_data.get("industry", ""),
                    "location": session_data.get("location", ""),
                    "business_name": session_data.get("business_name", ""),
                    "business_type": session_data.get("business_type", "")
                })
            
            # Conduct comprehensive competitor research
            competitor_research_result = await handle_competitor_research_request(user_content, business_context, history)
            
            if competitor_research_result.get("success"):
                search_results = f"\n\n🔍 **Comprehensive Competitor Research Results:**\n\n{competitor_research_result['analysis']}\n\n*Research conducted using {competitor_research_result['research_sources']} authoritative sources*"
            else:
                # Fallback to regular web search
                search_start = time.time()
                search_results = await conduct_web_search(web_search_query)
                search_time = time.time() - search_start
                print(f"🔍 Web search completed in {search_time:.2f} seconds")
                
                if search_results and "unable to conduct web research" not in search_results:
                    search_results = f"\n\nResearch Results:\n{search_results}"
        else:
            # Regular web search for non-competitor requests
            search_start = time.time()
            search_results = await conduct_web_search(web_search_query)
            search_time = time.time() - search_start
            print(f"🔍 Web search completed in {search_time:.2f} seconds")
            
            if search_results and "unable to conduct web research" not in search_results:
                search_results = f"\n\nResearch Results:\n{search_results}"
        
        # Update status to completed
        web_search_status = {"is_searching": False, "query": web_search_query, "completed": True}

    # Accept command should be handled by AI to generate next question naturally
    # Do NOT manually increment question numbers or use generate_next_question()
    # Let the AI follow the system prompt from constant.py
    # Check if this is a command that should not generate new questions
    is_command_response = user_content.lower() in ["draft", "support", "scrapping", "scraping", "draft more"] or user_content.lower().startswith("scrapping:")
    
    # Check if this is an "Accept" command from Support/Draft/Scrapping
    is_accept_command = user_content.lower().strip() == "accept"
    
    # Handle Accept command - treat as a regular answer to move to next question
    if is_accept_command and session_data and session_data.get("current_phase") == "BUSINESS_PLAN":
        print(f"✅ Accept command detected - treating as answer to move to next question")
        # Let it pass through to normal AI processing which will move to the next question
        # Don't bypass AI generation - we want to get the next question
        pass
    
    # For commands, bypass AI generation and provide direct responses
    elif is_command_response and session_data and session_data.get("current_phase") == "BUSINESS_PLAN":
        print(f"🔧 Command detected: {user_content.lower()} - bypassing AI generation to prevent question skipping")
        
        # Generate direct command response without AI
        command = user_content.lower()
        show_buttons_for_command = True

        if command == "draft":
            reply_content = await handle_draft_command("", history, session_data)
        elif command.startswith("scrapping:"):
            notes = user_content[10:].strip()
            scrapping_result = await handle_scrapping_command("", notes, history, session_data)
            # Add show_accept_modify for scrapping responses
            scrapping_result["show_accept_modify"] = True
            # Always return the scrapping result
            return scrapping_result
        elif command in ["scrapping", "scraping"]:
            scrapping_result = await handle_scrapping_command("", "", history, session_data)
            # Add show_accept_modify for scrapping responses
            scrapping_result["show_accept_modify"] = True
            # Always return the scrapping result
            return scrapping_result
        elif command == "support":
            reply_content = await handle_support_command("", history, session_data)
            show_buttons_for_command = False
        elif command in ["draft more", "draft answer"]:
            reply_content = await handle_draft_more_command("", history, session_data)
        else:
            # Fallback to normal AI generation
            reply_content = "I understand you'd like to use a command. Please try again."
        
        # For command responses, ALWAYS show Accept/Modify buttons
        # Return the command response with button detection
        return {
            "reply": reply_content,
            "web_search_status": {"is_searching": False, "query": None, "completed": False},
            "immediate_response": None,
            "show_accept_modify": show_buttons_for_command
        }
    
    # Build messages for OpenAI - optimized for speed
    msgs = [
        {"role": "system", "content": ANGEL_SYSTEM_PROMPT},
        {"role": "system", "content": TAG_PROMPT},
        {"role": "system", "content": FORMATTING_INSTRUCTION}
    ]
    
    # Only add web search prompt if web search was conducted
    if search_results:
        msgs.append({"role": "system", "content": WEB_SEARCH_PROMPT})
    
    # Add search results and immediate response if available
    if search_results:
        msgs.append({
            "role": "system", 
            "content": f"Web search results for your reference:\n{search_results}\n\nIntegrate relevant findings naturally into your response."
        })
    
    # Add immediate response instruction if web search was conducted
    if immediate_response:
        msgs.append({
            "role": "system",
            "content": f"IMPORTANT: The user has requested research and search results have been provided above. You MUST include the research findings in your response. Do not just acknowledge the research - provide the actual results and answer their question based on the search findings. The user expects to get the research results immediately, not just a notification that research is being conducted."
        })
    
    # Add session context to help AI maintain state
    if session_data:
        current_phase = session_data.get("current_phase", "KYC")
        asked_q = session_data.get("asked_q", "KYC.01")
        answered_count = session_data.get("answered_count", 0)
        
        # CRITICAL: After Draft/Support commands, ensure AI remembers the current question
        # Check if the last assistant message was a Draft/Support response
        last_assistant_msg = None
        for msg in reversed(history[-5:]):
            if msg.get('role') == 'assistant':
                last_assistant_msg = msg.get('content', '')
                break
        
        # If last message was Draft/Support, add instruction to NOT repeat the question
        if last_assistant_msg and any(indicator in last_assistant_msg.lower() for indicator in [
            "here's a draft", "here's a research-backed draft", "let me help you with research-backed insights",
            "support command", "draft command"
        ]):
            # User is now providing an answer after using Draft/Support
            # AI should acknowledge and move to next question, NOT repeat the current question
            msgs.append({
                "role": "system",
                "content": f"""
⚠️ CRITICAL CONTEXT - USER JUST PROVIDED ANSWER AFTER DRAFT/SUPPORT:

The user has just provided an answer to the current question: {asked_q}

You MUST:
1. Briefly acknowledge their answer (1-2 sentences max)
2. Immediately ask the NEXT question (do NOT repeat the current question)
3. Do NOT ask the same question again - they just answered it
4. Move forward to the next sequential question

The current question was: {asked_q}
You should now ask the NEXT question in sequence.

DO NOT repeat "{asked_q}" - the user has already answered it.
"""
            })
        
        # Determine next question number
        next_question_num = "01"
        if "." in asked_q:
            try:
                current_num = int(asked_q.split(".")[1])
                # Prevent going beyond KYC.20 (last KYC question)
                if current_phase == "KYC" and current_num >= 20:
                    # Don't increment beyond 20 for KYC
                    next_question_num = "20"
                else:
                    next_question_num = f"{current_num + 1:02d}"
            except (ValueError, IndexError):
                pass
        
        # Check if we're in missing questions mode
        missing_questions_instruction = ""
        next_question_to_ask = next_question_num
        business_context = session_data.get("business_context", {}) or {} if session_data else {}
        uploaded_plan_mode = business_context.get("uploaded_plan_mode", False) if isinstance(business_context, dict) else False
        missing_questions = business_context.get("missing_questions", []) if isinstance(business_context, dict) else []
        
        if session_data and uploaded_plan_mode and current_phase == "BUSINESS_PLAN":
            if isinstance(missing_questions, list) and len(missing_questions) > 0:
                # In missing questions mode, next question should be the next missing question
                next_missing = min(missing_questions)
                next_question_to_ask = f"{next_missing:02d}"
                sorted_missing = sorted(missing_questions)
                missing_questions_instruction = f"""
MISSING QUESTIONS MODE - CRITICAL INSTRUCTIONS:
- The user uploaded a business plan with answers for some questions
- You MUST ONLY ask questions from the missing list: {sorted_missing}
- The next missing question to ask is: Q{next_missing} (BUSINESS_PLAN.{next_question_to_ask})
- When user answers a missing question, automatically move to the NEXT missing question (not sequential)
- Example: If missing questions are [13, 17, 18, 19] and user answers Q13, ask Q17 next (NOT Q14)
- Do NOT ask questions that are NOT in the missing list - the system will redirect you
- After ALL missing questions are answered, continue sequentially with remaining questions (Q25, Q26, etc.)
- Missing questions must be asked in order: {sorted_missing}
- Once all missing questions are answered, the system will automatically continue with remaining questions

CRITICAL: Always use the tag [[Q:BUSINESS_PLAN.{next_question_to_ask}]] for the next missing question.

"""
        
        session_context = f"""
CURRENT SESSION STATE:
- Current Phase: {current_phase}
- Last Question Asked: {asked_q}
- Questions Answered: {answered_count}
- Next Question Should Be: {current_phase}.{next_question_to_ask}

{missing_questions_instruction}
CRITICAL INSTRUCTIONS:
1. You must continue from where the user left off
2. Do NOT restart the phase or go back to earlier questions
3. The next question should be {current_phase}.{next_question_to_ask}
4. Only ask ONE question at a time
5. Use the proper tag format: [[Q:{current_phase}.{next_question_to_ask}]]
6. NEVER include "Question X" text in your response - the UI displays it automatically
7. Do NOT ask about business plan drafting or other phases - stay in {current_phase} phase
8. Continue with the next sequential question in the {current_phase} phase
9. NEVER skip questions - ask them in exact sequential order
10. If user provides an answer, acknowledge it briefly and positively (1-2 sentences) - e.g., "Thank you for sharing that!" DO NOT ask the next question yet - the system will show Accept/Modify buttons and only move forward after user clicks Accept
11. If user uses Support/Draft/Scrapping commands, provide help but stay on the same question
12. Do NOT jump to random questions - follow the exact sequence
13. Do NOT list option bullets in your message - the UI displays clickable option buttons
14. Do NOT provide section summaries - just acknowledge answers briefly and wait for user confirmation
15. **IMPORTANT FOR BUSINESS_PLAN PHASE**: When asking business plan questions, make them DYNAMIC and TAILORED to the user's specific business type and industry. For example:
    - If it's a restaurant: ask about menu, service hours, dining capacity, kitchen equipment, food suppliers
    - If it's a service business: ask about service offerings, timelines, client management, service delivery methods
    - If it's a product business: ask about product features, manufacturing, inventory, distribution
    - Use industry-specific terminology and examples
    - Include relevant follow-up prompts (e.g., "Will you offer all services upon opening, or add certain services at specific times?")

"""
        msgs.append({"role": "system", "content": session_context})
    
    # Add conversation history (trimmed for performance) and current message
    trimmed_history = trim_conversation_history(history, max_messages=10)
    msgs.extend(trimmed_history)
    msgs.append({"role": "user", "content": user_content})

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=msgs,
        temperature=0.7,
        max_tokens=1000,  # Limit response length for faster processing
        stream=False  # Ensure non-streaming for consistent response times
    )

    reply_content = response.choices[0].message.content
    
    # Clean up extra newlines (keep "Question X of 45" format for Business Plan)
    reply_content = re.sub(r'\n{3,}', '\n\n', reply_content)  # Clean up 3+ newlines to 2
    
    # GUARDRAIL: Ensure new question is generated 100% of the time after previous question completes
    # This is critical for Business Planning Questionnaire - Angel must always generate next question
    # Only apply guardrail after user answers (not for commands like Draft/Support/Scrapping)
    if session_data and session_data.get("current_phase") == "BUSINESS_PLAN":
        # Check if user just provided an answer (not a command)
        user_lower = user_content.lower().strip()
        is_user_answer = (
            len(user_content.strip()) > 0 and
            user_lower not in ["draft", "support", "scrapping", "scraping", "modify"] and
            not user_lower.startswith(("draft", "support", "scrapping", "scraping", "modify"))
        )
        
        # Check if user just clicked "Accept" to move to next question
        is_accept_click = user_lower == "accept"
        
        # Only apply guardrail if user answered a question or accepted (not for commands)
        # Commands (Draft/Support/Scrapping) return early and don't reach this point
        if is_user_answer or is_accept_click:
            # Get the last question that was asked (from session or history)
            current_tag = session_data.get("asked_q", "")
            last_q_num = None
            
            # Extract question number from current session tag
            if current_tag and "BUSINESS_PLAN." in current_tag:
                try:
                    last_q_num = int(current_tag.split(".")[1])
                except (ValueError, IndexError):
                    pass
            
            # If we couldn't get from session, try to extract from last assistant message in history
            if last_q_num is None and history:
                for msg in reversed(history[-10:]):
                    if msg.get('role') == 'assistant' and msg.get('content'):
                        content = msg['content']
                        tag_match = re.search(r'\[\[Q:BUSINESS_PLAN\.(\d+)\]\]', content)
                        if tag_match:
                            last_q_num = int(tag_match.group(1))
                            break
            
            # Check if AI response contains a question tag
            tag_match = re.search(r'\[\[Q:BUSINESS_PLAN\.(\d+)\]\]', reply_content)
            reply_has_tag = tag_match is not None
            reply_q_num = int(tag_match.group(1)) if tag_match else None
            
            # Check if AI generated a valid new question (higher number than last asked)
            # After user answers question N, AI should generate question N+1 or higher
            has_valid_new_question = (
                reply_has_tag and
                last_q_num is not None and
                reply_q_num is not None and
                reply_q_num > last_q_num
            )
            
            # Check if response is missing a new question or has wrong question number
            needs_guardrail = (
                not reply_has_tag or  # No question tag at all
                (last_q_num is not None and reply_q_num is not None and reply_q_num <= last_q_num) or  # Same or lower number
                (last_q_num is None and not reply_has_tag)  # Can't determine but no tag
            )
            
            # Apply guardrail: Force generate next sequential question
            if needs_guardrail and last_q_num is not None and last_q_num < 46:
                next_q_num = last_q_num + 1
                next_tag = f"BUSINESS_PLAN.{next_q_num:02d}"
                
                print(f"🛡️ GUARDRAIL: AI didn't generate valid new question after Q{last_q_num}. Forcing next question: {next_tag}")
                print(f"   AI response has tag: {reply_has_tag}, AI question num: {reply_q_num}, Last question num: {last_q_num}")
                
                # Generate the next question using the question generation function
                try:
                    next_question = await generate_dynamic_business_question(
                        question_tag=next_tag,
                        session_data=session_data,
                        history=history,
                        is_missing_question=False
                    )
                    
                    # If AI gave a short acknowledgment, prepend it; otherwise replace with new question
                    if not reply_has_tag and len(reply_content.strip()) < 200:
                        # AI gave short acknowledgment - prepend it to new question
                        reply_content = f"{reply_content.strip()}\n\n{next_question}"
                    else:
                        # AI gave response without proper new question - replace with guaranteed next question
                        # Remove any incorrect question tags first
                        reply_content = re.sub(r'\[\[Q:BUSINESS_PLAN\.\d+\]\]', '', reply_content).strip()
                        if reply_content:
                            reply_content = f"{reply_content}\n\n{next_question}"
                        else:
                            reply_content = next_question
                    
                    print(f"✅ GUARDRAIL: Successfully generated next question {next_tag}")
                except Exception as e:
                    print(f"⚠️ GUARDRAIL ERROR: Failed to generate next question: {e}")
                    # Fallback: At least inject the tag manually
                    if not reply_has_tag:
                        reply_content = f"{reply_content}\n\n[[Q:{next_tag}]]"
                        print(f"✅ GUARDRAIL FALLBACK: Injected question tag {next_tag}")
            elif needs_guardrail and last_q_num is None:
                print(f"⚠️ GUARDRAIL: Cannot determine last question number, skipping guardrail")
    
    # Handle remaining commands (kickstart, contact) that weren't processed earlier
    current_phase = session_data.get("current_phase", "") if session_data else ""
    
    if current_phase != "KYC":
        # Only process remaining commands outside of KYC phase
        if user_content.lower() == "kickstart":
            reply_content = handle_kickstart_command(reply_content, history, session_data)
        elif user_content.lower() == "who do i contact?":
            reply_content = handle_contact_command(reply_content, history, session_data)
    
    # Inject missing tag if AI forgot to include one
    reply_content = inject_missing_tag(reply_content, session_data)
    
    # Check if AI response contains WEBSEARCH_QUERY (from scrapping command)
    if "WEBSEARCH_QUERY:" in reply_content:
        needs_web_search = True
        web_search_query = reply_content.split("WEBSEARCH_QUERY:")[1].strip()
        print(f"🔍 Web search triggered by AI response: {web_search_query}")
        # Remove the WEBSEARCH_QUERY from the response
        reply_content = reply_content.split("WEBSEARCH_QUERY:")[0].strip()
    
    # Format response structure to use proper list format instead of paragraph
    reply_content = format_response_structure(reply_content)
    
    # Ensure questions are properly separated
    reply_content = ensure_question_separation(reply_content, session_data)
    
    # Check if we need to provide a section summary BEFORE updating asked_q
    # (Check based on the PREVIOUS question that was just answered, not the next question)
    current_tag_before_update = session_data.get("asked_q") if session_data else None
    section_summary_info = None
    
    # RE-ENABLED: Section summaries with proper timing to prevent question skipping
    # Only show section summary if user just answered a section-ending question
    # Don't show if user clicked Accept (they want to proceed from summary)
    if not is_accept_command and not is_command_response:
        # Check if we just completed a section-ending question
        section_summary_info = check_for_section_summary(current_tag_before_update, session_data, history)
    
    # Extract question tag from reply and update session data BEFORE sequence validation
    # IMPORTANT: Don't update asked_q if we're showing a section summary
    patch_session = {}
    tag_match = re.search(r'\[\[Q:([A-Z_]+\.\d+)\]\]', reply_content)
    if tag_match and session_data and not section_summary_info:
        new_question_tag = tag_match.group(1)
        current_asked_q = session_data.get("asked_q", "")
        
        # Only update if this is a new question (not the same as current)
        if new_question_tag != current_asked_q:
            # Update session data immediately for sequence validation
            session_data["asked_q"] = new_question_tag
            patch_session["asked_q"] = new_question_tag
            print(f"🔧 Updating session asked_q: {current_asked_q} → {new_question_tag}")
    elif section_summary_info:
        print(f"🔒 Section summary active - NOT updating asked_q (staying at {current_tag_before_update})")
    
    # Validate business plan question sequence (now with updated session data)
    reply_content = validate_business_plan_sequence(reply_content, session_data)
    
    # Fix verification flow to separate verification from next question
    # reply_content = fix_verification_flow(reply_content, session_data)
    
    # Prevent AI from molding user answers without verification
    reply_content = prevent_ai_molding(reply_content, session_data)
    
    # Add critiquing insights based on user's business field
    reply_content = await add_critiquing_insights(reply_content, session_data, user_content)
    
    # Suggest using Draft if user has already provided relevant information
    reply_content = suggest_draft_if_relevant(reply_content, session_data, user_content, history)
    
    # Add proactive support guidance based on identified areas needing help
    reply_content = add_proactive_support_guidance(reply_content, session_data, history)
    
    if section_summary_info:
        print(f"🎯 SECTION SUMMARY TRIGGERED for {section_summary_info['section_name']} at question {current_tag_before_update}")
        
        # CRITICAL: Don't let the question number increment during section summary
        # The summary shows AFTER answering the last question of a section
        # We stay on the same question number until user accepts the summary
        
        # Add section summary requirements to the system prompt
        summary_instruction = f"""
IMPORTANT: You have just completed {section_summary_info['section_name']} section. 
You MUST provide a comprehensive section summary that includes:

1. **Summary**: Recap the key information provided in this section
2. **Educational Insights**: Provide valuable insights about this business area
3. **Critical Considerations**: Highlight important watchouts and considerations for this business type
4. **Verification Request**: Ask user to verify the information before proceeding

Use this EXACT format:
"🎯 **{section_summary_info['section_name']} Section Complete**

**Summary of Your Information:**
[Recap key points from this section]

**Educational Insights:**
[Provide valuable business insights related to this section]

**Critical Considerations:**
[Highlight important watchouts and things to consider]

**Ready to Continue?**
Please confirm that this information is accurate before we move to the next section. You can either accept this summary and continue, or let me know what you'd like to modify.

[[ACCEPT_MODIFY_BUTTONS]]"

CRITICAL: 
- End your response with [[ACCEPT_MODIFY_BUTTONS]] to trigger the Accept/Modify buttons
- Do NOT ask the next question immediately
- Do NOT include any question tags like [[Q:BUSINESS_PLAN.XX]] in this response
"""
        # Add this instruction to the messages
        msgs.append({"role": "system", "content": summary_instruction})
        
        # Regenerate the response with section summary
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=msgs,
            temperature=0.7,
            max_tokens=1000,
            stream=False
        )
        reply_content = response.choices[0].message.content
        
        # IMPORTANT: Clear any question tags from the summary response to prevent asked_q from updating
        reply_content = re.sub(r'\[\[Q:[A-Z_]+\.\d+\]\]', '', reply_content)
        print(f"🔒 Section summary generated - keeping asked_q at {current_tag_before_update} until user accepts")
    
    # Ensure proper question formatting with line breaks and structure
    reply_content = ensure_proper_question_formatting(reply_content, session_data)
    reply_content = await personalize_business_question(reply_content, history, session_data)

    # Check if we're in "missing questions mode" and handle question progression correctly
    # CRITICAL: After answering a missing question, jump to NEXT missing question (not sequential)
    # After all missing questions are answered, continue sequentially with remaining questions
    business_context = session_data.get("business_context", {}) or {} if session_data else {}
    uploaded_plan_mode = business_context.get("uploaded_plan_mode", False) if isinstance(business_context, dict) else False
    missing_questions = business_context.get("missing_questions", []) if isinstance(business_context, dict) else []
    
    if session_data and uploaded_plan_mode and session_data.get("current_phase") == "BUSINESS_PLAN":
        # Ensure missing_questions is a list
        if not isinstance(missing_questions, list):
            missing_questions = []
        
        current_tag = session_data.get("asked_q", "")
        
        # Check if user just answered a missing question
        if current_tag and current_tag.startswith("BUSINESS_PLAN."):
            try:
                current_q_num = int(current_tag.split(".")[1])
                
                # Detect if this is a user answer (not a command)
                is_answer = (len(user_content.strip()) > 0 and 
                            not user_content.lower().strip() in ("support", "draft", "scrapping", "scraping", "accept", "modify", "kickstart", "draft more") and
                            not user_content.lower().startswith(("support", "draft", "scrapping", "scraping", "accept", "modify", "kickstart")))
                
                # If user just answered a missing question, remove it from list and jump to next missing
                if is_answer and current_q_num in missing_questions:
                    missing_questions = [q for q in missing_questions if q != current_q_num]
                    print(f"✅ User answered missing question Q{current_q_num} - removed from missing list")
                    print(f"📋 Remaining missing questions: {missing_questions}")
                    
                    # Update business_context with updated missing_questions list
                    business_context["missing_questions"] = missing_questions
                    business_context["uploaded_plan_mode"] = True
                    session_data["business_context"] = business_context
                    
                    # If there are more missing questions, jump to the next one
                    if missing_questions:
                        next_missing_q = min(missing_questions)
                        next_tag = f"BUSINESS_PLAN.{next_missing_q:02d}"
                        
                        print(f"🎯 Jumping to next missing question: Q{next_missing_q}")
                        print(f"📋 Remaining missing questions: {sorted(missing_questions)}")
                        
                        # Check if AI generated a tag in the reply - if so, replace it
                        tag_match = re.search(r'\[\[Q:BUSINESS_PLAN\.(\d+)\]\]', reply_content)
                        if tag_match:
                            # Replace AI's tag with next missing question tag
                            reply_content = re.sub(
                                r'\[\[Q:BUSINESS_PLAN\.\d+\]\]',
                                f'[[Q:{next_tag}]]',
                                reply_content,
                                count=1
                            )
                            print(f"✅ Replaced AI tag with next missing question tag: {next_tag}")
                        
                        # Update session to jump to next missing question
                        if "patch_session" not in locals():
                            patch_session = {}
                        patch_session["asked_q"] = next_tag
                        patch_session["business_context"] = business_context
                        session_data["asked_q"] = next_tag
                        
                    else:
                        # All missing questions answered - continue sequentially
                        print(f"🎉 All missing questions answered! Continuing with remaining questions sequentially.")
                        
                        # Find the highest answered question number from history
                        from services.chat_service import fetch_chat_history
                        history_for_max = await fetch_chat_history(session_data.get("session_id", "")) if session_data.get("session_id") else []
                        max_answered = 0
                        for msg in history_for_max:
                            if msg.get("role") == "assistant":
                                content = msg.get("content", "")
                                q_match = re.search(r'\[\[Q:BUSINESS_PLAN\.(\d+)\]\]', content)
                                if q_match:
                                    q_num = int(q_match.group(1))
                                    max_answered = max(max_answered, q_num)
                        
                        # Next question should be max_answered + 1, but not exceed 45
                        next_sequential = min(max_answered + 1, 46)
                        next_tag = f"BUSINESS_PLAN.{next_sequential:02d}"
                        
                        print(f"🎯 All missing questions done - continuing sequentially from Q{next_sequential}")
                        
                        # Update session to continue sequentially
                        if "patch_session" not in locals():
                            patch_session = {}
                        patch_session["asked_q"] = next_tag
                        # Clear uploaded_plan_mode since we're done with missing questions
                        business_context["uploaded_plan_mode"] = False
                        business_context["missing_questions"] = []
                        patch_session["business_context"] = business_context
                        session_data["asked_q"] = next_tag
                        session_data["business_context"] = business_context
                
                # If AI is trying to ask a question that's NOT in missing list (and we still have missing questions)
                elif missing_questions:
                    tag_match = re.search(r'\[\[Q:BUSINESS_PLAN\.(\d+)\]\]', reply_content)
                    if tag_match:
                        ai_question_num = int(tag_match.group(1))
                        
                        # If AI is asking a question not in missing list, redirect to next missing
                        if ai_question_num not in missing_questions:
                            next_missing_q = min(missing_questions)
                            next_tag = f"BUSINESS_PLAN.{next_missing_q:02d}"
                            
                            print(f"🎯 AI tried to ask Q{ai_question_num} (not in missing list) - redirecting to next missing Q{next_missing_q}")
                            print(f"📋 Remaining missing questions: {sorted(missing_questions)}")
                            
                            # Replace tag in reply
                            reply_content = re.sub(
                                r'\[\[Q:BUSINESS_PLAN\.\d+\]\]',
                                f'[[Q:{next_tag}]]',
                                reply_content,
                                count=1
                            )
                            
                            # Update session
                            if "patch_session" not in locals():
                                patch_session = {}
                            patch_session["asked_q"] = next_tag
                            patch_session["business_context"] = business_context
                            session_data["asked_q"] = next_tag
                            session_data["business_context"] = business_context
                            
                            print(f"✅ Redirected to Q{next_missing_q}")
            except (ValueError, IndexError) as e:
                print(f"⚠️ Error parsing question number: {e}")

    end_time = time.time()
    response_time = end_time - start_time
    print(f"⏱️ Angel reply generated in {response_time:.2f} seconds")
    
    # Keep Supabase business_context in sync with answers captured in history
    should_update_context = (
        session_data
        and history
        and session_data.get("current_phase") in [
            "KYC",
            "BUSINESS_PLAN",
            "PLAN_TO_ROADMAP_TRANSITION",
            "ROADMAP",
            "ROADMAP_GENERATED",
        ]
    )
    if should_update_context:
        try:
            extracted_context = extract_business_context_from_history(history) or {}
            if extracted_context:
                existing_context = session_data.get("business_context") or {}
                if not isinstance(existing_context, dict):
                    existing_context = {}
                updated_context = existing_context.copy()
                changed = False
                for key, value in extracted_context.items():
                    if isinstance(value, str):
                        value = value.strip()
                    if value and updated_context.get(key) != value:
                        updated_context[key] = value
                        changed = True
                if changed:
                    session_data["business_context"] = updated_context
                    patch_session["business_context"] = updated_context
        except Exception as exc:
            print(f"⚠️ Failed to update business context: {exc}")
    
    # Use AI to determine if Accept/Modify buttons should be shown (pass session_data)
    button_detection = await should_show_accept_modify_buttons(reply_content, user_content, session_data)
    
    # Clean up internal tags before sending to user
    # Remove [[ACCEPT_MODIFY_BUTTONS]] tag - it's only for backend detection, not display
    reply_content = reply_content.replace("[[ACCEPT_MODIFY_BUTTONS]]", "").strip()
    
    return {
        "reply": reply_content,
        "web_search_status": web_search_status,
        "immediate_response": immediate_response,
        "patch_session": patch_session if patch_session else None,
        "show_accept_modify": button_detection.get("show_buttons", False)
    }

async def handle_draft_command(reply, history, session_data=None):
    """Handle the Draft command with research-backed comprehensive response generation"""
    # Extract context from conversation history
    context_summary = extract_conversation_context(history)
    business_context = extract_business_context_from_history(history)
    
    # Get current question context for more targeted responses
    current_question = get_current_question_context(history, session_data)
    
    # Conduct web search for research-backed drafts (for specific question types)
    business_name = business_context.get("business_name", "business")
    industry = business_context.get("industry", "business")
    location = business_context.get("location", "")
    question_topic = get_question_topic(current_question)
    
    # Trigger research ONLY for data-heavy questions that truly need external data
    # Skip research for simple questions like mission statement/tagline to reduce latency
    research_topics = ["competitor", "competitive analysis", "startup costs", "operational requirements", 
                       "staffing needs", "target market", "sales projections", "financial planning",
                       "expenses", "pricing", "market", "customer acquisition"]
    
    # Exclude mission statement/tagline from research - it doesn't need external data
    skip_research_topics = ["mission statement", "tagline", "business name"]
    
    research_results = None
    if (any(topic in question_topic.lower() for topic in research_topics) and 
        not any(skip_topic in question_topic.lower() for skip_topic in skip_research_topics)):
        # Only conduct research if throttling allows
        if should_conduct_web_search():
            research_query = f"{industry} {question_topic} {location} data statistics 2024"
            print(f"🔍 Draft command - Conducting research: {research_query}")
            research_results = await conduct_web_search(research_query)
        else:
            print(f"⏱️ Draft command - Skipping research due to throttling (reducing latency)")
    
    # Generate draft content based on conversation history, question, and research
    draft_content = await generate_draft_content(history, business_context, current_question, research_results)
    
    # Create a comprehensive draft response with clear heading
    draft_response = f"Here's a research-backed draft for you:\n\n{draft_content}\n\n"
    
    thought_starter = None
    if session_data and session_data.get("current_phase") == "BUSINESS_PLAN":
        current_tag = session_data.get("asked_q")
        thought_starter = get_thought_starter_for_tag(current_tag)
    if thought_starter:
        draft_response += f"🧠 Thought Starter: {thought_starter}\n"
    
    return draft_response

def get_current_question_context(history, session_data=None):
    """Extract the current question context from the most recent assistant message or session data"""
    
    # First, try to get current question from session data if available
    if session_data and session_data.get('asked_q'):
        asked_q = session_data.get('asked_q')
        print(f"🔍 DEBUG - Found current question from session: {asked_q}")
        
        # Look for the actual question content in recent history that matches this question tag
        for msg in reversed(history[-10:]):  # Look at last 10 messages
            if msg.get('role') == 'assistant' and msg.get('content'):
                content = msg['content']
                # Check if this message contains the current question tag
                if f'[[Q:{asked_q}]]' in content:
                    print(f"🔍 DEBUG - Found matching question content for {asked_q}")
                    return content
        
        # If no matching content found, return the question tag for context
        print(f"🔍 DEBUG - No matching content found, returning question tag: {asked_q}")
        return f"Current question: {asked_q}"
    
    # Fallback: Look for the most recent assistant message that contains a question tag
    for msg in reversed(history[-8:]):  # Look at last 8 messages to find the actual question
        if msg.get('role') == 'assistant' and msg.get('content'):
            content = msg['content'].lower()
            # Skip command responses and look for actual questions
            if any(command in content for command in ['here\'s a draft', 'let\'s work through this', 'here\'s a refined version', 'verification:', 'here\'s what i\'ve captured']):
                continue
            # Look for question tags or question indicators
            if '[[' in content and ']]' in content and any(indicator in content for indicator in ['what', 'how', 'when', 'where', 'why', 'do you', 'are you', 'can you']):
                question_text = content
                print(f"🔍 DEBUG - Found current question from history: {question_text[:200]}...")
                return question_text
    print("🔍 DEBUG - No question found in recent history")
    return ""

def get_question_topic(current_question):
    """Extract the main topic from the current question - prioritize topline question, not sub-questions"""
    if not current_question:
        print("🔍 DEBUG - No current question provided to get_question_topic")
        return "business planning"
    
    # Check for BUSINESS_PLAN.02 tag first - this is the topline question
    if '[[Q:BUSINESS_PLAN.02]]' in current_question or 'business_plan.02' in current_question.lower():
        print("🔍 DEBUG - Detected BUSINESS_PLAN.02 - mission statement/tagline topic")
        return "mission statement"
    
    # Check for mission/tagline keywords - but only if it's the main question, not a sub-question
    if any(keyword in current_question.lower() for keyword in ['mission statement', 'tagline', 'business tagline']):
        # Make sure it's not a sub-question by checking if it's the first question in the text
        question_lower = current_question.lower()
        if 'what is your business tagline or mission statement' in question_lower:
            print("🔍 DEBUG - Detected mission statement topic (topline question)")
            return "mission statement"
    
    if any(keyword in current_question for keyword in ['problem does your business solve', 'who has this problem', 'problem', 'solve', 'pain point', 'need']):
        print("🔍 DEBUG - Detected problem-solution topic")
        return "problem-solution fit"
    elif any(keyword in current_question for keyword in ['competitor', 'competition', 'main competitors', 'strengths and weaknesses', 'competitive advantage', 'unique value proposition', 'what makes your business unique']):
        print("🔍 DEBUG - Detected competitive analysis topic")
        return "competitive analysis"
    elif any(keyword in current_question for keyword in ['target market', 'demographics', 'psychographics', 'behaviors', 'ideal customer']):
        print("🔍 DEBUG - Detected target market topic")
        return "target market definition"
    elif any(keyword in current_question for keyword in ['location', 'space', 'facility', 'equipment', 'infrastructure', 'where will your business be located']):
        print("🔍 DEBUG - Detected operational requirements topic")
        return "operational requirements"
    elif any(keyword in current_question for keyword in ['staff', 'hiring', 'team', 'employee', 'operational needs', 'initial staff']):
        print("🔍 DEBUG - Detected staffing needs topic")
        return "staffing needs"
    elif any(keyword in current_question for keyword in ['supplier', 'vendor', 'partner', 'relationship', 'key partners']):
        print("🔍 DEBUG - Detected supplier relationships topic")
        return "supplier and vendor relationships"
    elif any(keyword in current_question for keyword in ['key features and benefits', 'how does it work', 'main components', 'steps involved', 'value or results', 'product', 'service', 'core offering', 'what will you be offering']):
        print("🔍 DEBUG - Detected core product/service topic")
        return "core product or service"
    elif any(keyword in current_question for keyword in ['sales', 'projected sales', 'first year', 'sales projections', 'revenue', 'income']):
        print("🔍 DEBUG - Detected sales projections topic")
        return "sales projections"
    elif any(keyword in current_question for keyword in ['startup costs', 'estimated startup costs', 'one-time expenses', 'initial costs', 'launch costs']):
        print("🔍 DEBUG - Detected startup costs topic")
        return "startup costs"
    elif any(keyword in current_question for keyword in ['financial', 'budget', 'costs', 'expenses', 'funding', 'investment']):
        print("🔍 DEBUG - Detected financial planning topic")
        return "financial planning"
    elif any(keyword in current_question for keyword in ['intellectual property', 'patents', 'trademarks', 'copyrights', 'proprietary technology', 'unique processes', 'formulas', 'legal protections']):
        print("🔍 DEBUG - Detected intellectual property topic")
        return "intellectual property"
    elif any(keyword in current_question for keyword in ['where will you sell', 'sales location', 'sales channels', 'where will you sell your services', 'distribution channels', 'sales platforms']):
        print("🔍 DEBUG - Detected sales location topic")
        return "sales location"
    else:
        print("🔍 DEBUG - No specific topic detected, using default business planning")
        return "business planning"

async def generate_draft_content(history, business_context, current_question="", research_results=None):
    """Generate research-backed draft content based on conversation history"""
    # Extract recent messages (both user and assistant) to understand context
    recent_messages = []
    for msg in history[-8:]:  # Look at last 8 messages (4 exchanges)
        if msg.get('content'):
            recent_messages.append(msg['content'])
    
    # Debug logging
    print(f"🔍 DEBUG - Recent messages for draft context: {recent_messages}")
    print(f"🔍 DEBUG - Research results available for draft: {bool(research_results)}")
    
    # Generate contextual draft based on what they've been discussing
    if not recent_messages:
        return "Based on our conversation, here's a draft response that captures the key points we've discussed and provides a comprehensive answer to your current question."
    
    # Look for key topics in recent messages (both questions and responses)
    recent_text = " ".join(recent_messages).lower()
    print(f"🔍 DEBUG - Recent text for draft analysis: {recent_text[:200]}...")
    
    # Use the current_question parameter if provided, otherwise extract from history
    if not current_question:
        current_question = get_current_question_context(history, None)
    
    print(f"🔍 DEBUG - Current question context for draft: {current_question[:100]}...")
    
    # Extract business context
    business_name = business_context.get("business_name", "your business")
    industry = business_context.get("industry", "your industry")
    business_type = business_context.get("business_type", "your business type")
    location = business_context.get("location", "your location")
    
    # Extract previous answers from history for better context - look at ALL history, not just recent
    previous_answers = []
    key_information = []  # Extract key facts like "sole employee", "no staff", etc.
    
    # Look through ALL history to find important previous answers
    for msg in history:
        if msg.get('role') == 'user' and len(msg.get('content', '')) > 10:
            content = msg.get('content', '')
            # Skip command words
            if content.lower() not in ['support', 'draft', 'scrapping', 'scraping', 'accept', 'modify', 'yes', 'no']:
                # Extract key information about staffing, ownership, etc.
                content_lower = content.lower()
                if any(phrase in content_lower for phrase in ['sole employee', 'only me', 'just me', 'no employees', 'no staff', 'working solo', 'i will be the only', 'i am the only']):
                    key_information.append(f"CRITICAL: User stated they are the sole employee/owner - NO staff will be hired initially")
                if any(phrase in content_lower for phrase in ['no funding', 'self-funded', 'personal savings', 'no investors']):
                    key_information.append(f"CRITICAL: User stated funding approach")
                if len(content.strip()) > 20:  # Only include substantial answers
                    previous_answers.append(content[:300])  # Increased from 200 to 300
    
    # Prioritize recent answers but include key information from anywhere
    recent_answers = previous_answers[-5:] if len(previous_answers) > 5 else previous_answers
    
    # Use AI to generate a comprehensive, personalized, research-backed draft
    research_section = ""
    if research_results:
        research_section = f"""
    
    📊 RESEARCH DATA (INCORPORATE INTO DRAFT):
        {research_results}
    
    Use this research to provide data-driven, factual content with citations.
    """
    
    draft_prompt = f"""
    ⚠️ CRITICAL CONTEXT - READ FIRST:
        This business is in the {industry.upper()} INDUSTRY operating as a {business_type.upper()}.
    ALL draft content must be 100% specific to {industry.upper()} businesses - NOT education, NOT technology, NOT consulting.
    Use ONLY {industry.upper()} industry examples, terminology, and context.
    {research_section}
    
    Create a comprehensive, detailed, research-backed draft answer for this business question: "{current_question}"
    
    Business Context (PRIMARY IDENTIFIERS):
    - Business Name: {business_name}
    - PRIMARY INDUSTRY: {industry.upper()} ⭐ (THIS IS THE CORE BUSINESS TYPE)
    - Business Structure: {business_type}
    - Location: {location}
    
    Previous Answers and Context:
    {' | '.join(recent_answers) if recent_answers else 'No previous context available'}
    
    ⚠️ CRITICAL PREVIOUS ANSWERS - MUST RESPECT THESE:
    {chr(10).join(key_information) if key_information else 'No critical constraints identified'}
    
    IMPORTANT: If the user previously stated they are the sole employee/owner with no staff, 
    your draft MUST reflect this. Do NOT suggest hiring employees or building a team if they 
    explicitly stated they will work solo. Respect their previous answers completely.
    
    Generate a complete, well-structured draft answer that:
        1. Directly answers the question with specific, data-backed content for a {industry.upper()} business
    2. Incorporates research findings, statistics, and data when available
    3. Cites sources and data points from research findings
    4. Is personalized to {business_name} in the {industry.upper()} industry
    5. Considers the {location} market and local factors with actual data
    6. Provides concrete details and examples from the {industry.upper()} industry (not generic advice)
    7. Is appropriate for a {business_type} business structure
    8. Uses information from previous answers when relevant
    9. Includes bullet points or numbered lists for clarity
    10. ⚠️ CRITICAL WORD LIMIT: Your response MUST be exactly 100 words or less. Be concise and focused. Do not exceed 100 words.
    11. NEVER mentions unrelated industries - stay focused on {industry.upper()}
    
    ⚠️ CRITICAL FOR COST/FINANANCIAL QUESTIONS:
    - If the question asks about costs, expenses, pricing, acquisition costs, startup costs, or any financial estimates:
      * You MUST provide ACTUAL NUMERICAL ESTIMATES based on the {industry.upper()} industry and {location} market
      * Include specific dollar amounts, ranges, or percentages (e.g., "$50-$200 per customer", "15-25% of revenue", "$10,000-$25,000")
      * Base estimates on research data, industry benchmarks, and {location} market conditions
      * Break down costs by category if applicable
      * DO NOT just provide general advice - provide actual numbers the user can use
      * Example: For "customer acquisition cost" - provide a specific range like "$25-$75 per customer for a {industry.upper()} in {location}"
    
    Structure the draft with clear sections like:
        - Main answer/core content for {industry.upper()} business (with data)
    - Key points or features with statistics (use bullet points)
    - Research-backed insights and market data
    - Specific considerations for the {industry} business
    - Next steps or recommendations
    - Sources cited (if research data was provided)
    
    Make this a complete, polished, research-backed draft that the user can accept and use immediately. Be specific and detailed, not generic.
    REMEMBER: This is a {industry.upper()} business - all examples, features, and recommendations must be relevant to {industry.upper()}.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": draft_prompt}],
            temperature=0.3,
            max_tokens=500  # Reduced to enforce 100-word limit (approximately 500 tokens for 100 words)
        )
        
        ai_draft = response.choices[0].message.content
        # Enforce 100-word limit
        ai_draft = truncate_to_word_limit(ai_draft, 100)
        word_count = len(ai_draft.split())
        print(f"✅ Draft content generated with {len(ai_draft)} characters ({word_count} words){' (with research)' if research_results else ''}")
        return ai_draft
    except Exception as e:
        print(f"❌ AI draft generation failed: {e}, falling back to template-based drafts")
        # Fallback with research if available
        if research_results:
            return f"""Based on research findings for {business_name} in the {industry} industry:

{research_results}

This data can help you craft a comprehensive answer for your {location} market."""
        pass
    
    # Check for specific business plan question topics based on current question
    if any(keyword in current_question for keyword in ['problem does your business solve', 'who has this problem', 'problem', 'solve', 'pain point', 'need']):
        return generate_problem_solution_draft(business_context, history)
    
    elif any(keyword in current_question for keyword in ['competitor', 'competition', 'main competitors', 'strengths and weaknesses', 'competitive advantage', 'unique value proposition', 'what makes your business unique']):
        return generate_competitive_analysis_draft(business_context, history)
    
    elif any(keyword in current_question for keyword in ['target market', 'demographics', 'psychographics', 'behaviors', 'ideal customer']):
        return generate_target_market_draft(business_context, history)
    
    elif any(keyword in current_question for keyword in ['location', 'space', 'facility', 'equipment', 'infrastructure', 'where will your business be located']):
        return generate_operational_requirements_draft(business_context, history)
    
    elif any(keyword in current_question for keyword in ['staff', 'hiring', 'team', 'employee', 'operational needs', 'initial staff', 'staffing needs']):
        # Check if user previously mentioned specific staff (like secretary, assistant, etc.)
        history_text = " ".join([msg.get('content', '') for msg in history if msg.get('role') == 'user']).lower()
        
        # Extract previously mentioned staff from history
        mentioned_staff = []
        staff_keywords = ['secretary', 'assistant', 'receptionist', 'office manager', 'bookkeeper', 'accountant', 'staff', 'employee', 'worker', 'help']
        
        import re
        for msg in history:
            if msg.get('role') == 'user':
                content = msg.get('content', '')
                content_lower = content.lower()
                
                # Look for patterns like "1 office secretary", "1 secretary", "a secretary", "secretary", etc.
                for keyword in staff_keywords:
                    # Pattern to match: (number)? (office )? (a/an )? keyword (s)?
                    # Use word boundaries to avoid partial matches
                    pattern = r'\b(\d+)?\s*(?:office\s+)?(?:a\s+|an\s+)?' + re.escape(keyword) + r's?\b'
                    matches = re.finditer(pattern, content_lower)
                    for match in matches:
                        full_match = match.group(0)  # The full matched string
                        number = match.group(1)  # The number group (if present)
                        
                        # Extract the full phrase including "office" if present
                        if number:
                            # Has a number, include it
                            staff_mention = f"{number} {full_match.replace(number, '').strip()}"
                        else:
                            # No number, use the full match
                            staff_mention = full_match.strip()
                        
                        # Clean up the mention (remove extra spaces, normalize)
                        staff_mention = re.sub(r'\s+', ' ', staff_mention).strip()
                        
                        # Add to list if not already present
                        if staff_mention and staff_mention not in mentioned_staff:
                            mentioned_staff.append(staff_mention)
                            print(f"🔍 DEBUG - Found staff mention in history: '{staff_mention}'")
                        break  # Only process first match per keyword per message
        
        # Check if user previously stated they are sole employee
        if any(phrase in history_text for phrase in ['sole employee', 'only me', 'just me', 'no employees', 'no staff', 'working solo', 'i will be the only', 'i am the only']):
            return f"""Based on your previous answer that you will be the sole employee and owner, here's a draft for your staffing needs:

**Initial Staffing Structure:**
Since you've indicated you will be working solo initially, your staffing needs focus on your own skills and capabilities rather than hiring employees.

**Key Considerations:**
• You will handle all business functions yourself initially (operations, sales, marketing, customer service)
• Focus on developing or acquiring the skills you need to run the business effectively
• Consider contractors or freelancers for specialized tasks you can't handle yourself
• Plan for potential future growth when you might need to hire your first employee

**Skills Development:**
Identify any skills or expertise you need to develop or acquire to successfully run the business solo. This might include technical skills, business management, marketing, or customer service capabilities.

**Resource Planning:**
As a sole employee, consider:
• Time management and workload capacity
• Tools and systems to maximize your productivity
• When you might need to bring in contractors or part-time help
• Long-term plan for when you're ready to hire your first employee

This approach allows you to maintain full control while building the business foundation before expanding your team."""
        elif mentioned_staff:
            # User previously mentioned specific staff - reference it
            staff_list = list(set(mentioned_staff))  # Remove duplicates
            staff_summary = ", ".join(staff_list[:3])  # Limit to first 3 mentions
            return f"""Based on your previous answers where you mentioned {staff_summary}, here's a draft for your staffing needs:

**Initial Staffing Structure:**
You've previously indicated your staffing needs include {staff_summary}. This is a great starting point for your business operations.

**Key Considerations:**
• {staff_summary} will help support your core business functions
• Consider the specific roles and responsibilities for each position
• Think about the qualifications and skills needed for these roles
• Plan for how these staff members will integrate into your operations

**Operational Integration:**
• How will {staff_summary} support your daily operations?
• What systems and processes will you need to manage this team effectively?
• Consider training needs and onboarding processes
• Plan for supervision and performance management

**Resource Planning:**
• Budget for salaries, benefits, and training
• Workspace requirements for your team
• Tools and equipment needed for each role
• Consider part-time vs. full-time arrangements based on your needs

This staffing structure will help you build a strong foundation for your business operations."""
        else:
            return generate_staffing_needs_draft(business_context, history)
    
    elif any(keyword in current_question for keyword in ['supplier', 'vendor', 'partner', 'relationship', 'key partners']):
        return generate_supplier_relationships_draft(business_context, history)
    
        return f"""Based on your business vision, here's a draft for your key features and benefits:

{business_context.get('business_name', 'Your business')} offers advanced AI-powered features that provide significant productivity benefits to customers. The main components include intelligent voice recognition technology, automated text formatting, and seamless integration capabilities.

**Key Features:**
- Advanced AI-powered voice recognition with 95%+ accuracy
- Automated text formatting and organization
- Multiple output formats (plain text, formatted documents, blog posts)
- Real-time processing with instant results
- Cloud-based storage and access
- Integration with popular productivity tools

**Customer Benefits:**
- Dramatic time savings (up to 80% reduction in transcription time)
- Improved accuracy compared to manual transcription
- Enhanced productivity and workflow efficiency
- Cost-effective solution for content creation
- Easy-to-use interface requiring no technical expertise

**How It Works:**
Customers experience seamless results through a simple three-step process: 1) Upload voice recordings via web interface, 2) AI processes and transcribes audio with intelligent formatting, 3) Download formatted text in preferred format. The entire process takes under 5 minutes for most recordings.

**Measurable Results:**
Customers can expect 95%+ transcription accuracy, processing times under 5 minutes, and significant productivity improvements in their content creation workflows."""
    
    elif any(keyword in current_question for keyword in ['intellectual property', 'patents', 'trademarks', 'copyrights', 'proprietary technology', 'unique processes', 'formulas', 'legal protections']):
        return generate_intellectual_property_draft(business_context, history)
    
    elif any(keyword in current_question for keyword in ['product', 'service', 'core offering', 'what will you be offering']):
        business_name = business_context.get("business_name", "Your business")
        industry = business_context.get("industry", "your industry")
        business_type = business_context.get("business_type", "your business type")
        
        return f"""Based on your business vision, here's a draft for your core product or service: 

{business_name} offers innovative solutions in the {industry} sector designed to help customers achieve their goals more efficiently. As a {business_type}, we focus on delivering value through specialized expertise and customer-centric approaches.

**Core Features:**
- Specialized solutions tailored to the {industry} market
- Customer-focused service delivery
- Innovative approaches to common challenges
- Scalable solutions that grow with customer needs

**Key Benefits:**
- Improved efficiency and productivity for customers
- Cost-effective solutions compared to alternatives
- Expert guidance and support
- Customized approaches for different customer segments

**Customer Experience:**
Customers interact with {business_name} through a streamlined process that focuses on understanding their specific needs and delivering tailored solutions. Our approach emphasizes clear communication, quality service, and measurable results.

**Unique Value Proposition:**
{business_name} combines industry expertise with innovative approaches to deliver superior solutions in the {industry} sector. Our focus on customer success and continuous improvement sets us apart from competitors.

**Expected Outcomes:**
Customers can expect improved results, enhanced efficiency, and ongoing support that helps them achieve their business objectives in the {industry} sector."""
    
    elif any(keyword in current_question for keyword in ['mission', 'tagline', 'mission statement', 'business stands for']):
        business_name = business_context.get("business_name", "Your business")
        industry = business_context.get("industry", "your industry")
        
        return f"""Based on your business vision, here's a draft mission statement:

"{business_name} aims to deliver innovative solutions in the {industry} sector, empowering customers to achieve their goals through expert guidance, quality service, and continuous improvement."

**Core Values:**
- Customer-centric approach and service excellence
- Innovation and continuous improvement
- Integrity and transparency in all interactions
- Commitment to delivering measurable results
- Building long-term partnerships with customers

**Purpose Statement:**
We believe that every customer deserves solutions that are tailored to their specific needs and delivered with expertise and care. By focusing on understanding our customers' challenges and goals, we provide value that goes beyond expectations.

**Unique Positioning:**
{business_name} stands for combining industry expertise with personalized service, making professional solutions accessible and effective for customers in the {industry} sector."""
    
    elif any(keyword in current_question for keyword in ['sales', 'projected sales', 'first year', 'sales projections', 'revenue', 'income']):
        return await generate_sales_projection_draft(business_context, current_question)
    
    elif any(keyword in current_question for keyword in ['startup costs', 'estimated startup costs', 'one-time expenses', 'initial costs', 'launch costs']):
        return await generate_startup_costs_table_draft(business_context, current_question)
    
    elif any(keyword in current_question for keyword in ['monthly expenses', 'monthly operating expenses', 'recurring costs', 'operating expenses']):
        return await generate_monthly_expenses_draft(business_context, current_question)
    
    elif any(keyword in current_question for keyword in ['customer acquisition cost', 'acquisition cost', 'customer acquisition', 'cost to acquire', 'cac']):
        return await generate_customer_acquisition_cost_draft(business_context, current_question)
    
    elif any(keyword in current_question for keyword in ['pricing', 'price', 'pricing strategy', 'how will you price', 'pricing model']):
        return await generate_pricing_with_cost_analysis_draft(business_context, current_question)
    
    elif any(keyword in current_question for keyword in ['financial', 'budget', 'costs', 'expenses', 'funding', 'investment']):
        return "Based on your business requirements, here's a draft for your financial planning: Your financial plan should include startup costs, operating expenses, cash flow projections, and funding requirements. Consider fixed costs (rent, salaries, equipment) and variable costs (materials, marketing, commissions). Focus on creating realistic budgets, identifying funding sources, and planning for financial sustainability. Think about break-even analysis, profit margins, and financial contingency planning to ensure long-term viability."
    
    elif any(keyword in current_question for keyword in ['intellectual property', 'patents', 'trademarks', 'copyrights', 'proprietary technology', 'unique processes', 'formulas', 'legal protections']):
        return generate_intellectual_property_draft(business_context, history)
    
    elif any(keyword in current_question for keyword in ['where will you sell', 'sales location', 'sales channels', 'where will you sell your services', 'distribution channels', 'sales platforms']):
        business_name = business_context.get("business_name", "your business")
        industry = business_context.get("industry", "your industry")
        business_type = business_context.get("business_type", "your business type")
        sales_location = business_context.get("sales_location", "")
        
        return f"""Based on your business goals, here's a draft for where you will sell your services:

**Sales Channels:**
• Online platforms: Website, e-commerce, social media, online marketplaces
• Physical locations: Office, retail space, client sites, pop-up locations
• Hybrid approach: Combination of online and in-person sales

**Regulatory Considerations:**
• Licensing requirements based on sales location (local, state, federal)
• Tax obligations for different sales channels
• Compliance with online sales regulations if applicable
• Permits needed for physical locations

**Key Milestones:**
• Complete market research and validation
• Develop working prototype
• Create minimum viable product (MVP)
• Conduct testing and validation
• Prepare for full product launch

**Timeline Considerations:**
• Development phases: 3-6 months per phase
• Testing periods: 2-4 weeks for each iteration
• Validation steps: Continuous throughout development
• Resource requirements: Technical team, testing equipment, market research

**Validation Strategy:**
Focus on validating your concept before full development through market research, prototype testing, and user feedback to ensure market fit and demand."""
    
    # Fallback to analyzing recent text if current question doesn't match
    elif any(keyword in recent_text for keyword in ['problem does your business solve', 'who has this problem', 'problem', 'solve', 'pain point', 'need']):
        return generate_problem_solution_draft(business_context, history)
    
    elif any(keyword in recent_text for keyword in ['competitor', 'competition', 'main competitors', 'strengths and weaknesses', 'competitive advantage', 'unique value proposition', 'what makes your business unique']):
        return generate_competitive_analysis_draft(business_context, history)
    
    elif any(keyword in recent_text for keyword in ['target market', 'demographics', 'psychographics', 'behaviors', 'ideal customer']):
        return generate_target_market_draft(business_context, history)
    
    elif any(keyword in recent_text for keyword in ['location', 'space', 'facility', 'equipment', 'infrastructure', 'where will your business be located']):
        return "Based on your business needs, here's a draft for your operational requirements: Your business location should be strategically chosen to maximize accessibility for your target customers while considering operational efficiency. Key factors include proximity to suppliers, transportation access, zoning requirements, and cost considerations. Your space and equipment needs should align with your business operations, ensuring you have adequate facilities to serve your customers effectively while maintaining operational efficiency. Focus on factors like zoning, transportation access, costs, and scalability."
    
    elif any(keyword in recent_text for keyword in ['staff', 'hiring', 'team', 'employee', 'operational needs', 'initial staff', 'staffing needs']):
        # Check if user previously stated they are sole employee
        history_text = " ".join([msg.get('content', '') for msg in history if msg.get('role') == 'user']).lower()
        if any(phrase in history_text for phrase in ['sole employee', 'only me', 'just me', 'no employees', 'no staff', 'working solo', 'i will be the only', 'i am the only']):
            return "Based on your previous answer that you will be the sole employee and owner, here's a draft for your staffing needs: Since you've indicated you will be working solo initially, your staffing needs focus on your own skills and capabilities rather than hiring employees. You will handle all business functions yourself initially (operations, sales, marketing, customer service). Focus on developing or acquiring the skills you need to run the business effectively. Consider contractors or freelancers for specialized tasks you can't handle yourself. Plan for potential future growth when you might need to hire your first employee. Identify any skills or expertise you need to develop or acquire to successfully run the business solo. As a sole employee, consider time management, tools and systems to maximize productivity, when you might need contractors or part-time help, and your long-term plan for when you're ready to hire your first employee."
        else:
            return "Based on your business goals, here's a draft for your staffing needs: Your short-term operational needs should focus on identifying critical roles required for launch, including key personnel who can drive your core business functions. Consider hiring initial staff who bring essential skills and experience, securing appropriate workspace, and establishing operational processes. Prioritize roles that directly impact customer experience and business operations, ensuring you have the right team in place to execute your business plan effectively. Focus on identifying key positions, required qualifications, and your hiring timeline."
    
    elif any(keyword in recent_text for keyword in ['supplier', 'vendor', 'partner', 'relationship', 'key partners']):
        return "Based on your business requirements, here's a draft for your supplier and vendor relationships: You'll need to identify key suppliers and vendors who can provide essential products, services, or resources for your business operations. Consider building relationships with reliable partners who offer competitive pricing, quality products, and consistent service. Key partners might include suppliers for raw materials, service providers for essential business functions, and strategic partners who can help you reach your target market or enhance your offerings. Focus on reliability, quality, pricing, and long-term partnership potential."
    
    elif any(keyword in recent_text for keyword in ['key features and benefits', 'how does it work', 'main components', 'steps involved', 'value or results']):
        return f"Based on your business vision, here's a draft for your key features and benefits: {business_context.get('business_name', 'Your business')} offers advanced AI-powered features that provide significant productivity benefits to customers. The main components include intelligent voice recognition technology, automated text formatting, and seamless integration capabilities. Customers will experience dramatic time savings and improved accuracy through a process that involves uploading audio files, AI processing, and downloading formatted results. Focus on clearly articulating the technical aspects, user experience, and measurable results customers can expect from using your solution."
    
    elif any(keyword in recent_text for keyword in ['product', 'service', 'core offering', 'what will you be offering']):
        return "Based on your business vision, here's a draft for your core product or service: Your core offering is [product/service description] designed to [key benefits]. Consider what specific features, benefits, or outcomes customers will receive and how customers will interact with or use your product/service. Focus on your unique value proposition and how you'll deliver exceptional customer experience. Think about the key features that differentiate you from competitors and the specific outcomes customers can expect."
    
    elif any(keyword in recent_text for keyword in ['intellectual property', 'patents', 'trademarks', 'copyrights', 'proprietary technology', 'unique processes', 'formulas', 'legal protections']):
        return "Based on your business needs, here's a draft for your intellectual property strategy: Your business may have intellectual property assets including [patents/trademarks/copyrights] that protect your [unique processes/formulas/technology]. Consider what legal protections are important for your business, including patent applications for innovative processes, trademark registration for your brand, and copyright protection for original content. Focus on identifying your proprietary assets, understanding the legal requirements for protection, and developing a strategy to safeguard your competitive advantages."
    
    elif any(keyword in recent_text for keyword in ['where will you sell', 'sales location', 'sales channels', 'where will you sell your services', 'distribution channels', 'sales platforms']):
        return "Based on your business goals, here's a draft for where you will sell your services: Consider the channels and platforms where your target customers are most likely to find and purchase your services. Think about online platforms (website, e-commerce, social media), physical locations (office, retail space, client sites), or hybrid approaches. Consider how your sales location affects regulatory requirements (licensing, permits, tax obligations), marketing strategy (local vs. online marketing, SEO, advertising), and operations (logistics, delivery, customer service). Also consider competitive analysis - where do your competitors sell, and how can you differentiate your sales approach?"
    
    elif any(keyword in recent_text for keyword in ['mission', 'tagline', 'mission statement', 'business stands for']):
        return "Based on your business vision, here's a draft mission statement: [Business name] aims to [core purpose] by [key approach] to [target outcome]. Consider what your business stands for and how you would describe it in one compelling sentence. Think about your core values, purpose, and what makes you unique. Focus on creating a clear, inspiring statement that guides your business decisions and resonates with your target audience."
    
    elif any(keyword in recent_text for keyword in ['sales', 'projected sales', 'first year', 'sales projections', 'revenue', 'income']):
        return generate_sales_projection_draft(business_context, current_question)
    
    elif any(keyword in recent_text for keyword in ['startup costs', 'estimated startup costs', 'one-time expenses', 'initial costs', 'launch costs']):
        return "Based on your business needs, here's a draft for your startup costs: Your estimated startup costs should include essential one-time expenses like equipment purchases, initial inventory, legal fees, permits and licenses, website development, initial marketing campaigns, and office setup. Consider both essential startup costs and optional investments that could be deferred to manage cash flow. Focus on creating a comprehensive list of all one-time expenses needed to launch your business, including equipment, technology, legal requirements, and initial marketing. Think about equipment leasing vs. buying, bulk purchasing discounts, and phased implementation to optimize your startup investment."
    
    elif any(keyword in recent_text for keyword in ['financial', 'budget', 'costs', 'expenses', 'funding', 'investment']):
        return "Based on your business requirements, here's a draft for your financial planning: Your financial plan should include startup costs, operating expenses, cash flow projections, and funding requirements. Consider fixed costs (rent, salaries, equipment) and variable costs (materials, marketing, commissions). Focus on creating realistic budgets, identifying funding sources, and planning for financial sustainability. Think about break-even analysis, profit margins, and financial contingency planning to ensure long-term viability."
    
    else:
        return "Based on our conversation, here's a comprehensive draft response that addresses your current question with detailed insights and actionable recommendations tailored to your business context and goals. Consider breaking down complex questions into smaller parts and thinking through each aspect systematically."

async def handle_scrapping_command(reply, notes, history, session_data=None):
    """Handle the Scrapping command with actual web search research"""
    print(f"🔍 DEBUG - Scrapping command called with notes: '{notes}'")
    
    # Extract business context from history for targeted research
    business_context = extract_business_context_from_history(history)
    
    # Get current question context for more targeted responses
    current_question = get_current_question_context(history, session_data)
    
    # Generate scrapping content based on conversation history and current question
    if notes and len(notes.strip()) > 3:
        # Use the new refine function to actually refine user's input
        scrapping_content = await refine_user_input(notes, business_context, current_question)
    else:
        # Fallback to generic content if no notes provided
        scrapping_content = await generate_scrapping_content(history, business_context, notes, current_question)
    
    scrapping_response = f"Here's a refined version of your thoughts:\n\n{scrapping_content}\n\n"
    
    # If user provided specific research notes, conduct actual web search
    if notes and len(notes.strip()) > 3:
        print(f"🔍 DEBUG - Conducting web search for: '{notes}'")
        scrapping_response += f"**🔍 Researching: {notes}**\n\n"
        scrapping_response += "I'm conducting web search research to provide you with current, actionable insights. This will help refine your approach with real data and trends.\n\n"
        
        # Add web search trigger for the backend to process
        scrapping_response += f"\n\nWEBSEARCH_QUERY: {notes}"
        
        # Return the scrapping response with web search trigger
        return {
            "reply": scrapping_response,
            "web_search_status": {"is_searching": True, "query": notes, "completed": False},
            "immediate_response": None
        }
    else:
        print(f"🔍 DEBUG - No specific research topic, providing contextual analysis with web search")
        # If no specific research request, provide contextual analysis based on current question
        # Trigger web search for general scrapping as well
        web_search_query = f"{business_context.get('business_name', 'business')} {business_context.get('industry', 'business')} {get_question_topic(current_question)}"
        scrapping_response += f"\n\nWEBSEARCH_QUERY: {web_search_query}"
        
        return {
            "reply": scrapping_response,
            "web_search_status": {"is_searching": True, "query": web_search_query, "completed": False},
            "immediate_response": None
        }
    
    print(f"🔍 DEBUG - Scrapping response generated, length: {len(scrapping_response)}")
    return {
        "reply": scrapping_response,
        "web_search_status": {"is_searching": False, "query": None, "completed": False},
        "immediate_response": None
    }

async def refine_user_input(user_notes, business_context, current_question=""):
    """Refine user's actual input instead of generating generic content"""
    business_name = business_context.get("business_name", "your business")
    industry = business_context.get("industry", "your industry")
    business_type = business_context.get("business_type", "your business type")
    location = business_context.get("location", "your location")
    
    print(f"🔍 DEBUG - Refining user input: '{user_notes}' for {business_name}")
    
    # Clean up the user's notes
    cleaned_notes = user_notes.strip()
    
    # Use AI to refine and expand on user's input with proper context
    refine_prompt = f"""
    ⚠️ CRITICAL CONTEXT - READ FIRST:
        This business is in the {industry.upper()} INDUSTRY operating as a {business_type.upper()}.
    ALL refinements must be 100% specific to {industry.upper()} businesses - NOT education, NOT technology, NOT consulting.
    Use ONLY {industry.upper()} industry examples, insights, and terminology.
    
    Take this user's rough notes/ideas and refine them into a comprehensive, well-structured answer for the question: "{current_question}"
    
    User's Notes/Ideas:
    "{cleaned_notes}"
    
    Business Context (PRIMARY IDENTIFIERS):
    - Business Name: {business_name}
    - PRIMARY INDUSTRY: {industry.upper()} ⭐ (THIS IS THE CORE BUSINESS TYPE)
    - Business Structure: {business_type}
    - Location: {location}
    
    Your task:
        1. Take the user's rough ideas and refine them into polished, professional content for a {industry.upper()} business
    2. Expand on their ideas with industry-specific insights for {industry.upper()} only
    3. Add relevant details and context appropriate for a {business_type} in {location}
    4. Structure the content clearly with sections and bullet points
    5. Keep the user's core ideas but make them more comprehensive and actionable
    6. Add strategic recommendations that build on their initial thoughts
    7. ⚠️ CRITICAL WORD LIMIT: Your response MUST be exactly 100 words or less. Be concise and focused. Do not exceed 100 words.
    8. NEVER mentions unrelated industries - stay focused on {industry.upper()}
    
    Structure your refined version with:
    **Refined Core Concept:**
    [Their idea, polished and expanded for {industry.upper()} business]
    
    **{industry.upper()} Industry-Specific Application:**
    [How this applies to the {industry.upper()} industry specifically]
    
    **Strategic Recommendations for {industry.upper()} Business:**
    [3-5 specific recommendations building on their ideas]
    
    **Implementation Steps:**
    [4-6 concrete steps they can take]
    
    **Key Considerations for {industry.upper()}:**
    [2-3 important factors to consider]
    
    Make this a comprehensive refinement that takes their rough ideas and turns them into polished, actionable content.
    REMEMBER: This is a {industry.upper()} business - all refinements must be relevant to {industry.upper()}.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": refine_prompt}],
            temperature=0.3,
            max_tokens=500  # Reduced to enforce 100-word limit (approximately 500 tokens for 100 words)
        )
        
        refined_content = response.choices[0].message.content
        # Enforce 100-word limit for scrapping
        refined_content = truncate_to_word_limit(refined_content, 100)
        word_count = len(refined_content.split())
        print(f"🔍 DEBUG - AI-refined content length: {len(refined_content)} characters ({word_count} words)")
        return refined_content
    except Exception as e:
        print(f"AI refinement failed: {e}, falling back to basic refinement")
        # Fallback to basic refinement if AI fails
        if len(cleaned_notes) < 50:
            return f"""Based on your input "{cleaned_notes}", here's a refined version:

**Core Concept:**
{cleaned_notes}

**Refined Analysis:**
For {business_name} in the {industry} sector, this concept can be developed into a strategic approach that aligns with your {business_type} business model.

**Key Considerations:**
• Strategic alignment with your business goals
• Customer value proposition
• Implementation requirements
• Resource needs

**Next Steps:**
• Define specific implementation details
• Identify potential challenges
• Develop action plan"""
        
        # For longer notes, provide a concise refinement
        return f"""Based on your detailed input, here's a refined version:

**Your Core Idea:**
{cleaned_notes}

**Refined Analysis:**
This concept shows strong potential for {business_name} in the {industry} sector. The approach aligns well with {business_type} business models and can provide significant value to your target market in {location}.

**Strategic Recommendations:**
• Focus on core value proposition
• Identify key implementation steps
• Consider market positioning
• Plan for scalability

**Implementation Focus:**
• Define specific deliverables
• Establish success metrics
• Create timeline for execution"""

async def generate_scrapping_content(history, business_context, notes, current_question=""):
    """Generate concise scrapping content based on conversation history and research notes"""
    # Extract business context
    business_name = business_context.get("business_name", "your business")
    industry = business_context.get("industry", "your industry")
    business_type = business_context.get("business_type", "your business type")
    location = business_context.get("location", "your location")
    
    # Extract previous answers from history for better context
    previous_answers = []
    for msg in history[-10:]:
        if msg.get('role') == 'user' and len(msg.get('content', '')) > 20:
            content = msg.get('content', '')
            # Skip command words
            if content.lower() not in ['support', 'draft', 'scrapping', 'scraping', 'accept', 'modify']:
                previous_answers.append(content[:200])
    
    # Use AI to generate comprehensive scrapping analysis
    scrapping_prompt = f"""
    ⚠️ CRITICAL CONTEXT - READ FIRST:
        This business is in the {industry.upper()} INDUSTRY operating as a {business_type.upper()}.
    ALL analysis must be 100% specific to {industry.upper()} businesses - NOT education, NOT technology, NOT consulting.
    Use ONLY {industry.upper()} industry examples, trends, and insights.
    
    Generate a comprehensive, refined analysis that helps answer this business question: "{current_question}"
    
    Business Context (PRIMARY IDENTIFIERS):
    - Business Name: {business_name}
    - PRIMARY INDUSTRY: {industry.upper()} ⭐ (THIS IS THE CORE BUSINESS TYPE)
    - Business Structure: {business_type}
    - Location: {location}
    
    Previous Context:
    {' | '.join(previous_answers[-3:]) if previous_answers else 'No previous context available'}
    
    Research Notes (if provided):
    {notes if notes else 'No specific research notes provided'}
    
    Create a detailed, refined analysis that:
        1. Synthesizes relevant information from the {industry.upper()} business context
    2. Provides industry-specific insights for the {industry.upper()} sector only
    3. Considers market dynamics in {location}
    4. Offers strategic recommendations appropriate for a {business_type}
    5. Includes current {industry.upper()} industry trends and best practices (2024-2025)
    6. Provides actionable next steps
    7. ⚠️ CRITICAL WORD LIMIT: Your response MUST be exactly 100 words or less. Be concise and focused. Do not exceed 100 words.
    8. NEVER mentions unrelated industries - stay focused on {industry.upper()}
    
    Structure your analysis with these sections:
    **Business Context Analysis:**
    [Overview of the {industry.upper()} business and how it relates to the question]
    
    **{industry.upper()} Industry-Specific Insights:**
    [3-4 insights specific to the {industry.upper()} industry]
    
    **Market Opportunities in {industry.upper()}:**
    [2-3 opportunities in the {location} market for {industry} businesses]
    
    **Strategic Recommendations for {industry.upper()} Business:**
    [4-5 specific, actionable recommendations]
    
    **Implementation Priorities:**
    [3-4 priority actions to take]
    
    **Key Success Factors for {industry.upper()}:**
    [2-3 factors critical for success in {industry}]
    
    Make this comprehensive, strategic, and highly actionable.
    REMEMBER: This is a {industry.upper()} business - all analysis must be relevant to {industry.upper()}.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": scrapping_prompt}],
            temperature=0.3,
            max_tokens=500  # Reduced to enforce 100-word limit (approximately 500 tokens for 100 words)
        )
        
        scrapping_content = response.choices[0].message.content
        # Enforce 100-word limit for scrapping
        scrapping_content = truncate_to_word_limit(scrapping_content, 100)
        word_count = len(scrapping_content.split())
        print(f"🔍 DEBUG - AI-generated scrapping content length: {len(scrapping_content)} characters ({word_count} words)")
        return scrapping_content
    except Exception as e:
        print(f"AI scrapping generation failed: {e}, falling back to basic analysis")
        # Fallback to basic analysis
        return f"""Based on your business context, here's a refined analysis for {business_name}:

**Business Overview:**
{business_name} operates in the {industry} sector as a {business_type} business located in {location}.

**Key Focus Areas:**
• Market positioning in the {industry} sector
• Customer value proposition development
• Operational efficiency and scalability
• Competitive differentiation strategies

**Strategic Recommendations:**
• Focus on core strengths and unique value propositions
• Develop targeted customer acquisition strategies
• Implement efficient operational processes
• Build sustainable competitive advantages

**Next Steps:**
• Define specific implementation priorities
• Identify key success metrics
• Create actionable development timeline"""

async def handle_support_command(reply, history, session_data=None):
    """Handle the Support command with aggressive web search research"""
    # Extract business context for verification
    business_context = extract_business_context_from_history(history)
    
    # Get current question context for more targeted responses
    current_question = get_current_question_context(history, session_data)
    
    # ALWAYS conduct web search for Support command
    business_name = business_context.get("business_name", "business")
    industry = business_context.get("industry", "business")
    location = business_context.get("location", "")
    
    # Create targeted research query
    question_topic = get_question_topic(current_question)
    current_year = datetime.now().year
    previous_year = current_year - 1
    primary_location = location or "United States"
    
    if question_topic == "competitive analysis":
        research_query = (
            f"top {industry} competitors in {primary_location} {previous_year} {current_year} market share recent developments"
        )
    else:
        research_query = f"{industry} {question_topic} {primary_location} {previous_year} {current_year}"
    
    print(f"🔍 Support command - Conducting research: {research_query}")
    
    # Conduct comprehensive web search
    research_results = await conduct_web_search(research_query)
    
    # Generate support content based on conversation history, question, AND research
    support_content = await generate_support_content(
        history,
        business_context,
        current_question,
        research_results,
        question_topic
    )
    
    support_response = f"Let me help you with research-backed insights:\n\n{support_content}\n\n"
    support_response += (
        "When you're ready, choose the Draft quick action so I can assemble a full answer using these insights. "
        "After I share the draft, you'll be able to Accept or Modify it."
    )
    
    return support_response

async def generate_support_content(history, business_context, current_question="", research_results=None, question_topic=""):
    """Generate support content with research-backed insights and citations"""
    # Extract recent messages (both user and assistant) to understand context
    recent_messages = []
    for msg in history[-8:]:  # Look at last 8 messages (4 exchanges)
        if msg.get('content'):
            recent_messages.append(msg['content'])
    
    # Debug logging
    print(f"🔍 DEBUG - Recent messages for support context: {recent_messages}")
    print(f"🔍 DEBUG - Research results available: {bool(research_results)}")
    
    # Generate contextual support based on what they've been discussing
    if not recent_messages:
        return "I'm here to provide comprehensive support for your business planning journey. Let me help you think through the current question with additional insights and guidance."
    
    # Look for key topics in recent messages (both questions and responses)
    recent_text = " ".join(recent_messages).lower()
    print(f"🔍 DEBUG - Recent text for analysis: {recent_text[:200]}...")
    
    # Use the current_question parameter if provided, otherwise extract from history
    if not current_question:
        current_question = get_current_question_context(history, None)
    
    print(f"🔍 DEBUG - Current question context: {current_question[:100]}...")
    
    # DYNAMIC APPROACH: Use AI model to generate industry-specific support
    business_name = business_context.get("business_name", "your business")
    industry = business_context.get("industry", "your industry")
    business_type = business_context.get("business_type", "your business type")
    location = business_context.get("location", "your location")
    
    # Extract previous answers from history for better context
    previous_answers = []
    for msg in history[-10:]:
        if msg.get('role') == 'user' and len(msg.get('content', '')) > 20:
            content = msg.get('content', '')
            # Skip command words
            if content.lower() not in ['support', 'draft', 'scrapping', 'scraping', 'accept', 'modify']:
                previous_answers.append(content[:200])
    
    # Generate dynamic support using AI model with research results and citations
    research_section = ""
    if research_results:
        research_section = f"""
    
    📊 RESEARCH FINDINGS (USE THESE IN YOUR RESPONSE):
        {research_results}
    
    CRITICAL: Incorporate the research findings above into your response. Cite specific data points, statistics, and sources mentioned.
    """
    
    current_year = datetime.now().year
    previous_year = current_year - 1
    competitor_requirements = ""
    if question_topic == "competitive analysis":
        competitor_requirements = f"""
    
    ⚔️ COMPETITOR REQUIREMENTS:
        • Provide a ranked list of 5-7 named competitors active in {location or 'the primary market'} with one-line descriptions.
        • Include 2024 or {current_year} data points (funding, locations, revenue, product launches, partnerships) for each competitor—avoid citing sources older than {previous_year}.
        • Highlight differentiators and gaps that {business_name} can exploit versus each competitor.
        • Summarize recent competitive moves and cite every data point with a source published in {previous_year} or {current_year} (or the most recent available if newer).
        """

    support_prompt = f"""
    ⚠️ CRITICAL CONTEXT - READ FIRST:
        This business is in the {industry.upper()} INDUSTRY operating as a {business_type.upper()}.
    ALL guidance must be 100% specific to {industry.upper()} businesses - NOT education, NOT technology, NOT consulting.
    Focus EXCLUSIVELY on {industry.upper()} industry challenges, examples, trends, and best practices.
    {research_section}
    Ensure all statistics, market metrics, and competitor moves reference sources from {previous_year} or {current_year} whenever available. Discard any data older than {previous_year - 1} unless no newer information exists.
    {competitor_requirements}
    
    🎯 CURRENT QUESTION BEING ADDRESSED:
        "{current_question}"
    
    ⚠️ CRITICAL REQUIREMENT: Your entire response must be DIRECTLY RELEVANT to answering this specific question. Do not provide general business advice or information that doesn't directly help answer this question. Stay focused and on-topic.
    
    Business Context (PRIMARY IDENTIFIERS):
    - Business Name: {business_name}
    - PRIMARY INDUSTRY: {industry.upper()} ⭐ (THIS IS THE CORE BUSINESS TYPE)
    - Business Structure: {business_type}
    - Location: {location}
    
    Previous Context from Conversation:
    {' | '.join(previous_answers[-3:]) if previous_answers else 'No previous context available'}
    
    Provide extremely detailed, research-backed guidance that DIRECTLY ANSWERS the current question:
        1. Incorporates actual research findings, statistics, and data from authoritative sources
    2. Cites specific sources and URLs when available from the research
    3. Is highly specific to the {industry.upper()} industry with real examples and current data
    4. Considers the {location} market dynamics with local data when available
    5. Is appropriate for a {business_type} with practical, evidence-based implementation steps
    6. Includes 5-7 concrete, actionable steps backed by research and industry data
    7. References current {industry.upper()} industry trends, statistics, and best practices (2024-2025)
    8. Addresses common challenges specific to {industry.upper()} businesses with data-driven solutions
    9. Provides strategic insights backed by research and market data
    10. ⚠️ STAYS FOCUSED on the current question - do not include unrelated information
    11. CITES SOURCES throughout the response when referencing data or statistics
    
    Structure your response with:
        **Research-Backed Insights for {industry.upper()}**
    [Key findings from research with citations]
    
    **Understanding the Question**
    [What this question means for their {industry.upper()} business, with relevant data]
    
    **Industry Data & Statistics**
    [Specific data points, trends, and statistics for {industry.upper()} with sources]
    
    **Practical Action Steps (Evidence-Based)**
    [5-7 numbered, detailed action steps backed by research and data]
    
    **Common Challenges & Data-Driven Solutions**
    [2-3 challenges {industry} businesses face with research-backed solutions]
    
    **Best Practices (Industry Research)**
    [3-4 best practices from authoritative sources and industry leaders]
    
    **Sources & Citations**
    [List all sources referenced with URLs when available]
    
    Make the guidance extremely comprehensive, detailed, and research-backed. 
    ⚠️ CRITICAL WORD LIMIT: Your response MUST be exactly 150 words or less. Be concise and focused. Do not exceed 150 words.
    REMEMBER: This is a {industry.upper()} business - keep all examples, insights, and recommendations relevant to {industry.upper()}.
    CITE YOUR SOURCES throughout the response using the research findings provided.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": support_prompt}],
            temperature=0.3,
            max_tokens=800  # Reduced to enforce 150-word limit (approximately 800 tokens for 150 words)
        )
        
        generated_content = response.choices[0].message.content
        # Enforce 150-word limit
        generated_content = truncate_to_word_limit(generated_content, 150)
        word_count = len(generated_content.split())
        print(f"✅ Support content generated with {len(generated_content)} characters ({word_count} words)")
        return generated_content
    except Exception as e:
        print(f"❌ Dynamic support generation failed: {e}")
        # Fallback to basic guidance with research if available
        if research_results:
            return f"""Based on research findings for your {industry} business:

{research_results}

Let me help you apply this to your specific situation in {location}. Consider how this data relates to your {business_type} structure and the unique aspects of your {industry} business."""
        else:
            return f"Let me help you think through this question for your {industry} business. Consider the specific challenges and opportunities in the {industry} sector, especially in {location}. Focus on how this relates to your {business_type} structure and the unique aspects of your industry."
    
    

async def handle_draft_more_command(reply, history, session_data=None):
    """Handle the Draft Answer (formerly Draft More) command to create additional content"""
    # Extract business context for verification
    business_context = extract_business_context_from_history(history)
    
    # Get current question context for more targeted responses
    current_question = get_current_question_context(history, session_data)
    
    # Generate additional content based on current question
    additional_content = await generate_additional_draft_content(history, business_context, current_question)
    
    # Use consistent format with "Here's a draft" to trigger button detection
    draft_more_response = f"Here's a draft for you:\n\n{additional_content}\n\n"
    
    thought_starter = None
    if session_data and session_data.get("current_phase") == "BUSINESS_PLAN":
        current_tag = session_data.get("asked_q")
        thought_starter = get_thought_starter_for_tag(current_tag)
    if thought_starter:
        draft_more_response += f"🧠 Thought Starter: {thought_starter}\n"
    
    return draft_more_response

async def generate_additional_draft_content(history, business_context, current_question=""):
    """Generate additional draft content based on current question using AI"""
    business_name = business_context.get("business_name", "your business")
    industry = business_context.get("industry", "your industry")
    business_type = business_context.get("business_type", "your business type")
    location = business_context.get("location", "your location")
    
    # Extract previous answers from history for better context
    previous_answers = []
    for msg in history[-10:]:
        if msg.get('role') == 'user' and len(msg.get('content', '')) > 20:
            content = msg.get('content', '')
            # Skip command words
            if content.lower() not in ['support', 'draft', 'scrapping', 'scraping', 'accept', 'modify', 'draft more']:
                previous_answers.append(content[:200])
    
    # Use AI to generate enhanced additional content
    draft_more_prompt = f"""
    ⚠️ CRITICAL CONTEXT - READ FIRST:
        This business is in the {industry.upper()} INDUSTRY operating as a {business_type.upper()}.
    ALL enhanced content must be 100% specific to {industry.upper()} businesses - NOT education, NOT technology, NOT consulting.
    Use ONLY {industry.upper()} industry examples, innovations, and insights.
    
    The user requested "Draft Answer" - they want additional, enhanced content on top of what was already provided.
    
    Current Question: "{current_question}"
    
    Business Context (PRIMARY IDENTIFIERS):
    - Business Name: {business_name}
    - PRIMARY INDUSTRY: {industry.upper()} ⭐ (THIS IS THE CORE BUSINESS TYPE)
    - Business Structure: {business_type}
    - Location: {location}
    
    Previous Context:
    {' | '.join(previous_answers[-3:]) if previous_answers else 'No previous context available'}
    
    Generate ENHANCED, ADDITIONAL content that:
        1. Takes the original answer to the next level with MORE detail for {industry.upper()} businesses
    2. Adds 3-5 UNIQUE angles or perspectives specific to {industry.upper()} industry
    3. Provides ADVANCED strategic insights specific to {industry.upper()} in {location}
    4. Includes innovative ideas and creative approaches for {industry} businesses
    5. Offers cutting-edge {industry.upper()} industry trends and best practices (2024-2025)
    6. Makes it stand out with unique value propositions
    7. ⚠️ CRITICAL WORD LIMIT: Your response MUST be exactly 100 words or less. Be concise and focused. Do not exceed 100 words.
    8. NEVER mentions unrelated industries - stay focused on {industry.upper()}
    
    Structure your enhanced draft with:
    **Enhanced Main Content:**
    [Take the original concept and elevate it with unique insights for {industry.upper()}]
    
    **Unique Angles & Innovation for {industry.upper()}:**
    [3-5 creative approaches specific to {industry} businesses]
    
    **Advanced Strategic Insights for {industry.upper()}:**
    [Deep industry-specific strategies for {industry.upper()}]
    
    **Implementation Roadmap:**
    [Detailed 5-7 step plan with specifics]
    
    **Competitive Edge Factors in {industry.upper()}:**
    [What makes this approach uniquely powerful for {industry} businesses]
    
    Make this draft MORE creative, MORE detailed, and MORE strategic than a standard response. Think outside the box!
    REMEMBER: This is a {industry.upper()} business - all enhanced content must be relevant to {industry.upper()}.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": draft_more_prompt}],
            temperature=0.4,  # Slightly higher for more creativity
            max_tokens=500  # Reduced to enforce 100-word limit (approximately 500 tokens for 100 words)
        )
        
        enhanced_content = response.choices[0].message.content
        # Enforce 100-word limit
        enhanced_content = truncate_to_word_limit(enhanced_content, 100)
        word_count = len(enhanced_content.split())
        print(f"🔍 DEBUG - AI-generated enhanced draft length: {len(enhanced_content)} characters ({word_count} words)")
        return enhanced_content
    except Exception as e:
        print(f"AI enhanced draft generation failed: {e}, falling back to template")
        # Fallback to template if AI fails
        pass
    
    # Fallback templates if AI generation fails
    if any(keyword in current_question.lower() for keyword in ['target market', 'demographics', 'psychographics', 'behaviors', 'ideal customer']):
        return f"""Here's additional detailed content for your target market strategy:

**Customer Journey Mapping:**
Map out the complete customer journey for {business_name} from awareness to purchase to retention. Identify touchpoints where your {business_type} business can engage with customers and create positive experiences that drive loyalty and referrals.

**Market Segmentation Deep Dive:**
Break down your target market into micro-segments within the {industry} sector. Consider factors like company size, decision-making processes, budget ranges, and pain point severity. This helps you create more targeted messaging and offerings.

**Competitive Differentiation:**
Identify specific ways {business_name} can differentiate from competitors in the {industry} space. Focus on unique value propositions, service delivery methods, or customer experience elements that competitors cannot easily replicate.

**Customer Acquisition Channels:**
Detail the specific channels and tactics that work best for reaching your target market in the {industry} sector. Consider both digital and traditional channels, and how they align with your customers' preferences and behaviors.

**Pricing Strategy Alignment:**
Ensure your pricing strategy aligns with your target market's willingness to pay and budget constraints. Consider value-based pricing that reflects the specific benefits your {business_type} solution provides to customers in the {industry} sector."""

    elif any(keyword in current_question.lower() for keyword in ['competitor', 'competition', 'main competitors', 'strengths and weaknesses', 'competitive advantage']):
        return f"""Here's additional detailed content for your competitive analysis:

**Competitive Intelligence Framework:**
Develop a systematic approach to monitor competitors in the {industry} sector. Track their pricing changes, product launches, marketing campaigns, and customer feedback to identify opportunities and threats.

**Market Positioning Analysis:**
Analyze how competitors position themselves in the {industry} market and identify positioning gaps that {business_name} can exploit. Consider emotional positioning, functional positioning, and price positioning strategies.

**Competitive Response Strategy:**
Develop specific strategies for how {business_name} will respond to competitive actions. This includes defensive strategies to protect market share and offensive strategies to gain competitive advantage.

**Partnership Opportunities:**
Identify potential partnership opportunities with complementary businesses in the {industry} sector. Strategic partnerships can help {business_name} compete more effectively against larger competitors.

**Innovation Differentiation:**
Focus on innovation areas where {business_name} can lead the {industry} market. Consider technology adoption, service delivery innovation, or business model innovation that creates sustainable competitive advantages."""

    else:
        return f"""Here's additional detailed content for your business planning:

**Implementation Timeline:**
Create a detailed timeline for implementing your strategies, including key milestones, dependencies, and resource requirements. This helps ensure realistic planning and successful execution.

**Risk Assessment and Mitigation:**
Identify potential risks and challenges for {business_name} in the {industry} sector, and develop specific mitigation strategies for each risk. This includes market risks, operational risks, and competitive risks.

**Success Metrics and KPIs:**
Define specific, measurable success metrics that align with your business objectives. Include both leading indicators (early warning signs) and lagging indicators (outcome measures) to track progress effectively.

**Resource Planning:**
Detail the specific resources {business_name} needs to execute your strategies, including human resources, technology, capital, and partnerships. Ensure resource allocation aligns with your strategic priorities.

**Growth Strategy:**
Develop a comprehensive growth strategy that includes market expansion, product development, and scaling considerations. Focus on sustainable growth that maintains quality and customer satisfaction."""

def handle_kickstart_command(reply, history, session_data):
    """Handle the Kickstart command"""
    kickstart_response = f"Here are some kickstart resources to get you moving:\n\n{reply}\n\n"
    kickstart_response += "These templates and frameworks are customized for your business context. "
    kickstart_response += "Would you like me to:\n• **Customize** these further for your specific needs\n• **Provide** additional templates or checklists\n• **Move forward** with the current resources"
    
    return kickstart_response

def handle_contact_command(reply, history, session_data):
    """Handle the Who do I contact? command"""
    contact_response = f"Based on your business needs, here are some trusted professionals:\n\n{reply}\n\n"
    contact_response += "These recommendations are tailored to your industry, location, and business stage. "
    contact_response += "Would you like me to:\n• **Research** more specific providers in your area\n• **Provide** contact templates for reaching out\n• **Suggest** questions to ask when interviewing them"
    
    return contact_response

def extract_conversation_context(history):
    """Extract relevant context from conversation history"""
    recent_messages = history[-6:] if len(history) > 6 else history
    context = []
    
    for msg in recent_messages:
        if msg["role"] == "user" and len(msg["content"]) > 10:
            context.append(msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"])
    
    return " | ".join(context)

def extract_business_context_from_history(history):
    """Extract business context information from conversation history with weighted priority"""
    business_context = {
        "business_name": "",
        "industry": "",
        "location": "",
        "business_type": "",
        "target_market": "",
        "business_idea": ""
    }
    
    # Track weights for prioritization (higher = more authoritative)
    context_weights = {
        "business_name": 0,
        "industry": 0,
        "location": 0,
        "business_type": 0,
        "target_market": 0,
        "business_idea": 0
    }
    
    print(f"🔍 DEBUG - Extracting business context from {len(history)} messages with weighted priority")
    
    # NO MORE HARDCODED OVERRIDES - Let AI naturally detect business type from conversation
    # Removed plumbing-specific override logic - system now works for ALL business types dynamically
    
    # First pass: Identify KYC and Business Plan questions to prioritize their answers
    kyc_question_indices = {}
    for i, msg in enumerate(history):
        if msg["role"] == "assistant":
            content = msg["content"]
            # KYC questions
            if "[[Q:KYC.12]]" in content:  # Industry question (renumbered from KYC.11)
                kyc_question_indices["industry"] = i
                print(f"🔍 DEBUG - Found KYC.12 (industry question) at index {i}")
            elif "[[Q:KYC.17]]" in content:  # Business structure question (renumbered from KYC.16)
                kyc_question_indices["business_type"] = i
                print(f"🔍 DEBUG - Found KYC.17 (business type question) at index {i}")
            elif "[[Q:KYC.10]]" in content:  # Business location question
                kyc_question_indices["location"] = i
                print(f"🔍 DEBUG - Found KYC.10 (business location question) at index {i}")
            elif "[[Q:KYC.11]]" in content:  # Business offering location question
                kyc_question_indices["offering_location"] = i
                print(f"🔍 DEBUG - Found KYC.11 (business offering location question) at index {i}")
            # Business Plan Question 1 - Business Name (HIGHEST PRIORITY)
            elif "[[Q:BUSINESS_PLAN.01]]" in content or "[[Q:BP.01]]" in content:
                kyc_question_indices["business_name"] = i
                print(f"🔍 DEBUG - Found BP.01 (business name question) at index {i}")
    
    # Extract from all messages (not just recent ones)
    for i, msg in enumerate(history):
        if msg["role"] == "user":
            content = msg["content"]
            content_lower = content.lower()
            
            print(f"🔍 DEBUG - Message {i}: {content[:100]}...")
            
            # Check if this is a response to a KYC or BP question (HIGHEST PRIORITY - weight 100)
            is_bp_name_answer = "business_name" in kyc_question_indices and i == kyc_question_indices["business_name"] + 1
            is_kyc_industry_answer = "industry" in kyc_question_indices and i == kyc_question_indices["industry"] + 1
            is_kyc_business_type_answer = "business_type" in kyc_question_indices and i == kyc_question_indices["business_type"] + 1
            is_kyc_location_answer = "location" in kyc_question_indices and i == kyc_question_indices["location"] + 1
            is_kyc_offering_location_answer = "offering_location" in kyc_question_indices and i == kyc_question_indices["offering_location"] + 1
            is_bp_sales_location_answer = "sales_location" in kyc_question_indices and i == kyc_question_indices["sales_location"] + 1
            
            # Extract business name from BP.01 answer (HIGHEST PRIORITY - weight 100)
            if is_bp_name_answer and len(content.strip()) > 2:
                # Use the user's exact answer as business name
                business_name_answer = content.strip()
                # Remove common command words if present
                command_words = ["support", "draft", "scrapping", "accept", "modify"]
                is_command = any(cmd in business_name_answer.lower() for cmd in command_words)
                if not is_command:
                    business_context["business_name"] = business_name_answer
                    context_weights["business_name"] = 100
                    print(f"🔍 DEBUG - ⭐ HIGHEST PRIORITY: BP.01 business name answer (EXACT): '{business_name_answer}' (weight 100)")
            
            # Extract industry from KYC.12 answer - Use user's EXACT answer (renumbered from KYC.11)
            if is_kyc_industry_answer and len(content.strip()) > 2:
                # Use the user's exact answer - no keyword matching, no hardcoding
                industry_answer = content.strip()
                business_context["industry"] = industry_answer
                context_weights["industry"] = 100
                print(f"🔍 DEBUG - ⭐ HIGHEST PRIORITY: KYC.12 industry answer (EXACT): '{industry_answer}' (weight 100)")
            
            # Extract business type from KYC.17 answer (HIGHEST PRIORITY) (renumbered from KYC.16)
            if is_kyc_business_type_answer and len(content.strip()) > 2:
                business_type_answer = content.strip()
                business_context["business_type"] = business_type_answer
                context_weights["business_type"] = 100
                print(f"🔍 DEBUG - ⭐ HIGHEST PRIORITY: KYC.17 business type answer: '{business_type_answer}' (weight 100)")
            
            # Extract business location from KYC.10 answer (HIGHEST PRIORITY)
            if is_kyc_location_answer and len(content.strip()) > 2:
                location_answer = content.strip()
                business_context["location"] = location_answer
                context_weights["location"] = 100
                print(f"🔍 DEBUG - ⭐ HIGHEST PRIORITY: KYC.10 business location answer: '{location_answer}' (weight 100)")
            
            # Extract business offering location from KYC.11 answer (HIGHEST PRIORITY)
            if is_kyc_offering_location_answer and len(content.strip()) > 2:
                offering_location_answer = content.strip()
                business_context["offering_location"] = offering_location_answer
                context_weights["offering_location"] = 100
                print(f"🔍 DEBUG - ⭐ HIGHEST PRIORITY: KYC.11 business offering location answer: '{offering_location_answer}' (weight 100)")
            
            # Extract sales location from BP.08 answer (HIGHEST PRIORITY)
            if is_bp_sales_location_answer and len(content.strip()) > 2:
                sales_location_answer = content.strip()
                business_context["sales_location"] = sales_location_answer
                context_weights["sales_location"] = 100
                print(f"🔍 DEBUG - ⭐ HIGHEST PRIORITY: BP.08 sales location answer: '{sales_location_answer}' (weight 100)")
            
            # Extract previously mentioned staff (for context in future questions)
            import re
            staff_keywords = ['secretary', 'assistant', 'receptionist', 'office manager', 'bookkeeper', 'accountant', 'staff', 'employee', 'worker']
            for keyword in staff_keywords:
                # Pattern to match: (number)? (office )? (a/an )? keyword (s)?
                # Use word boundaries to avoid partial matches
                pattern = r'\b(\d+)?\s*(?:office\s+)?(?:a\s+|an\s+)?' + re.escape(keyword) + r's?\b'
                matches = re.finditer(pattern, content_lower)
                found_match = False
                for match in matches:
                    full_match = match.group(0)  # The full matched string
                    number = match.group(1)  # The number group (if present)
                    
                    # Extract the full phrase including "office" if present
                    if number:
                        # Has a number, include it
                        staff_mention = f"{number} {full_match.replace(number, '').strip()}"
                    else:
                        # No number, use the full match
                        staff_mention = full_match.strip()
                    
                    # Clean up the mention (remove extra spaces, normalize)
                    staff_mention = re.sub(r'\s+', ' ', staff_mention).strip()
                    
                    # Add to list if not already present
                    if "staffing_needs" not in business_context:
                        business_context["staffing_needs"] = []
                    if staff_mention and staff_mention not in business_context["staffing_needs"]:
                        business_context["staffing_needs"].append(staff_mention)
                        print(f"🔍 DEBUG - Found staff mention in extract_business_context: '{staff_mention}'")
                        found_match = True
                if found_match:
                    break  # Only process first keyword match per message
            
            # Extract business name - prioritize domain names and longer names over short responses
            # First check for domain-like names (highest priority - weight 80)
            if "." in content and any(ext in content_lower for ext in [".com", ".net", ".org", ".co"]):
                potential_name = content.strip()
                command_words = ["support", "draft", "scrapping", "scraping", "accept", "modify", "ok", "okay", "yes", "no", "small business", "corporation", "llc", "inc", "sole proprietorship"]
                # Limit business name to reasonable length to prevent long content
                if len(potential_name) > 5 and len(potential_name) < 50 and potential_name.lower() not in command_words:
                    if context_weights["business_name"] < 80:
                        business_context["business_name"] = potential_name
                        context_weights["business_name"] = 80
                        print(f"🔍 DEBUG - Found domain business name: {potential_name} (weight 80)")
            
            # Then look for patterns like "my business is", "company name", etc. (weight 70)
            elif context_weights["business_name"] < 70 and any(phrase in content_lower for phrase in ["my business is", "company name", "startup name", "business name", "what is your business name"]):
                # Extract the name after these phrases
                for phrase in ["my business is", "company name", "startup name", "business name", "what is your business name"]:
                    if phrase in content_lower:
                        parts = content.split(phrase)
                        if len(parts) > 1:
                            potential_name = parts[1].strip().split()[0]
                            if len(potential_name) > 2:
                                business_context["business_name"] = potential_name
                                context_weights["business_name"] = 70
                                print(f"🔍 DEBUG - Found business name: {potential_name} (weight 70)")
                                break
            
            # Finally look for direct business name responses (weight 50)
            elif context_weights["business_name"] < 50 and len(content.strip()) < 100 and not any(word in content_lower for word in ["yes", "no", "maybe", "i", "my", "the", "a", "an"]) and not any(char.isdigit() for char in content.strip()):
                # If it's a short response that looks like a business name (and doesn't contain numbers)
                potential_name = content.strip()
                # Exclude command words and common responses
                command_words = ["support", "draft", "scrapping", "scraping", "accept", "modify", "ok", "okay", "yes", "no", "small business", "corporation", "llc", "inc", "sole proprietorship", "sure", "financial", "personal savings"]
                # Allow domain names and business names with dots, hyphens, etc.
                if len(potential_name) > 2 and potential_name.lower() not in command_words:
                    # Check if it looks like a business name (contains letters and possibly dots, hyphens)
                    if any(c.isalpha() for c in potential_name) and not potential_name.lower() in ["small business", "corporation", "llc", "inc"]:
                            business_context["business_name"] = potential_name
                            context_weights["business_name"] = 50
                            print(f"🔍 DEBUG - Found direct business name: {potential_name} (weight 50)")
            
            # Extract industry from natural conversation - use exact user words, no keyword lists
            # Only as fallback if KYC answer not available (weight < 100)
            if context_weights["industry"] < 50:
                # Look for business/industry mentions in user's own words
                if any(phrase in content_lower for phrase in ["business", "company", "startup", "industry", "service"]):
                    # Extract the full phrase - let AI understand it later
                    if len(content.strip()) > 5 and len(content.strip()) < 100:
                        # Use user's exact words as industry descriptor
                        business_context["industry"] = content.strip()
                        context_weights["industry"] = 20
                        print(f"🔍 DEBUG - Using user's exact description as industry: '{content.strip()[:50]}' (weight 20)")
            
            # Extract location information - Only if not from KYC (weight < 100)
            if context_weights["location"] < 100:
                # Look for location mentions
                if any(phrase in content_lower for phrase in ["located in", "based in", "karachi", "lahore", "islamabad", "city", "location"]):
                    # Look for city names or location patterns
                    locations = ["karachi", "lahore", "islamabad", "rawalpindi", "faisalabad", "multan", "peshawar", "quetta", "sialkot", "gujranwala"]
                    for location in locations:
                        if location in content_lower:
                            if context_weights["location"] < 50:
                                business_context["location"] = location.title()
                                context_weights["location"] = 50
                                print(f"🔍 DEBUG - Found location: {location} (weight 50)")
                            break
                    # If no specific city found, look for "located in" pattern
                    if context_weights["location"] < 50 and "located in" in content_lower:
                        parts = content.split("located in")
                        if len(parts) > 1:
                            potential_location = parts[1].strip().split()[0]
                            if len(potential_location) > 2:
                                business_context["location"] = potential_location.title()
                                context_weights["location"] = 50
                                print(f"🔍 DEBUG - Found location from pattern: {potential_location} (weight 50)")
            
            # Extract business type - Only if not from KYC (weight < 100)
            if context_weights["business_type"] < 100:
                # Look for business type mentions
                if any(phrase in content_lower for phrase in ["business type", "type of business", "startup", "company", "corporation", "llc", "partnership"]):
                    business_types = ["startup", "company", "corporation", "llc", "partnership", "sole proprietorship", "nonprofit", "franchise"]
                    for biz_type in business_types:
                        if biz_type in content_lower:
                            if context_weights["business_type"] < 50:
                                business_context["business_type"] = biz_type
                                context_weights["business_type"] = 50
                                print(f"🔍 DEBUG - Found business type: {biz_type} (weight 50)")
                            break
            
            # Extract business idea - look for longer descriptive responses
            if not business_context["business_idea"] and len(content.strip()) > 20:
                # Look for business idea descriptions with specific keywords
                if any(phrase in content_lower for phrase in ["tea good", "on tap", "business idea", "my idea", "startup idea", "venture", "business concept"]):
                    # For tea-related descriptions, capture the full content
                    if any(phrase in content_lower for phrase in ["tea good", "on tap"]):
                        business_context["business_idea"] = content.strip()
                        print(f"🔍 DEBUG - Found tea business idea: {content}")
                    else:
                        # Extract a reasonable portion of the business idea
                        for phrase in ["business idea", "my idea", "startup idea", "venture", "business concept"]:
                            if phrase in content_lower:
                                parts = content.split(phrase)
                                if len(parts) > 1:
                                    idea_text = parts[1].strip()[:100]  # First 100 characters
                                    if len(idea_text) > 10:
                                        business_context["business_idea"] = idea_text
                                        print(f"🔍 DEBUG - Found business idea: {idea_text}")
                                        break
                # Also capture longer responses that might be business ideas (but exclude preference responses)
                elif len(content.strip()) > 30 and not any(word in content_lower for word in ["yes", "no", "maybe", "support", "draft", "scrapping", "hands-on", "decide", "personal savings", "subscriptions", "online only"]):
                    business_context["business_idea"] = content.strip()
                    print(f"🔍 DEBUG - Found business idea (long response): {content[:50]}...")
    
    print(f"🔍 DEBUG - Final business context: {business_context}")
    print(f"🔍 DEBUG - Context weights: {context_weights}")
    print(f"⭐ PRIORITY SUMMARY - Industry: '{business_context.get('industry', 'N/A')}' (weight: {context_weights['industry']}), Business Type: '{business_context.get('business_type', 'N/A')}' (weight: {context_weights['business_type']})")
    return business_context

async def handle_competitor_research_request(user_input, business_context, history):
    """Handle specific requests for competitor research"""
    
    # Extract business information for targeted research
    industry = business_context.get("industry", "")
    location = business_context.get("location", "")
    business_name = business_context.get("business_name", "")
    business_type = business_context.get("business_type", "")
    
    # Create targeted research queries
    research_queries = []
    
    if industry:
        research_queries.append(f"main competitors in {industry} industry")
        research_queries.append(f"top companies in {industry} market")
        research_queries.append(f"{industry} industry leaders and market share")
    
    if location and industry:
        research_queries.append(f"{industry} companies in {location}")
        research_queries.append(f"local {industry} competitors in {location}")
    
    if business_type:
        research_queries.append(f"{business_type} business competitors")
        research_queries.append(f"successful {business_type} companies")
    
    # Conduct web search for competitor research
    competitor_research_results = []
    
    for query in research_queries[:3]:  # Limit to 3 queries for efficiency
        try:
            search_result = await conduct_web_search(query)
            if search_result and "unable to conduct web research" not in search_result:
                competitor_research_results.append({
                    "query": query,
                    "result": search_result
                })
        except Exception as e:
            print(f"Error conducting competitor research for query '{query}': {e}")
    
    # Generate comprehensive competitor analysis
    if competitor_research_results:
        analysis_prompt = f"""
        Based on the following research results, provide a comprehensive competitor analysis for a business in the {industry} industry:
        
        Business Context:
        - Industry: {industry}
        - Location: {location}
        - Business Type: {business_type}
        - Business Name: {business_name}
        
        Research Results:
        {chr(10).join([f"Query: {r['query']}{chr(10)}Result: {r['result']}{chr(10)}" for r in competitor_research_results])}
        
        Please provide:
        1. Main competitors identified
        2. Market positioning analysis
        3. Competitive advantages and weaknesses
        4. Market opportunities
        5. Strategic recommendations
        
        Make this analysis actionable and specific to the business context.
        """
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": analysis_prompt}],
                temperature=0.7,
                max_tokens=1500
            )
            
            return {
                "success": True,
                "analysis": response.choices[0].message.content,
                "research_sources": len(competitor_research_results),
                "queries_used": [r["query"] for r in competitor_research_results]
            }
        except Exception as e:
            print(f"Error generating competitor analysis: {e}")
            return {
                "success": False,
                "error": "Failed to generate competitor analysis",
                "research_sources": len(competitor_research_results)
            }
    else:
        return {
            "success": False,
            "error": "Unable to conduct competitor research at this time",
            "research_sources": 0
        }

async def generate_business_plan_artifact_async(session_data, conversation_history):
    """Generate business plan artifact in background (non-blocking)"""
    try:
        print("📄 Background: Generating COMPLETE Business Plan Artifact...")
        artifact = await generate_business_plan_artifact(session_data, conversation_history)
        artifact_length = len(artifact) if artifact else 0
        print(f"✅ Background: Business Plan Artifact generated: {artifact_length} characters")
        
        # Save artifact to session in background
        from services.session_service import patch_session
        session_id = session_data.get("id") or session_data.get("session_id")
        if session_id and artifact:
            await patch_session(session_id, {"business_plan_artifact": artifact})
            print(f"✅ Background: Artifact saved to session {session_id}")
        
        return artifact
    except Exception as e:
        print(f"❌ Background: Error generating artifact: {str(e)}")
        return None

async def generate_business_plan_artifact(session_data, conversation_history):
    """Generate comprehensive business plan artifact with deep research"""
    
    # Conduct comprehensive research for business plan
    industry = session_data.get('industry', 'general business')
    location = session_data.get('location', 'United States')
    
    current_year = datetime.now().year
    previous_year = current_year - 1
    
    print(f"🔍 Conducting research for {industry} business in {location}")
    
    # OPTIMIZED: Use asyncio with timeout to prevent blocking - only do 2 quick searches
    # If searches timeout, continue without them (artifact will still be comprehensive)
    async def quick_search(query, timeout=5):
        try:
            return await asyncio.wait_for(conduct_web_search(query), timeout=timeout)
        except asyncio.TimeoutError:
            print(f"⏱️ Search timeout for: {query[:50]}... (continuing without it)")
            return None
        except Exception as e:
            print(f"⚠️ Search error for {query[:50]}: {str(e)} (continuing without it)")
            return None
    
    # Only do 2 essential searches (market and competitor) with timeout
    # This prevents long delays while still providing valuable research
    market_research_task = quick_search(f"market analysis {industry} {location} {previous_year}", timeout=8)
    competitor_research_task = quick_search(f"top competitors {industry} business model analysis {previous_year}", timeout=8)
    
    # Run searches in parallel and wait for both (or timeout)
    market_research, competitor_research = await asyncio.gather(
        market_research_task, 
        competitor_research_task,
        return_exceptions=True
    )
    
    # Handle exceptions
    if isinstance(market_research, Exception):
        print(f"⚠️ Market research failed: {market_research}")
        market_research = None
    if isinstance(competitor_research, Exception):
        print(f"⚠️ Competitor research failed: {competitor_research}")
        competitor_research = None
    
    # Skip optional searches (trends and financial) to speed up generation
    # These can be added later if needed, but they're causing timeouts
    industry_trends = None
    financial_benchmarks = None
    print(f"⚡ Using optimized research: Market={bool(market_research)}, Competitor={bool(competitor_research)}")
    
    # Get full conversation history for comprehensive business plan
    # Use more history to ensure we capture all business plan answers
    full_history = conversation_history if len(conversation_history) <= 100 else conversation_history[-100:]
    print(f"📚 Using {len(full_history)} messages from conversation history for business plan generation")
    
    business_plan_prompt = f"""
    ⚠️⚠️⚠️ CRITICAL FORMAT REQUIREMENT - READ THIS FIRST ⚠️⚠️⚠️
    
    YOUR OUTPUT MUST START WITH EXACTLY THIS TEXT (NO EXCEPTIONS):
    
    ## Scene 1 - Executive Summary & Business Overview
    
    ### Business Plan Summary Table
    
    | Section | Highlights |
    |---------|------------|
    
    YOU MUST HAVE EXACTLY 8 SCENES WITH THESE EXACT HEADERS:
    1. ## Scene 1 - Executive Summary & Business Overview
    2. ## Scene 2 - Company Description & Business Model
    3. ## Scene 3 - Market Analysis & Research
    4. ## Scene 4 - Competitive Analysis
    5. ## Scene 5 - Product/Service Offering
    6. ## Scene 6 - Marketing & Sales Strategy
    7. ## Scene 7 - Financial Projections & Funding
    8. ## Scene 8 - Operations, Risk Management & Implementation Timeline
    
    FORBIDDEN - DO NOT USE:
    ❌ "Executive Summary" (without "Scene 1 -")
    ❌ "Company Description" (without "Scene 2 -")
    ❌ Any traditional section headers
    
    NOW GENERATE THE BUSINESS PLAN:
    
    Generate a COMPREHENSIVE, DETAILED, and PROFESSIONAL business plan document in EXACTLY 8 SCENES with TABLES based on the following conversation history and extensive research.
    
    **CRITICAL REQUIREMENTS**:
    1. This MUST be structured as exactly 8 scenes (Scene 1 through Scene 8) - NO MORE, NO LESS
    2. Each scene MUST start with at least one table in markdown format
    3. After each table, provide 2-3 detailed paragraphs expanding on the table content
    4. Extract ALL information from the conversation history - use ACTUAL data, NOT placeholders
    5. Reference and align with "Business Plan Deep Research Questions V2" to ensure comprehensive coverage
    6. Use the user's answers from the conversation history as the foundation
    7. Enhance with research-driven insights to create a professional, investor-ready document
    8. Format as a professional business plan with clear scene headers (## Scene X - Title)
    9. Each scene should be 2-3 pages of content when formatted (tables + detailed paragraphs)
    10. Total document should be 15-20 pages when formatted
    
    **Session Data**:
    {json.dumps(session_data, indent=2)}
    
    **Deep Research Conducted**:
    Market Analysis: {market_research[:2000] if market_research else "Research pending"}
    Competitor Analysis: {competitor_research[:2000] if competitor_research else "Research pending"}
    Industry Trends: {industry_trends[:2000] if industry_trends else "Research pending"}
    Financial Benchmarks: {financial_benchmarks[:2000] if financial_benchmarks else "Research pending"}
    
    **Full Conversation History** (all business plan Q&A):
    {json.dumps(full_history, indent=2)}
    
    **CRITICAL DATA EXTRACTION INSTRUCTIONS**:
    - Read through the conversation history above carefully
    - Extract ACTUAL business information from user's answers
    - Replace ALL placeholders like "[Extract from conversation]" with REAL data from the conversation
    - If information is not found in the conversation, state "Not yet specified" instead of using placeholders
    - Use the actual business name: {session_data.get('business_name', 'Your Business')}
    - Use the actual industry: {session_data.get('industry', 'General Business')}
    - Use the actual location: {session_data.get('location', 'United States')}
    - Extract mission statements, value propositions, target markets, revenue models, etc. from actual user answers
    - DO NOT make up information - only use what's in the conversation history
    
    **Reference Document**: Business Plan Deep Research Questions V2
    
    **MANDATORY FORMAT - 8 SCENES WITH TABLES**:
    
    You MUST structure the business plan as 8 distinct scenes, each with tables. Follow this exact format:
    
    ## Scene 1 - Executive Summary & Business Overview
    
    ### Business Plan Summary Table
    
    | Section | Highlights |
    |---------|------------|
    | **Mission & Vision** | [Extract actual mission statement and vision from conversation history] |
    | **Target Market** | [Extract target market details from conversation history] |
    | **Problem & Solution** | [Extract problem statement and solution from conversation history] |
    | **Revenue Model** | [Extract revenue model and pricing from conversation history] |
    | **Marketing & Growth** | [Extract marketing strategy and growth plans from conversation history] |
    | **Legal & Operations** | [Extract legal structure and operational details from conversation history] |
    | **Financial Projections** | [Extract key financial projections from conversation history] |
    | **Risk Management** | [Extract risk analysis and mitigation strategies from conversation history] |
    
    [Then provide detailed paragraphs expanding on each section above]
    
    ## Scene 2 - Company Description & Business Model
    
    ### Company Overview Table
    
    | Aspect | Details |
    |--------|---------|
    | **Business Name** | [Extract from conversation] |
    | **Legal Structure** | [Extract from conversation] |
    | **Industry** | [Extract from conversation] |
    | **Location** | [Extract from conversation] |
    | **Business Type** | [Extract from conversation] |
    | **Founded/Launch Date** | [Extract or estimate from conversation] |
    | **Mission Statement** | [Extract from conversation] |
    | **Vision Statement** | [Extract from conversation] |
    
    ### Business Model Table
    
    | Component | Description |
    |-----------|-------------|
    | **Value Proposition** | [Extract from conversation] |
    | **Revenue Streams** | [Extract from conversation] |
    | **Pricing Strategy** | [Extract from conversation] |
    | **Key Partnerships** | [Extract from conversation] |
    | **Key Resources** | [Extract from conversation] |
    | **Key Activities** | [Extract from conversation] |
    | **Customer Segments** | [Extract from conversation] |
    | **Cost Structure** | [Extract from conversation] |
    
    [Then provide detailed paragraphs expanding on each section above]
    
    ## Scene 3 - Market Analysis & Research
    
    ### Market Research Findings Table
    
    | Research Area | Findings | Source Type |
    |---------------|----------|-------------|
    | **Market Size** | [Extract from conversation and research] | [Government/Academic/Industry] |
    | **Market Growth** | [Extract from conversation and research] | [Government/Academic/Industry] |
    | **Target Demographics** | [Extract from conversation] | User Input |
    | **Customer Needs** | [Extract from conversation] | User Input |
    | **Market Trends** | [From research conducted] | Industry Reports |
    | **Market Opportunity** | [Extract from conversation] | User Input |
    
    ### Target Market Segmentation Table
    
    | Segment | Description | Size | Growth Rate | Priority |
    |---------|-------------|------|-------------|----------|
    | **Primary Segment** | [Extract from conversation] | [Estimate] | [From research] | High |
    | **Secondary Segment** | [Extract from conversation] | [Estimate] | [From research] | Medium |
    | **Tertiary Segment** | [Extract from conversation] | [Estimate] | [From research] | Low |
    
    [Then provide detailed paragraphs expanding on each section above]
    
    ## Scene 4 - Competitive Analysis
    
    ### Competitive Landscape Table
    
    | Competitor | Strengths | Weaknesses | Market Position | Our Advantage |
    |------------|-----------|------------|------------------|---------------|
    | **[Competitor 1]** | [From research] | [From research] | [From research] | [Extract from conversation] |
    | **[Competitor 2]** | [From research] | [From research] | [From research] | [Extract from conversation] |
    | **[Competitor 3]** | [From research] | [From research] | [From research] | [Extract from conversation] |
    
    ### SWOT Analysis Table
    
    | Category | Factor | Impact | Strategy |
    |----------|--------|--------|---------|
    | **Strengths** | [Extract from conversation] | High/Medium/Low | [Extract from conversation] |
    | **Weaknesses** | [Extract from conversation] | High/Medium/Low | [Extract from conversation] |
    | **Opportunities** | [Extract from conversation] | High/Medium/Low | [Extract from conversation] |
    | **Threats** | [Extract from conversation] | High/Medium/Low | [Extract from conversation] |
    
    [Then provide detailed paragraphs expanding on each section above]
    
    ## Scene 5 - Product/Service Offering
    
    ### Product/Service Features Table
    
    | Feature | Description | Benefit | Priority | Status |
    |---------|-------------|---------|----------|--------|
    | **[Feature 1]** | [Extract from conversation] | [Extract from conversation] | High/Medium/Low | Planned/In Development/Launched |
    | **[Feature 2]** | [Extract from conversation] | [Extract from conversation] | High/Medium/Low | Planned/In Development/Launched |
    | **[Feature 3]** | [Extract from conversation] | [Extract from conversation] | High/Medium/Low | Planned/In Development/Launched |
    
    ### Product Development Roadmap Table
    
    | Phase | Timeline | Key Features | Milestones | Resources Needed |
    |-------|----------|--------------|------------|-----------------|
    | **Phase 1** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] |
    | **Phase 2** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] |
    | **Phase 3** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] |
    
    [Then provide detailed paragraphs expanding on each section above]
    
    ## Scene 6 - Marketing & Sales Strategy
    
    ### Marketing Channels Table
    
    | Channel | Strategy | Budget Allocation | Expected ROI | Timeline |
    |---------|----------|-------------------|--------------|----------|
    | **[Channel 1]** | [Extract from conversation] | [Extract from conversation] | [Estimate] | [Extract from conversation] |
    | **[Channel 2]** | [Extract from conversation] | [Extract from conversation] | [Estimate] | [Extract from conversation] |
    | **[Channel 3]** | [Extract from conversation] | [Extract from conversation] | [Estimate] | [Extract from conversation] |
    
    ### Sales Process Table
    
    | Stage | Activity | Duration | Conversion Rate | Tools/Resources |
    |-------|----------|----------|-----------------|-----------------|
    | **Lead Generation** | [Extract from conversation] | [Extract from conversation] | [Estimate] | [Extract from conversation] |
    | **Qualification** | [Extract from conversation] | [Extract from conversation] | [Estimate] | [Extract from conversation] |
    | **Proposal** | [Extract from conversation] | [Extract from conversation] | [Estimate] | [Extract from conversation] |
    | **Closing** | [Extract from conversation] | [Extract from conversation] | [Estimate] | [Extract from conversation] |
    
    [Then provide detailed paragraphs expanding on each section above]
    
    ## Scene 7 - Financial Projections & Funding
    
    ### Financial Projections Table (3-5 Years)
    
    | Year | Revenue | Operating Expenses | Net Profit | Growth Rate | Key Assumptions |
    |------|---------|---------------------|------------|-------------|----------------|
    | **Year 1** | [Extract from conversation] | [Extract from conversation] | [Calculate] | [Calculate] | [Extract from conversation] |
    | **Year 2** | [Extract from conversation] | [Extract from conversation] | [Calculate] | [Calculate] | [Extract from conversation] |
    | **Year 3** | [Extract from conversation] | [Extract from conversation] | [Calculate] | [Calculate] | [Extract from conversation] |
    | **Year 4** | [Project] | [Project] | [Calculate] | [Calculate] | [Estimate] |
    | **Year 5** | [Project] | [Project] | [Calculate] | [Calculate] | [Estimate] |
    
    ### Funding Requirements Table
    
    | Category | Amount | Use of Funds | Timeline | Funding Source |
    |----------|--------|--------------|----------|----------------|
    | **Startup Costs** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] |
    | **Operating Capital** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] |
    | **Marketing & Sales** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] |
    | **Product Development** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] |
    | **Total Funding Needed** | [Calculate] | [Summary] | [Extract from conversation] | [Extract from conversation] |
    
    [Then provide detailed paragraphs expanding on each section above]
    
    ## Scene 8 - Operations, Risk Management & Implementation Timeline
    
    ### Operations Structure Table
    
    | Area | Current Status | Requirements | Timeline | Resources Needed |
    |------|----------------|--------------|----------|------------------|
    | **Location/Facilities** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] |
    | **Staffing** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] |
    | **Technology/Equipment** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] |
    | **Suppliers/Vendors** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] |
    | **Legal & Compliance** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] |
    
    ### Risk Management Table
    
    | Risk Category | Risk Description | Likelihood | Impact | Mitigation Strategy | Contingency Plan |
    |---------------|------------------|------------|--------|---------------------|------------------|
    | **Market Risk** | [Extract from conversation] | High/Medium/Low | High/Medium/Low | [Extract from conversation] | [Extract from conversation] |
    | **Operational Risk** | [Extract from conversation] | High/Medium/Low | High/Medium/Low | [Extract from conversation] | [Extract from conversation] |
    | **Financial Risk** | [Extract from conversation] | High/Medium/Low | High/Medium/Low | [Extract from conversation] | [Extract from conversation] |
    | **Regulatory Risk** | [Extract from conversation] | High/Medium/Low | High/Medium/Low | [Extract from conversation] | [Extract from conversation] |
    | **Competitive Risk** | [Extract from conversation] | High/Medium/Low | High/Medium/Low | [Extract from conversation] | [Extract from conversation] |
    
    ### Implementation Timeline Table
    
    | Phase | Timeline | Key Activities | Milestones | Dependencies | Status |
    |-------|----------|----------------|------------|--------------|--------|
    | **Phase 1: Foundation** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | Planned |
    | **Phase 2: Development** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | Planned |
    | **Phase 3: Launch** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | Planned |
    | **Phase 4: Growth** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | Planned |
    | **Phase 5: Scaling** | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | [Extract from conversation] | Planned |
    
    [Then provide detailed paragraphs expanding on each section above]
    
    **CRITICAL FORMATTING INSTRUCTIONS - MANDATORY TABLE FORMAT**:
    
    ⚠️ **YOU MUST FOLLOW THIS EXACT STRUCTURE - NO EXCEPTIONS**:
    
    1. **MANDATORY**: Create EXACTLY 8 scenes (Scene 1 through Scene 8) - NO MORE, NO LESS
    2. **MANDATORY**: Each scene MUST start with a markdown table (use the exact table structure shown in the template above)
    3. **MANDATORY**: After each table, provide 2-3 detailed paragraphs expanding on the table content
    4. **MANDATORY**: Scene titles must be EXACTLY:
       - "## Scene 1 - Executive Summary & Business Overview"
       - "## Scene 2 - Company Description & Business Model"
       - "## Scene 3 - Market Analysis & Research"
       - "## Scene 4 - Competitive Analysis"
       - "## Scene 5 - Product/Service Offering"
       - "## Scene 6 - Marketing & Sales Strategy"
       - "## Scene 7 - Financial Projections & Funding"
       - "## Scene 8 - Operations, Risk Management & Implementation Timeline"
    5. **MANDATORY**: Extract ALL information from the conversation history - replace ALL [Extract from conversation] placeholders with ACTUAL data
    6. **MANDATORY**: Use actual business name: {session_data.get('business_name', 'Your Business')}
    7. **MANDATORY**: Use actual industry: {session_data.get('industry', 'General Business')}
    8. **MANDATORY**: Use actual location: {session_data.get('location', 'United States')}
    9. **MANDATORY**: All tables must be properly formatted markdown tables with | separators
    10. **MANDATORY**: DO NOT create traditional sections like "Executive Summary", "Company Description", etc. - ONLY use Scene 1-8 format
    11. **MANDATORY**: DO NOT create sections beyond Scene 8 - the document MUST end after Scene 8
    12. **MANDATORY**: Each scene should be 2-3 pages of content when formatted (tables + detailed paragraphs)
    13. **MANDATORY**: The total document should be 15-20 pages when formatted
    
    **OUTPUT FORMAT EXAMPLE**:
    ```
    ## Scene 1 - Executive Summary & Business Overview
    
    ### Business Plan Summary Table
    
    | Section | Highlights |
    |---------|------------|
    | **Mission & Vision** | [ACTUAL mission statement from conversation] |
    | **Target Market** | [ACTUAL target market from conversation] |
    ...
    
    [2-3 detailed paragraphs here]
    
    ## Scene 2 - Company Description & Business Model
    
    ### Company Overview Table
    
    | Aspect | Details |
    |--------|---------|
    | **Business Name** | [ACTUAL business name] |
    ...
    
    [2-3 detailed paragraphs here]
    
    [Continue for all 8 scenes]
    ```
    
    **DO NOT OUTPUT**:
    - Traditional section headers like "Executive Summary", "Company Description", etc.
    - Paragraphs without tables at the start of each scene
    - More or fewer than 8 scenes
    - Any content after Scene 8
    
    **IMPORTANT**: This must be a COMPLETE, PROFESSIONAL business plan document that could be presented to investors, banks, or partners. It should be comprehensive, well-researched, and demonstrate deep understanding of the business opportunity.
    
    **LENGTH REQUIREMENT**: This document MUST be extensive and detailed. Aim for 15,000-25,000 words (approximately 15-20 pages when formatted). Each scene should have substantial content with:
    - Tables at the start of each scene (as shown in template)
    - 2-3 detailed paragraphs after each table
    - Specific examples and data from conversation history
    - Comprehensive analysis
    - Professional formatting
    
    **CRITICAL**: Do NOT create a brief summary. This is the FULL, COMPLETE business plan artifact in 8-scene table format. Every scene must be thoroughly developed with extensive detail.
    
    Generate the complete business plan now in EXACTLY 8 scenes with tables. Make it comprehensive and detailed:
    """
    
    print(f"📝 Generating comprehensive business plan artifact (this may take 30-60 seconds)...")
    print(f"📊 Using conversation history with {len(full_history)} messages")
    print(f"🔍 Research data available: Market={bool(market_research)}, Competitor={bool(competitor_research)}, Trends={bool(industry_trends)}, Financial={bool(financial_benchmarks)}")
    
    try:
        # Add system message to enforce format - MAXIMUM STRICTNESS
        system_message = """You are a business plan generator. You MUST output documents in EXACTLY 8 scenes with tables.

⚠️⚠️⚠️ CRITICAL - YOUR OUTPUT WILL BE REJECTED IF IT DOESN'T MATCH THIS EXACT FORMAT ⚠️⚠️⚠️

MANDATORY OUTPUT FORMAT - NO EXCEPTIONS:

Your output MUST start with EXACTLY this text:
## Scene 1 - Executive Summary & Business Overview

### Business Plan Summary Table

| Section | Highlights |
|---------|------------|

You MUST have EXACTLY these 8 scene headers (copy them EXACTLY):
1. ## Scene 1 - Executive Summary & Business Overview
2. ## Scene 2 - Company Description & Business Model
3. ## Scene 3 - Market Analysis & Research
4. ## Scene 4 - Competitive Analysis
5. ## Scene 5 - Product/Service Offering
6. ## Scene 6 - Marketing & Sales Strategy
7. ## Scene 7 - Financial Projections & Funding
8. ## Scene 8 - Operations, Risk Management & Implementation Timeline

ABSOLUTELY FORBIDDEN - DO NOT USE:
❌ "Executive Summary" (without "Scene 1 -")
❌ "Company Description" (without "Scene 2 -")
❌ "Market Analysis" (without "Scene 3 -")
❌ Any section header that doesn't start with "## Scene X -"

If your output doesn't start with "## Scene 1 - Executive Summary & Business Overview", it will be REJECTED and you will be asked to regenerate.

Each scene MUST:
- Start with the exact header format shown above
- Have at least one markdown table immediately after the header
- Include 2-3 detailed paragraphs after the table

Generate the business plan NOW starting with "## Scene 1 - Executive Summary & Business Overview"."""
        
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": business_plan_prompt}
            ],
            temperature=0.2,  # Very low temperature for strict format adherence
            max_tokens=16000  # Ensure we get a comprehensive, full-length document
        )
        
        artifact_content = response.choices[0].message.content
        
        # Log first 500 characters to debug format
        print(f"🔍 First 500 chars of generated artifact: {artifact_content[:500]}")
        
        # STRICT VALIDATION - Reject old format completely
        starts_with_scene_1 = artifact_content.strip().startswith("## Scene 1 - Executive Summary & Business Overview")
        scene_count = artifact_content.count("## Scene ")
        has_scene_1 = "## Scene 1" in artifact_content
        has_scene_8 = "## Scene 8" in artifact_content
        has_tables = "|" in artifact_content and "---" in artifact_content
        has_old_format = ("## Executive Summary" in artifact_content or 
                         ("Executive Summary" in artifact_content and "## Scene 1" not in artifact_content) or
                         ("Company Description" in artifact_content and "## Scene 2" not in artifact_content))
        
        print(f"🔍 Validation: starts_with_scene_1={starts_with_scene_1}, scene_count={scene_count}, has_scene_1={has_scene_1}, has_scene_8={has_scene_8}, has_tables={has_tables}, has_old_format={has_old_format}")
        
        # REJECT if it doesn't start with Scene 1 or has old format
        if not artifact_content or len(artifact_content) < 5000 or not starts_with_scene_1 or scene_count != 8 or not has_scene_1 or not has_scene_8 or has_old_format:
            print(f"⚠️ Warning: Generated artifact doesn't match required format")
            print(f"   - Length: {len(artifact_content) if artifact_content else 0} characters")
            print(f"   - Scene count: {scene_count} (expected 8)")
            print(f"   - Has tables: {has_tables}")
            print("🔄 Regenerating with STRICT format enforcement...")
            # Retry with STRICT format enforcement
            enhanced_prompt = business_plan_prompt + """
            
            ⚠️⚠️⚠️ CRITICAL FORMAT VALIDATION - YOUR OUTPUT WILL BE REJECTED IF IT DOESN'T MATCH ⚠️⚠️⚠️
            
            **YOUR OUTPUT MUST START WITH THIS EXACT TEXT**:
            ## Scene 1 - Executive Summary & Business Overview
            
            ### Business Plan Summary Table
            
            | Section | Highlights |
            |---------|------------|
            
            **YOU MUST HAVE EXACTLY 8 SCENES**:
            Scene 1 - Executive Summary & Business Overview
            Scene 2 - Company Description & Business Model
            Scene 3 - Market Analysis & Research
            Scene 4 - Competitive Analysis
            Scene 5 - Product/Service Offering
            Scene 6 - Marketing & Sales Strategy
            Scene 7 - Financial Projections & Funding
            Scene 8 - Operations, Risk Management & Implementation Timeline
            
            **FORBIDDEN - DO NOT INCLUDE**:
            ❌ "Executive Summary" (without "Scene 1 -")
            ❌ "Company Description" (without "Scene 2 -")
            ❌ "Market Analysis" (without "Scene 3 -")
            ❌ Any section that doesn't start with "## Scene X -"
            
            **REQUIRED - YOU MUST INCLUDE**:
            ✅ Each scene header must be "## Scene X - [Title]"
            ✅ Each scene must have at least one markdown table immediately after the header
            ✅ Tables must use | separators
            ✅ After each table, include 2-3 detailed paragraphs
            
            If your output doesn't start with "## Scene 1 - Executive Summary & Business Overview", it will be rejected.
            Generate the business plan NOW following this EXACT format. Start with Scene 1.
            """
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": enhanced_prompt}
                ],
                temperature=0.1,  # Very low temperature for strict format adherence
                max_tokens=16000
            )
            artifact_content = response.choices[0].message.content
            
            # Final validation
            final_scene_count = artifact_content.count("## Scene ")
            final_has_scene_1 = "## Scene 1" in artifact_content
            final_has_scene_8 = "## Scene 8" in artifact_content
            final_has_tables = "|" in artifact_content and "---" in artifact_content
            final_has_old_format = ("## Executive Summary" in artifact_content or 
                                   ("Executive Summary" in artifact_content and "## Scene 1" not in artifact_content))
            
            print(f"🔍 Final validation: scene_count={final_scene_count}, has_scene_1={final_has_scene_1}, has_scene_8={final_has_scene_8}, has_tables={final_has_tables}, has_old_format={final_has_old_format}")
            print(f"🔍 First 500 chars of final artifact: {artifact_content[:500]}")
            
            if final_scene_count != 8 or not final_has_scene_1 or not final_has_scene_8 or final_has_old_format:
                print(f"⚠️ WARNING: Final artifact still doesn't match 8-scene format!")
                print(f"   - Scene count: {final_scene_count} (expected 8)")
                print(f"   - Has Scene 1: {final_has_scene_1}")
                print(f"   - Has Scene 8: {final_has_scene_8}")
                print(f"   - Has old format: {final_has_old_format}")
                # Force one more regeneration with even stricter prompt
                print("🔄 Attempting final regeneration with maximum strictness...")
                ultra_strict_prompt = """
                
                ⚠️⚠️⚠️ CRITICAL - YOUR OUTPUT MUST START WITH EXACTLY THIS TEXT ⚠️⚠️⚠️
                
                ## Scene 1 - Executive Summary & Business Overview
                
                ### Business Plan Summary Table
                
                | Section | Highlights |
                |---------|------------|
                | **Mission & Vision** | [ACTUAL DATA FROM CONVERSATION] |
                
                DO NOT use "Executive Summary" without "Scene 1 -"
                DO NOT use "Company Description" without "Scene 2 -"
                DO NOT use any traditional section headers
                
                You MUST have exactly 8 scenes:
                - Scene 1 - Executive Summary & Business Overview
                - Scene 2 - Company Description & Business Model
                - Scene 3 - Market Analysis & Research
                - Scene 4 - Competitive Analysis
                - Scene 5 - Product/Service Offering
                - Scene 6 - Marketing & Sales Strategy
                - Scene 7 - Financial Projections & Funding
                - Scene 8 - Operations, Risk Management & Implementation Timeline
                
                Start generating NOW with "## Scene 1 - Executive Summary & Business Overview"
                """
                final_response = await client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": business_plan_prompt + ultra_strict_prompt}
                    ],
                    temperature=0.0,  # Zero temperature for maximum determinism
                    max_tokens=16000
                )
                artifact_content = final_response.choices[0].message.content
                print(f"🔍 Ultra-strict regeneration: First 500 chars: {artifact_content[:500]}")
                
                # Final check - if still wrong, raise error
                ultra_starts_with_scene_1 = artifact_content.strip().startswith("## Scene 1 - Executive Summary & Business Overview")
                ultra_has_old = (
                    "## Executive Summary" in artifact_content or 
                    ("Executive Summary" in artifact_content and "## Scene 1" not in artifact_content) or
                    ("## Company Description" in artifact_content and "## Scene 2" not in artifact_content) or
                    ("## Market Analysis" in artifact_content and "## Scene 3" not in artifact_content)
                )
                
                if not ultra_starts_with_scene_1 or ultra_has_old:
                    print(f"❌ CRITICAL ERROR: Even ultra-strict regeneration failed!")
                    print(f"   Output starts with Scene 1: {ultra_starts_with_scene_1}")
                    print(f"   Has old format: {ultra_has_old}")
                    raise Exception("AI failed to generate business plan in required 8-scene table format after multiple attempts. The output is in the old format which is COMPLETELY FORBIDDEN. Old format has been removed from the system.")
            
            if not final_has_tables:
                print(f"⚠️ WARNING: Final artifact may not have proper table formatting")
        
        # FINAL VALIDATION - Reject old format completely before returning
        final_starts_with_scene_1 = artifact_content.strip().startswith("## Scene 1 - Executive Summary & Business Overview")
        final_has_old_format_check = (
            "## Executive Summary" in artifact_content or 
            ("Executive Summary" in artifact_content and "## Scene 1" not in artifact_content) or
            ("## Company Description" in artifact_content and "## Scene 2" not in artifact_content)
        )
        
        if not final_starts_with_scene_1 or final_has_old_format_check:
            print(f"❌ FINAL REJECTION: Artifact is in old format - COMPLETELY FORBIDDEN")
            raise Exception("Business plan artifact is in old format which is COMPLETELY FORBIDDEN. Old format has been removed from the system. Only 8-scene table format is supported.")
        
        artifact_length = len(artifact_content) if artifact_content else 0
        print(f"✅ Business Plan Artifact generated: {artifact_length} characters (~{artifact_length // 2000} pages)")
        
        if artifact_length < 3000:
            print(f"⚠️ WARNING: Artifact may be incomplete ({artifact_length} characters)")
        
        return artifact_content
        
    except Exception as e:
        print(f"❌ Error generating business plan artifact: {str(e)}")
        raise Exception(f"Failed to generate business plan artifact: {str(e)}")

async def generate_roadmap_artifact(session_data, business_plan_data):
    """Generate comprehensive roadmap based on business plan"""
    
    # Research current tools and vendors
    industry = session_data.get('industry', 'general business')
    business_type = session_data.get('business_type', 'startup')
    
    current_year = datetime.now().year
    previous_year = current_year - 1
    
    vendor_research = await conduct_web_search(f"best business tools vendors {industry} {business_type} {previous_year}")
    legal_research = await conduct_web_search(f"business formation requirements {session_data.get('location', 'United States')}")
    
    roadmap_prompt = f"""
    Create a detailed, chronological roadmap for launching this business:
    
    Business Context: {json.dumps(session_data, indent=2)}
    Business Plan Summary: {business_plan_data}
    
    Current Vendor Research: {vendor_research}
    Legal Requirements Research: {legal_research}
    
    Include:
    - Specific timelines and deadlines
    - Clear task ownership (Angel vs User)
    - 3 recommended vendors/platforms per category with current pricing
    - Industry-specific milestones
    - Pre-launch, launch, and post-launch phases
    - Critical path dependencies
    
    Make this actionable and comprehensive for immediate implementation.
    """
    
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": roadmap_prompt}],
        temperature=0.6
    )
    
    return response.choices[0].message.content

def parse_roadmap_step_tables(roadmap_content: str) -> List[Dict[str, Any]]:
    """Parse roadmap markdown tables into structured phases and steps"""
    lines = roadmap_content.splitlines()
    phases: List[Dict[str, Any]] = []
    current_phase: Optional[Dict[str, Any]] = None
    current_phase_title: Optional[str] = None
    in_table = False
    table_lines: List[str] = []

    def flush_table():
        nonlocal table_lines, current_phase
        if not table_lines or not current_phase:
            table_lines = []
            return

        header_cells = [cell.strip() for cell in table_lines[0].split('|') if cell.strip()]
        if len(header_cells) < 4:
            table_lines = []
            return

        is_step_table = (
            header_cells[0].lower().startswith('step name')
            and header_cells[1].lower().startswith('step description')
            and 'timeline' in header_cells[2].lower()
            and 'source' in header_cells[3].lower()
        )

        if is_step_table:
            for row_line in table_lines[2:]:
                row_cells = [cell.strip() for cell in row_line.split('|') if cell.strip()]
                if len(row_cells) < 4:
                    continue
                step_entry = {
                    "step_name": row_cells[0],
                    "step_description": row_cells[1],
                    "timeline": row_cells[2],
                    "research_source": row_cells[3]
                }
                current_phase.setdefault("steps", []).append(step_entry)

        table_lines = []

    for raw_line in lines:
        line = raw_line.strip()

        if line.startswith('###'):
            if current_phase and current_phase.get("steps"):
                phases.append(current_phase)
            current_phase_title = line.lstrip('#').strip()
            current_phase = None
            continue

        if line.lower().startswith('**roadmap steps -'):
            if current_phase and current_phase.get("steps"):
                phases.append(current_phase)
            phase_title = line.replace('*', '').replace(':', '').strip()
            current_phase = {
                "phase_title": current_phase_title or phase_title,
                "raw_heading": phase_title,
                "steps": []
            }
            continue

        if line.startswith('|'):
            if not in_table:
                flush_table()
                in_table = True
            table_lines.append(raw_line)
        else:
            if in_table:
                flush_table()
                in_table = False

    if in_table:
        flush_table()

    if current_phase and current_phase.get("steps"):
        phases.append(current_phase)

    return phases

async def generate_step_substeps(step: Dict[str, Any], session_data: Dict[str, Any]) -> List[str]:
    """Generate 3-5 actionable substeps for a roadmap step"""
    prompt = f"""
    You are assisting an entrepreneur in the {session_data.get('industry', 'general business')} industry located in {session_data.get('location', 'the United States')}.
    Break the following roadmap task into 3-5 sequential, actionable substeps that help them complete the task end-to-end.

    Task Name: {step.get('step_name', 'Unnamed Task')}
    Task Description: {step.get('step_description', '')}
    Timeline Guidance: {step.get('timeline', 'No timeline provided')}
    Research Source Summary: {step.get('research_source', '')}

    Requirements:
    - Provide exactly 3, 4, or 5 substeps depending on what is necessary.
    - Begin each substep with an action verb.
    - Include key deliverables or decision points.
    - Reference the provided research sources when relevant.
    - Keep each substep concise (max 25 words) and specific.
    - Format your response as a JSON array of strings.
    """

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300
        )
        content = response.choices[0].message.content
        substeps = json.loads(content)
        if isinstance(substeps, list):
            return [str(step).strip() for step in substeps if step]
    except Exception as e:
        print(f"Failed to generate substeps for {step.get('step_name')}: {e}")

    fallback = step.get('step_description', '')
    return [fallback] if fallback else ["Complete this task following the guidance provided."]

async def build_structured_roadmap_data(session_data: Dict[str, Any], roadmap_content: str) -> Dict[str, Any]:
    """Build structured roadmap data including phases, steps, and implementation tasks"""
    phases = parse_roadmap_step_tables(roadmap_content)
    tasks: List[Dict[str, Any]] = []

    for phase_index, phase in enumerate(phases, start=1):
        phase_title = phase.get("phase_title", f"Phase {phase_index}")
        for step_index, step in enumerate(phase.get("steps", []), start=1):
            task_id = f"PHASE{phase_index:02d}_STEP{step_index:02d}"
            substeps = await generate_step_substeps(step, session_data)

            tasks.append({
                "id": task_id,
                "phase_index": phase_index,
                "phase_title": phase_title,
                "step_index": step_index,
                "step_name": step.get("step_name"),
                "step_description": step.get("step_description"),
                "timeline": step.get("timeline"),
                "research_source": step.get("research_source"),
                "substeps": substeps
            })

    return {
        "phases": phases,
        "tasks": tasks,
        "generated_at": datetime.now().isoformat()
    }

async def handle_roadmap_generation(session_data, history):
    """Handle the transition from Plan to Roadmap phase"""
    
    # Generate comprehensive roadmap using RAG principles
    roadmap_content = await generate_detailed_roadmap(session_data, history)
    structured_data = await build_structured_roadmap_data(session_data, roadmap_content)
    quote_payload = pick_motivational_quote()
    
    # Replace static inspirational quote in roadmap content with the dynamically selected quote
    if "**Inspirational Quote:**" in roadmap_content:
        replacement_text = f'**Inspirational Quote:** "{quote_payload["quote"]}" – {quote_payload["author"]}'
        roadmap_content = re.sub(
            r'\*\*Inspirational Quote:\*\* ".*?" – .*',
            replacement_text,
            roadmap_content,
            count=1
        )
    
    # Create the roadmap presentation message
    roadmap_message = f"""🗺️ **Your Launch Roadmap is Ready!** 🗺️

Congratulations! Based on your comprehensive business plan, I've generated a detailed, actionable launch roadmap that will guide you from planning to execution.

**"{quote_payload['quote']}"** – {quote_payload['author']}

---

## 📋 **Your Launch Roadmap Overview**

{roadmap_content}

---

## 🎯 **Key Features of Your Roadmap**

✅ **Research-Backed**: Every recommendation is based on current best practices and industry standards
✅ **Actionable Tasks**: Each phase contains specific, executable tasks with clear timelines
✅ **Multiple Options**: Decision points include various options to fit your specific needs
✅ **Local Resources**: Provider recommendations include local service providers where applicable
✅ **Progress Tracking**: Built-in milestones and success metrics for each phase

---

## 🚀 **What's Next**

Your roadmap is now ready for implementation! Each phase is designed to build upon the previous one, ensuring a smooth transition from planning to execution.

**Ready to begin implementation?** Let me know when you're ready to start executing your roadmap, and I'll guide you through each step with detailed instructions, resources, and support.

---

*This roadmap is tailored specifically to your business, industry, and location. Every recommendation is designed to help you build the business of your dreams.*
"""
    
    return {
        "reply": roadmap_message,
        "transition_phase": "ROADMAP_GENERATED",
        "roadmap_content": roadmap_content,
        "quote": quote_payload,
        "structured_steps": structured_data.get("phases", []),
        "implementation_tasks": structured_data.get("tasks", []),
        "roadmap_metadata": {
            "generated_at": structured_data.get("generated_at"),
            "total_tasks": len(structured_data.get("tasks", []))
        }
    }

async def handle_roadmap_to_implementation_transition(session_data, history):
    """
    Handle the transition from Roadmap completion to Implementation phase
    Based on the "Transition Roadmap to Implementation - Descriptive.docx" document
    """
    
    # Extract business context from session data and history
    extracted_context = {}
    if history:
        extracted_context = extract_business_context_from_history(history)
    
    # Get business context - prioritize extracted context from history over session data
    business_context = session_data.get("business_context", {}) or {}
    if not isinstance(business_context, dict):
        business_context = {}
    
    # Extract business details with proper fallbacks
    business_name = extracted_context.get('business_name') or business_context.get('business_name') or 'your business'
    industry = extracted_context.get('industry') or business_context.get('industry') or 'general business'
    location = extracted_context.get('location') or business_context.get('location') or 'United States'
    
    # Get a dynamic motivational quote
    motivational_quote = pick_motivational_quote()
    
    # Generate roadmap summary
    roadmap_summary = f"""**Your Completed Roadmap Summary:**

✅ **Legal Formation** - Complete
✅ **Financial Planning** - Complete
✅ **Product & Operations** - Defined
✅ **Marketing** - Launched
✅ **Launch & Scaling** - Finalized"""
    
    # Create comprehensive transition message based on DOCX document
    transition_message = f"""[Confetti animation 🎊 floats upward across the screen]

🏅 **EXECUTION READY BADGE UNLOCKED** 🏅

*For completing your full roadmap journey and preparing for business launch.*

---

**That's incredible.** You've completed your full Launch Roadmap. Every milestone — from formation to marketing — checked off. You're now ready to bring {business_name} fully to life.

---

## **📋 Your Completed Roadmap Summary**

{roadmap_summary}

You've officially built the foundation. Now let's execute with precision and confidence.

---

## **🚀 Next Phase: Implementation — Bringing {business_name} to Life**

What you've done so far isn't just planning — it's progress. Now it's time to step into the **Implementation Phase** — where we turn every plan into real, measurable action.

I'll stay with you, just as before, guiding you through each task one at a time — whether it's filing documents, managing outreach, or setting up your first customer channel.

---

## **⚙️ How Angel Helps in Implementation Phase**

Here's what you can expect in this phase:

| **Function** | **Description** |
|--------------|----------------|
| **Advice & Tips** | I'll share focused, practical insights to guide every action |
| **Kickstart** | I can complete parts of tasks for you — like drafting outreach emails or setting up a checklist |
| **Help** | Ask for deep, detailed guidance whenever you hit a roadblock |
| **Who do I contact?** | I'll connect you with trusted, relevant professionals or providers near you in {location} |
| **Dynamic Feedback** | I'll notice when tasks look incomplete or off-track and help correct them quickly |

---

## **📊 Implementation Progress Tracking**

Just like before, you'll have a visual tracker — so you can watch your real progress, not just your plans. Each task you complete gets you closer to full launch.

**[Implementation Progress: 0% → Ready to Begin]**

---

## **💪 Take a Moment to Recognize Your Journey**

Before we dive in, take a second to recognize how far you've come:

✅ You started with an idea
✅ You've built a comprehensive plan
✅ You've created a detailed roadmap
✅ Now, we'll bring it all to life — step by step

---

## **💡 Inspirational Quote**

> **"{motivational_quote['quote']}"**
> 
> — {motivational_quote['author']}

---

## **🎯 Ready to Begin Implementation?**

When you're ready, we'll show you the first real-world action to take — and we'll tackle it together.

---

*This implementation process is tailored specifically to {business_name} in the {industry} industry, located in {location}. Every recommendation is designed to help you build the business of your dreams.*"""
    
    # Check if we should show Accept/Modify buttons
    button_detection = await should_show_accept_modify_buttons(
        user_last_input="Roadmap completion",
        ai_response=transition_message,
        session_data=session_data
    )
    
    return {
        "reply": transition_message,
        "transition_phase": "ROADMAP_TO_IMPLEMENTATION",
        "patch_session": {
            "current_phase": "IMPLEMENTATION",
            "asked_q": "IMPLEMENTATION.01",
            "answered_count": 0
        },
        "show_accept_modify": button_detection.get("show_buttons", False),
        "awaiting_confirmation": True  # Signal that we need user to confirm before starting implementation tasks
    }

async def generate_detailed_roadmap(session_data, history):
    """Generate detailed roadmap using Founderport-style format with proper table structure"""
    
    # Import the Founderport-style roadmap generator
    from services.founderport_roadmap_service import generate_founderport_style_roadmap
    
    # Use the Founderport-style roadmap generator which creates proper table format
    # with Task | Description | Dependencies | Angel's Role | Status columns
    roadmap_content = await generate_founderport_style_roadmap(session_data, history)
    
    return roadmap_content

async def generate_dynamic_business_question(
    question_tag: str, 
    session_data: dict, 
    history: list = None,
    is_missing_question: bool = False
) -> str:
    """
    Generate a dynamic, context-aware business plan question tailored to the user's specific business.
    
    Args:
        question_tag: The question tag (e.g., "BUSINESS_PLAN.19")
        session_data: Session data containing business context
        history: Chat history for context
        is_missing_question: Whether this is a missing question from uploaded plan
    
    Returns:
        Formatted question string with tag
    """
    # Extract business context from KYC history (prioritize KYC answers over session title)
    extracted_context = {}
    if history:
        extracted_context = extract_business_context_from_history(history)
    
    # Merge: For uploaded plans, prioritize session business_context; otherwise, KYC-extracted context takes priority
    # NEVER use session title as business name - it's just a venture label, not the actual business name
    business_context = session_data.get("business_context", {}) or {}
    if not isinstance(business_context, dict):
        business_context = {}
    
    # Check if we're in uploaded plan mode - if so, prioritize session business_context
    uploaded_plan_mode = business_context.get("uploaded_plan_mode", False) if isinstance(business_context, dict) else False
    
    if uploaded_plan_mode:
        # For uploaded plans, prioritize session business_context (has uploaded plan data) over extracted from history
        industry = business_context.get("industry") or extracted_context.get("industry") or ""
        business_type = business_context.get("business_type") or extracted_context.get("business_type") or ""
        location = business_context.get("location") or extracted_context.get("location") or ""
        business_name = business_context.get("business_name") or extracted_context.get("business_name") or ""
        mission = business_context.get("mission") or business_context.get("tagline") or extracted_context.get("mission") or ""
    else:
        # For normal flow, prioritize extracted context from KYC over stored business_context
        industry = extracted_context.get("industry") or business_context.get("industry") or ""
        business_type = extracted_context.get("business_type") or business_context.get("business_type") or ""
        location = extracted_context.get("location") or business_context.get("location") or ""
        business_name = extracted_context.get("business_name") or business_context.get("business_name") or ""
        mission = extracted_context.get("mission") or business_context.get("mission") or business_context.get("tagline") or ""
    
    # Get question topic/objective
    question_num = int(question_tag.split(".")[1]) if "." in question_tag else 1
    
    # If we're asking Question 1 (business name), don't use any name - we're asking for it
    if question_num == 1:
        business_name = ""  # Don't use any name for the name question itself
    
    # If no business name found, use generic placeholder
    if not business_name:
        business_name = "your business"
    
    print(f"🎯 Dynamic question context: industry={industry}, business_type={business_type}, location={location}, name={business_name}")
    print(f"🎯 Question number: {question_num}, Using business_name: '{business_name}'")
    print(f"🎯 Uploaded plan mode: {uploaded_plan_mode}, Source: {'session_context' if uploaded_plan_mode else 'extracted_history'}")
    
    # Get question topic/objective (updated for 9-section structure, 45 questions)
    question_topics = {
        1: "business idea in detail",
        2: "product or service offering",
        3: "unique value proposition (differentiation)",
        4: "current business stage",
        5: "business name",
        6: "industry classification",
        7: "short-term business goals",
        8: "target customer demographics",
        9: "where products/services available for purchase",
        10: "problem solving for customers",
        11: "competitor research and analysis",
        12: "industry trends research",
        13: "business differentiation strategy",
        14: "business location",
        15: "facilities and resources needed",
        16: "primary delivery method",
        17: "short-term operational needs",
        18: "business mission statement",
        19: "marketing plan",
        20: "marketing method (sales team, firm, self-market)",
        21: "unique selling proposition (USP)",
        22: "promotional strategies for launch",
        23: "short-term marketing needs",
        24: "business structure type",
        25: "business name registration",
        26: "permits and licenses needed",
        27: "insurance policies needed",
        28: "compliance adherence plan",
        29: "revenue model",
        30: "pricing strategy",
        31: "financial tracking and accounting",
        32: "initial funding source",
        33: "first year financial goals",
        34: "main costs and expenses",
        35: "plans for scaling business",
        36: "long-term business goals",
        37: "long-term operational needs",
        38: "long-term financial needs",
        39: "long-term marketing goals",
        40: "approach to expanding product/service lines",
        41: "long-term administrative goals",
        42: "contingency plans for challenges",
        43: "adapting to market changes",
        44: "additional funding for expansion",
        45: "overall vision for 5 years"
    }
    
    topic = question_topics.get(question_num, "business planning")
    
    # Build context from history
    business_info_summary = ""
    if history:
        recent_answers = []
        for msg in history[-10:]:  # Last 10 messages for context
            if msg.get("role") == "user" and msg.get("content"):
                content = msg.get("content", "").strip()
                if content and len(content) > 10:  # Skip very short answers
                    recent_answers.append(content[:100])  # Truncate long answers
        
        if recent_answers:
            business_info_summary = f"\n\nBased on what you've shared so far:\n" + "\n".join(f"- {ans}" for ans in recent_answers[-3:])  # Last 3 answers
    
    # Create dynamic question prompt
    # Use industry name as the primary identifier if available (from KYC or uploaded plan)
    if industry:
        business_identifier = industry  # Use industry from KYC/uploaded plan (e.g., "Chai Stall", "Software Development")
    elif business_name and business_name != "your business":
        business_identifier = business_name
    else:
        business_identifier = "your business"
    
    industry_context = f" in the {industry} industry" if industry else ""
    business_type_context = f" as a {business_type}" if business_type else ""
    location_context = f" in {location}" if location else ""
    
    # Add critical context warning for uploaded plans
    critical_context_warning = ""
    if uploaded_plan_mode and industry:
        critical_context_warning = f"""
⚠️ CRITICAL CONTEXT - This business is in the {industry} INDUSTRY - ALL guidance must be 100% specific to {industry}.
- The user uploaded a business plan for a {industry} business
- Use the business information from the uploaded plan, NOT from KYC answers
- Business Name: {business_name if business_name and business_name != "your business" else "From uploaded plan"}
- Location: {location if location else "From uploaded plan"}
- Industry: {industry}
- ALL questions must be tailored specifically to {industry} businesses

"""
    
    question_prompt = f"""{critical_context_warning}Generate a dynamic, tailored business plan question for {business_identifier}{industry_context}{business_type_context}{location_context}.

QUESTION TOPIC: {topic}
QUESTION TAG: {question_tag}

CRITICAL REQUIREMENTS:
1. The question MUST be specifically tailored to {business_identifier}'s business type and industry
2. Use the industry name from KYC answers (e.g., "Chai Stall", "POS Development") - NOT the venture/session title
3. For a restaurant/chai stall: ask about menu, service hours, dining capacity, kitchen equipment, food suppliers, etc.
4. For a service business: ask about service offerings, timelines, client management, service delivery methods, etc.
5. For a product business: ask about product features, manufacturing, inventory, distribution, etc.
6. Include follow-up prompts that are relevant to the specific business type
7. Use industry-specific terminology and examples
8. Make the question conversational and natural
9. Include the tag: [[Q:{question_tag}]]
10. Add 1-2 thought-provoking follow-up questions if relevant

EXAMPLES (use these as patterns, NOT exact text):
- For a food service business asking about name: "What will you name your [industry]? If you haven't decided yet, what are your top 3-5 name options?"
- For a restaurant asking about operations: "What are your service offering timelines? Will you offer all services (dine-in, takeout, delivery) upon opening, or will you add certain services at specific times after opening?"
- For a service business asking about services: "What services will you offer initially? Will you start with a full suite of services or launch with core offerings and expand later?"
- For a retail business asking about location: "What are your space requirements for your [business type]? Do you need display areas, storage, fitting rooms, or a back office?"

IMPORTANT: Replace [industry] and [business type] with the ACTUAL industry and business type from the user's KYC answers. Do NOT use hardcoded examples like "Chai Stall" - use the actual industry name the user provided.

{business_info_summary}

Generate the question now:"""
    
    if is_missing_question:
        question_prompt += "\n\nNOTE: This information was missing from the user's uploaded business plan. Mention this contextually."
    
    # Define formatting instruction for question generation
    formatting_instruction = """
FORMATTING REQUIREMENTS:
- Use clear, conversational language
- Include proper line breaks for readability (add blank line after question)
- Keep questions concise but informative
- Use the exact tag format: [[Q:QUESTION_TAG]]
- Do NOT include "Question X" text - the UI displays it automatically
- Format the main question text with **bold** markdown for emphasis
- Add a blank line after the question for spacing
- Keep follow-up prompts concise and on separate lines if needed

EXAMPLE FORMAT:
[[Q:BUSINESS_PLAN.01]]

**What will you name your POS Development business?**

If you haven't settled on a name yet, what are your top 3-5 options?
"""
    
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": ANGEL_SYSTEM_PROMPT},
            {"role": "system", "content": TAG_PROMPT},
            {"role": "system", "content": formatting_instruction},
            {"role": "user", "content": question_prompt}
        ],
        temperature=0.8,  # Higher temperature for more creative, tailored questions
        max_tokens=500
    )
    
    return response.choices[0].message.content

async def generate_next_question(question_tag: str, session_data: dict) -> str:
    """Generate the next business planning question based on the question tag"""
    
    # Business planning questions mapping
    business_plan_questions = {
        "BUSINESS_PLAN.01": "What problem does your business solve?",
        "BUSINESS_PLAN.02": "Who has this problem (your target market)?",
        "BUSINESS_PLAN.03": "What is your solution (product or service)?",
        "BUSINESS_PLAN.04": "How is your solution different from existing alternatives?",
        "BUSINESS_PLAN.05": "What are your key features and benefits?",
        "BUSINESS_PLAN.06": "What is your business model (how will you make money)?",
        "BUSINESS_PLAN.07": "Who are your main competitors?",
        "BUSINESS_PLAN.08": "What is your competitive advantage?",
        "BUSINESS_PLAN.09": "What is your target market size?",
        "BUSINESS_PLAN.10": "How will you reach your customers (marketing strategy)?",
        "BUSINESS_PLAN.11": "What is your pricing strategy?",
        "BUSINESS_PLAN.12": "What are your estimated startup costs?",
        "BUSINESS_PLAN.13": "Where will your business be located? Why did you choose this location?",
        "BUSINESS_PLAN.14": "What funding do you need and how will you get it?",
        "BUSINESS_PLAN.15": "What are your key operational requirements?",
        "BUSINESS_PLAN.16": "What equipment or technology do you need?",
        "BUSINESS_PLAN.17": "Where will your business be located?",
        "BUSINESS_PLAN.18": "What staff do you need initially?",
        "BUSINESS_PLAN.19": "Who are your key suppliers and vendors?",
        "BUSINESS_PLAN.20": "What legal requirements do you need to meet?",
        "BUSINESS_PLAN.21": "Do you have any intellectual property or proprietary technology?",
        "BUSINESS_PLAN.22": "What is your mission statement or tagline?",
        "BUSINESS_PLAN.23": "What are your short-term goals (first 6 months)?",
        "BUSINESS_PLAN.24": "What are your long-term goals (1-3 years)?",
        "BUSINESS_PLAN.25": "What are the main risks and challenges you face?",
        "BUSINESS_PLAN.26": "How will you measure success?",
        "BUSINESS_PLAN.27": "What is your exit strategy (if applicable)?",
        "BUSINESS_PLAN.28": "What support do you need to launch your business?"
    }
    
    # Get the question text
    question_text = business_plan_questions.get(question_tag, "Please provide additional information about your business.")
    
    # Add the question tag
    formatted_question = f"[[Q:{question_tag}]] {question_text}"
    
    # Add some context and encouragement
    context = f"Great! I'm glad we're making progress.\n\nLet's continue by exploring another important aspect of your business.\n\n{question_text}\n\nConsider: What specific details would help clarify this aspect of your business?\nThink about: How does this relate to your overall business strategy?"
    
    return f"[[Q:{question_tag}]] {context}"

def generate_problem_solution_draft(business_context, history):
    """Generate a specific problem-solution draft based on business context"""
    business_name = business_context.get("business_name", "your business")
    industry = business_context.get("industry", "your industry")
    business_type = business_context.get("business_type", "your business type")
    location = business_context.get("location", "your location")
    
    # Generate contextual content based on actual business context
    return f"""Based on your business vision, here's a draft for your problem-solution fit:

**Problem Identification:**
{business_name} addresses critical challenges in the {industry} sector that affect businesses and individuals in {location}. These challenges include inefficiencies in current processes, lack of specialized expertise, and outdated approaches that limit growth potential.

**Target Audience:**
Your target audience consists of {business_type} businesses and professionals in the {industry} sector who are experiencing these operational challenges and seeking more effective solutions.

**Solution Approach:**
{business_name} provides innovative, specialized solutions that directly address these pain points through:
• Industry-specific expertise and knowledge
• Streamlined processes and methodologies
• Customized approaches for different client needs
• Ongoing support and guidance

**Key Benefits:**
• Improved efficiency and productivity
• Cost-effective solutions compared to alternatives
• Expert guidance and support
• Customized approaches for different segments

**Competitive Advantage:**
Your solution is uniquely positioned because it combines deep industry knowledge with innovative approaches, providing superior value that competitors cannot easily replicate."""

def generate_competitive_analysis_draft(business_context, history):
    """Generate a specific competitive analysis draft based on business context"""
    business_name = business_context.get("business_name", "your business")
    industry = business_context.get("industry", "your industry")
    business_type = business_context.get("business_type", "your business type")
    
    return f"Based on your business context, here's a draft analysis of your competitive landscape: In the {industry} sector, your main competitors likely include established players who offer similar {business_type} solutions. These competitors typically have strengths in brand recognition, resources, and market share, but often have weaknesses in pricing flexibility, customer service personalization, and innovation gaps. {business_name}'s competitive advantage should focus on what makes your solution unique - whether it's better pricing, superior customer experience, innovative features, or specialized expertise in the {industry} sector. Focus on identifying 3-5 key competitors in the {industry} space and analyzing their market positioning, pricing models, and customer base to understand how you can differentiate effectively."

def generate_intellectual_property_draft(business_context, history):
    """Generate a specific intellectual property draft based on business context"""
    business_name = business_context.get("business_name", "your business")
    industry = business_context.get("industry", "your industry")
    business_type = business_context.get("business_type", "your business type")
    
    return f"Based on your business needs, here's a draft for your intellectual property strategy: {business_name} may have intellectual property assets including patents for innovative {business_type} processes, trademarks for your brand identity, and copyrights for original content in the {industry} sector. Consider what legal protections are important for your business, including patent applications for innovative processes or technologies, trademark registration for your brand name and logo, and copyright protection for original content, software, or creative materials. Focus on identifying your proprietary assets, understanding the legal requirements for protection in the {industry} sector, and developing a strategy to safeguard your competitive advantages through appropriate IP protection."

def generate_target_market_draft(business_context, history):
    """Generate a specific target market draft based on business context"""
    business_name = business_context.get("business_name", "your business")
    industry = business_context.get("industry", "your industry")
    business_type = business_context.get("business_type", "your business type")
    location = business_context.get("location", "your location")
    
    return f"""Based on your business goals, here's a draft for your target market:

**Primary Target Audience:**
{business_name}'s ideal customers are {business_type} businesses and professionals in the {industry} sector who are seeking specialized solutions and expertise. These customers value quality service, innovation, and results-driven approaches.

**Demographic Profile:**
• Business Type: {business_type} companies
• Industry Focus: {industry} sector
• Geographic Location: {location} and surrounding areas
• Company Size: Small to medium businesses seeking growth

**Psychographic Characteristics:**
• Value quality service and expertise
• Seek innovative solutions to industry challenges
• Prefer working with specialized service providers
• Focus on efficiency and measurable results

**Customer Behaviors:**
• Research extensively before making decisions
• Prefer direct communication and personalized service
• Value long-term partnerships over transactional relationships
• Respond well to industry-specific expertise and knowledge

**Pain Points:**
• Lack of specialized expertise in the {industry} sector
• Inefficient processes and outdated approaches
• Limited access to innovative solutions
• Need for ongoing support and guidance

**How to Reach Them:**
Focus on industry-specific channels, professional networks, and direct outreach that demonstrates your expertise in the {industry} sector."""

def generate_operational_requirements_draft(business_context, history):
    """Generate a specific operational requirements draft based on business context"""
    business_name = business_context.get("business_name", "your business")
    industry = business_context.get("industry", "your industry")
    business_type = business_context.get("business_type", "your business type")
    location = business_context.get("location", "your location")
    
    return f"Based on your business needs, here's a draft for your operational requirements: {business_name}'s location in {location} should be strategically chosen to maximize accessibility for your target customers while considering operational efficiency for your {business_type} operations. Key factors include proximity to suppliers, transportation access, zoning requirements for {industry} businesses, and cost considerations. Your space and equipment needs should align with your {business_type} operations, ensuring you have adequate facilities to serve your customers effectively while maintaining operational efficiency. Focus on factors like zoning compliance for {industry} businesses, transportation access for customers and suppliers, costs, and scalability as your business grows."

def generate_staffing_needs_draft(business_context, history):
    """Generate a specific staffing needs draft based on business context"""
    business_name = business_context.get("business_name", "your business")
    industry = business_context.get("industry", "your industry")
    business_type = business_context.get("business_type", "your business type")
    
    # Check if user previously mentioned specific staff
    mentioned_staff = business_context.get("staffing_needs", [])
    
    # Also extract from history if not in business_context
    if not mentioned_staff:
        import re
        staff_keywords = ['secretary', 'assistant', 'receptionist', 'office manager', 'bookkeeper', 'accountant', 'staff', 'employee', 'worker']
        for msg in history:
            if msg.get('role') == 'user':
                content_lower = msg.get('content', '').lower()
                for keyword in staff_keywords:
                    pattern = r'\b(\d+)?\s*(?:office\s+)?(?:a\s+|an\s+)?' + re.escape(keyword) + r's?\b'
                    matches = re.finditer(pattern, content_lower)
                    for match in matches:
                        full_match = match.group(0)
                        number = match.group(1)
                        if number:
                            staff_mention = f"{number} {full_match.replace(number, '').strip()}"
                        else:
                            staff_mention = full_match.strip()
                        staff_mention = re.sub(r'\s+', ' ', staff_mention).strip()
                        if staff_mention and staff_mention not in mentioned_staff:
                            mentioned_staff.append(staff_mention)
                        break
    
    # If user previously mentioned specific staff, reference it
    if mentioned_staff:
        staff_list = list(set(mentioned_staff))  # Remove duplicates
        staff_summary = ", ".join(staff_list[:3])  # Limit to first 3 mentions
        return f"""Based on your previous answers where you mentioned {staff_summary}, here's a draft for your staffing needs:

**Initial Staffing Structure:**
You've previously indicated your staffing needs include {staff_summary}. This is a great starting point for {business_name}'s operations in the {industry} sector.

**Key Considerations:**
• {staff_summary} will help support your core {business_type} business functions
• Consider the specific roles and responsibilities for each position
• Think about the qualifications and skills needed for these roles in the {industry} industry
• Plan for how these staff members will integrate into your operations

**Operational Integration:**
• How will {staff_summary} support your daily operations at {business_name}?
• What systems and processes will you need to manage this team effectively?
• Consider training needs and onboarding processes specific to {industry}
• Plan for supervision and performance management

**Resource Planning:**
• Budget for salaries, benefits, and training for {staff_summary}
• Workspace requirements for your team
• Tools and equipment needed for each role in {industry}
• Consider part-time vs. full-time arrangements based on your needs

This staffing structure will help you build a strong foundation for {business_name}'s operations."""
    
    return f"Based on your business goals, here's a draft for your staffing needs: {business_name}'s short-term operational needs should focus on identifying critical roles required for launch in the {industry} sector, including key personnel who can drive your core {business_type} business functions. Consider hiring initial staff who bring essential skills and experience in {industry}, securing appropriate workspace for your team, and establishing operational processes that support your business model. Prioritize roles that directly impact customer experience and business operations, ensuring you have the right team in place to execute your business plan effectively. Focus on identifying key positions specific to {business_type} operations, required qualifications for {industry} professionals, and your hiring timeline for building a strong foundation team."

def generate_supplier_relationships_draft(business_context, history):
    """Generate a specific supplier relationships draft based on business context"""
    business_name = business_context.get("business_name", "your business")
    industry = business_context.get("industry", "your industry")
    business_type = business_context.get("business_type", "your business type")
    
    return f"Based on your business requirements, here's a comprehensive draft for your supplier and vendor relationships: {business_name} will need to identify key suppliers and vendors who can provide essential products, services, or resources for your {business_type} operations in the {industry} sector. Consider building relationships with reliable partners who offer competitive pricing, quality products, and consistent service. Key partners might include suppliers for raw materials or components specific to {industry}, service providers for essential business functions, and strategic partners who can help you reach your target market or enhance your offerings. Focus on reliability, quality, pricing, and long-term partnership potential. Evaluate potential partners based on their track record in the {industry} sector, financial stability, capacity to meet your needs, and alignment with your business values. Consider backup suppliers to ensure business continuity and negotiate favorable terms that support your growth objectives in the {industry} market."
async def generate_startup_costs_table_draft(business_context, current_question):
    """Generate dynamic, AI-powered startup costs table for ANY business type"""
    industry = business_context.get("industry", "your industry")
    business_name = business_context.get("business_name", "your business")
    location = business_context.get("location", "your location")
    business_type = business_context.get("business_type", "service")
    
    # Use AI to generate industry-specific, location-aware startup costs
    prompt = f"""You are a business finance expert. Generate a comprehensive startup costs table for a {industry} business named "{business_name}" in {location}.

CONTEXT:
- Business Type: {business_type}
- Industry: {industry}
- Location: {location}

REQUIREMENTS:
1. Include industry-specific equipment, tools, and technology
2. Include all necessary licenses and certifications specific to {industry}
3. Adjust costs realistically for {location}'s cost of living
4. Provide 4-6 main categories with specific line items
5. Give realistic cost ranges (minimum - maximum)
6. Add helpful, industry-specific notes
7. Calculate and show total estimated costs

FORMAT EXACTLY AS BELOW:

**Startup Costs Breakdown**

| Category | Item | Estimated Cost | Notes |
|----------|------|----------------|-------|
| **[Category 1]** | | | |
| | [Specific item] | $X,XXX - $X,XXX | [Helpful note] |
| | [Specific item] | $X,XXX - $X,XXX | [Helpful note] |
| **[Category 2]** | | | |
| | [Specific item] | $X,XXX - $X,XXX | [Helpful note] |
[... continue for all categories ...]

**Total Estimated Startup Costs: $XX,XXX - $XX,XXX**

*Note: [Add location and industry-specific context]*

Be specific to {industry}, not generic. Include actual industry requirements."""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1200
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating startup costs: {e}")
        # Fallback if AI fails
        return f"""Based on your {industry} business in {location}, consider these startup cost categories:

**Key Startup Cost Areas:**
- Industry-specific equipment and tools
- Required business licenses and permits
- Insurance and legal setup costs
- Marketing and technology infrastructure
- Working capital and inventory

Please provide more details for a customized breakdown."""
async def generate_sales_projection_draft(business_context, current_question):
    """Generate dynamic, AI-powered sales projections for ANY business type"""
    industry = business_context.get("industry", "your industry")
    business_name = business_context.get("business_name", "your business")
    location = business_context.get("location", "your location")
    business_type = business_context.get("business_type", "service")
    
    prompt = f"""You are a business finance expert. Generate realistic first-year sales projections for "{business_name}" - a {industry} business in {location}.

CONTEXT:
- Industry: {industry}
- Business Type: {business_type}
- Location: {location}

Generate industry-specific sales projections using the CORRECT revenue model for {industry}:
- Service business: billable hours × hourly rate OR number of jobs × average price
- Product business: units sold × price per unit
- SaaS: monthly subscribers × price × 12 months
- Restaurant: covers per day × average check × days per year
- Retail: foot traffic × conversion rate × average purchase
- Consulting: billable hours × hourly rate × utilization rate

REQUIREMENTS:
1. Use industry-standard pricing for {industry} in {location}
2. Provide detailed calculation breakdown with correct math
3. Show weekly/monthly/annual projections
4. Include growth assumptions
5. Add critical considerations for {industry}
6. Format with clear sections and calculations

Be SPECIFIC to {industry} - use correct metrics, pricing, and volume assumptions for that industry."""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating sales projections: {e}")
        return f"""Based on your {industry} business goals, create realistic first-year sales projections considering:
- Industry-standard pricing for {industry}
- Market size and accessibility in {location}
- Customer acquisition rate and conversion
- Seasonal variations
- Growth trajectory"""

async def generate_monthly_expenses_draft(business_context, current_question):
    """Generate dynamic, AI-powered monthly expenses for ANY business type"""
    industry = business_context.get("industry", "your industry")
    business_name = business_context.get("business_name", "your business")
    location = business_context.get("location", "your location")
    business_type = business_context.get("business_type", "service")
    
    prompt = f"""You are a business finance expert. Generate realistic monthly operating expenses for "{business_name}" - a {industry} business in {location}.

CONTEXT:
- Industry: {industry}
- Business Type: {business_type}
- Location: {location}

REQUIREMENTS:
1. Include industry-specific expense categories for {industry}
2. Automatically adjust ALL costs for {location}'s cost of living (research typical costs for that area)
3. Include ALL necessary expenses (don't miss vehicle costs if needed, rent if needed, etc.)
4. Provide realistic cost ranges (min - max)
5. Add helpful notes for each line item
6. Calculate total monthly expenses
7. Format as a table

For {industry} businesses, typical expense categories might include:
- Staffing (wages appropriate for {location})
- Facilities/rent (if needed for {industry})
- Vehicle costs (if {industry} requires transportation)
- Equipment/tools maintenance
- Materials/inventory
- Marketing & advertising
- Insurance & licenses
- Technology/software
- Utilities

**Total Monthly Expenses: $X,XXX - $X,XXX**

Adjust ALL numbers for {location}. Be SPECIFIC to {industry}."""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1200
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating monthly expenses: {e}")
        return f"""Based on your {industry} business in {location}, consider these monthly expense categories:
- Staffing costs
- Facility/rent (if applicable)
- Vehicle/transportation (if applicable)
- Materials/inventory
- Marketing & advertising
- Insurance & licenses
- Technology & software"""
async def generate_pricing_with_cost_analysis_draft(business_context, current_question):
    """Generate pricing strategy with comprehensive cost analysis"""
    industry = business_context.get("industry", "your industry")
    business_name = business_context.get("business_name", "your business")
    location = business_context.get("location", "your location")
    business_type = business_context.get("business_type", "service")
    
    prompt = f"""You are a business pricing expert. Generate a comprehensive pricing strategy with detailed cost analysis for "{business_name}" - a {industry} business in {location}.

CONTEXT:
- Industry: {industry}
- Business Type: {business_type}
- Location: {location}

REQUIREMENTS:
1. Provide a comprehensive cost analysis that includes:
   - Fixed costs (rent, salaries, insurance, utilities, etc.) with actual dollar amounts
   - Variable costs per unit/service (materials, labor, commissions, etc.) with actual dollar amounts
   - Overhead costs (marketing, administrative, etc.) with actual dollar amounts
   - Total cost per unit/service calculation

2. Develop pricing strategy based on cost analysis:
   - Cost-plus pricing: Calculate minimum price needed to cover costs
   - Competitive pricing: Research-based pricing relative to competitors
   - Value-based pricing: Pricing based on customer value perception
   - Recommended pricing range with specific dollar amounts

3. Include break-even analysis:
   - Break-even point in units/services
   - Break-even point in revenue (actual dollar amount)
   - Profit margin targets (specific percentages)

4. Provide pricing tiers/options if applicable:
   - Basic tier: $X - includes [features]
   - Standard tier: $Y - includes [features]
   - Premium tier: $Z - includes [features]

5. Include industry-specific considerations for {industry}:
   - Market pricing benchmarks for {location}
   - Customer willingness to pay
   - Seasonal pricing variations if applicable

⚠️ CRITICAL: You MUST provide ACTUAL NUMERICAL ESTIMATES:
- All costs must have specific dollar amounts (e.g., "$500-$1,200 per month", "$25-$50 per unit")
- Pricing recommendations must include specific dollar ranges (e.g., "$99-$149 per service", "$49-$79 per product")
- Break-even calculations must show actual numbers (e.g., "Break-even at 50 units/month = $5,000 revenue")
- Base all estimates on {industry} industry benchmarks and {location} market conditions

Be SPECIFIC to {industry} - use actual pricing strategies that industry uses, not generic ones.
DO NOT provide general advice - provide actual numbers and calculations the user can use immediately."""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating pricing with cost analysis: {e}")
        return f"""Pricing Strategy with Cost Analysis for {industry} business:

**Cost Analysis Required:**
- Calculate all fixed costs (rent, salaries, insurance, utilities)
- Calculate variable costs per unit/service (materials, labor, commissions)
- Calculate overhead costs (marketing, administrative)
- Determine total cost per unit/service

**Pricing Strategy:**
- Cost-plus pricing: Add desired profit margin to total costs
- Competitive pricing: Research competitor pricing in {location}
- Value-based pricing: Price based on customer value perception

**Break-Even Analysis:**
- Calculate break-even point in units/services
- Calculate break-even revenue
- Set profit margin targets

**Recommendations:**
- Research {industry} pricing benchmarks for {location}
- Consider customer willingness to pay
- Test pricing with target market"""

async def generate_customer_acquisition_cost_draft(business_context, current_question):
    """Generate dynamic, AI-powered CAC analysis for ANY business type"""
    industry = business_context.get("industry", "your industry")
    business_name = business_context.get("business_name", "your business")
    location = business_context.get("location", "your location")
    business_type = business_context.get("business_type", "service")
    
    prompt = f"""You are a business marketing expert. Generate a comprehensive Customer Acquisition Cost (CAC) analysis for "{business_name}" - a {industry} business in {location}.

CONTEXT:
- Industry: {industry}
- Business Type: {business_type}
- Location: {location}

REQUIREMENTS:
1. Identify industry-appropriate marketing channels for {industry} (NOT generic)
2. Use realistic costs for {location}'s market
3. Provide detailed CAC breakdown by channel
4. Calculate profitability (LTV:CAC ratio)
5. Give optimization recommendations
6. Format as tables

⚠️ CRITICAL: You MUST provide ACTUAL NUMERICAL ESTIMATES with specific dollar amounts:
- Provide specific dollar ranges for CAC per channel (e.g., "$25-$75 per customer", "$50-$150 per customer")
- Include actual monthly marketing spend estimates (e.g., "$500-$2,000 per month")
- Provide specific conversion rate percentages (e.g., "2-5%", "10-15%")
- Calculate actual total CAC with a specific dollar amount (e.g., "$45-$120 per customer")
- Include actual LTV estimates with dollar amounts (e.g., "$200-$500 per customer")
- Provide actual LTV:CAC ratios (e.g., "3:1", "4:1")
- Base all estimates on {industry} industry benchmarks and {location} market conditions

Marketing channels should be SPECIFIC to {industry}:
- B2B SaaS: LinkedIn Ads, content marketing, cold outreach, webinars
- Restaurant: Local SEO, food delivery apps, Instagram, Yelp
- E-commerce: Facebook/Instagram ads, Google Shopping, influencers
- Consulting: LinkedIn, referrals, speaking engagements, thought leadership
- Retail: Local ads, social media, events, partnerships
- Professional services: Referrals, networking, SEO, professional directories

Include:
- Monthly cost per channel (with actual dollar amounts)
- Leads generated (with actual numbers)
- Conversion rates (industry-realistic percentages)
- CAC per channel (with actual dollar amounts like "$30-$80")
- Total CAC (with actual dollar amount like "$45-$120 per customer")
- LTV calculation (with actual dollar amount)
- LTV:CAC ratio (with actual ratio like "3:1" or "4:1")
- Profitability assessment (with actual numbers)
- Optimization recommendations

Be SPECIFIC to {industry} - use actual channels that industry uses, not generic ones.
DO NOT provide general advice - provide actual numbers the user can use immediately."""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating CAC analysis: {e}")
        return f"""Customer Acquisition Cost Analysis for {industry} business:

Consider industry-appropriate channels for {industry}:
- Research which channels work best for {industry}
- Calculate realistic costs for {location}
- Determine conversion rates
- Calculate LTV:CAC ratio
- Assess profitability"""

def build_fallback_question(
    question_tag: str,
    objective: Optional[str],
    business: str,
    industry_descriptor: str,
    location_phrase: str,
    location_only: str,
    target_market: str,
    business_type: str,
    offering: str,
    recent_excerpt: str,
    launch_context: str
) -> str:
    """Generate a deterministic fallback question if model generation fails"""
    if objective:
        objective_clause = objective.rstrip(".")
        base_question = (
            f"How does {business} plan to {objective_clause.lower()}?"
            if objective_clause else
            ""
        )
    else:
        base_question = ""
    
    if not base_question:
        if recent_excerpt:
            base_question = (
                f"Building on \"{recent_excerpt}\", what should {business} focus on next for {question_tag.lower()}?"
            )
        else:
            base_question = f"What should {business} address for {question_tag.lower()}?"
    
    personalized_bits = []
    if industry_descriptor and "your industry" not in industry_descriptor.lower():
        personalized_bits.append(industry_descriptor)
    if location_phrase:
        personalized_bits.append(location_phrase)
    if personalized_bits:
        context_phrase = ", ".join(personalized_bits)
        base_question = f"{base_question.rstrip('?')} ({context_phrase})?"
    
    if not base_question.endswith("?"):
        base_question = f"{base_question.rstrip('.')}?"
    
    return base_question.strip()

async def generate_question_with_model(
    question_tag: str,
    objective: str,
    business: str,
    industry: str,
    location: str,
    target_market: str,
    business_type: str,
    offering: str,
    recent_excerpt: str
) -> Optional[str]:
    """Use the LLM to craft a dynamic business question"""
    system_prompt = "You are an entrepreneurship coach who writes bespoke business-planning questions."
    user_prompt = f"""
Context:
- Business Name: {business}
- Industry: {industry}
- Offering: {offering}
- Location: {location or 'unspecified'}
- Target Market: {target_market}
- Business Type/Structure: {business_type}
- Recent Answer From Founder: {recent_excerpt or 'None provided'}

Question Objective:
{objective}

Instructions:
1. Produce exactly ONE business-planning question tailored to the context above.
2. Ground the question in the founder's specific business details (industry, offering, location, recent answer).
3. Start the output on its own line, wrap the full sentence in <strong>...</strong>, and include a blank line before and after.
4. Keep the question under 45 words and end with a question mark.
5. Do not include commentary, bullet points, or multiple sentences—return only the formatted question.
""".strip()

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=120
    )

    raw_question = (response.choices[0].message.content or "").strip()
    if not raw_question:
        return None
    if "<strong>" not in raw_question.lower():
        raw_question = f"<strong>{raw_question.strip()}</strong>"
    question = raw_question.strip()
    if not question.startswith("\n"):
        question = f"\n{question}"
    if not question.endswith("\n"):
        question = f"{question}\n"
    return question

async def generate_dynamic_critiquing_insight(field: str, session_data: Optional[dict], user_input: str) -> Optional[str]:
    business_name = (session_data or {}).get("business_name") or "this business"
    industry = (session_data or {}).get("industry") or field
    location = (session_data or {}).get("location") or "unspecified location"
    target_market = (session_data or {}).get("target_market") or "target customers"

    system_prompt = (
        "You are a supportive entrepreneurship coach who gives concise, practical coaching insights."
    )
    user_prompt = f"""
Business Name: {business_name}
Primary Industry: {industry}
Detected Focus Area: {field}
Location: {location}
Target Audience: {target_market}

Founder Response:
{user_input}

Task:
In 2 sentences, provide constructive coaching that balances encouragement with actionable guidance for this founder. Reference the detected focus area and, when helpful, the founder's response. Offer specific next steps or considerations rather than generic platitudes. Do not use bullet points, headings, or repeat the original answer.
""".strip()

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.4,
            max_tokens=200
        )
        insight = (response.choices[0].message.content or "").strip()
        return insight if insight else None
    except Exception as exc:
        print(f"⚠️ Failed to generate dynamic critiquing insight: {exc}")
        return None

def transform_question_objective(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if not text:
        return text
    sentences = re.split(r'(?<=[.?!])\s+', text)
    transformed: list[str] = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if sentence.endswith("?"):
            statement = convert_question_to_objective(sentence[:-1].strip())
            transformed.append(statement)
        else:
            transformed.append(sentence)
    return " ".join(transformed).strip()

def convert_question_to_objective(question: str) -> str:
    if not question:
        return ""
    replacements = [
        (r"(?i)^what\s+are\s+your\s+", "Detail your "),
        (r"(?i)^what\s+is\s+your\s+", "Explain your "),
        (r"(?i)^what\s+is\s+the\s+", "Explain the "),
        (r"(?i)^what\s+will\s+you\s+", "Outline how you will "),
        (r"(?i)^how\s+will\s+you\s+", "Describe how you will "),
        (r"(?i)^how\s+do\s+you\s+", "Describe how you "),
        (r"(?i)^who\s+are\s+your\s+", "Identify your "),
        (r"(?i)^who\s+is\s+your\s+", "Identify your "),
        (r"(?i)^when\s+do\s+you\s+", "Clarify when you "),
        (r"(?i)^where\s+will\s+you\s+", "Explain where you will "),
        (r"(?i)^do\s+you\s+have\s+", "State whether you have "),
        (r"(?i)^have\s+you\s+", "Indicate whether you have "),
    ]
    for pattern, replacement in replacements:
        if re.match(pattern, question):
            return re.sub(pattern, replacement, question, count=1)
    return f"Address {question.lower()}"

def remove_duplicate_paragraphs(text: str) -> str:
    if not text:
        return text
    paragraphs = text.split("\n\n")
    seen: set[str] = set()
    deduped: list[str] = []
    for para in paragraphs:
        normalized = re.sub(r'\s+', ' ', para.strip()).lower()
        if normalized and normalized in seen:
            continue
        if normalized:
            seen.add(normalized)
        deduped.append(para)
    return "\n\n".join(deduped)
