import json
import os
import numpy as np

LEAGUE_AVG_GOALS = 1.35
HOME_ADVANTAGE = 1.10
N_SIMULATIONS = 10000

# Load team data bundled alongside this file (not relative to the working dir,
# since Lambda runs from an unknown location).
_DATA_PATH = os.path.join(os.path.dirname(__file__), "teams_seed.json")
with open(_DATA_PATH) as f:
    TEAMS = json.load(f)


def expected_goals(team_a_id, team_b_id, a_is_home=False, b_is_home=False):
    """Compute each team's expected goals (Poisson lambda) for the matchup."""
    a = TEAMS[team_a_id]
    b = TEAMS[team_b_id]

    lambda_a = LEAGUE_AVG_GOALS * a["attack_strength"] * b["defense_strength"]
    lambda_b = LEAGUE_AVG_GOALS * b["attack_strength"] * a["defense_strength"]

    if a_is_home:
        lambda_a *= HOME_ADVANTAGE
    if b_is_home:
        lambda_b *= HOME_ADVANTAGE

    return lambda_a, lambda_b


def simulate(team_a_id, team_b_id, a_is_home=False, b_is_home=False, n=N_SIMULATIONS):
    """Run n Monte Carlo trials, drawing each team's goals from a Poisson distribution."""
    lambda_a, lambda_b = expected_goals(team_a_id, team_b_id, a_is_home, b_is_home)

    goals_a = np.random.poisson(lambda_a, n)
    goals_b = np.random.poisson(lambda_b, n)

    a_wins = int(np.sum(goals_a > goals_b))
    b_wins = int(np.sum(goals_b > goals_a))
    draws  = int(np.sum(goals_a == goals_b))

    # Most likely exact scoreline across all simulations.
    from collections import Counter
    scorelines = Counter(zip(goals_a.tolist(), goals_b.tolist()))
    (best_a, best_b), _ = scorelines.most_common(1)[0]

    return {
        "win_prob": [round(a_wins / n, 3), round(draws / n, 3), round(b_wins / n, 3)],
        "expected_goals": [round(lambda_a, 2), round(lambda_b, 2)],
        "most_likely_score": f"{best_a}-{best_b}",
        "model_notes": ("Poisson/Monte Carlo on Elo-derived strengths. Does not account for "
                        "injuries, suspensions, current form, or tactical matchups — those are "
                        "the news tool's domain. Home advantage applied only for co-hosts at home."),
        "n_simulations": n,
    }


def lambda_handler(event, context):
    """Lambda entry point. Expects event with team_a, team_b, and optional flags."""
    team_a = event["team_a"]
    team_b = event["team_b"]
    a_is_home = event.get("a_is_home", False)
    b_is_home = event.get("b_is_home", False)

    if team_a not in TEAMS or team_b not in TEAMS:
        return {"error": f"Unknown team_id. Valid example IDs: BRA, MAR, MEX."}

    return simulate(team_a, team_b, a_is_home, b_is_home)
