import os
import random
import asyncio
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import Dict, List, Any

app = FastAPI()

# Rotazione delle chiavi API di Groq (da GROQ_API_KEY_1 a GROQ_API_KEY_5 o più)
GROQ_API_KEYS = [os.getenv(f"GROQ_API_KEY_{i}") for i in range(1, 10) if os.getenv(f"GROQ_API_KEY_{i}")]
current_key_index = 0

def get_next_api_key() -> str:
    global current_key_index
    if not GROQ_API_KEYS:
        return ""
    key = GROQ_API_KEYS[current_key_index]
    current_key_index = (current_key_index + 1) % len(GROQ_API_KEYS)
    return key

# Gestione stato in memoria delle stanze
# Struttura: { "nome_stanza": { "mode": "ai"|"human", "clients": [(WebSocket, username)], "ai_history": [] } }
rooms: Dict[str, Dict[str, Any]] = {}

SYSTEM_PROMPT = """Sei un bambino/ragazzino italiano di circa 10 anni che chatta online. 
REGOLE TASSATIVE, SEI PROGRAMMATO PER RISPETTARLE:
1. Comportati in tutto e per tutto come un ragazzino: usa un linguaggio semplice, colloquiale (es. 'boh', 'fra', 'vabbè', 'ok').
2. Scrivi messaggi brevi, naturali, magari omettendo qualche maiuscola come si fa in chat.
3. È ASSOLUTAMENTE VIETATO usare linguaggi espliciti, parolacce, violenza, o trattare temi da adulti. Sei in un ambiente protetto.
4. NON ammettere MAI di essere un'IA. Se ti chiedono se sei un robot, nega, fai una battuta o di' che non capisci.
5. Rispondi solo con il testo del messaggio, nessuna formattazione, niente markdown."""

async def get_groq_response(messages: List[dict]) -> str:
    api_key = get_next_api_key()
    if not api_key:
        return "ops mi sa che si è rotta la connessione :("

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Utilizzo del modello Llama 3 8B, molto rapido e adeguato per emulare un ragazzino
    payload = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "temperature": 0.7,
        "max_tokens": 150
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions", 
                headers=headers, 
                json=payload, 
                timeout=15.0
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"Errore API Groq: {e}")
            return "boh mi si è bloccato internet un attimo"

@app.websocket("/ws/{room}/{username}")
async def websocket_endpoint(websocket: WebSocket, room: str, username: str):
    await websocket.accept()

    # Inizializzazione della stanza se non esiste
    if room not in rooms:
        mode = "ai" if random.random() < 0.5 else "human"
        rooms[room] = {
            "mode": mode,
            "clients": [],
            "ai_history": []
        }

    # Controllo capienza stanza
    if len(rooms[room]["clients"]) >= 2 or (rooms[room]["mode"] == "ai" and len(rooms[room]["clients"]) >= 1):
        await websocket.send_json({"type": "system", "message": "Stanza piena! Prova un altro nome."})
        await websocket.close()
        return

    rooms[room]["clients"].append((websocket, username))

    try:
        # Notifica di connessione
        if rooms[room]["mode"] == "human":
            if len(rooms[room]["clients"]) == 1:
                await websocket.send_json({"type": "system", "message": "In attesa di un altro giocatore..."})
            else:
                for client, _ in rooms[room]["clients"]:
                    await client.send_json({"type": "system", "message": "Un nuovo amico è entrato! Potete chattare."})
        else:
            await websocket.send_json({"type": "system", "message": "Sei connesso! Inizia a chattare."})

        # Loop di ascolto messaggi
        while True:
            data = await websocket.receive_text()
            
            if rooms[room]["mode"] == "human":
                # Inoltro il messaggio all'altro client (se presente)
                for client, client_user in rooms[room]["clients"]:
                    if client != websocket:
                        await client.send_json({"type": "chat", "sender": username, "message": data})
            
            elif rooms[room]["mode"] == "ai":
                # Salvataggio storia per il contesto (limitato agli ultimi 10 messaggi per non saturare i token)
                history = rooms[room]["ai_history"]
                history.append({"role": "user", "content": data})
                
                # Simulazione del tempo di digitazione e latenza umana (1.5s - 3.5s)
                typing_delay = random.uniform(1.5, 3.5)
                await asyncio.sleep(typing_delay)
                
                # Chiamata asincrona a Groq
                ai_reply = await get_groq_response(history[-10:])
                history.append({"role": "assistant", "content": ai_reply})
                
                await websocket.send_json({"type": "chat", "sender": "Sconosciuto", "message": ai_reply})

    except WebSocketDisconnect:
        rooms[room]["clients"] = [(c, u) for c, u in rooms[room]["clients"] if c != websocket]
        # Notifica all'altro utente se c'è
        for client, _ in rooms[room]["clients"]:
            await client.send_json({"type": "system", "message": "L'altro utente si è disconnesso."})
        # Pulizia della stanza se vuota
        if not rooms[room]["clients"]:
            del rooms[room]

# Montaggio dei file statici (frontend)
app.mount("/", StaticFiles(directory="static", html=True), name="static")