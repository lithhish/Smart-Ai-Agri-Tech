/**
 * agriculture_chatbot.js - Frontend interactions for Agriculture AI Chatbot
 * Supports:
 * - Conversational UI on the left sidebar
 * - Multi-language switching (English, Tamil, Hindi, Telugu, Kannada, Malayalam)
 * - Soil moisture and irrigation decision queries
 * - Speech-to-text (Web Speech API) and Text-to-speech
 * - Citations and sensor readings display
 */

let currentSessionId = "session_" + Math.random().toString(36).substring(2, 9);
let currentLanguage = "en";
let recognition = null;
let isListening = false;

document.addEventListener("DOMContentLoaded", () => {
    initChatbot();
});

async function initChatbot() {
    const langSelect = document.getElementById("chatLanguageSelect");
    if (langSelect) {
        langSelect.addEventListener("change", (e) => {
            currentLanguage = e.target.value;
            updateQuickPromptChips();
        });
    }

    const chatInput = document.getElementById("chatUserInput");
    if (chatInput) {
        chatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    }

    // Initialize Web Speech API if supported
    initSpeechRecognition();

    // Fetch engine and document status
    loadChatbotStatus();
}

async function loadChatbotStatus() {
    try {
        const resp = await fetch("/api/chatbot/status");
        if (resp.ok) {
            const data = await resp.json();
            const tag = document.getElementById("chatbotEngineStatus");
            if (tag) {
                if (data.gemini && data.gemini.available) {
                    tag.innerHTML = `<span class="status-dot"></span> Gemini (${data.gemini.model || "Active"})`;
                } else {
                    tag.innerHTML = `<span class="status-dot" style="background:#0284c7;"></span> Grounded RAG (${data.total_chunks} passages)`;
                }
            }
        }
    } catch (e) {
        console.warn("Could not check chatbot status", e);
    }
}

function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const micBtn = document.getElementById("chatMicBtn");
    if (!SpeechRecognition) {
        if (micBtn) {
            micBtn.title = "Voice recognition not supported in this browser";
            micBtn.style.opacity = "0.5";
        }
        return;
    }

    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
        isListening = true;
        if (micBtn) micBtn.classList.add("recording");
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        const input = document.getElementById("chatUserInput");
        if (input) {
            input.value = transcript;
            sendChatMessage();
        }
    };

    recognition.onerror = (event) => {
        console.error("Speech recognition error", event.error);
        stopListening();
    };

    recognition.onend = () => {
        stopListening();
    };
}

function toggleVoiceInput() {
    if (!recognition) {
        alert("Speech-to-text requires a browser supporting Web Speech API (such as Chrome or Edge).");
        return;
    }

    if (isListening) {
        recognition.stop();
        stopListening();
    } else {
        // Set speech language
        const langMap = {
            "en": "en-IN",
            "ta": "ta-IN",
            "hi": "hi-IN",
            "te": "te-IN",
            "kn": "kn-IN",
            "ml": "ml-IN"
        };
        recognition.lang = langMap[currentLanguage] || "en-IN";
        try {
            recognition.start();
        } catch (e) {
            console.warn("Speech start error:", e);
        }
    }
}

function stopListening() {
    isListening = false;
    const micBtn = document.getElementById("chatMicBtn");
    if (micBtn) micBtn.classList.remove("recording");
}

function speakText(text) {
    if (!window.speechSynthesis) {
        alert("Text-to-speech is not supported by your browser.");
        return;
    }

    window.speechSynthesis.cancel(); // Stop any ongoing speech
    // Clean markdown asterisks and icons for speech
    const cleanText = text.replace(/[*#_`]/g, "").replace(/💧|✅|⚠️|📄|•/g, "");
    const utterance = new SpeechSynthesisUtterance(cleanText);

    const langMap = {
        "en": "en-IN",
        "ta": "ta-IN",
        "hi": "hi-IN",
        "te": "te-IN",
        "kn": "kn-IN",
        "ml": "ml-IN"
    };
    utterance.lang = langMap[currentLanguage] || "en-IN";
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
}

function sendQuickPrompt(promptText) {
    const input = document.getElementById("chatUserInput");
    if (input) {
        input.value = promptText;
        sendChatMessage();
    }
}

function updateQuickPromptChips() {
    const container = document.getElementById("quickPromptsBar");
    if (!container) return;

    if (currentLanguage === "ta") {
        container.innerHTML = `
            <button class="quick-chip" onclick="sendQuickPrompt('மண் ஈரப்பதம் எவ்வளவு?')">மண் ஈரப்பதம்</button>
            <button class="quick-chip" onclick="sendQuickPrompt('இப்போது பாசனம் தேவையா?')">பாசனம் தேவையா?</button>
            <button class="quick-chip" onclick="sendQuickPrompt('கரும்பு நீர்ப்பாசன வழிகாட்டி')">கரும்பு பாசனம்</button>
            <button class="quick-chip" onclick="sendQuickPrompt('பருத்தி ஈரப்பதம் அளவு')">பருத்தி பாசனம்</button>
        `;
    } else if (currentLanguage === "hi") {
        container.innerHTML = `
            <button class="quick-chip" onclick="sendQuickPrompt('मिट्टी की नमी कितनी है?')">मिट्टी की नमी</button>
            <button class="quick-chip" onclick="sendQuickPrompt('क्या अभी सिंचाई चाहिए?')">सिंचाई की जरूरत</button>
            <button class="quick-chip" onclick="sendQuickPrompt('गन्ने के लिए सिंचाई सीमा')">गन्ना सिंचाई</button>
        `;
    } else {
        container.innerHTML = `
            <button class="quick-chip" onclick="sendQuickPrompt('What is the latest soil moisture reading?')">Soil Moisture</button>
            <button class="quick-chip" onclick="sendQuickPrompt('Is irrigation required according to threshold?')">Irrigation Needed?</button>
            <button class="quick-chip" onclick="sendQuickPrompt('What is the moisture threshold for sugarcane?')">Sugarcane Guide</button>
            <button class="quick-chip" onclick="sendQuickPrompt('What are the recorded NPK values?')">NPK Status</button>
        `;
    }
}

async function sendChatMessage() {
    const input = document.getElementById("chatUserInput");
    if (!input) return;

    const message = input.value.trim();
    if (!message) return;

    input.value = "";
    appendMessage("user", message);

    const sendBtn = document.getElementById("chatSendBtn");
    if (sendBtn) sendBtn.disabled = true;

    const typingId = showTypingIndicator();

    try {
        const response = await fetch("/api/chatbot/message", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: message,
                session_id: currentSessionId,
                language: currentLanguage
            })
        });

        removeTypingIndicator(typingId);

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            appendMessage("assistant", "⚠️ Server Error: " + (errData.error || response.statusText));
            return;
        }

        const data = await response.json();
        appendMessage("assistant", data.answer, data.citations, data.sensor_data);

    } catch (err) {
        removeTypingIndicator(typingId);
        appendMessage("assistant", "⚠️ Could not connect to chatbot server. Please verify Flask is running.");
    } finally {
        if (sendBtn) sendBtn.disabled = false;
        input.focus();
    }
}

function appendMessage(role, text, citations = [], sensorData = null) {
    const messagesContainer = document.getElementById("chatMessages");
    if (!messagesContainer) return;

    const msgDiv = document.createElement("div");
    msgDiv.className = `chat-message ${role}`;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.innerHTML = formatMarkdown(text);

    msgDiv.appendChild(bubble);

    // Citations box if citations exist
    if (citations && citations.length > 0) {
        const citeBox = document.createElement("div");
        citeBox.className = "citations-box";
        citeBox.innerHTML = `
            <div class="citations-title">
                <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
                Verified Sources:
            </div>
            ${citations.map(c => `
                <div class="citation-item">
                    • <strong>${escapeHtml(c.title || "Document")}</strong> (${escapeHtml(c.source || "Official")})
                    ${c.page ? ` - Page ${c.page}` : ""}
                    ${c.url ? ` <a class="citation-link" href="${c.url}" target="_blank" rel="noopener">Link</a>` : ""}
                </div>
            `).join("")}
        `;
        msgDiv.appendChild(citeBox);
    }

    // Audio read aloud button for assistant responses
    if (role === "assistant") {
        const speakBtn = document.createElement("button");
        speakBtn.className = "speak-btn";
        speakBtn.innerHTML = `<svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg> Speak`;
        speakBtn.onclick = () => speakText(text);
        msgDiv.appendChild(speakBtn);
    }

    const timeSpan = document.createElement("span");
    timeSpan.className = "message-time";
    timeSpan.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    msgDiv.appendChild(timeSpan);

    messagesContainer.appendChild(msgDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showTypingIndicator() {
    const messagesContainer = document.getElementById("chatMessages");
    if (!messagesContainer) return null;

    const typingDiv = document.createElement("div");
    const id = "typing_" + Date.now();
    typingDiv.id = id;
    typingDiv.className = "chat-message assistant";
    typingDiv.innerHTML = `
        <div class="message-bubble typing-dots">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
    `;
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    return id;
}

function removeTypingIndicator(id) {
    if (!id) return;
    const elem = document.getElementById(id);
    if (elem) elem.remove();
}

function formatMarkdown(text) {
    if (!text) return "";
    let safe = escapeHtml(text);
    safe = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    safe = safe.replace(/\*([^\*]+?)\*/g, '<em>$1</em>');
    safe = safe.replace(/\n/g, '<br>');
    return safe;
}

function escapeHtml(text) {
    if (!text) return "";
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
