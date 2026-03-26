## 1. Implementation
- [x] 1.1 Add `POST /media/upload` alias in media-storage (reuse existing upload handler).
- [x] 1.2 Route `/media/upload` to media-storage in ingress (remove monolith special case).
- [x] 1.3 Leave monolith `/media/upload` for compatibility (no ingress route).
- [x] 1.4 Update deployment docs to reflect routing change.
- [ ] 1.5 Validate: lint, local deploy, media upload/download check (upload/download pending).
