# Déploiement de l'application GIC

Deux environnements sur le serveur, `test` (port 8001, base `gic_test`, site
`suivi-test`) et `prod` (port 8000, base `gic`, site `suivi`), dans
`C:\GIC\<env>\`. Tout passe par les scripts de ce dossier ; rien ne se fait à
la main.

## Règle : Git seul, aucun outil de développement sur le serveur (décision du 08/10/2026)

Le serveur ne reçoit que ce qui est dans GitHub, par `git`. Il n'a ni Tailwind, ni gettext, ni
PyInstaller, ni compilateur, ni pytest : tout ce qui se **construit** l'est sur le poste du
développeur et **commité** :

| Construit sur le poste | Commité dans | Par |
|---|---|---|
| Feuille de style `gic.css` | `interface/static/css/` | `scripts\dev\construire_css.ps1` |
| Traductions `django.mo` | `locale/fr/LC_MESSAGES/` | `scripts/dev/compiler_traductions.py` |
| Liste des dépendances d'exécution | `deploy/requirements.txt` | `scripts/dev/exporter_dependances.py` (vérifié par `scripts\dev\verifier.ps1`) |
| Agent (exécutable, kit d'installation) | **hors Git** — `C:\dev\livraisons\agent\*.zip`, copié sur le partage `\\AD-SERVEUR\GIC\deploy\agent\` | `agent\preparer-kit.ps1` |

Sur le serveur, `installer.ps1` copie le dépôt, installe les dépendances en **roues binaires
seulement** (`pip install --only-binary=:all: -r deploy\requirements.txt`), migre, collecte les
statiques, redémarre. Il refuse une référence où `gic.css` ou `django.mo` manquerait.

```
Poste du développeur                        Serveur (console ou RDP local)
────────────────────                        ──────────────────────────────
scripts\dev\verifier.ps1 (tout vert)
fusion dans main ; git push         ──────► C:\GIC\depot  (clone privé, jeton GitHub lecture seule)
                                            .\deploy\installer.ps1 -Env test -Ref main
                                            .\deploy\verifier.ps1 -Env test
                                            validation sur https://suivi-test.giconseils.local
git tag -a v1.0.0 ; git push --tags ──────► .\deploy\installer.ps1 -Env prod -Ref v1.0.0
                                            .\deploy\verifier.ps1 -Env prod
```

Premier clone sur le serveur : Git pour Windows installé ; un **jeton d'accès GitHub à
granularité fine** (ce dépôt seulement, « Contents : read-only », expiration un an) créé par le
porteur, saisi une fois à la demande de Git, mémorisé par le gestionnaire d'identifiants Windows
pour le compte d'administration qui lance les scripts. Le serveur doit joindre `github.com` et
`pypi.org` (dépendances).

## Scripts

| Script | Où | Rôle |
|---|---|---|
| `installer.ps1` | serveur | Installe ou met à jour un environnement depuis `C:\GIC\depot` (`-Ref main` ou `-Ref vX.Y.Z`) : copie, venv, dépendances, `.env`, migrations, statiques, redémarrage du service. Garde la version précédente pour retour arrière |
| `service.ps1` | serveur | Crée ou met à jour le service Windows `GIC-<Env>` (NSSM) sous `svc-application` |
| `taches.ps1` | serveur | Tâches planifiées : purge, recalcul, postes muets, sauvegarde PostgreSQL, contrôle de santé |
| `sauvegarde_pg.ps1` | serveur | `pg_dump -Fc` des deux bases vers `D:\SAUVEGARDES\pg\`, 14 jours conservés ; appelé par la tâche de 01:00 |
| `verifier.ps1` | serveur | Version déployée, service, `/api/sante` en local et via IIS, tâches, dernière sauvegarde, disques, mémoire, journaux ; code 1 si un point bloquant échoue |
| `requirements.txt` | généré | Dépendances d'exécution (ne pas éditer : `scripts/dev/exporter_dependances.py`) |
| `serveur/` | serveur | Préparation du serveur (01 à 08), à faire une fois |

## Première installation d'un environnement

```powershell
# 1. Outils (une fois) : NSSM téléchargé depuis https://nssm.cc
.\service.ps1 -Env test -Nssm C:\GIC\installateurs\nssm-2.24\win64\nssm.exe -Creer
# 2. Application
.\installer.ps1 -Env test -Ref main
# 3. Tâches planifiées
.\taches.ps1 -Env test
# 4. Vérification
.\verifier.ps1 -Env test
```

## Retour arrière

`installer.ps1` conserve `C:\GIC\<env>\app_precedent\`. Pour revenir :

```powershell
.\installer.ps1 -Env prod -RetourArriere
```

Si une migration de base doit être défaite, la commande `manage.py migrate
<app> <migration>` à exécuter est notée dans le message du commit ou du tag déployé ;
`installer.ps1 -RetourArriere` l'affiche en rappel mais ne la devine pas.

## Secrets

Jamais dans Git. `installer.ps1` construit `C:\GIC\<env>\.env` à partir de
`C:\GIC\secrets\pg.env` (créé par `serveur\07-PostgreSQL.ps1`) ; la `SECRET_KEY`
Django est générée une fois et conservée entre les mises à jour.
