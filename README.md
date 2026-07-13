(application en pause, attention, l'usage est très restreint, il n'y a pas encore les fonctionnalités necessaire)

# IA Assistance

IA Assistance est une application desktop Windows pour écouter le son du PC, écouter le microphone, transcrire en direct avec Murmure, sauvegarder les transcriptions et les analyser avec un assistant IA local via Ollama.

Le dépôt GitHub officiel est :

<https://github.com/aminechaff/assistance_ia>

## Sommaire

- [Ce que fait l'application](#ce-que-fait-lapplication)
- [Architecture rapide](#architecture-rapide)
- [Prérequis](#prérequis)
- [Installation depuis le code source](#installation-depuis-le-code-source)
- [Configuration de Murmure](#configuration-de-murmure)
- [Configuration de Ollama](#configuration-de-ollama)
- [Lancer l'application](#lancer-lapplication)
- [Utilisation quotidienne](#utilisation-quotidienne)
- [Assistant IA](#assistant-ia)
- [Historique et fichiers générés](#historique-et-fichiers-générés)
- [Créer une version portable `.exe`](#créer-une-version-portable-exe)
- [Utilisation avec une release portable](#utilisation-avec-une-release-portable)
- [Configuration technique](#configuration-technique)
- [Dépannage](#dépannage)
- [Développement](#développement)
- [Structure du projet](#structure-du-projet)
- [Ce qui ne doit pas être versionné](#ce-qui-ne-doit-pas-être-versionné)
- [Remerciements](#remerciements)

## Ce que fait l'application

IA Assistance sert de hub local autour de Murmure et Ollama.

Fonctions principales :

- écouter le son du PC avec WASAPI loopback ;
- écouter le microphone ;
- envoyer les segments audio à l'API locale de Murmure ;
- afficher la transcription en direct ;
- sauvegarder chaque session en Markdown ;
- ouvrir, renommer, modifier et supprimer les transcriptions ;
- poser des questions à un assistant IA local ;
- produire des résumés, comptes-rendus, points clés, actions, fiches étudiant, analyses doctorat et versions simplifiées ;
- suspendre automatiquement l'écoute pendant qu'Ollama répond, puis reprendre l'écoute ensuite ;
- afficher clairement les statuts de Murmure, Ollama, du moteur Python, du PC et du micro.

Le projet est pensé pour rester local : l'audio, les transcriptions et l'assistant tournent sur la machine, à condition que Murmure et Ollama soient lancés localement.

## Architecture rapide

```text
IA Assistance.cmd
  -> app-electron/
      -> interface desktop Electron
      -> lance le moteur Python

ecoute-pc/
  -> serveur FastAPI sur http://127.0.0.1:4900
  -> capture audio PC et micro
  -> découpe en segments de parole
  -> envoie les WAV à Murmure
  -> diffuse les résultats à Electron en WebSocket
  -> sauvegarde les transcriptions dans ecoute-pc/transcripts/

Murmure
  -> application externe
  -> API locale attendue sur http://127.0.0.1:4800/api/transcribe

Ollama
  -> application externe
  -> API locale attendue sur http://127.0.0.1:11434
```

Important : IA Assistance ne remplace pas Murmure. Pour l'instant, elle s'appuie sur Murmure pour faire la transcription audio.

## Prérequis

### Système

- Windows 10 ou Windows 11.
- Une sortie audio fonctionnelle pour l'écoute PC.
- Un microphone fonctionnel pour l'écoute voix.

### Outils nécessaires pour installer depuis le code source

- Git : <https://git-scm.com/downloads>
- Node.js LTS avec npm : <https://nodejs.org/>
- Python 3.11 ou plus récent : <https://www.python.org/downloads/>
- Murmure : <https://github.com/Kieirra/murmure/releases>
- Ollama, optionnel mais recommandé pour l'assistant IA : <https://ollama.com/>

Pendant l'installation de Python, coche l'option :

```text
Add python.exe to PATH
```

### Vérifier les outils

Dans PowerShell :

```powershell
git --version
node --version
npm --version
python --version
```

Si une commande n'est pas reconnue, l'outil correspondant n'est pas installé ou n'est pas dans le `PATH`.

## Installation depuis le code source

### 1. Récupérer le projet

Avec Git :

```powershell
git clone https://github.com/aminechaff/assistance_ia.git
cd assistance_ia
```

Sans Git :

1. Ouvrir <https://github.com/aminechaff/assistance_ia>.
2. Cliquer sur `Code`.
3. Cliquer sur `Download ZIP`.
4. Extraire le ZIP.
5. Ouvrir PowerShell dans le dossier extrait.

### 2. Installer les dépendances Electron

Depuis la racine du projet :

```powershell
cd app-electron
npm install
```

Cette commande recrée le dossier :

```text
app-electron/node_modules/
```

### 3. Installer les dépendances Python

Depuis `app-electron`, revenir dans le dossier Python :

```powershell
cd ..\ecoute-pc
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Cette commande recrée le dossier :

```text
ecoute-pc/.venv/
```

## Configuration de Murmure

IA Assistance utilise Murmure pour transcrire l'audio. Murmure doit être installé, lancé et configuré avec son API locale.

Étapes :

1. Télécharger Murmure depuis <https://github.com/Kieirra/murmure/releases>.
2. Installer Murmure.
3. Lancer Murmure.
4. Ouvrir les paramètres de Murmure.
5. Aller dans les paramètres système.
6. Activer l'API locale.
7. Vérifier que le port est `4800`.

L'URL attendue par IA Assistance est :

```text
http://127.0.0.1:4800/api/transcribe
```

Si Murmure est fermé ou si l'API locale est désactivée, le statut Murmure devient hors ligne dans IA Assistance.

## Configuration de Ollama

Ollama est utilisé pour l'assistant IA : résumés, questions, actions, compte-rendu, version étudiant, doctorat, etc.

### 1. Installer Ollama

Télécharger Ollama depuis :

<https://ollama.com/>

Lancer Ollama après installation.

### 2. Installer le modèle par défaut

Le modèle attendu par défaut est :

```text
qwen3.5:4b
```

Commande :

```powershell
ollama pull qwen3.5:4b
```

### 3. Vérifier Ollama

```powershell
ollama list
```

L'API locale attendue par IA Assistance est :

```text
http://127.0.0.1:11434
```

Si Ollama n'est pas lancé ou si le modèle n'est pas installé, l'assistant sera indiqué comme hors ligne ou indisponible.

## Lancer l'application

### Méthode simple

Depuis la racine du projet, double-cliquer sur :

```text
IA Assistance.cmd
```

Ce fichier lance Electron, et Electron démarre automatiquement le moteur Python.

### Méthode PowerShell

Depuis la racine du projet :

```powershell
cd app-electron
npm start
```

Si tout est prêt :

- la fenêtre IA Assistance s'ouvre ;
- le statut `Moteur` passe au vert ;
- le statut `Murmure` passe au vert si Murmure est lancé ;
- le statut `Ollama` passe au vert si Ollama et le modèle sont prêts ;
- les boutons `Ecoute PC` et `Ma voix` peuvent démarrer l'écoute.

## Utilisation quotidienne

### 1. Démarrer les services externes

Avant d'utiliser IA Assistance :

1. Lancer Murmure.
2. Vérifier que l'API locale de Murmure est activée sur le port `4800`.
3. Lancer Ollama si l'assistant IA est souhaité.
4. Lancer IA Assistance.

### 2. Transcrire le son du PC

Cliquer sur :

```text
Ecoute PC -> Demarrer
```

Cela capture ce que l'ordinateur joue : navigateur, YouTube, Discord, Teams, musique, vidéo, etc.

### 3. Transcrire le micro

Cliquer sur :

```text
Ma voix -> Demarrer
```

Cela capture le microphone par défaut.

### 4. Lire la transcription en direct

La zone centrale affiche les lignes transcrites avec :

- la source (`PC`, `Micro`, `Assistant`) ;
- l'heure ;
- le texte transcrit ;
- les réponses de l'assistant IA.

### 5. Créer une nouvelle transcription

Cliquer sur :

```text
Nouvelle transcription
```

Tu peux entrer un nom ou laisser vide pour générer un nom basé sur la date et l'heure.

Si l'écoute PC ou le micro est actif, IA Assistance suspend brièvement l'écoute, crée la nouvelle session, vide l'affichage en direct, puis relance automatiquement les sources qui étaient actives. Cela évite que des segments audio de l'ancienne session se mélangent à la nouvelle transcription.

### 6. Renommer la transcription en cours

Cliquer sur :

```text
Renommer
```

Le bouton renomme la session active sans arrêter l'application. Les segments audio déjà en attente restent attachés au bon fichier, même si le renommage arrive pendant une transcription.

### 7. Vider l'écran

Cliquer sur :

```text
Vider l'ecran
```

Cela vide seulement l'affichage en direct. Le fichier Markdown de transcription n'est pas supprimé.

### 8. Ouvrir l'historique

Dans la colonne de gauche :

- rechercher une transcription ;
- cliquer sur une ancienne session ;
- lire le contenu ;
- modifier ;
- renommer ;
- supprimer.

Quand une transcription est ouverte depuis l'historique, l'assistant IA peut analyser cette transcription précise.

## Assistant IA

L'assistant IA est local et s'appuie sur Ollama.

Modes disponibles :

| Mode | Utilité |
| --- | --- |
| `Resume` | Obtenir une synthèse claire |
| `Compte-rendu` | Transformer la transcription en compte-rendu structuré |
| `Actions` | Extraire les tâches, décisions, personnes et échéances |
| `Points cles` | Lister les éléments importants |
| `Parent presse` | Expliquer vite et simplement |
| `Etudiant` | Produire une fiche de révision |
| `Doctorat` | Analyser avec un niveau recherche |
| `Simplifier` | Reformuler en langage simple |
| Question libre | Poser une question personnalisée |

Pendant une demande à l'assistant :

- un indicateur visuel montre que Ollama réfléchit ;
- l'écoute PC et micro est suspendue si elle était active ;
- l'écoute reprend automatiquement après la réponse ;
- les étapes de raisonnement internes du modèle sont filtrées ;
- la réponse finale est affichée en français.

## Historique et fichiers générés

Les transcriptions sont sauvegardées ici :

```text
ecoute-pc/transcripts/
```

Chaque transcription est un fichier Markdown `.md`.

Exemple :

```text
ecoute-pc/transcripts/2026-07-08_23h31.md
```

Ces fichiers sont locaux et personnels. Ils ne doivent pas être envoyés dans GitHub.

## Créer une version portable `.exe`

Pour générer une version portable depuis le code source :

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-release.ps1
```

Le script :

1. vérifie ou crée l'environnement Python ;
2. installe les dépendances Python ;
3. installe PyInstaller ;
4. compile le moteur Python ;
5. installe les dépendances Electron ;
6. construit l'application portable avec `electron-builder`.

Le fichier final est créé ici :

```text
app-electron\dist\IA Assistance-0.1.0-portable.exe
```

Important :

- l'exécutable contient IA Assistance ;
- il ne contient pas Murmure ;
- il ne contient pas Ollama ;
- il faut toujours installer Murmure séparément ;
- Ollama reste nécessaire pour l'assistant IA.

## Utilisation avec une release portable

Si une release GitHub contient :

```text
IA Assistance-0.1.0-portable.exe
```

Alors l'utilisateur n'a pas besoin d'installer :

- Node.js ;
- npm ;
- Python ;
- les dépendances Python ;
- les dépendances Electron.

Il doit quand même installer :

- Murmure, avec l'API locale activée ;
- Ollama, seulement s'il veut utiliser l'assistant IA.

Étapes pour un utilisateur non développeur :

1. Installer Murmure depuis <https://github.com/Kieirra/murmure/releases>.
2. Lancer Murmure.
3. Activer l'API locale de Murmure sur le port `4800`.
4. Installer Ollama depuis <https://ollama.com/> si l'assistant IA est souhaité.
5. Installer le modèle :

```powershell
ollama pull qwen3.5:4b
```

6. Télécharger l'exécutable portable depuis les releases du dépôt.
7. Double-cliquer sur l'exécutable.

## Configuration technique

Les valeurs importantes sont actuellement définies dans le code.

| Élément | Valeur par défaut | Fichier |
| --- | --- | --- |
| API Murmure | `http://127.0.0.1:4800/api/transcribe` | `ecoute-pc/moteur.py` |
| Serveur IA Assistance | `http://127.0.0.1:4900` | `ecoute-pc/serveur.py` |
| API côté interface | `http://127.0.0.1:4900` | `app-electron/renderer/app.js` |
| WebSocket live | `ws://127.0.0.1:4900/live` | `app-electron/renderer/app.js` |
| API Ollama | `http://127.0.0.1:11434` | `ecoute-pc/serveur.py` |
| Modèle assistant | `qwen3.5:4b` | `ecoute-pc/serveur.py` |
| Dossier transcriptions | `ecoute-pc/transcripts/` | `ecoute-pc/moteur.py` |

Si tu changes un port, il faut mettre à jour les fichiers correspondants.

## Dépannage

### `python` n'est pas reconnu

Python n'est pas installé ou n'est pas dans le `PATH`.

Solutions :

- réinstaller Python en cochant `Add python.exe to PATH` ;
- fermer et rouvrir PowerShell ;
- utiliser le chemin complet vers `python.exe`.

### `npm` n'est pas reconnu

Node.js n'est pas installé ou n'est pas dans le `PATH`.

Solution :

1. Installer Node.js LTS depuis <https://nodejs.org/>.
2. Fermer et rouvrir PowerShell.
3. Vérifier :

```powershell
npm --version
```

### Murmure reste hors ligne

Vérifier que :

- Murmure est lancé ;
- l'API locale est activée ;
- le port est `4800` ;
- aucun pare-feu ne bloque `127.0.0.1:4800` ;
- l'URL attendue est bien `http://127.0.0.1:4800/api/transcribe`.

### Ollama reste hors ligne

Vérifier que :

- Ollama est installé ;
- Ollama est lancé ;
- le modèle est installé ;
- l'API répond sur `127.0.0.1:11434`.

Commandes utiles :

```powershell
ollama list
ollama pull qwen3.5:4b
```

### L'assistant répond lentement

Ollama tourne localement. La vitesse dépend :

- du modèle utilisé ;
- du processeur ;
- de la mémoire ;
- de la longueur de la transcription ;
- de l'activité de la machine.

IA Assistance affiche un indicateur pendant l'attente et filtre les étapes de raisonnement du modèle quand elles apparaissent.

### L'écoute PC ne démarre pas

La capture PC utilise WASAPI loopback via PyAudioWPatch.

Vérifier que :

- l'application tourne sur Windows ;
- un périphérique de sortie audio est actif ;
- du son est en train de jouer ;
- le périphérique de sortie par défaut est correct ;
- aucun autre logiciel ne bloque l'accès audio.

### Le micro ne démarre pas

Vérifier que :

- le micro est branché ;
- Windows autorise l'accès au micro ;
- le micro par défaut est le bon ;
- le micro fonctionne dans une autre application.

### Le port `4900` est déjà utilisé

IA Assistance utilise :

```text
http://127.0.0.1:4900
```

Si le port est déjà pris :

- fermer l'autre instance de IA Assistance ;
- fermer le programme qui utilise le port ;
- redémarrer l'application.

### L'application ne s'ouvre pas avec `IA Assistance.cmd`

Essayer en PowerShell :

```powershell
cd app-electron
npm start
```

Si cela échoue, vérifier que `npm install` a bien été lancé.

## Développement

### Lancer seulement le serveur Python

```powershell
cd ecoute-pc
.\.venv\Scripts\python.exe serveur.py
```

### Lancer seulement l'interface Electron

Dans un autre PowerShell :

```powershell
cd app-electron
npm start
```

En pratique, `npm start` lance Electron, et Electron lance le serveur Python automatiquement.

### Vérifier rapidement les fichiers Python

```powershell
cd ecoute-pc
.\.venv\Scripts\python.exe -m py_compile ecoute_pc.py moteur.py serveur.py
```

### Vérifier rapidement le JavaScript renderer

Depuis la racine :

```powershell
node --check app-electron\renderer\app.js
```

## Structure du projet

```text
assistance_ia/
  IA Assistance.cmd
  README.md
  scripts/
    build-release.ps1

  app-electron/
    main.js
    package.json
    package-lock.json
    renderer/
      index.html
      style.css
      app.js

  ecoute-pc/
    requirements.txt
    serveur.py
    moteur.py
    ecoute_pc.py
```

Rôle des principaux fichiers :

| Fichier | Rôle |
| --- | --- |
| `IA Assistance.cmd` | Lance l'application Electron depuis la racine |
| `app-electron/main.js` | Crée la fenêtre Electron et lance le moteur Python |
| `app-electron/renderer/index.html` | Structure de l'interface |
| `app-electron/renderer/style.css` | Apparence de l'application |
| `app-electron/renderer/app.js` | Logique UI, appels API, WebSocket, assistant |
| `ecoute-pc/serveur.py` | API FastAPI, historique, assistant Ollama |
| `ecoute-pc/moteur.py` | Capture audio, découpage, appel Murmure |
| `ecoute-pc/ecoute_pc.py` | Ancien mode CLI / script autonome d'écoute PC |
| `scripts/build-release.ps1` | Génération de l'exécutable portable |

## Ce qui ne doit pas être versionné

Ces dossiers et fichiers sont générés localement et ignorés par Git :

```text
app-electron/node_modules/
app-electron/dist/
ecoute-pc/.venv/
ecoute-pc/build/
ecoute-pc/dist/
ecoute-pc/__pycache__/
ecoute-pc/transcripts/
murmure/
```

Pourquoi :

- `node_modules/` se recrée avec `npm install` ;
- `.venv/` se recrée avec `python -m venv .venv` ;
- `build/` et `dist/` sont des sorties de compilation ;
- `transcripts/` contient des données personnelles ;
- `murmure/` est une copie locale externe, pas le code source de IA Assistance.

## Limites actuelles

- L'application cible Windows.
- Murmure doit être installé séparément.
- Ollama doit être installé séparément pour l'assistant IA.
- La qualité et la vitesse de l'assistant dépendent du modèle Ollama et du PC.
- Les ports sont encore configurés dans le code.

## Feuille de route possible

Améliorations possibles :

- rendre les ports configurables depuis l'interface ;
- choisir le modèle Ollama depuis l'interface ;
- exporter les transcriptions en PDF ;
- ajouter une recherche plein texte dans les transcriptions ;
- ajouter une synthèse automatique en fin de session ;
- intégrer un moteur de transcription directement dans IA Assistance ;
- créer un installateur plus simple pour les utilisateurs non techniques.

## Remerciements

Merci à [Kieirra/murmure](https://github.com/Kieirra/murmure). IA Assistance s'appuie sur Murmure pour la transcription locale.

Merci aussi aux projets utilisés dans cette couche :

- Electron ;
- FastAPI ;
- PyAudioWPatch ;
- NumPy ;
- Requests ;
- Uvicorn ;
- Ollama ;
- PyInstaller ;
- electron-builder.

## Note importante

IA Assistance est un projet local d'assistance personnelle. Il ne vend pas Murmure, ne remplace pas Murmure et ne fournit pas Ollama. Il ajoute une interface, une capture audio PC/micro, un historique et un assistant IA autour de services locaux existants.
