# -*- coding: utf-8 -*-
"""
Moteur d'écoute — capture l'audio (loopback PC ou microphone), le découpe en
segments de parole, et le fait transcrire par l'API locale de Murmure.

Utilisé par serveur.py (piloté par l'app Electron) et réutilisable en CLI.
"""

import io
import queue
import re
import threading
import wave
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
import requests
import pyaudiowpatch as pyaudio

MURMURE_API = "http://127.0.0.1:4800/api/transcribe"
LANGUE_TRANSCRIPTION = "fr"
FRAME_MS = 100
SILENCE_RMS = 280
SILENCE_FLUSH_S = 1.15
MIN_SEGMENT_S = 1.8
MAX_SEGMENT_S = 12.0
TRANSCRIPTS_DIR = Path(__file__).parent / "transcripts"
ESPACES_RE = re.compile(r"\s+")
PONCTUATION_RE = re.compile(r"[\"'`.,;:!?()\[\]{}<>«»“”‘’…-]+")
ACCENTS_FR_RE = re.compile(r"[àâçéèêëîïôùûüÿœæ]", re.IGNORECASE)
FRAGMENTS_ANGLAIS_PARASITES_RE = re.compile(
    r"\b(?:"
    r"i\s*(?:'|’)?ve\s+got(?:\s+the)?|"
    r"i\s+got(?:\s+the)?|"
    r"don\s*(?:'|’)?t|"
    r"do\s+not|"
    r"not\s+the\s+(?:bush|bus)|"
    r"of\s+people\s+who\s+s?"
    r")\b[ \t\r\n\"'`.,;:!?()]*",
    re.IGNORECASE,
)

CORRECTIONS_COURTES_FR = {
    "i think": "Je pense.",
    "i think so": "Je pense que oui.",
    "yes": "Oui.",
    "yeah": "Oui.",
    "yeah yeah": "Oui, oui.",
    "ok": "D'accord.",
    "okay": "D'accord.",
    "all right": "D'accord.",
    "thank you": "Merci.",
    "thanks": "Merci.",
}

FAUX_POSITIFS_ANGLAIS_FR = {
    "don t",
    "dont",
    "i ve got",
    "i ve got the",
    "ive got",
    "ive got the",
    "not the bush",
    "of people who s",
    "of people who",
    "people who s",
}

MOTS_FRANCAIS_INDICES = {
    "ah",
    "alors",
    "appelé",
    "appele",
    "avec",
    "bon",
    "bonjour",
    "ça",
    "ca",
    "ce",
    "cest",
    "comme",
    "dans",
    "daccord",
    "de",
    "des",
    "donc",
    "est",
    "et",
    "il",
    "jai",
    "je",
    "la",
    "le",
    "les",
    "mais",
    "mes",
    "non",
    "oui",
    "parce",
    "pas",
    "pour",
    "que",
    "quoi",
    "suis",
    "sur",
    "tu",
    "un",
    "une",
}

MOTS_REMPLISSAGE_ANGLAIS = {
    "ah",
    "eh",
    "er",
    "hm",
    "hmm",
    "mhm",
    "mm",
    "mmhm",
    "mmm",
    "uh",
    "uhh",
    "um",
    "umm",
    "yeah",
}

EvenementCallback = Callable[[dict], None]
# Deux types d'événements circulent vers l'UI :
#   {"type": "ligne", "heure", "source", "texte"}   → une phrase transcrite
#   {"type": "etat",  "source", "etat"}             → attente | parole | transcription


def murmure_disponible() -> bool:
    try:
        requests.post(MURMURE_API, timeout=3)
        return True
    except requests.ConnectionError:
        return False
    except requests.RequestException:
        return True  # il a répondu (même une erreur 4xx) : l'API est là


def trouver_peripherique(pa: pyaudio.PyAudio, source: str) -> dict:
    """source = "pc" (loopback de la sortie par défaut) ou "moi" (micro par défaut)."""
    if source == "moi":
        return pa.get_default_input_device_info()
    wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    sortie = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
    if sortie.get("isLoopbackDevice"):
        return sortie
    for loopback in pa.get_loopback_device_info_generator():
        if sortie["name"] in loopback["name"]:
            return loopback
    raise RuntimeError("Aucun périphérique loopback trouvé pour la sortie par défaut.")


def vers_wav_mono(frames: bytes, canaux: int, freq: int) -> bytes:
    audio = np.frombuffer(frames, dtype=np.int16)
    if canaux > 1:
        audio = audio.reshape(-1, canaux).mean(axis=1).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(freq)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()


def _normaliser_pour_filtre(texte: str) -> str:
    texte = ESPACES_RE.sub(" ", texte).strip().lower()
    texte = PONCTUATION_RE.sub(" ", texte)
    return ESPACES_RE.sub(" ", texte).strip()


def _semble_contenir_du_francais(texte: str, cle: str) -> bool:
    if ACCENTS_FR_RE.search(texte):
        return True
    mots = cle.split()
    return sum(1 for mot in mots if mot in MOTS_FRANCAIS_INDICES) >= 2


def _nettoyer_fragments_anglais_parasites(texte: str) -> str | None:
    if not FRAGMENTS_ANGLAIS_PARASITES_RE.search(texte):
        return texte
    nettoye = FRAGMENTS_ANGLAIS_PARASITES_RE.sub(" ", texte)
    nettoye = re.sub(r"\s+([,.;:!?])", r"\1", nettoye)
    nettoye = ESPACES_RE.sub(" ", nettoye).strip(" \t\r\n,.;:!?-")
    return nettoye or None


def stabiliser_transcription_francaise(texte: str) -> str | None:
    """Limite les faux départs anglais fréquents sur les courts segments audio."""
    texte = ESPACES_RE.sub(" ", texte).strip()
    if not texte:
        return None

    if LANGUE_TRANSCRIPTION.lower() != "fr":
        return texte

    cle = _normaliser_pour_filtre(texte.replace("-", " "))
    if cle in CORRECTIONS_COURTES_FR:
        return CORRECTIONS_COURTES_FR[cle]
    if cle in FAUX_POSITIFS_ANGLAIS_FR:
        return None

    mots = [mot.strip(" \t\r\n\"'`.,;:!?()[]{}<>«»“”‘’…-").lower() for mot in cle.split()]
    mots = [mot for mot in mots if mot]
    if 0 < len(mots) <= 4 and all(mot in MOTS_REMPLISSAGE_ANGLAIS for mot in mots):
        return None

    if _semble_contenir_du_francais(texte, cle):
        return _nettoyer_fragments_anglais_parasites(texte)

    return texte


class Transcripteur(threading.Thread):
    """Worker unique (l'API Murmure est séquentielle) partagé par tous les écouteurs."""

    def __init__(self, on_evenement: EvenementCallback):
        super().__init__(daemon=True)
        self.file_attente: queue.Queue = queue.Queue()
        self.on_evenement = on_evenement
        self.fichier_actif: Path | None = None
        self._session_lock = threading.RLock()
        self._session_aliases: dict[Path, Path] = {}
        TRANSCRIPTS_DIR.mkdir(exist_ok=True)

    def nouvelle_session(self, nom: str | None = None) -> Path:
        """Démarre un nouveau fichier de transcription ; les lignes suivantes y vont."""
        with self._session_lock:
            nom = (nom or f"{datetime.now():%Y-%m-%d_%Hh%M}").strip()
            nom = "".join(c for c in nom if c not in '\\/:*?"<>|').strip() or f"{datetime.now():%Y-%m-%d_%Hh%M}"
            if nom.lower().endswith(".md"):
                nom = nom[:-3].strip() or f"{datetime.now():%Y-%m-%d_%Hh%M}"
            fichier = TRANSCRIPTS_DIR / f"{nom}.md"
            i = 2
            while fichier.exists():
                fichier = TRANSCRIPTS_DIR / f"{nom} ({i}).md"
                i += 1
            fichier.write_text(f"# {fichier.stem} — {datetime.now():%d/%m/%Y %H:%M}\n\n", encoding="utf-8")
            self.fichier_actif = fichier
            return fichier

    def session_pour_segment(self) -> Path:
        with self._session_lock:
            if self.fichier_actif is None or not self.fichier_actif.exists():
                return self.nouvelle_session()
            return self.fichier_actif

    def remplacer_session(self, ancien: Path, nouveau: Path):
        with self._session_lock:
            self._session_aliases[ancien] = nouveau
            if self.fichier_actif == ancien:
                self.fichier_actif = nouveau

    def resoudre_session(self, fichier: Path) -> Path:
        with self._session_lock:
            while fichier in self._session_aliases:
                fichier = self._session_aliases[fichier]
            return fichier

    def soumettre(self, horodatage: datetime, source: str, frames: bytes, canaux: int, freq: int):
        fichier = self.session_pour_segment()
        self.file_attente.put((horodatage, source, frames, canaux, freq, fichier))

    def run(self):
        while True:
            horodatage, source, frames, canaux, freq, fichier = self.file_attente.get()
            try:
                reponse = requests.post(
                    MURMURE_API,
                    data={"language": LANGUE_TRANSCRIPTION, "lang": LANGUE_TRANSCRIPTION},
                    files={"audio": ("segment.wav", vers_wav_mono(frames, canaux, freq), "audio/wav")},
                    timeout=120,
                )
                reponse.raise_for_status()
                texte = stabiliser_transcription_francaise(reponse.json().get("text", ""))
            except requests.ConnectionError:
                # Murmure fermé ou API désactivée : on signale l'état, sans polluer le flux
                self.on_evenement({"type": "murmure", "disponible": False})
                continue
            except Exception as e:
                self.on_evenement({"type": "ligne", "heure": f"{horodatage:%H:%M:%S}", "source": "erreur", "texte": str(e)})
                continue
            finally:
                if self.file_attente.empty():
                    self.on_evenement({"type": "etat", "source": source, "etat": "attente"})
            if not texte:
                continue
            fichier = self.resoudre_session(fichier)
            ligne = {
                "type": "ligne",
                "heure": f"{horodatage:%H:%M:%S}",
                "source": source,
                "texte": texte,
                "session": fichier.name,
            }
            with open(fichier, "a", encoding="utf-8") as f:
                f.write(f"[{ligne['heure']}] [{source.upper()}] {texte}\n")
            self.on_evenement(ligne)


class Ecouteur(threading.Thread):
    """Capture une source audio en continu et découpe en segments de parole."""

    def __init__(self, source: str, transcripteur: Transcripteur):
        super().__init__(daemon=True)
        self.source = source          # "pc" ou "moi"
        self.transcripteur = transcripteur
        self._stop_event = threading.Event()
        self.nom_peripherique = "?"

    def _etat(self, etat: str):
        self.transcripteur.on_evenement({"type": "etat", "source": self.source, "etat": etat})

    def arreter(self):
        self._stop_event.set()

    def run(self):
        pa = pyaudio.PyAudio()
        try:
            peripherique = trouver_peripherique(pa, self.source)
            self.nom_peripherique = peripherique["name"]
            freq = int(peripherique["defaultSampleRate"])
            canaux = int(peripherique["maxInputChannels"]) if self.source == "pc" else 1
            frames_par_bloc = int(freq * FRAME_MS / 1000)

            flux = pa.open(
                format=pyaudio.paInt16,
                channels=canaux,
                rate=freq,
                input=True,
                input_device_index=peripherique["index"],
                frames_per_buffer=frames_par_bloc,
            )

            segment: list[bytes] = []
            debut: datetime | None = None
            silence = 0.0

            def flush():
                nonlocal segment, debut, silence
                if debut and len(segment) * FRAME_MS / 1000 >= MIN_SEGMENT_S:
                    self.transcripteur.soumettre(debut, self.source, b"".join(segment), canaux, freq)
                    self._etat("transcription")
                else:
                    self._etat("attente")
                segment, debut, silence = [], None, 0.0

            self._etat("attente")
            while not self._stop_event.is_set():
                bloc = flux.read(frames_par_bloc, exception_on_overflow=False)
                rms = np.sqrt(np.mean(np.frombuffer(bloc, dtype=np.int16).astype(np.float64) ** 2))
                if rms >= SILENCE_RMS:
                    if debut is None:
                        debut = datetime.now()
                        self._etat("parole")
                    segment.append(bloc)
                    silence = 0.0
                    if len(segment) * FRAME_MS / 1000 >= MAX_SEGMENT_S:
                        flush()
                elif debut is not None:
                    segment.append(bloc)
                    silence += FRAME_MS / 1000
                    if silence >= SILENCE_FLUSH_S:
                        flush()

            flush()
            flux.close()
        finally:
            pa.terminate()
