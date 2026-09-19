/**
 * Universal Agentic Platform - Frontend Logic
 * Claude Desktop Aesthetic with Dynamic API Management & Artifacts Drawer
 */

document.addEventListener("DOMContentLoaded", () => {
  // -------------------------------------------------------------------------
  // State
  // -------------------------------------------------------------------------
  let activeAgentId = "chief-architect";
  let agentsList = [];
  let conversationHistory = [];
  let currentArtifacts = [];
  let isGenerating = false;

  // -------------------------------------------------------------------------
  // DOM Elements
  // -------------------------------------------------------------------------
  const sidebar = document.getElementById("sidebar");
  const btnToggleSidebar = document.getElementById("btnToggleSidebar");
  const agentListContainer = document.getElementById("agentList");
  const headerAgentAvatar = document.getElementById("headerAgentAvatar");
  const headerAgentName = document.getElementById("headerAgentName");
  const headerAgentRole = document.getElementById("headerAgentRole");
  const primaryProviderName = document.getElementById("primaryProviderName");
  const fallbackProviderName = document.getElementById("fallbackProviderName");
  const activeModelLabel = document.getElementById("activeModelLabel");

  const chatMessages = document.getElementById("chatMessages");
  const welcomeHero = document.getElementById("welcomeHero");
  const chatInput = document.getElementById("chatInput");
  const btnSend = document.getElementById("btnSend");
  const btnNewChat = document.getElementById("btnNewChat");
  const btnClearChat = document.getElementById("btnClearChat");

  const failoverBanner = document.getElementById("failoverBanner");
  const failoverText = document.getElementById("failoverText");
  const btnDismissFailover = document.getElementById("btnDismissFailover");

  const artifactsDrawer = document.getElementById("artifactsDrawer");
  const btnToggleArtifacts = document.getElementById("btnToggleArtifacts");
  const btnCloseArtifacts = document.getElementById("btnCloseArtifacts");
  const artifactCountBadge = document.getElementById("artifactCountBadge");
  const artifactCodeBlock = document.getElementById("artifactCodeBlock");
  const artifactPreviewContainer = document.getElementById("artifactPreviewContainer");
  const btnCopyArtifact = document.getElementById("btnCopyArtifact");

  // Modal Elements
  const btnOpenApiModal = document.getElementById("btnOpenApiModal");
  const apiModalBackdrop = document.getElementById("apiModalBackdrop");
  const btnCloseApiModal = document.getElementById("btnCloseApiModal");
  const providersTableBody = document.getElementById("providersTableBody");
  const addProviderForm = document.getElementById("addProviderForm");

  // -------------------------------------------------------------------------
  // Initialization
  // -------------------------------------------------------------------------
  init();

  async function init() {
    await loadAgents();
    await loadProvidersAndHealth();
    setupEventListeners();
  }

  // -------------------------------------------------------------------------
  // Event Listeners
  // -------------------------------------------------------------------------
  function setupEventListeners() {
    // Sidebar toggle
    btnToggleSidebar.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
    });

    // Artifacts Drawer
    btnToggleArtifacts.addEventListener("click", () => {
      artifactsDrawer.classList.toggle("collapsed");
    });
    btnCloseArtifacts.addEventListener("click", () => {
      artifactsDrawer.classList.add("collapsed");
    });

    // Copy Artifact
    btnCopyArtifact.addEventListener("click", () => {
      if (currentArtifacts.length > 0) {
        navigator.clipboard.writeText(currentArtifacts[0].code);
        btnCopyArtifact.textContent = "Copied!";
        setTimeout(() => (btnCopyArtifact.textContent = "Copy"), 2000);
      }
    });

    // Tab buttons in Artifacts
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        document.querySelectorAll(".artifact-tab-content").forEach((c) => c.classList.remove("active"));
        btn.classList.add("active");
        const tab = btn.getAttribute("data-tab");
        if (tab === "code") {
          document.getElementById("artifactCodeTab").classList.add("active");
        } else {
          document.getElementById("artifactPreviewTab").classList.add("active");
        }
      });
    });

    // Modal open/close
    btnOpenApiModal.addEventListener("click", () => {
      loadProvidersTable();
      apiModalBackdrop.classList.add("open");
    });
    btnCloseApiModal.addEventListener("click", () => {
      apiModalBackdrop.classList.remove("open");
    });
    apiModalBackdrop.addEventListener("click", (e) => {
      if (e.target === apiModalBackdrop) apiModalBackdrop.classList.remove("open");
    });

    // Insert Provider Form
    addProviderForm.addEventListener("submit", handleAddProvider);

    // Failover banner dismiss
    btnDismissFailover.addEventListener("click", () => {
      failoverBanner.style.display = "none";
    });

    // Chat sending
    btnSend.addEventListener("click", handleSendMessage);
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    });

    // Auto-resize input
    chatInput.addEventListener("input", () => {
      chatInput.style.height = "auto";
      chatInput.style.height = Math.min(chatInput.scrollHeight, 180) + "px";
    });

    // Clear & New Chat
    btnClearChat.addEventListener("click", resetChat);
    btnNewChat.addEventListener("click", resetChat);

    // Starter cards
    document.querySelectorAll(".starter-card").forEach((card) => {
      card.addEventListener("click", () => {
        const prompt = card.getAttribute("data-prompt");
        chatInput.value = prompt;
        handleSendMessage();
      });
    });
  }

  // -------------------------------------------------------------------------
  // Agents & Personas
  // -------------------------------------------------------------------------
  async function loadAgents() {
    try {
      const res = await fetch("/api/agents");
      agentsList = await res.json();
      renderAgentList();
    } catch (err) {
      console.error("Failed to load agents:", err);
    }
  }

  function renderAgentList() {
    agentListContainer.innerHTML = "";
    agentsList.forEach((agent) => {
      const div = document.createElement("div");
      div.className = `agent-item ${agent.id === activeAgentId ? "active" : ""}`;
      div.innerHTML = `
        <span class="agent-item-avatar">${agent.avatar}</span>
        <span>${agent.name}</span>
      `;
      div.addEventListener("click", () => selectAgent(agent.id));
      agentListContainer.appendChild(div);
    });
    updateHeaderAgent();
  }

  function selectAgent(agentId) {
    activeAgentId = agentId;
    renderAgentList();
    updateHeaderAgent();
  }

  function updateHeaderAgent() {
    const current = agentsList.find((a) => a.id === activeAgentId);
    if (current) {
      headerAgentAvatar.textContent = current.avatar;
      headerAgentName.textContent = current.name;
      headerAgentRole.textContent = current.role;
    }
  }

  // -------------------------------------------------------------------------
  // Providers & Health
  // -------------------------------------------------------------------------
  async function loadProvidersAndHealth() {
    try {
      const res = await fetch("/api/health");
      const health = await res.json();
      const providers = health.providers || [];

      if (providers.length > 0) {
        primaryProviderName.textContent = `${providers[0].name} (${providers[0].model})`;
        activeModelLabel.textContent = providers[0].model;
      } else {
        primaryProviderName.textContent = "No provider active";
      }

      if (providers.length > 1) {
        fallbackProviderName.textContent = `${providers[1].name} (${providers[1].model})`;
      } else {
        fallbackProviderName.textContent = "No secondary fallback";
      }
    } catch (err) {
      console.error("Failed to load health status:", err);
    }
  }

  async function loadProvidersTable() {
    try {
      const res = await fetch("/api/providers");
      const providers = await res.json();
      providersTableBody.innerHTML = "";

      if (providers.length === 0) {
        providersTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #888;">No providers configured yet.</td></tr>`;
        return;
      }

      providers.forEach((p) => {
        const tr = document.createElement("tr");
        const keysText = p.api_keys_masked ? p.api_keys_masked.join(", ") : "None";
        tr.innerHTML = `
          <td><span class="badge-priority">P${p.priority}</span></td>
          <td><strong>${p.name}</strong></td>
          <td>${p.provider_type}</td>
          <td><code>${p.model}</code></td>
          <td><small>${keysText}</small></td>
          <td><span class="badge-status-on">${p.enabled ? "Active" : "Disabled"}</span></td>
          <td>
            <button class="btn-delete-provider" data-name="${p.name}">Delete</button>
          </td>
        `;
        tr.querySelector(".btn-delete-provider").addEventListener("click", () => handleDeleteProvider(p.name));
        providersTableBody.appendChild(tr);
      });
    } catch (err) {
      console.error("Failed to load providers table:", err);
    }
  }

  // -------------------------------------------------------------------------
  // Insert & Delete Provider
  // -------------------------------------------------------------------------
  async function handleAddProvider(e) {
    e.preventDefault();
    const type = document.getElementById("newProviderType").value;
    const name = document.getElementById("newProviderName").value.trim();
    const model = document.getElementById("newProviderModel").value.trim();
    const keysRaw = document.getElementById("newProviderKeys").value.trim();
    const priority = parseInt(document.getElementById("newProviderPriority").value, 10);
    const baseUrl = document.getElementById("newProviderBaseUrl").value.trim();

    const keys = keysRaw.split(",").map((k) => k.trim()).filter((k) => k);

    const payload = {
      name,
      provider_type: type,
      model,
      api_keys: keys,
      priority,
      base_url: baseUrl || null,
      enabled: true,
    };

    try {
      const res = await fetch("/api/providers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        alert(`Failed to add provider: ${err.detail || "Error"}`);
        return;
      }

      // Reset form & reload
      addProviderForm.reset();
      await loadProvidersTable();
      await loadProvidersAndHealth();
    } catch (err) {
      alert(`Network error: ${err}`);
    }
  }

  async function handleDeleteProvider(name) {
    if (!confirm(`Are you sure you want to delete provider '${name}'?`)) return;

    try {
      const res = await fetch(`/api/providers/${encodeURIComponent(name)}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const err = await res.json();
        alert(`Failed to delete provider: ${err.detail || "Error"}`);
        return;
      }

      await loadProvidersTable();
      await loadProvidersAndHealth();
    } catch (err) {
      alert(`Delete error: ${err}`);
    }
  }

  // -------------------------------------------------------------------------
  // Chat Execution
  // -------------------------------------------------------------------------
  async function handleSendMessage() {
    const text = chatInput.value.trim();
    if (!text || isGenerating) return;

    // Hide welcome hero
    welcomeHero.style.display = "none";

    // Append user message
    appendMessage("user", text);
    conversationHistory.push({ role: "user", content: text });
    chatInput.value = "";
    chatInput.style.height = "auto";

    // Show assistant placeholder
    isGenerating = true;
    const assistantBubble = appendLoadingBubble();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: conversationHistory,
          agent_id: activeAgentId,
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to generate response");
      }

      const data = await res.json();

      // Check for failover events
      if (data.failover_events && data.failover_events.length > 0) {
        const ev = data.failover_events[0];
        failoverText.textContent = `AUTOMATIC FAILOVER: Shifted from '${ev.from_provider}' to '${ev.to_provider}' (${ev.reason})`;
        failoverBanner.style.display = "flex";
      }

      // Update Assistant Bubble
      updateAssistantBubble(assistantBubble, data);
      conversationHistory.push({ role: "assistant", content: data.content });

      // Check for code artifacts
      extractArtifacts(data.content);
    } catch (err) {
      assistantBubble.innerHTML = `<div class="message-content" style="color: #ef4444;">Error: ${err.message}</div>`;
    } finally {
      isGenerating = false;
      scrollToBottom();
    }
  }

  function appendMessage(role, content) {
    const bubble = document.createElement("div");
    bubble.className = `message-bubble ${role}`;
    bubble.innerHTML = `<div class="message-content">${escapeHtml(content)}</div>`;
    chatMessages.appendChild(bubble);
    scrollToBottom();
    return bubble;
  }

  function appendLoadingBubble() {
    const bubble = document.createElement("div");
    bubble.className = "message-bubble assistant";
    bubble.innerHTML = `
      <div class="message-header">
        <span class="message-author">${headerAgentName.textContent}</span>
        <span class="message-provider-tag">Routing...</span>
      </div>
      <div class="message-content">Thinking...</div>
    `;
    chatMessages.appendChild(bubble);
    scrollToBottom();
    return bubble;
  }

  function updateAssistantBubble(bubble, data) {
    const parsedHtml = marked.parse(data.content);
    bubble.innerHTML = `
      <div class="message-header">
        <span class="message-author">${data.agent ? data.agent.name : headerAgentName.textContent}</span>
        <span class="message-provider-tag">${data.provider_name} • ${data.model}</span>
      </div>
      <div class="message-content">${parsedHtml}</div>
    `;

    // Highlight code blocks
    bubble.querySelectorAll("pre code").forEach((block) => {
      hljs.highlightElement(block);
    });
  }

  function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function resetChat() {
    conversationHistory = [];
    currentArtifacts = [];
    chatMessages.innerHTML = "";
    welcomeHero.style.display = "flex";
    chatMessages.appendChild(welcomeHero);
    artifactCountBadge.textContent = "0";
    failoverBanner.style.display = "none";
  }

  // -------------------------------------------------------------------------
  // Artifacts Extraction & Preview
  // -------------------------------------------------------------------------
  function extractArtifacts(content) {
    const codeBlockRegex = /```([a-zA-Z0-9_\-]+)?\n([\s\S]*?)```/g;
    let match;
    let foundArtifacts = [];

    while ((match = codeBlockRegex.exec(content)) !== null) {
      foundArtifacts.push({
        lang: match[1] || "plaintext",
        code: match[2],
      });
    }

    if (foundArtifacts.length > 0) {
      currentArtifacts = foundArtifacts;
      artifactCountBadge.textContent = currentArtifacts.length;

      // Populate first artifact in drawer
      const primary = currentArtifacts[0];
      artifactCodeBlock.textContent = primary.code;
      artifactCodeBlock.className = `hljs language-${primary.lang}`;
      hljs.highlightElement(artifactCodeBlock);

      // Populate preview tab
      if (primary.lang === "html" || primary.lang === "svg") {
        artifactPreviewContainer.innerHTML = primary.code;
      } else {
        artifactPreviewContainer.innerHTML = `<pre style="font-family: monospace; padding: 10px; color: #ddd;">${escapeHtml(primary.code)}</pre>`;
      }

      // Automatically slide open the artifacts drawer on code generation
      artifactsDrawer.classList.remove("collapsed");
    }
  }

  function escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
