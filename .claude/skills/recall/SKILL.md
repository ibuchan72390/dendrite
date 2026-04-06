---
name: recall
description: Search dendrite for relevant knowledge using semantic similarity and activation spreading
argument-hint: "<query>"
allowed-tools: Bash
user-invocable: true
---

Search dendrite's knowledge graph for: $ARGUMENTS

```bash
dendrite ask "$ARGUMENTS" --json --top 5
```

Present results showing:
1. Each result's title, confidence score, and key concepts
2. Activation paths (how knowledge connects)
3. Content summaries for the top results
