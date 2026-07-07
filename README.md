⚠️ Warning ! Pour l’instant, la transcription fonctionne, mais Ollama est moyen.

# IA Assistance

IA Assistance est un hub local de transcription audio pour Windows. Il permet d'ecouter le son du PC, le microphone, de transcrire en continu avec l'API locale de Murmure, puis d'interroger la transcription avec un assistant Ollama.

Le projet est une couche pratique au-dessus de Murmure: interface Electron, serveur FastAPI, capture audio WASAPI loopback, historique Markdown et assistant local.

## Ce qui est inclus

- Une interface desktop Electron dans `app-electron/`.
- Un moteur Python FastAPI dans `ecoute-pc/`.
- Un lanceur Windows: `IA Assistance.cmd`.
- Un fichier `requirements.txt` pour reconstruire l'environnement Python.
- Un README d'installation pour remettre le projet en route sur un autre PC.

## Ce qui n'est pas inclus

Ces elements ne sont pas envoyes dans le depot, volontairement:

- `node_modules/`: dependances Electron, a recreer avec `npm install`.
- `ecoute-pc/.venv/`: environnement Python local, a recreer avec `python -m venv .venv`.
- `ecoute-pc/transcripts/`: transcriptions personnelles/locales.
- `murmure/`: projet externe complet. IA Assistance utilise Murmure via son API locale.
- `__pycache__/`: fichiers generes par Python.

Le depot est donc un projet source propre, pas encore une application portable autonome.

## Fonctionnalites

- Ecoute du son du PC: YouTube, Discord, Teams, musique, navigateur, etc.
- Ecoute du microphone.
- Transcription en direct via Murmure en local.
- Historique des transcriptions en fichiers Markdown.
- Renommage, edition et suppression des transcriptions depuis l'interface.
- Assistant local via Ollama pour resumer, extraire les points cles, lister les actions ou poser une question.
- Lancement simple avec `IA Assistance.cmd` une fois l'installation faite.

## Architecture

```text
IA Assistance.cmd
  -> app-electron/
      -> interface desktop Electron
      -> demarre ecoute-pc/serveur.py

ecoute-pc/
  -> FastAPI sur http://127.0.0.1:4900
  -> capture audio PC/micro avec PyAudioWPatch
  -> envoie les segments WAV a Murmure
  -> diffuse le live en WebSocket
  -> sauvegarde les transcriptions dans ecoute-pc/transcripts/

Murmure
  -> API locale sur http://127.0.0.1:4800/api/transcribe

Ollama
  -> API locale sur http://127.0.0.1:11434
```

## Prerequis

Pour installer IA Assistance sur un nouveau PC, il faut:

- Windows 10 ou plus recent.
- Git, optionnel mais recommande: https://git-scm.com/downloads
- Node.js LTS avec npm: https://nodejs.org/
- Python 3.11 ou plus recent: https://www.python.org/downloads/
- Murmure installe et lance: https://github.com/Kieirra/murmure/releases
- Ollama, optionnel pour l'assistant: https://ollama.com/

Pendant l'installation de Python, cocher l'option `Add python.exe to PATH`.

## Installation complete sur un nouveau PC

### 1. Recuperer le projet

Avec Git:

```powershell
git clone https://github.com/aminechaff/assistance_ia.git
cd assistance_ia
```

Sans Git:

1. Aller sur la page GitHub du projet.
2. Cliquer sur `Code`.
3. Cliquer sur `Download ZIP`.
4. Extraire le ZIP.
5. Ouvrir PowerShell dans le dossier extrait.

### 2. Installer les dependances Electron

Depuis la racine du projet:

```powershell
cd app-electron
npm install
```

Cette commande recree `app-electron/node_modules/`.

### 3. Installer les dependances Python

Toujours depuis `app-electron`, revenir dans `ecoute-pc`:

```powershell
cd ..\ecoute-pc
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Cette etape recree `ecoute-pc/.venv/`.

### 4. Installer et preparer Murmure

1. Telecharger Murmure depuis les releases officielles: https://github.com/Kieirra/murmure/releases
2. Installer Murmure.
3. Lancer Murmure.
4. Ouvrir les parametres de Murmure.
5. Aller dans les parametres systeme.
6. Activer l'API locale.
7. Verifier que le port de l'API locale est `4800`.

IA Assistance ne transcrit pas directement l'audio: il envoie les segments audio a Murmure sur:

```text
http://127.0.0.1:4800/api/transcribe
```

### 5. Installer Ollama, optionnel

Ollama est seulement necessaire pour les boutons assistant: `Resumer`, `Points cles`, `Actions` et les questions.

Installer Ollama: https://ollama.com/

Puis installer le modele attendu par defaut:

```powershell
ollama pull qwen3.5:4b
```

Verifier qu'Ollama est lance. Son API doit repondre sur:

```text
http://127.0.0.1:11434
```

### 6. Lancer IA Assistance

Revenir a la racine du projet, puis double-cliquer sur:

```text
IA Assistance.cmd
```

Le fichier lance Electron, et Electron demarre automatiquement le serveur Python `ecoute-pc/serveur.py`.

Si tout est pret:

- la fenetre IA Assistance s'ouvre;
- le statut Murmure passe au vert;
- les boutons `Ecoute PC` et `Ma voix` peuvent demarrer l'enregistrement;
- les transcriptions apparaissent en direct;
- les fichiers Markdown sont crees dans `ecoute-pc/transcripts/`.

## Utilisation

1. Lancer Murmure et verifier que l'API locale est activee.
2. Lancer Ollama si les fonctions assistant sont souhaitees.
3. Lancer `IA Assistance.cmd`.
4. Cliquer sur `Demarrer` dans `Ecoute PC` pour transcrire le son de l'ordinateur.
5. Cliquer sur `Demarrer` dans `Ma voix` pour transcrire le micro.
6. Utiliser l'historique pour ouvrir, modifier, renommer ou supprimer une transcription.

## Configuration

Les valeurs importantes sont actuellement definies dans le code:

| Element | Valeur par defaut | Fichier |
| --- | --- | --- |
| API Murmure | `http://127.0.0.1:4800/api/transcribe` | `ecoute-pc/moteur.py` |
| Serveur IA Assistance | `http://127.0.0.1:4900` | `ecoute-pc/serveur.py` et `app-electron/renderer/app.js` |
| API Ollama | `http://127.0.0.1:11434` | `ecoute-pc/serveur.py` |
| Modele assistant | `qwen3.5:4b` | `ecoute-pc/serveur.py` |

Si tu changes le port de l'API Murmure dans Murmure, il faut aussi changer `MURMURE_API` dans `ecoute-pc/moteur.py`.

Si tu changes le port du serveur IA Assistance, il faut changer la valeur dans `ecoute-pc/serveur.py` et dans `app-electron/renderer/app.js`.

Si tu veux utiliser un autre modele Ollama, changer `MODELE_ASSISTANT` dans `ecoute-pc/serveur.py`, puis installer le modele avec `ollama pull`.

## Depannage

### `python` n'est pas reconnu

Python n'est pas dans le PATH. Reinstaller Python en cochant `Add python.exe to PATH`, ou utiliser le chemin complet vers `python.exe`.

### `npm` n'est pas reconnu

Node.js n'est pas installe ou pas dans le PATH. Installer Node.js LTS depuis https://nodejs.org/, puis rouvrir PowerShell.

### Le statut Murmure reste rouge

Verifier que:

- Murmure est lance;
- l'API locale est activee dans Murmure;
- le port est bien `4800`;
- aucun pare-feu ou antivirus ne bloque `127.0.0.1:4800`.

### L'ecoute PC ne demarre pas

Verifier que le PC utilise bien Windows et que le peripherique audio de sortie par defaut fonctionne. La capture PC utilise WASAPI loopback via PyAudioWPatch.

### L'assistant indique Ollama hors ligne

Verifier que:

- Ollama est installe;
- Ollama est lance;
- le modele est installe avec `ollama pull qwen3.5:4b`;
- l'API Ollama repond sur `http://127.0.0.1:11434`.

### Le port `4900` est deja utilise

Fermer l'autre instance de IA Assistance ou l'autre programme qui utilise ce port. Le serveur Python ecoute sur `127.0.0.1:4900`.

## Developpement

Lancer seulement l'interface Electron:

```powershell
cd app-electron
npm start
```

Lancer seulement le serveur Python:

```powershell
cd ecoute-pc
.\.venv\Scripts\python.exe serveur.py
```

Verifier rapidement les fichiers Python:

```powershell
cd ecoute-pc
.\.venv\Scripts\python.exe -m py_compile ecoute_pc.py moteur.py serveur.py
```

## Remerciements

Un tres grand merci a [Kieirra/murmure](https://github.com/Kieirra/murmure). IA Assistance s'appuie sur Murmure comme base de transcription locale: sans ce projet open source, ce hub n'aurait pas le meme sens ni la meme qualite.

Merci egalement aux projets open source utilises dans cette couche: Electron, FastAPI, PyAudioWPatch, NumPy, Requests, Uvicorn et Ollama.

## Note importante

Ce depot ne vend pas et ne remplace pas Murmure. Il fournit une interface et un moteur d'ecoute autour de l'API locale de Murmure.

Les transcriptions locales, les environnements virtuels, `node_modules` et les copies locales de Murmure sont ignores par Git.
