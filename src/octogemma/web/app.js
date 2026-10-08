/**
 * OctoGemma Studio — Frontend Controller
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const ollamaStatusInd = document.getElementById("ollama-status-indicator");
  const ollamaStatusText = document.getElementById("ollama-status-text");
  const modelSelector = document.getElementById("model-selector");
  const pullModelBtn = document.getElementById("pull-model-btn") || document.getElementById("add-model-btn");
  const addModelBtn = document.getElementById("add-model-btn");
  const refreshModelsBtn = document.getElementById("refresh-models-btn");
  const workspacePathText = document.getElementById("workspace-path-text");
  const taskInput = document.getElementById("task-input");
  const runAgentBtn = document.getElementById("run-agent-btn");
  const stopAgentBtn = document.getElementById("stop-agent-btn");
  const stepCounterBadge = document.getElementById("step-counter-badge");
  const fileTree = document.getElementById("file-tree");
  const refreshFilesBtn = document.getElementById("refresh-files-btn");
  const timelineFeed = document.getElementById("timeline-feed");
  const timelineDot = document.getElementById("timeline-dot");
  const agentStateLabel = document.getElementById("agent-state-label");
  const clearTimelineBtn = document.getElementById("clear-timeline-btn");
  
  // Right Pane Elements
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");
  const diffFileTitle = document.getElementById("diff-file-title");
  const diffCodeContent = document.getElementById("diff-code-content");
  const terminalContent = document.getElementById("terminal-content");
  const previewFileTitle = document.getElementById("preview-file-title");
  const fileCodeContent = document.getElementById("file-code-content");
  const refreshDiffBtn = document.getElementById("refresh-diff-btn");

  // Local LLM Manager Modal Elements
  const addModelModal = document.getElementById("add-model-modal");
  const pullModal = addModelModal; // alias for compatibility
  const closeAddModelModalBtn = document.getElementById("close-add-model-modal-btn");
  const closeModalFooterBtn = document.getElementById("close-modal-footer-btn");
  const customModelTagInput = document.getElementById("custom-model-tag-input");
  const addTagBtn = document.getElementById("add-tag-btn");
  const installedModelsList = document.getElementById("installed-models-list");
  const addTagStatus = document.getElementById("add-tag-status");

  const pullModelNameInput = document.getElementById("pull-model-name-input");
  const startPullBtn = document.getElementById("start-pull-btn");
  const pullProgressContainer = document.getElementById("pull-progress-container");
  const pullProgressFill = document.getElementById("pull-progress-fill");
  const pullStatusText = document.getElementById("pull-status-text");

  const ggufModelNameInput = document.getElementById("gguf-model-name-input");
  const ggufFilePathInput = document.getElementById("gguf-file-path-input");
  const startGgufImportBtn = document.getElementById("start-gguf-import-btn");
  const ggufProgressContainer = document.getElementById("gguf-progress-container");
  const ggufProgressFill = document.getElementById("gguf-progress-fill");
  const ggufStatusText = document.getElementById("gguf-status-text");
  const ggufStatusMsg = document.getElementById("gguf-status-msg");

  const endpointUrlInput = document.getElementById("endpoint-url-input");
  const saveEndpointBtn = document.getElementById("save-endpoint-btn");
  const endpointStatusMsg = document.getElementById("endpoint-status-msg");

  // Workspace Switcher Modal
  const workspaceBadge = document.getElementById("workspace-badge");
  const workspaceModal = document.getElementById("workspace-modal");
  const closeWorkspaceModalBtn = document.getElementById("close-workspace-modal-btn");
  const cancelWorkspaceBtn = document.getElementById("cancel-workspace-btn");
  const saveWorkspaceBtn = document.getElementById("save-workspace-btn");
  const workspacePathInput = document.getElementById("workspace-path-input");
  const workspaceModalStatus = document.getElementById("workspace-modal-status");

  let activeEventSource = null;
  let isRunning = false;
  let healthFailCount = 0;
  const HEALTH_FAIL_THRESHOLD = 3; // Only show disconnected after 3 consecutive failures
  let healthPollTimer = null;

  // Initialize System
  async function init() {
    await checkHealth();
    await loadModels();
    await loadFiles();
    setupEventListeners();
    // Start gentle background heartbeat — poll every 15 seconds
    healthPollTimer = setInterval(checkHealth, 15000);
  }

  // Check Ollama Health — resilient with consecutive-failure threshold
  async function checkHealth() {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      const res = await fetch("/api/health", { signal: controller.signal });
      clearTimeout(timeout);
      const data = await res.json();

      if (data.ollama_connected) {
        // Reset fail counter on success
        const wasDisconnected = healthFailCount >= HEALTH_FAIL_THRESHOLD;
        healthFailCount = 0;
        ollamaStatusText.textContent = "Ollama Active";
        ollamaStatusInd.style.color = "var(--accent-emerald, #10b981)";
        ollamaStatusInd.style.borderColor = "rgba(16, 185, 129, 0.4)";
        workspacePathText.textContent = data.workspace.split(/[\\/]/).pop() || data.workspace;
        workspacePathText.dataset.fullPath = data.workspace;
        workspaceBadge.title = `Active: ${data.workspace} (Click to change)`;
        // If we just recovered, silently refresh models list
        if (wasDisconnected) {
          await loadModels();
        }
      } else {
        healthFailCount++;
        if (healthFailCount >= HEALTH_FAIL_THRESHOLD) {
          ollamaStatusText.textContent = "Ollama Disconnected";
          ollamaStatusInd.style.color = "var(--accent-rose, #f43f5e)";
          ollamaStatusInd.style.borderColor = "rgba(244, 63, 94, 0.4)";
        } else {
          // Brief blip — keep showing active, just log it
          console.log(`Health check: Ollama not connected (attempt ${healthFailCount}/${HEALTH_FAIL_THRESHOLD})`);
        }
      }
    } catch (err) {
      healthFailCount++;
      if (healthFailCount >= HEALTH_FAIL_THRESHOLD) {
        ollamaStatusText.textContent = "Backend Offline";
        ollamaStatusInd.style.color = "var(--accent-rose, #f43f5e)";
        ollamaStatusInd.style.borderColor = "rgba(244, 63, 94, 0.4)";
      } else {
        console.log(`Health check: fetch error (attempt ${healthFailCount}/${HEALTH_FAIL_THRESHOLD}): ${err.message}`);
      }
    }
  }

  // Load Models
  async function loadModels() {
    try {
      const res = await fetch("/api/models");
      const data = await res.json();
      const currentSelected = modelSelector.value;

      if (data.endpoint && endpointUrlInput) {
        endpointUrlInput.value = data.endpoint;
      }

      modelSelector.innerHTML = "";
      if (data.models && data.models.length > 0) {
        data.models.forEach(m => {
          const opt = document.createElement("option");
          opt.value = m.name;
          const isGemma = m.name.includes("gemma");
          const isCustom = m.is_custom;
          opt.textContent = `${m.name} ${isGemma ? '★ Recommended' : (isCustom ? '⚙ Custom' : '')}`;
          if (m.name === currentSelected || (!currentSelected && m.name === data.preferred)) {
            opt.selected = true;
          }
          modelSelector.appendChild(opt);
        });

        // Add gemma4 option if not yet downloaded
        const hasGemma4 = data.models.some(m => m.name.includes("gemma4"));
        if (!hasGemma4) {
          const gemmaOpt = document.createElement("option");
          gemmaOpt.value = "gemma4:e4b";
          gemmaOpt.textContent = "gemma4:e4b (Available to Pull)";
          modelSelector.appendChild(gemmaOpt);
        }
      }

      // Add Manage / Add New option at bottom
      const manageOpt = document.createElement("option");
      manageOpt.value = "__manage__";
      manageOpt.textContent = "+ Add / Manage Local LLMs...";
      modelSelector.appendChild(manageOpt);

      // Render Installed Models in Modal Tab 1
      renderInstalledModels(data.models || [], currentSelected || data.preferred);
    } catch (err) {
      console.error("Failed to load models:", err);
    }
  }

  // Render Installed Models in Modal List
  function renderInstalledModels(models, activeModel) {
    if (!installedModelsList) return;
    if (!models || models.length === 0) {
      installedModelsList.innerHTML = '<div class="empty-state-text" style="color: var(--text-dim); padding: 8px;">No local models detected. Use the tabs above to add or pull one.</div>';
      return;
    }

    installedModelsList.innerHTML = "";
    models.forEach(m => {
      const item = document.createElement("div");
      item.className = "installed-model-item";

      const sizeStr = m.size ? `• ${formatBytes(m.size)}` : "";
      const isCustom = m.is_custom;
      const isCurrent = m.name === (modelSelector.value || activeModel);

      item.innerHTML = `
        <div class="model-info">
          <span class="model-name">${escapeHtml(m.name)}</span>
          <span class="model-size">${sizeStr}</span>
          <span class="tag-badge ${isCustom ? 'custom' : ''}">${isCustom ? 'Custom' : 'Ollama'}</span>
          ${isCurrent ? '<span class="tag-badge" style="background: rgba(56, 189, 248, 0.2); color: #38bdf8;">Active</span>' : ''}
        </div>
        <div class="model-actions">
          <button class="btn btn-secondary select-model-btn" style="padding: 3px 8px; font-size: 0.72rem;" data-name="${escapeHtml(m.name)}">
            ${isCurrent ? 'Selected' : 'Use'}
          </button>
          ${isCustom ? `<button class="icon-btn delete-custom-btn" style="color: var(--accent-rose); font-size: 0.85rem;" title="Remove Custom Model" data-name="${escapeHtml(m.name)}">&times;</button>` : ''}
        </div>
      `;

      item.querySelector(".select-model-btn").addEventListener("click", () => {
        modelSelector.value = m.name;
        renderInstalledModels(models, m.name);
        if (addModelModal) addModelModal.style.display = "none";
      });

      const delBtn = item.querySelector(".delete-custom-btn");
      if (delBtn) {
        delBtn.addEventListener("click", async () => {
          if (confirm(`Remove custom model tag '${m.name}'?`)) {
            await deleteCustomModel(m.name);
          }
        });
      }

      installedModelsList.appendChild(item);
    });
  }

  async function deleteCustomModel(modelName) {
    try {
      await fetch(`/api/models/custom/${encodeURIComponent(modelName)}`, { method: "DELETE" });
      await loadModels();
    } catch (err) {
      console.error("Failed to delete model:", err);
    }
  }

  // Load Workspace File Tree
  async function loadFiles() {
    try {
      fileTree.innerHTML = '<div class="tree-loading">Loading workspace files...</div>';
      const res = await fetch("/api/files");
      const data = await res.json();

      if (data.items && data.items.length > 0) {
        fileTree.innerHTML = "";
        data.items.forEach(item => {
          const el = document.createElement("div");
          el.className = `tree-item ${item.type}`;
          el.dataset.path = item.path;

          const icon = item.type === "directory" ? "📁" : "📄";
          el.innerHTML = `<span class="tree-item-icon">${icon}</span> <span>${item.path}</span>`;

          if (item.type === "file") {
            el.addEventListener("click", () => previewFile(item.path));
          }
          fileTree.appendChild(el);
        });
      } else {
        fileTree.innerHTML = '<div class="tree-loading">No files found in workspace</div>';
      }
    } catch (err) {
      fileTree.innerHTML = '<div class="tree-loading">Error loading files</div>';
    }
  }

  // Preview File Content
  async function previewFile(filePath) {
    switchTab("view-file");
    previewFileTitle.textContent = filePath;
    fileCodeContent.textContent = "Loading file content...";

    try {
      const res = await fetch(`/api/file?path=${encodeURIComponent(filePath)}`);
      const data = await res.json();
      if (data.content) {
        fileCodeContent.textContent = data.content;
      } else if (data.error) {
        fileCodeContent.textContent = `Error: ${data.error}`;
      }
    } catch (err) {
      fileCodeContent.textContent = `Failed to read file: ${err.message}`;
    }
  }

  // Refresh Git Diff
  async function refreshDiff() {
    try {
      const res = await fetch("/api/diff");
      const data = await res.json();
      if (data.diff) {
        renderDiff(data.diff, "Workspace Git Diff");
      } else {
        diffFileTitle.textContent = "Workspace Clean";
        diffCodeContent.textContent = "No active git modifications in workspace.";
      }
    } catch (err) {
      diffCodeContent.textContent = "Error fetching diff.";
    }
  }

  // Render Diff with Colorization
  function renderDiff(diffText, title = "Live Patch") {
    diffFileTitle.textContent = title;
    diffCodeContent.innerHTML = "";

    const lines = diffText.split("\n");
    const frag = document.createDocumentFragment();

    lines.forEach(line => {
      const span = document.createElement("span");
      if (line.startsWith("+") && !line.startsWith("+++")) {
        span.className = "diff-add";
      } else if (line.startsWith("-") && !line.startsWith("---")) {
        span.className = "diff-del";
      } else if (line.startsWith("@@") || line.startsWith("diff ") || line.startsWith("index ")) {
        span.className = "diff-header";
      }
      span.textContent = line + "\n";
      frag.appendChild(span);
    });

    diffCodeContent.appendChild(frag);
  }

  // Tab Switching
  function switchTab(targetTabId) {
    tabBtns.forEach(b => b.classList.toggle("active", b.dataset.tab === targetTabId));
    tabPanes.forEach(p => p.classList.toggle("active", p.id === targetTabId));
  }

  // Event Listeners
  function setupEventListeners() {
    tabBtns.forEach(btn => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    refreshFilesBtn.addEventListener("click", loadFiles);
    refreshDiffBtn.addEventListener("click", refreshDiff);
    clearTimelineBtn.addEventListener("click", () => {
      timelineFeed.innerHTML = "";
    });

    // Quick Scenario Chips
    document.querySelectorAll(".chip").forEach(chip => {
      chip.addEventListener("click", () => {
        taskInput.value = chip.dataset.task;
        taskInput.focus();
      });
    });

    // Run Agent Button
    runAgentBtn.addEventListener("click", runAgent);
    stopAgentBtn.addEventListener("click", stopAgent);

    // Keyboard shortcut (Ctrl+Enter) in textarea
    taskInput.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        runAgent();
      }
    });

    // Model Selector Change & Refresh
    modelSelector.addEventListener("change", () => {
      if (modelSelector.value === "__manage__") {
        openModelModal();
      }
    });

    if (refreshModelsBtn) {
      refreshModelsBtn.addEventListener("click", async () => {
        refreshModelsBtn.classList.add("spinning");
        await loadModels();
        setTimeout(() => refreshModelsBtn.classList.remove("spinning"), 500);
      });
    }

    // Modal Opening & Closing
    function openModelModal(initialTab = "tab-add-tag") {
      if (!addModelModal) return;
      addModelModal.style.display = "flex";
      switchModalTab(initialTab);
    }

    function closeModelModal() {
      if (!addModelModal) return;
      addModelModal.style.display = "none";
      if (modelSelector.value === "__manage__") {
        modelSelector.selectedIndex = 0;
      }
    }

    if (addModelBtn) {
      addModelBtn.addEventListener("click", () => openModelModal("tab-add-tag"));
    }
    if (pullModelBtn && pullModelBtn !== addModelBtn) {
      pullModelBtn.addEventListener("click", () => openModelModal("tab-pull-library"));
    }
    if (closeAddModelModalBtn) {
      closeAddModelModalBtn.addEventListener("click", closeModelModal);
    }
    if (closeModalFooterBtn) {
      closeModalFooterBtn.addEventListener("click", closeModelModal);
    }

    // Modal Tab Navigation
    const modalTabBtns = document.querySelectorAll(".modal-tab-btn");
    const modalTabPanes = document.querySelectorAll(".modal-tab-pane");
    function switchModalTab(targetTabId) {
      modalTabBtns.forEach(b => b.classList.toggle("active", b.dataset.tab === targetTabId));
      modalTabPanes.forEach(p => p.classList.toggle("active", p.id === targetTabId));
    }
    modalTabBtns.forEach(btn => {
      btn.addEventListener("click", () => switchModalTab(btn.dataset.tab));
    });

    // Model Quick Chips in Tab 1
    document.querySelectorAll(".model-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        if (customModelTagInput) {
          customModelTagInput.value = chip.dataset.model;
          customModelTagInput.focus();
        }
      });
    });

    // Tab 1: Add Custom / Installed Model Tag
    if (addTagBtn) {
      addTagBtn.addEventListener("click", addCustomModelTag);
    }
    if (customModelTagInput) {
      customModelTagInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") addCustomModelTag();
      });
    }

    // Tab 2: Pull Model from Registry
    if (startPullBtn) {
      startPullBtn.addEventListener("click", startPullModel);
    }

    // Tab 3: Import Local GGUF
    if (startGgufImportBtn) {
      startGgufImportBtn.addEventListener("click", startGgufImport);
    }

    // Tab 4: Server Endpoint
    if (saveEndpointBtn) {
      saveEndpointBtn.addEventListener("click", saveEndpointConfig);
    }

    // Workspace Switcher Events
    workspaceBadge.addEventListener("click", () => {
      workspaceModal.style.display = "flex";
      workspaceModalStatus.style.display = "none";
      workspacePathInput.value = workspacePathText.dataset.fullPath || "";
      workspacePathInput.focus();
    });

    closeWorkspaceModalBtn.addEventListener("click", () => {
      workspaceModal.style.display = "none";
    });

    cancelWorkspaceBtn.addEventListener("click", () => {
      workspaceModal.style.display = "none";
    });

    saveWorkspaceBtn.addEventListener("click", async () => {
      const newPath = workspacePathInput.value.trim();
      if (!newPath) return;

      saveWorkspaceBtn.disabled = true;
      workspaceModalStatus.style.display = "none";

      try {
        const res = await fetch("/api/workspace", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: newPath })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          workspacePathText.textContent = data.workspace.split(/[\\/]/).pop() || data.workspace;
          workspacePathText.dataset.fullPath = data.workspace;
          workspaceBadge.title = `Active: ${data.workspace} (Click to change)`;
          workspaceModal.style.display = "none";
          await loadFiles();
          await refreshDiff();
        } else {
          workspaceModalStatus.textContent = data.detail || "Failed to switch workspace";
          workspaceModalStatus.style.display = "block";
        }
      } catch (err) {
        workspaceModalStatus.textContent = `Error: ${err.message}`;
        workspaceModalStatus.style.display = "block";
      } finally {
        saveWorkspaceBtn.disabled = false;
      }
    });
  }

  // Execute Agent via Server-Sent Events (SSE)
  async function runAgent() {
    const task = taskInput.value.trim();
    if (!task) {
      alert("Please provide a task description or choose a quick scenario.");
      return;
    }

    if (isRunning) return;
    isRunning = true;

    // UI Updates
    runAgentBtn.style.display = "none";
    stopAgentBtn.style.display = "inline-flex";
    timelineDot.className = "status-indicator-dot active";
    agentStateLabel.textContent = "Autonomous Agent Running...";
    stepCounterBadge.textContent = "Starting...";

    // Remove welcome card if present
    const welcome = document.getElementById("welcome-message");
    if (welcome) welcome.remove();

    const selectedModel = modelSelector.value;

    try {
      const response = await fetch("/api/agent/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task: task,
          model: selectedModel,
          max_steps: 25
        })
      });

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop(); // Keep incomplete chunk

        for (const block of lines) {
          const match = block.match(/^data:\s*(.+)$/m);
          if (match) {
            try {
              const event = JSON.parse(match[1]);
              handleAgentEvent(event);
            } catch (e) {
              console.warn("SSE parse error", e, match[1]);
            }
          }
        }
      }
    } catch (err) {
      appendTimelineCard("error", {
        message: `Agent execution failed: ${err.message}`
      });
    } finally {
      finishAgentRun();
    }
  }

  function stopAgent() {
    finishAgentRun();
    agentStateLabel.textContent = "Agent Stopped by User";
  }

  function finishAgentRun() {
    isRunning = false;
    runAgentBtn.style.display = "inline-flex";
    stopAgentBtn.style.display = "none";
    timelineDot.className = "status-indicator-dot completed";
    agentStateLabel.textContent = "Execution Finished";
    loadFiles(); // Refresh file explorer
  }

  // Handle Event from Streaming Agent
  function handleAgentEvent(event) {
    const etype = event.type;

    if (etype === "agent_started") {
      stepCounterBadge.textContent = `Model: ${event.model}`;
      appendTimelineCard("system", {
        title: "Agent Initialized",
        content: `Target Model: <strong>${event.model}</strong><br>Objective: <em>${event.instruction}</em>`
      });
    } else if (etype === "step_start") {
      stepCounterBadge.textContent = `Step ${event.step} / ${event.max_steps}`;
    } else if (etype === "thought") {
      appendTimelineCard("thought", {
        step: event.step,
        thought: event.thought
      });
    } else if (etype === "tool_call") {
      appendTimelineCard("tool_call", {
        step: event.step,
        tool: event.tool,
        arguments: event.arguments
      });
    } else if (etype === "diff_updated") {
      switchTab("view-diff");
      renderDiff(event.diff, `Patch: ${event.path}`);
    } else if (etype === "self_healing_triggered") {
      appendTimelineCard("repair", {
        step: event.step,
        tool: event.tool,
        reason: event.reason,
        attempt: event.attempt
      });
    } else if (etype === "tool_result") {
      if (event.tool === "run_command") {
        const res = event.result || {};
        terminalContent.textContent = `$ ${res.command || ''}\n[Exit: ${res.exit_code}]\n\nSTDOUT:\n${res.stdout || '(none)'}\n\nSTDERR:\n${res.stderr || '(none)'}`;
        switchTab("view-terminal");
      }
      appendTimelineCard("tool_result", {
        step: event.step,
        tool: event.tool,
        result: event.result
      });
    } else if (etype === "task_finished") {
      stepCounterBadge.textContent = "Mission Accomplished";
      appendTimelineCard("finished", {
        step: event.step,
        summary: event.summary
      });
      refreshDiff();
    } else if (etype === "error") {
      appendTimelineCard("error", {
        message: event.message
      });
    }

    // Smooth autoscroll
    timelineFeed.scrollTop = timelineFeed.scrollHeight;
  }

  // Create UI Card in Timeline
  function appendTimelineCard(type, data) {
    const card = document.createElement("div");
    card.className = "timeline-card";

    if (type === "system") {
      card.innerHTML = `
        <div class="timeline-card-header">
          <span class="timeline-badge badge-thought">System</span>
        </div>
        <div class="thought-text">${data.content}</div>
      `;
    } else if (type === "thought") {
      card.innerHTML = `
        <div class="timeline-card-header">
          <span class="timeline-badge badge-thought">Chain-of-Thought</span>
          <span class="timeline-step">Step ${data.step}</span>
        </div>
        <div class="thought-text">${escapeHtml(data.thought)}</div>
      `;
    } else if (type === "tool_call") {
      const argsStr = JSON.stringify(data.arguments, null, 2);
      card.innerHTML = `
        <div class="timeline-card-header">
          <span class="timeline-badge badge-tool">Action: ${data.tool}</span>
          <span class="timeline-step">Step ${data.step}</span>
        </div>
        <pre class="tool-details"><code>${escapeHtml(argsStr)}</code></pre>
      `;
    } else if (type === "repair") {
      card.innerHTML = `
        <div class="timeline-card-header">
          <span class="timeline-badge badge-repair">Self-Healing Activated</span>
          <span class="timeline-step">Attempt #${data.attempt}</span>
        </div>
        <div class="repair-banner">
          <strong>Failure in ${data.tool}:</strong>
          <pre style="margin-top:4px;">${escapeHtml(data.reason)}</pre>
          <div style="margin-top:6px; font-weight:600;">Diagnosing error & generating recovery patch...</div>
        </div>
      `;
    } else if (type === "tool_result") {
      const isSuccess = data.result && !data.result.error && (data.result.exit_code === undefined || data.result.exit_code === 0);
      const statusBadge = isSuccess ? 'style="color: var(--accent-emerald)"' : 'style="color: var(--accent-rose)"';
      card.innerHTML = `
        <div class="timeline-card-header">
          <span class="timeline-badge badge-tool" ${statusBadge}>Observation: ${data.tool}</span>
          <span class="timeline-step">Step ${data.step}</span>
        </div>
        <pre class="tool-details"><code>${escapeHtml(JSON.stringify(data.result, null, 2).slice(0, 800))}</code></pre>
      `;
    } else if (type === "finished") {
      card.innerHTML = `
        <div class="timeline-card-header">
          <span class="timeline-badge badge-finished">Task Complete</span>
          <span class="timeline-step">Resolved in Step ${data.step}</span>
        </div>
        <div class="thought-text" style="color: #6ee7b7; font-weight: 500;">
          <strong>Summary:</strong><br>${escapeHtml(data.summary)}
        </div>
      `;
    } else if (type === "error") {
      card.innerHTML = `
        <div class="timeline-card-header">
          <span class="timeline-badge badge-repair">Error</span>
        </div>
        <div class="thought-text" style="color: var(--accent-rose);">${escapeHtml(data.message)}</div>
      `;
    }

    timelineFeed.appendChild(card);
  }

  // Model Pull Streaming
  async function startPullModel() {
    const modelTag = pullModelNameInput.value.trim();
    if (!modelTag) return;

    startPullBtn.disabled = true;
    pullProgressContainer.style.display = "block";
    pullStatusText.textContent = `Connecting to Ollama registry for ${modelTag}...`;

    try {
      const res = await fetch("/api/pull", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: modelTag })
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop();

        for (const block of lines) {
          const match = block.match(/^data:\s*(.+)$/m);
          if (match) {
            try {
              const chunk = JSON.parse(match[1]);
              const status = chunk.status || "";
              const completed = chunk.completed || 0;
              const total = chunk.total || 0;

              if (total > 0) {
                const pct = Math.round((completed / total) * 100);
                pullProgressFill.style.width = `${pct}%`;
                pullStatusText.textContent = `${status} - ${pct}% (${formatBytes(completed)} / ${formatBytes(total)})`;
              } else {
                pullStatusText.textContent = status;
              }
            } catch (e) {}
          }
        }
      }

      pullStatusText.textContent = `✓ Successfully downloaded ${modelTag}!`;
      pullProgressFill.style.width = "100%";
      setTimeout(() => {
        if (addModelModal) addModelModal.style.display = "none";
        startPullBtn.disabled = false;
        loadModels();
      }, 1500);
    } catch (err) {
      pullStatusText.textContent = `Error: ${err.message}`;
      startPullBtn.disabled = false;
    }
  }

  // Tab 1: Add Custom Model Tag
  async function addCustomModelTag() {
    const tagName = customModelTagInput.value.trim();
    if (!tagName) return;

    addTagBtn.disabled = true;
    addTagStatus.style.display = "block";
    addTagStatus.className = "status-message";
    addTagStatus.textContent = `Verifying model '${tagName}'...`;

    try {
      const res = await fetch("/api/models/custom", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: tagName })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        addTagStatus.className = "status-message success";
        addTagStatus.textContent = `✓ Successfully added '${tagName}' to OctoGemma!`;
        customModelTagInput.value = "";
        await loadModels();
        modelSelector.value = tagName;
        setTimeout(() => {
          addTagStatus.style.display = "none";
        }, 2500);
      } else {
        addTagStatus.className = "status-message error";
        addTagStatus.textContent = data.detail || "Failed to add model.";
      }
    } catch (err) {
      addTagStatus.className = "status-message error";
      addTagStatus.textContent = `Error: ${err.message}`;
    } finally {
      addTagBtn.disabled = false;
    }
  }

  // Tab 3: Import Local GGUF
  async function startGgufImport() {
    const modelName = ggufModelNameInput.value.trim();
    const ggufPath = ggufFilePathInput.value.trim();

    if (!modelName || !ggufPath) {
      if (ggufStatusMsg) {
        ggufStatusMsg.style.display = "block";
        ggufStatusMsg.className = "status-message error";
        ggufStatusMsg.textContent = "Please provide both a Model Name and a valid local GGUF File Path.";
      }
      return;
    }

    startGgufImportBtn.disabled = true;
    ggufProgressContainer.style.display = "block";
    if (ggufStatusMsg) ggufStatusMsg.style.display = "none";
    ggufStatusText.textContent = `Building Ollama model '${modelName}' from GGUF...`;

    try {
      const res = await fetch("/api/models/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: modelName, gguf_path: ggufPath })
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop();

        for (const block of lines) {
          const match = block.match(/^data:\s*(.+)$/m);
          if (match) {
            try {
              const chunk = JSON.parse(match[1]);
              const status = chunk.status || "";
              const completed = chunk.completed || 0;
              const total = chunk.total || 0;

              if (total > 0) {
                const pct = Math.round((completed / total) * 100);
                ggufProgressFill.style.width = `${pct}%`;
                ggufStatusText.textContent = `${status} - ${pct}%`;
              } else {
                ggufStatusText.textContent = status || "Processing GGUF...";
              }
            } catch (e) {}
          }
        }
      }

      ggufStatusText.textContent = `✓ Successfully created model '${modelName}'!`;
      ggufProgressFill.style.width = "100%";
      await loadModels();
      modelSelector.value = modelName;
      setTimeout(() => {
        if (addModelModal) addModelModal.style.display = "none";
        startGgufImportBtn.disabled = false;
      }, 1500);
    } catch (err) {
      if (ggufStatusMsg) {
        ggufStatusMsg.style.display = "block";
        ggufStatusMsg.className = "status-message error";
        ggufStatusMsg.textContent = `Import failed: ${err.message}`;
      }
      startGgufImportBtn.disabled = false;
    }
  }

  // Tab 4: Save Endpoint Config
  async function saveEndpointConfig() {
    const url = endpointUrlInput.value.trim();
    if (!url) return;

    saveEndpointBtn.disabled = true;
    endpointStatusMsg.style.display = "block";
    endpointStatusMsg.className = "status-message";
    endpointStatusMsg.textContent = "Connecting to endpoint...";

    try {
      const res = await fetch("/api/models/endpoint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: url })
      });
      const data = await res.json();
      if (data.connected) {
        endpointStatusMsg.className = "status-message success";
        endpointStatusMsg.textContent = `✓ Connected to ${data.endpoint}!`;
        await checkHealth();
        await loadModels();
      } else {
        endpointStatusMsg.className = "status-message error";
        endpointStatusMsg.textContent = `Endpoint set to ${data.endpoint}, but server is unreachable.`;
        await checkHealth();
      }
    } catch (err) {
      endpointStatusMsg.className = "status-message error";
      endpointStatusMsg.textContent = `Error: ${err.message}`;
    } finally {
      saveEndpointBtn.disabled = false;
    }
  }

  // Helper Functions
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  init();
});
