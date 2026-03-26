# Tech Debt: refactor-media-routing

## Open Items
- media-storage still depends on monolith `/auth/me`; uploads fail if monolith is down.
- monolith `/media/upload` remains as a compatibility endpoint and should be removed after cutover.
- two upload entrypoints (`/upload` and `/media/upload`) must remain aligned.
