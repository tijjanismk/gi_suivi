# Agent de poste GI-Suivi — v0.1.0

Mesure le temps actif sur le poste et le rattache aux dossiers de projet par
convention de dossiers. Fonctionne en **mode local** sans serveur (mesure,
tampon SQLite, icône, résumé du jour) et en **mode connecté** dès que
`url_api` est renseignée (envoi par lots, identité Windows, reprise).

## Contenu

| Fichier | Rôle |
|---|---|
| `gisuivi_agent/principal.py` | Boucle : observer → segmenter → tampon → envoi ; événements de session |
| `gisuivi_agent/observation.py` | Fenêtre active, processus, inactivité, verrouillage (pywin32) |
| `gisuivi_agent/fichiers.py` | Fichier ouvert : COM Office, titre, puis fichiers ouverts sous une racine (ADR 0003) |
| `gisuivi_agent/tampon.py` | SQLite `%LOCALAPPDATA%\GiSuivi\tampon.db` (un par utilisateur), lots, acquittement, résumé du jour |
| `gisuivi_agent/service.py` | Service `GiSuivi` (G06) : relance l'agent dans chaque session ouverte |
| `gisuivi_agent/envoi.py` | `POST /api/segments`, Negotiate (SSPI), attente exponentielle |
| `gisuivi_agent/icone.py` | Le voyant : vert / orange / gris, menu, notification au démarrage |
| `gisuivi_agent/config.py` | Registre `HKLM\SOFTWARE\GI-CONSEILS\Suivi` (GPO) > `config.json` > défauts |
| `pont-mcp.py`, `gisuivi_agent/pont_mcp.py` | Pont MCP de Claude Desktop (ADR 0016) : stdio → `UrlApi/mcp/` en Negotiate ; `pont-mcp.exe --claude` l'ajoute à `claude_desktop_config.json` |
| `../moteur/suivi/` | Segmentation et classement, Python pur, 22 tests |
| `tests/test_fichiers.py` | 17 titres de fenêtres réels |
| `construire.ps1` | PyInstaller `--onedir` → `dist\gisuivi-agent\`, avec `pont-mcp.exe` (console) et `_pont\` |
| `installer-poste.ps1` / `desinstaller-poste.ps1` | Pilote sur un poste, avant le MSI : `Program Files` + service |
| `construire-msi.ps1`, `msi/Produit.wxs` | MSI WiX 3 (G07), non signé tant qu'il n'y a pas de certificat ; embarque le pont MCP (`pont-mcp.exe`, `_pont\` moissonné avec des identifiants préfixés par `msi/prefixer-pont.xslt`) |
| `CONTROLE.md` | Les 10 vérifications manuelles avant chaque livraison |

## Essayer sur un poste Windows (sans rien installer sur le serveur)

```powershell
cd <dépôt>\agent
.\construire.ps1 -Tester
Copy-Item config.exemple.json dist\gisuivi-agent\config.json      # ajuster les racines si besoin
.\dist\gisuivi-agent\gisuivi-agent.exe
```

**Où l'agent lit sa configuration.** Le registre
`HKLM\SOFTWARE\GI-CONSEILS\Suivi` (GPO) passe avant tout. Ensuite, **le
premier** `config.json` trouvé : à côté de l'exécutable, puis
`%ProgramData%\GiSuivi\config.json`. Un fichier posé à côté de l'exe fait donc
ignorer celui de ProgramData. Un fichier illisible est sauté et signalé dans
le journal (`WARNING Configuration : …`) ; le BOM qu'ajoutent le Bloc-notes et
PowerShell 5.1 est accepté. Au démarrage, le journal annonce le nombre de
racines : « 0 racines » veut dire qu'aucune configuration n'a été lue.

L'icône apparaît dans le tiroir « ^ » près de l'horloge avec une
notification ; clic droit → « Mon activité du jour ». Journal de l'agent dans
`%LOCALAPPDATA%\GiSuivi\agent.log` (un par utilisateur, comme le tampon) ;
journal du service dans `%ProgramData%\GiSuivi\service.log`. Pour l'arrêter
pendant les essais : Gestionnaire des tâches (il n'a pas de « Quitter » par
conception) — si le service est installé, il le relance sous 15 s : arrêter
d'abord le service (`Stop-Service GiSuivi`, en administrateur).

## Ce qui reste pour la phase 3 (tickets G06, G07, G08)

- Service de supervision qui relance l'agent (G06).
- MSI WiX, signature, GPO (G07).
- Mesure d'empreinte sur une journée et liste de contrôle (G08) — décide si
  l'agent reste en Python (ADR 0002).

## Le voyant, honnêtement

Windows 10/11 masque les nouvelles icônes dans le tiroir « ^ ». Aucune
stratégie de groupe ne force proprement leur affichage permanent sur
Windows 11. L'agent compense par une notification au démarrage de session et
une info-bulle explicite ; la note à l'équipe dira : « glissez l'icône à côté
du réseau pour la garder visible ». Ce que l'agent garantit : l'icône
existe toujours, elle est nommée, elle explique ce qui est mesuré, et elle ne
peut pas être fermée sans fermer la session.
