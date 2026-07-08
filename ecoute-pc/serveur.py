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
import re
from pathlib import Path

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

import moteur

OLLAMA = "http://127.0.0.1:11434"
MODELE_ASSISTANT = "qwen3.5:4b"
MAX_TRANSCRIPTION_CHARS = 24000
BALISE_REFLEXION = re.compile(r"<think\b[^>]*>.*?</think>", re.IGNORECASE | re.DOTALL)

PROMPTS_ASSISTANT = {
    "resume": (
        "Produit un résumé clair et utile de cette transcription. "
        "Structure la réponse avec: Résumé court, Détails importants, Conclusion."
    ),
    "points": (
        "Extrais les points clés. Classe-les par thèmes si possible. "
        "Chaque point doit être court, concret et compréhensible sans relire toute la transcription."
    ),
    "actions": (
        "Liste les actions à faire, décisions prises, échéances et personnes concernées. "
        "Si une information manque, écris 'Non précisé' plutôt que d'inventer."
    ),
    "compte_rendu": (
        "Transforme cette transcription en compte-rendu propre. "
        "Utilise les sections: Contexte, Sujets abordés, Décisions, Actions à suivre, Points ouverts."
    ),
    "famille": (
        "Explique cette transcription comme à un parent occupé qui veut comprendre vite. "
        "Sois simple, chaleureux, pratique. Termine par 'Ce que je dois retenir'."
    ),
    "etudiant": (
        "Transforme cette transcription en fiche de révision pour étudiant. "
        "Utilise: Notions importantes, Définitions, Plan logique, Questions possibles, À mémoriser."
    ),
    "doctorat": (
        "Analyse cette transcription pour un profil recherche/doctorat. "
        "Fais ressortir problématique, hypothèses, méthode, limites, concepts, pistes de recherche et références à vérifier."
    ),
    "simplifier": (
        "Réécris les idées principales en langage très simple, sans jargon inutile. "
        "Ajoute une analogie courte si elle aide vraiment."
    ),
}


def preparer_transcription(contenu: str) -> tuple[str, bool]:
    contenu = contenu.strip()
    if len(contenu) <= MAX_TRANSCRIPTION_CHARS:
        return contenu, False
    debut = contenu[: MAX_TRANSCRIPTION_CHARS // 2]
    fin = contenu[-MAX_TRANSCRIPTION_CHARS // 2 :]
    extrait = (
        debut
        + "\n\n[... transcription raccourcie pour rester dans le contexte du modèle ...]\n\n"
        + fin
    )
    return extrait, True


def nettoyer_reponse_assistant(texte: str) -> str:
    texte = BALISE_REFLEXION.sub("", texte)
    texte = texte.replace("<think>", "").replace("</think>", "")
    return texte


def morceaux_visibles_ollama(reponse):
    """Filtre le raisonnement interne des modèles qui l'exposent malgré les consignes."""
    dans_reflexion = False
    tampon = ""

    for brut in reponse.iter_lines():
        if not brut:
            continue
        morceau = json.loads(brut)
        message = morceau.get("message", {})
        texte = message.get("content", "")
        if not texte:
            continue

        tampon += texte
        while tampon:
            minuscule = tampon.lower()
            if dans_reflexion:
                fin = minuscule.find("</think>")
                if fin == -1:
                    tampon = tampon[-16:]
                    break
                tampon = tampon[fin + len("</think>") :]
                dans_reflexion = False
                continue

            debut = minuscule.find("<think")
            fin_orpheline = minuscule.find("</think>")
            if fin_orpheline != -1 and (debut == -1 or fin_orpheline < debut):
                tampon = tampon[fin_orpheline + len("</think>") :]
                continue
            if debut == -1:
                retenu = ""
                for prefixe in ("<think", "<thin", "<thi", "<th", "<t", "<"):
                    if minuscule.endswith(prefixe):
                        retenu = tampon[-len(prefixe) :]
                        tampon = tampon[: -len(prefixe)]
                        break
                visible = nettoyer_reponse_assistant(tampon)
                tampon = retenu
                if visible:
                    yield visible
                break

            visible = nettoyer_reponse_assistant(tampon[:debut])
            if visible:
                yield visible
            fermeture = minuscule.find(">", debut)
            if fermeture == -1:
                tampon = tampon[debut:]
                break
            tampon = tampon[fermeture + 1 :]
            dans_reflexion = True

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
    etait_actif = transcripteur.fichier_actif == fichier
    fichier.unlink()
    if etait_actif:
        transcripteur.fichier_actif = None  # une nouvelle session se créera à la prochaine ligne
    return {"ok": True, "etait_actif": etait_actif}


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
    """corps = {"action": ..., "nom": fichier optionnel, "question": "..."}"""
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
    contenu, tronque = preparer_transcription(fichier.read_text(encoding="utf-8"))

    if action == "question":
        consigne = corps.get("question", "").strip()
        if not consigne:
            raise HTTPException(400, "question vide")
        consigne = (
            "Réponds à cette question sur la transcription. "
            "Adapte ton niveau de détail à la question, puis termine par une réponse courte en une phrase. "
            f"Question: {consigne}"
        )
    elif action in PROMPTS_ASSISTANT:
        consigne = PROMPTS_ASSISTANT[action]
    else:
        raise HTTPException(400, "action inconnue")

    def generer():
        try:
            requete = {
                "model": MODELE_ASSISTANT,
                "stream": True,
                "think": False,
                "options": {
                    "temperature": 0.2,
                },
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Tu es l'assistant universel d'une application de transcription audio. "
                            "Tu aides aussi bien un parent pressé, un étudiant, un professionnel, "
                            "qu'un doctorant. Tu réponds toujours en français, avec un ton clair, "
                            "direct et utile. Tu ne dois pas inventer les informations absentes. "
                            "Si une transcription est confuse, tu le dis et tu proposes une lecture probable. "
                            "Tu donnes uniquement la réponse finale. "
                            "N'écris jamais de balise <think>, de plan de réflexion, de brouillon, "
                            "ni d'étapes de raisonnement interne."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Fichier analysé: {fichier.name}\n"
                            f"Transcription raccourcie: {'oui' if tronque else 'non'}\n\n"
                            f"Mission:\n{consigne}\n\n"
                            "Réponds uniquement avec le résultat final, en français. "
                            "Utilise des titres courts et des puces quand c'est utile. "
                            "Ne montre jamais tes étapes de réflexion.\n\n"
                            f"<transcription>\n{contenu}\n</transcription>"
                        ),
                    },
                ],
            }

            reponse = requests.post(
                f"{OLLAMA}/api/chat",
                json=requete,
                stream=True,
                timeout=300,
            )
            if reponse.status_code == 400:
                reponse.close()
                requete.pop("think", None)
                reponse = requests.post(
                    f"{OLLAMA}/api/chat",
                    json=requete,
                    stream=True,
                    timeout=300,
                )

            with reponse as r:
                r.raise_for_status()
                contenu_visible = False
                for texte in morceaux_visibles_ollama(r):
                    contenu_visible = True
                    yield texte
                if not contenu_visible:
                    yield "Je n'ai pas reçu de réponse finale exploitable. Relance la demande ou essaie une question plus courte."
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
