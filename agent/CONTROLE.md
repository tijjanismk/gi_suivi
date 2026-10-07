# Liste de contrôle de l'agent — à faire sur un poste du domaine avant chaque MSI

Poste : ____________  Version : ______  Date : __________  Testeur : __________

| # | Vérification | Attendu | OK |
|---|---|---|---|
| 1 | Ouvrir un Word depuis le partage | Le segment porte le chemin UNC complet (COM) | ☐ |
| 2 | Ouvrir un PDF depuis le Bureau | Segment « à classer » dans le résumé du jour | ☐ |
| 3 | Rester 6 min sans toucher au clavier ni à la souris | Le temps au-delà de la dernière action est retiré | ☐ |
| 4 | Verrouiller l'écran 2 min | Rien n'est compté | ☐ |
| 5 | Débrancher le réseau 10 min, travailler, rebrancher | Les segments arrivent, une seule fois (mode connecté) | ☐ |
| 6 | Fermer la session, la rouvrir | L'agent redémarre, l'icône et la notification apparaissent | ☐ |
| 7 | Gestionnaire des tâches après 1 h | Processeur < 1 %, mémoire < 80 Mo | ☐ |
| 8 | Tuer gisuivi-agent.exe | Relancé en moins d'une minute par le service | ☐ |
| 9 | Clic sur l'icône → « Mon activité du jour » | Résumé cohérent avec la journée | ☐ |
| 10 | Document1 puis Enregistrer sous… | Un seul segment, au nom final | ☐ |

Résultat collé dans la pull request qui publie le MSI.
