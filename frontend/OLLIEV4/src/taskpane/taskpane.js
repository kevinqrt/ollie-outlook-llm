/* global Office */

let API_URL = localStorage.getItem("apiUrl") || "/api";
let sessionId = null;
let attachedFiles = [];

const chatArea      = document.getElementById("chatArea");
const chatInput     = document.getElementById("chatInput");
const sendBtn       = document.getElementById("sendBtn");
const testBtn       = document.getElementById("testBtn");
const loadBtn       = document.getElementById("loadSuggestions");
const chip1         = document.getElementById("chip1");
const chip2         = document.getElementById("chip2");
const chip3         = document.getElementById("chip3");
const welcomeName   = document.getElementById("welcomeName");
const settingsBtn   = document.getElementById("settingsBtn");
const settingsPanel = document.getElementById("settingsPanel");
const apiUrlInput   = document.getElementById("apiUrl");
const saveSettings  = document.getElementById("saveSettings");
const fileInput     = document.getElementById("fileInput");
const fileList      = document.getElementById("fileList");

apiUrlInput.value = API_URL;

Office.onReady(async () => {
  try {
    const name = Office.context.mailbox.userProfile.displayName.split(" ")[0];
    if (name) welcomeName.textContent = `Hallo ${name},`;
  } catch(e) {}
  // Session-Initialisierung deaktiviert, da Backend nur /email/suggestion unterstützt
  // await initSession();
});

function getMailContext() {
  return new Promise((resolve) => {
    try {
      const item = Office.context.mailbox.item;
      if (!item) throw new Error("Kein Mail-Item");
      item.body.getAsync(Office.CoercionType.Text, (result) => {
        const von = item.from ? `${item.from.displayName} <${item.from.emailAddress}>` : "unbekannt";
        const an  = item.to  ? item.to.map(r => r.emailAddress).join(", ") : "unbekannt";
        resolve({
          subject: item.subject || "(kein Betreff)",
          from: von,
          to: an,
          date: item.dateTimeCreated ? item.dateTimeCreated.toLocaleString("de-DE") : "",
          body: result.value ? result.value.substring(0, 3000) : "(kein Inhalt)"
        });
      });
    } catch(e) {
      resolve({
        subject: "Meeting morgen",
        from: "max.mustermann@hs-osnabrueck.de",
        to: "julian.kachur@hs-osnabrueck.de",
        date: new Date().toLocaleString("de-DE"),
        body: "Hallo, ich wollte fragen ob das Meeting morgen um 10 Uhr noch stattfindet. Bitte gib mir kurz Bescheid. Viele Grüße, Max"
      });
    }
  });
}

function readFileAsText(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target.result);
    reader.onerror = () => resolve("");
    reader.readAsText(file);
  });
}

async function initSession() {
  try {
    const mail = await getMailContext();
    let documents = `=== E-MAIL KONTEXT ===\nVon: ${mail.from}\nAn: ${mail.to}\nDatum: ${mail.date}\nBetreff: ${mail.subject}\n\nInhalt:\n${mail.body}`;

    for (const file of attachedFiles) {
      const content = await readFileAsText(file);
      if (content) {
        documents += `\n\n=== DATEI: ${file.name} ===\n${content.substring(0, 2000)}`;
      }
    }

    console.log("Verbinde zu Backend für Session:", `${API_URL}/sessions`);
    const response = await fetch(`${API_URL}/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ documents_text: documents })
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    sessionId = data.session_id;
    console.log("Session gestartet:", sessionId);
  } catch(e) {
    console.error("Initialisierung fehlgeschlagen:", e);
    addToCard("⚠️ Backend nicht bereit. Bitte prüfe, ob das Backend läuft und die URL in den Einstellungen stimmt.");
  }
}

async function askRAG(query) {
  if (!sessionId) {
    await initSession();
    if (!sessionId) throw new Error("Keine Session verfügbar.");
  }
  const response = await fetch(`${API_URL}/sessions/${encodeURIComponent(sessionId)}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query })
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();
  return data.answer || "Keine Antwort erhalten.";
}

function addToCard(text) {
  const div = document.createElement("div");
  div.className = "bot-msg";
  div.textContent = text;
  chatArea.appendChild(div);
  chatArea.scrollTop = chatArea.scrollHeight;
}

function addUserMsg(text) {
  const div = document.createElement("div");
  div.className = "user-msg";
  div.textContent = text;
  chatArea.appendChild(div);
  chatArea.scrollTop = chatArea.scrollHeight;
}

function showTyping() {
  const t = document.createElement("div");
  t.id = "typingIndicator";
  t.className = "typing-wrap";
  t.innerHTML = `<div class="typing"><span></span><span></span><span></span></div>`;
  chatArea.appendChild(t);
  chatArea.scrollTop = chatArea.scrollHeight;
}

function removeTyping() {
  const t = document.getElementById("typingIndicator");
  if (t) t.remove();
}

// ── Vorschläge ─────────────────────────────────────────────────
loadBtn.addEventListener("click", async () => {
  loadBtn.disabled = true;
  loadBtn.textContent = "⏳ Lade Vorschläge...";
  try {
    const result = await askRAG(
        "Erstelle genau 3 kurze Antwortvorschläge auf Deutsch für diese E-Mail. " +
        "Nummeriere sie mit 1. 2. 3. Keine weiteren Erklärungen."
    );
    const lines = result.split("\n")
        .filter(l => l.match(/^\d\./))
        .map(l => l.replace(/^\d\.\s*/, "").trim())
        .filter(l => l.length > 0);

    chip1.textContent = lines[0] || "Danke für Ihre Nachricht, ich kümmere mich darum.";
    chip2.textContent = lines[1] || "Ich melde mich so schnell wie möglich bei Ihnen.";
    chip3.textContent = lines[2] || "Könnten Sie mir weitere Details dazu schicken?";
    loadBtn.textContent = "🔄 Neue Vorschläge";
  } catch(e) {
    addToCard(`❌ Fehler: ${e.message}`);
    loadBtn.textContent = "✨ Vorschläge generieren";
  }
  loadBtn.disabled = false;
});

function handleChipClick(text) {
  addUserMsg(text);
  try {
    Office.context.mailbox.item.displayReplyForm(text);
  } catch(e) {}
}

chip1.addEventListener("click", () => handleChipClick(chip1.textContent));
chip2.addEventListener("click", () => handleChipClick(chip2.textContent));
chip3.addEventListener("click", () => handleChipClick(chip3.textContent));

testBtn.addEventListener("click", async () => {
  addToCard("⏳ Analysiere E-Mail...");
  showTyping();
  try {
    const mail = await getMailContext();
    const fullContent = `Betreff: ${mail.subject}\n\nInhalt:\n${mail.body}`;

    const response = await fetch(`${API_URL}/email/suggestion`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email_content: fullContent })
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

    removeTyping();
    addToCard("Hier ist ein Test-Antwortvorschlag basierend auf deiner Mail:");
    addToCard(data.suggested_reply);
  } catch (e) {
    removeTyping();
    addToCard(`❌ Fehler: ${e.message}`);
    console.error("Test-Button Fehler:", e);
  }
});

// ── Chat ───────────────────────────────────────────────────────
async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = "";
  addUserMsg(text);
  showTyping();
  sendBtn.disabled = true;
  try {
    const reply = await askRAG(text);
    removeTyping();
    addToCard(reply);
  } catch(e) {
    removeTyping();
    addToCard(`❌ Fehler: ${e.message}`);
  }
  sendBtn.disabled = false;
  chatInput.focus();
}

sendBtn.addEventListener("click", sendMessage);
chatInput.addEventListener("keydown", e => { if (e.key === "Enter") sendMessage(); });

// ── Datei anhängen ─────────────────────────────────────────────
fileInput.addEventListener("change", async () => {
  for (const file of fileInput.files) {
    if (!attachedFiles.find(f => f.name === file.name)) {
      attachedFiles.push(file);
      addFileTag(file);
    }
  }
  fileInput.value = "";
  sessionId = null;
  await initSession();
});

function addFileTag(file) {
  const tag = document.createElement("div");
  tag.className = "file-tag";
  tag.id = `tag-${file.name}`;
  tag.innerHTML = `📄 ${file.name} `;
  
  const btn = document.createElement("button");
  btn.textContent = "×";
  btn.addEventListener("click", () => removeFile(file.name));
  tag.appendChild(btn);
  
  fileList.appendChild(tag);
}

function removeFile(name) {
  attachedFiles = attachedFiles.filter(f => f.name !== name);
  const tag = document.getElementById(`tag-${name}`);
  if (tag) tag.remove();
  sessionId = null;
  initSession();
}

// ── Einstellungen ──────────────────────────────────────────────
settingsBtn.addEventListener("click", () => {
  settingsPanel.style.display = settingsPanel.style.display === "none" ? "flex" : "none";
});

saveSettings.addEventListener("click", async () => {
  API_URL = apiUrlInput.value.trim();
  localStorage.setItem("apiUrl", API_URL);
  settingsPanel.style.display = "none";
  sessionId = null;
  await initSession();
  addToCard(`✅ Verbunden mit: ${API_URL}`);
});
