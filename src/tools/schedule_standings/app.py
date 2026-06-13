import boto3
from boto3.dynamodb.conditions import Key, Attr

dynamodb = boto3.resource("dynamodb")
matches_table = dynamodb.Table("Matches")
standings_table = dynamodb.Table("GroupStandings")


def lambda_handler(event, context):
    """Routes to the right query based on query_type."""
    query_type = event.get("query_type")

    if query_type == "group_standings":
        return get_group_standings(event["group_id"])
    elif query_type == "team_schedule":
        return get_team_schedule(event["team_id"])
    elif query_type == "match_result":
        return get_match_result(event["match_id"])
    else:
        return {"error": f"Unknown query_type: {query_type}. "
                         f"Use group_standings, team_schedule, or match_result."}

def get_group_standings(group_id):
    """Query GroupStandings by partition key — returns the group's teams, sorted by points."""
    response = standings_table.query(
        KeyConditionExpression=Key("group_id").eq(group_id)
    )
    rows = response["Items"]

    # DynamoDB returns sort-key order (team_id); re-sort by standings logic.
    rows.sort(key=lambda r: (r["points"], r["goal_diff"], r["goals_for"]), reverse=True)

    return {"group_id": group_id, "standings": rows}

def get_team_schedule(team_id):
    """Find all matches involving a team. Uses a scan with filter because team_a/team_b
    are not key fields. Justified: the Matches table is permanently bounded at 104 items
    (a tournament has fixed matches), so scan cost/latency never grows. At larger scale,
    the right approach would be a GSI on team_a/team_b."""
    response = matches_table.scan(
        FilterExpression=Attr("team_a").eq(team_id) | Attr("team_b").eq(team_id)
    )
    matches = response["Items"]

    # Sort chronologically by kickoff.
    matches.sort(key=lambda m: m["datetime_pacific"])

    return {"team_id": team_id, "matches": matches}

def get_match_result(match_id):
    """Fetch one match by its exact primary key — the cheapest possible read."""
    response = matches_table.get_item(Key={"match_id": match_id})
    match = response.get("Item")

    if match is None:
        return {"error": f"No match found with match_id: {match_id}"}

    return {"match": match}
