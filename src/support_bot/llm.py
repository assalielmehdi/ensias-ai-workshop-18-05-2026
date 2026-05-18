"""LLM factory.

Two responsibilities:
1. Hand back a chat model object (real or mock) based on `settings.llm_mode`.
2. Provide a deterministic mock that's good enough to drive both the workflow
   and the agent end-to-end without an API key.

The real client is `langchain_openai.ChatOpenAI` pointed at an OpenAI-compatible
base URL, which works for OpenRouter, OpenAI itself, and most local servers
(Ollama via LiteLLM, vLLM, etc.).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from typing import Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from pydantic import Field, SecretStr

from .config import settings


def _as_text(content: object) -> str:
    """Coerce a LangChain message `content` (str | list[...] | None) to str.

    LangChain types `BaseMessage.content` as a union to support multi-modal
    payloads; for our purposes it's always plain text, so we normalize once
    here instead of guarding at every call site.
    """

    if isinstance(content, str):
        return content
    if content is None:
        return ""
    return str(content)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Real LLM
# ---------------------------------------------------------------------------


def _real_chat_model() -> BaseChatModel:
    """Build a ChatOpenAI client pointed at the configured base URL."""

    from langchain_openai import ChatOpenAI

    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is empty. Set it in .env or switch LLM_MODE=mock.")
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=SecretStr(settings.llm_api_key),
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
    )


# ---------------------------------------------------------------------------
# Mock LLM — deterministic, no network
# ---------------------------------------------------------------------------


class MockChatModel(BaseChatModel):
    """A tiny deterministic chat model.

    It inspects the last system + human message and produces:
    - JSON classifications for the workflow classifier prompt.
    - JSON safety verdicts for the safety prompt.
    - Short text drafts for the drafter prompt.
    - Tool-calling messages or final JSON answers for the agent prompt.

    Behaviour is rules-based and intentionally simple — the goal is to keep the
    workshop runnable offline, not to be smart.
    """

    bound_tools: list[BaseTool] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "mock"

    # LangChain calls this for non-streaming generation.
    def _generate(  # type: ignore[override]
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        system = next((m for m in messages if isinstance(m, SystemMessage)), None)
        last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        system_text = _as_text(system.content) if system else ""
        human_text = _as_text(last_human.content) if last_human else ""

        reply = self._route(system_text, human_text, messages)
        return ChatResult(generations=[ChatGeneration(message=reply)])

    # LangChain's BaseChatModel.bind_tools uses a broader Sequence/Callable
    # union that's painful to mirror exactly; the override works at runtime.
    def bind_tools(  # type: ignore[override]  # ty: ignore[invalid-method-override]
        self, tools: Iterable[BaseTool], **kwargs: Any
    ) -> BaseChatModel:
        new = MockChatModel()
        new.bound_tools = list(tools)
        return new

    # --- routing -----------------------------------------------------------

    def _route(self, system: str, human: str, history: list[BaseMessage]) -> AIMessage:
        s = system.lower()
        if "classifier" in s:
            return AIMessage(content=json.dumps(_mock_classify(human)))
        if "safety reviewer" in s:
            # We need the original customer message too — look back in history.
            customer = _first_human(history)
            return AIMessage(content=json.dumps(_mock_safety(customer, human)))
        if "draft" in s or "friendly customer support agent" in s:
            return AIMessage(content=_mock_draft(human))
        if "customer support assistant" in s:
            return self._mock_agent_step(human, history)
        # Fallback: echo.
        return AIMessage(content="I am a mock LLM; I would respond here.")

    def _mock_agent_step(self, human: str, history: list[BaseMessage]) -> AIMessage:
        """Drive the agent loop with hand-coded rules.

        Each turn we look at:
        - the original customer message (first HumanMessage),
        - which tools we have already called (from ToolMessage history),
        and decide on the next tool call OR the final answer.
        """

        from langchain_core.messages import ToolMessage

        original = _first_human(history)
        used: list[str] = [
            m.name for m in history if isinstance(m, ToolMessage) and m.name is not None
        ]
        original_text = _as_text(original.content) if original else human
        text = original_text.lower()

        # Step 1: legal/threat → escalate immediately.
        if any(k in text for k in ("legal", "lawyer", "sue", "lawsuit", "attorney")):
            if "escalate_to_human" not in used:
                return _tool_call(
                    "escalate_to_human",
                    {"reason": "legal threat from customer"},
                )
            return _final_answer(
                category="escalation_required",
                urgency="high",
                customer_response=(
                    "I'm sorry for the frustration. Because of the seriousness of "
                    "what you've described, a human teammate from our team will "
                    "follow up with you within one business day."
                ),
                needs_human=True,
                reasoning_summary="Escalated due to legal-action language.",
            )

        # Step 2: duplicate-charge → escalate.
        if "charged twice" in text or "duplicate charge" in text:
            if "escalate_to_human" not in used:
                return _tool_call(
                    "escalate_to_human",
                    {"reason": "duplicate charge requires billing review"},
                )
            return _final_answer(
                category="billing_issue",
                urgency="high",
                customer_response=(
                    "Thank you for flagging this. Duplicate charges have to be "
                    "reviewed by our billing team; a teammate will reach out shortly."
                ),
                needs_human=True,
                reasoning_summary="Escalated duplicate-charge billing issue.",
            )

        # Step 3: order-ID present → check it first.
        order_id = _extract_order_id(original_text)
        if order_id and "check_order_status" not in used:
            return _tool_call("check_order_status", {"order_id": order_id})

        # Step 4: refund language → look up policy.
        if (
            "refund" in text or "broken" in text or "damaged" in text
        ) and "check_refund_policy" not in used:
            return _tool_call(
                "check_refund_policy",
                {"product_type": "electronics", "days_since_purchase": 7},
            )

        # Step 5: missing-info delivery → ask the customer.
        if (
            ("never arrived" in text or "package" in text)
            and not order_id
            and "search_knowledge_base" not in used
        ):
            return _tool_call("search_knowledge_base", {"query": "delivered but not received"})

        # Otherwise: finalize.
        return _final_answer_from_history(original_text, used)


def _extract_order_id(text: str) -> Optional[str]:
    m = re.search(r"ORD-\d{3,}", text, flags=re.IGNORECASE)
    return m.group(0).upper() if m else None


def _first_human(history: list[BaseMessage]) -> Optional[HumanMessage]:
    return next((m for m in history if isinstance(m, HumanMessage)), None)


def _tool_call(name: str, args: dict[str, Any]) -> AIMessage:
    """Build an AIMessage that LangGraph will interpret as a tool call."""

    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": f"call_{name}"}],
    )


def _final_answer(
    *,
    category: str,
    urgency: str,
    customer_response: str,
    needs_human: bool,
    reasoning_summary: str,
) -> AIMessage:
    payload = {
        "category": category,
        "urgency": urgency,
        "customer_response": customer_response,
        "needs_human": needs_human,
        "reasoning_summary": reasoning_summary,
    }
    return AIMessage(content=json.dumps(payload))


def _final_answer_from_history(text: str, used_tools: list[str]) -> AIMessage:
    t = text.lower()
    if "never arrived" in t or "package" in t:
        return _final_answer(
            category="delivery_issue",
            urgency="medium",
            customer_response=(
                "I'm sorry your package hasn't arrived. To investigate, could you "
                "share the order ID and the email used at checkout? Once I have "
                "those I'll pull the latest tracking and next steps."
            ),
            needs_human=False,
            reasoning_summary="Asked for missing order ID; no tools could resolve without it.",
        )
    if "refund" in t or "broken" in t or "damaged" in t:
        return _final_answer(
            category="refund_request",
            urgency="medium",
            customer_response=(
                "Thanks for letting us know. Damaged-on-arrival items are eligible "
                "for return regardless of category. A teammate will confirm the "
                "refund and email you a prepaid return label."
            ),
            needs_human=True,
            reasoning_summary="Damaged item: eligible per policy, refund needs human approval.",
        )
    return _final_answer(
        category="general_question",
        urgency="low",
        customer_response=(
            "Thanks for reaching out! Could you share a bit more about what you'd "
            "like help with — an order ID, or the specific question you have?"
        ),
        needs_human=False,
        reasoning_summary="No clear intent; asked for clarification.",
    )


# Workflow mocks -----------------------------------------------------------


def _mock_classify(text: str) -> dict[str, str]:
    t = text.lower()
    if any(k in t for k in ("legal", "lawyer", "sue", "lawsuit", "attorney", "furious")):
        return {"category": "escalation_required", "urgency": "high"}
    if "charged twice" in t or "duplicate" in t or "billing" in t:
        return {"category": "billing_issue", "urgency": "high"}
    if "refund" in t or "broken" in t or "damaged" in t:
        return {"category": "refund_request", "urgency": "medium"}
    if "package" in t or "arrived" in t or "delivery" in t or "shipping" in t:
        return {"category": "delivery_issue", "urgency": "medium"}
    if "pair" in t or "reset" in t or "not working" in t:
        return {"category": "technical_issue", "urgency": "low"}
    return {"category": "general_question", "urgency": "low"}


def _mock_safety(customer: Optional[HumanMessage], _draft: str) -> dict[str, Any]:
    raw = customer.content if customer else ""
    text = (raw if isinstance(raw, str) else "").lower()
    risky = [
        "legal",
        "lawyer",
        "sue",
        "lawsuit",
        "attorney",
        "court",
        "charged twice",
        "duplicate charge",
        "manager",
        "supervisor",
    ]
    for kw in risky:
        if kw in text:
            return {"needs_human": True, "reason": f"matched: {kw}"}
    return {"needs_human": False, "reason": ""}


def _mock_draft(prompt_text: str) -> str:
    """Mock drafter — uses the structured context we feed it.

    The drafter node passes context (KB snippets, order info) as the human
    message. We just produce a short, generic-but-plausible reply.
    """

    t = prompt_text.lower()
    if "order " in t and "delivered" in t:
        return (
            "Thanks for reaching out — I've pulled up your order. If the item "
            "arrived damaged, you're covered: I'll have a teammate confirm the "
            "refund and send you a return label by email."
        )
    if "refund" in t:
        return (
            "I'm sorry to hear about the issue. Based on our policy, this looks "
            "eligible for a return. A teammate will confirm and email you the "
            "next steps shortly."
        )
    if "package" in t or "delivery" in t:
        return (
            "I'm sorry your package hasn't arrived. Could you share the order ID "
            "and the email on the order? Once I have those I can pull the latest "
            "tracking and decide next steps."
        )
    return (
        "Thanks for reaching out! Could you tell me a bit more so I can help — "
        "an order ID or the specific question you have would be perfect."
    )


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def get_chat_model() -> BaseChatModel:
    """Return a chat model based on the current settings."""

    if settings.llm_mode == "mock":
        logger.info("Using mock LLM (LLM_MODE=mock).")
        return MockChatModel()
    logger.info(
        "Using %s LLM model=%s base_url=%s",
        settings.llm_mode,
        settings.llm_model,
        settings.llm_base_url,
    )
    return _real_chat_model()
