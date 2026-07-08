# Raven AI Stylist

> NOTE: This is a trimmed down and sanitised version of documendation and code to illustation the overall design and implmentation of end-to-end AI-native app spanning data pipeline, model training, and multi-agent applications.

Conversational AI application for personalised style recommendations, powered by custom fine-tuned language models and multi-agent architecture.

## Overview

Raven AI stylist showcasing domain-specific model fine-tuning and multi-agent system design for personalised recommendations. The system combines a custom-trained MoE model with a multi-agent orchestrator to deliver contextual style advice and AI-generated virtual try-on images.

**Purpose**: Demonstrate that domain-specific trained models and multi-agent system design can enhance personalisation and recommendations. This is a showcase piece to validate model metrics.

## Features

- Profile-based persona selection
- Conversational style query interface
- Real-time outfit card generation
- AI-rendered virtual try-on images
- Feedback loop (thumbs up/down) for personalisation refinement

## Architecture

![System Architecture](images/architecture-overview.png)

### Multi-Agent System

The system follows standard orchestrator + stateless-sub-agent pattern.

![MLOPs Architecture](images/multi-agent-architecture.png)

**Components**:
1. **Stylist Master Agent** (Orchestrator)
   - Stateful session management
   - Coordinates sub-agents via tool calls
   - Maintains user preference state
   - Appends conversation memory

2. **Style Agent**
   - Processes context and returns style guides
   - Generates outfit recommendations

3. **VTO Agent**
   - Generates Gemini Flash prompts for image generation
   - Combines user photo with outfit descriptions
   - Returns photorealistic virtual try-on images

4. **User Profile Tool**
   - Stores user profiles in JSON format
   - Provides profile list for frontend selection

**Architecture Principles**:
- Stylist orchestrator holds session state (stateful)
- Sub-agents are stateless functions
- Episode-based persistence with atomic writes

## Technical Approach

1. **ML Pipeline**: 6-step orchestrated workflow (SageMaker Pipelines + model deployment)
2. **Data Engineering**: Schema-driven feature extraction. Medallion Architecture data processing.
3. **Training**: LoRA fine-tuning with Unsloth (4-bit quantisation, memory optimisation)
4. **Evaluation**: Dual-track assessment (automated model metrics + LLM-as-judge)
5. **Multi-Agent Systems**: Stateful orchestrator with stateless sub-agents
6. **Context Management**: Match training data distribution to inference patterns

### Tech Stack

**Backend**
- Python 3.x
- Custom fine-tuned GPT-OSS-20B (unsloth framework)
- AWS Lambda microservices architecture
- S3 storage for profiles and episodes

**Frontend**
- Next.js SPA
- Tailwind CSS
- Conversational UI

**Infrastructure**
- Terraform (IaC)
- AWS deployment (Lambda, S3)
- Local and remote deployment modes

### MLOps (separate repo)
**Architecture Overview**

![MLOPs Architecture](images/ml-pipeline.png)

**SageMaker Pipeline Orchestration**:

![SageMaker Pipeline Orchestration](images/pipeline.png)

- **SageMaker Pipelines**: Cloud-based orchestration with step dependencies
- **Local Pipeline**: Development mode with isolated run directories
- **Step Isolation**: Each step is a separate Python module with clear inputs/outputs
- **Run Tracking**: MLflow run ID propagation across pipeline steps

**Evaluation Framework**:
- **Automated Metrics**: Loss, perplexity, ROUGE, JSON validity
- **LLM Judge**: External model (Gemini/Claude) for qualitative assessment
- **Metric Tracking**: MLflow integration for experiment comparison
- **Quality Gates**: Conditional registration based on evaluation thresholds

![Judge Metrics](images/judge_metrics.png)


## Project Structure

```
raven/
├── backend/
│   ├── stylist/          # Master orchestrator agent
│   ├── style/            # Style recommendation agent
│   ├── vto/              # Virtual try-on agent
│   ├── inference/        # Model serving
│   └── api/              # User profiles & episodes
├── frontend/             # Next.js SPA
├── terraform/            # AWS infrastructure
├── notebooks/            # Training & evaluation
├── scripts/              # Build & deployment
└── docs/                 # Architecture diagrams
```

## Getting Started

### Prerequisites

- Python 3.x
- Node.js & npm
- AWS CLI (for deployment)
- llama.cpp (see `docs/llama-cpp-setup.md`)

### Local Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
npm run dev
```

### Deployment

```bash
# Infrastructure setup
cd terraform
terraform init
terraform apply

# Deploy
./scripts/deploy.sh --mode remote
```

## User Journey

1. User selects a profile (starts new session)
2. User types style query in chat
3. System responds with outfit card
4. System displays VTO image (auto-updates canvas)
5. User provides feedback (thumbs up/down)
6. Repeat for refinement

**Note**: Switching profiles mid-session resets chat and VTO state.

## Data Flow

```
User → Frontend → Stylist Orchestrator → Sub-agents → Model Inference
                        ↓                      ↓
                  Session State          Structured Output
                        ↓                      ↓
                  conversations.jsonl    Episode Bundle
```

### Episode Persistence

After each turn, orchestrator writes atomic bundle to:
```
backend/api/profiles/{user_id}/episodes/{ep_id}/
  ├── request.json
  ├── style.json (if style agent ran)
  ├── vto.json (if VTO agent ran)
  └── vto.png (if VTO agent ran)
```

All files written together or none (atomic).

## Development Notes

- Each component has its own CLAUDE.md for scoping
- Build components individually unless dependencies exist
- Respect component boundaries and separation of concerns
- See `backend/*/CLAUDE.md` for implementation details

## Licence

Private repository - All rights reserved
