/**
 * OctoGemma Studio — Frontend Controller
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const ollamaStatusInd = document.getElementById("ollama-status-indicator");
  const ollamaStatusText = document.getElementById("ollama-status-text");
  const modelSelector = document.getElementById("model-selector");
  const pullModelBtn = document.getElementById("pull-model-btn");
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

  // Modal Elements
  const pullModal = document.getElementById("pull-modal");
  const closePullModalBtn = document.getElementById("close-pull-modal-btn");
  const cancelPullBtn = document.getElementById("cancel-pull-btn");
  const startPullBtn = document.getElementById("start-pull-btn");
  const pullModelNameInput = document.getElementById("pull-model-name-input");
  const pullProgressContainer = document.getElementById("pull-progress-container");
  const pullProgressFill = document.getElementById("pull-progress-fill");
  const pullStatusText = document.getElementById("pull-status-text");

  let activeEventSource = null;
  let isRunning = false;

  // Initialize System
  async function init() {
    await checkHealth();
    await loadModels();
    await loadFiles();
    setupEventListeners();
  }

  // Check Ollama Health
  async function checkHealth() {
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      if (data.ollama_connected) {
        ollamaStatusText.textContent = "Ollama Active";
        ollamaStatusInd.style.borderColor = "rgba(16, 185, 129, 0.4)";
        workspacePathText.textContent = data.workspace.split(/[\\/]/).pop() || "Workspace";
      } else {
        ollamaStatusText.textContent = "Ollama Disconnected";
        ollamaStatusInd.style.color = "var(--accent-rose)";
        ollamaStatusInd.style.borderColor = "rgba(244, 63, 94, 0.4)";
      }
    } catch (err) {
      ollamaStatusText.textContent = "Backend Offline";
      ollamaStatusInd.style.color = "var(--accent-rose)";
    }
  }

  // Load Models
  async function loadModels() {
    try {
      const res = await fetch("/api/models");
      const data = await res.json();
      if (data.models && data.models.length > 0) {
        modelSelector.innerHTML = "";
        data.models.forEach(m => {
          const opt = document.createElement("option");
          opt.value = m.name;
          const isGemma = m.name.includes("gemma");
          opt.textContent = `${m.name} ${isGemma ? '★ Recommended' : ''}`;
          if (m.name === data.preferred) {
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
    } catch (err) {
      console.error("Failed to load models:", err);
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

    // Modal Events
    pullModelBtn.addEventListener("click", () => {
      pullModal.style.display = "flex";
      pullProgressContainer.style.display = "none";
    });

    closePullModalBtn.addEventListener("click", () => {
      pullModal.style.display = "none";
    });

    cancelPullBtn.addEventListener("click", () => {
      pullModal.style.display = "none";
    });

    startPullBtn.addEventListener("click", startPullModel);
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
        pullModal.style.display = "none";
        startPullBtn.disabled = false;
        loadModels();
      }, 1500);
    } catch (err) {
      pullStatusText.textContent = `Error: ${err.message}`;
      startPullBtn.disabled = false;
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
