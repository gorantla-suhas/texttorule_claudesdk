# PROJECT_SKILLS.md

# Telecom Rule Engine - Project Knowledge

## Purpose

a telecom Rule Engine that converts natural language campaign
rules into structured JSON.

The project follows a **Claude SDK Centric Architecture ** design.

for better understanding of structure needed , you can go thorough the project in D:\vp_full_agents which works like  how we want this project to be 

Claude performs reasoning.

Python performs deterministic execution.

------------------------------------------------------------------------

# High Level Architecture

User ↓ FastAPI ↓ Claude Planner ↓ Validation Skill ↓ Condition Skill ↓
Action Skill ↓ Bonus Skill ↓ Policy Skill ↓ Schedule Skill ↓ Final Rule
JSON

------------------------------------------------------------------------



# Responsibilities (Architecture 1 - Claude SDK Centric)

## Core Philosophy

Architecture 1 is **Claude SDK Centric**.

Claude is the brain of the application.

Claude owns:
- Planning
- Workflow orchestration
- Reasoning
- Decision making
- Skill execution
- Tool selection
- State updates

Python is only responsible for deterministic execution and infrastructure.

---

# Claude Responsibilities

## 1. Planner

Responsible for:

- Understanding the user's request
- Creating the execution plan
- Selecting the next skill
- Managing workflow
- Handling retries
- Handling fallbacks
- Deciding when execution is complete

---

## 2. Workflow Orchestration

Claude controls the complete workflow.

Example:

User
↓

Planner
↓

Validation
↓

Condition
↓

Action
↓

Bonus
↓

Policy
↓

Schedule
↓

Final JSON

Python never controls this flow.

---

## 3. Skill Selection

Claude decides:

- Which skill to execute
- Which skill to skip
- Which skill to repeat
- Which skill requires clarification
- Which skill requires tool usage

---

## 4. Business Reasoning

Claude understands:

- Telecom campaigns
- Business rules
- Customer eligibility
- KPIs
- Products
- Recharge logic
- Subscription logic
- Promotions
- Bonus logic
- Scheduling logic

---

## 5. Tool Selection

Claude decides when tools are needed.

Examples

Need KPI
→ Vector Search Tool

Need Product
→ Product Tool

Need Policy
→ Policy Tool

Need SQL
→ SQL Tool

Python only exposes tools.

Claude chooses when to call them.

---

## 6. State Management

Claude owns the execution state.

It decides:

- What to remember
- What to update
- What to pass to the next skill
- What information should be discarded

Python simply stores the state.

---

## 7. Decision Making

Claude decides:

- KPI ambiguity
- Best action
- Bonus selection
- Policy conflicts
- Schedule selection
- Retry decisions
- Clarification requests

---

## 8. JSON Generation

Claude produces:

- Structured Conditions
- Structured Actions
- Bonus Objects
- Policy Objects
- Schedule Objects
- Final Campaign Rule JSON

---

## 9. Error Recovery

Claude decides:

- Retry current skill
- Try another tool
- Ask user for clarification
- Stop execution
- Continue execution

---

# Python Responsibilities

Python contains **no business reasoning**.

Its responsibility is deterministic execution.

---

## 1. Tool Execution

Examples

- Vector Search
- SQL Queries
- CSV Reading
- API Calls
- Redis
- Chroma
- Elasticsearch

---

## 2. Data Access

Python loads data from:

- KPI CSV
- YAML Configurations
- Product Database
- Policy Database
- Bonus Database
- SQL Server

---

## 3. Infrastructure

Python manages:

- FastAPI
- Authentication
- Configuration
- Logging
- Monitoring
- Environment Variables
- Dependency Injection

---

## 4. Builders

Python converts raw data into structured objects.

Example

CSV

↓

Python Object

↓

Claude

No reasoning happens here.

---

## 5. Technical Validation

Python validates only technical constraints.

Examples

- JSON Schema
- YAML Format
- Required Fields
- Database Connectivity
- API Availability
- File Existence

Business validation belongs to Claude.

---

## 6. External Integrations

Python communicates with:

- SQL
- Chroma
- Redis
- Elasticsearch
- REST APIs
- Internal Services
- File System

---

## 7. State Persistence

Python stores:

- RuleState
- Conversation State
- Cache
- Execution History
- Logs

Claude decides what changes.

Python persists those changes.

---

# Skill Responsibilities

## Planner

Responsible for:

- Planning
- Skill sequencing
- Retry strategy
- Workflow orchestration
- Tool invocation decisions

---

## Validation Skill

Responsible for:

- Validate user request
- Detect missing information
- Determine clarification needs
- Validate business completeness

---

## Condition Skill

Responsible for:

- Understand business conditions
- Identify required KPIs
- Retrieve KPIs using tools
- Resolve KPI ambiguity
- Generate structured conditions

---

## Action Skill

Responsible for:

- Determine business action
- Validate action parameters
- Select appropriate action
- Generate action structure

---

## Bonus Skill

Responsible for:

- Determine bonus type
- Determine aggregation type
- Determine products
- Validate bonus requirements
- Generate bonus structure

---

## Policy Skill

Responsible for:

- Determine eligibility
- Detect policy conflicts
- Validate campaign policies
- Generate policy structure

---

## Schedule Skill

Responsible for:

- Determine execution schedule
- Determine recurrence
- Validate scheduling parameters
- Generate schedule structure

---

# Execution Flow

User
        │
        ▼
 Claude Planner
        │
        ▼
 Validation Skill
        │
        ▼
 Condition Skill
        │
        ├────────► Vector Search Tool
        ├────────► KPI CSV Tool
        │
        ▼
 Action Skill
        │
        ├────────► Product Tool
        │
        ▼
 Bonus Skill
        │
        ├────────► Bonus DB Tool
        │
        ▼
 Policy Skill
        │
        ├────────► Policy DB Tool
        │
        ▼
 Schedule Skill
        │
        ▼
 Final Campaign JSON

---

# Guiding Principle

Claude owns:
- Planning
- Workflow
- Skills
- Reasoning
- Decisions
- Tool Selection
- State Updates

Python owns:
- Infrastructure
- Tool Execution
- Data Retrieval
- External Integrations
- Persistence
- Logging
- Configuration

**Claude thinks. Python executes parts of it**


------------------------------------------------------------------------

# Source of Truth

## KPI CSV

Contains

-   feature_name
-   description
-   group_name
-   value_references

Never duplicate KPI metadata inside YAML.

------------------------------------------------------------------------

# Configuration Philosophy

YAML stores only business configuration.

Examples

-   operators
-   action definitions
-   bonus definitions
-   schedule types
-   policy rules
-   validation rules

------------------------------------------------------------------------

# Claude Skills

Validation

Checks request completeness.

Condition

Identifies KPI requirements.

Uses KPI CSV.

Calls Vector Search.

Action

Identifies business action.

Bonus

Determines benefit.

Policy

Determines eligibility.

Schedule

Determines execution timing.

Planner

Controls execution order.

------------------------------------------------------------------------

# Shared State

need to be controlled by agents in most of the cases while the tools will be 

------------------------------------------------------------------------

# Execution Flow


                          USER
                            │
                            │  Natural Language Statement
                            ▼
                     FastAPI Endpoint
                            │
                            │  Start Claude Session
                            ▼
                  Claude Planner Agent
                            │
          [Reason]
          Decide execution plan
                            │
                            ▼
                  Validation Skill
                            │
          [Reason]
          Is the statement valid?
                            │
                            ▼
               Shared Conversation Memory
                            │
          [Next Task]
                            ▼
                  Condition Skill
                            │
          [Reason]
          Understand business intent
                            │
                            │
          [Call Tool]
          Search KPIs
                            ▼
                 Vector Search Tool
                      (Python)
                            │
          [Results]
          Top 20 KPI candidates
                            ▲
                            │
                  Condition Skill
                            │
          [Reason]
          Compare candidates
          Eliminate wrong KPIs
          Select best KPI
                            │
          [Update Memory]
                            ▼
               Shared Conversation Memory
                            │
          [Next Task]
                            ▼
                    Action Skill
                            │
          [Reason]
          Decide action type
                            │
          [Call Tool]
          Lookup products
                            ▼
               Product Lookup Tool
                     (Python)
                            │
          [Results]
          Matching products
                            ▲
                            │
                    Action Skill
                            │
          [Reason]
          Select correct product
                            │
                            ▼
                   Policy Skill
                            │
          [Reason]
          Resolve campaign policy
                            │
                            ▼
                   Bonus Skill
                            │
                            ▼
                 Schedule Skill
                            │
                            ▼
                 Builder Agent
                            │
          [Reason]
          Construct complete Rule JSON
                            │
                            ▼
                      Final Response





------------------------------------------------------------------------

# Project Structure

rule-engine/
│
├── .claude/
│   │
│   ├── settings.json                    # Claude SDK configuration
│
│   ├── agents/
│   │   ├── planner.md                   # Decides workflow and skill execution
│   │   ├── validator.md                 # Validates user input
│   │   ├── supervisor.md                # Monitors execution & retries
│   │   ├── reflection.md                # Self-checks reasoning
│   │   └── builder.md                   # Generates final Rule JSON
│   │
│   ├── skills/
│   │
│   │   ├── validation/
│   │   │   ├── SKILL.md                 # Validate statement
│   │   │   ├── examples.md              # Few-shot examples
│   │   │   └── references/              # Validation documentation
│   │   │
│   │   ├── condition/
│   │   │   ├── SKILL.md                 # Extract & reason about conditions
│   │   │   ├── examples.md              # Examples
│   │   │   └── references/              # KPI docs
│   │   │
│   │   ├── action/
│   │   │   ├── SKILL.md                 # Action reasoning
│   │   │   ├── examples.md
│   │   │   └── references/
│   │   │
│   │   ├── bonus/                       # Bonus reasoning
│   │   ├── policy/                      # Policy reasoning
│   │   ├── schedule/                    # Schedule reasoning
│   │   ├── parser/                      # Final parsing logic
│   │   └── message/                     # User-facing message generation
│   │
│   └── prompts/
│       ├── system.md                    # Global system prompt
│       └── common.md                    # Shared prompt snippets
│
├── configs/
│   ├── action_catalog.yaml              # Action definitions
│   ├── bonus_catalog.yaml               # Bonus metadata
│   ├── policy_catalog.yaml              # Policy metadata
│   ├── schedule_catalog.yaml            # Schedule metadata
│   └── parser_catalog.yaml              # Parser rules
│
├── data/
│   ├── kpis/                            # KPI datasets
│   ├── products/                        # Product catalog
│   ├── policies/                        # Policy datasets
│   ├── examples/                        # Golden examples
│   └── embeddings/                      # Vector DB
│
├── app/
│   ├── api.py                           # REST API
│   ├── server.py                        # FastAPI startup
│   ├── orchestrator.py                  # Starts Claude SDK session
│   ├── hooks.py                         # SDK hooks
│   ├── state.py                         # Shared execution state
│   ├── schemas.py                       # Pydantic models
│   │
│   └── tools/
│       ├── vector_search.py             # Vector search tool
│       ├── sql.py                       # SQL queries
│       ├── config_loader.py             # Read configs
│       ├── parser.py                    # Helper parser
│       ├── validator.py                 # Deterministic validation
│       ├── renderer.py                  # Render outputs
│       ├── logger.py                    # Logging
│       ├── product_lookup.py            # Product search
│       ├── policy_lookup.py             # Policy search
│       └── state_manager.py             # Read/update state
│
├── tests/
├── scripts/
├── README.md
└── pyproject.toml


------------------------------------------------------------------------

# Design Principles

-   Claude reasons.
-   Python executes.
-   Configuration driven.
-   Feature oriented.
-   Modular.
-   Reusable.
-   Single source of truth.
-   Avoid duplicated metadata.
-   Minimize hardcoding.
-   Every skill should be independently testable.

------------------------------------------------------------------------

# Finalized Decisions

-   Architecture 1 selected.
-   Claude SDK centric.
-   KPI CSV is source of truth.
-   YAML contains configuration only.
-   Shared RuleState.
-   Planner orchestrates workflow.
-   Skills remain generic.
-   Python owns deterministic logic.
-   Claude owns semantic reasoning.
