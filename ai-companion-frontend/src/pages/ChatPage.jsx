import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { Mic, LogOut, Square } from 'lucide-react';
import * as vad from "@ricky0123/vad-web";
// Corrected import path based on your confirmation
import '../styles/Chatpage.css';

// Ensure this is correctly set in your Vercel frontend project's environment variables
const API_URL = import.meta.env.VITE_API_URL;

export default function ChatPage() {
    // --- State and Refs ---
    const { user, logout, getAccessTokenSilently, isLoading, isAuthenticated } = useAuth0(); // Added isLoading, isAuthenticated
    const [messages, setMessages] = useState([]);
    const [emotion, setEmotion] = useState('neutral');
    const [isConversationActive, setIsConversationActive] = useState(false);
    const [isListeningForSpeech, setIsListeningForSpeech] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const vadRef = useRef(null);
    const streamRef = useRef(null);
    const audioContextRef = useRef(null);
    const silenceTimerRef = useRef(null);
    const messagesEndRef = useRef(null); // Ref for scrolling

    // --- VAD Logic ---
    const startVad = useCallback(async () => {
        if (vadRef.current || isProcessing) {
            console.log("VAD start skipped: Already running or processing.");
            return;
        }
        console.log("Attempting to start VAD...");
        setIsListeningForSpeech(true);
        try {
            if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
                audioContextRef.current = new AudioContext();
                await audioContextRef.current.resume();
            }
            if (!streamRef.current || streamRef.current.getAudioTracks().every(t => t.readyState === 'ended')) {
                streamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true });
            }

            const newVad = await vad.MicVAD.new({
                audioContext: audioContextRef.current,
                stream: streamRef.current,
                onSpeechStart: () => {
                    console.log("VAD: Speech Start");
                    setIsListeningForSpeech(true);
                    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
                },
                onSpeechEnd: (audio) => {
                    console.log("VAD: Speech End");
                    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
                    setIsListeningForSpeech(false);
                    setIsProcessing(true);

                    const audioBlob = createBlobFromFloat32Array(audio, audioContextRef.current.sampleRate);
                    if (audioBlob.size > 1000) {
                        console.log("VAD: Sending audio blob:", audioBlob.size, "bytes");
                        sendAudio(audioBlob);
                    } else {
                        console.log("VAD: Detected silence/short audio, not sending.");
                        setIsProcessing(false);
                        if (isConversationActive) {
                            console.log("VAD: Restarting listening after short audio.");
                            setTimeout(startVad, 100);
                        }
                    }
                },
                positiveSpeechThreshold: 0.6,
                negativeSpeechThreshold: 0.45,
                minSilenceFrames: 5, // Adjust based on how quickly you want it to detect end of speech
                redemptionFrames: 3,
                assetPath: '/vad-models'
            });
            vadRef.current = newVad;
            newVad.start();
            console.log("VAD started successfully.");
        } catch (error) {
            console.error('Error starting VAD:', error);
            alert(`Could not start microphone or VAD: ${error.message}`);
            stopConversation();
        }
    }, [isProcessing, isConversationActive]);

    const stopVad = useCallback(() => {
        console.log("Attempting to stop VAD...");
        if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
        if (vadRef.current) {
            vadRef.current.destroy();
            vadRef.current = null;
            console.log("VAD destroyed.");
        }
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
            console.log("Mic stream stopped.");
        }
        if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
            audioContextRef.current.close().then(() => console.log("AudioContext closed."));
            audioContextRef.current = null;
        }
    }, []);

    // --- Conversation Control ---
    const startConversation = () => {
        console.log("Start Conversation button clicked.");
        if (!isConversationActive) {
            setIsConversationActive(true);
        }
    };

    const stopConversation = () => {
        console.log("Stop Conversation button clicked.");
        setIsConversationActive(false);
        setIsProcessing(false);
    };

    // --- API Calls & Audio Playback ---
    const loadHistory = useCallback(async () => {
        // Guard against running if API_URL isn't set
        if (!API_URL) {
            console.error("VITE_API_URL is not defined. Cannot load history.");
            setMessages([{ type: 'assistant', text: 'Configuration error: API URL not set.', timestamp: new Date() }]);
            return;
        }
        console.log("Loading history from:", API_URL);
        try {
            const token = await getAccessTokenSilently({
                authorizationParams: {
                    audience: import.meta.env.VITE_AUTH0_AUDIENCE,
                    scope: 'read:current_user',
                }
            });
            const response = await fetch(`${API_URL}/api/history`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                 const errorText = await response.text();
                throw new Error(`History fetch failed: ${response.status} - ${errorText}`);
            }
            const data = await response.json();
            console.log("History loaded:", data.messages?.length || 0, "messages");
            setMessages(data.messages || []);
        } catch (error) {
            console.error('Error loading history:', error);
             setMessages([{ type: 'assistant', text: `Failed to load history: ${error.message}`, timestamp: new Date() }]);
        }
    }, [getAccessTokenSilently]);

    const sendAudio = async (audioBlob) => {
        // Guard against running if API_URL isn't set
        if (!API_URL) {
            console.error("VITE_API_URL is not defined. Cannot send audio.");
             setMessages(prev => [...prev, { type: 'assistant', text: 'Configuration error: API URL not set.', timestamp: new Date() }]);
             setIsProcessing(false); // Reset state
             // Attempt to restart VAD if conversation is active
             if (isConversationActive) setTimeout(startVad, 300);
            return;
        }
        console.log("Sending audio to:", API_URL);
        stopVad(); // Ensure VAD stops before sending
        setIsProcessing(true);
        setIsListeningForSpeech(false);
        try {
            console.log("1. Getting token for sendAudio...");
            const token = await getAccessTokenSilently({
                authorizationParams: {
                    audience: import.meta.env.VITE_AUTH0_AUDIENCE,
                    scope: 'openid profile email' // Ensure backend allows this scope for this endpoint if needed
                }
            });
            const formData = new FormData();
            formData.append('audio', audioBlob, 'speech.wav');
            console.log("2. Sending audio POST to backend...");
            const response = await fetch(`${API_URL}/api/process-audio`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });
            console.log("3. Backend response status:", response.status);
            if (!response.ok) {
                const errorText = await response.text();
                console.error("Backend error response:", errorText);
                 try { const errorData = JSON.parse(errorText); throw new Error(errorData.detail || `Backend error: ${response.status}`); }
                 catch(e) { throw new Error(`Backend error: ${response.status} - ${errorText}`); }
            }
            const data = await response.json();
            console.log("4. Backend response data:", data);
            setMessages(prev => [
                ...prev,
                { type: 'user', text: data.transcription || "[No transcription]", emotion: data.emotion, timestamp: new Date() },
                { type: 'assistant', text: data.response || "[No response]", emotion: data.emotion, timestamp: new Date() }
            ]);
            setEmotion(data.emotion || 'neutral');
            if (data.audio) {
                console.log("5. Playing response audio...");
                await playAudio(data.audio);
                console.log("6. Response audio finished playing.");
            } else {
                console.log("5. No response audio to play.");
            }
        } catch (error) {
            console.error('Error sending audio or playing response:', error);
            setMessages(prev => [...prev, { type: 'assistant', text: `Sorry, an error occurred: ${error.message}`, timestamp: new Date() }]);
        } finally {
            console.log("7. SendAudio finished. Resetting processing state.");
            setIsProcessing(false);
            if (isConversationActive) {
                console.log("8. Conversation active, restarting VAD listening...");
                setTimeout(startVad, 300);
            } else {
                console.log("8. Conversation stopped, VAD remains off.");
            }
        }
    };

    const playAudio = (audioBase64) => {
        return new Promise((resolve, reject) => {
            // ... (playAudio function remains the same)
             if (!audioBase64) { console.warn("playAudio called with empty data."); resolve(); return; }
             try {
                const audio = new Audio(`data:audio/mp3;base64,${audioBase64}`);
                audio.onended = () => { console.log("Audio playback finished."); resolve(); };
                audio.onerror = (e) => { console.error("Error playing audio:", e); reject(new Error("Failed to play audio")); };
                audio.play().catch(error => { console.error("Error starting audio playback:", error); reject(new Error(`Playback failed: ${error.message}`)); });
             } catch (error) { console.error("Error creating Audio object:", error); reject(error); }
        });
    };

    // --- Helper Function: Float32Array to WAV Blob ---
    function createBlobFromFloat32Array(audioData, sampleRate) {
        // ... (createBlobFromFloat32Array function remains the same)
        const bytesPerSample=2; const numChannels=1; const numSamples=audioData.length; const buffer=new ArrayBuffer(44+numSamples*bytesPerSample); const view=new DataView(buffer); writeString(view,0,'RIFF'); view.setUint32(4,36+numSamples*bytesPerSample,true); writeString(view,8,'WAVE'); writeString(view,12,'fmt '); view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,numChannels,true); view.setUint32(24,sampleRate,true); view.setUint32(28,sampleRate*numChannels*bytesPerSample,true); view.setUint16(32,numChannels*bytesPerSample,true); view.setUint16(34,bytesPerSample*8,true); writeString(view,36,'data'); view.setUint32(40,numSamples*bytesPerSample,true); let offset=44; for(let i=0;i<numSamples;i++,offset+=bytesPerSample){const sample=Math.max(-1,Math.min(1,audioData[i])); view.setInt16(offset,sample<0?sample*0x8000:sample*0x7FFF,true);} return new Blob([view],{type:'audio/wav'});
    }

    function writeString(view, offset, string) {
        // ... (writeString function remains the same)
         for(let i=0;i<string.length;i++){view.setUint8(offset+i,string.charCodeAt(i));}
    }

    // --- Logout ---
    const handleLogout = () => {
        // ... (handleLogout function remains the same)
        stopConversation(); logout({ logoutParams: { returnTo: window.location.origin } });
    };

    // --- Effects ---
    useEffect(() => {
        // Effect to manage VAD lifecycle
        if (isConversationActive) {
            if (!isProcessing) {
                startVad();
            } else {
                 console.log("useEffect: VAD start skipped, currently processing.");
            }
        } else {
            stopVad(); // Cleanup when conversation stops
        }
        // Cleanup function for when the component unmounts OR dependencies change causing stop
        return () => {
             console.log("useEffect [VAD Lifecycle]: Cleanup.");
            stopVad();
        };
    }, [isConversationActive, isProcessing, startVad, stopVad]); // Dependencies

    // **** THIS IS THE FIX for "Login required" error ****
    useEffect(() => {
        // Effect specifically for loading history AFTER authentication is confirmed
        if (!isLoading && isAuthenticated) {
            console.log("Auth is ready and authenticated, loading history...");
            loadHistory();
        } else if (!isLoading && !isAuthenticated) {
            console.log("Auth is ready but user is not authenticated, skipping history load.");
             setMessages([]); // Clear messages if user logs out
        } else {
             console.log("Auth is still loading...");
        }
    }, [isLoading, isAuthenticated, loadHistory]); // Dependencies: run when auth state changes


    // Effect for scrolling messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]); // Scroll when messages array changes


    // --- Render ---
    return (
        <div className="chat-container">
            <div className="chat-header">
                <div className="header-left">
                    <div className="user-avatar">
                        {user?.picture ? ( <img src={user.picture} alt={user.name} /> ) : ( user?.name?.[0] || 'U' )}
                    </div>
                    <div>
                        <h1>AI Companion</h1>
                        <p>{user?.name || user?.email || 'User'}</p>
                    </div>
                </div>
                <button onClick={handleLogout} className="logout-btn" title="Log Out"><LogOut size={20} /></button>
            </div>

            <div className="chat-content">
                <div className="emotion-display">
                    <p>Current Emotion</p>
                    <div className="emotion-badge" data-emotion={emotion}>{emotion}</div>
                </div>
                <div className="messages-container">
                    {messages.map((msg, idx) => (
                        <div key={idx} className={`message ${msg.type}`}>
                            <div className="message-bubble">
                                <p>{msg.text}</p>
                                <span className="timestamp">{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                            </div>
                        </div>
                    ))}
                    {/* Element to scroll to */}
                    <div ref={messagesEndRef} />
                </div>
            </div>

            <div className="chat-footer">
                {isConversationActive && isListeningForSpeech && !isProcessing && (
                    <div className="voice-visualizer">
                        {[1, 2, 3, 4, 5].map(i => <div key={i} className="bar" style={{ '--delay': `${i * 0.1}s` }} />)}
                    </div>
                )}
                <p className="recording-text">
                    {isConversationActive
                        ? (isProcessing ? 'Processing...' : (isListeningForSpeech ? 'Listening...' : 'Waiting for speech...'))
                        : 'Click Start to talk'}
                </p>
                <button
                    onClick={isConversationActive ? stopConversation : startConversation}
                    className={`record-btn ${isConversationActive ? (isProcessing ? 'processing' : 'recording') : ''}`}
                    // Disable button if Auth0 is loading OR if processing during active convo
                    disabled={isLoading || (isProcessing && isConversationActive)}
                    title={isConversationActive ? 'Stop Conversation' : 'Start Conversation'}
                >
                    {isConversationActive ? <Square size={20} /> : <Mic size={20} />}
                    {isConversationActive ? 'Stop' : 'Start'}
                </button>
            </div>
        </div>
    );
}