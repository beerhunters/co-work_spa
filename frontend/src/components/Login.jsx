// components/Login.jsx
import React from 'react';
import {
  Center,
  Container,
  Card,
  CardBody,
  Box,
  VStack,
  Input,
  Button,
  Heading,
  Text,
  Icon,
  Spinner,
  useColorModeValue,
  FormControl,
  FormErrorMessage,
} from '@chakra-ui/react';
import { FiUsers } from 'react-icons/fi';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { loginSchema } from '../utils/validationSchemas';
import { styles, animations } from '../styles/styles';

const Login = ({ login, setLogin, password, setPassword, handleLogin, isLoading }) => {
  // Инициализация react-hook-form с Zod валидацией
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setValue,
  } = useForm({
    resolver: zodResolver(loginSchema),
    mode: 'onBlur', // Валидация при потере фокуса
    defaultValues: {
      login: login || '',
      password: password || '',
    },
  });

  // Синхронизация с внешним state (для совместимости с существующим кодом)
  React.useEffect(() => {
    if (login !== undefined) {
      setValue('login', login);
    }
  }, [login, setValue]);

  React.useEffect(() => {
    if (password !== undefined) {
      setValue('password', password);
    }
  }, [password, setValue]);

  // Обработчик отправки формы с валидацией
  const onSubmit = (data) => {
    // Синхронизируем с внешним state
    if (setLogin) setLogin(data.login);
    if (setPassword) setPassword(data.password);

    // Вызываем оригинальный handleLogin
    handleLogin();
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !isLoading && !isSubmitting) {
      handleSubmit(onSubmit)();
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
            <form onSubmit={handleSubmit(onSubmit)}>
              <VStack spacing={5}>
                <FormControl isInvalid={!!errors.login}>
                  <Input
                    size="lg"
                    placeholder="Логин"
                    {...register('login', {
                      onChange: (e) => setLogin && setLogin(e.target.value),
                    })}
                    onKeyPress={handleKeyPress}
                    isDisabled={isLoading || isSubmitting}
                    borderRadius="lg"
                    _focus={{
                      borderColor: styles.login.inputFocusBorder,
                      boxShadow: `0 0 0 1px ${styles.login.inputFocusBorder}`,
                    }}
                  />
                  <FormErrorMessage>
                    {errors.login?.message}
                  </FormErrorMessage>
                </FormControl>

                <FormControl isInvalid={!!errors.password}>
                  <Input
                    size="lg"
                    type="password"
                    placeholder="Пароль"
                    {...register('password', {
                      onChange: (e) => setPassword && setPassword(e.target.value),
                    })}
                    onKeyPress={handleKeyPress}
                    isDisabled={isLoading || isSubmitting}
                    borderRadius="lg"
                    _focus={{
                      borderColor: styles.login.inputFocusBorder,
                      boxShadow: `0 0 0 1px ${styles.login.inputFocusBorder}`,
                    }}
                  />
                  <FormErrorMessage>
                    {errors.password?.message}
                  </FormErrorMessage>
                </FormControl>

                <Button
                  type="submit"
                  size="lg"
                  bgGradient={styles.login.buttonGradient}
                  color="white"
                  w="full"
                  isLoading={isLoading || isSubmitting}
                  loadingText="Вход..."
                  borderRadius="lg"
                  _hover={{
                    bgGradient: styles.login.buttonHoverGradient,
                    ...animations.hoverButton,
                  }}
                  transition={animations.transition}
                >
                  Войти в систему
                </Button>
              </VStack>
            </form>
          </CardBody>
        </Card>
      </Container>
    </Center>
  );
};

export default Login;