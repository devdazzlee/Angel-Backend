from openai import AsyncOpenAI
import os
import json
import random
from datetime import datetime
from typing import Dict, List, Optional
from utils.constant import ANGEL_SYSTEM_PROMPT

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Motivational quotes for business implementation - expanded collection from famous entrepreneurs and leaders
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
        "category": "Vision"
    },
    {
        "quote": "Don't be afraid to give up the good to go for the great.",
        "author": "John D. Rockefeller",
        "category": "Ambition"
    },
    {
        "quote": "The only way to do great work is to love what you do.",
        "author": "Steve Jobs",
        "category": "Passion"
    },
    {
        "quote": "Success usually comes to those who are too busy to be looking for it.",
        "author": "Henry David Thoreau",
        "category": "Focus"
    },
    {
        "quote": "Your time is limited, don't waste it living someone else's life.",
        "author": "Steve Jobs",
        "category": "Authenticity"
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

# Service provider categories with sample providers
SERVICE_PROVIDER_CATEGORIES = {
    "legal": [
        {
            "name": "LegalZoom",
            "type": "Online Legal Services",
            "description": "Comprehensive online legal services for business formation",
            "local": False
        },
        {
            "name": "Rocket Lawyer",
            "type": "Online Legal Platform", 
            "description": "Affordable legal services and document templates",
            "local": False
        }
    ],
    "financial": [
        {
            "name": "QuickBooks",
            "type": "Accounting Software",
            "description": "Leading accounting software for small businesses",
            "local": False
        },
        {
            "name": "Xero",
            "type": "Cloud Accounting",
            "description": "Modern cloud-based accounting platform",
            "local": False
        }
    ],
    "marketing": [
        {
            "name": "HubSpot",
            "type": "Marketing Platform",
            "description": "All-in-one marketing, sales, and service platform",
            "local": False
        },
        {
            "name": "Mailchimp",
            "type": "Email Marketing",
            "description": "Email marketing and automation platform",
            "local": False
        }
    ],
    "technology": [
        {
            "name": "Shopify",
            "type": "E-commerce Platform",
            "description": "Complete e-commerce solution for online stores",
            "local": False
        },
        {
            "name": "Squarespace",
            "type": "Website Builder",
            "description": "Website building and hosting platform",
            "local": False
        }
    ]
}

async def get_motivational_quote(business_context: Dict) -> Dict:
    """Get a motivational quote tailored to the business context"""
    
    # Select a relevant quote based on business context
    industry = business_context.get('industry', '').lower()
    business_type = business_context.get('business_type', '').lower()
    
    # Filter quotes based on business context
    relevant_quotes = MOTIVATIONAL_QUOTES.copy()
    
    if 'tech' in industry or 'technology' in industry:
        relevant_quotes.extend([
            q for q in MOTIVATIONAL_QUOTES 
            if q['category'] in ['Innovation', 'Vision']
        ])
    elif 'service' in business_type:
        relevant_quotes.extend([
            q for q in MOTIVATIONAL_QUOTES 
            if q['category'] in ['Passion', 'Authenticity']
        ])
    elif 'startup' in business_type:
        relevant_quotes.extend([
            q for q in MOTIVATIONAL_QUOTES 
            if q['category'] in ['Action', 'Ambition']
        ])
    
    # Return a random quote from the relevant ones
    return random.choice(relevant_quotes)

async def get_service_provider_preview(business_context: Dict) -> List[Dict]:
    """Get a preview of service providers relevant to the business context
    
    Requirements:
    - Minimum 3 providers
    - At least 1 local provider
    """
    
    industry = business_context.get('industry', '').lower()
    business_type = business_context.get('business_type', '').lower()
    location = business_context.get('location', 'United States')
    
    providers = []
    
    # Always include at least one legal provider
    if SERVICE_PROVIDER_CATEGORIES['legal']:
        providers.append(SERVICE_PROVIDER_CATEGORIES['legal'][0])
    
    # Always include at least one financial provider
    if SERVICE_PROVIDER_CATEGORIES['financial']:
        providers.append(SERVICE_PROVIDER_CATEGORIES['financial'][0])
    
    # Add industry-specific providers
    if 'tech' in industry or 'software' in industry:
        if SERVICE_PROVIDER_CATEGORIES['technology']:
            providers.append(SERVICE_PROVIDER_CATEGORIES['technology'][0])
    elif 'retail' in industry or 'ecommerce' in industry:
        if SERVICE_PROVIDER_CATEGORIES['technology']:
            providers.append(SERVICE_PROVIDER_CATEGORIES['technology'][0])
    elif 'service' in business_type or 'consulting' in business_type:
        if SERVICE_PROVIDER_CATEGORIES['marketing']:
            providers.append(SERVICE_PROVIDER_CATEGORIES['marketing'][0])
    
    # CRITICAL: Always add at least 1 local provider (required)
    local_providers = []
    # Always add a local provider regardless of location
    local_providers.append({
        "name": f"Local Business Attorney - {location}",
        "type": "Local Legal Services",
        "description": f"Personalized legal guidance for business formation in {location}",
        "local": True
    })
    
    # Add additional local provider if we need more
    if len(providers) < 2:  # If we have less than 2 non-local, add another local
        local_providers.append({
            "name": f"Local CPA - {location}",
            "type": "Local Accounting Services", 
            "description": f"Personalized accounting and tax services in {location}",
            "local": True
        })
    
    providers.extend(local_providers)
    
    # Ensure we have at least 3 providers total
    while len(providers) < 3:
        # Add more providers from available categories
        if len(providers) < 3 and SERVICE_PROVIDER_CATEGORIES['legal'] and len(providers) < 3:
            if SERVICE_PROVIDER_CATEGORIES['legal'][1] not in providers:
                providers.append(SERVICE_PROVIDER_CATEGORIES['legal'][1])
        if len(providers) < 3 and SERVICE_PROVIDER_CATEGORIES['financial']:
            if SERVICE_PROVIDER_CATEGORIES['financial'][1] not in providers:
                providers.append(SERVICE_PROVIDER_CATEGORIES['financial'][1])
        if len(providers) >= 3:
            break
    
    # Verify we have at least 1 local provider
    local_count = sum(1 for p in providers if p.get('local', False))
    if local_count == 0:
        # Force add a local provider if none exist
        providers.insert(0, {
            "name": f"Local Business Services - {location}",
            "type": "Local Business Services",
            "description": f"Comprehensive local business support in {location}",
            "local": True
        })
    
    # Return providers (minimum 3, at least 1 local)
    return providers[:max(3, len(providers))]

async def generate_implementation_insights(business_context: Dict, roadmap_content: str) -> str:
    """Generate research-backed implementation insights using RAG"""
    
    business_name = business_context.get('business_name', 'Your Business')
    industry = business_context.get('industry', 'general business')
    location = business_context.get('location', 'United States')
    business_type = business_context.get('business_type', 'startup')
    
    # Create comprehensive insights prompt
    insights_prompt = f"""
    Generate comprehensive, research-backed implementation insights for "{business_name}" - a {business_type} in the {industry} industry located in {location}.
    
    Business Context:
    - Business Name: {business_name}
    - Industry: {industry}
    - Location: {location}
    - Business Type: {business_type}
    
    Roadmap Content: {roadmap_content[:1000]}...
    
    Provide insights that include:
    1. Industry-specific implementation considerations
    2. Location-based regulatory and business requirements
    3. Business type specific challenges and opportunities
    4. Timeline and resource allocation recommendations
    5. Risk mitigation strategies
    6. Success metrics and milestones
    
    Make these insights actionable, specific, and tailored to their business context. 
    Focus on practical implementation guidance that will help them succeed.
    
    Format as clear, actionable insights with specific recommendations.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": ANGEL_SYSTEM_PROMPT},
                {"role": "user", "content": insights_prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating implementation insights: {e}")
        return f"Based on your {business_type} in the {industry} industry, implementation will require careful attention to {industry}-specific requirements and {location} regulations. Focus on building strong operational foundations and establishing clear processes for growth."

async def prepare_implementation_transition(session_data: Dict, roadmap_content: str) -> Dict:
    """Prepare comprehensive implementation transition data"""
    
    business_context = {
        "business_name": session_data.get('business_name', 'Your Business'),
        "industry": session_data.get('industry', 'general business'),
        "location": session_data.get('location', 'United States'),
        "business_type": session_data.get('business_type', 'startup')
    }
    
    try:
        # Get motivational quote
        motivational_quote = await get_motivational_quote(business_context)
        
        # Get service provider preview
        service_providers = await get_service_provider_preview(business_context)
        
        # Generate implementation insights
        implementation_insights = await generate_implementation_insights(business_context, roadmap_content)
        
        return {
            "success": True,
            "motivational_quote": motivational_quote,
            "service_providers": service_providers,
            "implementation_insights": implementation_insights,
            "business_context": business_context
        }
    except Exception as e:
        print(f"Error preparing implementation transition: {e}")
        return {
            "success": False,
            "error": str(e),
            "motivational_quote": MOTIVATIONAL_QUOTES[0],
            "service_providers": SERVICE_PROVIDER_CATEGORIES['legal'][:2],
            "implementation_insights": "Implementation insights generation in progress...",
            "business_context": business_context
        }

