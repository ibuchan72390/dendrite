---
name: knowledge
description: Show dendrite network statistics and knowledge health
allowed-tools: Bash
user-invocable: true
---

Show the current state of dendrite's knowledge network:

```bash
dendrite stats --json
```

Present:
1. Total neurons and connections
2. Average connectivity (avg degree)
3. Most connected neurons (knowledge hubs)
4. Top concepts (most frequently referenced terms)
5. Health assessment: is the network well-connected or fragmented?
