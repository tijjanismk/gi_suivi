from django.apps import AppConfig


class SuiviConfig(AppConfig):
    name = "suivi"
    verbose_name = "Suivi d'activité"

    def ready(self) -> None:
        from suivi import signals  # noqa: F401 — branche les demandes de recalcul
