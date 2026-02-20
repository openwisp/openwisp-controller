from __future__ import annotations

from django.db.migrations.executor import MigrationLoader
from django.test import SimpleTestCase


class TestMigrationGraphIntegrity(SimpleTestCase):
    def test_all_migration_states_render_apps(self) -> None:
        """
        Fail fast if any migration target produces an invalid historical StateApps.

        This catches missing dependencies / broken swappable references that only
        show up when Django renders historical models.
        """
        loader = MigrationLoader(None, ignore_no_migrations=True)

        failures: list[str] = []
        for key in sorted(loader.graph.nodes.keys()):
            try:
                state = loader.project_state([key])
                _ = state.apps  # triggers StateApps rendering
            except Exception as e:
                failures.append(f"{key[0]}.{key[1]} -> {type(e).__name__}: {e}")

        if failures:
            self.fail(
                "Some migration states cannot be rendered:\n" + "\n".join(failures)
            )
