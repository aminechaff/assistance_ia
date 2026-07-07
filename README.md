# IA Assistance

IA Assistance est un hub local de transcription audio pour Windows. Il permet d'ecouter le son du PC, le microphone, de transcrire en continu via l'API locale de Murmure, puis d'interroger la transcription avec un assistant Ollama.

Le projet est pense comme une couche pratique au-dessus de Murmure: interface Electron, serveur FastAPI, capture audio WASAPI loopback, historique Markdown et assistant local.

## Fonctionnalites

- Ecoute du son du PC: YouTube, Discord, Teams, musique, navigateur, etc.
- Ecoute du microphone.
- Transcription en direct via Murmure en local.
- Historique des transcriptions en fichiers Markdown.
- Renommage, edition et suppression des transcriptions depuis l'interface.
- Assistant local via Ollama pour resumer, extraire les points cles, lister les actions ou poser une question.
- Lancement simple avec `IA Assistance.cmd`.

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

- Windows 10 ou plus recent.
- Node.js et npm pour l'interface Electron.
- Python 3.11+ avec un environnement virtuel dans `ecoute-pc/.venv`.
- Murmure installe, lance, avec l'API locale activee sur le port `4800`.
- Ollama lance sur le port `11434` pour les fonctions assistant.
- Modele Ollama attendu par defaut: `qwen3.5:4b`.

## Installation

Installer les dependances Electron:

```powershell
cd app-electron
npm install
```

Installer les dependances Python:

```powershell
cd ..\ecoute-pc
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Installer le modele Ollama optionnel:

```powershell
ollama pull qwen3.5:4b
```

## Utilisation

1. Lancer Murmure.
2. Activer l'API locale de Murmure dans les parametres systeme, port `4800`.
3. Lancer Ollama si les fonctions assistant sont souhaitees.
4. Double-cliquer sur `IA Assistance.cmd`.

L'interface permet ensuite de demarrer ou arreter l'ecoute du PC et du micro, puis de consulter l'historique.

## Configuration des ports

Les ports utilises par defaut sont:

- `4800`: API locale Murmure.
- `4900`: serveur IA Assistance.
- `11434`: API locale Ollama.

Ces valeurs sont actuellement definies dans le code Python et JavaScript.

## Remerciements

Un tres grand merci a [Kieirra/murmure](https://github.com/Kieirra/murmure). IA Assistance s'appuie sur Murmure comme base de transcription locale: sans ce projet open source, ce hub n'aurait pas le meme sens ni la meme qualite.

Merci egalement aux projets open source utilises dans cette couche: Electron, FastAPI, PyAudioWPatch, NumPy, Requests, Uvicorn et Ollama.

## Notes

Ce depot ne vend pas et ne remplace pas Murmure. Il fournit une interface et un moteur d'ecoute autour de l'API locale de Murmure.

Les transcriptions locales, les environnements virtuels, `node_modules` et les copies locales de Murmure sont ignores par Git.
