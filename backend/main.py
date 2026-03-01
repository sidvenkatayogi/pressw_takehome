import json
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from starlette.responses import StreamingResponse

from config import LOG_LEVEL
from graphs.cooking_graph import cooking_graph
from schemas.requests import ChatRequest
from schemas.responses import ChatResponse, DebugInfo

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="[%(asctime)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Cooking & Recipe Q&A", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GRAPH_NODES = (
    "classify_query",
    "research_agent",
    "cookware_check",
    "generate_response",
    "refuse_response",
)


def build_langchain_messages(messages):
    """Convert request messages to LangChain message objects."""
    lc_messages = []
    for msg in messages:
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        else:
            lc_messages.append(AIMessage(content=msg.content))
    return lc_messages


def sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def build_initial_state(messages):
    return {
        "messages": build_langchain_messages(messages),
        "classification": None,
        "research_result": None,
        "tools_used": [],
        "cookware_check_result": None,
        "final_response": None,
        "debug_info": [],
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/chat/sync", response_model=ChatResponse)
async def chat_sync(request: ChatRequest):
    """Non-streaming chat endpoint."""
    logger.info(
        "[chat_sync] Processing %d messages",
        len(request.messages),
    )

    try:
        result = await cooking_graph.ainvoke(build_initial_state(request.messages))

        classification = result.get("classification")
        cookware_result = result.get("cookware_check_result")
        query_type = classification.category if classification else "unknown"

        debug = None
        if request.debug:
            debug = DebugInfo(
                classification_reasoning=(
                    classification.reasoning if classification else ""
                ),
                nodes_visited=result.get("debug_info", []),
                tool_calls=[{"tool": t} for t in result.get("tools_used", [])],
                cookware_analysis=(
                    cookware_result.analysis if cookware_result else None
                ),
            )

        return ChatResponse(
            answer=result.get(
                "final_response",
                "Sorry, I couldn't process that.",
            ),
            query_type=query_type,
            tools_used=result.get("tools_used", []),
            cookware_sufficient=(
                cookware_result.cookware_sufficient if cookware_result else None
            ),
            missing_cookware=(
                cookware_result.missing_cookware if cookware_result else []
            ),
            debug=debug,
        )

    except Exception as e:
        logger.error("[chat_sync] Error: %s", e, exc_info=True)
        return ChatResponse(
            answer=f"Sorry, something went wrong: {e}",
            query_type="error",
        )


@app.post("/api/chat")
async def chat_stream(request: ChatRequest):
    """Streaming SSE chat endpoint using astream_events."""
    logger.info(
        "[chat_stream] Processing %d messages",
        len(request.messages),
    )

    async def event_generator():
        try:
            final_response = ""
            tools_used = []
            query_type = "unknown"
            cookware_sufficient = None
            missing_cookware = []

            async for event in cooking_graph.astream_events(
                build_initial_state(request.messages),
                version="v2",
            ):
                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chain_start" and name in GRAPH_NODES:
                    yield sse({"type": "node_start", "node": name})

                elif kind == "on_chain_end" and name in GRAPH_NODES:
                    output = event.get("data", {}).get("output", {})
                    if name == "classify_query" and output.get("classification"):
                        cls = output["classification"]
                        query_type = cls.category
                        yield sse(
                            {
                                "type": "node_end",
                                "node": name,
                                "result": cls.category,
                            }
                        )
                    elif name == "cookware_check" and output.get(
                        "cookware_check_result"
                    ):
                        ck = output["cookware_check_result"]
                        cookware_sufficient = ck.cookware_sufficient
                        missing_cookware = ck.missing_cookware
                        sufficient = ck.cookware_sufficient
                        yield sse(
                            {
                                "type": "node_end",
                                "node": name,
                                "result": (
                                    "sufficient" if sufficient else "insufficient"
                                ),
                            }
                        )
                    else:
                        yield sse(
                            {
                                "type": "node_end",
                                "node": name,
                            }
                        )

                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        parent = event.get("metadata", {}).get("langgraph_node", "")
                        if parent in (
                            "generate_response",
                            "refuse_response",
                        ):
                            final_response += chunk.content
                            yield sse(
                                {
                                    "type": "token",
                                    "content": chunk.content,
                                }
                            )

                elif kind == "on_tool_start":
                    tool_input = event.get("data", {}).get("input", "")
                    tools_used.append(name)
                    yield sse(
                        {
                            "type": "tool_call",
                            "tool": name,
                            "query": str(tool_input)[:200],
                        }
                    )

            yield sse(
                {
                    "type": "done",
                    "metadata": {
                        "query_type": query_type,
                        "tools_used": tools_used,
                        "cookware_sufficient": cookware_sufficient,
                        "missing_cookware": missing_cookware,
                    },
                }
            )

        except Exception as e:
            logger.error("[chat_stream] Error: %s", e, exc_info=True)
            yield sse({"type": "error", "message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
