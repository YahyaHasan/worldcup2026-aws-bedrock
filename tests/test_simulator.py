import os
import sys

# Make the simulator module importable from its Lambda folder.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "tools", "simulate_match"))

from app import simulate, expected_goals, lambda_handler, TEAMS


def test_probabilities_sum_to_one():
    """Win + draw + lose must cover all outcomes."""
    r = simulate("BRA", "MAR")
    total = sum(r["win_prob"])
    assert abs(total - 1.0) < 0.01, f"probabilities summed to {total}, expected ~1.0"


def test_higher_elo_is_favored():
    """Monotonicity: the higher-Elo team must have higher win prob.
    Uses lopsided matchups so the property holds reliably without a fixed seed
    (alternative: np.random.seed(...) for deterministic runs)."""
    lopsided = [("ESP", "CUW"), ("ARG", "JOR"), ("FRA", "NOR"), ("BRA", "HAI")]
    for a, b in lopsided:
        r = simulate(a, b)
        assert TEAMS[a]["elo_rating"] > TEAMS[b]["elo_rating"], "test setup: A should be higher Elo"
        assert r["win_prob"][0] > r["win_prob"][2], (
            f"{a} (Elo {TEAMS[a]['elo_rating']}) should beat "
            f"{b} (Elo {TEAMS[b]['elo_rating']}) more often: got {r['win_prob']}")


def test_home_advantage_helps():
    """A co-host at home should win at least as often as at a neutral venue."""
    neutral = simulate("MEX", "RSA", a_is_home=False)
    at_home = simulate("MEX", "RSA", a_is_home=True)
    assert at_home["win_prob"][0] >= neutral["win_prob"][0] - 0.02, (
        "home win prob should not be meaningfully lower than neutral")


def test_expected_goals_positive():
    """Expected goals (Poisson lambdas) must be positive for any real matchup."""
    la, lb = expected_goals("BRA", "MAR")
    assert la > 0 and lb > 0


def test_unknown_team_returns_error():
    """Bad team IDs must return a graceful error, not crash —
    important since the model (Bedrock) generates these inputs."""
    r = lambda_handler({"team_a": "XXX", "team_b": "MAR"}, None)
    assert "error" in r
