import json
import boto3

bedrock = boto3.client("bedrock-runtime")
lambda_client = boto3.client("lambda")

from tools_config import TOOL_CONFIG

MODEL_ID = "us.amazon.nova-lite-v1:0"
MAX_ITERATIONS = 5

# Maps the tool name (from toolConfig) to the deployed Lambda function name.
TOOL_TO_LAMBDA = {
    "simulate_match": "simulate-match",
    "get_schedule_and_standings": "schedule-standings",
    "search_team_news": "news-search",
    "manage_memory": "memory",
}

SYSTEM_PROMPT = [{
    "text": (
        "You are a knowledgeable, friendly World Cup 2026 companion. You help users with "
        "match predictions, schedules, standings, team news, and you remember their "
        "preferences.\n\n"
        "Tool usage:\n"
        "- Use simulate_match for predictions and win probabilities.\n"
        "- Use get_schedule_and_standings for factual schedule, results, and standings.\n"
        "- Use search_team_news for current real-world news (injuries, form, lineups).\n"
        "- Use manage_memory to retrieve user preferences at the start and save new ones.\n\n"
        "Be transparent about limitations: when you cite a prediction, mention it comes from "
        "a statistical model that does not account for injuries or current form unless you "
        "also checked the news. When you cite news, mention your sources. Never frame "
        "predictions as betting advice — present probabilities as informational only."
    )
}]

def invoke_tool(tool_name, tool_input, session_id):
    """Invoke the Lambda backing a tool and return its parsed result."""
    function_name = TOOL_TO_LAMBDA.get(tool_name)
    if function_name is None:
        return {"error": f"Unknown tool: {tool_name}"}

    # The session_id comes from the browser, not the model — inject it for memory.
    if tool_name == "manage_memory":
        tool_input = {**tool_input, "session_id": session_id}

    response = lambda_client.invoke(
        FunctionName=function_name,
        Payload=json.dumps(tool_input).encode("utf-8"),
    )
    result = json.loads(response["Payload"].read().decode("utf-8"))
    return result

def run_agent(user_message, session_id):
    """The agentic loop: call Nova, dispatch any tool requests, feed results back,
    repeat until Nova returns a final text answer (or we hit the iteration cap)."""

    # Conversation starts with the user's message.
    messages = [{"role": "user", "content": [{"text": user_message}]}]
    trace = []  # records tool calls for observability

    for _ in range(MAX_ITERATIONS):
        response = bedrock.converse(
            modelId=MODEL_ID,
            system=SYSTEM_PROMPT,
            messages=messages,
            toolConfig=TOOL_CONFIG,
        )

        output_message = response["output"]["message"]
        messages.append(output_message)  # add the model's turn to the conversation

        stop_reason = response["stopReason"]

        # If the model is NOT asking for a tool, it has given its final answer.
        if stop_reason != "tool_use":
            final_text = "".join(
                block["text"] for block in output_message["content"] if "text" in block
            )
            return {"answer": final_text, "trace": trace}

        # Otherwise, handle every tool the model requested this turn.
        tool_results = []
        for block in output_message["content"]:
            if "toolUse" not in block:
                continue
            tool_use = block["toolUse"]
            tool_name = tool_use["name"]
            tool_input = tool_use["input"]

            result = invoke_tool(tool_name, tool_input, session_id)
            trace.append({"tool": tool_name, "input": tool_input, "output": result})

            tool_results.append({
                "toolResult": {
                    "toolUseId": tool_use["toolUseId"],
                    "content": [{"json": result}],
                }
            })

        # Feed all tool results back as a user turn, then loop.
        messages.append({"role": "user", "content": tool_results})

    # Safety: ran out of iterations without a final answer.
    return {"answer": "I wasn't able to complete that request.", "trace": trace}

def lambda_handler(event, context):
    """Entry point. Accepts a user message and session_id, runs the agent."""
    # When called via API Gateway, the payload arrives as a JSON string in event["body"].
    if "body" in event:
        body = json.loads(event["body"])
    else:
        body = event  # direct invocation (CLI testing)

    user_message = body.get("message")
    session_id = body.get("session_id", "anonymous")

    if not user_message:
        return _http_response(400, {"error": "message is required"})

    result = run_agent(user_message, session_id)
    return _http_response(200, result)


def _http_response(status_code, body):
    """Wrap a result in the HTTP shape API Gateway expects."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",  # allow the frontend to call this
        },
        "body": json.dumps(body),
    }
