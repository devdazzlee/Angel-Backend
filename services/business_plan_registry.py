"""
Business Plan questionnaire registry — single source of truth.

Parsed from ANGEL_SYSTEM_PROMPT (utils/constant.py). Downstream features
(draft, support, scrapping, research routing) must resolve question metadata
by tag via this module — never keyword-matching on free text.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Any, Optional

from utils.constant import ANGEL_SYSTEM_PROMPT

TAG_PATTERN = re.compile(r"\[\[Q:(BUSINESS_PLAN\.\d{2})\]\]", re.IGNORECASE)
QUESTION_BLOCK_PATTERN = re.compile(
    r"\[\[Q:(BUSINESS_PLAN\.\d{2})\]\](.*?)(?=\n\s*\[\[Q:BUSINESS_PLAN|\n\s*---|\Z)",
    re.DOTALL | re.IGNORECASE,
)
QUESTIONNAIRE_START_MARKER = "--- SECTION 1: PRODUCT/SERVICE DETAILS ---"
QUESTIONNAIRE_END_MARKER = "--- PHASE 3: ROADMAP ---"
SECTION_PATTERN = re.compile(
    r"---\s*SECTION\s+(\d+):\s*(.+?)\s*---",
    re.IGNORECASE,
)
AUTO_RESEARCH_NOTE = re.compile(
    r"AUTO-RESEARCH\s+question",
    re.IGNORECASE,
)

# Semantic topic labels per section (stable API for research / logging).
SECTION_TOPIC_LABELS: dict[int, str] = {
    1: "product and service",
    2: "business overview",
    3: "market research",
    4: "location and operations",
    5: "marketing and sales",
    6: "legal and regulatory compliance",
    7: "revenue and financials",
    8: "growth and scaling",
    9: "challenges and contingency planning",
}

# Section-level draft grounding — applies to all questions in the section.
SECTION_DRAFT_GROUNDING: dict[int, str] = {
    1: (
        "Describe concrete products or services that deliver the PRIMARY BUSINESS IDEA. "
        "Do not invent a different business model (e.g. generic consulting) unless the "
        "business idea explicitly describes that model. Never use placeholder phrases "
        "like 'your business'."
    ),
    2: (
        "Stay consistent with the business idea and product/service answers from Section 1. "
        "Use only facts the user has provided."
    ),
    3: (
        "Ground market/customer answers in the business idea and offering from earlier sections."
    ),
    4: (
        "Operational answers must fit the actual product/service and customer model already described."
    ),
    5: (
        "Marketing answers must reflect the real offering and target customer — no generic campaigns."
    ),
    6: (
        "Legal/compliance answers must match industry, location, and structure the user provided."
    ),
    7: (
        "Financial answers may use estimates only when labeled; never invent market statistics."
    ),
    8: (
        "Growth plans must extend the existing venture — not pivot to a new business."
    ),
    9: (
        "Risk and contingency answers must reflect this specific venture's context."
    ),
}

# Sections where web research may augment drafts (not auto-injected research questions).
RESEARCH_FRIENDLY_SECTIONS = frozenset({3, 7})

# Last question number in each BP section (triggers section summary).
SECTION_BOUNDARY_END_NUMBERS = frozenset({4, 7, 13, 17, 23, 28, 34, 41, 45})

# Global anchor: every question after Q01 needs the business idea to draft responsibly.
BUSINESS_IDEA_ANCHOR_TAG = "BUSINESS_PLAN.01"


@dataclass(frozen=True)
class BusinessPlanQuestionMeta:
    tag: str
    number: int
    section_id: int
    section_title: str
    prompt_text: str
    objective: str
    topic_label: str
    auto_research: bool
    draft_prerequisite_tags: tuple[str, ...]
    draft_required_tags: tuple[str, ...]
    draft_grounding: str

    @property
    def is_business_name_question(self) -> bool:
        return self.tag == "BUSINESS_PLAN.05"

    @property
    def is_industry_question(self) -> bool:
        return self.tag == "BUSINESS_PLAN.06"


def normalize_business_plan_tag(tag: str) -> str:
    if not tag:
        return ""
    upper = tag.strip().upper()
    if upper.startswith("BP."):
        return f"BUSINESS_PLAN.{upper[3:]}"
    return upper


def _extract_objective_block(block: str) -> str:
    """Full question text from the prompt block (matches legacy parser behavior)."""
    lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
    return " ".join(lines)


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


def transform_question_objective(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if not text:
        return text
    sentences = re.split(r"(?<=[.?!])\s+", text)
    transformed: list[str] = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if sentence.endswith("?"):
            transformed.append(convert_question_to_objective(sentence[:-1].strip()))
        else:
            transformed.append(sentence)
    return " ".join(transformed).strip()


@lru_cache(maxsize=1)
def _get_business_plan_questionnaire_text() -> str:
    """Slice of ANGEL_SYSTEM_PROMPT containing only the 45-question questionnaire."""
    start = ANGEL_SYSTEM_PROMPT.find(QUESTIONNAIRE_START_MARKER)
    end = ANGEL_SYSTEM_PROMPT.find(QUESTIONNAIRE_END_MARKER)
    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            "Business Plan questionnaire boundaries not found in ANGEL_SYSTEM_PROMPT"
        )
    return ANGEL_SYSTEM_PROMPT[start:end]


@lru_cache(maxsize=1)
def load_business_plan_registry() -> dict[str, BusinessPlanQuestionMeta]:
    """Build tag → metadata index from the canonical questionnaire section only."""
    questionnaire = _get_business_plan_questionnaire_text()

    section_spans: list[tuple[int, str, int, int]] = []
    for match in SECTION_PATTERN.finditer(questionnaire):
        section_id = int(match.group(1))
        section_title = match.group(2).strip()
        section_spans.append((section_id, section_title, match.start(), match.end()))

    def section_for_position(pos: int) -> tuple[int, str]:
        active = (1, "PRODUCT/SERVICE DETAILS")
        for section_id, title, start, _end in section_spans:
            if pos >= start:
                active = (section_id, title)
        return active

    raw_entries: list[tuple[str, int, int, str, str, str, bool]] = []
    for match in QUESTION_BLOCK_PATTERN.finditer(questionnaire):
        tag = normalize_business_plan_tag(match.group(1))
        number = int(tag.split(".")[-1])
        block = match.group(2)
        section_id, section_title = section_for_position(match.start())
        prompt_text = _extract_objective_block(block)
        objective = transform_question_objective(prompt_text)
        auto_research = bool(AUTO_RESEARCH_NOTE.search(block))
        raw_entries.append(
            (tag, number, section_id, section_title, prompt_text, objective, auto_research)
        )

    raw_entries.sort(key=lambda item: item[1])

    all_tags_by_number = [tag for tag, number, *_ in raw_entries]

    registry: dict[str, BusinessPlanQuestionMeta] = {}
    for tag, number, section_id, section_title, prompt_text, objective, auto_research in raw_entries:
        prior_tags = [t for t in all_tags_by_number if int(t.split(".")[-1]) < number]
        ordered_prereq = tuple(prior_tags)

        required: tuple[str, ...] = ()
        if number > 1:
            required = (BUSINESS_IDEA_ANCHOR_TAG,)

        topic_label = SECTION_TOPIC_LABELS.get(section_id, "business planning")
        grounding = SECTION_DRAFT_GROUNDING.get(section_id, "")

        registry[tag] = BusinessPlanQuestionMeta(
            tag=tag,
            number=number,
            section_id=section_id,
            section_title=section_title,
            prompt_text=prompt_text,
            objective=objective,
            topic_label=topic_label,
            auto_research=auto_research,
            draft_prerequisite_tags=ordered_prereq,
            draft_required_tags=required,
            draft_grounding=grounding,
        )

    return registry


def get_question_meta(tag: str) -> Optional[BusinessPlanQuestionMeta]:
    if not tag:
        return None
    return load_business_plan_registry().get(normalize_business_plan_tag(tag))


def get_question_topic(*, asked_q: str = "") -> str:
    """Resolve semantic topic from questionnaire tag — not from question text."""
    meta = get_question_meta(asked_q)
    if meta:
        return meta.topic_label
    return "business planning"


@lru_cache(maxsize=1)
def load_business_plan_question_objectives() -> dict[str, str]:
    """Canonical transformed objectives for all Business Plan questions."""
    return {tag: meta.objective for tag, meta in load_business_plan_registry().items()}


def get_question_objective(tag: str) -> Optional[str]:
    """Return the canonical objective text for a Business Plan question tag."""
    meta = get_question_meta(tag)
    return meta.objective if meta else None


def format_section_display_name(section_title: str) -> str:
    """Human-readable section label from prompt header (e.g. BUSINESS OVERVIEW)."""
    title = (section_title or "").strip()
    if not title:
        return "Business Plan Section"
    return title.title()


def get_section_boundary_info(question_num: int) -> Optional[dict[str, Any]]:
    """Return section summary trigger metadata when question_num ends a section."""
    if question_num not in SECTION_BOUNDARY_END_NUMBERS:
        return None
    tag = f"BUSINESS_PLAN.{question_num:02d}"
    meta = get_question_meta(tag)
    if not meta:
        return None
    display = format_section_display_name(meta.section_title)
    return {
        "trigger_question": question_num,
        "section_id": meta.section_id,
        "section_name": display,
        "section_title": meta.section_title,
    }


def get_question_tags_for_section(section_id: int) -> tuple[str, ...]:
    """All questionnaire tags in a section, in order."""
    registry = load_business_plan_registry()
    tags = sorted(
        (m.tag for m in registry.values() if m.section_id == section_id),
        key=lambda t: int(t.split(".")[-1]),
    )
    return tuple(tags)


def should_use_web_research_for_draft(tag: str) -> bool:
    meta = get_question_meta(tag)
    if not meta or meta.auto_research:
        return False
    return meta.section_id in RESEARCH_FRIENDLY_SECTIONS


def collect_draft_prerequisite_answers(
    history,
    asked_q: str,
    *,
    get_answer_for_tag,
) -> dict[str, str]:
    """Return {tag: answer} for prerequisite questions that have substantive answers."""
    meta = get_question_meta(asked_q)
    if not meta:
        return {}
    answers: dict[str, str] = {}
    for prereq_tag in meta.draft_prerequisite_tags:
        answer = get_answer_for_tag(history, prereq_tag)
        if answer:
            answers[prereq_tag] = answer
    return answers


def validate_draft_prerequisites(
    history,
    asked_q: str,
    *,
    get_answer_for_tag,
    business_context: dict | None = None,
) -> list[str]:
    """
    Return human-readable missing requirements (empty list = OK to draft).
    Uses registry required tags + business_context fields when applicable.
    """
    from utils.business_context import is_meaningful_context_value

    meta = get_question_meta(asked_q)
    if not meta:
        return []

    missing: list[str] = []
    ctx = business_context or {}

    for req_tag in meta.draft_required_tags:
        if req_tag == BUSINESS_IDEA_ANCHOR_TAG and is_meaningful_context_value(
            ctx.get("business_idea")
        ):
            continue
        answer = get_answer_for_tag(history, req_tag)
        if not answer:
            objective = get_question_objective(req_tag) or req_tag
            missing.append(f"Question {int(req_tag.split('.')[-1])}: {objective}")

    return missing
