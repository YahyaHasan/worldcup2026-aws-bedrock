import time
import boto3

dynamodb = boto3.resource("dynamodb")
memory_table = dynamodb.Table("SessionMemory")

TTL_SECONDS = 24 * 60 * 60  # sessions auto-expire after 24 hours


def lambda_handler(event, context):
    """Routes to save or retrieve based on the action field."""
    action = event.get("action")
    session_id = event.get("session_id")

    if not session_id:
        return {"error": "session_id is required"}

    if action == "save":
        return save_fact(session_id, event["key"], event["value"])
    elif action == "retrieve":
        return retrieve_facts(session_id)
    else:
        return {"error": f"Unknown action: {action}. Use save or retrieve."}

def retrieve_facts(session_id):
    """Get all stored facts for a session. Returns empty if the session is new."""
    response = memory_table.get_item(Key={"session_id": session_id})
    item = response.get("Item")

    if item is None:
        return {"session_id": session_id, "facts": {}}

    return {"session_id": session_id, "facts": item.get("facts", {})}

def save_fact(session_id, key, value):
    """Store a single key→value fact for a session, preserving existing facts."""
    # Read existing facts (read-modify-write so we don't clobber other facts).
    response = memory_table.get_item(Key={"session_id": session_id})
    item = response.get("Item")
    facts = item.get("facts", {}) if item else {}

    # Modify
    facts[key] = value

    # Write back the whole item with a refreshed expiry.
    expires_at = int(time.time()) + TTL_SECONDS
    memory_table.put_item(Item={
        "session_id": session_id,
        "facts": facts,
        "expires_at": expires_at,
    })

    return {"status": "saved", "session_id": session_id, "facts": facts}
