/* Apple Siri App Logic & PySide6 Bridge Handler for JARVIS */

let isListening = false;
let isSoundEnabled = true;
let recognition = null;
let pyBackend = null;

// Initialize WebChannel / PySide6 Bridge
window.addEventListener('DOMContentLoaded', () => {
    initSpeechRecognition();
    
    // Check PySide6 WebChannel Bridge
    if (typeof QWebChannel !== 'undefined' && window.qt) {
        new QWebChannel(qt.webChannelTransport, function (channel) {
            pyBackend = channel.objects.pyBackend;
            window.pyBridge = pyBackend;
            console.log("Connected to JARVIS PySide6 Backend");

            // Listen to backend signals
            if (pyBackend.responseReady) {
                pyBackend.responseReady.connect((response) => {
                    handleSiriResponse(response);
                });
            }
            if (pyBackend.stateChanged) {
                pyBackend.stateChanged.connect((state) => {
                    setSiriState(state);
                });
            }
        });
    }
});

/* Initialize Web Speech API for Native Siri Voice Listening */
function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
            isListening = true;
            setSiriState('listening');
            updateMicBtnState(true);
        };

        recognition.onresult = (event) => {
            let interimTranscript = '';
            let finalTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else {
                    interimTranscript += event.results[i][0].transcript;
                }
            }

            const currentText = finalTranscript || interimTranscript;
            document.getElementById('userInput').value = currentText;

            // Audio level simulation during voice input
            if (siriOrb) siriOrb.setAudioLevel(0.4 + Math.random() * 0.5);

            if (finalTranscript.trim()) {
                submitPrompt(finalTranscript.trim());
            }
        };

        recognition.onerror = (event) => {
            console.warn("Speech recognition error:", event.error);
            stopVoiceListening();
        };

        recognition.onend = () => {
            stopVoiceListening();
        };
    } else {
        console.log("Web Speech API not supported in this browser environment.");
    }
}

/* Toggle Siri Voice Listening */
function toggleVoiceListening() {
    if (isListening) {
        stopVoiceListening();
    } else {
        startVoiceListening();
    }
}

function startVoiceListening() {
    playChime();
    if (recognition) {
        try {
            recognition.start();
        } catch (e) {
            console.log("Recognition already active", e);
        }
    } else {
        // Fallback simulate voice listening state
        isListening = true;
        setSiriState('listening');
        updateMicBtnState(true);
        
        // If pyBackend is available, trigger backend mic
        if (pyBackend && pyBackend.startListening) {
            pyBackend.startListening();
        }
    }
}

function stopVoiceListening() {
    isListening = false;
    updateMicBtnState(false);
    if (recognition) {
        try { recognition.stop(); } catch (e) {}
    }
    if (pyBackend && pyBackend.stopListening) {
        pyBackend.stopListening();
    }
    setSiriState('idle');
}

function updateMicBtnState(active) {
    const micBtn = document.getElementById('micBtn');
    const orbWrapper = document.getElementById('orbWrapper');
    
    if (active) {
        micBtn.classList.add('active');
        orbWrapper.classList.add('listening');
    } else {
        micBtn.classList.remove('active');
        orbWrapper.classList.remove('listening');
    }
}

/* UI State Machine for Siri */
function setSiriState(state) {
    const statusText = document.getElementById('siriStatusText');
    const edgeGlow = document.getElementById('siriEdgeGlow');
    const orbWrapper = document.getElementById('orbWrapper');

    orbWrapper.className = 'orb-wrapper ' + state;

    if (siriOrb) siriOrb.setState(state);

    if (state === 'listening') {
        statusText.innerText = "Siri is listening...";
        edgeGlow.classList.add('active-listening');
    } else if (state === 'thinking') {
        statusText.innerText = "JARVIS is thinking...";
        edgeGlow.classList.remove('active-listening');
    } else if (state === 'speaking') {
        statusText.innerText = "Siri speaking...";
        edgeGlow.classList.remove('active-listening');
    } else { // idle
        statusText.innerText = "Tap to talk to Siri";
        edgeGlow.classList.remove('active-listening');
    }
}

/* Handle Form Submission */
function handleFormSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('userInput');
    const text = input.value.trim();
    if (text) {
        submitPrompt(text);
        input.value = '';
    }
}

function sendQuickPrompt(promptText) {
    document.getElementById('userInput').value = promptText;
    submitPrompt(promptText);
}

function submitPrompt(text) {
    // Hide greeting on first message
    const greeting = document.getElementById('siriGreeting');
    if (greeting) greeting.style.display = 'none';

    // Append User message to transcript
    appendMessage('user', text);
    
    // Set Siri state to thinking
    setSiriState('thinking');

    // Send to Python Backend or Web Fallback AI
    if (pyBackend && pyBackend.processPrompt) {
        pyBackend.processPrompt(text);
    } else {
        simulateLocalSiriAI(text);
    }
}

/* Append Message to Chat Stream */
function appendMessage(sender, text) {
    const container = document.getElementById('messagesContainer');
    
    const wrapper = document.createElement('div');
    wrapper.className = `msg-wrapper ${sender}`;

    const author = document.createElement('div');
    author.className = 'msg-author';
    author.innerText = sender === 'user' ? 'You' : 'JARVIS Siri';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    bubble.innerText = text;

    wrapper.appendChild(author);
    wrapper.appendChild(bubble);
    container.appendChild(wrapper);

    // Scroll to bottom
    const transcriptArea = document.getElementById('transcriptArea');
    transcriptArea.scrollTop = transcriptArea.scrollHeight;
}

/* Receive Response from Siri / JARVIS */
function handleSiriResponse(responseText) {
    appendMessage('siri', responseText);
    setSiriState('speaking');

    if (isSoundEnabled) {
        speakResponse(responseText);
    } else {
        setTimeout(() => setSiriState('idle'), 1500);
    }
}

/* Speech Synthesis for Siri */
function speakResponse(text) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.05;
        utterance.pitch = 1.0;

        // Try to pick a Siri / Natural voice if available
        const voices = window.speechSynthesis.getVoices();
        const siriVoice = voices.find(v => v.name.includes('Siri') || v.name.includes('Samantha') || v.name.includes('Google US English') || v.name.includes('Natural'));
        if (siriVoice) utterance.voice = siriVoice;

        utterance.onboundary = () => {
            if (siriOrb) siriOrb.setAudioLevel(0.3 + Math.random() * 0.6);
        };

        utterance.onend = () => {
            setSiriState('idle');
        };

        window.speechSynthesis.speak(utterance);
    } else {
        setTimeout(() => setSiriState('idle'), 2000);
    }
}

/* Local Simulated AI Response (Web Fallback) */
function simulateLocalSiriAI(query) {
    const q = query.toLowerCase();
    let reply = "";

    if (q.includes('time') || q.includes('date')) {
        const now = new Date();
        reply = `It's ${now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} on ${now.toLocaleDateString([], {weekday: 'long', month: 'long', day: 'numeric'})}.`;
    } else if (q.includes('joke')) {
        const jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "I asked Siri if she loves me... She said 'I respect you as a user'.",
            "Why did the computer go to the doctor? Because it had a virus!"
        ];
        reply = jokes[Math.floor(Math.random() * jokes.length)];
    } else if (q.includes('who is jarvis') || q.includes('who are you')) {
        reply = "I am JARVIS, your intelligent AI assistant, styled with Apple Siri's liquid glow aesthetic!";
    } else if (q.includes('chrome') || q.includes('open')) {
        reply = `Opening requested application for you right away.`;
    } else if (q.includes('health') || q.includes('system') || q.includes('cpu')) {
        reply = "System status: All services operational. CPU load is normal at 14%, Memory usage 4.2 GB.";
    } else {
        reply = `I processed your request: "${query}". How else can I assist you today?`;
    }

    setTimeout(() => {
        handleSiriResponse(reply);
    }, 1000);
}

/* Sound Chime & Controls */
function playChime() {
    const sound = document.getElementById('siriChimeSound');
    if (sound) {
        sound.currentTime = 0;
        sound.play().catch(() => {});
    }
}

function toggleSound() {
    isSoundEnabled = !isSoundEnabled;
    const soundBtn = document.getElementById('soundIcon');
    if (isSoundEnabled) {
        soundBtn.className = 'fa-solid fa-volume-high';
    } else {
        soundBtn.className = 'fa-solid fa-volume-xmark';
    }
}
