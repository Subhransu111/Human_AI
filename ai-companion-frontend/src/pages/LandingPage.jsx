// src/pages/LandingPage.jsx
import React from 'react';
import { Box, Flex, Heading, Text, Button, Container, VStack, Spacer } from '@chakra-ui/react';
import { useAuth0 } from '@auth0/auth0-react'; // Import useAuth0 to handle login

function LandingPage() {
  const { loginWithRedirect } = useAuth0();

  const handleLogin = () => {
    loginWithRedirect(); // Default login
  };

  const handleSignUp = () => {
    loginWithRedirect({
      authorizationParams: {
        screen_hint: 'signup', // Tell Auth0 to show the signup screen
      }
    });
  };

  return (
    <Flex
      direction="column" // Stack elements vertically
      minHeight="100vh" // Take full viewport height
      align="center"    // Center horizontally
      justify="center"  // Center vertically
      bg="gray.50"      // Example: Light gray background
      p={8}             // Add padding around the content
    >
      <Container maxW="container.md" centerContent> {/* Limit width and center */}
        <VStack spacing={6}> {/* Stack elements vertically with spacing */}
          {/* Add a logo or icon here if you have one */}
          <Heading as="h1" size="2xl" textAlign="center" color="blue.600">
            AI Companion
          </Heading>
          <Text fontSize="xl" color="gray.600" textAlign="center">
            Your emotional support AI, ready to listen.
          </Text>
          <Flex direction={{ base: 'column', sm: 'row' }} gap={4}> {/* Stack buttons vertically on small screens, row on larger */}
            <Button colorScheme="blue" size="lg" onClick={handleLogin}>
              Login
            </Button>
            <Button variant="outline" colorScheme="blue" size="lg" onClick={handleSignUp}>
              Sign Up
            </Button>
          </Flex>
          <Text fontSize="sm" color="gray.500" mt={8}>
            Secure login powered by Auth0
          </Text>
        </VStack>
      </Container>
    </Flex>
  );
}

export default LandingPage;