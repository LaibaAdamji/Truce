# Truce-
Multi-agent AI negotiator that turns a messy freelance brief into a signed scope-and-milestone contract . Powered by Gemma via Fireworks on AMD infrastructure

Set up backend :
    `python -m venv venv 
    venv\Scripts\activate
    pip install -r requirements.txt`

Set up frontend:
`streamlit run app.py`

### Folder Structure:
Note: This is very tentative for now and can/will be changed as required throughout the week 

```
project-root/
├── agents/
│   ├── client_agent.py       ← extracts requirements + flags gaps from client brief
│   ├── freelancer_agent.py   ← reasons about fair price floor from market data
│   └── mediator_agent.py     ← runs negotiation loop between client & freelancer
├── models/
│   └── schemas.py            ← shared Pydantic data models (single source of truth)
├── db/
│   ├── client.py              ← Supabase connection instance
│   └── operations.py         ← all DB read/write functions
├── tools/
│   ├── market_research.py    ← fetches comparable freelance rate data
│   ├── rate_ranking.py       ← GPU-ranking step (embeds + ranks comparables)
│   └── llm_client.py         ← wrapper around Fireworks/Gemma calls
├── crew.py                   ← wires the 3 agents into one CrewAI pipeline
├── app.py                    ← Streamlit frontend / UI
├── config/
│   └── settings.py           ← reads env vars, exposes typed settings
├── seed/
│   └── demo_data.py          ← seeds golden-path demo data for testing/judges
├── Dockerfile                ← containerizes the app for submission
├── requirements.txt          ← pinned Python dependencies
├── .env.example               ← env var names (no real values, safe to commit)
└── README.md                  ← setup + run instructions for judges
```