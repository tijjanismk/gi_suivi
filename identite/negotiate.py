"""Authentification Kerberos faite par l'application elle-même, avec le SSPI de Windows (pywin32).

Pourquoi : derrière IIS + ARR, l'identité authentifiée par IIS n'est pas disponible au moment où la
règle de réécriture pose les en-têtes (mode noyau), et le mode utilisateur refuse les tickets des
postes. IIS laisse donc passer la requête avec son en-tête `Authorization: Negotiate <ticket>`, et
c'est le service — qui tourne sous `svc-application`, le compte qui porte les SPN `HTTP/suivi…` —
qui valide le ticket et en tire `GICONSEILS\\login`. Kerberos seul : un ticket NTLM (plusieurs
allers-retours) est refusé, comme IIS le faisait (ADR 0007).
"""

from __future__ import annotations

import base64
import binascii
import logging

log = logging.getLogger(__name__)

PREFIXE = "Negotiate "


def authentifier(entete_authorization: str | None) -> tuple[str | None, str | None]:
    """Valide l'en-tête `Authorization` d'une requête.

    Rend `(login, jeton_de_reponse)` : `login` = `DOMAINE\\compte` si le ticket est accepté, sinon
    `None` ; `jeton_de_reponse` = jeton base64 à renvoyer dans `WWW-Authenticate` (authentification
    mutuelle), s'il y en a un."""
    if not entete_authorization or not entete_authorization.startswith(PREFIXE):
        return None, None
    try:
        jeton = base64.b64decode(entete_authorization[len(PREFIXE) :].strip(), validate=True)
    except (binascii.Error, ValueError):
        log.info("En-tête Negotiate illisible (base64).")
        return None, None
    try:
        import sspi  # pywin32 (win32/lib/sspi.py)
        import sspicon
        import win32security
    except ImportError:  # hors Windows : rien à valider
        log.error("pywin32 absent : l'authentification Negotiate est impossible sur ce système.")
        return None, None

    serveur = sspi.ServerAuth("Negotiate")
    try:
        err, sortie = serveur.authorize(jeton)
    except win32security.error as e:
        # ticket pour un autre service, horloge décalée, compte inconnu… : refus, sans trace de pile
        log.info("Ticket Kerberos refusé : %s", getattr(e, "strerror", e))
        return None, None
    if err != 0:
        # SEC_I_CONTINUE_NEEDED : échange en plusieurs étapes (NTLM) — refusé, Kerberos seul
        log.info("Negotiate incomplet (NTLM ?) : refusé, Kerberos requis.")
        return None, None
    login = serveur.ctxt.QueryContextAttributes(sspicon.SECPKG_ATTR_NAMES)
    reponse = None
    if sortie and sortie[0].Buffer:
        reponse = base64.b64encode(sortie[0].Buffer).decode("ascii")
    return (login or None), reponse
