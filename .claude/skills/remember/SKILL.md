---
name: remember
description: Store knowledge in dendrite's neural network for cross-session persistence
argument-hint: "<knowledge to store>"
allowed-tools: Bash
user-invocable: true
---

Store the following knowledge in dendrite's neural network:

```bash
dendrite add "$ARGUMENTS" --json
```

After storing, report:
1. The neuron ID and extracted concepts
2. How many connections were automatically created
3. Suggest running `dendrite reindex` if many neurons have been added recently
