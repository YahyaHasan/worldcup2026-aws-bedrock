import json
import boto3
from decimal import Decimal

dynamodb = boto3. resource("dynamodb", region_name="us-east-1")

def to_decimal(obj):
    """Recursively convert floats in a loaded-JSON object to Decimal,
    since DynamoDB rejects Python floats."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_decimal(v) for v in obj]
    return obj

def seed_teams():
    with open("data/teams_seed.json") as f:
        teams = json.load(f)
    
    table = dynamodb.Table("Teams")
    with table.batch_writer() as batch:
        for team in teams.values():
            batch.put_item(Item=to_decimal(team))
    
    print(f"Loaded {len(teams)} teams into Teams table")

def strip_nulls(item):
    """Remove keys whose value is None — DynamoDB items are schemaless,
    so absent fields are cleaner than stored nulls."""
    return {k: v for k, v in item.items() if v is not None}

def seed_matches():
    with open("data/schedule.json") as f:
        matches = json.load(f)
    
    table = dynamodb.Table("Matches")
    with table.batch_writer() as batch:
        for match in matches:
            batch.put_item(Item=to_decimal(strip_nulls(match)))
    
    print(f"Loaded {len(matches)} matches into Matches table")

def seed_group_standings():
    with open("data/teams_seed.json") as f:
        teams = json.load(f)

    table = dynamodb.Table("GroupStandings")
    with table.batch_writer() as batch:
        for team in teams.values():
            row = {
                "group_id": team["group"],   # partition key
                "team_id":  team["team_id"], # sort key
                "points": 0,
                "played": 0,
                "goals_for": 0,
                "goals_against": 0,
                "goal_diff": 0,
            }
            batch.put_item(Item=row)

    print(f"Loaded {len(teams)} initial standings rows into GroupStandings table")

if __name__ == "__main__":
    seed_teams()
    seed_matches()
    seed_group_standings()
    print("All tables seeded.")
