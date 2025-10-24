import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { Mic, LogOut, Square } from 'lucide-react'; // Added Square icon
import * as vad from "@ricky0123/vad-web"; // VAD library
import '../styles/Chatpage.css'; 

const API_URL = import.meta.env.VITE_API_URL; // Should be set in Vercel

export default function ChatPage() {
    const { user, logout, getAccessTokenSilently } = useAuth0();
    const [messages, setMessages] = useState([]);
    const [emotion, setEmotion] = useState('neutral');
    const [isConversationActive, setIsConversationActive] = useState(false); // NEW: Track conversation state
    const [isListeningForSpeech, setIsListeningForSpeech] = useState(false); // NEW: UI feedback
    const [isProcessing, setIsProcessing] = useState(false); // NEW: Track if sending/receiving
    const vadRef = useRef(null);
    const streamRef = useRef(null);
    const audioContextRef = useRef(null);
    const silenceTimerRef = useRef(null); // Timer for simple VAD fallback

    // --- VAD Initialization and Control ---
    const startVad = useCallback(async () => {
        // Prevent starting if already active or processing
        if (vadRef.current || isProcessing) return;

        console.log("Attempting to start VAD...");
        setIsListeningForSpeech(true);

        try {
            // Use AudioContext for better control
             if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
                audioContextRef.current = new AudioContext();
                await audioContextRef.current.resume(); // Ensure context is running
             }

            // Get microphone stream only if not already available
             if (!streamRef.current || streamRef.current.getAudioTracks().every(t => t.readyState === 'ended')) {
                streamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true });
             }


            const newVad = await vad.MicVAD.new({
                audioContext: audioContextRef.current,
                stream: streamRef.current,
                // --- VAD Event Handlers ---
                onSpeechStart: () => {
                    console.log("VAD: Speech Start");
                    setIsListeningForSpeech(true); // Ensure UI shows listening
                    // Clear simple silence timer if VAD detects speech
                    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
                },
                onSpeechEnd: (audio) => {
                    console.log("VAD: Speech End");
                    // Stop the simple silence timer as VAD handled it
                     if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);

                    setIsListeningForSpeech(false); // Speech ended, not actively listening for *more* speech in this segment
                    setIsProcessing(true); // Start processing phase

                    // Convert Float32Array to Blob (Needs proper WAV conversion)
                    const audioBlob = createBlobFromFloat32Array(audio, audioContextRef.current.sampleRate);

                    if (audioBlob.size > 1000) { // Send only if audio has meaningful size
                        console.log("VAD: Sending audio blob:", audioBlob);
                        sendAudio(audioBlob);
                    } else {
                        console.log("VAD: Detected silence/short audio, not sending.");
                        setIsProcessing(false); // Reset processing state
                        // If conversation still active, immediately try listening again
                        if (isConversationActive) {
                             console.log("VAD: Restarting listening after short audio.");
                            setTimeout(startVad, 100); // Small delay
                        }
                    }
                },
                 // --- Simple Silence Detection Fallback ---
                 // Start a timer when speech starts; if it completes without VAD onSpeechEnd, force send
                 // VAD library's onSpeechEnd is generally preferred
                 // onFrameProcessed: (probs) => {
                 //     if (probs.isSpeech > 0.6 && !silenceTimerRef.current) { // Threshold may need tuning
                 //         console.log("Silence Timer: Speech detected, starting timer.");
                 //         clearTimeout(silenceTimerRef.current); // Clear previous timer
                 //         silenceTimerRef.current = setTimeout(() => {
                 //             console.log("Silence Timer: Silence timeout reached, forcing send.");
                 //             if (vadRef.current) {
                 //                 // This assumes vadRef.current has a way to get current audio buffer,
                 //                 // which @ricky0123/vad-web might not directly expose easily.
                 //                 // You might need to manage audio chunks separately if using this timer method.
                 //                 // For now, relying on onSpeechEnd is better.
                 //                 // vadRef.current.pause(); // Example action
                 //                 // const audioData = /* get buffered audio */;
                 //                 // const blob = createBlobFromFloat32Array(audioData, audioContextRef.current.sampleRate);
                 //                 // sendAudio(blob);
                 //                 console.warn("Simple silence timer fired - relying on onSpeechEnd is preferred.");
                 //                 // If forced send, make sure to handle state transitions (setIsProcessing, etc.)
                 //             }
                 //             silenceTimerRef.current = null;
                 //         }, 2000); // Send after 2 seconds of silence
                 //     } else if (probs.isSpeech < 0.4) {
                 //         // Optionally reset timer if definitely not speech, but might clip ends
                 //     }
                 // },


                // --- VAD Configuration ---
                // You'll need to tune these based on testing
                positiveSpeechThreshold: 0.6,    // Confidence level to start detecting speech
                negativeSpeechThreshold: 0.45,   // Confidence level to stop detecting speech
                minSilenceFrames: 5,           // How many consecutive non-speech frames end speech
                redemptionFrames: 3,           // Allow a few non-speech frames within speech
                // preSpeechPadFrames: 1,      // Add a bit of audio before speech starts
            });
            vadRef.current = newVad;
            newVad.start();
            console.log("VAD started successfully.");

        } catch (error) {
            console.error('Error starting VAD:', error);
            alert(`Could not start microphone or VAD: ${error.message}`);
            stopConversation(); // Clean up if VAD fails to start
        }
    }, [isProcessing, isConversationActive]); // Re-run checks if processing state changes

    const stopVad = useCallback(() => {
        console.log("Attempting to stop VAD...");
         if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current); // Clear timer on stop
         silenceTimerRef.current = null;

        if (vadRef.current) {
            vadRef.current.destroy(); // Use destroy instead of pause/stop for cleanup
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
         // Don't set isListeningForSpeech here, let the calling context decide UI
    }, []);

    // --- Conversation Control ---
    const startConversation = () => {
        console.log("Start Conversation button clicked.");
        if (!isConversationActive) {
            setIsConversationActive(true);
            // VAD will be started by the useEffect hook
        }
    };

    const stopConversation = () => {
        console.log("Stop Conversation button clicked.");
        setIsConversationActive(false);
        setIsProcessing(false); // Ensure processing stops
        // VAD stopping is handled by the useEffect cleanup
    };

    // --- Effects ---
    useEffect(() => {
        // Effect to manage VAD lifecycle based on conversation state
        if (isConversationActive) {
             console.log("useEffect: Conversation active, ensuring VAD starts.");
             // Don't start VAD if backend is currently processing
             if(!isProcessing) {
                startVad();
             }
        } else {
            console.log("useEffect: Conversation inactive, ensuring VAD stops.");
            stopVad(); // Cleanup when conversation stops
        }

        // Cleanup function for when the component unmounts
        return () => {
             console.log("useEffect: Cleanup on unmount.");
             stopVad();
        };
    }, [isConversationActive, isProcessing, startVad, stopVad]); // Dependencies

    useEffect(() => {
        // Initial history load - DO NOT REMOVE
        loadHistory();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []); // Run only once on mount

    // --- API Calls & Audio Playback ---
    const loadHistory = useCallback(async () => {
        console.log("Loading history...");
        try {
            const token = await getAccessTokenSilently({
                authorizationParams: {
                    audience: import.meta.env.VITE_AUTH0_AUDIENCE,
                    scope: 'read:current_user', // Ensure this scope exists in Auth0 API Permissions
                }
            });

            const response = await fetch(`${API_URL}/api/history`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                throw new Error(`History fetch failed: ${response.status}`);
            }

            const data = await response.json();
            console.log("History loaded:", data.messages?.length || 0, "messages");
            setMessages(data.messages || []);
        } catch (error) {
            console.error('Error loading history:', error);
            // Maybe show an error message to the user
        }
    }, [getAccessTokenSilently]); // Added dependency

    const sendAudio = async (audioBlob) => {
        console.log("Sending audio...");
        // Ensure VAD is stopped before proceeding
        stopVad();
        setIsProcessing(true); // Explicitly set processing state
        setIsListeningForSpeech(false); // Not listening while processing

        try {
            console.log("1. Getting token for sendAudio...");
            const token = await getAccessTokenSilently({
                authorizationParams: {
                    audience: import.meta.env.VITE_AUTH0_AUDIENCE,
                    // Different scope might be needed for process-audio endpoint?
                    scope: 'openid profile email'
                }
            });

            const formData = new FormData();
            // IMPORTANT: Use WAV format if createBlobFromFloat32Array creates WAV
            formData.append('audio', audioBlob, 'speech.wav');

            console.log("2. Sending audio POST to backend...");
            const response = await fetch(`${API_URL}/api/process-audio`, {
                method: 'POST',
                headers: {
                    // Correct Authorization header - DO NOT REMOVE
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            });
            console.log("3. Backend response status:", response.status);

            if (!response.ok) {
                const errorText = await response.text(); // Get text for better debugging
                console.error("Backend error response:", errorText);
                try {
                    const errorData = JSON.parse(errorText); // Try parsing as JSON
                     throw new Error(errorData.detail || `Backend error: ${response.status}`);
                } catch(e) {
                     throw new Error(`Backend error: ${response.status} - ${errorText}`);
                }
            }

            const data = await response.json();
            console.log("4. Backend response data:", data);

            // Update UI state
            setMessages(prev => [
                ...prev,
                { type: 'user', text: data.transcription || "[No transcription]", emotion: data.emotion, timestamp: new Date() },
                { type: 'assistant', text: data.response || "[No response]", emotion: data.emotion, timestamp: new Date() }
            ]);
            setEmotion(data.emotion || 'neutral');

            // Play response audio if available
            if (data.audio) {
                console.log("5. Playing response audio...");
                await playAudio(data.audio);
                console.log("6. Response audio finished playing.");
            } else {
                 console.log("5. No response audio to play.");
            }

        } catch (error) {
            console.error('Error sending audio or playing response:', error);
            // Display error to user?
             setMessages(prev => [...prev, { type: 'assistant', text: `Sorry, an error occurred: ${error.message}`, timestamp: new Date() }]);

        } finally {
            console.log("7. SendAudio finished. Resetting processing state.");
            setIsProcessing(false); // Reset processing state

            // IMPORTANT: Restart VAD only if the conversation should still be active
            if (isConversationActive) {
                console.log("8. Conversation active, restarting VAD listening...");
                // Short delay before restarting VAD
                setTimeout(startVad, 300);
            } else {
                 console.log("8. Conversation stopped, VAD remains off.");
            }
        }
    };

    // Make playAudio return a Promise
    const playAudio = (audioBase64) => {
        return new Promise((resolve, reject) => {
            if (!audioBase64) {
                 console.warn("playAudio called with empty data.");
                 resolve(); // Resolve immediately if no audio
                 return;
            }
            try {
                const audio = new Audio(`data:audio/mp3;base64,${audioBase64}`);
                audio.onended = () => {
                     console.log("Audio playback finished.");
                     resolve();
                };
                audio.onerror = (e) => {
                     console.error("Error playing audio:", e);
                     reject(new Error("Failed to play audio"));
                };
                audio.play().catch(error => {
                     console.error("Error starting audio playback:", error);
                     // Common issue: Browser requires user interaction for audio.
                     // The click to start conversation should cover this.
                     reject(new Error(`Playback failed: ${error.message}`));
                });
            } catch (error) {
                 console.error("Error creating Audio object:", error);
                 reject(error);
            }

        });
    };

    // --- Helper Function: Float32Array to WAV Blob ---
    // Basic implementation - Robust library might be better
    function createBlobFromFloat32Array(audioData, sampleRate) {
        const bytesPerSample = 2; // 16-bit PCM
        const numChannels = 1;
        const numSamples = audioData.length;

        const buffer = new ArrayBuffer(44 + numSamples * bytesPerSample);
        const view = new DataView(buffer);

        // RIFF header
        writeString(view, 0, 'RIFF');
        view.setUint32(4, 36 + numSamples * bytesPerSample, true);
        writeString(view, 8, 'WAVE');
        // fmt chunk
        writeString(view, 12, 'fmt ');
        view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
        view.setUint16(20, 1, true); // AudioFormat (1 for PCM)
        view.setUint16(22, numChannels, true);
        view.setUint32(24, sampleRate, true);
        view.setUint32(28, sampleRate * numChannels * bytesPerSample, true); // ByteRate
        view.setUint16(32, numChannels * bytesPerSample, true); // BlockAlign
        view.setUint16(34, bytesPerSample * 8, true); // BitsPerSample
        // data chunk
        writeString(view, 36, 'data');
        view.setUint32(40, numSamples * bytesPerSample, true);

        // Write PCM samples
        let offset = 44;
        for (let i = 0; i < numSamples; i++, offset += bytesPerSample) {
            const sample = Math.max(-1, Math.min(1, audioData[i])); // Clamp
            view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true); // Convert to 16-bit PCM
        }

        return new Blob([view], { type: 'audio/wav' });
    }

    function writeString(view, offset, string) {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    }


    // --- Logout ---
    const handleLogout = () => {
        stopConversation(); // Stop listening before logging out
        logout({
            logoutParams: {
                returnTo: window.location.origin
            }
        });
    };

    // --- Render ---
    return (
        <div className="chat-container">
            <div className="chat-header">
                {/* ... existing header content ... */}
                 <button onClick={handleLogout} className="logout-btn"><LogOut size={20} /></button>
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
                     {/* Add a ref for scrolling */}
                     <div ref={(el) => el?.scrollIntoView({ behavior: 'smooth' })} />
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
                    disabled={isProcessing && isConversationActive} // Disable stop button while processing?
                >
                    {isConversationActive ? <Square size={20} /> : <Mic size={20} />}
                    {isConversationActive ? 'Stop' : 'Start'}
                </button>
            </div>
        </div>
    );
}