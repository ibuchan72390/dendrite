---
name: synthesize
description: Explore a concept in dendrite and synthesize connected knowledge into a coherent summary
argument-hint: "<concept>"
allowed-tools: Bash
user-invocable: true
---

Explore the concept "$ARGUMENTS" in dendrite's knowledge network:

```bash
dendrite explore "$ARGUMENTS" --json --depth 3
```

Then synthesize:
1. List all connected neurons found within 3 hops
2. Identify the strongest connection paths
3. Write a coherent summary that weaves the connected knowledge together
4. Note any knowledge gaps or weak connections that could be strengthened
