# Installer l'agent GI-Suivi sur un poste pilote — à la main, sans GPO

Ce kit sert tant que la stratégie de groupe (GPO) et le MSI ne sont pas en place. Il installe
l'agent et son service de supervision sur **un** poste Windows 10/11 du domaine.

## Avant d'installer chez quelqu'un

- La **note d'information à l'équipe** est signée et la personne l'a lue (`docs/pilote/note-equipe.md`) :
  ce qui est mesuré, ce qui ne l'est pas, qui voit quoi. On n'installe pas sans ça.
- Vous êtes **administrateur local** du poste.
- Le fichier `config.json` du kit porte les bonnes **racines** (dossiers de projet du partage) et,
  si le serveur est prêt, `url_api` (sinon `null` : l'agent mesure en local et enverra plus tard).
- Si le serveur utilise un **certificat auto-signé** (pas d'autorité de certification interne —
  c'est le cas d'AD-SERVEUR), le fichier **`gic-serveur.cer`** doit être dans le dossier du kit,
  à côté de `installer-poste.ps1` : il est produit sur le serveur par
  `deploy\serveur\08-Python-IIS.ps1 -AutoSigne` (dans `C:\GIC\deploy\`). Le script l'importe dans
  les autorités racines de confiance du poste ; sans lui, l'agent et le navigateur refuseront
  `https://suivi-test.giconseils.local`.

## Installation (5 minutes)

1. Copier le kit sur le poste (clé USB ou partage) et le décompresser, par exemple dans
   `C:\Temp\GiSuivi-agent-poste\`.
2. Ouvrir **PowerShell en administrateur** dans ce dossier, puis :
   ```powershell
   Unblock-File .\*.ps1
   Set-ExecutionPolicy -Scope Process Bypass -Force
   .\installer-poste.ps1
   ```
   Le script copie l'agent dans `C:\Program Files\GI-CONSEILS\GiSuivi\`, pose la configuration
   dans `C:\ProgramData\GiSuivi\config.json`, approuve le certificat du serveur s'il est fourni,
   crée et démarre le service `GiSuivi`.
3. Dans les 15 secondes, l'icône GI-Suivi apparaît dans le tiroir « ^ » près de l'horloge, avec
   une notification. Clic droit → « Mon activité du jour ». Conseil à donner : glisser l'icône à
   côté du réseau pour la garder visible.
4. Vérifier : `C:\ProgramData\GiSuivi\service.log` (« Agent lancé dans la session… ») et, dans la
   session de la personne, `%LOCALAPPDATA%\GiSuivi\agent.log` (« Agent 0.2.2 démarré, mode local/connecté, N racines »).
   **« 0 racines » = configuration non lue** : vérifier `config.json`.
5. En mode connecté, au bout de 3 minutes au plus : le poste apparaît dans « État des postes »
   (`https://suivi-test.giconseils.local/suivi/postes/`). Si `agent.log` dit « réseau :
   SSLError », le certificat n'est pas approuvé (point précédent) ; « 401 », le ticket Kerberos
   ou le SPN (`deploy\serveur\06-DNS-SPN.ps1`).

## Le navigateur demande un mot de passe (et le refuse)

C'est que le site n'est pas dans la zone « Intranet local » du poste : le navigateur ne présente
pas le ticket Kerberos de la session Windows, et l'application n'accepte que ce ticket.
`installer-poste.ps1` règle cela ; sur un poste installé avant, ou sans agent : `.\zone-intranet.ps1`
en administrateur, puis fermer complètement le navigateur et le rouvrir.

## Icône grise « hors réseau, N segments en attente » alors que le serveur répond

Après plusieurs échecs, l'agent espace ses essais (jusqu'à 30 min). Pour qu'il réessaie tout de
suite : `.\relancer-agent.ps1` dans la session de la personne (pas besoin d'être administrateur).
Il range d'abord ses segments dans le tampon, le service le relance, et l'icône passe au vert dès
qu'un lot est accepté. Le motif du dernier échec est dans `%LOCALAPPDATA%\GiSuivi\agent.log`.

## Changer la configuration plus tard (passer en mode connecté)

Modifier `C:\ProgramData\GiSuivi\config.json` (`url_api`, racines) avec le Bloc-notes, puis
ouvrir le Gestionnaire des tâches et terminer `gisuivi-agent.exe` : le service le relance avec
la nouvelle configuration. Pas besoin de réinstaller.

## Mettre à jour l'agent

Relancer `installer-poste.ps1` depuis le nouveau kit : il arrête proprement l'agent (les segments
en attente sont conservés), remplace les fichiers et redémarre. La configuration existante est
conservée si le kit n'en apporte pas.

## Désinstaller

`.\desinstaller-poste.ps1` en administrateur : service et programme retirés ; les données
(`C:\ProgramData\GiSuivi`, `%LOCALAPPDATA%\GiSuivi`) sont laissées — le tampon peut contenir des
segments non envoyés.

## Ce que fait l'agent — en une phrase pour la personne

Il mesure le temps actif sur le poste et le rattache aux dossiers de projet par le dossier où
sont rangés les fichiers ouverts ; il ne lit ni le contenu des fichiers, ni les courriels, ni les
sites visités ; la personne voit sa propre journée en un clic.
