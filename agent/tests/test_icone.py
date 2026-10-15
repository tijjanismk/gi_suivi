"""Le clic sur l'icône ouvre la page dans un fil à part : une ouverture lente ne bloque plus
les clics suivants."""

import threading

from gisuivi_agent.icone import ouvrir


def test_ouverture_lente_ne_bloque_pas():
    libere = threading.Event()
    ouverts = []

    def lent(url):
        ouverts.append(url)
        libere.wait(5)

    premier = ouvrir("https://suivi/moi", lent)
    second = ouvrir("https://suivi/moi", lent)  # rendu aussitôt, malgré le premier en cours
    second.join(0.5)
    assert ouverts == ["https://suivi/moi", "https://suivi/moi"]
    libere.set()
    premier.join(1)
    second.join(1)


def test_echec_puis_webbrowser(monkeypatch, caplog):
    vus = []
    monkeypatch.setattr("webbrowser.open", lambda url: vus.append(url))

    def echoue(_url):
        raise OSError("refus")

    ouvrir("https://suivi/moi", echoue).join(1)
    assert vus == ["https://suivi/moi"] and "essai par webbrowser" in caplog.text

    def rate(_url):
        raise RuntimeError("non")

    monkeypatch.setattr("webbrowser.open", rate)
    ouvrir("https://suivi/moi", echoue).join(1)
    assert "impossible : non" in caplog.text
