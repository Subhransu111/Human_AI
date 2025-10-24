import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { Mic, LogOut } from 'lucide-react'; // Removed Square
// Corrected import path
import '../styles/Chatpage.css';

// Ensure this is correctly set in your Vercel frontend project's environment variables
const API_URL = import.meta.env.VITE_API_URL;

export default function ChatPage() {
    // --- State and Refs ---
    const { user, logout, getAccessTokenSilently, isLoading, isAuthenticated } = useAuth0();
    const [messages, setMessages] = useState([]);
    const [emotion, setEmotion] = useState('neutral');
    const [recording, setRecording] = useState(false); // Back to manual recording state
    const [isProcessing, setIsProcessing] = useState(false); // Keep track of backend processing
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);
    const messagesEndRef = useRef(null); // Ref for scrolling

    // --- Original Recording Logic ---
    const startRecording = async () => {
        if (recording || isProcessing) return; // Prevent starting if already recording or processing
        console.log("Start Recording clicked");
        setIsProcessing(true); // Indicate activity starts
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            // You might need to specify a MIME type supported by AssemblyAI if 'audio/wav' isn't default
            // Common options: 'audio/webm', 'audio/ogg'
            const options = { mimeType: 'audio/webm;codecs=opus' }; // Example using webm/opus
             try {
                 mediaRecorderRef.current = new MediaRecorder(stream, options);
             } catch (e) {
                 console.warn("Specified mimeType not supported, trying default:", e);
                 mediaRecorderRef.current = new MediaRecorder(stream); // Fallback to browser default
             }

            audioChunksRef.current = [];

            mediaRecorderRef.current.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);
                }
            };

            mediaRecorderRef.current.onstop = () => {
                console.log("Recording stopped, processing chunks.");
                // Use the determined mimeType or a fallback
                const mimeType = mediaRecorderRef.current?.mimeType || 'audio/webm';
                const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
                console.log("Audio Blob created:", audioBlob.size, "bytes, type:", audioBlob.type);
                if (audioBlob.size > 1000) { // Send only if meaningful audio
                    sendAudio(audioBlob); // sendAudio will set isProcessing to false in finally
                } else {
                     console.log("Audio blob too small, likely silence. Not sending.");
                     setIsProcessing(false); // Reset processing if not sending
                     setRecording(false); // Also reset recording state
                }
                // Clean up stream tracks
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorderRef.current.start();
            setRecording(true);
            setIsProcessing(false); // Recording started, no longer in the initial "processing" phase
            console.log("Recording started");

        } catch (error) {
            console.error('Error starting recording:', error);
            alert(`Could not start microphone: ${error.message}`);
            setIsProcessing(false); // Reset processing on error
        }
    };

    const stopRecording = () => {
        console.log("Stop Recording clicked");
        if (mediaRecorderRef.current && recording) {
            mediaRecorderRef.current.stop(); // This will trigger the onstop handler
            setRecording(false);
            // Don't set isProcessing false here, onstop->sendAudio handles it
        } else {
             console.log("Stop clicked but not recording or recorder not ready.");
        }
    };

    // --- API Calls & Audio Playback ---
    const loadHistory = useCallback(async () => {
        if (!API_URL) { console.error("API_URL missing"); return; }
        console.log("Loading history...");
        try {
            const token = await getAccessTokenSilently({
                authorizationParams: {
                    audience: import.meta.env.VITE_AUTH0_AUDIENCE,
                    scope: 'read:current_user openid profile email', // Ensure all needed scopes are here or in main.jsx
                }
            });
            const response = await fetch(`${API_URL}/api/history`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) { throw new Error(`History fetch failed: ${response.status}`); }
            const data = await response.json();
            console.log("History loaded:", data.messages?.length || 0);
            setMessages(data.messages || []);
        } catch (error) {
            console.error('Error loading history:', error);
            setMessages([{ type: 'assistant', text: `Failed to load history: ${error.message}`, timestamp: new Date() }]);
        }
    }, [getAccessTokenSilently]); // Keep dependency

    const sendAudio = async (audioBlob) => {
        if (!API_URL) { console.error("API_URL missing"); return; }
        console.log("Sending audio...");
        setIsProcessing(true); // Set processing true while sending/receiving
        setRecording(false); // Ensure recording state is false

        try {
            console.log("1. Getting token for sendAudio...");
            const token = await getAccessTokenSilently({
                authorizationParams: {
                    audience: import.meta.env.VITE_AUTH0_AUDIENCE,
                    scope: 'openid profile email' // Scopes needed for this specific endpoint
                }
            });
            const formData = new FormData();
            // Send with a filename and the correct type
            const filename = `recording.${audioBlob.type.split('/')[1] || 'webm'}`;
            formData.append('audio', audioBlob, filename);

            console.log("2. Sending audio POST to backend...");
            const response = await fetch(`${API_URL}/api/process-audio`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });
            console.log("3. Backend response status:", response.status);
            if (!response.ok) { /* ... (error handling from previous code) ... */
                 const errorText = await response.text(); console.error("Backend error response:", errorText);
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
            setIsProcessing(false); // Reset processing state here
             setRecording(false); // Ensure recording state is false
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

    // --- Helper Functions (Not needed for VAD, keep if used elsewhere) ---
    // Remove createBlobFromFloat32Array and writeString if ONLY used for VAD

    // --- Logout ---
    const handleLogout = () => {
        // Stop recording if active before logging out
        if (mediaRecorderRef.current && recording) {
             mediaRecorderRef.current.stop();
        }
        setRecording(false);
        setIsProcessing(false);
        logout({ logoutParams: { returnTo: window.location.origin } });
    };

    // --- Effects ---
    useEffect(() => {
        // Load history only when authenticated and not loading
        if (!isLoading && isAuthenticated) {
            console.log("Auth is ready and authenticated, loading history...");
            loadHistory();
        } else if (!isLoading && !isAuthenticated) {
            console.log("Auth is ready but user not authenticated, skipping history load.");
            setMessages([]);
        } else {
             console.log("Auth is still loading...");
        }
    }, [isLoading, isAuthenticated, loadHistory]); // Correct dependencies

    useEffect(() => {
        // Scroll to bottom when messages change
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

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
                    <div ref={messagesEndRef} /> {/* Scroll target */}
                </div>
            </div>

            <div className="chat-footer">
                {/* Remove VAD visualizer */}
                <p className="recording-text">
                    {isProcessing ? 'Processing...' : (recording ? 'Recording... Speak naturally' : 'Click Start to talk')}
                </p>
                <button
                    onClick={recording ? stopRecording : startRecording}
                    className={`record-btn ${recording ? 'recording' : ''}`}
                    disabled={isLoading || isProcessing} // Disable if Auth0 loading or backend processing
                    title={recording ? 'Stop Recording' : 'Start Recording'}
                >
                    <Mic size={20} /> {/* Always show Mic icon */}
                    {recording ? 'Stop' : 'Start'}
                </button>
            </div>
        </div>
    );
}