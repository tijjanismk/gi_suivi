"""AV09, ADR 0016 — le serveur MCP sous /mcp/, joué comme Uvicorn le joue (cycle de vie, puis
requêtes HTTP) : monté à côté de Django, identité des écrans (Negotiate), lecture pour la
consultation des avis, écriture pour GI-Direction et GI-Offres, attribuée au ticket."""

from __future__ import annotations

import json

import anyio
import pytest
from asgiref.sync import async_to_sync
from django.test import override_settings

from avis import outils_mcp
from avis.models import Proposition
from config import serveur_mcp
from identite.models import Utilisateur
from moteur.avis.filtres import CLES

pytestmark = pytest.mark.django_db

NEGOTIATE = {
    "IDENTITE_SOURCE": "negotiate",
    "IDENTITE_AUTHENTIFICATEUR_NEGOTIATE": "tests.test_serveur_mcp.faux_authentifier",
    "IDENTITE_LECTEUR_GROUPES": "tests.test_serveur_mcp.groupes_fictifs",
}
VERSION = "2025-06-18"
INITIALISER = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": VERSION,
        "capabilities": {},
        "clientInfo": {"name": "essai", "version": "0"},
    },
}
LISTER = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}


def faux_authentifier(entete):
    return {
        "Negotiate TICKET-OFFRES": ("GICONSEILS\\Offres", "MUTUELLE"),
        "Negotiate TICKET-VISIONNEUSE": ("GICONSEILS\\visionneuse", None),
        "Negotiate TICKET-COMPTABLE": ("GICONSEILS\\comptable", None),
    }.get(entete, (None, None))


def groupes_fictifs(login: str) -> list[str]:
    return {
        "giconseils\\offres": ["GI-Offres", "Utilisateurs du domaine"],
        "giconseils\\visionneuse": ["GI-Direction-Lecture", "Utilisateurs du domaine"],
    }.get(login, ["Utilisateurs du domaine"])


async def faux_django(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"django"})


async def requete(app, message=None, ticket=None, chemin="/mcp/", **entetes):
    """Une requête HTTP complète : (statut, en-têtes, corps)."""
    corps = json.dumps(message).encode() if message is not None else b""
    fini = anyio.Event()
    lu = False
    reponse = {"statut": None, "entetes": {}, "corps": b""}

    async def recevoir():
        nonlocal lu
        if not lu:
            lu = True
            return {"type": "http.request", "body": corps, "more_body": False}
        await fini.wait()
        return {"type": "http.disconnect"}

    async def envoyer(m):
        if m["type"] == "http.response.start":
            reponse["statut"] = m["status"]
            reponse["entetes"] = {k.decode().lower(): v.decode() for k, v in m["headers"]}
        elif m["type"] == "http.response.body":
            reponse["corps"] += m.get("body", b"")
            if not m.get("more_body"):
                fini.set()

    h = {
        "host": "localhost",
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
    }
    if message is not None and message.get("method") != "initialize":
        h["mcp-protocol-version"] = VERSION
    if ticket:
        h["authorization"] = f"Negotiate {ticket}"
    h.update({k.replace("_", "-"): v for k, v in entetes.items()})
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": "POST" if message is not None else "GET",
        "scheme": "http",
        "path": chemin,
        "raw_path": chemin.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [(k.encode(), v.encode()) for k, v in h.items()],
        "client": ("127.0.0.1", 50000),
        "server": ("localhost", 80),
    }
    await app(scope, recevoir, envoyer)
    return reponse["statut"], reponse["entetes"], reponse["corps"]


def jouer(scenario):
    """Démarre l'application comme Uvicorn (cycle de vie ASGI), joue le scénario, l'arrête."""
    app = serveur_mcp.aiguiller(faux_django, serveur_mcp.creer_application())

    async def tout():
        envoi, reception = anyio.create_memory_object_stream(4)
        etapes: list[str] = []
        demarre, arrete = anyio.Event(), anyio.Event()

        async def envoyer(m):
            etapes.append(m["type"])
            (demarre if m["type"].startswith("lifespan.startup") else arrete).set()

        portee = {"type": "lifespan", "asgi": {"version": "3.0"}, "state": {}}
        async with anyio.create_task_group() as tg:
            tg.start_soon(app, portee, reception.receive, envoyer)
            await envoi.send({"type": "lifespan.startup"})
            await demarre.wait()
            assert etapes == ["lifespan.startup.complete"]
            try:
                return await scenario(app)
            finally:
                await envoi.send({"type": "lifespan.shutdown"})
                await arrete.wait()

    return async_to_sync(tout)()


def appel(nom, arguments=None, ident=2):
    return {
        "jsonrpc": "2.0",
        "id": ident,
        "method": "tools/call",
        "params": {"name": nom, "arguments": arguments or {}},
    }


def resultat(corps: bytes) -> dict:
    """Le dict rendu par l'outil (texte JSON du premier contenu)."""
    reponse = json.loads(corps)
    return json.loads(reponse["result"]["content"][0]["text"])


def test_les_outils_sont_enregistres_tels_quels():
    outils = {t.name: t for t in async_to_sync(serveur_mcp.creer_serveur().list_tools)()}
    assert list(outils) == [f.__name__ for f in outils_mcp.OUTILS]
    for fonction in outils_mcp.OUTILS:
        outil = outils[fonction.__name__]
        assert outil.description == fonction.__doc__
        assert "ctx" not in outil.input_schema["properties"]
        assert outil.annotations.read_only_hint is (fonction.__name__ not in serveur_mcp.ECRITURES)
    # écritures attribuées par le serveur, jamais par Claude
    assert "par" not in outils["creer_proposition"].input_schema["properties"]
    assert "par" not in outils["proposer_terme"].input_schema["properties"]
    # le filtre de rechercher_missions, clé par clé
    proprietes = outils["rechercher_missions"].input_schema["properties"]
    assert set(proprietes) == CLES | {"texte", "limite"}


def test_cles_du_filtre_suivent_le_moteur():
    assert set(serveur_mcp.CLES_FILTRE) == CLES


def test_aiguillage_entre_django_et_mcp():
    assert serveur_mcp.vers_mcp("/mcp/") and serveur_mcp.vers_mcp("/mcp")
    assert not serveur_mcp.vers_mcp("/mcpx") and not serveur_mcp.vers_mcp("/avis/")

    async def scenario(app):
        return await requete(app, chemin="/avis/")

    statut, _, corps = jouer(scenario)
    assert (statut, corps) == (200, b"django")


@override_settings(**NEGOTIATE)
def test_sans_ticket_le_serveur_reclame_negotiate():
    async def scenario(app):
        return [
            await requete(app, INITIALISER),
            await requete(app, INITIALISER, ticket="N-IMPORTE-QUOI"),
        ]

    for statut, entetes, _ in jouer(scenario):
        assert statut == 401 and entetes["www-authenticate"] == "Negotiate"
    assert not Utilisateur.objects.exists()


@override_settings(**NEGOTIATE)
def test_ticket_accepte_initialise_et_liste_les_outils():
    async def scenario(app):
        return [
            await requete(app, INITIALISER, "TICKET-OFFRES"),
            await requete(app, LISTER, "TICKET-OFFRES"),
        ]

    (statut, entetes, corps), (statut_liste, _, liste) = jouer(scenario)
    assert statut == 200 and entetes["www-authenticate"] == "Negotiate MUTUELLE"
    initialise = json.loads(corps)["result"]
    assert initialise["protocolVersion"] == VERSION
    assert initialise["serverInfo"]["name"] == "gi-conseils"
    assert statut_liste == 200
    noms = [t["name"] for t in json.loads(liste)["result"]["tools"]]
    assert noms == [f.__name__ for f in outils_mcp.OUTILS]


@override_settings(**NEGOTIATE)
def test_ecriture_attribuee_a_la_personne_du_ticket():
    champs = {"reference": "AMI-2026-001", "objet": "Étude d'un seuil", "type": "AMI"}
    # un `par` venu de Claude est ignoré : seul le ticket dit qui écrit
    message = appel("creer_proposition", {"champs": champs, "par": "quelqu'un d'autre"})

    async def scenario(app):
        return await requete(app, message, "TICKET-OFFRES")

    statut, _, corps = jouer(scenario)
    assert statut == 200
    rendu = resultat(corps)
    p = Proposition.objects.get(pk=rendu["proposition_id"])
    assert p.proposee_par == "giconseils\\offres" and p.origine == "claude"
    assert p.champs_extraits["reference"] == "AMI-2026-001"


@override_settings(**NEGOTIATE)
def test_consultation_seule_lit_sans_ecrire():
    lire = appel("lister_referentiel", {"table": "domaines"})
    ecrire = appel("creer_proposition", {"champs": {}})

    async def scenario(app):
        return [
            await requete(app, lire, "TICKET-VISIONNEUSE"),
            await requete(app, ecrire, "TICKET-VISIONNEUSE"),
            await requete(app, lire, "TICKET-COMPTABLE"),
        ]

    lecture, ecriture, hors_groupes = (resultat(corps) for _, _, corps in jouer(scenario))
    assert "erreur" not in lecture
    assert ecriture == {"erreur": "réservé aux membres de GI-Direction, GI-Offres"}
    assert hors_groupes["erreur"].startswith("réservé aux membres de GI-Direction, GI-Offres")
    assert not Proposition.objects.exists()


def test_filtre_detaille_transmis_au_moteur():
    # mode « dev » des tests : utilisateur fictif de GI-Direction, sans ticket
    async def scenario(app):
        return [
            await requete(app, appel("rechercher_missions", {"annee_min": 2010})),
            await requete(app, appel("rechercher_missions", {"natures": ["XYZ"]})),
        ]

    trouve, refuse = (resultat(corps) for _, _, corps in jouer(scenario))
    assert trouve == {"total": 0, "missions": []}
    assert refuse["erreur"].startswith("filtre : ")


def test_page_web_et_nom_inconnu_refuses():
    async def scenario(app):
        return [
            await requete(app, INITIALISER, origin="http://app.giconseils.local"),
            await requete(app, INITIALISER, host="ailleurs.exemple"),
        ]

    (origine, _, _), (hote, _, _) = jouer(scenario)
    assert (origine, hote) == (403, 421)


def test_protocole_2026_a_requete_autonome():
    """2026-07-28 : pas de poignée de main, la version et la méthode en en-têtes (le pont les
    recopie du message)."""
    message = appel("lister_referentiel", {"table": "domaines"}, ident=7)
    message["params"]["_meta"] = {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {},
    }

    async def scenario(app):
        return await requete(
            app,
            message,
            mcp_protocol_version="2026-07-28",
            mcp_method="tools/call",
            mcp_name="lister_referentiel",
        )

    statut, _, corps = jouer(scenario)
    assert statut == 200
    assert "erreur" not in resultat(corps)


def test_point_d_entree_asgi():
    from config import asgi

    assert callable(asgi.application)
