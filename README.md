# Legalyze AI Agent Backend

## Overview

**Legalyze AI Agent** is an intelligent legal assistant designed to streamline the process of understanding legal documents and engaging in casual legal-related conversations.

Built with a robust, modular **agent-based architecture**, this system can:

- Automatically detect whether the input is a legal document or a casual query
- Analyze legal documents to provide summaries, detect risks, and offer clause verdicts
- Engage in friendly chat for general legal inquiries
- Use intelligent guardrails to ensure safe and appropriate interactions (e.g. sensitive data detection)

This project showcases a **multi-agent system** in Python, with a strong emphasis on clear separation of concerns and robust error handling.

---

## Features

- **Intelligent Input Routing**
  Determines whether input is for document analysis or casual chat.

- **Comprehensive Legal Analysis**
  Summarizes documents, identifies risks, and checks clauses.

- **Conversational AI**
  Handles general legal questions and informal interactions.

- **Sensitive Data Guardrails**
  Prevents processing of sensitive personal information.

- **Modular Agent Design**
  Each function handled by a specialized AI agent.

---

## Project Setup

### Prerequisites

- Python 3.9+
- [`uv`](https://github.com/astral-sh/uv) (Fast Python package manager)

Install `uv` if not already installed:

```bash
# Linux/macOS:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell):
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

### Installation

```bash
git clone <your-repository-url>
cd <your-project-directory>

# Create virtual environment and install dependencies
uv venv
uv pip install -r requirements.txt
```

> If you don't have `requirements.txt` yet, run:

```bash
uv add openai pydantic python-dotenv
uv pip freeze > requirements.txt
```

---

### Environment Variables

Create a `.env` file in your root directory:

```env
GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE"
```

> `.env` is already in `.gitignore` — don’t commit it.

---

## How to Run

```bash
uv run main.py
```

You’ll be able to interact with your Legalyze AI Agent via the terminal.

---

## Project Flow Diagram

```mermaid
graph TD
    A["User Input"] --> B["Input Guardrail Check"]
    B --> C{"Contains Sensitive Info?"}
    C -- Yes --> D["Block Request"]
    C -- No --> E["MainAgent - Decision Router"]
    E --> F["DocumentDetectorAgent Tool"]
    F --> G{"Input Type?"}
    G -- Legal Document --> H["Analysis-Agent"]
    G -- Casual Chat --> I["CasualChatAgent"]
    G -- Unclear --> J["Default Response"]
    H --> K["Input Guardrail Check"]
    K --> L{"Sensitive Info?"}
    L -- Yes --> M["Block Analysis"]
    L -- No --> N["Start Analysis Workflow"]
    N --> O["SummarizerAgent Tool"]
    O --> P["Wait for Summary"]
    P --> Q["RiskDetectorAgent Tool"]
    Q --> R["Wait for Risk Analysis"]
    R --> S["ClauseCheckerAgent Tool"]
    S --> T["Wait for Clause Check"]
    T --> U["Combine Results"]
    U --> V["Output Guardrail Check"]
    V --> W{"Output Valid?"}
    W -- No --> X["Trigger Error"]
    W -- Yes --> Y["FriendlyAgent"]
    Y --> Z["Format Response"]
    Z --> AA["Output Guardrail Check"]
    AA --> BB{"Response Valid?"}
    BB -- No --> CC["Trigger Error"]
    BB -- Yes --> DD["Final Response"]
    I --> EE["Generate Chat Response"]
    EE --> FF["Output Guardrail Check"]
    FF --> GG{"Response Valid?"}
    GG -- No --> HH["Trigger Error"]
    GG -- Yes --> II["Chat Response"]
    J --> JJ["Default Message"]
    D --> KK["Error Message"]
    M --> KK
    X --> KK
    CC --> KK
    HH --> KK
    DD --> LL["User Sees Legal Analysis"]
    II --> MM["User Sees Chat Response"]
    JJ --> NN["User Sees Default Message"]
    KK --> OO["User Sees Error"]
     B:::guardrail
     C:::decision
     D:::error
     E:::agent
     G:::decision
     H:::agent
     I:::agent
     K:::guardrail
     L:::decision
     M:::error
     O:::agent
     Q:::agent
     S:::agent
     V:::guardrail
     W:::decision
     X:::error
     Y:::agent
     AA:::guardrail
     BB:::decision
     CC:::error
     DD:::output
     FF:::guardrail
     GG:::decision
     HH:::error
     II:::output
     JJ:::output
     KK:::error
    classDef agent fill:#e3f2fd,stroke:#1565c0,color:#000,font-weight:bold,stroke-width:2px
    classDef guardrail fill:#fff8e1,stroke:#ff8f00,color:#000,font-weight:bold,stroke-width:2px
    classDef decision fill:#ede7f6,stroke:#6a1b9a,color:#000,font-weight:bold,stroke-width:2px
    classDef output fill:#e8f5e9,stroke:#2e7d32,color:#000,font-weight:bold,stroke-width:2px
    classDef error fill:#ffebee,stroke:#c62828,color:#000,font-weight:bold,stroke-width:2px

```

---

## Flow Explanation

### 1. Input Guardrail

Scans input for sensitive data. If found → **blocked**.

### 2. Main Agent - Decision Router

Routes input to the right agent (Document or Chat) using `DocumentDetectorAgent`.

### 3. Legal Document Flow

- Re-checks sensitive data
- Runs:

  - `SummarizerAgent`
  - `RiskDetectorAgent`
  - `ClauseCheckerAgent`

- Validates final response
- Formats via `FriendlyAgent`

### 4. Casual Chat Flow

- Response generated by `CasualChatAgent`
- Final output guardrails applied

### 5. Unclear Input

- Shows a default message.

### 6. Errors

- Any blocked or invalid step shows user-friendly error messages.
