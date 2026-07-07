const API = "http://127.0.0.1:4900";

const boutons = {
  pc: document.getElementById("btn-pc"),
  moi: document.getElementById("btn-moi"),
};
const cartes = {
  pc: document.getElementById("carte-pc"),
  moi: document.getElementById("carte-moi"),
};
const periphs = {
  pc: document.getElementById("periph-pc"),
  moi: document.getElementById("periph-moi"),
};
const flux = document.getElementById("flux");
const pastilleMurmure = document.getElementById("statut-murmure");
const listeTranscripts = document.getElementById("liste-transcripts");
const visionneuse = document.getElementById("visionneuse");

// ---------------------------------------------------------------- statut

const chips = {
  pc: document.getElementById("etat-pc"),
  moi: document.getElementById("etat-moi"),
};

const LIBELLES_ETAT = {
  attente: "à l'écoute…",
  parole: "🗣 parole détectée…",
  transcription: "⏳ transcription…",
};

function majChip(source, etat) {
  const chip = chips[source];
  chip.querySelector("em").textContent = LIBELLES_ETAT[etat] || etat;
  chip.classList.toggle("parole", etat === "parole");
  chip.classList.toggle("transcription", etat === "transcription");
}

async function rafraichirStatut() {
  try {
    const s = await (await fetch(`${API}/status`)).json();
    pastilleMurmure.classList.toggle("ok", s.murmure);
    for (const source of ["pc", "moi"]) {
      const actif = s[source];
      cartes[source].classList.toggle("actif", actif);
      boutons[source].textContent = actif ? "Arrêter" : "Démarrer";
      boutons[source].disabled = false;
      periphs[source].textContent = actif ? (s.peripheriques[source] || "") : "";
      chips[source].hidden = !actif;
    }
  } catch {
    pastilleMurmure.classList.remove("ok");
    // le moteur Python démarre peut-être encore — on réessaie
  }
}

for (const source of ["pc", "moi"]) {
  boutons[source].addEventListener("click", async () => {
    boutons[source].disabled = true;
    const actif = cartes[source].classList.contains("actif");
    await fetch(`${API}/ecoute/${source}/${actif ? "stop" : "start"}`, { method: "POST" });
    setTimeout(rafraichirStatut, 400);
  });
}

setInterval(rafraichirStatut, 4000);
rafraichirStatut();

// ---------------------------------------------------------------- flux live

let derniereSource = null;   // pour regrouper les segments consécutifs d'une même source

function ajouterLigne({ heure, source, texte }) {
  const propre = texte.replace(/</g, "&lt;");

  // Même source qui continue → on complète la dernière bulle au lieu d'en créer une nouvelle
  if (source === derniereSource && flux.lastElementChild) {
    const zone = flux.lastElementChild.querySelector(".texte");
    if (zone) {
      zone.innerHTML += " " + propre;
      flux.scrollTop = flux.scrollHeight;
      return;
    }
  }

  const div = document.createElement("div");
  div.className = "ligne";
  div.innerHTML = `
    <div class="meta"><span class="badge ${source}">${source.toUpperCase()}</span>${heure}</div>
    <div class="texte">${propre}</div>`;
  flux.appendChild(div);
  flux.scrollTop = flux.scrollHeight;
  derniereSource = source;
}

function connecterWebSocket() {
  const ws = new WebSocket("ws://127.0.0.1:4900/live");
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "etat") majChip(msg.source, msg.etat);
    else ajouterLigne(msg);
  };
  ws.onclose = () => setTimeout(connecterWebSocket, 2000);
  ws.onerror = () => ws.close();
}
connecterWebSocket();

// ---------------------------------------------------------------- historique

const sessionNom = document.getElementById("session-nom");
let transcriptOuvert = null;

async function rafraichirSession() {
  try {
    const s = await (await fetch(`${API}/session`)).json();
    sessionNom.textContent = s.nom ? s.nom.replace(".md", "") : "— (démarrera à la première phrase)";
    sessionNom.classList.toggle("active", !!s.nom);
  } catch { /* moteur pas prêt */ }
}

document.getElementById("btn-nouvelle-session").addEventListener("click", async () => {
  const nom = prompt("Nom de la nouvelle transcription (vide = date/heure) :", "");
  if (nom === null) return;
  await fetch(`${API}/session/nouvelle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nom: nom || null }),
  });
  flux.innerHTML = "";
  rafraichirSession();
  rafraichirHistorique();
});

async function rafraichirHistorique() {
  try {
    const fichiers = await (await fetch(`${API}/transcripts`)).json();
    listeTranscripts.innerHTML = "";
    for (const f of fichiers) {
      const li = document.createElement("li");
      const nom = document.createElement("span");
      nom.className = "nom";
      nom.textContent = `📄 ${f.nom.replace(".md", "")}`;
      li.appendChild(nom);
      if (f.actif) {
        const tag = document.createElement("span");
        tag.className = "tag-actif";
        tag.textContent = "en cours";
        li.appendChild(tag);
      }
      li.addEventListener("click", () => ouvrirTranscript(f.nom));
      listeTranscripts.appendChild(li);
    }
  } catch { /* moteur pas encore prêt */ }
}

async function ouvrirTranscript(nom) {
  const t = await (await fetch(`${API}/transcripts/${encodeURIComponent(nom)}`)).json();
  transcriptOuvert = t.nom;
  document.getElementById("visionneuse-titre").textContent = t.nom.replace(".md", "");
  document.getElementById("visionneuse-contenu").value = t.contenu;
  document.getElementById("visionneuse-etat").textContent = "";
  visionneuse.showModal();
}

document.getElementById("visionneuse-enregistrer").addEventListener("click", async () => {
  const r = await fetch(`${API}/transcripts/${encodeURIComponent(transcriptOuvert)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contenu: document.getElementById("visionneuse-contenu").value }),
  });
  document.getElementById("visionneuse-etat").textContent = r.ok ? "✅ Enregistré" : "⚠ Erreur";
});

document.getElementById("visionneuse-renommer").addEventListener("click", async () => {
  const nouveau = prompt("Nouveau nom :", transcriptOuvert.replace(".md", ""));
  if (!nouveau) return;
  const r = await fetch(`${API}/transcripts/${encodeURIComponent(transcriptOuvert)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nouveau_nom: nouveau }),
  });
  if (r.ok) {
    const rep = await r.json();
    transcriptOuvert = rep.nom;
    document.getElementById("visionneuse-titre").textContent = rep.nom.replace(".md", "");
    rafraichirHistorique();
    rafraichirSession();
  } else {
    document.getElementById("visionneuse-etat").textContent = "⚠ Renommage impossible (nom déjà pris ?)";
  }
});

document.getElementById("visionneuse-supprimer").addEventListener("click", async () => {
  if (!confirm(`Supprimer définitivement « ${transcriptOuvert.replace(".md", "")} » ?`)) return;
  await fetch(`${API}/transcripts/${encodeURIComponent(transcriptOuvert)}`, { method: "DELETE" });
  visionneuse.close();
  rafraichirHistorique();
  rafraichirSession();
});

document.getElementById("visionneuse-fermer").addEventListener("click", () => visionneuse.close());
setInterval(rafraichirHistorique, 10000);
setInterval(rafraichirSession, 5000);
rafraichirHistorique();
rafraichirSession();

// ---------------------------------------------------------------- assistant

const statutAssistant = document.getElementById("assistant-statut");
const champQuestion = document.getElementById("champ-question");
const btnQuestion = document.getElementById("btn-question");
const btnsAssistant = [...document.querySelectorAll(".btn-assistant")];

async function rafraichirAssistant() {
  try {
    const s = await (await fetch(`${API}/assistant/disponible`)).json();
    if (s.pret) {
      statutAssistant.textContent = `🧠 ${s.modele} prêt`;
      statutAssistant.classList.add("pret");
    } else {
      statutAssistant.textContent = s.ollama ? `téléchargement de ${s.modele}…` : "assistant hors ligne (Ollama fermé ?)";
      statutAssistant.classList.remove("pret");
    }
  } catch { /* moteur pas prêt */ }
}
setInterval(rafraichirAssistant, 8000);
rafraichirAssistant();

function verrouillerAssistant(v) {
  btnsAssistant.forEach((b) => (b.disabled = v));
  btnQuestion.disabled = v;
}

async function demanderAssistant(action, question = null) {
  verrouillerAssistant(true);
  const div = document.createElement("div");
  div.className = "ligne assistant";
  const heure = new Date().toLocaleTimeString("fr-FR");
  div.innerHTML = `<div class="meta"><span class="badge assistant">🤖 ASSISTANT</span>${heure}</div><div class="texte">⏳ réflexion…</div>`;
  flux.appendChild(div);
  flux.scrollTop = flux.scrollHeight;
  const zone = div.querySelector(".texte");

  try {
    const r = await fetch(`${API}/assistant`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, question }),
    });
    if (!r.ok) {
      zone.textContent = `⚠ ${(await r.json()).detail || "erreur"}`;
      return;
    }
    zone.textContent = "";
    const lecteur = r.body.getReader();
    const decodeur = new TextDecoder();
    while (true) {
      const { done, value } = await lecteur.read();
      if (done) break;
      zone.textContent += decodeur.decode(value, { stream: true });
      flux.scrollTop = flux.scrollHeight;
    }
  } catch (e) {
    zone.textContent = `⚠ ${e.message}`;
  } finally {
    verrouillerAssistant(false);
  }
}

btnsAssistant.forEach((b) =>
  b.addEventListener("click", () => demanderAssistant(b.dataset.action)),
);

function envoyerQuestion() {
  const q = champQuestion.value.trim();
  if (!q) return;
  champQuestion.value = "";
  demanderAssistant("question", q);
}
btnQuestion.addEventListener("click", envoyerQuestion);
champQuestion.addEventListener("keydown", (e) => {
  if (e.key === "Enter") envoyerQuestion();
});
