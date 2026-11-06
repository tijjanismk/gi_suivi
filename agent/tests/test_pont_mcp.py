"""Pont MCP du poste (ADR 0016) : en-têtes du transport HTTP de MCP, lecture des réponses (JSON,
flux SSE), erreurs dites à Claude Desktop, entrée dans claude_desktop_config.json. Le serveur est
simulé : ni réseau ni Kerberos ici."""

import io
import json

import pytest
from gisuivi_agent.pont_mcp import (
    NOM_SERVEUR,
    Pont,
    ajouter_a_claude,
    entree_claude,
    lire_sse,
    servir,
    url_mcp,
    valeur_d_entete,
)

URL = "https://app.giconseils.local/mcp/"
INITIALISER = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
}


class Reponse:
    def __init__(self, statut=200, corps=b"", type_="application/json", entetes=None):
        self.status_code = statut
        self.content = corps if isinstance(corps, bytes) else json.dumps(corps).encode()
        self.headers = {"Content-Type": type_, **(entetes or {})}
        self.fermee = False

    def iter_lines(self):
        return iter(self.content.splitlines())

    def close(self):
        self.fermee = True


class Session:
    def __init__(self, *reponses):
        self.reponses = list(reponses)
        self.envois = []

    def post(self, url, data, headers, timeout, stream):
        self.envois.append({"url": url, "corps": json.loads(data), "entetes": headers})
        reponse = self.reponses.pop(0)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


def appel(nom, ident=2, **params):
    return {
        "jsonrpc": "2.0",
        "id": ident,
        "method": "tools/call",
        "params": {"name": nom, "arguments": {}, **params},
    }


def test_version_negociee_puis_recopiee_en_entete():
    accord = {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-06-18"}}
    note = {"jsonrpc": "2.0", "id": 2, "result": {"content": []}}
    session = Session(Reponse(corps=accord), Reponse(corps=note))
    pont = Pont(URL, session)

    assert pont.relayer(INITIALISER) == [accord]
    assert pont.relayer(appel("simuler_avis")) == [note]

    initialisation, outil = (e["entetes"] for e in session.envois)
    assert "Mcp-Protocol-Version" not in initialisation
    assert initialisation["Mcp-Method"] == "initialize"
    assert outil["Mcp-Protocol-Version"] == "2025-06-18"
    assert (outil["Mcp-Method"], outil["Mcp-Name"]) == ("tools/call", "simuler_avis")
    assert outil["Accept"] == "application/json, text/event-stream"
    assert session.envois[1] == {"url": URL, "corps": appel("simuler_avis"), "entetes": outil}


def test_protocole_2026_la_version_vient_du_message():
    meta = {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}
    message = appel("lister_referentiel", _meta=meta)
    session = Session(Reponse(corps={"jsonrpc": "2.0", "id": 2, "result": {}}))
    Pont(URL, session).relayer(message)
    assert session.envois[0]["entetes"]["Mcp-Protocol-Version"] == "2026-07-28"


def test_valeur_d_entete():
    assert valeur_d_entete("simuler_avis") == "simuler_avis"
    assert valeur_d_entete("détail") == "=?base64?ZMOpdGFpbA==?="
    assert valeur_d_entete(" bord").startswith("=?base64?")


def test_notification_acceptee_rien_a_rendre():
    reponse = Reponse(statut=202, corps=b"", type_="")
    pont = Pont(URL, Session(reponse))
    assert pont.relayer({"jsonrpc": "2.0", "method": "notifications/initialized"}) == []
    assert reponse.fermee


def test_flux_sse_lu_en_utf8():
    flux = (
        'event: message\ndata: {"jsonrpc": "2.0", "method": "notifications/progress"}\n\n'
        'event: message\ndata: {"jsonrpc": "2.0", "id": 2, "result": {"texte": "Ségou"}}\n\n'
    ).encode()
    session = Session(Reponse(corps=flux, type_="text/event-stream"))
    messages = Pont(URL, session).relayer(appel("detail_mission"))
    assert [m.get("id") for m in messages] == [None, 2]
    assert messages[1]["result"]["texte"] == "Ségou"
    assert list(lire_sse(["data: 1", "", "data: [2,", "data: 3]"])) == [1, [2, 3]]


def test_serveur_injoignable_dit_a_claude():
    pont = Pont(URL, Session(OSError("connexion refusée"), OSError("connexion refusée")))
    [erreur] = pont.relayer(appel("simuler_avis", ident=9))
    assert erreur["id"] == 9 and erreur["error"]["code"] == -32603
    assert "injoignable" in erreur["error"]["message"] and URL in erreur["error"]["message"]
    # une notification n'attend pas de réponse
    assert pont.relayer({"jsonrpc": "2.0", "method": "notifications/initialized"}) == []


def test_identite_refusee_expliquee():
    refus = Reponse(statut=401, corps=b"Kerberos requis.", type_="text/plain")
    [erreur] = Pont(URL, Session(refus)).relayer(appel("simuler_avis"))
    assert "401" in erreur["error"]["message"] and "GICONSEILS" in erreur["error"]["message"]


def test_erreur_json_rpc_du_serveur_relayee_telle_quelle():
    erreur = {"jsonrpc": "2.0", "id": 2, "error": {"code": -32602, "message": "outil inconnu"}}
    assert Pont(URL, Session(Reponse(statut=400, corps=erreur))).relayer(appel("x")) == [erreur]


def test_identifiant_de_session_recopie():
    session = Session(
        Reponse(corps={"jsonrpc": "2.0", "id": 1, "result": {}}, entetes={"Mcp-Session-Id": "s1"}),
        Reponse(statut=202, corps=b"", type_=""),
    )
    pont = Pont(URL, session)
    pont.relayer(INITIALISER)
    pont.relayer({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert session.envois[1]["entetes"]["Mcp-Session-Id"] == "s1"


def test_boucle_stdio():
    entree = [
        b'{"jsonrpc": "2.0", "method": "notifications/initialized"}\n',
        b"\n",
        b"{pas du json\n",
        b'{"jsonrpc": "2.0", "id": 4, "method": "ping"}\n',
    ]
    session = Session(
        Reponse(statut=202, corps=b"", type_=""),
        Reponse(corps={"jsonrpc": "2.0", "id": 4, "result": {"note": "élevée"}}),
    )
    sortie = io.BytesIO()
    servir(Pont(URL, session), entree, sortie)
    lignes = sortie.getvalue().split(b"\n")
    assert lignes[-1] == b"" and len(lignes) == 3
    illisible, pong = (json.loads(ligne) for ligne in lignes[:2])
    assert illisible["id"] is None and illisible["error"]["code"] == -32700
    assert pong == {"jsonrpc": "2.0", "id": 4, "result": {"note": "élevée"}}
    assert "élevée".encode() in lignes[1]


def test_adresse_du_serveur():
    assert url_mcp("https://app.giconseils.local/") == URL
    assert url_mcp(None) == URL


def test_entree_claude_desktop():
    exe = r"C:\Program Files\GI-CONSEILS\GiSuivi\pont-mcp.exe"
    assert entree_claude(exe) == {"command": exe, "args": []}
    assert entree_claude("python.exe", "pont-mcp.py") == {
        "command": "python.exe",
        "args": ["pont-mcp.py"],
    }


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
def test_ajout_a_claude_garde_le_reste(tmp_path, bom):
    chemin = tmp_path / "Claude" / "claude_desktop_config.json"
    chemin.parent.mkdir()
    autre = {"command": "npx", "args": ["autre-serveur"]}
    chemin.write_bytes(bom + json.dumps({"mcpServers": {"autre": autre}, "theme": "x"}).encode())
    entree = entree_claude(r"C:\Program Files\GI-CONSEILS\GiSuivi\pont-mcp.exe")

    assert ajouter_a_claude(chemin, entree) is True
    config = json.loads(chemin.read_text(encoding="utf-8"))
    assert config == {"mcpServers": {"autre": autre, NOM_SERVEUR: entree}, "theme": "x"}
    assert ajouter_a_claude(chemin, entree) is False


def test_ajout_a_claude_sans_fichier(tmp_path):
    chemin = tmp_path / "Claude" / "claude_desktop_config.json"
    entree = entree_claude("pont-mcp.exe")
    assert ajouter_a_claude(chemin, entree) is True
    assert json.loads(chemin.read_text(encoding="utf-8")) == {"mcpServers": {NOM_SERVEUR: entree}}
