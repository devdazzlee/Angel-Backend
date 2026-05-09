import os
import re
import json
from typing import Dict, Any, Optional, List, Tuple
import PyPDF2
import docx
from docx import Document
import tempfile
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


_CANONICAL_BP_QUESTIONS_CACHE: Optional[List[Tuple[int, str]]] = None


def parse_canonical_business_plan_questions() -> List[Tuple[int, str]]:
    """
    Parse the canonical 45 BUSINESS_PLAN questions from ANGEL_SYSTEM_PROMPT in
    constant.py — the single source of truth used by Angel itself. Returns a sorted
    list of (question_number, first_line_question_text) tuples. Cached after first
    parse since the prompt is static.

    The regex is anchored to start-of-line (^ with re.MULTILINE) because canonical
    definitions appear at column 0 in the prompt:
        [[Q:BUSINESS_PLAN.08]] Who is your target customer?...
    while inline mentions (which would otherwise hijack the capture) are always
    embedded mid-sentence:
        Market Research applies to [[Q:BUSINESS_PLAN.08]] through [[Q:BUSINESS_PLAN.13]].
    Without the anchor, the regex grabbed "through" as Q8's text, etc.
    """
    global _CANONICAL_BP_QUESTIONS_CACHE
    if _CANONICAL_BP_QUESTIONS_CACHE is not None:
        return _CANONICAL_BP_QUESTIONS_CACHE

    from utils.constant import ANGEL_SYSTEM_PROMPT

    # ^ + MULTILINE → only definitions at the start of a line are captured.
    pattern = re.compile(
        r'^\[\[Q:BUSINESS_PLAN\.(\d{2})\]\]\s*([^\n\[]+)',
        re.MULTILINE,
    )
    seen: Dict[int, str] = {}
    for num_str, text in pattern.findall(ANGEL_SYSTEM_PROMPT):
        num = int(num_str)
        if not (1 <= num <= 45):
            continue
        cleaned = text.strip()
        if cleaned and num not in seen:
            seen[num] = cleaned

    result = sorted(seen.items())
    _CANONICAL_BP_QUESTIONS_CACHE = result
    return result


async def extract_per_question_answers(content: str) -> Dict[int, Optional[str]]:
    """
    Single LLM pass: for each canonical BUSINESS_PLAN question, extract an answer
    from the document or return None. Returns a mapping {question_number: answer}.

    This is the source-of-truth extraction. Other helpers (business_info summary,
    completeness analysis) derive from this single result so the upload pipeline
    cannot drift from Angel's actual questionnaire.
    """
    questions = parse_canonical_business_plan_questions()
    if not questions:
        return {}

    questions_payload = "\n".join([f"Q{n}. {t}" for n, t in questions])
    last_q = questions[-1][0]

    prompt = f"""Extract answers to the following business plan questions using ONLY the document content provided. Do not invent details.

QUESTIONS (Q1 through Q{last_q}):
{questions_payload}

DOCUMENT CONTENT (first 12,000 chars):
{content[:12000]}

INSTRUCTIONS:
- For each question, return a 1-4 sentence answer drawn from the document, written naturally as the founder would write it.
- If the document does not address a question, return null for that question.
- Do NOT copy the question text; return only the answer.
- Return ONE valid JSON object with this exact shape (no commentary, no markdown fences):
  {{ "answers": {{ "1": "...", "2": null, "3": "...", ... }} }}
- Keys MUST be string question numbers from "1" through "{last_q}"."""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You extract structured answers from business documents. Use only document content. Return strict JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=4000,
        )
        text = response.choices[0].message.content.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        parsed = json.loads(text)
        answers_raw = parsed.get("answers", {}) if isinstance(parsed, dict) else {}

        out: Dict[int, Optional[str]] = {}
        for q_num, _ in questions:
            value = answers_raw.get(str(q_num))
            if value is None:
                out[q_num] = None
            elif isinstance(value, str):
                v = value.strip()
                out[q_num] = v if v and v.upper() not in {"NULL", "N/A", "NOT_FOUND"} else None
            else:
                try:
                    serialized = json.dumps(value, ensure_ascii=False)
                    out[q_num] = serialized if serialized and serialized != "null" else None
                except Exception:
                    out[q_num] = None
        return out
    except Exception as e:
        print(f"⚠️ extract_per_question_answers failed: {e}")
        return {q_num: None for q_num, _ in questions}


# Maps canonical question numbers (1–45) to legacy business_info summary keys that
# downstream code (business_context, prompts, frontend) already reads. This lets us
# populate the summary dict without breaking existing consumers.
_QUESTION_TO_SUMMARY_KEYS: Dict[int, List[str]] = {
    1: ["business_idea", "solution"],
    2: ["product_or_service", "product_description"],
    3: ["unique_advantage", "competitive_advantage", "value_proposition", "unique_value"],
    4: ["business_stage"],
    5: ["business_name"],
    6: ["industry", "business_type"],
    7: ["short_term_goals"],
    8: ["target_market"],
    9: ["distribution_channels"],
    10: ["problem_solved", "problem"],
    11: ["competitors"],
    13: ["differentiation"],
    14: ["location"],
    18: ["mission", "tagline", "vision"],
    19: ["marketing_methods", "marketing_strategy"],
    21: ["unique_selling_proposition"],
    24: ["legal_structure", "business_structure"],
    29: ["revenue_model"],
    30: ["pricing", "pricing_strategy"],
    32: ["funding_source"],
    33: ["first_year_financial_goals", "key_metrics"],
    34: ["startup_costs"],
    36: ["long_term_goals", "goals"],
    44: ["funding_needs"],
    45: ["five_year_vision"],
}


def _summary_from_per_question(per_question: Dict[int, Optional[str]]) -> Dict[str, Any]:
    """Build the legacy business_info summary dict (preserving downstream key names)
    from the canonical per-question answers."""
    summary: Dict[str, Any] = {}
    for q_num, keys in _QUESTION_TO_SUMMARY_KEYS.items():
        value = per_question.get(q_num)
        for key in keys:
            summary[key] = value
    return summary

async def process_uploaded_plan(file_path: str, file_extension: str) -> str:
    """
    Process uploaded business plan file and extract text content
    Supports: PDF, DOC, DOCX, TXT
    """
    try:
        if file_extension == '.pdf':
            return await extract_pdf_text(file_path)
        elif file_extension == '.docx':
            return await extract_docx_text(file_path)
        elif file_extension == '.doc':
            return await extract_doc_text(file_path)
        elif file_extension == '.txt':
            return await extract_txt_text(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
            
    except Exception as e:
        print(f"Error processing file: {e}")
        raise Exception(f"Failed to process file: {str(e)}")

async def extract_pdf_text(file_path: str) -> str:
    """Extract text from PDF file"""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
                
        return text.strip()
    except Exception as e:
        raise Exception(f"Error extracting PDF text: {str(e)}")

async def extract_docx_text(file_path: str) -> str:
    """Extract text from DOCX file"""
    try:
        doc = Document(file_path)
        text = ""
        
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
            
        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text += cell.text + " "
                text += "\n"
                
        return text.strip()
    except Exception as e:
        raise Exception(f"Error extracting DOCX text: {str(e)}")

async def extract_doc_text(file_path: str) -> str:
    """Extract text from DOC file (requires additional library)"""
    try:
        # For .doc files, we'd need python-docx2txt or similar
        # For now, return a message to convert to .docx
        raise Exception("DOC files are not supported. Please convert to DOCX format.")
    except Exception as e:
        raise Exception(f"Error extracting DOC text: {str(e)}")

async def extract_txt_text(file_path: str) -> str:
    """Extract text from TXT file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except Exception as e:
        raise Exception(f"Error extracting TXT text: {str(e)}")

async def extract_business_info_from_plan(
    content: str,
    per_question_answers: Optional[Dict[int, Optional[str]]] = None,
) -> Dict[str, Any]:
    """
    Build the legacy business_info summary dict from canonical per-question answers.

    Downstream code (business_context fields, generate_plan_service, prompts in
    angel_service, frontend display) reads keys like business_name, industry,
    mission, location, target_market — those are preserved by mapping canonical
    question answers back to those keys via _QUESTION_TO_SUMMARY_KEYS.

    `per_question_answers` is normally provided by the caller (already extracted
    from the document) so we don't double-call the LLM. When omitted, this helper
    extracts on demand for backward compatibility.
    """
    if per_question_answers is None:
        per_question_answers = await extract_per_question_answers(content)

    if not any(per_question_answers.values()):
        # Last-resort heuristic fallback when AI extraction yielded nothing.
        return create_fallback_business_info(content)

    return _summary_from_per_question(per_question_answers)

def create_fallback_business_info(content: str) -> Dict[str, Any]:
    """Create basic business info when AI extraction fails"""
    return {
        "business_name": extract_basic_info(content, ["company", "business", "organization"]),
        "business_type": extract_basic_info(content, ["service", "product", "technology"]),
        "industry": extract_basic_info(content, ["industry", "sector", "market"]),
        "mission": extract_basic_info(content, ["mission", "purpose"]),
        "vision": extract_basic_info(content, ["vision", "goal"]),
        "tagline": extract_basic_info(content, ["tagline", "slogan"]),
        "target_market": extract_basic_info(content, ["customer", "client", "target"]),
        "value_proposition": extract_basic_info(content, ["value", "benefit", "advantage"]),
        "revenue_model": extract_basic_info(content, ["revenue", "income", "pricing"]),
        "competitive_advantage": extract_basic_info(content, ["competitive", "unique", "differentiation"]),
        "problem_solved": extract_basic_info(content, ["problem", "challenge", "issue"]),
        "solution": extract_basic_info(content, ["solution", "approach", "method"]),
        "market_size": None,
        "business_structure": extract_basic_info(content, ["LLC", "corporation", "partnership"]),
        "location": extract_basic_info(content, ["location", "address", "city"]),
        "founding_year": extract_basic_info(content, ["founded", "established", "started"]),
        "team_size": None,
        "funding_needs": extract_basic_info(content, ["funding", "investment", "capital"]),
        "key_metrics": None,
        "goals": extract_basic_info(content, ["goal", "objective", "target"])
    }

def extract_basic_info(content: str, keywords: list) -> Optional[str]:
    """Extract basic information using keyword matching"""
    content_lower = content.lower()
    
    for keyword in keywords:
        pattern = rf'{keyword}[:\s]*([^\n\r]{{10,100}})'
        match = re.search(pattern, content_lower)
        if match:
            return match.group(1).strip()
    
    return None

async def validate_business_plan_content(content: str) -> Dict[str, Any]:
    """
    Validate that the uploaded content is actually a business plan
    """
    try:
        validation_prompt = f"""
        Analyze this document and determine if it's a business plan. Return JSON with:
        {{
            "is_business_plan": true/false,
            "confidence": 0.0-1.0,
            "missing_sections": ["list of missing typical business plan sections"],
            "content_type": "description of what type of document this is",
            "recommendations": "suggestions for improvement"
        }}

        Document content:
        {content[:4000]}

        Typical business plan sections include: Executive Summary, Company Description, Market Analysis, Organization, Service/Product Line, Marketing, Financial Projections, etc.
        """

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing business documents and plans."},
                {"role": "user", "content": validation_prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )

        validation_result = response.choices[0].message.content.strip()
        
        if validation_result.startswith('```json'):
            validation_result = validation_result[7:]
        if validation_result.endswith('```'):
            validation_result = validation_result[:-3]
            
        return json.loads(validation_result)
        
    except Exception as e:
        print(f"Error validating business plan: {e}")
        return {
            "is_business_plan": True,  # Default to accepting
            "confidence": 0.5,
            "missing_sections": [],
            "content_type": "Unknown document type",
            "recommendations": "Unable to validate document structure"
        }

async def analyze_plan_completeness(
    content: str,
    business_info: Dict[str, Any],
    per_question_answers: Optional[Dict[int, Optional[str]]] = None,
) -> Dict[str, Any]:
    """
    Build the analysis payload (summary, completeness score, missing_questions list)
    directly from canonical per-question answers. The previous version compared the
    document against a hardcoded 45-question list that had drifted out of sync with
    Angel's actual questionnaire — the canonical source is now ANGEL_SYSTEM_PROMPT.
    """
    canonical = parse_canonical_business_plan_questions()

    if per_question_answers is None:
        per_question_answers = await extract_per_question_answers(content)

    if not canonical:
        return {
            "summary": "Unable to load canonical business plan questions.",
            "completeness_score": 0.0,
            "found_information": {},
            "missing_questions": [],
            "recommendations": "An internal error occurred. Please proceed manually.",
        }

    found_question_numbers: List[int] = []
    missing_question_entries: List[Dict[str, Any]] = []
    for q_num, q_text in canonical:
        answer = per_question_answers.get(q_num)
        if answer and answer.strip():
            found_question_numbers.append(q_num)
        else:
            missing_question_entries.append({
                "question_number": q_num,
                "question_text": q_text,
                "category": _category_for_question(q_num),
                "priority": _priority_for_question(q_num),
            })

    completeness_score = round(len(found_question_numbers) / len(canonical), 2)

    # The summary flags in the analysis modal must be forgiving across adjacent
    # canonical questions: the LLM extraction often classifies a topic into a
    # neighbouring Q number (e.g., target-market detail may land in Q9 not Q8,
    # business-structure in Q25 not Q24). Single-question checks made the modal
    # misleadingly show ✗ for topics that are clearly present in the document.
    def _any_filled(*nums: int) -> bool:
        return any(bool(per_question_answers.get(n)) for n in nums)

    found_information = {
        # Business name lives in Q5; Q1 (idea) often mentions it as well.
        "business_name": _any_filled(5, 1),
        # Mission lives in Q18; idea/USP (Q1, Q21) frequently encode the same intent.
        "mission_vision": _any_filled(18, 1, 21),
        # Either side of the problem/solution pair counts — we'll catch the gap
        # in missing_questions for whichever specific Q wasn't covered.
        "problem_solution": _any_filled(10, 2, 3),
        # Customer demographics (Q8) or distribution channel (Q9) both indicate
        # the founder has thought about who the customer is and where to reach them.
        "target_market": _any_filled(8, 9),
        # Competitors (Q11) or differentiation framing (Q13) both reflect
        # competitive awareness.
        "competitors": _any_filled(11, 13),
        "financial_projections": _any_filled(29, 30, 31, 32, 33, 34),
        "marketing_strategy": _any_filled(19, 20, 21, 22, 23),
        "operational_plan": _any_filled(14, 15, 16, 17),
        # Legal structure family: entity (Q24), name registration (Q25),
        # permits (Q26), insurance (Q27), compliance (Q28).
        "legal_structure": _any_filled(24, 25, 26, 27, 28),
        # Risk family: contingency (Q42), market adaptation (Q43), funding fallback (Q44).
        "risk_analysis": _any_filled(42, 43, 44),
    }

    if completeness_score >= 0.85:
        summary_line = f"Your plan covers {len(found_question_numbers)} of {len(canonical)} Founderport questions. Only a few gaps remain."
    elif completeness_score >= 0.5:
        summary_line = f"Your plan covers {len(found_question_numbers)} of {len(canonical)} Founderport questions. We will fill the {len(missing_question_entries)} remaining gaps together."
    else:
        summary_line = f"Your plan covers {len(found_question_numbers)} of {len(canonical)} Founderport questions. Most sections still need detail — we will work through them step by step."

    return {
        "summary": summary_line,
        "completeness_score": completeness_score,
        "found_information": found_information,
        "found_question_numbers": found_question_numbers,
        "missing_questions": missing_question_entries,
        "recommendations": "Complete the remaining questions to produce your full Founderport business plan.",
    }


def _category_for_question(q_num: int) -> str:
    """Approximate section grouping for the analysis modal display."""
    if 1 <= q_num <= 7:
        return "Business Overview"
    if 8 <= q_num <= 13:
        return "Market & Customers"
    if 14 <= q_num <= 17:
        return "Operations"
    if 18 <= q_num <= 23:
        return "Brand & Marketing"
    if 24 <= q_num <= 28:
        return "Legal & Regulatory"
    if 29 <= q_num <= 34:
        return "Financials"
    if 35 <= q_num <= 41:
        return "Growth & Long-Term"
    if 42 <= q_num <= 45:
        return "Risk & Vision"
    return "General"


def _priority_for_question(q_num: int) -> str:
    """Coarse priority hint for the analysis modal — high for foundational items."""
    if q_num in {1, 2, 3, 5, 8, 10, 18, 24, 29}:
        return "high"
    if q_num in {6, 7, 11, 13, 14, 19, 21, 30, 32, 33, 42}:
        return "medium"
    return "low"


