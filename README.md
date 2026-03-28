# Dendrite

Neural-inspired knowledge synthesis CLI. Each note is a **neuron**; shared concepts create **synaptic connections** scored by TF-IDF cosine similarity. Querying activates neurons and spreads through high-strength connections. Consolidation strengthens frequently traversed paths; decay weakens unused links over time.

## Install

```bash
pip install -e ".[dev]"
```

## Usage

```bash
dendrite add "The mitochondria is the powerhouse of the cell"
dendrite add "Cells produce ATP through oxidative phosphorylation" --title "ATP Production"
dendrite ask "how does the brain get energy?"
dendrite explore "energy"
dendrite graph
dendrite stats
dendrite consolidate
dendrite list
dendrite show <id>
```

## Run tests

```bash
pytest -v
```
