# AGENTS.md

## Project Overview

`openwisp-controller` is the OpenWISP Django app for device configuration management, VPN provisioning, shell/SSH commands, PKI integration, maps, and IPAM integration.

Core code lives in `openwisp_controller/`:

- `config/` handles device configuration, templates, VPNs, commands, and related APIs.
- `connection/` handles device credentials, connectors, SSH operations, and command execution.
- `pki/`, `geo/`, and `subnet_division/` integrate x509, geographic data, and subnet/IPAM behavior.
- Tests live alongside their owning packages under `openwisp_controller/**/tests/`; `tests/` is the Django test project used by local development and CI, including sample-app integration coverage.

## Source of Truth

- Use `docs/developer/installation.rst` and `docs/developer/index.rst` for local setup, services, and baseline test commands.
- Use `.github/workflows/ci.yml` for CI-tested dependencies, QA/test commands, env vars, and supported Python/Django versions.
- Use GitHub issue/PR templates when asked to open issues or PRs.

If instructions conflict (please let us know!), repository config and CI workflows win first, official docs next, and this file is supplemental.

## Contributing Guidelines

- Before editing, inspect the relevant implementation, tests, documentation, and configuration. Follow existing repository patterns and do not invent behavior or requirements.
- Keep each contribution focused and change only the lines necessary for its goal. Do not include unrelated refactors, formatting churn, or generated and dependency-file changes unless explicitly required.
- Add or update focused tests for every behavior change. Use test-driven development when the scope is very clear, such as bug fixes or narrowly scoped changes. For new features, tests may be added after implementation, but confirm they fail when key feature code is removed. When a test failure does not clearly state the expected outcome that was not met, add an explicit assertion message.
- Run `openwisp-qa-format` after each change when available.
- Run the relevant targeted tests, builds, and documented QA checks, including `./run-qa-checks` when provided. Do not claim a change is complete when verification fails; report the failure or blocker.
- When requirements, intended behavior, or an unexpected failure are unclear, stop and seek clarification instead of making speculative changes.
- When starting work on a new issue, create a new branch from `master`. Use `issues/<issue-number>-<short-title>` for issue work; otherwise, use a short, descriptive branch name.
- Commit messages must be descriptive and use past tense. Past tense is a writing guideline that agents and contributors must follow; it is not checked automatically. For issue work, use an allowed prefix and a capitalized, past-tense subject ending with `#<issue-number>`, for example `[fix] Fixed perennial "modified" state #213`. Repeat the issue reference in the body with `Fixes`, `Closes`, `Resolves`, or `Related to` as appropriate. Use `openwisp-commit --check` to validate the structural commit convention and `cz -n cz_openwisp info` to view the allowed prefixes and message structure.
- Add an explanatory commit body only for substantial changes, new features, or non-obvious bug fixes. The releaser automatically publishes the subject of `[feature]`, `[change]`, `[change!]`, `[deps]`, and `[fix]` commits, including scoped variants, in the changelog. Write those subjects in clear, user-friendly language suitable for release notes.
- Send new commits in response to review feedback instead of amending existing commits.

## Development Notes

- Follow the DRY principle: do not duplicate information or code across files.
- Preserve public APIs, migrations, swappable models, VPN backends, connector behavior, and integration points unless explicitly required.
- Mark user-facing strings for translation with Django i18n helpers in Django code.
- Place imports at the top of the file. Only defer imports when necessary (for example, Django model imports inside functions or methods where the app registry is not yet ready).
- Avoid unnecessary blank lines inside function and method bodies.
- Prefer short, precise names that rely on their nearest meaningful scope. Do not repeat a feature, domain object, or namespace already named by the containing module, class, or function. For example, prefer `EstimatedLocation.refresh()` over `EstimatedLocation.refresh_estimated_location()`. Repeat that context only when the name is used outside that scope or is needed to distinguish genuinely different concepts. When a concise name cannot express a necessary distinction, use a concise docstring to describe it rather than encoding it in an excessively long name.
- Before adding a comment or docstring, ask whether it conveys information a reader cannot reasonably infer from clear code, names, and surrounding scope. Add a concise comment when it explains a non-obvious reason, constraint, compatibility or security requirement, side effect, or unavoidable complexity. In opaque syntax or domain-specific code, especially shell scripts, a comment may also explain what the code does. Do not add comments that merely restate adjacent code one-to-one.
- Update docs when behavior, settings, public APIs, setup steps, or supported versions change, including when a documented feature's behavior changes or a new user-facing feature is added.

## Testing and QA

- For complex or long tests, add a docstring when a longer test name would improve readability or maintainability.
- When separate tests cover different cases of the same feature, share almost identical database preparation, and primarily vary in input or expected outcome, group them in one test method with subTest. This is especially encouraged, but not limited to, TransactionTestCase tests, where it avoids repeated expensive database setup and teardown. Keep each subtest's setup explicit and independent, and retain separate test methods when cases exercise genuinely distinct behavior. Leave one blank line immediately before each with self.subTest(...): call.
- Prefer method decorators for context managers that apply to the entire test method and would otherwise create unnecessary nesting, unless decorator ordering conflicts or the context manager requires data unavailable when the method is defined.
- During development, run the focused tests and test suites directly affected by the change instead of routinely running the full test suite. For example, run the relevant `test_admin` tests for admin changes and Selenium tests for JavaScript or browser-facing changes.
- Changes to core logic, model validation, migrations, database schema, tenant isolation, authentication, or shared behavior require all affected package and integration suites.
- Before pushing a branch or opening a pull request for a behavior-affecting change, verify that the full test suite has passed at least once for the current branch after its latest code, test, dependency, migration, or configuration change. If no successful full-suite result is available, stop, report the missing verification, and do not push or open the pull request. If the full suite cannot run, report the blocker and wait for user direction.
- Prefer in-process tests so coverage tools can measure changed code.

## Django Notes

- Preserve multi-tenant isolation and object-level permissions for organizations, devices, templates, VPNs, credentials, commands, maps, and IP/subnet data.
- Be careful with authentication, authorization, queryset filtering, serializers, admin behavior, cache invalidation, signals, Celery tasks, and websocket updates.
- When changing APIs, include tests for permissions, validation, filtering, pagination, and organization boundaries.
- Changes to swappable models, tenant isolation, authentication flows, or admin/REST authorization must be covered by both the default package suite and the `SAMPLE_APP=1` integration suite. Add a `tests/openwisp2` regression test when the affected feature has no existing sample-app analogue.
- When a Celery task, notification, cache invalidation, or other external side effect depends on database changes made in the current transaction, register it with `transaction.on_commit()` so it cannot run against uncommitted or rolled-back data. Do not defer work that must run before commit or is independent of the transaction. Test commit and rollback behavior, and account for Celery eager execution in tests versus asynchronous execution in production.

## Security Notes

- Watch for cross-organization data leaks, command execution issues, unsafe file paths, unsafe redirects, insecure credentials, and secrets.
- Preserve validation around templates, VPN/PKI material, SSH credentials, device commands, uploaded files, URLs, and subnet/IP data.

## Troubleshooting

- If documentation and CI commands differ, use CI for verification and report the exact documentation path, CI workflow path, and differing commands. Do not change the documentation until the user explicitly chooses one of these actions: update the named documentation file in the current change because the divergence was caused by that change, or leave it unchanged for a separate follow-up. Never decide that scope distinction independently.
