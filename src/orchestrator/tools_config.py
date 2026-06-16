"""Tool definitions for the Bedrock Converse API. Each toolSpec tells the model
what a tool does, WHEN to use it, and what arguments it takes. The model reads
these descriptions to decide which tool(s) to call."""

TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "simulate_match",
                "description": (
                    "Predict the probable outcome of a match between two teams using a "
                    "Poisson/Monte Carlo model. Use this for ANY question about who would "
                    "win, win probabilities, predicted scorelines, or 'what if' matchups — "
                    "including hypothetical matchups between teams not scheduled to play. "
                    "Do NOT use this for factual past results (use get_schedule_and_standings)."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "team_a": {
                                "type": "string",
                                "description": "Three-letter FIFA team ID, e.g. BRA, MAR, MEX.",
                            },
                            "team_b": {
                                "type": "string",
                                "description": "Three-letter FIFA team ID for the opponent.",
                            },
                            "a_is_home": {
                                "type": "boolean",
                                "description": "True only if team_a is a co-host (USA/MEX/CAN) playing in its own country.",
                            },
                            "b_is_home": {
                                "type": "boolean",
                                "description": "True only if team_b is a co-host playing in its own country.",
                            },
                        },
                        "required": ["team_a", "team_b"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_schedule_and_standings",
                "description": (
                    "Look up FACTUAL tournament data: a team's match schedule, group "
                    "standings, or a specific match's result. Use this for 'when does X "
                    "play', 'show me Group C', or 'what was the score of match M001'. "
                    "Do NOT use this for predictions (use simulate_match)."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "query_type": {
                                "type": "string",
                                "enum": ["team_schedule", "group_standings", "match_result"],
                                "description": "Which kind of lookup to perform.",
                            },
                            "team_id": {
                                "type": "string",
                                "description": "FIFA team ID, required for team_schedule.",
                            },
                            "group_id": {
                                "type": "string",
                                "description": "Group letter A-L, required for group_standings.",
                            },
                            "match_id": {
                                "type": "string",
                                "description": "Match ID like M001, required for match_result.",
                            },
                        },
                        "required": ["query_type"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "search_team_news",
                "description": (
                    "Get CURRENT real-world news about a team: injuries, suspensions, "
                    "recent form, lineup changes, controversies. Use this for anything "
                    "about a team's present-day situation that a statistical model cannot "
                    "know. Complements simulate_match, which handles probabilities only."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "team_name": {
                                "type": "string",
                                "description": "Full team name, e.g. Morocco, Brazil.",
                            },
                            "topic_hint": {
                                "type": "string",
                                "description": "Optional focus, e.g. injury, lineup, form.",
                            },
                        },
                        "required": ["team_name"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "manage_memory",
                "description": (
                    "Save or retrieve user preferences for this conversation. Call with "
                    "action='retrieve' at the start of a conversation to load what you "
                    "know about the user. Call with action='save' when the user states a "
                    "preference (e.g. their favorite team). Use consistent snake_case keys "
                    "like favorite_team."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["save", "retrieve"],
                                "description": "Whether to save a new fact or retrieve all facts.",
                            },
                            "key": {
                                "type": "string",
                                "description": "Fact name, required for save. Use snake_case, e.g. favorite_team.",
                            },
                            "value": {
                                "type": "string",
                                "description": "Fact value, required for save.",
                            },
                        },
                        "required": ["action"],
                    }
                },
            }
        },
    ]
}
