// src/App.jsx
import React from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { Box, Spinner } from '@chakra-ui/react'; // Import Spinner for loading

import LandingPage from './pages/LandingPage';
import ChatPage from './pages/ChatPage'; // Assuming ChatPage is in pages folder

function App() {
  const { isAuthenticated, isLoading, error } = useAuth0();

  // Show loading spinner while Auth0 initializes
  if (isLoading) {
    return (
      <Flex minHeight="100vh" align="center" justify="center">
        <Spinner size="xl" />
      </Flex>
    );
  }

  // Show error if Auth0 fails
  if (error) {
     return <Box p={5}>Oops... {error.message}</Box>;
  }


  return (
    <Router>
      <Routes>
        {/* If logged in, '/chat' is the main page, otherwise show LandingPage */}
        <Route
          path="/"
          element={!isAuthenticated ? <LandingPage /> : <Navigate to="/chat" replace />}
        />
        {/* Protect the /chat route */}
        <Route
          path="/chat"
          element={isAuthenticated ? <ChatPage /> : <Navigate to="/" replace />}
        />
        {/* Optional: Add a catch-all route for 404s */}
        {/* <Route path="*" element={<NotFoundPage />} /> */}
      </Routes>
    </Router>
  );
}

export default App;


