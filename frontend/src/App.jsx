import React, { useState, useEffect, useRef } from 'react';
import { ChakraProvider, Box, Flex, VStack, HStack, Text, Input, Button, Heading, useToast, Badge, Icon, Avatar, Divider, Tabs, TabList, TabPanels, Tab, TabPanel, Table, Thead, Tbody, Tr, Th, Td, TableContainer, Card, CardBody, CardHeader, Stat, StatLabel, StatNumber, StatHelpText, StatArrow, IconButton, Menu, MenuButton, MenuList, MenuItem, Spinner, Center, SimpleGrid, useColorModeValue, Container, Stack, Spacer } from '@chakra-ui/react';
import { FiBell, FiUser, FiCalendar, FiTag, FiPercent, FiHelpCircle, FiSend, FiLogOut, FiHome, FiCheck, FiX, FiEye, FiEdit, FiTrash, FiMoreVertical, FiPlus, FiRefreshCw, FiUsers, FiShoppingBag, FiMessageCircle, FiTrendingUp } from 'react-icons/fi';
import axios from 'axios';
import Chart from 'chart.js/auto';

// Вспомогательная функция для получения токена из localStorage
const getAuthToken = () => localStorage.getItem('authToken');

// Настройка axios для автоматического добавления токена
axios.interceptors.request.use(
  config => {
    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  error => Promise.reject(error)
);

const Login = ({ login, setLogin, password, setPassword, handleLogin, isLoading }) => {
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !isLoading) {
      handleLogin();
    }
  };

  const bgGradient = useColorModeValue(
    'linear(to-br, blue.50, purple.50)',
    'linear(to-br, gray.900, purple.900)'
  );

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
            bgGradient="linear(to-r, blue.500, purple.600)"
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
                  borderColor: 'purple.500',
                  boxShadow: '0 0 0 1px purple.500'
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
                  borderColor: 'purple.500',
                  boxShadow: '0 0 0 1px purple.500'
                }}
              />
              <Button
                size="lg"
                bgGradient="linear(to-r, blue.500, purple.600)"
                color="white"
                w="full"
                onClick={handleLogin}
                isLoading={isLoading}
                loadingText="Вход..."
                borderRadius="lg"
                _hover={{
                  bgGradient: "linear(to-r, blue.600, purple.700)",
                  transform: 'translateY(-2px)',
                  boxShadow: 'lg',
                }}
                transition="all 0.2s"
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

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [section, setSection] = useState('dashboard');
  const [users, setUsers] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [tariffs, setTariffs] = useState([]);
  const [promocodes, setPromocodes] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [newsletters, setNewsletters] = useState([]);
  const [hasNewNotifications, setHasNewNotifications] = useState(false);
  const [dashboardStats, setDashboardStats] = useState({
    total_users: 0,
    total_bookings: 0,
    open_tickets: 0
  });
  const [lastNotificationId, setLastNotificationId] = useState(0);
  const toast = useToast();
  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);

  // Проверка валидности токена при загрузке
  useEffect(() => {
    const checkAuth = async () => {
      const token = getAuthToken();
      if (token) {
        try {
          await axios.get('http://localhost/api/verify_token', { withCredentials: true });
          setIsAuthenticated(true);
          setSection('dashboard');
          fetchData();
        } catch (error) {
          localStorage.removeItem('authToken');
          setIsAuthenticated(false);
        }
      }
      setIsCheckingAuth(false);
    };
    checkAuth();
  }, []);

  const fetchData = async () => {
    const endpoints = [
      { url: '/users', setter: setUsers },
      { url: '/bookings', setter: setBookings },
      { url: '/tariffs', setter: setTariffs },
      { url: '/promocodes', setter: setPromocodes },
      { url: '/tickets', setter: setTickets },
      { url: '/newsletters', setter: setNewsletters },
      { url: '/notifications', setter: (data) => {
        setNotifications(data);
        if (data.length > 0) {
          setLastNotificationId(Math.max(...data.map(n => n.id), 0));
        }
      }},
      { url: '/dashboard/stats', setter: setDashboardStats }
    ];

    try {
      await Promise.all(endpoints.map(async ({ url, setter }) => {
        try {
          const res = await axios.get(`http://localhost/api${url}`, { withCredentials: true });
          setter(res.data);
        } catch (error) {
          console.error(`Ошибка загрузки ${url}:`, error);
        }
      }));
    } catch (err) {
      console.error('Ошибка загрузки данных:', err);
      toast({ title: 'Ошибка', description: 'Не удалось загрузить данные', status: 'error', duration: 5000, isClosable: true });
    }
  };

  const fetchNotifications = async () => {
    try {
      const res = await axios.get(`http://localhost/api/notifications/check_new?since_id=${lastNotificationId}`, { withCredentials: true });
      if (res.data.recent_notifications && res.data.recent_notifications.length > 0) {
        const newNotifications = res.data.recent_notifications.filter(n => !n.is_read);
        if (newNotifications.length > 0) {
          setNotifications(prev => [...newNotifications, ...prev]);
          setLastNotificationId(Math.max(...res.data.recent_notifications.map(n => n.id), lastNotificationId));
          setHasNewNotifications(true);

          newNotifications.forEach(n => {
            toast({
              title: 'Новое уведомление',
              description: n.message.substring(0, 100),
              status: 'info',
              duration: 5000,
              isClosable: true,
              position: 'top-right',
            });
          });
        }
      }
    } catch (err) {
      console.error('Ошибка получения уведомлений:', err);
    }
  };

  const fetchDashboardStats = async () => {
    try {
      const res = await axios.get('http://localhost/api/dashboard/stats', { withCredentials: true });
      setDashboardStats(res.data);
    } catch (err) {
      console.error('Ошибка получения статистики:', err);
    }
  };

  const handleLogin = async () => {
    setIsLoading(true);
    try {
      const res = await axios.post('http://localhost/api/login', { login, password }, { withCredentials: true });
      localStorage.setItem('authToken', res.data.access_token);
      setIsAuthenticated(true);
      setSection('dashboard');
      fetchData();
      toast({
        title: 'Успешный вход',
        description: 'Добро пожаловать в панель администратора',
        status: 'success',
        duration: 3000,
        position: 'top-right',
      });
    } catch (error) {
      toast({
        title: 'Ошибка входа',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
        isClosable: true,
        position: 'top-right',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await axios.get('http://localhost/api/logout', { withCredentials: true });
      localStorage.removeItem('authToken');
      setIsAuthenticated(false);
      setSection('login');
      setLogin('');
      setPassword('');
      toast({
        title: 'Выход выполнен',
        description: 'До свидания!',
        status: 'info',
        duration: 3000,
        position: 'top-right',
      });
    } catch (error) {
      console.error('Ошибка выхода:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось выйти',
        status: 'error',
        duration: 5000,
        isClosable: true,
        position: 'top-right',
      });
    }
  };

  const markNotificationRead = async (notificationId, targetUrl) => {
    try {
      await axios.post(`http://localhost/api/notifications/mark_read/${notificationId}`, {}, { withCredentials: true });
      setNotifications(prev => prev.map(n => n.id === notificationId ? { ...n, is_read: true } : n));
      if (targetUrl) {
        const urlParts = targetUrl.split('/');
        if (urlParts.length >= 2) {
          setSection(urlParts[1]);
        }
      }
    } catch (error) {
      console.error('Ошибка при пометке уведомления:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось пометить уведомление как прочитанное',
        status: 'error',
        duration: 5000,
        isClosable: true,
        position: 'top-right',
      });
    }
  };

  const markAllNotificationsRead = async () => {
    try {
      await axios.post('http://localhost/api/notifications/mark_all_read', {}, { withCredentials: true });
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      setHasNewNotifications(false);
      toast({
        title: 'Успех',
        description: 'Все уведомления помечены как прочитанные',
        status: 'success',
        duration: 5000,
        isClosable: true,
        position: 'top-right',
      });
    } catch (error) {
      console.error('Ошибка при пометке всех уведомлений:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось пометить уведомления',
        status: 'error',
        duration: 5000,
        isClosable: true,
        position: 'top-right',
      });
    }
  };

  // Auto-refresh для уведомлений
  useEffect(() => {
    if (isAuthenticated) {
      const notificationInterval = setInterval(fetchNotifications, 10000);
      return () => {
        clearInterval(notificationInterval);
      };
    }
  }, [isAuthenticated, lastNotificationId]);

  // График загружается только при монтировании дашборда
  useEffect(() => {
    if (section === 'dashboard' && chartRef.current && users.length > 0 && !chartInstanceRef.current) {
      const userRegistrationCounts = users.reduce((acc, u) => {
        if (u.reg_date || u.first_join_time) {
          const date = new Date(u.reg_date || u.first_join_time);
          const day = date.getDay() === 0 ? 6 : date.getDay() - 1;
          acc[day]++;
        }
        return acc;
      }, Array(7).fill(0));

      const ctx = chartRef.current.getContext('2d');
      chartInstanceRef.current = new Chart(ctx, {
        type: 'line',
        data: {
          labels: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
          datasets: [{
            label: 'Регистрации пользователей',
            data: userRegistrationCounts,
            borderColor: 'rgb(147, 51, 234)',
            backgroundColor: 'rgba(147, 51, 234, 0.1)',
            tension: 0.4,
            borderWidth: 3,
            pointBackgroundColor: 'rgb(147, 51, 234)',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointRadius: 5,
            pointHoverRadius: 7,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: false
            },
            tooltip: {
              backgroundColor: 'rgba(0, 0, 0, 0.8)',
              padding: 12,
              cornerRadius: 8,
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              grid: {
                color: 'rgba(0, 0, 0, 0.05)',
              }
            },
            x: {
              grid: {
                display: false,
              }
            }
          }
        }
      });
    }

    return () => {
      if (section !== 'dashboard' && chartInstanceRef.current) {
        chartInstanceRef.current.destroy();
        chartInstanceRef.current = null;
      }
    };
  }, [section, users]);

  // Обновляем индикатор новых уведомлений
  useEffect(() => {
    const unreadCount = notifications.filter(n => !n.is_read).length;
    setHasNewNotifications(unreadCount > 0);
  }, [notifications]);

  const Sidebar = () => (
    <Box
      w="260px"
      bg="gray.900"
      color="white"
      minH="100vh"
      display="flex"
      flexDirection="column"
    >
      <Box p={6}>
        <VStack align="stretch" spacing={1}>
          <Flex align="center" mb={6}>
            <Icon as={FiHome} boxSize={6} color="purple.400" mr={3} />
            <Heading size="md" fontWeight="bold">
              Админ панель
            </Heading>
          </Flex>

          {[
            { icon: FiTrendingUp, label: 'Дашборд', section: 'dashboard', color: 'purple' },
            { icon: FiUser, label: 'Пользователи', section: 'users', color: 'blue' },
            { icon: FiCalendar, label: 'Бронирования', section: 'bookings', color: 'green' },
            { icon: FiTag, label: 'Тарифы', section: 'tariffs', color: 'cyan' },
            { icon: FiPercent, label: 'Промокоды', section: 'promocodes', color: 'orange' },
            { icon: FiHelpCircle, label: 'Заявки', section: 'tickets', color: 'yellow' },
            { icon: FiBell, label: 'Уведомления', section: 'notifications', color: 'pink' },
            { icon: FiSend, label: 'Рассылка', section: 'newsletters', color: 'teal' }
          ].map(({ icon: Icon, label, section: sec, color }) => (
            <Button
              key={sec}
              leftIcon={<Icon />}
              variant={section === sec ? 'solid' : 'ghost'}
              bg={section === sec ? `${color}.600` : 'transparent'}
              color={section === sec ? 'white' : 'gray.400'}
              justifyContent="flex-start"
              onClick={() => setSection(sec)}
              _hover={{
                bg: section === sec ? `${color}.700` : 'gray.800',
                color: 'white',
              }}
              borderRadius="lg"
              px={4}
              py={6}
              fontSize="md"
              transition="all 0.2s"
            >
              {label}
            </Button>
          ))}
        </VStack>
      </Box>

      <Spacer />

      <Box p={6} borderTop="1px" borderColor="gray.700">
        <Button
          leftIcon={<FiLogOut />}
          variant="ghost"
          color="red.400"
          justifyContent="flex-start"
          onClick={handleLogout}
          _hover={{
            bg: 'red.900',
            color: 'red.300',
          }}
          borderRadius="lg"
          px={4}
          py={6}
          w="full"
          fontSize="md"
          transition="all 0.2s"
        >
          Выйти из системы
        </Button>
      </Box>
    </Box>
  );

  const Navbar = () => (
    <Box
      bg="white"
      px={8}
      py={4}
      borderBottom="2px"
      borderColor="gray.100"
      boxShadow="sm"
    >
      <Flex justify="space-between" align="center">
        <Heading size="lg" color="gray.800">
          {section === 'dashboard' ? 'Дашборд' :
          section === 'users' ? 'Пользователи' :
          section === 'bookings' ? 'Бронирования' :
          section === 'tariffs' ? 'Тарифы' :
          section === 'promocodes' ? 'Промокоды' :
          section === 'tickets' ? 'Заявки' :
          section === 'notifications' ? 'Уведомления' :
          section === 'newsletters' ? 'Рассылка' : ''}
        </Heading>
        <HStack spacing={4}>
          <Menu>
            <MenuButton
              as={IconButton}
              icon={
                <Box position="relative">
                  <FiBell size={20} />
                  {hasNewNotifications && (
                    <Box
                      position="absolute"
                      top="-2px"
                      right="-2px"
                      w="10px"
                      h="10px"
                      bg="red.500"
                      borderRadius="full"
                      border="2px solid white"
                    />
                  )}
                </Box>
              }
              variant="ghost"
              borderRadius="lg"
              _hover={{ bg: 'gray.100' }}
            />
            <MenuList
              maxH="500px"
              overflowY="auto"
              boxShadow="xl"
              borderRadius="xl"
              p={2}
            >
              <Box p={3}>
                <Flex justify="space-between" align="center" mb={3}>
                  <Text fontWeight="bold" fontSize="lg">Уведомления</Text>
                  {notifications.filter(n => !n.is_read).length > 0 && (
                    <Button
                      size="xs"
                      colorScheme="purple"
                      onClick={markAllNotificationsRead}
                      borderRadius="full"
                    >
                      Прочитать все
                    </Button>
                  )}
                </Flex>
              </Box>
              <Divider />
              {notifications.length === 0 ? (
                <Box p={8} textAlign="center">
                  <Icon as={FiBell} boxSize={10} color="gray.300" mb={2} />
                  <Text color="gray.500">Нет уведомлений</Text>
                </Box>
              ) : (
                notifications.slice(0, 5).map(n => (
                  <MenuItem
                    key={n.id}
                    onClick={() => markNotificationRead(n.id, n.target_url)}
                    bg={n.is_read ? 'white' : 'purple.50'}
                    borderRadius="lg"
                    mb={1}
                    p={3}
                    _hover={{
                      bg: n.is_read ? 'gray.50' : 'purple.100',
                    }}
                  >
                    <VStack align="stretch" spacing={1} w="full">
                      <Text fontSize="sm" fontWeight="medium" noOfLines={2}>
                        {n.message}
                      </Text>
                      <Text fontSize="xs" color="gray.500">
                        {new Date(n.created_at).toLocaleString('ru-RU')}
                      </Text>
                    </VStack>
                  </MenuItem>
                ))
              )}
            </MenuList>
          </Menu>
          <Avatar
            size="md"
            name={login || 'Admin'}
            bg="purple.500"
            color="white"
          />
        </HStack>
      </Flex>
    </Box>
  );

  const Dashboard = () => (
    <Box p={8} bg="gray.50" minH="calc(100vh - 80px)">
      <VStack spacing={8} align="stretch">
        <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
          <Card
            bgGradient="linear(to-br, blue.400, blue.600)"
            color="white"
            boxShadow="xl"
            borderRadius="xl"
            transition="all 0.3s"
            _hover={{ transform: 'translateY(-4px)', boxShadow: '2xl' }}
          >
            <CardBody p={6}>
              <Stat>
                <StatLabel fontSize="sm" fontWeight="medium" opacity={0.9}>
                  Всего пользователей
                </StatLabel>
                <StatNumber fontSize="3xl" fontWeight="bold" my={2}>
                  {dashboardStats.total_users}
                </StatNumber>
                <StatHelpText opacity={0.9}>
                  <HStack spacing={1}>
                    <Icon as={FiUsers} />
                    <Text>Активные пользователи</Text>
                  </HStack>
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card
            bgGradient="linear(to-br, green.400, green.600)"
            color="white"
            boxShadow="xl"
            borderRadius="xl"
            transition="all 0.3s"
            _hover={{ transform: 'translateY(-4px)', boxShadow: '2xl' }}
          >
            <CardBody p={6}>
              <Stat>
                <StatLabel fontSize="sm" fontWeight="medium" opacity={0.9}>
                  Всего бронирований
                </StatLabel>
                <StatNumber fontSize="3xl" fontWeight="bold" my={2}>
                  {dashboardStats.total_bookings}
                </StatNumber>
                <StatHelpText opacity={0.9}>
                  <HStack spacing={1}>
                    <Icon as={FiShoppingBag} />
                    <Text>Все бронирования</Text>
                  </HStack>
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card
            bgGradient="linear(to-br, orange.400, orange.600)"
            color="white"
            boxShadow="xl"
            borderRadius="xl"
            transition="all 0.3s"
            _hover={{ transform: 'translateY(-4px)', boxShadow: '2xl' }}
          >
            <CardBody p={6}>
              <Stat>
                <StatLabel fontSize="sm" fontWeight="medium" opacity={0.9}>
                  Открытые заявки
                </StatLabel>
                <StatNumber fontSize="3xl" fontWeight="bold" my={2}>
                  {dashboardStats.open_tickets}
                </StatNumber>
                <StatHelpText opacity={0.9}>
                  <HStack spacing={1}>
                    <Icon as={FiMessageCircle} />
                    <Text>Требуют внимания</Text>
                  </HStack>
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        <Card
          boxShadow="xl"
          borderRadius="xl"
          overflow="hidden"
        >
          <CardHeader
            bg="white"
            borderBottom="2px"
            borderColor="gray.100"
            p={6}
          >
            <Flex align="center">
              <Icon as={FiTrendingUp} boxSize={6} color="purple.500" mr={3} />
              <Heading size="md" color="gray.800">
                Активность пользователей за неделю
              </Heading>
            </Flex>
          </CardHeader>
          <CardBody p={6} bg="white">
            <Box h="350px">
              <canvas ref={chartRef}></canvas>
            </Box>
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );

  const renderSection = () => {
    switch (section) {
      case 'dashboard':
        return <Dashboard />;
      case 'users':
        return (
          <Box p={8} bg="gray.50" minH="calc(100vh - 80px)">
            <Card borderRadius="xl" boxShadow="xl">
              <CardHeader>
                <Heading size="md">Список пользователей</Heading>
              </CardHeader>
              <CardBody>
                {users.map(user => (
                  <Box key={user.id} p={3} borderBottom="1px" borderColor="gray.100">
                    <Text>{user.full_name || 'Без имени'}</Text>
                  </Box>
                ))}
              </CardBody>
            </Card>
          </Box>
        );
      case 'bookings':
        return (
          <Box p={8} bg="gray.50" minH="calc(100vh - 80px)">
            <Card borderRadius="xl" boxShadow="xl">
              <CardHeader>
                <Heading size="md">Бронирования</Heading>
              </CardHeader>
              <CardBody>
                {bookings.map(b => (
                  <Box key={b.id} p={3} borderBottom="1px" borderColor="gray.100">
                    <Text>{b.visit_date}</Text>
                  </Box>
                ))}
              </CardBody>
            </Card>
          </Box>
        );
      case 'tariffs':
        return (
          <Box p={8} bg="gray.50" minH="calc(100vh - 80px)">
            <Card borderRadius="xl" boxShadow="xl">
              <CardHeader>
                <Heading size="md">Тарифы</Heading>
              </CardHeader>
              <CardBody>
                {tariffs.map(t => (
                  <Box key={t.id} p={3} borderBottom="1px" borderColor="gray.100">
                    <Text>{t.name}</Text>
                  </Box>
                ))}
              </CardBody>
            </Card>
          </Box>
        );
      case 'promocodes':
        return (
          <Box p={8} bg="gray.50" minH="calc(100vh - 80px)">
            <Card borderRadius="xl" boxShadow="xl">
              <CardHeader>
                <Heading size="md">Промокоды</Heading>
              </CardHeader>
              <CardBody>
                {promocodes.map(p => (
                  <Box key={p.id} p={3} borderBottom="1px" borderColor="gray.100">
                    <Text>{p.name}</Text>
                  </Box>
                ))}
              </CardBody>
            </Card>
          </Box>
        );
      case 'tickets':
        return (
          <Box p={8} bg="gray.50" minH="calc(100vh - 80px)">
            <Card borderRadius="xl" boxShadow="xl">
              <CardHeader>
                <Heading size="md">Заявки</Heading>
              </CardHeader>
              <CardBody>
                {tickets.map(t => (
                  <Box key={t.id} p={3} borderBottom="1px" borderColor="gray.100">
                    <Text>{t.description}</Text>
                  </Box>
                ))}
              </CardBody>
            </Card>
          </Box>
        );
      case 'notifications':
        return (
          <Box p={8} bg="gray.50" minH="calc(100vh - 80px)">
            <Card borderRadius="xl" boxShadow="xl">
              <CardHeader>
                <Heading size="md">Уведомления</Heading>
              </CardHeader>
              <CardBody>
                {notifications.map(n => (
                  <Box key={n.id} p={3} borderBottom="1px" borderColor="gray.100">
                    <Text>{n.message}</Text>
                  </Box>
                ))}
              </CardBody>
            </Card>
          </Box>
        );
      case 'newsletters':
        return (
          <Box p={8} bg="gray.50" minH="calc(100vh - 80px)">
            <Card borderRadius="xl" boxShadow="xl">
              <CardHeader>
                <Heading size="md">Рассылка</Heading>
              </CardHeader>
              <CardBody>
                {newsletters.map(n => (
                  <Box key={n.id} p={3} borderBottom="1px" borderColor="gray.100">
                    <Text>{n.message}</Text>
                  </Box>
                ))}
              </CardBody>
            </Card>
          </Box>
        );
      default:
        return <Dashboard />;
    }
  };

  if (isCheckingAuth) {
    return (
      <ChakraProvider>
        <Center h="100vh" bg="gray.50">
          <VStack spacing={4}>
            <Spinner size="xl" color="purple.500" thickness="4px" />
            <Text color="gray.600">Загрузка...</Text>
          </VStack>
        </Center>
      </ChakraProvider>
    );
  }

  if (!isAuthenticated) {
    return (
      <ChakraProvider>
        <Login
          login={login}
          setLogin={setLogin}
          password={password}
          setPassword={setPassword}
          handleLogin={handleLogin}
          isLoading={isLoading}
        />
      </ChakraProvider>
    );
  }

  return (
    <ChakraProvider>
      <Flex minH="100vh" bg="gray.50">
        <Sidebar />
        <Box flex={1}>
          <Navbar />
          {renderSection()}
        </Box>
      </Flex>
    </ChakraProvider>
  );
}

export default App;