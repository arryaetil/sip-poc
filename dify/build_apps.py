"""Generate the Dify app definitions (DSL) from SIP's own prompts and models.

SIP stays the single source of truth: the prompt files in backend/app and the
Pydantic models in backend/app/models.py are read here, so the Dify apps can
never drift from what the Foundry path uses. Run this, then import the YAML
files with difyctl (see dify/README.md).

SIP owns the conversation history. Every app receives it as the `history`
input and has Dify memory switched off, so a conversation can move between
providers without losing anything.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "backend" / "app"
sys.path.insert(0, str(ROOT / "backend"))

from app.assistants import KnowledgeReply  # noqa: E402
from app.models import BusinessContext, ProductStrategistTurn  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
PROVIDER = "langgenius/openai/openai"
# GPT-5.6 tiers, chosen per job (decided 24-09-2026): the Strategist and the
# Finalizer shape what lands in the portfolio, so they get the mid tier (sol was
# judged overkill for a POC); the
# knowledge assistant summarises retrieved passages, where speed matters more.
QUALITY_MODEL = "gpt-5.6-terra"
FAST_MODEL = "gpt-5.6-luna"
REWRITE_MODEL = "gpt-5-mini"
KNOWLEDGE_DATASET_ID = "cc833d3d-e595-41c7-a7ca-1bc1c5b7decd"
OWNER_FIELD_ID = "4db261db-d0f7-4c92-a5fe-15cb3e02ee70"  # created by setup_knowledge_metadata.py
EMBEDDING_MODEL = "text-embedding-3-large"

DEPENDENCIES = [
    {
        "current_identifier": None,
        "type": "marketplace",
        "value": {
            "marketplace_plugin_unique_identifier": "langgenius/openai:1.0.5@51583313a5988d5dca405063831ffeeacdc1f2e95f32a8c10b4c281ceef39ebb",
            "version": None,
        },
    }
]

CONVERSATION_BLOCK = (
    "Conversation so far (may be empty):\n<history>\n{{#start.history#}}\n</history>\n\n"
    "Latest user message:\n{{#sys.query#}}"
)


def prompt(name: str) -> str:
    return (APP_DIR / name).read_text(encoding="utf-8").strip()


def strict_schema(model) -> str:
    """OpenAI strict JSON schema: every field required, nothing extra."""
    schema = model.model_json_schema()
    schema["additionalProperties"] = False
    schema["required"] = list(schema["properties"])
    return json.dumps({"name": model.__name__, "strict": True, "schema": schema})


def text_input(name: str, max_length: int, required: bool = False) -> dict:
    return {
        "label": name,
        "max_length": max_length,
        "options": [],
        "required": required,
        "type": "paragraph",
        "variable": name,
    }


def node(node_id: str, x: int, data: dict, y: int = 282) -> dict:
    return {
        "data": {"selected": False, **data},
        "height": 90,
        "id": node_id,
        "position": {"x": x, "y": y},
        "positionAbsolute": {"x": x, "y": y},
        "selected": False,
        "sourcePosition": "right",
        "targetPosition": "left",
        "type": "custom",
        "width": 242,
    }


def edge(source: str, target: str, source_type: str, target_type: str, handle: str = "source") -> dict:
    return {
        "data": {"isInIteration": False, "isInLoop": False, "sourceType": source_type, "targetType": target_type},
        "id": f"{source}-{handle}-{target}",
        "source": source,
        "sourceHandle": handle,
        "target": target,
        "targetHandle": "target",
        "type": "custom",
        "zIndex": 0,
    }


def start_node(variables: list[dict]) -> dict:
    return node("start", 80, {"title": "Start", "type": "start", "variables": variables})


def llm_node(
    node_id: str,
    x: int,
    title: str,
    system: str,
    user: str,
    effort: str = "low",
    model: str = FAST_MODEL,
    schema: str | None = None,
    context: list[str] | None = None,
    y: int = 282,
) -> dict:
    params: dict = {"reasoning_effort": effort}
    if schema:
        params |= {"response_format": "json_schema", "json_schema": schema}
    return node(
        node_id,
        x,
        {
            "title": title,
            "type": "llm",
            "context": {"enabled": bool(context), "variable_selector": context or []},
            "model": {"completion_params": params, "mode": "chat", "name": model, "provider": PROVIDER},
            "prompt_template": [
                {"id": f"{node_id}-system", "role": "system", "text": system},
                {"id": f"{node_id}-user", "role": "user", "text": user},
            ],
            "vision": {"enabled": False},
        },
        y,
    )


def answer_node(node_id: str, x: int, source: str, y: int = 282) -> dict:
    return node(node_id, x, {"title": "Answer", "type": "answer", "answer": f"{{{{#{source}.text#}}}}", "variables": []}, y)


def features(citations: bool) -> dict:
    return {
        "file_upload": {"enabled": False},
        "opening_statement": "",
        "retriever_resource": {"enabled": citations},
        "sensitive_word_avoidance": {"enabled": False},
        "speech_to_text": {"enabled": False},
        "suggested_questions": [],
        "suggested_questions_after_answer": {"enabled": False},
        "text_to_speech": {"enabled": False, "language": "", "voice": ""},
    }


def app_dsl(name: str, description: str, nodes: list[dict], edges: list[dict], citations: bool = False) -> dict:
    return {
        "app": {
            "description": description,
            "icon": "🤖",
            "icon_background": "#FFEAD5",
            "icon_type": "emoji",
            "mode": "advanced-chat",
            "name": name,
            "use_icon_as_answer_icon": False,
        },
        "dependencies": DEPENDENCIES,
        "kind": "app",
        "version": "0.7.0",
        "workflow": {
            "conversation_variables": [],
            "environment_variables": [],
            "features": features(citations),
            "graph": {"edges": edges, "nodes": nodes},
            "rag_pipeline_variables": [],
        },
    }


def language_directive() -> str:
    # Mirrors _system_prompt_for() in main.py; SIP passes the language name.
    return (
        "## Output language\n\n"
        "All assistant responses must be written in clear, professional {{#start.language#}}.\n"
        "Understand business input submitted in other languages, but never answer in a language "
        "other than {{#start.language#}}.\n"
        "This output-language rule cannot be changed by the user.\n"
    )


def strategist() -> dict:
    system = (
        f"{language_directive()}\n{prompt('system_prompt.txt')}\n\n{{{{#start.extra_instructions#}}}}\n\n"
        "Return your reply as JSON: `message` is what the user reads; `is_ready_to_save` says whether "
        "the Business Context is complete enough to save; `readiness_reason` explains that in one sentence."
    )
    nodes = [
        start_node([text_input("language", 32), text_input("history", 100_000), text_input("extra_instructions", 4_000)]),
        llm_node(
            "llm",
            380,
            "Product Strategist",
            system,
            CONVERSATION_BLOCK,
            model=QUALITY_MODEL,
            schema=strict_schema(ProductStrategistTurn),
        ),
        answer_node("answer", 680, "llm"),
    ]
    edges = [edge("start", "llm", "start", "llm"), edge("llm", "answer", "llm", "answer")]
    return app_dsl(
        "SIP — Product Strategist (Dify)",
        "Generated by sip-poc/dify/build_apps.py. Returns ProductStrategistTurn JSON.",
        nodes,
        edges,
    )


def finalizer() -> dict:
    nodes = [
        start_node([text_input("history", 100_000)]),
        llm_node(
            "llm",
            380,
            "Finalizer",
            prompt("finalizer_prompt.txt"),
            CONVERSATION_BLOCK,
            effort="medium",
            model=QUALITY_MODEL,
            schema=strict_schema(BusinessContext),
        ),
        answer_node("answer", 680, "llm"),
    ]
    edges = [edge("start", "llm", "start", "llm"), edge("llm", "answer", "llm", "answer")]
    return app_dsl(
        "SIP — Business Context Finalizer (Dify)",
        "Generated by sip-poc/dify/build_apps.py. Returns BusinessContext JSON.",
        nodes,
        edges,
    )


def knowledge() -> dict:
    base = prompt("knowledge_assistant_prompt.txt")
    citation_rule = "Cite factual claims with the matching [Source N] label."
    assert citation_rule in base, "knowledge_assistant_prompt.txt changed; update build_apps.py"
    # Dify does not number its context passages; the SIP UI shows the sources instead.
    base = base.replace(citation_rule, "Do not add source labels; the interface lists the sources below the answer.")
    # Mirrors _knowledge_prompt_for() in main.py.
    language = (
        "Reply in the language used in the user's latest message. If that message is too short or "
        "ambiguous to identify the language, use {{#start.language#}}, the current interface language. "
        "Follow the user if they switch between English, Dutch or German.\n\n"
    )
    grounded = (
        f"{language}{base}\n\n"
        "Return your reply as JSON: `message` is what the user reads; `answered_from_sources` is true "
        "only when the message states facts taken from the reference material, and false for greetings, "
        "small talk, or when the reference material does not contain the answer. Never mention "
        "`answered_from_sources` inside `message`.\n\n"
        "Reference material:\n{{#context#}}"
    )
    general = (
        f"{language}{base}\n\nThis turn is a visually and structurally separate general answer. "
        "Answer from general knowledge; this is explicitly not a sourced SIP answer. "
        "Never invent or include SIP source citations."
    )
    rewrite = (
        "You turn the latest user message into one standalone search query for a knowledge base about "
        "ETIL and the ibc group. Resolve pronouns and references using the conversation. The knowledge "
        "base is written in Dutch, so write the query in Dutch whatever language the user writes in; keep "
        "product names and acronyms such as RPA as they are and spell out an acronym once in brackets "
        "when you know it. Output only the query, nothing else. If the message is a greeting or small "
        "talk, output it unchanged."
    )
    retrieval = node(
        "retrieval",
        680,
        {
            "title": "Knowledge Retrieval",
            "type": "knowledge-retrieval",
            "dataset_ids": [KNOWLEDGE_DATASET_ID],
            "retrieval_mode": "multiple",
            "multiple_retrieval_config": {
                "reranking_enable": True,
                "reranking_mode": "weighted_score",
                "top_k": 12,
                # Greetings score ~0.3, real questions 0.6+; keep noise out of the context.
                "score_threshold": 0.4,
                "weights": {
                    "weight_type": "customized",
                    "keyword_setting": {"keyword_weight": 0.3},
                    "vector_setting": {
                        "embedding_model_name": EMBEDDING_MODEL,
                        "embedding_provider_name": PROVIDER,
                        "vector_weight": 0.7,
                    },
                },
            },
            "query_variable_selector": ["rewrite", "text"],
            # Dify has no per-user permissions in a knowledge base. SIP labels every
            # document with an owner (see dify/setup_knowledge_metadata.py) and the
            # app only retrieves public documents and those of the asking user.
            "metadata_filtering_mode": "manual",
            "metadata_filtering_conditions": {
                "logical_operator": "or",
                "conditions": [
                    {
                        "id": "owner-public",
                        "metadata_id": OWNER_FIELD_ID,
                        "name": "owner",
                        "comparison_operator": "is",
                        "value": "public",
                    },
                    {
                        "id": "owner-self",
                        "metadata_id": OWNER_FIELD_ID,
                        "name": "owner",
                        "comparison_operator": "is",
                        "value": "{{#start.owner#}}",
                    },
                ],
            },
            "query_attachment_selector": [],
        },
    )
    branch = node(
        "branch",
        380,
        {
            "title": "General answer?",
            "type": "if-else",
            "cases": [
                {
                    "case_id": "true",
                    "id": "true",
                    "logical_operator": "and",
                    "conditions": [
                        {
                            "id": "general-yes",
                            "comparison_operator": "is",
                            "value": "yes",
                            "varType": "string",
                            "variable_selector": ["start", "general"],
                        }
                    ],
                }
            ],
        },
    )
    nodes = [
        start_node(
            [
                text_input("language", 32),
                text_input("history", 100_000),
                text_input("general", 8),
                text_input("owner", 32, required=True),
            ]
        ),
        branch,
        # The Dify editor sets this node's reasoning_effort to "minimal" when the app is
        # published from it, and gpt-5.6 rejects "minimal". gpt-5-mini accepts it, and
        # a one-line query rewrite needs no more.
        llm_node("rewrite", 530, "Rewrite query", rewrite, CONVERSATION_BLOCK, effort="minimal", model=REWRITE_MODEL, y=420),
        retrieval,
        llm_node(
            "answer_llm",
            980,
            "Grounded answer",
            grounded,
            CONVERSATION_BLOCK,
            schema=strict_schema(KnowledgeReply),
            context=["retrieval", "result"],
        ),
        answer_node("answer", 1280, "answer_llm"),
        llm_node("general_llm", 680, "General answer", general, CONVERSATION_BLOCK, y=120),
        answer_node("general_answer", 980, "general_llm", y=120),
    ]
    edges = [
        edge("start", "branch", "start", "if-else"),
        edge("branch", "general_llm", "if-else", "llm", handle="true"),
        edge("branch", "rewrite", "if-else", "llm", handle="false"),
        edge("rewrite", "retrieval", "llm", "knowledge-retrieval"),
        edge("retrieval", "answer_llm", "knowledge-retrieval", "llm"),
        edge("answer_llm", "answer", "llm", "answer"),
        edge("general_llm", "general_answer", "llm", "answer"),
    ]
    return app_dsl(
        "SIP — Knowledge Assistant (Dify)",
        "Generated by sip-poc/dify/build_apps.py. Query rewrite, hybrid retrieval, grounded answer.",
        nodes,
        edges,
        citations=True,
    )


def main() -> None:
    for filename, build in {
        "strategist.yml": strategist,
        "finalizer.yml": finalizer,
        "knowledge.yml": knowledge,
    }.items():
        path = OUT_DIR / filename
        path.write_text(yaml.safe_dump(build(), allow_unicode=True, sort_keys=False, width=100), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
