const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");

const DEV_MOTEUR_DIR = path.join(__dirname, "..", "ecoute-pc");
const DEV_PYTHON = path.join(DEV_MOTEUR_DIR, ".venv", "Scripts", "python.exe");
const PACKAGED_MOTEUR = path.join(process.resourcesPath, "moteur", "ia-assistance-moteur.exe");

let fenetre = null;
let moteur = null;

function lancerMoteur() {
  const commande = app.isPackaged ? PACKAGED_MOTEUR : DEV_PYTHON;
  const args = app.isPackaged ? [] : ["serveur.py"];
  const cwd = app.isPackaged ? path.dirname(PACKAGED_MOTEUR) : DEV_MOTEUR_DIR;

  moteur = spawn(commande, args, { cwd });
  moteur.stdout.on("data", (d) => console.log(`[moteur] ${d}`));
  moteur.stderr.on("data", (d) => console.error(`[moteur] ${d}`));
  moteur.on("exit", (code) => console.log(`[moteur] arrete (code ${code})`));
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
