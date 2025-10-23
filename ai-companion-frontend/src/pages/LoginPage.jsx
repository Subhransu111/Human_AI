import React from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import '../styles/AuthPages.css'

export default function LoginPage() {
  const { loginWithRedirect } = useAuth0()

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <h1>AI Companion</h1>
          <p>Your emotional support AI</p>
        </div>

        <div className="auth-form">
          <button 
            onClick={() => loginWithRedirect()}
            className="submit-btn"
          >
            Login with Auth0
          </button>

          <div className="divider">or</div>

          <button 
            onClick={() => loginWithRedirect({
              screen_hint: 'signup',
            })}
            className="submit-btn secondary"
          >
            Sign Up with Auth0
          </button>
        </div>

        <div className="auth-footer">
          <p>Secure login powered by Auth0</p>
        </div>
      </div>
    </div>
  )
}