import json
import logging
import boto3
import re
from langchain_aws import ChatBedrockConverse
from langchain_core.tools import tool
from langchain.agents import create_agent


logger = logging.getLogger()
logger.setLevel(logging.INFO)

lambda_client = boto3.client("lambda")

llm = ChatBedrockConverse(
    model="us.amazon.nova-lite-v1:0",
    region_name="us-east-1",
)

TOOL_TO_LAMBDA = {
    "simulate_match": "simulate-match",
    "get_schedule_and_standings": "schedule-standings",
    "search_team_news": "news-search",
    "manage_memory": "memory",
}

def clean_answer(text):
    """Strip leaked internal-reasoning tags before returning to the user."""
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
    text = re.sub(r"</?thinking>", "", text)
    return text.strip()

def _invoke_lambda(function_name, payload):
    response = lambda_client.invoke(
        FunctionName=function_name,
        Payload=json.dumps(payload).encode("utf-8"),
    )
    raw = response["Payload"].read().decode("utf-8")
    # Surface Lambda-level failures (FunctionError) instead of silently returning null.
    if response.get("FunctionError"):
        logger.error(f"Tool {function_name} failed: {raw}")
        return {"error": f"Tool {function_name} failed", "detail": raw[:500]}
    result = json.loads(raw)
    if result is None:
        logger.error(f"Tool {function_name} returned null. payload={payload}")
        return {"error": f"Tool {function_name} returned no data"}
    return result

@tool
def simulate_match(team_a: str, team_b: str, a_is_home: bool = False, b_is_home: bool = False) -> dict:
    """Predict the probable outcome of a match using a Poisson/Monte Carlo model. Use for ANY
    question about who would win, win probabilities, or predicted scorelines, including
    hypothetical matchups. Do NOT use for factual past results. team_a/team_b are FIFA IDs
    (BRA, MAR). Set a_is_home/b_is_home True only for a co-host playing in its own country."""
    return _invoke_lambda("simulate-match", {
        "team_a": team_a, "team_b": team_b, "a_is_home": a_is_home, "b_is_home": b_is_home,
    })


@tool
def get_schedule_and_standings(query_type: str, team_id: str = "", group_id: str = "", match_id: str = "") -> dict:
    """Look up FACTUAL tournament data: a team's schedule, group standings, or a match result.
    Do NOT use for predictions. query_type is one of: team_schedule, group_standings,
    match_result. Provide team_id, group_id (A-L), or match_id (M001) as appropriate."""
    payload = {"query_type": query_type}
    if team_id: payload["team_id"] = team_id
    if group_id: payload["group_id"] = group_id
    if match_id: payload["match_id"] = match_id
    return _invoke_lambda("schedule-standings", payload)

@tool
def search_team_news(team_name: str, topic_hint: str = "") -> str:
    """Get CURRENT real-world news about a team: injuries, form, lineups, suspensions. Use ONLY
    when the user explicitly asks about news or a team's present-day situation. team_name is the
    full name (e.g. Morocco). ALWAYS set topic_hint to the specific aspect the user asked about
    (e.g. topic_hint='injury' for injury questions, 'lineup' for lineup questions) — this
    sharply improves results. Without it the search returns only generic team info."""
    result = _invoke_lambda("news-search", {"team_name": team_name, "topic_hint": topic_hint})
    return json.dumps(result)



def make_memory_tool(session_id):
    """Build a memory tool with the request's session_id bound in (closure), since the model
    must not supply the session and the executor owns dispatch."""
    @tool
    def manage_memory(action: str, key: str = "", value: str = "") -> dict:
        """Save or retrieve user preferences. action='retrieve' to load, action='save' when the
        user states a preference. Use snake_case keys like favorite_team."""
        payload = {"action": action, "session_id": session_id}
        if key: payload["key"] = key
        if value: payload["value"] = value
        return _invoke_lambda("memory", payload)
    return manage_memory

SYSTEM_PROMPT = (
    "You are a knowledgeable, friendly World Cup 2026 companion. Help with predictions, "
    "schedules, standings, team news, and remember user preferences.\n"
    "- Use simulate_match for predictions; ALWAYS state the resulting win probabilities and "
    "most likely score in your answer.\n"
    "- Use get_schedule_and_standings for factual schedule/results/standings.\n"
    "- Use search_team_news ONLY when the user explicitly asks about news/injuries/form, and "
    "pass topic_hint matching what they asked (e.g. 'injury').\n"
    "- Use manage_memory to retrieve preferences at the start and save new ones.\n"
    "- Only fetch what the question needs. Cite news sources; note predictions come from a "
    "statistical model that ignores injuries and form. Never output internal reasoning."
)

def build_agent(session_id):
    """Build an agent for one request, with session-bound memory."""
    tools = [simulate_match, get_schedule_and_standings, search_team_news,
             make_memory_tool(session_id)]
    return create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT)

def lambda_handler(event, context):
    body = json.loads(event["body"]) if "body" in event else event
    user_message = body.get("message")
    session_id = body.get("session_id", "anonymous")

    if not user_message:
        return _http_response(400, {"error": "message is required"})

    agent = build_agent(session_id)
    result = agent.invoke({"messages": [{"role": "user", "content": user_message}]})

    # The final answer is the last message; reconstruct the trace from tool messages.
    messages = result["messages"]
    answer = clean_answer(messages[-1].content)
    trace = _extract_trace(messages)

    logger.info(json.dumps({
        "event": "agent_request_complete",
        "session_id": session_id,
        "user_message": user_message,
        "tools_used": [t["tool"] for t in trace],
        "trace": trace,
    }, default=str))

    return _http_response(200, {"answer": answer, "trace": trace})

def _extract_trace(messages):
    """Pull tool calls and their results out of the agent's message list."""
    trace = []
    pending = {}  # tool_call_id -> {tool, input}
    for m in messages:
        for tc in getattr(m, "tool_calls", None) or []:
            pending[tc["id"]] = {"tool": tc["name"], "input": tc["args"]}
        tcid = getattr(m, "tool_call_id", None)
        if tcid and tcid in pending:
            entry = pending.pop(tcid)
            entry["output"] = m.content
            trace.append(entry)
    return trace

def _http_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body, default=str),
    }
