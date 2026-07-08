# Raven AI Stylist
Raven is a converstaional AI application (powered by custom trained MoE model fined tune on base model gpt-oss-20b) where user can simply chat and ask for style and outfit recommendations. The user can also ask for it to be display a rendering of virtual try-on (VTO) image combining user's profile photo and recommended descriptions of outfit items.

The scope of this project is a demo prototype. The purpose to do demonstrate domain specific trained models and multi-agent system design can enhance personalisation and recommendations. The protoype is a showcase piece to back up model metrics.

The prototype functionalities include:

User can choose a profile representing a persona type, and then ask the AI stylist for style advice to showcase that the style is personalised for that user. 

For style prompt requests, recommendation, and VTO, the system is a multi-stage workflow for the Raven to analyse user query and profile data to recommend styles. The workflow will be implemented using multi-agents and tool calls to fulfil user requests. 

## User Journey
1. User selects a profile (this starts a new session — switching profile mid-demo resets chat and VTO state)
2. User types a prompt in the chat box to ask for style guides
3. The system responds with style guides (synthesised in chat as an outfit card)
4. The system displays a VTO image when one is generated; the VTO canvas auto-updates whenever a new image is returned
5. User can thumb up / thumb down the outfit card or the VTO image; signals are added to the session's liked/rejected lists and fed into the next style request
6. Repeat 2–5 for refinement, or exit the application

No persistent logging required at this stage — the goal is to demo that the model and the system work. (Per-turn writes to `conversations.jsonl` are still part of the orchestrator's design; they're cheap and align with the long-term shape.)

## System Design
The system is divided into several components and sub-components, they will have their own project folder and CLAUDE.md for scoping. The components are to be integrated as part of Raven application.

Please refer to @docs/sdd.png

The following are the components of the system to be build individually to facilitate the functionalities of the system. Read the whole document before planning, and confirm plan before implmentation.


### Backend 
The backend has all the business logic to serve the frontend dynamic content. The backend consists several components that are either agents or regular functions for to support calls from the conversational UI frontend. Each component should be their own microservices hosting on AWS Lambda.

#### Agents
The reasoning model for the agent is a domain specific custom finetuned from the base model GPT-OSS (unsloth/gpt-oss-20b-unsloth-bnb-4bit). Use the unsloth framework for faster inferencing and other optimisations. 

1. Stylist Master Agent: Orchestrator. Receives user requests from the chat and is the single point of contact for the frontend. Owns active-session state — running conversation, plus the items the user has thumbed up/down so far in this session — and is responsible for appending each turn to that user's `conversations.jsonl`. Coordinates the sub-agents below as stateless tool calls; sub-agents do not maintain session state of their own.

Code location: backend/stylist

2. Style Agent: Single agent that process context and return style guides and generate recommendations product list that are brand agnostic. 

Code location: backend/style

3. VTO Agent: A virtual try-on agent that process request and style input to generate a Gemini Flash prompt. This prompt is used to query Gemini Flash API for style, scene along with user photo and products to generate a photo realistic image plus description as a response. The VTO Agent only uses the custom model to generate Gemini Flash prompt that is personalised to the user. It uses third party to generate image as this is not in the scope of this project. Also, it can generate high fidelity images, which is important for users.

Code location: backend/vto

4. User Profile Tool: Stores user profile in JSON format. The profiles are used to construct a list for the front end so it can be choosen to demo as the logged in user.

Code location: backend/profile

5. Product Search Tool (out of scope): A list of fashion product images and description. The search tool accepts semantic search queries and return matching products.
Code location: backend/product

Agent 5 is not in scope - the system should be design to cater for agent 5 extension in the next phase.

For more details of each component and implementation requirements, refer to the CLAUDE.md inside their folder.

#### Agent workflow

The system follows the standard orchestrator + stateless-sub-agent pattern
(as in OpenAI Agents SDK, LangGraph, Bedrock Agents, Anthropic tool-use):

- **Stylist orchestrator** holds session state and is the only stateful
  component. Per turn it: (a) reads the user message, (b) builds a
  request object for whichever sub-agent it needs to call, (c) makes the
  tool call, (d) synthesises the reply to the user, (e) appends the turn
  to that user's `conversations.jsonl`.
- **Sub-agents (style, vto)** are stateless functions. They take their
  inputs as explicit arguments, fetch any reference data they need from
  `backend/api`, call the model via `backend/inference`, and return
  structured JSON. They do not read session history or write logs.

Two distinct conversation surfaces exist and must not be confused:

- **Active-session conversation** — held in memory by the orchestrator.
  When calling a sub-agent, the orchestrator passes the **last ~3 turns**
  ending on the current user ask. This bound matches the model's training
  distribution (training data was filtered to 0–3 prior turns due to
  context budget); going wider degrades output quality.
- **Historical log** — `backend/api/profiles/{user_id}/evidence/conversations.jsonl`.
  Append-only across all sessions. Source corpus for the offline
  distillation that produces `derived/profile.json` and
  `derived/persona.json`. Never loaded into a live prompt.

#### Episode persistence

After each turn that involved a sub-agent, the orchestrator writes an
**atomic bundle** to `backend/api/profiles/{user_id}/episodes/{ep_id}/`:
`request.json` + `style.json` (if style ran) + `vto.json` + `vto.png`
(if VTO ran). All files for a turn are written together or none — never
a partial episode.

Sub-agents do not write episodes. They return structured payloads
(`vto.run()` returns `image_b64` plus the full Sigmoi response); the
orchestrator decodes and persists. This keeps sub-agents stateless and
lets episodes stay coherent. When `backend/api` gains a `POST
/users/{user_id}/episodes` create endpoint, the orchestrator switches
from filesystem writes to HTTP without changing the schema.

### Frontend 
The frontend is an SPA built with Next.js and Tailwind CSS. It is a conversational UI where the user picks a profile, asks for style guides, and sees the recommendations rendered as outfit cards in chat alongside a VTO image in the left canvas. See @docs/ui/screens/ for the current mockups.

The frontend talks **only** to the stylist orchestrator (`backend/stylist`); it does not call the sub-agents (`backend/style`, `backend/vto`) or `backend/inference` directly. The one exception is the profile picker, which reads `backend/api/users` to populate its list before any session exists.

Code location: frontend

For more details of the frontend and implementation requirements, refer to the CLAUDE.md inside the frontend folder.

### Infrastructure 
The agents and websites are to be hosted on AWS Cloud. The infrastructer is to be set up using Infrastructre as Code (IaC).

The IaC code should go into the `terraform` folder. It should contains all files for aws. This include:
- Lambda for hosting the agents
- Frontend component hosting
- User profiles (can store in S3 as JSON files)

Server start script should start the app with local or remote mode. Local is hosting everything locally. Remote is starting everything remotely.

For testing, it should be done locally first.

## Prerequisites
- **llama.cpp** — required by `scripts/merge_model.py --method gguf` to export
  GGUF artefacts. Install steps and the expected `LLAMA_CPP_DIR` env var are
  documented in @docs/llama-cpp-setup.md.

TIPS:

Please take a look at Alex repo at ../alex/ to understand the system design concept.
The Alex project contains multi-agent, orchestrator, frontend, backend, terraform and the workflow similar to this project but for different domain. Don't copy the "alex" project verbatinm, just borrow the approach. This project is much simpler.

## Build Instructions
- Use an agent to build each component
- Use project root CLAUDE.md for system context
- Use component CLAUDE.md for more build details
- Build each component at at time unless there is a dependency
- If outside of scope is required, communicate with that Claude Code agent
- Do not step outside of their component and respect boundaries and separation of concerns 
- For each component, define a PLAN.md and list the overall plan, tasks to be done, and task status (ie, completed, new, pending, review etc)
- For each component, make a changelog.md to keep track of what changed and why
- For each component, update CLAUDE.md to reflect accurate information. Don't be too verbose
- For each mini task completed, make a PR and merge if no conflicts
- For each component completion, make a release along with release notes
- For any major changes, update project root CLAUDE.md to reflect accurate information
- If anything you are unsure, ask, plan, request approval, update plan, execute, update relevant docs, submit PR and merge to main.
- If you have any suggestion for good tools (mcp, plugins etc) to use please ask. E.g fashion inventory db plugin, research etc.

### Tools
- context7 
- jira
- github
- others

