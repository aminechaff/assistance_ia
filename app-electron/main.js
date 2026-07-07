const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");

const MOTEUR_DIR = path.join(__dirname, "..", "ecoute-pc");
const PYTHON = path.join(MOTEUR_DIR, ".venv", "Scripts", "python.exe");

let fenetre = null;
let moteur = null;

function lancerMoteur() {
  moteur = spawn(PYTHON, ["serveur.py"], { cwd: MOTEUR_DIR });
  moteur.stdout.on("data", (d) => console.log(`[moteur] ${d}`));
  moteur.stderr.on("data", (d) => console.error(`[moteur] ${d}`));
  moteur.on("exit", (code) => console.log(`[moteur] arrêté (code ${code})`));
}

function creerFenetre() {
  fenetre = new BrowserWindow({
    width: 1050,
    height: 720,
    minWidth: 760,
    minHeight: 520,
    backgroundColor: "#12141a",
    title: "IA Assistance",
    autoHideMenuBar: true,
  });
  fenetre.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.whenReady().then(() => {
  lancerMoteur();
  creerFenetre();
});

app.on("window-all-closed", () => {
  if (moteur) moteur.kill();
  app.quit();
});
