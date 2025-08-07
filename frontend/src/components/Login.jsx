// components/Login.jsx
import React from 'react';
import { Center, Container, Card, CardBody, Box, VStack, Input, Button, Heading, Text, Icon, Spinner, useColorModeValue } from '@chakra-ui/react';
import { FiUsers } from 'react-icons/fi';
import { styles, animations } from '../styles/styles';

const Login = ({ login, setLogin, password, setPassword, handleLogin, isLoading }) => {
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !isLoading) {
      handleLogin();
    }
  };

  const bgGradient = useColorModeValue(
    styles.login.gradient,
    'linear(to-br, gray.900, purple.900)'
  );

  // Если просто показываем загрузку
  if (isLoading && !login && !setLogin) {
    return (
      <Center h="100vh" bg="gray.50">
        <VStack spacing={4}>
          <Spinner size="xl" color="purple.500" thickness="4px" />
          <Text color="gray.600">Загрузка...</Text>
        </VStack>
      </Center>
    );
  }

  return (
    <Center minH="100vh" bgGradient={bgGradient}>
      <Container maxW="lg" py={12}>
        <Card
          maxW="md"
          mx="auto"
          boxShadow="2xl"
          borderRadius="xl"
          overflow="hidden"
        >
          <Box
            bgGradient={styles.login.cardGradient}
            p={6}
            color="white"
          >
            <VStack spacing={2}>
              <Icon as={FiUsers} boxSize={12} />
              <Heading size="lg">Панель администратора</Heading>
              <Text fontSize="sm" opacity={0.9}>Войдите в систему управления</Text>
            </VStack>
          </Box>
          <CardBody p={8}>
            <VStack spacing={5}>
              <Input
                size="lg"
                placeholder="Логин"
                value={login}
                onChange={e => setLogin(e.target.value)}
                onKeyPress={handleKeyPress}
                isDisabled={isLoading}
                borderRadius="lg"
                _focus={{
                  borderColor: styles.login.inputFocusBorder,
                  boxShadow: `0 0 0 1px ${styles.login.inputFocusBorder}`
                }}
              />
              <Input
                size="lg"
                type="password"
                placeholder="Пароль"
                value={password}
                onChange={e => setPassword(e.target.value)}
                onKeyPress={handleKeyPress}
                isDisabled={isLoading}
                borderRadius="lg"
                _focus={{
                  borderColor: styles.login.inputFocusBorder,
                  boxShadow: `0 0 0 1px ${styles.login.inputFocusBorder}`
                }}
              />
              <Button
                size="lg"
                bgGradient={styles.login.buttonGradient}
                color="white"
                w="full"
                onClick={handleLogin}
                isLoading={isLoading}
                loadingText="Вход..."
                borderRadius="lg"
                _hover={{
                  bgGradient: styles.login.buttonHoverGradient,
                  ...animations.hoverButton
                }}
                transition={animations.transition}
              >
                Войти в систему
              </Button>
            </VStack>
          </CardBody>
        </Card>
      </Container>
    </Center>
  );
};

export default Login;