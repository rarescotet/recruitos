const STORAGE_KEY = "recruitos-mvp-state";
const AUTH_STORAGE_KEY = "recruitos-auth-session";
const stages = [
  "Erstkontakt",
  "Datenerfassung",
  "Dokumentenupload",
  "Qualifizierung",
  "Recruiter Review",
  "Vermittlung",
];
const requiredDocuments = ["cv", "certificate", "id"];
const documentLabels = {
  cv: "Lebenslauf",
  certificate: "Zertifikate",
  id: "Ausweis",
};

const state = loadState();
let selectedCandidateId = state.candidates[0]?.id || null;
let currentUser = loadDemoSession();
const supabaseClient = createSupabaseClient();

const els = {
  authScreen: document.querySelector("#auth-screen"),
  appShell: document.querySelector("#app-shell"),
  loginForm: document.querySelector("#login-form"),
  signupForm: document.querySelector("#signup-form"),
  authTabs: document.querySelectorAll(".auth-tab"),
  authMessage: document.querySelector("#auth-message"),
  demoLogin: document.querySelector("#demo-login"),
  logoutButton: document.querySelector("#logout-button"),
  userChip: document.querySelector("#user-chip"),
  title: document.querySelector("#view-title"),
  navItems: document.querySelectorAll(".nav-item"),
  views: document.querySelectorAll(".view"),
  seedDemo: document.querySelector("#seed-demo"),
  candidateForm: document.querySelector("#candidate-form"),
  jobForm: document.querySelector("#job-form"),
  candidateList: document.querySelector("#candidate-list"),
  candidateProfile: document.querySelector("#candidate-profile"),
  jobList: document.querySelector("#job-list"),
  candidateHint: document.querySelector("#candidate-hint"),
  jobHint: document.querySelector("#job-hint"),
  pipelineBoard: document.querySelector("#pipeline-board"),
  botIntakeForm: document.querySelector("#bot-intake-form"),
  botResult: document.querySelector("#bot-result"),
  botScoreLabel: document.querySelector("#bot-score-label"),
  aiMode: document.querySelector("#ai-mode"),
  aiModel: document.querySelector("#ai-model"),
  aiActions: document.querySelector("#ai-actions"),
  aiTokens: document.querySelector("#ai-tokens"),
  aiUsageList: document.querySelector("#ai-usage-list"),
  topMatches: document.querySelector("#top-matches"),
  chatLog: document.querySelector("#chat-log"),
  chatForm: document.querySelector("#chat-form"),
  candidateCount: document.querySelector("#candidate-count"),
  jobCount: document.querySelector("#job-count"),
  matchCount: document.querySelector("#match-count"),
  avgScore: document.querySelector("#avg-score"),
};

els.authTabs.forEach((button) => {
  button.addEventListener("click", () => switchAuthMode(button.dataset.authMode));
});

els.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  await loginUser(form.get("email").trim(), form.get("password"));
});

els.signupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  await signupUser({
    fullName: form.get("fullName").trim(),
    organization: form.get("organization").trim(),
    email: form.get("email").trim(),
    password: form.get("password"),
  });
});

els.demoLogin.addEventListener("click", () => {
  currentUser = {
    id: "demo-user",
    email: "demo@recruitos.local",
    fullName: "Demo Recruiter",
    organization: "Demo Recruiting GmbH",
    role: "owner",
    provider: "demo",
  };
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(currentUser));
  showApp();
});

els.logoutButton.addEventListener("click", async () => {
  if (supabaseClient && currentUser?.provider === "supabase") {
    await supabaseClient.auth.signOut();
  }
  currentUser = null;
  localStorage.removeItem(AUTH_STORAGE_KEY);
  showAuth();
});

els.navItems.forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

els.seedDemo.addEventListener("click", () => {
  state.candidates = [
    {
      id: createId(),
      name: "Lea Wagner",
      role: "Sales Manager",
      location: "Hamburg",
      email: "lea.wagner@example.com",
      phone: "+49 170 4455667",
      experience: "6 Jahre B2B-Vertrieb, davon 3 Jahre SaaS",
      availability: "ab 01.08.2026",
      salary: "62.000 EUR brutto",
      documents: ["cv", "certificate", "id"],
      notes: "Starkes Kundenprofil, CRM-sicher, sehr gute Kommunikation.",
      skills: ["B2B", "CRM", "Vertrieb", "Deutsch"],
      status: "Qualifizierung",
    },
    {
      id: createId(),
      name: "Murat Kaya",
      role: "Pflegefachkraft",
      location: "Berlin",
      email: "murat.kaya@example.com",
      phone: "+49 176 7788990",
      experience: "8 Jahre stationaere Pflege und Dokumentation",
      availability: "sofort verfuegbar",
      salary: "3.800 EUR brutto",
      documents: ["cv", "certificate"],
      notes: "Ausweis fehlt noch. Sehr gutes Matching fuer Klinikbedarf.",
      skills: ["Pflege", "Schichtplanung", "Dokumentation", "Deutsch"],
      status: "Recruiter Review",
    },
    {
      id: createId(),
      name: "Nora Schmidt",
      role: "HR Generalist",
      location: "Muenchen",
      email: "nora.schmidt@example.com",
      phone: "+49 151 3344556",
      experience: "4 Jahre Recruiting, Active Sourcing und Onboarding",
      availability: "nach 4 Wochen Kuendigungsfrist",
      salary: "58.000 EUR brutto",
      documents: ["cv"],
      notes: "Bot soll Zertifikate und Arbeitszeugnisse nachfordern.",
      skills: ["Recruiting", "Active Sourcing", "Onboarding", "Englisch"],
      status: "Datenerfassung",
    },
  ];
  state.jobs = [
    {
      id: createId(),
      title: "Sales Manager B2B",
      client: "NovaCare GmbH",
      location: "Hamburg",
      requirements: ["B2B", "CRM", "Vertrieb"],
      priority: "Hoch",
    },
    {
      id: createId(),
      title: "Pflegefachkraft Station",
      client: "MediPlus Klinik",
      location: "Berlin",
      requirements: ["Pflege", "Dokumentation", "Deutsch"],
      priority: "Hoch",
    },
  ];
  selectedCandidateId = state.candidates[0]?.id || null;
  saveAndRender();
});

els.candidateForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  state.candidates.push({
    id: createId(),
    name: form.get("name").trim(),
    role: form.get("role").trim(),
    location: form.get("location").trim(),
    email: form.get("email").trim(),
    phone: form.get("phone").trim(),
    experience: form.get("experience").trim(),
    availability: form.get("availability").trim(),
    salary: form.get("salary").trim(),
    documents: splitTerms(form.get("documents")),
    notes: form.get("notes").trim(),
    skills: splitTerms(form.get("skills")),
    status: form.get("status"),
  });
  selectedCandidateId = state.candidates[state.candidates.length - 1].id;
  event.target.reset();
  saveAndRender();
});

els.jobForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  state.jobs.push({
    id: createId(),
    title: form.get("title").trim(),
    client: form.get("client").trim(),
    location: form.get("location").trim(),
    requirements: splitTerms(form.get("requirements")),
    priority: form.get("priority"),
  });
  event.target.reset();
  saveAndRender();
});

els.chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = new FormData(event.target).get("message").trim();
  addChat("user", message);
  addChat("assistant", generateAssistantReply(message));
  event.target.reset();
});

els.botIntakeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = {
    channel: form.get("channel"),
    name: form.get("name").trim(),
    phone: form.get("phone").trim(),
    role: form.get("role").trim(),
    location: form.get("location").trim(),
    contactStatus: form.get("contactStatus"),
    whatsappOptIn: form.get("whatsappOptIn") === "on",
    answers: form.get("answers").trim(),
    documents: splitTerms(form.get("documents")),
  };
  els.botScoreLabel.textContent = "KI analysiert...";
  els.botResult.className = "bot-result empty";
  els.botResult.textContent = "Der Bot prueft Antworten, Dokumente und Qualifikation.";
  const intake = await runBotIntake(payload);
  renderBotResult(intake);
});

function switchView(viewName) {
  els.navItems.forEach((item) => item.classList.toggle("active", item.dataset.view === viewName));
  els.views.forEach((view) => view.classList.toggle("active", view.id === `${viewName}-view`));
  els.title.textContent = {
    dashboard: "Dashboard",
    candidates: "Bewerber",
    jobs: "Stellen",
    pipeline: "Pipeline",
    bots: "KI-Bots",
    assistant: "KI-Assistent",
  }[viewName];
  if (viewName === "bots") refreshAiUsage();
}

async function initAuth() {
  if (supabaseClient) {
    const { data } = await supabaseClient.auth.getSession();
    if (data.session?.user) {
      currentUser = normalizeSupabaseUser(data.session.user);
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(currentUser));
    }
  }

  if (currentUser) {
    showApp();
  } else {
    showAuth();
  }
}

function switchAuthMode(mode) {
  els.authTabs.forEach((button) => button.classList.toggle("active", button.dataset.authMode === mode));
  els.loginForm.classList.toggle("hidden", mode !== "login");
  els.signupForm.classList.toggle("hidden", mode !== "signup");
  setAuthMessage("");
}

async function loginUser(email, password) {
  if (!supabaseClient) {
    setAuthMessage("Supabase ist noch nicht konfiguriert. Nutze vorerst den Demo-Login oder trage URL und anon key in supabase-config.js ein.", "warning");
    return;
  }

  setAuthMessage("Login wird geprueft...");
  const { data, error } = await supabaseClient.auth.signInWithPassword({ email, password });
  if (error) {
    setAuthMessage(error.message, "error");
    return;
  }
  currentUser = normalizeSupabaseUser(data.user);
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(currentUser));
  showApp();
}

async function signupUser({ fullName, organization, email, password }) {
  if (!supabaseClient) {
    setAuthMessage("Supabase ist noch nicht konfiguriert. Die Registrierungsmaske ist bereit, braucht aber URL und anon key.", "warning");
    return;
  }

  setAuthMessage("Account wird erstellt...");
  const { data, error } = await supabaseClient.auth.signUp({
    email,
    password,
    options: {
      data: {
        full_name: fullName,
        organization,
      },
    },
  });
  if (error) {
    setAuthMessage(error.message, "error");
    return;
  }
  if (!data.session) {
    setAuthMessage("Account erstellt. Bitte bestaetige deine E-Mail und logge dich danach ein.", "success");
    switchAuthMode("login");
    return;
  }
  currentUser = normalizeSupabaseUser(data.user);
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(currentUser));
  showApp();
}

function showApp() {
  els.authScreen.classList.add("hidden");
  els.appShell.classList.remove("hidden");
  els.userChip.textContent = `${currentUser.fullName || currentUser.email} - ${currentUser.organization || "Agentur"}`;
  refreshAiUsage();
}

function showAuth() {
  els.appShell.classList.add("hidden");
  els.authScreen.classList.remove("hidden");
  setAuthMessage(supabaseClient ? "" : "Demo-Modus aktiv: Fuer echtes Login URL und anon key in supabase-config.js eintragen.", "warning");
}

function setAuthMessage(message, type = "") {
  els.authMessage.textContent = message;
  els.authMessage.dataset.type = type;
}

function createSupabaseClient() {
  const config = window.RECRUITOS_SUPABASE || {};
  if (!config.url || !config.anonKey || !window.supabase?.createClient) return null;
  return window.supabase.createClient(config.url, config.anonKey);
}

function normalizeSupabaseUser(user) {
  return {
    id: user.id,
    email: user.email,
    fullName: user.user_metadata?.full_name || user.email,
    organization: user.user_metadata?.organization || "Agentur",
    role: "recruiter",
    provider: "supabase",
  };
}

function loadDemoSession() {
  const saved = localStorage.getItem(AUTH_STORAGE_KEY);
  return saved ? JSON.parse(saved) : null;
}

function render() {
  renderMetrics();
  renderCandidates();
  renderJobs();
  renderPipeline();
  renderTopMatches();
}

function renderMetrics() {
  const matches = buildMatches();
  els.candidateCount.textContent = state.candidates.length;
  els.jobCount.textContent = state.jobs.length;
  els.matchCount.textContent = matches.length;
  els.avgScore.textContent = matches.length
    ? `${Math.round(matches.reduce((sum, match) => sum + match.score, 0) / matches.length)}%`
    : "0%";
}

function renderCandidates() {
  els.candidateHint.textContent = `${state.candidates.length} Eintraege`;
  if (!selectedCandidateId || !state.candidates.some((candidate) => candidate.id === selectedCandidateId)) {
    selectedCandidateId = state.candidates[0]?.id || null;
  }
  els.candidateList.innerHTML = state.candidates.length
    ? state.candidates.map(candidateProfileCard).join("")
    : `<div class="empty">Noch keine Bewerber erfasst.</div>`;
  els.candidateList.querySelectorAll("[data-candidate-id]").forEach((button) => {
    button.addEventListener("click", () => {
      selectedCandidateId = button.dataset.candidateId;
      renderCandidates();
    });
  });
  renderCandidateProfile();
}

function renderJobs() {
  els.jobHint.textContent = `${state.jobs.length} Eintraege`;
  els.jobList.innerHTML = state.jobs.length
    ? state.jobs.map(jobCard).join("")
    : `<div class="empty">Noch keine Stellen erfasst.</div>`;
}

function renderPipeline() {
  els.pipelineBoard.innerHTML = stages
    .map((stage) => {
      const cards = state.candidates
        .filter((candidate) => candidate.status === stage)
        .map((candidate) => `
          <article class="pipeline-card">
            <strong>${escapeHtml(candidate.name)}</strong>
            <span>${escapeHtml(candidate.role)}</span>
            <button data-advance="${candidate.id}">Weiter</button>
          </article>
        `)
        .join("");
      return `
        <section class="pipeline-column">
          <h2>${stage}</h2>
          ${cards || `<div class="empty">Leer</div>`}
        </section>
      `;
    })
    .join("");

  els.pipelineBoard.querySelectorAll("[data-advance]").forEach((button) => {
    button.addEventListener("click", () => advanceCandidate(button.dataset.advance));
  });
}

function renderTopMatches() {
  const matches = buildMatches().slice(0, 5);
  els.topMatches.innerHTML = matches.length
    ? matches.map(matchCard).join("")
    : `<div class="empty">Lege Bewerber und Stellen an, um Matches zu sehen.</div>`;
}

function renderBotResult(intake) {
  els.botScoreLabel.textContent = `${intake.score}% qualifiziert${intake.aiEnabled ? " - KI aktiv" : " - Demo-Modus"}`;
  els.botResult.className = "bot-result";
  els.botResult.innerHTML = `
    <div class="qualification-score">
      <span>Qualifizierungs-Score</span>
      <strong>${intake.score}%</strong>
    </div>
    <div class="bot-summary">
      <strong>${escapeHtml(intake.name)}</strong>
      <span>${escapeHtml(intake.role)} - ${escapeHtml(intake.location)} - ${escapeHtml(intake.channel)} - ${escapeHtml(intake.phone || "keine Nummer")}</span>
    </div>
    ${intake.whatsappMessage ? `
      <div class="whatsapp-preview">
        <strong>WhatsApp Erstnachricht</strong>
        <p>${escapeHtml(intake.whatsappMessage)}</p>
        ${intake.phone ? `
          <div class="whatsapp-actions">
            <button class="secondary-action" id="send-whatsapp-from-bot" type="button">Per Twilio senden</button>
            <a href="${createWhatsAppLink(intake.phone, intake.whatsappMessage)}" target="_blank" rel="noreferrer">In WhatsApp oeffnen</a>
          </div>
        ` : ""}
      </div>
    ` : ""}
    <div class="tag-row">
      ${intake.skills.map((skill) => `<span class="tag">${escapeHtml(skill)}</span>`).join("")}
    </div>
    <div class="bot-checklist">
      ${intake.checklist.map((item) => `
        <div class="check-row ${item.done ? "done" : "missing"}">
          <span>${item.done ? "OK" : "Fehlt"}</span>
          <strong>${escapeHtml(item.label)}</strong>
        </div>
      `).join("")}
    </div>
    <div class="next-action">
      <strong>Naechste Aktion</strong>
      <p>${escapeHtml(intake.nextAction)}</p>
    </div>
    ${intake.warning ? `<div class="api-warning">${escapeHtml(safeWarning(intake.warning))}</div>` : ""}
    <button class="primary-action" id="create-candidate-from-bot" type="button">Ins Bewerber-CRM uebernehmen</button>
  `;

  document.querySelector("#create-candidate-from-bot").addEventListener("click", () => {
    state.candidates.push({
      id: createId(),
      name: intake.name,
      role: intake.role,
      location: intake.location,
      email: "",
      phone: intake.phone || "",
      experience: intake.experience || intake.answers || "",
      availability: intake.availability || extractAvailability(intake.answers || ""),
      salary: intake.salary || extractSalary(intake.answers || ""),
      documents: intake.documents,
      skills: intake.skills,
      status: intake.score >= 75 ? "Qualifizierung" : "Datenerfassung",
      notes: intake.summary,
    });
    selectedCandidateId = state.candidates[state.candidates.length - 1].id;
    saveAndRender();
    switchView("candidates");
  });

  const sendButton = document.querySelector("#send-whatsapp-from-bot");
  if (sendButton) {
    sendButton.addEventListener("click", async () => {
      sendButton.disabled = true;
      sendButton.textContent = "Sende...";
      const result = await sendWhatsAppMessage(intake.phone, intake.whatsappMessage);
      sendButton.textContent = result.sent ? "Gesendet" : "Senden fehlgeschlagen";
      if (!result.sent) {
        const warning = document.createElement("div");
        warning.className = "api-warning";
        warning.textContent = result.error || "WhatsApp konnte nicht gesendet werden.";
        els.botResult.insertBefore(warning, document.querySelector("#create-candidate-from-bot"));
        sendButton.disabled = false;
      }
    });
  }
}

async function runBotIntake(payload) {
  try {
    const response = await fetch("/api/bot-intake", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...payload,
        organizationId: getCurrentOrganizationId(),
        userId: currentUser?.id || "anonymous",
      }),
    });
    if (!response.ok) throw new Error(`API Status ${response.status}`);
    const result = await response.json();
    const intake = {
      ...payload,
      ...result,
      documents: Array.isArray(result.documents) ? result.documents : payload.documents,
      skills: Array.isArray(result.skills) ? result.skills : [],
      checklist: Array.isArray(result.checklist) ? result.checklist : [],
    };
    refreshAiUsage();
    return intake;
  } catch (error) {
    const fallback = evaluateBotIntake(payload);
    return {
      ...fallback,
      aiEnabled: false,
      warning: `Backend nicht erreichbar, lokale Demo-Auswertung genutzt: ${error.message}`,
    };
  }
}

async function sendWhatsAppMessage(to, message) {
  try {
    const response = await fetch("/api/whatsapp/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        to,
        message,
        organizationId: getCurrentOrganizationId(),
        userId: currentUser?.id || "anonymous",
      }),
    });
    const result = await response.json();
    if (!response.ok) return { sent: false, error: result.error || `API Status ${response.status}` };
    return result;
  } catch (error) {
    return {
      sent: false,
      error: `Backend nicht erreichbar: ${error.message}`,
    };
  }
}

async function refreshAiUsage() {
  await Promise.all([loadAiStatus(), loadAiUsage()]);
}

async function loadAiStatus() {
  try {
    const response = await fetch("/api/ai-status");
    const status = await response.json();
    els.aiMode.textContent = status.configured ? "Aktiv" : "Demo";
    els.aiModel.textContent = status.model || "-";
  } catch {
    els.aiMode.textContent = "Offline";
    els.aiModel.textContent = "-";
  }
}

async function loadAiUsage() {
  try {
    const response = await fetch("/api/ai-usage");
    const usage = await response.json();
    els.aiActions.textContent = usage.totalActions || 0;
    els.aiTokens.textContent = formatNumber(usage.totalTokens || 0);
    renderAiUsageList(usage.latest || []);
  } catch {
    els.aiActions.textContent = "0";
    els.aiTokens.textContent = "0";
    els.aiUsageList.className = "usage-list empty";
    els.aiUsageList.textContent = "KI-Nutzung konnte nicht geladen werden.";
  }
}

function renderAiUsageList(events) {
  if (!events.length) {
    els.aiUsageList.className = "usage-list empty";
    els.aiUsageList.textContent = "Noch keine KI-Nutzung erfasst.";
    return;
  }

  els.aiUsageList.className = "usage-list";
  els.aiUsageList.innerHTML = events.map((event) => `
    <article class="usage-event">
      <div>
        <strong>${escapeHtml(event.feature || "bot_intake")}</strong>
        <span>${escapeHtml(event.model || "-")} - ${event.aiEnabled ? "KI" : "Demo"}</span>
      </div>
      <div>
        <strong>${formatNumber(event.totalTokens || 0)}</strong>
        <span>Tokens</span>
      </div>
      <div>
        <strong>${event.score || 0}%</strong>
        <span>Score</span>
      </div>
    </article>
  `).join("");
}

function getCurrentOrganizationId() {
  return (currentUser?.organization || "demo-org").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function candidateCard(candidate) {
  return `
    <article class="entity-card">
      <strong>${escapeHtml(candidate.name)}</strong>
      <span>${escapeHtml(candidate.role)} · ${escapeHtml(candidate.location)} · ${escapeHtml(candidate.status)}</span>
      <div class="tag-row">${candidate.skills.map((skill) => `<span class="tag">${escapeHtml(skill)}</span>`).join("")}</div>
    </article>
  `;
}

function candidateProfileCard(candidate) {
  const profile = normalizeCandidate(candidate);
  const completeness = getProfileCompleteness(profile);
  return `
    <button class="candidate-card ${profile.id === selectedCandidateId ? "active" : ""}" data-candidate-id="${profile.id}" type="button">
      <span class="avatar">${escapeHtml(getInitials(profile.name))}</span>
      <span class="candidate-card-main">
        <strong>${escapeHtml(profile.name)}</strong>
        <span>${escapeHtml(profile.role)} - ${escapeHtml(profile.location)}</span>
        <span class="candidate-meta">${escapeHtml(profile.status)} - Profil ${completeness}%</span>
        <span class="mini-doc-row">${documentBadges(profile.documents).join("")}</span>
      </span>
    </button>
  `;
}

function renderCandidateProfile() {
  const candidate = state.candidates.find((item) => item.id === selectedCandidateId);
  if (!candidate) {
    els.candidateProfile.className = "candidate-profile empty";
    els.candidateProfile.textContent = "Waehle einen Bewerber aus.";
    return;
  }

  const profile = normalizeCandidate(candidate);
  const completeness = getProfileCompleteness(profile);
  els.candidateProfile.className = "candidate-profile";
  els.candidateProfile.innerHTML = `
    <div class="profile-hero">
      <div class="avatar large">${escapeHtml(getInitials(profile.name))}</div>
      <div>
        <strong>${escapeHtml(profile.name)}</strong>
        <span>${escapeHtml(profile.role)} - ${escapeHtml(profile.location)}</span>
      </div>
      <span class="status-pill">${escapeHtml(profile.status)}</span>
    </div>

    <div class="profile-completeness">
      <div>
        <span>Profilvollstaendigkeit</span>
        <strong>${completeness}%</strong>
      </div>
      <div class="progress-track"><span style="width: ${completeness}%"></span></div>
    </div>

    <div class="profile-section">
      <h3>Kontakt</h3>
      <div class="info-grid">
        ${infoItem("E-Mail", profile.email)}
        ${infoItem("Telefon", profile.phone)}
        ${infoItem("Verfuegbarkeit", profile.availability)}
        ${infoItem("Gehaltswunsch", profile.salary)}
      </div>
    </div>

    <div class="profile-section">
      <h3>Berufliches Profil</h3>
      <p>${escapeHtml(profile.experience || "Noch keine Erfahrung hinterlegt.")}</p>
      <div class="tag-row">${profile.skills.map((skill) => `<span class="tag">${escapeHtml(skill)}</span>`).join("")}</div>
    </div>

    <div class="profile-section">
      <h3>Dokumente</h3>
      <div class="document-grid">
        ${requiredDocuments.map((doc) => documentCard(doc, profile.documents.includes(doc))).join("")}
      </div>
    </div>

    <div class="profile-section">
      <h3>Notizen und Bot-Dokumentation</h3>
      <p>${escapeHtml(profile.notes || "Noch keine Notizen vorhanden.")}</p>
    </div>
  `;
}

function jobCard(job) {
  return `
    <article class="entity-card">
      <strong>${escapeHtml(job.title)}</strong>
      <span>${escapeHtml(job.client)} · ${escapeHtml(job.location)} · Prioritaet ${escapeHtml(job.priority)}</span>
      <div class="tag-row">${job.requirements.map((term) => `<span class="tag">${escapeHtml(term)}</span>`).join("")}</div>
    </article>
  `;
}

function matchCard(match) {
  return `
    <article class="match-card">
      <strong>${escapeHtml(match.candidate.name)} → ${escapeHtml(match.job.title)}</strong>
      <span>${escapeHtml(match.job.client)} · <span class="score">${match.score}% Match</span></span>
      <div class="tag-row">${match.shared.map((term) => `<span class="tag">${escapeHtml(term)}</span>`).join("")}</div>
    </article>
  `;
}

function buildMatches() {
  const matches = [];
  state.candidates.forEach((candidate) => {
    state.jobs.forEach((job) => {
      const candidateTerms = normalizeTerms([...candidate.skills, candidate.role, candidate.location]);
      const jobTerms = normalizeTerms([...job.requirements, job.title, job.location]);
      const shared = candidateTerms.filter((term) => jobTerms.includes(term));
      const score = Math.min(100, Math.round((shared.length / Math.max(jobTerms.length, 1)) * 100));
      if (score > 0) {
        matches.push({
          candidate,
          job,
          score,
          shared: shared.slice(0, 5),
        });
      }
    });
  });
  return matches.sort((a, b) => b.score - a.score);
}

function evaluateBotIntake(intake) {
  const answerTerms = splitTerms(intake.answers.replaceAll("\n", ","));
  const documents = intake.documents;
  const missingDocuments = requiredDocuments.filter((doc) => !documents.includes(doc));
  const hasAvailability = /verfuegbar|verf.gbar|sofort|kuendigung|k.ndigung|start/i.test(intake.answers);
  const hasExperience = /jahr|erfahrung|ausbildung|zertifikat|abschluss|projekt/i.test(intake.answers);
  const hasSalary = /gehalt|lohn|stunde|brutto|netto|euro|eur/i.test(intake.answers);
  const skills = normalizeExtractedSkills([intake.role, ...answerTerms]).slice(0, 6);

  let score = intake.phone ? 30 : 15;
  score += Math.min(documents.length * 12, 36);
  if (hasAvailability) score += 10;
  if (hasExperience) score += 12;
  if (hasSalary) score += 7;
  if (intake.whatsappOptIn) score += 5;
  score = Math.min(score, 100);

  const checklist = [
    { label: "Telefonnummer fuer WhatsApp erfasst", done: Boolean(intake.phone) },
    { label: "WhatsApp-Kontakt erlaubt", done: Boolean(intake.whatsappOptIn) },
    { label: "Kontaktdaten und Zielrolle erfasst", done: Boolean(intake.name && intake.role && intake.location) },
    { label: "Berufserfahrung erkennbar", done: hasExperience },
    { label: "Verfuegbarkeit geklaert", done: hasAvailability },
    { label: "Gehaltswunsch geklaert", done: hasSalary },
    ...requiredDocuments.map((doc) => ({
      label: documentLabels[doc],
      done: documents.includes(doc),
    })),
  ];

  const whatsappMessage = createWhatsAppMessage(intake);
  const nextAction = !intake.phone
    ? "Telefonnummer fehlt. Bot kann keinen WhatsApp-Erstkontakt starten."
    : !intake.whatsappOptIn
      ? "WhatsApp-Opt-in fehlt. Bitte Einwilligung klaeren oder alternativen Kanal nutzen."
      : !intake.answers
        ? "Bot sendet WhatsApp-Erstnachricht und wartet auf Antwort."
        : missingDocuments.length
    ? `Bot fordert noch ${missingDocuments.map((doc) => documentLabels[doc]).join(", ")} an und erinnert automatisch nach 24 Stunden.`
    : score >= 75
      ? "Bewerber ist vollstaendig genug fuer Recruiter Review und Matching."
      : "Bot stellt Rueckfragen zu Erfahrung, Verfuegbarkeit und Gehaltswunsch.";

  return {
    ...intake,
    score,
    skills,
    checklist,
    nextAction,
    whatsappMessage,
    summary: `Bot Intake: ${score}% qualifiziert. ${nextAction}`,
  };
}

function advanceCandidate(id) {
  const candidate = state.candidates.find((item) => item.id === id);
  const currentIndex = stages.indexOf(candidate.status);
  candidate.status = stages[Math.min(currentIndex + 1, stages.length - 1)];
  saveAndRender();
}

function generateAssistantReply(message) {
  const matches = buildMatches().slice(0, 3);
  if (!state.candidates.length || !state.jobs.length) {
    return "Ich brauche mindestens einen Bewerber und eine Stelle, dann kann ich Matching-Vorschlaege erstellen.";
  }
  if (/match|passt|kandidat|stelle|sales|pflege/i.test(message)) {
    return `Top-Vorschlag: ${matches[0].candidate.name} fuer ${matches[0].job.title} mit ${matches[0].score}% Score. Begruendung: gemeinsame Kriterien ${matches[0].shared.join(", ")}.`;
  }
  return `Aktuell sehe ich ${state.candidates.length} Bewerber, ${state.jobs.length} aktive Stellen und ${matches.length} potenzielle Matches. Als naechstes wuerde ich die Top-Kandidaten qualifizieren und Kundenupdates vorbereiten.`;
}

function addChat(type, text) {
  const bubble = document.createElement("div");
  bubble.className = `chat-message ${type}`;
  bubble.textContent = text;
  els.chatLog.appendChild(bubble);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

function splitTerms(value) {
  return value
    .split(",")
    .map((term) => term.trim())
    .filter(Boolean);
}

function normalizeExtractedSkills(values) {
  const blocked = ["ich", "und", "oder", "mit", "der", "die", "das", "eine", "ein"];
  return [...new Set(values
    .flatMap((value) => String(value).split(/[,\s]+/))
    .map((value) => value.trim())
    .filter((value) => value.length > 2)
    .filter((value) => !blocked.includes(value.toLowerCase())))]
    .map((value) => value.charAt(0).toUpperCase() + value.slice(1));
}

function normalizeCandidate(candidate) {
  return {
    id: candidate.id,
    name: candidate.name || "Unbekannter Bewerber",
    role: candidate.role || "Rolle offen",
    location: candidate.location || "Ort offen",
    email: candidate.email || "",
    phone: candidate.phone || "",
    experience: candidate.experience || "",
    availability: candidate.availability || "",
    salary: candidate.salary || "",
    documents: Array.isArray(candidate.documents) ? candidate.documents : [],
    notes: candidate.notes || "",
    skills: Array.isArray(candidate.skills) ? candidate.skills : [],
    status: candidate.status || "Erstkontakt",
  };
}

function getProfileCompleteness(candidate) {
  const checks = [
    candidate.name,
    candidate.role,
    candidate.location,
    candidate.email,
    candidate.phone,
    candidate.experience,
    candidate.availability,
    candidate.salary,
    candidate.skills.length,
    candidate.documents.includes("cv"),
    candidate.documents.includes("certificate"),
    candidate.documents.includes("id"),
    candidate.notes,
  ];
  const completed = checks.filter(Boolean).length;
  return Math.round((completed / checks.length) * 100);
}

function getInitials(name) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "B";
}

function documentBadges(documents) {
  return requiredDocuments.map((doc) => {
    const done = documents.includes(doc);
    return `<span class="doc-badge ${done ? "done" : "missing"}">${done ? "OK" : "Fehlt"} ${escapeHtml(documentLabels[doc])}</span>`;
  });
}

function documentCard(doc, done) {
  return `
    <article class="document-card ${done ? "done" : "missing"}">
      <strong>${escapeHtml(documentLabels[doc])}</strong>
      <span>${done ? "Vorhanden" : "Fehlt noch"}</span>
    </article>
  `;
}

function infoItem(label, value) {
  return `
    <div class="info-item">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value || "Nicht angegeben")}</strong>
    </div>
  `;
}

function extractAvailability(text) {
  const match = text.match(/(sofort|ab\s+\d{1,2}\.\d{1,2}\.\d{2,4}|verfuegbar|verf.gbar|kuendigung|k.ndigung)/i);
  return match ? match[0] : "";
}

function extractSalary(text) {
  const match = text.match(/(\d{2,3}[\.\s]?\d{3}|\d{3,5})\s*(eur|euro|brutto|netto)?/i);
  return match ? match[0] : "";
}

function formatNumber(value) {
  return new Intl.NumberFormat("de-DE").format(value);
}

function safeWarning(message) {
  if (/Incorrect API key|OpenAI API Fehler 401|API key/i.test(message)) {
    return "KI-Auswertung nicht verfuegbar: OpenAI API-Key ist ungueltig, widerrufen oder unvollstaendig kopiert.";
  }
  return message;
}

function createWhatsAppMessage(intake) {
  return `Hallo ${intake.name}, hier ist RecruitOS im Auftrag deiner Recruiting-Agentur. Du hast Interesse an der Rolle ${intake.role} in ${intake.location} angegeben. Kannst du mir kurz deine Erfahrung, Verfuegbarkeit, Gehaltswunsch und vorhandene Dokumente nennen?`;
}

function createWhatsAppLink(phone, message) {
  const cleanPhone = phone.replace(/[^\d+]/g, "").replace(/^\+/, "");
  return `https://wa.me/${cleanPhone}?text=${encodeURIComponent(message || "")}`;
}

function createId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function normalizeTerms(terms) {
  return terms.map((term) => term.toLowerCase().trim()).filter(Boolean);
}

function saveAndRender() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  render();
}

function loadState() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) return JSON.parse(saved);
  return { candidates: [], jobs: [] };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

addChat("assistant", "Hallo, ich bin dein Recruiting-Assistent. Lade Demo-Daten oder lege Bewerber und Stellen an, dann berechne ich Matches.");
initAuth();
render();
