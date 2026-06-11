# World Cup 2026 Tournament Companion Agent

An agentic AI system built on **Amazon Bedrock (Nova) + AWS Lambda**. The orchestrator
implements a tool-use loop via the Bedrock Converse API: the model — not hardcoded logic —
decides which of four tools to call (deterministic match simulator, live news search,
schedule/standings lookup, session memory), dispatches them, and synthesizes results into
an answer. Built to run on/near the AWS free tier.

Demo project for AWS NYC Summit 2026.

## Architecture

```
                     ┌──────────────────────┐
                     │   Frontend (React)   │
                     │  S3 + CloudFront     │
                     └─────────┬────────────┘
                               │
                               ▼
                     ┌──────────────────────┐
                     │     API Gateway      │
                     └─────────┬────────────┘
                               │
                               ▼
                     ┌──────────────────────┐
                     │  Orchestrator Lambda │
                     │  (Bedrock Nova +     │
                     │   tool-use loop)     │
                     └─────────┬────────────┘
                               │
        ┌──────────────┬───────┴───────┬──────────────────┐
        ▼              ▼               ▼                  ▼
┌───────────────┐ ┌───────────┐ ┌──────────────┐ ┌──────────────────┐
│ Match          │ │ News      │ │ Schedule /   │ │ Memory Tool       │
│ Simulator Tool │ │ Search    │ │ Standings    │ │ (DynamoDB)        │
│ (Lambda)       │ │ Tool      │ │ Tool         │ │                   │
│ Poisson/Monte  │ │ (Lambda)  │ │ (Lambda)     │ │                   │
│ Carlo on Elo   │ │ Tavily    │ │ DynamoDB     │ │                   │
└────────────────┘ └───────────┘ └──────────────┘ └──────────────────┘

Cross-cutting: Bedrock Guardrails (input/output), CloudWatch structured
reasoning-trace logging, optional X-Ray tracing.
```

## Repo structure

```
├── template.yaml              # AWS SAM — all infrastructure as code (Phase 6+)
├── data/
│   ├── build_teams.py         # generates teams_seed.json from eloratings.net data
│   ├── teams_seed.json        # 48 teams: Elo, groups, confederations, Poisson strengths
│   ├── venues.json            # 16 venues: altitude, climate, country (co-host detection)
│   └── schedule.json          # 104-match schedule (pending)
├── scripts/
│   └── seed_dynamodb.py       # one-shot loader for the four DynamoDB tables (pending)
├── src/
│   ├── orchestrator/          # Bedrock Converse tool-use loop
│   ├── tools/                 # simulate_match, schedule_standings, news_search, memory
│   └── shared/                # DynamoDB helpers, structured logging
├── tests/
└── frontend/                  # Vite + React chat UI with reasoning-trace panel
```

## Build phases

1. **Data layer** — DynamoDB tables + seed data *(in progress)*
2. Match simulator Lambda (Poisson / Monte Carlo)
3. Schedule/standings Lambda
4. News search Lambda (Tavily)
5. Session memory Lambda
6. Orchestrator: Converse API tool-use loop
7. Bedrock Guardrails
8. Observability: structured reasoning traces
9. Frontend (React on S3 + CloudFront)
10. End-to-end demo polish

## Design decisions

A running log of choices and their tradeoffs. (This section is the point of the repo.)

**Elo as the single strength input.** Team attack/defense strengths for the Poisson model
are derived from eloratings.net Elo via a documented transformation, rather than scraped
per-team goals data. Rationale: free football APIs cover the 48-team field unevenly
(strong for Brazil, spotty for Curaçao or Cape Verde); one well-understood input with a
deterministic transformation beats mixing sources of inconsistent quality. Tradeoff:
loses team-specific style information (a defensive 1800-Elo team and an attacking
1800-Elo team get identical parameters).

**Strength transformation and K calibration.** `attack = 10^(K·(elo−mean)/400)`,
`defense = 10^(−K·(elo−mean)/400)`, where `mean` is the 48-team field average (1784).
Expected goals: `xG_A = league_avg × attack_A × defense_B`. K was tuned empirically
against the field's extreme case: at K=0.45, Spain (2157) vs Curaçao (1434) produced an
absurd 8.8 xG; K=0.25 yields 3.8 — consistent with real-world lopsided internationals.
Honest caveat: K is eyeballed against sanity checks, not regressed on historical data.
The simulator's `model_notes` field discloses this; qualitative gaps (injuries, form)
are the news tool's job.

**SAM over CDK/Terraform/console.** Infrastructure lives in `template.yaml` so a fresh
clone reproduces the entire stack with `sam deploy --guided`. SAM chosen over CDK
(heavier, general-purpose) and Terraform (multi-cloud, overkill) because the stack is
pure serverless. Bedrock itself is a managed service, not deployed — the template grants
Lambdas `bedrock:Converse` permission and injects the guardrail ID as an env var.

**Secrets hygiene.** No credentials in the repo, ever. API keys (Tavily) live in SSM
Parameter Store, referenced from the SAM template; local dev uses `.env` (gitignored).

## Data sources

- **Elo ratings**: [eloratings.net](https://www.eloratings.net) `World.tsv` endpoint
  (programmatically refreshable — future EventBridge-scheduled Lambda).
- **Schedule/groups**: official 2026 tournament structure (12 groups of 4, 48 teams).
- **Venues**: 16 stadiums across USA/Mexico/Canada with altitude and climate metadata.

## Deploy

*(Coming with Phase 6: `sam build && sam deploy --guided`, then `scripts/seed_dynamodb.py`.)*
