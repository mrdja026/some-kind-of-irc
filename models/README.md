# Synthetic Claims Types

Use [claim.schema.yaml](/home/mrdjanubuntu/workspaace/some-kind-of-irc/synthetic_claims/claim.schema.yaml) as the canonical contract for the JSON files in this folder.

- Each `CLM-2026-*.json` file is a single `Claim`.
- [all_claims.json](/home/mrdjanubuntu/workspaace/some-kind-of-irc/synthetic_claims/all_claims.json) is `ClaimDataset`, which is just `Claim[]`.
- [claim_models.py](/home/mrdjanubuntu/workspaace/some-kind-of-irc/synthetic_claims/claim_models.py) is the Python ingestion model using Pydantic.
- [claim.types.ts](/home/mrdjanubuntu/workspaace/some-kind-of-irc/synthetic_claims/claim.types.ts) is the TypeScript compile-time shape.

This layout is the most practical cross-language option here: keep one language-neutral schema in YAML, then mirror it with thin Python and TypeScript bindings.

## Python

```python
from pathlib import Path

from synthetic_claims.claim_models import Claim, ClaimDataset

claim = Claim.model_validate_json(
    Path("synthetic_claims/CLM-2026-0001.json").read_text(encoding="utf-8")
)

dataset = ClaimDataset.model_validate_json(
    Path("synthetic_claims/all_claims.json").read_text(encoding="utf-8")
)
```

## TypeScript

```ts
import type { Claim, ClaimDataset } from "./claim.types";

const claim = JSON.parse(jsonText) as Claim;
const dataset = JSON.parse(jsonText) as ClaimDataset;
```

If you want runtime validation in TypeScript later, validate against [claim.schema.yaml](/home/mrdjanubuntu/workspaace/some-kind-of-irc/synthetic_claims/claim.schema.yaml) with AJV.
