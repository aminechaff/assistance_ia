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
const statutMoteur = document.getElementById("statut-moteur");
const statutOllama = document.getElementById("statut-ollama");
const statutTraduction = document.getElementById("statut-traduction");
const statutPcTop = document.getElementById("statut-pc-top");
const statutMoiTop = document.getElementById("statut-moi-top");
const listeTranscripts = document.getElementById("liste-transcripts");
const rechercheTranscripts = document.getElementById("recherche-transcripts");
const historiqueVide = document.getElementById("historique-vide");
const visionneuse = document.getElementById("visionneuse");
const toggleTraduction = document.getElementById("toggle-traduction");
const traductionEtat = document.getElementById("traduction-etat");
let assistantEnCours = false;
let transcriptsCache = [];
const CLE_TRADUCTION = "ia-assistance-traduction-active";
let traductionSouhaitee = null;

// ---------------------------------------------------------------- statut

const chips = {
  pc: document.getElementById("etat-pc"),
  moi: document.getElementById("etat-moi"),
};

const LIBELLES_ETAT = {
  attente: "a l'ecoute",
  parole: "parole detectee",
  transcription: "transcription",
};

const sourceStates = {
  pc: document.getElementById("source-state-pc"),
  moi: document.getElementById("source-state-moi"),
};

const statusTop = {
  pc: statutPcTop,
  moi: statutMoiTop,
};

function libelleSource(source) {
  if (source === "pc") return "PC";
  if (source === "moi") return "Micro";
  if (source === "traduction") return "TRAD";
  if (source === "erreur") return "Erreur";
  return source.toUpperCase();
}

function majPill(element, etat, texte = null) {
  if (!element) return;
  element.classList.toggle("ok", etat === "ok");
  element.classList.toggle("active", etat === "active");
  element.classList.toggle("warn", etat === "warn");
  element.classList.toggle("offline", etat === "offline");
  if (texte) {
    const label = element.querySelector("span:last-child");
    if (label) label.textContent = texte;
  }
}

function majChip(source, etat) {
  const chip = chips[source];
  chip.querySelector("em").textContent = LIBELLES_ETAT[etat] || etat;
  chip.classList.toggle("parole", etat === "parole");
  chip.classList.toggle("transcription", etat === "transcription");
  if (sourceStates[source]) {
    sourceStates[source].textContent = LIBELLES_ETAT[etat] || etat;
    sourceStates[source].classList.toggle("speaking", etat === "parole");
    sourceStates[source].classList.toggle("transcribing", etat === "transcription");
  }
  if (statusTop[source]) {
    majPill(statusTop[source], etat === "attente" ? "active" : "warn", source === "pc" ? "PC" : "Micro");
  }
}

async function rafraichirStatut() {
  try {
    const s = await (await fetch(`${API}/status`)).json();
    majPill(statutMoteur, "ok", "Moteur");
    pastilleMurmure.classList.toggle("ok", s.murmure);
    majPill(pastilleMurmure, s.murmure ? "ok" : "offline", "Murmure");
    document.getElementById("bandeau-murmure").hidden = s.murmure;
    for (const source of ["pc", "moi"]) {
      const actif = s[source];
      cartes[source].classList.toggle("actif", actif);
      boutons[source].textContent = actif ? "Arreter" : "Demarrer";
      boutons[source].disabled = assistantEnCours;
      periphs[source].textContent = actif ? (s.peripheriques[source] || "") : "";
      sourceStates[source].textContent = actif ? "actif" : "inactif";
      sourceStates[source].classList.toggle("active", actif);
      sourceStates[source].classList.toggle("speaking", false);
      sourceStates[source].classList.toggle("transcribing", false);
      majPill(statusTop[source], actif ? "active" : "offline", source === "pc" ? "PC" : "Micro");
      chips[source].hidden = !actif;
    }
  } catch {
    majPill(statutMoteur, "offline", "Moteur");
    pastilleMurmure.classList.remove("ok");
    majPill(pastilleMurmure, "offline", "Murmure");
    // le moteur Python démarre peut-être encore — on réessaie
  }
}

function afficherEtatTraduction(etat) {
  if (!toggleTraduction || !traductionEtat) return;
  const active = !!etat.active;
  toggleTraduction.checked = active;
  traductionEtat.textContent = active ? (etat.etat || "active") : "désactivée";

  let pillEtat = "offline";
  if (active && etat.etat === "ollama indisponible") pillEtat = "warn";
  else if (active && (etat.etat === "traduction" || etat.etat === "en attente")) pillEtat = "warn";
  else if (active) pillEtat = "ok";
  majPill(statutTraduction, pillEtat, active ? "Trad FR" : "Traduction");
}

async function configurerTraduction(active, memoriser = true) {
  if (!toggleTraduction) return;
  traductionSouhaitee = active;
  toggleTraduction.disabled = true;
  if (traductionEtat) traductionEtat.textContent = active ? "activation..." : "désactivation...";
  if (memoriser) localStorage.setItem(CLE_TRADUCTION, active ? "1" : "0");
  try {
    const r = await fetch(`${API}/traduction`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active }),
    });
    afficherEtatTraduction(await r.json());
  } catch {
    afficherEtatTraduction({ active: false, etat: "moteur en attente" });
    setTimeout(() => {
      if (traductionSouhaitee === active) configurerTraduction(active, false);
    }, 2000);
  } finally {
    toggleTraduction.disabled = false;
  }
}

async function rafraichirTraduction() {
  try {
    const etat = await (await fetch(`${API}/traduction`)).json();
    if (traductionSouhaitee === true && !etat.active) {
      configurerTraduction(true, false);
      return;
    }
    afficherEtatTraduction(etat);
  } catch {
    afficherEtatTraduction({ active: false, etat: "moteur en attente" });
  }
}

if (toggleTraduction) {
  toggleTraduction.addEventListener("change", () => configurerTraduction(toggleTraduction.checked));
  const memorisee = localStorage.getItem(CLE_TRADUCTION);
  if (memorisee !== null) configurerTraduction(memorisee === "1", false);
  else rafraichirTraduction();
  setInterval(rafraichirTraduction, 7000);
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
const DISTANCE_AUTOSCROLL = 80;

function estPresDuBas() {
  return flux.scrollHeight - flux.scrollTop - flux.clientHeight < DISTANCE_AUTOSCROLL;
}

function scrollSiBesoin(doitSuivre) {
  if (doitSuivre) flux.scrollTop = flux.scrollHeight;
}

function ajouterLigne({ heure, source, texte, session = null, langue = null, langue_nom = null, source_originale = null }) {
  if (session && sessionActiveNom && session !== sessionActiveNom) return;

  const doitSuivre = estPresDuBas();
  const sourceRegroupable = source === "pc" || source === "moi";

  // Même source qui continue → on complète la dernière bulle au lieu d'en créer une nouvelle
  if (sourceRegroupable && source === derniereSource && flux.lastElementChild) {
    const zone = flux.lastElementChild.querySelector(".texte");
    if (zone) {
      zone.textContent += " " + texte;
      scrollSiBesoin(doitSuivre);
      return;
    }
  }

  const div = document.createElement("div");
  const classes = ["ligne"];
  if (source === "erreur") classes.push("erreur");
  if (source === "traduction") classes.push("traduction");
  div.className = classes.join(" ");

  const meta = document.createElement("div");
  meta.className = "meta";

  const badge = document.createElement("span");
  badge.className = `badge ${source}`;
  badge.textContent = libelleSource(source);

  const time = document.createElement("span");
  time.textContent = heure;

  meta.appendChild(badge);
  meta.appendChild(time);

  if (source === "traduction") {
    const detail = document.createElement("span");
    detail.className = "translation-meta";
    const langueAffichee = langue_nom || langue || "langue détectée";
    const origine = source_originale ? ` · depuis ${libelleSource(source_originale)}` : "";
    detail.textContent = `${langueAffichee} → français${origine}`;
    meta.appendChild(detail);
  }

  const zone = document.createElement("div");
  zone.className = "texte";
  zone.textContent = texte;

  div.appendChild(meta);
  div.appendChild(zone);
  flux.appendChild(div);
  scrollSiBesoin(doitSuivre);
  derniereSource = source;
}

function connecterWebSocket() {
  const ws = new WebSocket("ws://127.0.0.1:4900/live");
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "etat") majChip(msg.source, msg.etat);
    else if (msg.type === "murmure") {
      if (!msg.disponible) pastilleMurmure.classList.remove("ok");
    } else if (msg.type === "traduction") {
      afficherEtatTraduction(msg);
    } else ajouterLigne(msg);
  };
  ws.onclose = () => setTimeout(connecterWebSocket, 2000);
  ws.onerror = () => ws.close();
}
connecterWebSocket();

// ---------------------------------------------------------------- historique

const sessionNom = document.getElementById("session-nom");
const btnRenommerSession = document.getElementById("btn-renommer-session");
let transcriptOuvert = null;
let sessionActiveNom = null;

async function rafraichirSession() {
  try {
    const s = await (await fetch(`${API}/session`)).json();
    sessionActiveNom = s.nom || null;
    sessionNom.textContent = s.nom ? s.nom.replace(".md", "") : "En attente";
    sessionNom.classList.toggle("active", !!s.nom);
  } catch { /* moteur pas prêt */ }
}

document.getElementById("btn-nouvelle-session").addEventListener("click", async () => {
  const nom = prompt("Nom de la nouvelle transcription (vide = date/heure) :", "");
  if (nom === null) return;
  const sourcesARelancer = await sourcesActives();
  if (sourcesARelancer.length) {
    await Promise.all(sourcesARelancer.map((source) => fetch(`${API}/ecoute/${source}/stop`, { method: "POST" })));
    await new Promise((resolve) => setTimeout(resolve, 800));
  }
  const r = await fetch(`${API}/session/nouvelle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nom: nom || null }),
  });
  if (!r.ok) return alert((await r.json()).detail || "Creation impossible");
  const rep = await r.json();
  sessionActiveNom = rep.nom;
  sessionNom.textContent = rep.nom.replace(".md", "");
  sessionNom.classList.add("active");
  majCibleAssistant(null);
  flux.innerHTML = "";
  derniereSource = null;
  rafraichirHistorique();
  if (sourcesARelancer.length) {
    await Promise.all(sourcesARelancer.map((source) => fetch(`${API}/ecoute/${source}/start`, { method: "POST" }).catch(() => null)));
    setTimeout(rafraichirStatut, 500);
  }
});

btnRenommerSession.addEventListener("click", async () => {
  await rafraichirSession();
  if (!sessionActiveNom) {
    alert("Aucune transcription en cours a renommer.");
    return;
  }
  const actuel = sessionActiveNom.replace(".md", "");
  const nom = prompt("Nouveau nom de la transcription en cours :", actuel);
  if (!nom || nom === actuel) return;
  const r = await fetch(`${API}/session/renommer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nom }),
  });
  if (!r.ok) {
    alert((await r.json()).detail || "Renommage impossible");
    return;
  }
  const rep = await r.json();
  sessionActiveNom = rep.nom;
  sessionNom.textContent = rep.nom.replace(".md", "");
  if (transcriptAssistant) majCibleAssistant(rep.nom);
  rafraichirHistorique();
});

document.getElementById("btn-vider-ecran").addEventListener("click", () => {
  flux.innerHTML = "";     // n'efface que l'affichage, pas le fichier
  derniereSource = null;
});

async function rafraichirHistorique() {
  try {
    transcriptsCache = await (await fetch(`${API}/transcripts`)).json();
    renderHistorique();
  } catch { /* moteur pas encore prêt */ }
}

function renderHistorique() {
  const filtre = (rechercheTranscripts?.value || "").trim().toLowerCase();
  const fichiers = transcriptsCache.filter((f) => f.nom.toLowerCase().includes(filtre));
  listeTranscripts.innerHTML = "";
  historiqueVide.hidden = fichiers.length > 0;

  for (const f of fichiers) {
    const li = document.createElement("li");
    li.classList.toggle("actif", f.actif);

    const nom = document.createElement("span");
    nom.className = "nom";
    nom.textContent = f.nom.replace(".md", "");
    li.appendChild(nom);

    const meta = document.createElement("span");
    meta.className = "history-meta";
    meta.textContent = `${Math.max(1, Math.round(f.taille / 1024))} Ko`;
    li.appendChild(meta);

    if (f.actif) {
      const tag = document.createElement("span");
      tag.className = "tag-actif";
      tag.textContent = "en cours";
      li.appendChild(tag);
    }

    li.addEventListener("click", () => ouvrirTranscript(f.nom));
    listeTranscripts.appendChild(li);
  }
}

async function ouvrirTranscript(nom) {
  const t = await (await fetch(`${API}/transcripts/${encodeURIComponent(nom)}`)).json();
  transcriptOuvert = t.nom;
  majCibleAssistant(t.nom);
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
    if (transcriptAssistant) majCibleAssistant(rep.nom);
    document.getElementById("visionneuse-titre").textContent = rep.nom.replace(".md", "");
    rafraichirHistorique();
    rafraichirSession();
  } else {
    document.getElementById("visionneuse-etat").textContent = "⚠ Renommage impossible (nom déjà pris ?)";
  }
});

document.getElementById("visionneuse-supprimer").addEventListener("click", async () => {
  if (!confirm(`Supprimer définitivement « ${transcriptOuvert.replace(".md", "")} » ?`)) return;
  const r = await fetch(`${API}/transcripts/${encodeURIComponent(transcriptOuvert)}`, { method: "DELETE" });
  const rep = await r.json().catch(() => ({}));
  if (rep.etait_actif) {
    flux.innerHTML = "";       // c'était la session affichée en direct → on vide l'écran
    derniereSource = null;
  }
  if (transcriptAssistant === transcriptOuvert) majCibleAssistant(null);
  visionneuse.close();
  rafraichirHistorique();
  rafraichirSession();
});

document.getElementById("visionneuse-fermer").addEventListener("click", () => visionneuse.close());
rechercheTranscripts.addEventListener("input", renderHistorique);
setInterval(rafraichirHistorique, 10000);
setInterval(rafraichirSession, 5000);
rafraichirHistorique();
rafraichirSession();

// ---------------------------------------------------------------- assistant

const statutAssistant = document.getElementById("assistant-statut");
const assistantCible = document.getElementById("assistant-cible");
const btnAssistantSession = document.getElementById("btn-assistant-session");
const champQuestion = document.getElementById("champ-question");
const btnQuestion = document.getElementById("btn-question");
const btnsAssistant = [...document.querySelectorAll(".btn-assistant")];
let transcriptAssistant = null;

const TITRES_ACTIONS = {
  resume: "Résumé",
  points: "Points clés",
  actions: "Actions",
  compte_rendu: "Compte-rendu",
  famille: "Parent pressé",
  etudiant: "Fiche étudiant",
  doctorat: "Analyse doctorat",
  simplifier: "Version simplifiée",
  question: "Question",
};

function majCibleAssistant(nom = null) {
  transcriptAssistant = nom;
  if (nom) {
    assistantCible.textContent = `Analyse : ${nom.replace(".md", "")}`;
    btnAssistantSession.hidden = false;
  } else {
    assistantCible.textContent = "Analyse la session en cours";
    btnAssistantSession.hidden = true;
  }
}

function echapperHtml(texte) {
  return texte
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function nettoyerTexteAssistant(texte) {
  return texte
    .replace(/<think[\s\S]*?<\/think>/gi, "")
    .replace(/<\/?think[^>]*>/gi, "")
    .trim();
}

function formaterInline(texte) {
  return echapperHtml(texte).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function formaterReponseAssistant(texte) {
  const propre = nettoyerTexteAssistant(texte);
  if (!propre) return "";

  const lignes = propre.split(/\r?\n/);
  let html = "";
  let liste = null;

  const fermerListe = () => {
    if (liste) {
      html += `</${liste}>`;
      liste = null;
    }
  };

  for (const ligneBrute of lignes) {
    const ligne = ligneBrute.trim();
    if (!ligne) {
      fermerListe();
      continue;
    }

    const titre = ligne.match(/^#{1,3}\s+(.+)$/);
    if (titre) {
      fermerListe();
      html += `<h4>${formaterInline(titre[1])}</h4>`;
      continue;
    }

    const puce = ligne.match(/^[-*]\s+(.+)$/);
    if (puce) {
      if (liste !== "ul") {
        fermerListe();
        html += "<ul>";
        liste = "ul";
      }
      html += `<li>${formaterInline(puce[1])}</li>`;
      continue;
    }

    const numero = ligne.match(/^\d+\.\s+(.+)$/);
    if (numero) {
      if (liste !== "ol") {
        fermerListe();
        html += "<ol>";
        liste = "ol";
      }
      html += `<li>${formaterInline(numero[1])}</li>`;
      continue;
    }

    fermerListe();
    html += `<p>${formaterInline(ligne)}</p>`;
  }

  fermerListe();
  return html;
}

function afficherChargementAssistant(zone, sourcesSuspendues) {
  const detail = sourcesSuspendues.length
    ? "Écoute suspendue pendant l'analyse. Elle reprendra automatiquement."
    : "Je prépare une réponse finale, sans étapes de réflexion.";
  zone.innerHTML = `
    <div class="assistant-loader">
      <span class="assistant-spinner"></span>
      <div>
        <strong>Ollama réfléchit...</strong>
        <small>${detail}</small>
      </div>
    </div>`;
}

async function suspendreEcoutePourAssistant() {
  try {
    const statut = await (await fetch(`${API}/status`)).json();
    const sources = ["pc", "moi"].filter((source) => statut[source]);
    if (!sources.length) return [];
    assistantCible.textContent = "Analyse en cours - écoute suspendue";
    await Promise.all(sources.map((source) => fetch(`${API}/ecoute/${source}/stop`, { method: "POST" })));
    setTimeout(rafraichirStatut, 300);
    await new Promise((resolve) => setTimeout(resolve, 500));
    return sources;
  } catch {
    return [];
  }
}

async function reprendreEcouteApresAssistant(sources) {
  if (!sources.length) return;
  await Promise.all(sources.map((source) => fetch(`${API}/ecoute/${source}/start`, { method: "POST" }).catch(() => null)));
  setTimeout(rafraichirStatut, 500);
}

async function sourcesActives() {
  try {
    const statut = await (await fetch(`${API}/status`)).json();
    return ["pc", "moi"].filter((source) => statut[source]);
  } catch {
    return [];
  }
}

async function rafraichirAssistant() {
  try {
    const s = await (await fetch(`${API}/assistant/disponible`)).json();
    if (s.pret) {
      statutAssistant.textContent = `${s.modele} pret`;
      statutAssistant.classList.add("pret");
      majPill(statutOllama, "ok", "Ollama");
    } else {
      statutAssistant.textContent = s.ollama ? `${s.modele} indisponible` : "assistant hors ligne";
      statutAssistant.classList.remove("pret");
      majPill(statutOllama, s.ollama ? "warn" : "offline", "Ollama");
    }
  } catch {
    majPill(statutOllama, "offline", "Ollama");
  }
}
setInterval(rafraichirAssistant, 8000);
rafraichirAssistant();

function verrouillerAssistant(v) {
  btnsAssistant.forEach((b) => (b.disabled = v));
  btnQuestion.disabled = v;
  btnAssistantSession.disabled = v;
}

async function demanderAssistant(action, question = null) {
  assistantEnCours = true;
  verrouillerAssistant(true);
  const div = document.createElement("div");
  div.className = "ligne assistant";
  const heure = new Date().toLocaleTimeString("fr-FR");
  const titre = TITRES_ACTIONS[action] || "Assistant";
  div.innerHTML = `<div class="meta"><span class="badge assistant">ASSISTANT</span>${heure} · ${titre}</div><div class="texte assistant-output"></div>`;
  const doitSuivre = estPresDuBas();
  flux.appendChild(div);
  scrollSiBesoin(doitSuivre);
  derniereSource = "assistant";  // la prochaine transcription repartira dans une nouvelle bulle
  const zone = div.querySelector(".texte");
  const sourcesSuspendues = await suspendreEcoutePourAssistant();
  afficherChargementAssistant(zone, sourcesSuspendues);

  try {
    const r = await fetch(`${API}/assistant`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, question, nom: transcriptAssistant }),
    });
    if (!r.ok) {
      zone.textContent = `⚠ ${(await r.json()).detail || "erreur"}`;
      return;
    }
    let reponseComplete = "";
    const lecteur = r.body.getReader();
    const decodeur = new TextDecoder();
    while (true) {
      const { done, value } = await lecteur.read();
      if (done) break;
      reponseComplete += decodeur.decode(value, { stream: true });
      const html = formaterReponseAssistant(reponseComplete);
      const doitSuivreFlux = estPresDuBas();
      if (html) zone.innerHTML = html;
      scrollSiBesoin(doitSuivreFlux);
    }
    const htmlFinal = formaterReponseAssistant(reponseComplete);
    zone.innerHTML = htmlFinal || "<p>Je n'ai pas reçu de réponse finale exploitable.</p>";
  } catch (e) {
    zone.textContent = `⚠ ${e.message}`;
  } finally {
    await reprendreEcouteApresAssistant(sourcesSuspendues);
    majCibleAssistant(transcriptAssistant);
    assistantEnCours = false;
    verrouillerAssistant(false);
    rafraichirStatut();
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
btnAssistantSession.addEventListener("click", () => majCibleAssistant(null));
