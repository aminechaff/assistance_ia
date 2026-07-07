# -*- coding: utf-8 -*-
"""
Écoute PC — capture tout ce que l'ordinateur joue (YouTube, Discord, Teams, musique…)
et le transcrit en continu via l'API locale de Murmure.

Prérequis : Murmure ouvert, avec « API locale » activée (Paramètres > Système, port 4800).

Usage :
    python ecoute_pc.py            # démarre l'écoute, Ctrl+C pour arrêter
La transcription s'affiche en direct et s'enregistre dans transcripts/.
"""

import io
import queue
import sys
import threading
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np
import requests
import pyaudiowpatch as pyaudio

# ----------------------------- Réglages -----------------------------------
MURMURE_API = "http://127.0.0.1:4800/api/transcribe"
SOURCE_LABEL = "PC"          # étiquette de la source dans la transcription
FRAME_MS = 100               # taille d'un bloc d'analyse (ms)
SILENCE_RMS = 250            # en dessous = silence (échelle int16, 0..32767)
SILENCE_FLUSH_S = 0.9        # durée de silence qui clôt un segment
MIN_SEGMENT_S = 1.2          # segments plus courts = ignorés (bruit)
MAX_SEGMENT_S = 20.0         # découpe forcée (musique/parole continue)
TRANSCRIPTS_DIR = Path(__file__).parent / "transcripts"
# ---------------------------------------------------------------------------


def trouver_loopback(pa: "pyaudio.PyAudio") -> dict:
    """Trouve le périphérique loopback WASAPI correspondant à la sortie par défaut."""
    wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    sortie = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
    if not sortie.get("isLoopbackDevice"):
        for loopback in pa.get_loopback_device_info_generator():
            if sortie["name"] in loopback["name"]:
                return loopback
        raise RuntimeError("Aucun périphérique loopback trouvé pour la sortie par défaut.")
    return sortie


def vers_wav_mono(frames: bytes, canaux: int, freq: int) -> bytes:
    """Convertit le PCM int16 capturé en WAV mono (Murmure rééchantillonne lui-même)."""
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


def transcrire(wav: bytes) -> str:
    reponse = requests.post(
        MURMURE_API,
        files={"audio": ("segment.wav", wav, "audio/wav")},
        timeout=120,
    )
    reponse.raise_for_status()
    return reponse.json().get("text", "").strip()


class Transcripteur(threading.Thread):
    """Consomme les segments audio et écrit la transcription (fichier + console)."""

    def __init__(self, fichier: Path, canaux: int, freq: int):
        super().__init__(daemon=True)
        self.file_attente: "queue.Queue[tuple[datetime, bytes] | None]" = queue.Queue()
        self.fichier = fichier
        self.canaux = canaux
        self.freq = freq

    def run(self):
        while True:
            element = self.file_attente.get()
            if element is None:
                return
            horodatage, frames = element
            try:
                texte = transcrire(vers_wav_mono(frames, self.canaux, self.freq))
            except requests.ConnectionError:
                print("⚠ API Murmure injoignable — active-la dans Paramètres > Système.")
                continue
            except Exception as e:  # segment illisible : on continue l'écoute
                print(f"⚠ transcription échouée : {e}")
                continue
            if not texte:
                continue
            ligne = f"[{horodatage:%H:%M:%S}] [{SOURCE_LABEL}] {texte}"
            print(ligne, flush=True)
            with open(self.fichier, "a", encoding="utf-8") as f:
                f.write(ligne + "\n")


def main():
    pa = pyaudio.PyAudio()
    try:
        peripherique = trouver_loopback(pa)
    except Exception as e:
        print(f"Erreur : {e}")
        sys.exit(1)

    freq = int(peripherique["defaultSampleRate"])
    canaux = int(peripherique["maxInputChannels"])
    frames_par_bloc = int(freq * FRAME_MS / 1000)

    TRANSCRIPTS_DIR.mkdir(exist_ok=True)
    fichier = TRANSCRIPTS_DIR / f"{datetime.now():%Y-%m-%d_%H%M%S}.md"
    fichier.write_text(
        f"# Écoute PC — {datetime.now():%d/%m/%Y %H:%M}\n"
        f"Périphérique : {peripherique['name']}\n\n",
        encoding="utf-8",
    )

    transcripteur = Transcripteur(fichier, canaux, freq)
    transcripteur.start()

    flux = pa.open(
        format=pyaudio.paInt16,
        channels=canaux,
        rate=freq,
        input=True,
        input_device_index=peripherique["index"],
        frames_per_buffer=frames_par_bloc,
    )

    print(f"🎧 Écoute de : {peripherique['name']}")
    print(f"📄 Transcription : {fichier}")
    print("Lance un son (YouTube, Discord…) — Ctrl+C pour arrêter.\n")

    segment: list[bytes] = []
    debut_segment: datetime | None = None
    silence_depuis = 0.0

    def flush():
        nonlocal segment, debut_segment, silence_depuis
        duree = len(segment) * FRAME_MS / 1000
        if debut_segment and duree >= MIN_SEGMENT_S:
            transcripteur.file_attente.put((debut_segment, b"".join(segment)))
        segment = []
        debut_segment = None
        silence_depuis = 0.0

    try:
        while True:
            bloc = flux.read(frames_par_bloc, exception_on_overflow=False)
            rms = np.sqrt(np.mean(np.frombuffer(bloc, dtype=np.int16).astype(np.float64) ** 2))

            if rms >= SILENCE_RMS:
                if debut_segment is None:
                    debut_segment = datetime.now()
                segment.append(bloc)
                silence_depuis = 0.0
                if len(segment) * FRAME_MS / 1000 >= MAX_SEGMENT_S:
                    flush()
            elif debut_segment is not None:
                segment.append(bloc)  # garde un peu de silence (fins de mots)
                silence_depuis += FRAME_MS / 1000
                if silence_depuis >= SILENCE_FLUSH_S:
                    flush()
    except KeyboardInterrupt:
        print("\n⏹ Arrêt demandé — traitement des derniers segments…")
        flush()
        transcripteur.file_attente.put(None)
        transcripteur.join(timeout=60)
        print(f"✅ Transcription enregistrée : {fichier}")
    finally:
        flux.close()
        pa.terminate()


if __name__ == "__main__":
    main()
