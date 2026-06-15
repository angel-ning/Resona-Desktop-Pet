const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const wsUrl = `${wsProtocol}//${window.location.host}/ws`;

let socket = null;
let sessionId = localStorage.getItem("resona_agent_session_id");
let pendingConfirmation = null;

const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const transcript = document.getElementById("transcript");
const events = document.getElementById("events");
const tools = document.getElementById("tools");
const input = document.getElementById("agent-input");
const sendBtn = document.getElementById("send-btn");
const confirmationPanel = document.getElementById("confirmation-panel");

function setStatus(state, text) {
    statusDot.className = `status-dot ${state}`;
    statusText.textContent = text;
}

function appendEntry(container, label, content, className = "") {
    const el = document.createElement("div");
    el.className = `entry ${className}`.trim();

    const labelEl = document.createElement("span");
    labelEl.className = "entry-label";
    labelEl.textContent = label;
    el.appendChild(labelEl);

    const body = document.createElement("div");
    body.textContent = typeof content === "string" ? content : JSON.stringify(content, null, 2);
    el.appendChild(body);

    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
}

function renderConfirmation(confirmation) {
    pendingConfirmation = confirmation;
    confirmationPanel.classList.remove("hidden");
    confirmationPanel.innerHTML = "";

    const title = document.createElement("h2");
    title.textContent = `Confirmation required: ${confirmation.tool_name}`;
    confirmationPanel.appendChild(title);

    const reason = document.createElement("div");
    reason.textContent = confirmation.policy_reason || "Runtime policy requires confirmation.";
    confirmationPanel.appendChild(reason);

    const args = document.createElement("pre");
    args.textContent = JSON.stringify(confirmation.arguments || {}, null, 2);
    confirmationPanel.appendChild(args);

    const actions = document.createElement("div");
    actions.className = "confirmation-actions";

    const approve = document.createElement("button");
    approve.textContent = "Confirm and execute";
    approve.addEventListener("click", () => sendConfirmation(true));

    const reject = document.createElement("button");
    reject.className = "danger";
    reject.textContent = "Reject";
    reject.addEventListener("click", () => sendConfirmation(false));

    actions.appendChild(approve);
    actions.appendChild(reject);
    confirmationPanel.appendChild(actions);
}

function clearConfirmation() {
    pendingConfirmation = null;
    confirmationPanel.classList.add("hidden");
    confirmationPanel.innerHTML = "";
}

function sendConfirmation(approved) {
    if (!pendingConfirmation || !socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({
        type: approved ? "confirm_tool" : "reject_tool",
        confirmation_id: pendingConfirmation.confirmation_id
    }));
    appendEntry(tools, approved ? "confirmation approved" : "confirmation rejected", pendingConfirmation, approved ? "" : "error");
    clearConfirmation();
}

function connect() {
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        setStatus("connected", "Connected");
        socket.send(JSON.stringify({
            type: "handshake",
            client_type: "agent_console",
            session_id: sessionId,
            pack_id: "Resona_Operator"
        }));
    };

    socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    };

    socket.onclose = () => {
        setStatus("disconnected", "Disconnected");
        setTimeout(connect, 2500);
    };

    socket.onerror = () => {
        setStatus("disconnected", "Connection error");
    };
}

function handleMessage(msg) {
    if (msg.type === "handshake_ack") {
        sessionId = msg.session_id;
        localStorage.setItem("resona_agent_session_id", sessionId);
        appendEntry(events, "handshake", {
            session_id: sessionId,
            pack: "Resona_Operator"
        });
        return;
    }

    if (msg.type === "agent_status") {
        const running = msg.state === "running";
        setStatus(running ? "running" : "connected", msg.message || msg.state || "Ready");
        input.disabled = running;
        sendBtn.disabled = running;
        appendEntry(events, "status", msg);
        return;
    }

    if (msg.type === "agent_event") {
        appendEntry(events, msg.event?.type || "agent_event", msg.event || msg);
        return;
    }

    if (msg.type === "tool_result") {
        appendEntry(tools, msg.result?.status || "tool_result", msg.result || msg);
        return;
    }

    if (msg.type === "confirmation_required") {
        appendEntry(tools, "confirmation_required", msg.confirmation || msg);
        renderConfirmation(msg.confirmation);
        return;
    }

    if (msg.type === "agent_message") {
        appendEntry(transcript, "Resona Operator", msg.text || "", "agent");
        if (msg.thought) appendEntry(events, "thought", msg.thought);
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
        return;
    }

    if (msg.type === "agent_error") {
        appendEntry(transcript, "error", msg.message || "Unknown error", "error");
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
        return;
    }

    appendEntry(events, msg.type || "message", msg);
}

function sendText() {
    const text = input.value.trim();
    if (!text || !socket || socket.readyState !== WebSocket.OPEN) return;
    if (pendingConfirmation) {
        appendEntry(transcript, "error", "A tool call is awaiting confirmation.", "error");
        return;
    }

    appendEntry(transcript, "You", text, "user");
    socket.send(JSON.stringify({ type: "text_input", text }));
    input.value = "";
    input.disabled = true;
    sendBtn.disabled = true;
}

sendBtn.addEventListener("click", sendText);
input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        sendText();
    }
});

appendEntry(events, "hint", "Use Ctrl+Enter to send.");
connect();
