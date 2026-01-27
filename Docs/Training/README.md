# Oracle of Secrets Training Data

Training data and examples for improving local models (Zelda/Oracle specialized agents).

## Directory Structure

```
Training/
├── asm_examples/        # 65816 assembly code examples
│   ├── sprite_*.json    # Sprite implementation examples
│   ├── routine_*.json   # Vanilla routine adaptations
│   └── debug_*.json     # Bug fix case studies
├── debugging_sessions/  # Full debugging session transcripts
│   └── session_*.jsonl  # JSONL format for training
├── model_prompts/       # Curated prompt/response pairs
│   └── prompts_*.json   # Categorized prompt examples
└── README.md           # This file
```

## Data Formats

### ASM Examples (`asm_examples/*.json`)
```json
{
  "id": "sprite_example_001",
  "category": "sprite",
  "title": "Basic Sprite State Machine",
  "context": "Creating a simple NPC with idle/walk states",
  "input": "Create a sprite that walks back and forth",
  "code": "; Assembly code here",
  "explanation": "Step-by-step explanation",
  "tags": ["sprite", "state-machine", "npc"],
  "verified": true,
  "source": "campaign_iteration_XX"
}
```

### Debugging Sessions (`debugging_sessions/*.jsonl`)
One JSON object per line:
```json
{"turn": 1, "role": "user", "content": "Black screen on building entry"}
{"turn": 2, "role": "assistant", "content": "Let me check INIDISP..."}
{"turn": 3, "role": "tool", "name": "read_memory", "result": "..."}
```

### Model Prompts (`model_prompts/*.json`)
```json
{
  "prompts": [
    {
      "id": "prompt_001",
      "category": "assembly",
      "prompt": "What does LDA.w SprState, X do?",
      "response": "This loads the sprite state...",
      "quality": "verified",
      "model_version": "din-v4"
    }
  ]
}
```

## Collection Guidelines

1. **Verify correctness** - All code examples must be tested
2. **Include context** - Explain why the code works
3. **Tag appropriately** - Use consistent category tags
4. **Source attribution** - Link to campaign iteration or commit

## Usage

Training data can be used to:
- Fine-tune local Zelda models (din, veran, farore)
- Create evaluation datasets
- Build prompt libraries for agent orchestration
- Document successful debugging patterns

## Campaign Integration

Training examples are automatically extracted from:
- Successful debugging sessions in CampaignLog.md
- Code fixes with detailed explanations
- Model consultations rated as "HELPFUL"

---

*Created: 2026-01-24 (Iteration 91)*
*Part of Goal E: Knowledge Synthesis*
