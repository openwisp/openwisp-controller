# AGENTS.md

## Project Overview

`openwisp-controller` is the OpenWISP Django app for device configuration management, VPN provisioning, shell/SSH commands, PKI integration, maps, and IPAM integration.

Core code lives in `openwisp_controller/`:

- `config/` handles device configuration, templates, VPNs, commands, and related APIs.
- `connection/` handles device credentials, connectors, SSH operations, and command execution.
- `pki/`, `geo/`, and `subnet_division/` integrate x509, geographic data, and subnet/IPAM behavior.
- Tests live in `openwisp_controller/tests/` and `tests/`.

## Source of Truth

- Use `docs/developer/installation.rst` and `docs/developer/index.rst` for local setup, services, and baseline test commands.
- Use `.github/workflows/ci.yml` for CI-tested dependencies, QA/test commands, env vars, and supported Python/Django versions.
- Use GitHub issue/PR templates when asked to open issues or PRs.

If instructions conflict, repository config and CI workflows win first, official docs next, and this file is supplemental.

## Development Notes

- Keep changes focused. Avoid unrelated refactors and formatting churn.
- Preserve public APIs, migrations, swappable models, VPN backends, connector behavior, and integration points unless explicitly required.
- Mark user-facing strings for translation with Django i18n helpers in Django code.
- Avoid unnecessary blank lines inside function and method bodies.
- Update docs when behavior, settings, public APIs, setup steps, or supported versions change.

## Testing and QA

- Add or update tests for every behavior change.
- For bug fixes, write the regression test first, run it against the unfixed code, confirm it fails for the expected reason, then implement the fix.
- Use targeted tests while iterating, then run the documented full test command before considering the change complete.
- Run `openwisp-qa-format` after editing when available.
- Run `./run-qa-checks` when present. Treat failures as blocking unless confirmed unrelated and reported.
- Prefer in-process tests so coverage tools can measure changed code.

## Django Notes

- Preserve tenant isolation and object-level permissions for organizations, devices, templates, VPNs, credentials, commands, maps, and IP/subnet data.
- Be careful with authentication, authorization, queryset filtering, serializers, admin behavior, cache invalidation, signals, Celery tasks, and websocket updates.
- When changing APIs, include tests for permissions, validation, filtering, pagination, and tenant boundaries.

## Security Notes

- Watch for cross-tenant data leaks, command execution issues, unsafe file paths, unsafe redirects, insecure credentials, and secrets.
- Preserve validation around templates, VPN/PKI material, SSH credentials, device commands, uploaded files, URLs, and subnet/IP data.
- Write comments and docstrings only when they explain why code is shaped a certain way. Put comments before the relevant code block instead of scattering them inside it.

## Troubleshooting

- If setup, QA, or tests fail, check docs first, then compare with CI. If commands diverge, follow CI.
