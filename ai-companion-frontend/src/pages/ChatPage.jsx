import React, { useState, useEffect, useRef } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { Mic, LogOut } from 'lucide-react'
import '../styles/Chatpage.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function ChatPage() {
  const { user, logout, getAccessTokenSilently } = useAuth0()
  const [messages, setMessages] = useState([])
  const [recording, setRecording] = useState(false)
  const [emotion, setEmotion] = useState('neutral')
  const [isListening, setIsListening] = useState(false)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])

  useEffect(() => {
    const loadHistory = async () => {
  try {
    const token = await getAccessTokenSilently({
      // FIX: Add the authorizationParams object
      authorizationParams: {
        audience: import.meta.env.VITE_AUTH0_AUDIENCE,
        scope: 'read:current_user',
      }
    })

    const response = await fetch(`${API_URL}/api/history`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })

    if (!response.ok) {
        // Throw an error to be caught by the catch block
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json()
    setMessages(data.messages || [])
  } catch (error) {
    console.error('Error loading history:', error)
    // Optional: Let the user know something went wrong
    // setMessages([{ type: 'assistant', text: 'Sorry, I couldn\'t load your history.', timestamp: new Date() }])
  }
}},[])

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const options = { mimeType: 'audio/webm' }
      const mediaRecorder = new MediaRecorder(stream, options)
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []

      mediaRecorder.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data)
      }

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        sendAudio(audioBlob)
      }

      mediaRecorder.start()
      setRecording(true)
      setIsListening(true)
    } catch (error) {
      alert('Microphone access denied')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop()
      setRecording(false)
    }
  }

  const sendAudio = async (audioBlob) => {
    try {
      console.log("1. Getting token...");
      const token = await getAccessTokenSilently({
        authorizationParams: {
            audience: import.meta.env.VITE_AUTH0_AUDIENCE,
            scope: 'openid profile email',
            }
        })

      const formData = new FormData()
      formData.append('audio', audioBlob, 'recording.webm')
      formData.append('token', token)

      console.log("2. Sending audio to backend...");
      const response = await fetch(`${API_URL}/api/process-audio`, {
        method: 'POST',
        body: formData
      })
      console.log("3. Response status:", response.status);
    
      if (!response.ok) {
      const errorData = await response.json()
      console.error("Error:", errorData)
      throw new Error(errorData.detail || 'Failed to process audio')
      }
      

      const data = await response.json()
      console.log("4. Response data:", data);

      setMessages(prev => [
        ...prev,
        { type: 'user', text: data.transcription, emotion: data.emotion, timestamp: new Date() },
        { type: 'assistant', text: data.response, emotion: data.emotion, timestamp: new Date() }
      ])

      setEmotion(data.emotion)

      if (data.audio) {
        playAudio(data.audio)
      }

      setIsListening(false)
    } catch (error) {
      console.error('Error:', error)
      setIsListening(false)
    }
  }

  const playAudio = (audioBase64) => {
    const audio = new Audio(`data:audio/mp3;base64,${audioBase64}`)
    audio.play()
  }

  const loadHistory = async () => {
    try {
      const token = await getAccessTokenSilently({
        audience: import.meta.env.VITE_AUTH0_AUDIENCE,
        scope: 'read:current_user',
      })

      const response = await fetch(`${API_URL}/api/history`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })

      const data = await response.json()
      setMessages(data.messages || [])
    } catch (error) {
      console.error('Error loading history:', error)
    }
  }

  const handleLogout = () => {
    logout({ 
      logoutParams: { 
        returnTo: window.location.origin 
      } 
    })
  }

  return (
    <div className="chat-container">
      <div className="chat-header">
        <div className="header-left">
          <div className="user-avatar">
            {user?.picture ? (
              <img src={user.picture} alt={user.name} />
            ) : (
              user?.name?.[0] || 'U'
            )}
          </div>
          <div>
            <h1>AI Companion</h1>
            <p>{user?.name || user?.email || 'User'}</p>
          </div>
        </div>
        <button onClick={handleLogout} className="logout-btn">
          <LogOut size={20} />
        </button>
      </div>

      <div className="chat-content">
        <div className="emotion-display">
          <p>Current Emotion</p>
          <div className="emotion-badge" data-emotion={emotion}>
            {emotion}
          </div>
        </div>

        <div className="messages-container">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.type}`}>
              <div className="message-bubble">
                <p>{msg.text}</p>
                <span className="timestamp">{new Date(msg.timestamp).toLocaleTimeString()}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="chat-footer">
        {isListening && (
          <div className="voice-visualizer">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="bar" style={{ '--delay': `${i * 0.1}s` }} />
            ))}
          </div>
        )}
        <p className="recording-text">
          {recording ? 'Recording... Speak naturally' : 'Click to start speaking'}
        </p>
        <button
          onClick={recording ? stopRecording : startRecording}
          className={`record-btn ${recording ? 'recording' : ''}`}
        >
          <Mic size={20} />
          {recording ? 'Stop' : 'Start'}
        </button>
      </div>
    </div>
  )
}
