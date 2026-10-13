"""Choix du module de réglages : les tâches planifiées du serveur lisent `.env`."""

from config.demarrage import module_reglages


def test_lu_dans_env(tmp_path):
    f = tmp_path / ".env"
    f.write_text("SECRET_KEY=x\nDJANGO_SETTINGS_MODULE=config.settings.prod\n", encoding="ascii")
    assert module_reglages(f, "config.settings.dev") == "config.settings.prod"


def test_bom_espaces_et_guillemets(tmp_path):
    f = tmp_path / ".env"
    f.write_text(' DJANGO_SETTINGS_MODULE = "config.settings.prod" \n', encoding="utf-8-sig")
    assert module_reglages(f, "config.settings.dev") == "config.settings.prod"


def test_absent_ou_vide(tmp_path):
    assert module_reglages(tmp_path / "absent", "config.settings.dev") == "config.settings.dev"
    f = tmp_path / ".env"
    contenu = "# DJANGO_SETTINGS_MODULE=config.settings.prod\nDJANGO_SETTINGS_MODULE=\n"
    f.write_text(contenu, encoding="ascii")
    assert module_reglages(f, "config.settings.dev") == "config.settings.dev"
