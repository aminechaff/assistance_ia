# -*- coding: utf-8 -*-
"""
Serveur de pilotage du moteur d'écoute — l'app Electron s'y connecte.

    HTTP  http://127.0.0.1:4900
      GET  /status                     état des écouteurs + Murmure
      POST /ecoute/{pc|moi}/start      démarre une source
      POST /ecoute/{pc|moi}/stop       arrête une source
      GET  /transcripts                liste des fichiers de transcription
      GET  /transcripts/{nom}          contenu d'un fichier
    WS    /live                        lignes transcrites en temps réel (JSON)
"""

import asyncio
import json
import queue
from pathlib import Path

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

import moteur

OLLAMA = "http://127.0.0.1:11434"
MODELE_ASSISTANT = "qwen3.5:4b"

PROMPTS_ASSISTANT = {
    "resume": "Résume cette transcription en français, de façon claire et structurée. Va à l'essentiel.",
    "points": "Liste les points clés de cette transcription en français, sous forme de puces courtes.",
    "actions": "Liste les actions à faire / décisions prises mentionnées dans cette transcription, en français. S'il n'y en a aucune, dis-le simplement.",
}

app = FastAPI(title="IA Assistance — moteur d'écoute")

lignes_a_diffuser: queue.Queue = queue.Queue()
clients_ws: set[WebSocket] = set()
ecouteurs: dict[str, moteur.Ecouteur] = {}

transcripteur = moteur.Transcripteur(on_evenement=lignes_a_diffuser.put)
transcripteur.start()


@app.on_event("startup")
async def demarrer_diffusion():
    asyncio.create_task(boucle_diffusion())


async def boucle_diffusion():
    """Relaie les lignes transcrites (threads) vers les clients WebSocket (asyncio)."""
    loop = asyncio.get_event_loop()
    while True:
        ligne = await loop.run_in_executor(None, lignes_a_diffuser.get)
        deconnectes = set()
        for ws in clients_ws:
            try:
                await ws.send_json(ligne)
            except Exception:
                deconnectes.add(ws)
        clients_ws.difference_update(deconnectes)


@app.get("/status")
def status():
    return {
        "murmure": moteur.murmure_disponible(),
        "pc": "pc" in ecouteurs and ecouteurs["pc"].is_alive(),
        "moi": "moi" in ecouteurs and ecouteurs["moi"].is_alive(),
        "peripheriques": {s: e.nom_peripherique for s, e in ecouteurs.items() if e.is_alive()},
    }


@app.post("/ecoute/{source}/start")
def demarrer(source: str):
    if source not in ("pc", "moi"):
        raise HTTPException(400, "source inconnue (pc ou moi)")
    if source in ecouteurs and ecouteurs[source].is_alive():
        return {"ok": True, "deja_actif": True}
    e = moteur.Ecouteur(source, transcripteur)
    e.start()
    ecouteurs[source] = e
    return {"ok": True}


@app.post("/ecoute/{source}/stop")
def arreter(source: str):
    e = ecouteurs.get(source)
    if e and e.is_alive():
        e.arreter()
    return {"ok": True}


def _fichier_transcript(nom: str) -> Path:
    fichier = (moteur.TRANSCRIPTS_DIR / Path(nom).name).resolve()
    if fichier.parent != moteur.TRANSCRIPTS_DIR.resolve() or fichier.suffix != ".md":
        raise HTTPException(400, "nom invalide")
    return fichier


@app.get("/session")
def session_courante():
    f = transcripteur.fichier_actif
    return {"nom": f.name if f and f.exists() else None}


@app.post("/session/nouvelle")
def nouvelle_session(corps: dict | None = None):
    nom = (corps or {}).get("nom")
    fichier = transcripteur.nouvelle_session(nom)
    return {"ok": True, "nom": fichier.name}


@app.get("/transcripts")
def liste_transcripts():
    fichiers = sorted(moteur.TRANSCRIPTS_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    actif = transcripteur.fichier_actif
    return [
        {"nom": f.name, "taille": f.stat().st_size, "actif": actif is not None and f == actif}
        for f in fichiers
    ]


@app.get("/transcripts/{nom}")
def lire_transcript(nom: str):
    fichier = _fichier_transcript(nom)
    if not fichier.exists():
        raise HTTPException(404, "fichier introuvable")
    return {"nom": fichier.name, "contenu": fichier.read_text(encoding="utf-8")}


@app.put("/transcripts/{nom}")
def modifier_transcript(nom: str, corps: dict):
    """corps = {"contenu": "..."} pour éditer, et/ou {"nouveau_nom": "..."} pour renommer."""
    fichier = _fichier_transcript(nom)
    if not fichier.exists():
        raise HTTPException(404, "fichier introuvable")
    if "contenu" in corps:
        fichier.write_text(corps["contenu"], encoding="utf-8")
    if corps.get("nouveau_nom"):
        propre = "".join(c for c in corps["nouveau_nom"] if c not in '\\/:*?"<>|').strip()
        if not propre:
            raise HTTPException(400, "nouveau nom invalide")
        cible = _fichier_transcript(propre + ".md")
        if cible.exists():
            raise HTTPException(409, "un fichier porte déjà ce nom")
        fichier.rename(cible)
        if transcripteur.fichier_actif == fichier:
            transcripteur.fichier_actif = cible
        fichier = cible
    return {"ok": True, "nom": fichier.name}


@app.delete("/transcripts/{nom}")
def supprimer_transcript(nom: str):
    fichier = _fichier_transcript(nom)
    if not fichier.exists():
        raise HTTPException(404, "fichier introuvable")
    fichier.unlink()
    if transcripteur.fichier_actif == fichier:
        transcripteur.fichier_actif = None  # une nouvelle session se créera à la prochaine ligne
    return {"ok": True}


@app.get("/assistant/disponible")
def assistant_disponible():
    try:
        modeles = requests.get(f"{OLLAMA}/api/tags", timeout=3).json().get("models", [])
        noms = [m["name"] for m in modeles]
        return {"ollama": True, "modele": MODELE_ASSISTANT, "pret": any(MODELE_ASSISTANT in n for n in noms)}
    except requests.RequestException:
        return {"ollama": False, "modele": MODELE_ASSISTANT, "pret": False}


@app.post("/assistant")
def assistant(corps: dict):
    """corps = {"action": resume|points|actions|question, "nom": fichier, "question": "..."}"""
    action = corps.get("action")
    nom = corps.get("nom")
    if not nom:
        f = transcripteur.fichier_actif
        if not (f and f.exists()):
            raise HTTPException(400, "aucune transcription en cours — précise un fichier")
        nom = f.name
    fichier = _fichier_transcript(nom)
    if not fichier.exists():
        raise HTTPException(404, "fichier introuvable")
    contenu = fichier.read_text(encoding="utf-8")

    if action == "question":
        consigne = corps.get("question", "").strip()
        if not consigne:
            raise HTTPException(400, "question vide")
        consigne = f"Réponds en français à cette question sur la transcription : {consigne}"
    elif action in PROMPTS_ASSISTANT:
        consigne = PROMPTS_ASSISTANT[action]
    else:
        raise HTTPException(400, "action inconnue")

    def generer():
        try:
            with requests.post(
                f"{OLLAMA}/api/chat",
                json={
                    "model": MODELE_ASSISTANT,
                    "stream": True,
                    "messages": [
                        {"role": "system", "content": "Tu es l'assistant d'une application de transcription audio. Tu réponds toujours en français, sans balises <think>."},
                        {"role": "user", "content": f"{consigne}\n\n<transcription>\n{contenu}\n</transcription>"},
                    ],
                },
                stream=True,
                timeout=300,
            ) as r:
                r.raise_for_status()
                for brut in r.iter_lines():
                    if not brut:
                        continue
                    morceau = json.loads(brut)
                    texte = morceau.get("message", {}).get("content", "")
                    if texte:
                        yield texte
        except requests.RequestException as e:
            yield f"\n⚠ Assistant indisponible : {e}"

    return StreamingResponse(generer(), media_type="text/plain; charset=utf-8")


@app.websocket("/live")
async def live(ws: WebSocket):
    await ws.accept()
    clients_ws.add(ws)
    try:
        while True:
            await ws.receive_text()  # on ne reçoit rien d'utile, ça maintient la connexion
    except WebSocketDisconnect:
        clients_ws.discard(ws)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=4900, log_level="warning")
