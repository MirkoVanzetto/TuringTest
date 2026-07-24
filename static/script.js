let ws = null;
const loginPanel = document.getElementById('login-panel');
const chatPanel = document.getElementById('chat-panel');
const joinBtn = document.getElementById('join-btn');
const sendBtn = document.getElementById('send-btn');
const leaveBtn = document.getElementById('leave-btn');
const usernameInput = document.getElementById('username');
const roomInput = document.getElementById('room');
const messageInput = document.getElementById('message-input');
const chatBox = document.getElementById('chat-box');
const roomDisplay = document.getElementById('room-display');

function addMessage(text, senderType) {
    const div = document.createElement('div');
    div.classList.add('msg');
    
    if (senderType === 'me') {
        div.classList.add('msg-me');
        div.textContent = text;
    } else if (senderType === 'system') {
        div.classList.add('msg-system');
        div.textContent = text;
    } else {
        div.classList.add('msg-other');
        div.textContent = text;
    }
    
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

joinBtn.addEventListener('click', () => {
    const username = usernameInput.value.trim();
    const room = roomInput.value.trim();

    if (!username || !room) {
        alert("Per favore, inserisci sia il nome che la stanza!");
        return;
    }

    // Gestione protocollo sicuro se in hosting su Render (https -> wss)
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${protocol}://${window.location.host}/ws/${room}/${username}`;
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        loginPanel.classList.add('hidden');
        chatPanel.classList.remove('hidden');
        roomDisplay.textContent = room;
        chatBox.innerHTML = '';
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'system') {
            addMessage(data.message, 'system');
        } else if (data.type === 'chat') {
            addMessage(`${data.message}`, 'other');
        }
    };

    ws.onclose = () => {
        addMessage("Connessione chiusa. Aggiorna la pagina.", "system");
    };
});

function sendMessage() {
    const text = messageInput.value.trim();
    if (text && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(text);
        addMessage(text, 'me');
        messageInput.value = '';
    }
}

sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

leaveBtn.addEventListener('click', () => {
    if (ws) ws.close();
    chatPanel.classList.add('hidden');
    loginPanel.classList.remove('hidden');
    usernameInput.value = '';
    roomInput.value = '';
});