"""Transforme la suite d'observations en segments d'activité.

Règles (blueprint GI-SUIVI, 7.1 et 7.3) :
- observations identiques (application, fichier) fusionnées en un segment ;
- segment clos au changement de fenêtre/fichier, au changement d'état de
  session, ou quand il atteint la durée maximale (5 min par défaut) ; il prend
  fin à l'instant de l'observation qui le clôt, si bien que les segments se
  suivent sans trou ;
- au-delà du seuil d'inactivité (5 min), le temps depuis la dernière action
  réelle est retiré : le segment est clos à l'instant de la dernière action,
  et un segment INACTIF couvre la suite ;
- écran verrouillé, veille, session fermée : INACTIF ;
- un brouillon (fichier sans chemin, ex. Document1) suivi d'un fichier
  enregistré dans la même fenêtre est fusionné sous le nom final ;
- fichiers techniques ignorés ; pour les navigateurs, aucun titre conservé.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta

from .types import Etat, EtatSession, Observation, Parametres, Segment


def _normaliser(obs: Observation, p: Parametres) -> Observation:
    """Filtres : navigateurs sans titre (sauf le nom d'un PDF), fichiers techniques ignorés."""
    app = obs.application.lower()
    if app in p.navigateurs:
        pdf = obs.fichier if obs.fichier and obs.fichier.lower().endswith(".pdf") else None
        return Observation(
            obs.instant,
            obs.application,
            pdf,
            None,
            obs.inactif_depuis_s,
            obs.session,
            obs.fenetre_id,
        )
    if obs.fichier:
        nom = obs.fichier.lower()
        if nom.startswith(p.prefixes_ignores) or nom.endswith(p.extensions_ignorees):
            return Observation(
                obs.instant,
                obs.application,
                None,
                None,
                obs.inactif_depuis_s,
                obs.session,
                obs.fenetre_id,
            )
    return obs


class Segmenteur:
    """État de segmentation : on lui donne des observations, il rend des segments clos."""

    def __init__(self, parametres: Parametres | None = None) -> None:
        self.p = parametres or Parametres()
        self.courant: Segment | None = None
        self.derniere_action: datetime | None = None
        # Segments clos mais encore retaillables : une inactivité détectée plus
        # tard peut retirer du temps qui les chevauche (clôture forcée à 5 min).
        self.en_attente: list[Segment] = []

    # -- API principale -----------------------------------------------------

    def observer(self, obs: Observation) -> list[Segment]:
        """Intègre une observation ; rend les segments clos par cette observation."""
        obs = _normaliser(obs, self.p)
        seuil = timedelta(seconds=self.p.seuil_inactivite_s)
        action = obs.instant - timedelta(seconds=obs.inactif_depuis_s)

        session_inactive = obs.session != EtatSession.ACTIVE
        inactif = timedelta(seconds=obs.inactif_depuis_s) >= seuil

        if session_inactive or inactif:
            # Fin de l'activité réelle : l'instant de la dernière action
            fin_activite = action if inactif else obs.instant
            if self.courant and self.courant.etat == Etat.ACTIF:
                self.courant.fin = (
                    obs.instant
                )  # _retailler retire ensuite ce qui suit la dernière action
                self.en_attente.append(self._clore())
            self._retailler(fin_activite)
            if self.courant is None:
                self.courant = Segment(
                    fin_activite,
                    obs.instant,
                    obs.application,
                    None,
                    None,
                    Etat.INACTIF,
                    obs.fenetre_id,
                )
            else:
                self.courant.fin = obs.instant
            return self._liberer(obs.instant)

        # Session active, utilisateur actif
        self.derniere_action = action
        if self.courant and self.courant.etat == Etat.INACTIF:
            self.courant.fin = obs.instant
            self.en_attente.append(self._clore())

        if self.courant is None:
            self.courant = self._nouveau(obs)
            return self._liberer(obs.instant)

        if self._meme_contexte(self.courant, obs):
            self.courant.fin = obs.instant
        elif self._brouillon_enregistre(self.courant, obs):
            # Document1 -> Courrier.docx dans la même fenêtre : début gardé, nom final pris
            self.courant.fichier, self.courant.chemin = obs.fichier, obs.chemin
            self.courant.fin = obs.instant
        else:
            # L'intervalle depuis l'observation précédente revient au contexte qu'elle montrait :
            # sans cela, chaque changement de fenêtre perd un intervalle, et un passage vu une
            # seule fois (moins d'un intervalle) disparaît.
            self.courant.fin = obs.instant
            self.en_attente.append(self._clore())
            self.courant = self._nouveau(obs)

        if self.courant.duree_s >= self.p.duree_max_segment_s:
            seg = self._clore()
            self.en_attente.append(seg)
            self.courant = Segment(
                seg.fin,
                seg.fin,
                seg.application,
                seg.fichier,
                seg.chemin,
                Etat.ACTIF,
                seg.fenetre_id,
            )
        return self._liberer(obs.instant)

    def clore_tout(self, instant: datetime | None = None) -> list[Segment]:
        """À l'arrêt de l'agent ou à la fermeture de session : rend tout, sans attendre."""
        if self.courant is not None:
            if instant is not None:
                self.courant.fin = max(
                    self.courant.debut,
                    min(instant, self.courant.fin) if self.courant.etat == Etat.ACTIF else instant,
                )
            self.en_attente.append(self._clore())
        rendus = [s for s in self.en_attente if s.duree_s > 0]
        self.en_attente = []
        return rendus

    # -- Internes -----------------------------------------------------------

    def _nouveau(self, obs: Observation) -> Segment:
        return Segment(
            obs.instant,
            obs.instant,
            obs.application,
            obs.fichier,
            obs.chemin,
            Etat.ACTIF,
            obs.fenetre_id,
        )

    def _clore(self) -> Segment:
        seg = self.courant
        self.courant = None
        return seg

    def _retailler(self, fin_activite: datetime) -> None:
        """Retire des segments ACTIF en attente ce qui suit la dernière action réelle."""
        retailles: list[Segment] = []
        for seg in self.en_attente:
            if seg.etat == Etat.ACTIF and seg.fin > fin_activite:
                seg.fin = max(seg.debut, fin_activite)
            if seg.duree_s > 0 or seg.etat == Etat.INACTIF:
                retailles.append(seg)
        self.en_attente = retailles

    def _liberer(self, maintenant: datetime) -> list[Segment]:
        """Rend les segments assez anciens pour ne plus pouvoir être retaillés."""
        seuil = timedelta(seconds=self.p.seuil_inactivite_s)
        prets = [
            s for s in self.en_attente if s.etat == Etat.INACTIF or maintenant - s.fin >= seuil
        ]
        self.en_attente = [s for s in self.en_attente if s not in prets]
        return [s for s in prets if s.duree_s > 0]

    @staticmethod
    def _meme_contexte(seg: Segment, obs: Observation) -> bool:
        return (
            seg.application.lower() == obs.application.lower()
            and seg.fichier == obs.fichier
            and seg.chemin == obs.chemin
        )

    @staticmethod
    def _brouillon_enregistre(seg: Segment, obs: Observation) -> bool:
        # Brouillon enregistré (Document1 -> Courrier.docx), ou chemin trouvé avec retard par
        # l'énumération des fichiers ouverts (ADR 0003) : même fenêtre, le chemin arrive.
        return (
            seg.application.lower() == obs.application.lower()
            and seg.chemin is None
            and obs.chemin is not None
            and seg.fenetre_id is not None
            and seg.fenetre_id == obs.fenetre_id
        )


def segmenter(
    observations: Iterable[Observation], parametres: Parametres | None = None
) -> Iterator[Segment]:
    """Version fonctionnelle : une suite d'observations -> les segments, le dernier inclus."""
    s = Segmenteur(parametres)
    derniere = None
    for obs in observations:
        derniere = obs
        yield from s.observer(obs)
    if derniere is not None:
        yield from s.clore_tout(derniere.instant)


def filtrer_actifs(segments: Iterable[Segment], duree_min_s: float = 1.0) -> list[Segment]:
    """Ne garde que les segments ACTIF d'une durée significative."""
    return [s for s in segments if s.etat == Etat.ACTIF and s.duree_s >= duree_min_s]
