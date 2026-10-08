"""Jeu de démonstration pour montrer les écrans à la direction (critère T02 : « validée sur des
données de test »). Deux semaines d'activité plausible, déterministe (même graine → mêmes chiffres).

    manage.py suivi_jeu_demo            # crée (idempotent : ne double rien)
    manage.py suivi_jeu_demo --effacer  # retire tout le jeu (postes DEMO-*, employés S-DEMO-*)
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from moteur.suivi.classement import normaliser_chemin
from suivi.models import Dossier, Employe, Poste, Racine, Segment

RACINE_MISSIONS = r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS"
RACINE_AVIS = r"\\AD-SERVEUR\GIC\AVIS"
PERSONNES = [
    ("S-DEMO-1", "giconseils\\a.traore", "Awa Traoré", "DEMO-ETUDES-01"),
    ("S-DEMO-2", "giconseils\\m.keita", "Moussa Keïta", "DEMO-ETUDES-02"),
    ("S-DEMO-3", "giconseils\\f.diallo", "Fatoumata Diallo", "DEMO-SIG-01"),
    ("S-DEMO-4", "giconseils\\o.hassane", "Oumar Hassane", "DEMO-DIR-01"),
]
DOSSIERS = [
    ("GIC-HYD-ETU-052", "Bargondaga", "Bargondaga — APD digue", "DNH", RACINE_MISSIONS, "actif"),
    ("GIC-AEP-CTR-003", "Kayes", "Kayes — contrôle AEP", "SOMAGEP", RACINE_MISSIONS, "actif"),
    (
        "GIC-HYD-ETU-061",
        "Sikasso",
        "Sikasso — étude micro-barrages",
        "DRGR Sikasso",
        RACINE_MISSIONS,
        "actif",
    ),
    ("2026-SOMAPEP-001", "recharge-nappe", "", "", RACINE_AVIS, "detecte"),
]
FICHIERS = [
    "Rapport_APD.docx",
    "Devis.xlsx",
    "Plans\\digue.dwg",
    "SIG\\carte.qgz",
    "Note_calcul.docx",
]
APPLIS = {"docx": "WINWORD.EXE", "xlsx": "EXCEL.EXE", "dwg": "acad.exe", "qgz": "qgis-bin.exe"}


class Command(BaseCommand):
    help = "Crée (ou efface avec --effacer) deux semaines d'activité de démonstration."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--effacer", action="store_true")
        parser.add_argument("--jours", type=int, default=14)

    @transaction.atomic
    def handle(self, *args, effacer: bool = False, jours: int = 14, **options) -> None:
        if effacer:
            n = Segment.objects.filter(poste__nom__startswith="DEMO-").delete()[0]
            Poste.objects.filter(nom__startswith="DEMO-").delete()
            Employe.objects.filter(sid_ad__startswith="S-DEMO-").delete()
            self.stdout.write(f"Jeu de démonstration effacé ({n} segments).")
            return
        if Segment.objects.filter(poste__nom__startswith="DEMO-").exists():
            self.stdout.write(
                "Le jeu de démonstration existe déjà (rien ajouté). --effacer pour le refaire."
            )
            return

        racines = {
            RACINE_MISSIONS: Racine.objects.get_or_create(
                chemin=RACINE_MISSIONS, defaults={"profondeur": 1}
            )[0],
            RACINE_AVIS: Racine.objects.get_or_create(
                chemin=RACINE_AVIS, defaults={"profondeur": 3}
            )[0],
        }
        dossiers = []
        for code, suffixe, nom, client, racine, statut in DOSSIERS:
            chemin = (
                f"{racine}\\{code}_{suffixe}"
                if racine == RACINE_MISSIONS
                else f"{racine}\\MALI\\2026-10\\{code}_{suffixe}"
            )
            d, _ = Dossier.objects.get_or_create(
                chemin_windows=normaliser_chemin(chemin),  # save() normalise : chercher pareil
                defaults={
                    "code": code,
                    "nom": nom or f"{code.lower()}_{suffixe}",
                    "client": client,
                    "racine": racines[racine],
                    "statut": statut,
                    "valide": statut == "actif",
                },
            )
            dossiers.append((d, chemin))

        alea = random.Random(42)  # noqa: S311 — données de démonstration, pas de sécurité en jeu
        tz = timezone.get_current_timezone()
        aujourd_hui = timezone.localdate()
        segments: list[Segment] = []
        for sid, login, nom, poste_nom in PERSONNES:
            employe, _ = Employe.objects.get_or_create(
                sid_ad=sid, defaults={"login": login, "nom_affiche": nom}
            )
            poste, _ = Poste.objects.get_or_create(
                nom=poste_nom, defaults={"version_agent": "0.2.0"}
            )
            poste.dernier_envoi = timezone.now() - timedelta(minutes=alea.randint(1, 30))
            poste.save()
            favoris = alea.sample(dossiers[:3], 2) + [dossiers[3]]
            for recul in range(jours - 1, -1, -1):
                jour = aujourd_hui - timedelta(days=recul)
                if jour.weekday() >= 5 or alea.random() < 0.08:  # week-end, ou absence
                    continue
                t = datetime.combine(jour, time(7, 45), tzinfo=tz) + timedelta(
                    minutes=alea.randint(0, 75)
                )
                fin_journee = datetime.combine(jour, time(16, 30), tzinfo=tz) + timedelta(
                    minutes=alea.randint(0, 90)
                )
                while t < fin_journee:
                    duree = timedelta(minutes=alea.choice([20, 30, 45, 60, 90]))
                    fin = min(t + duree, fin_journee)
                    if time(12, 15) <= t.time() < time(13, 45) and alea.random() < 0.7:
                        segments.append(
                            self._seg(
                                employe,
                                poste,
                                t,
                                fin,
                                "INACTIF",
                                "session",
                                "",
                                "",
                                "application",
                                None,
                            )
                        )
                    else:
                        tirage = alea.random()
                        if tirage < 0.68:
                            dossier, chemin_dossier = alea.choice(favoris)
                            fichier = alea.choice(FICHIERS)
                            segments.append(
                                self._seg(
                                    employe,
                                    poste,
                                    t,
                                    fin,
                                    "ACTIF",
                                    APPLIS[fichier.rsplit(".", 1)[1]],
                                    fichier.rsplit("\\", 1)[-1],
                                    f"{chemin_dossier}\\{fichier}",
                                    "dossier",
                                    dossier,
                                )
                            )
                        elif tirage < 0.80:
                            segments.append(
                                self._seg(
                                    employe,
                                    poste,
                                    t,
                                    fin,
                                    "ACTIF",
                                    "chrome.exe",
                                    "",
                                    "",
                                    "application",
                                    None,
                                )
                            )
                        elif tirage < 0.90:
                            segments.append(
                                self._seg(
                                    employe,
                                    poste,
                                    t,
                                    fin,
                                    "ACTIF",
                                    "OUTLOOK.EXE",
                                    "",
                                    "",
                                    "application",
                                    None,
                                )
                            )
                        elif tirage < 0.96:
                            segments.append(
                                self._seg(
                                    employe,
                                    poste,
                                    t,
                                    fin,
                                    "ACTIF",
                                    "Acrobat.exe",
                                    "TDR_appel_offres.pdf",
                                    rf"C:\Users\{login.split(chr(92))[-1]}\Desktop\TDR_appel_offres.pdf",
                                    "a_classer",
                                    None,
                                )
                            )
                        else:
                            segments.append(
                                self._seg(
                                    employe,
                                    poste,
                                    t,
                                    fin,
                                    "ACTIF",
                                    "WINWORD.EXE",
                                    "Document1",
                                    "",
                                    "brouillon",
                                    None,
                                )
                            )
                    t = fin
        Segment.objects.bulk_create(segments, batch_size=500)
        self.stdout.write(
            f"Jeu de démonstration créé : {len(PERSONNES)} personnes, {len(DOSSIERS)} dossiers, "
            f"{len(segments)} segments sur {jours} jours."
        )

    @staticmethod
    def _seg(employe, poste, debut, fin, etat, appli, fichier, chemin, statut, dossier) -> Segment:
        return Segment(
            employe=employe,
            poste=poste,
            debut=debut,
            fin=fin,
            duree_s=int((fin - debut).total_seconds()),
            etat=etat,
            application=appli,
            fichier=fichier,
            chemin=chemin,
            statut_classement=statut,
            dossier=dossier,
            lot_id=uuid.uuid4(),
        )
