<!-- OPENSPEC:START -->

# OpenSpec Instructions

These instructions are for AI assistants working in this project.

# IGNORE Enhancments.md

Always open `@/openspec/AGENTS.md` when the request:

- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:

- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

Default venv name is be if not present ask for permission to create it. When running somethning that has a requierments.txt allways suggest that venv via pixi toml be creted first

# When cannot find plans try first /openspec folder in working repository 

When you cannot find plans try searching /openspec folder in working repository when in plan mode
or  /home/mrdjanubuntu/workspaace/some-kind-of-irc/openspec path 

# Coding self loop

**Your code will be evaluated by three agents Claude Opus 4.6, and Codex 5.3 and a Secret Frontier lab, be paranoid**

**MUST** be acceptable to other agents as solution

After the coding agent does it job check the changes with the git diff short and do a static linting provivded by pixi.toml python pixi run python-lint 

**YOU MUST** Ask for review of git diff if prompted do a self review, and document the tradeofs in openspec/**/tech_debt.md 

**MUST** Every coding task must be completed with @deploy_local.sh --build working


# Planning loop

**Allways** ask questions when building for ambiguities and tradofs
**Allwas** ground research in search provided by the agent google/bing/fetch
**Allways** describe tradeofs and propose them for simplicity

# Debugging loop

**MUST** the agent must ask if we are deploying on vps or localy
**VPS** run-localy-k3s.sh
**Local** deploy_local.sh --build --flags must pass
When working with **VPS** add allways instructions to apply helm chart changes if applicible **AND** command to restart a affected part of the k3s plane

# Caddy routing rules

Caddy evaluates `path` matchers top-down. **Specific routes must come before generic wildcards** or the generic rule swallows the request.

Current routing for `/media/*`:

```
@media_upload  path /media/upload        → backend:8002
@media_claims  path /media/claims/*      → backend:8002
@media         path /media/*             → media-storage:9101
```

**Why this order matters:**
- `backend:8002` owns all claims logic (`/media/claims/random`, `/media/claims/{id}/files`, `/media/claims/deep-review/random`)
- `media-storage:9101` owns raw file serving (`/media/<key>` for images, PDFs, etc.)
- If `@media_claims` is missing or placed after `@media`, claims requests hit media-storage which has no claims endpoints → 404

**Rule:** When adding new `/media/...` backend endpoints, add a specific Caddy matcher **above** the generic `@media` rule. Never rely on the generic `/media/*` rule to reach the backend.


When you cannot find plans try searching /openspec folder in working repository when in plan mode
or  /home/mrdjanubuntu/workspaace/some-kind-of-irc/openspec path
<!-- OPENSPEC:END -->


