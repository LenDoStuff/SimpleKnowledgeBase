# Agent Instructions

## Backend Style

Keep backend flows explicit and readable. Prefer direct dependencies and clear failure semantics over optional wrappers, fallback paths, or test-only indirection in production code. Abstractions must earn their place by encoding real domain policy or reducing real complexity.

- No speculative abstraction. Add wrappers, interfaces, or seams only when they hide real complexity or encode app policy.
- No hidden fallback behavior. If Azure, splitter, or required API config is missing, fail clearly.
- Production flow should read top-to-bottom. A reader should see exactly which external API is called.
- Tests should not distort production code. If tests need control, monkeypatch the real imported dependency instead of adding test-only parameters to production functions.
- Mocks stay isolated. Mock and demo behavior belongs outside the main path and must be opt-in only.
- Dependency use is honest. If the app depends on a specific API, import and call that API directly.
- Adapters must add value. Keep adapters when they enforce app policy or map external output into app models; remove wrappers that only add indirection.
