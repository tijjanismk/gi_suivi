# Déploiement de l'application GIC

Deux environnements sur le serveur, `test` (port 8001, base `gic_test`, site
`suivi-test`) et `prod` (port 8000, base `gic`, site `suivi`), dans
`C:\GIC\<env>\`. Tout passe par les scripts de ce dossier ; rien ne se fait à
la main.

## Flux normal : Git entre le poste et le serveur (décision du 08/10/2026)

```
Poste du développeur                        Serveur (console ou RDP local)
────────────────────                        ──────────────────────────────
scripts\dev\verifier.ps1 (tout vert)
fusion dans main ; git push         ──────► C:\GIC\depot  (clone privé, jeton GitHub lecture seule)
                                            .\deploy\installer.ps1 -Env test -Ref main
                                            validation sur https://suivi-test.giconseils.local
git tag -a v1.0.0 ; git push --tags ──────► .\deploy\installer.ps1 -Env prod -Ref v1.0.0
                                            .\deploy\verifier.ps1 -Env prod
```

Le serveur ne reçoit que ce qui est dans GitHub : rien n'est copié à la main. `publier.ps1`
(archive zip sur le partage) reste disponible pour un serveur sans accès à GitHub.

Premier clone sur le serveur : Git pour Windows installé ; un **jeton d'accès GitHub à
granularité fine** (ce dépôt seulement, « Contents : read-only », expiration un an) créé par le
porteur, saisi une fois à la demande de Git, mémorisé par le gestionnaire d'identifiants Windows
pour le compte d'administration qui lance les scripts. Le serveur doit joindre `github.com` et
`pypi.org` (installation des dépendances).

## Scripts

| Script | Où | Rôle |
|---|---|---|
| `publier.ps1` | poste du développeur | `git archive` du tag en zip, copie sur le partage `GIC\deploy\app\` |
| `installer.ps1` | serveur | Installe ou met à jour un environnement depuis un zip : extraction, venv, dépendances, `.env`, migrations, statiques, redémarrage du service. Garde la version précédente pour retour arrière |
| `service.ps1` | serveur | Crée ou met à jour le service Windows `GIC-<Env>` (NSSM) sous `svc-application` |
| `taches.ps1` | serveur | Tâches planifiées : purge, recalcul, postes muets, sauvegarde PostgreSQL, contrôle de santé |
| `sauvegarde_pg.ps1` | serveur | `pg_dump` des bases, 14 jours conservés ; appelé par la tâche |
| `verifier.ps1` | serveur | État du service, réponse de `/api/sante` en local et via IIS, dernières lignes de journal |
| `serveur/` | serveur | Préparation du serveur (01 à 08), à faire une fois |

## Première installation d'un environnement

```powershell
# 1. Outils (une fois) : NSSM téléchargé depuis https://nssm.cc
.\service.ps1 -Env test -Nssm C:\Users\adm-x\Downloads\nssm-2.24\win64\nssm.exe -Creer
# 2. Application
.\installer.ps1 -Env test -Zip \\AD-SERVEUR\GIC\deploy\app\gic-v0.1.0.zip
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
<app> <migration>` à exécuter est notée dans la pull request du tag déployé ;
`installer.ps1 -RetourArriere` l'affiche en rappel mais ne la devine pas.

## Secrets

Jamais dans le zip ni dans Git. `installer.ps1` construit `C:\GIC\<env>\.env`
à partir de `.env.exemple` et de `C:\GIC\secrets\pg.env` (créé par
`serveur\07-PostgreSQL.ps1`) ; la `SECRET_KEY` Django est générée une fois et
conservée entre les mises à jour.
