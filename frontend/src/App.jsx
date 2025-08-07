import React, { useState, useEffect, useRef } from 'react';
import { ChakraProvider, Box, Flex, VStack, HStack, Text, Button, Input, Card, CardBody, Heading, Badge, Popover, PopoverTrigger, PopoverContent, PopoverArrow, PopoverCloseButton, PopoverHeader, PopoverBody, useToast, IconButton, Spacer } from '@chakra-ui/react';
import { FaUsers, FaTags, FaChartBar, FaEnvelope, FaBell, FaTicketAlt, FaCalendarAlt, FaCopy, FaQuestion } from 'react-icons/fa';
import axios from 'axios';
import Chart from 'chart.js/auto';
import './App.css';

const Login = ({ login, setLogin, password, setPassword, handleLogin }) => {
  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleLogin();
    }
  };

  return (
    <Flex height="100vh" align="center" justify="center" bg="linear-gradient(135deg, #667eea 0%, #764ba2 100%)">
      <Card maxW="md" w="full" p={8} shadow="2xl" bg="white" borderRadius="xl">
        <CardBody>
          <VStack spacing={6}>
            <VStack spacing={2}>
              <Heading size="lg" color="gray.700">Добро пожаловать</Heading>
              <Text color="gray.500" textAlign="center">Войдите в административную панель</Text>
            </VStack>

            <VStack spacing={4} w="full">
              <Input
                className="form-control"
                type="text"
                value={login}
                onChange={e => setLogin(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Введите логин"
                size="lg"
                focusBorderColor="blue.500"
              />
              <Input
                className="form-control"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Введите пароль"
                size="lg"
                focusBorderColor="blue.500"
              />
              <Button
                colorScheme="blue"
                onClick={handleLogin}
                w="full"
                size="lg"
                isLoading={false}
                _hover={{ transform: 'translateY(-2px)', shadow: 'lg' }}
              >
                Войти
              </Button>
            </VStack>
          </VStack>
        </CardBody>
      </Card>
    </Flex>
  );
};

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [section, setSection] = useState('login');
  const [users, setUsers] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [tariffs, setTariffs] = useState([]);
  const [promocodes, setPromocodes] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [newsletters, setNewsletters] = useState([]);
  const [lastNotificationId, setLastNotificationId] = useState(0);
  const toast = useToast();
  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);

  const fetchData = async () => {
    try {
      const endpoints = [
        { url: '/users', setter: setUsers },
        { url: '/bookings', setter: setBookings },
        { url: '/tariffs', setter: setTariffs },
        { url: '/promocodes', setter: setPromocodes },
        { url: '/tickets', setter: setTickets },
        { url: '/notifications', setter: (data) => {
          setNotifications(data);
          if (data && data.length > 0) {
            setLastNotificationId(Math.max(...data.map(n => n.id), 0));
          }
        }},
        { url: '/newsletters', setter: setNewsletters }
      ];

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

      if (res.data && res.data.recent_notifications) {
        const newNotifications = res.data.recent_notifications.filter(n => !n.is_read);
        if (newNotifications.length > 0) {
          setNotifications(prev => [...newNotifications, ...prev]);
          setLastNotificationId(Math.max(...res.data.recent_notifications.map(n => n.id), lastNotificationId));

          newNotifications.forEach(n => {
            toast({
              title: 'Новое уведомление',
              description: n.message,
              status: 'info',
              duration: 5000,
              isClosable: true
            });
          });
        }
      }
    } catch (err) {
      console.error('Ошибка получения уведомлений:', err);
    }
  };

  const handleLogin = async () => {
    try {
      await axios.post('http://localhost/api/login', { login, password }, { withCredentials: true });
      setIsAuthenticated(true);
      setSection('dashboard');
      fetchData();
    } catch (error) {
      toast({ title: 'Ошибка входа', description: error.response?.data?.detail || error.message, status: 'error', duration: 5000, isClosable: true });
    }
  };

  const handleLogout = async () => {
    try {
      await axios.get('http://localhost/api/logout', { withCredentials: true });
      setIsAuthenticated(false);
      setSection('login');
    } catch (error) {
      console.error('Ошибка выхода:', error);
      toast({ title: 'Ошибка', description: 'Не удалось выйти', status: 'error', duration: 5000, isClosable: true });
    }
  };

  const markNotificationRead = async (notificationId, targetUrl) => {
    try {
      await axios.post(`http://localhost/api/notifications/mark_read/${notificationId}`, {}, { withCredentials: true });
      setNotifications(prev => prev.map(n => n.id === notificationId ? { ...n, is_read: true } : n));
      if (targetUrl) window.open(targetUrl, '_blank');
    } catch (error) {
      console.error('Ошибка при пометке уведомления:', error);
      toast({ title: 'Ошибка', description: 'Не удалось пометить уведомление как прочитанное', status: 'error', duration: 5000, isClosable: true });
    }
  };

  const markAllNotificationsRead = async () => {
    try {
      await axios.post('http://localhost/api/notifications/mark_all_read', {}, { withCredentials: true });
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      toast({ title: 'Успех', description: 'Все уведомления помечены как прочитанные', status: 'success', duration: 5000, isClosable: true });
    } catch (error) {
      console.error('Ошибка при пометке всех уведомлений:', error);
      toast({ title: 'Ошибка', description: 'Не удалось пометить уведомления', status: 'error', duration: 5000, isClosable: true });
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      const interval = setInterval(fetchNotifications, 10000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, lastNotificationId]);

  useEffect(() => {
    if (section === 'dashboard' && chartRef.current && users.length > 0) {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.destroy();
      }

      const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

      // Подсчитываем только зарегистрированных пользователей по дням недели
      const userRegistrationCounts = users.reduce((acc, u) => {
        if (u.reg_date || u.first_join_time) {
          const date = new Date(u.reg_date || u.first_join_time);
          const day = date.getDay() === 0 ? 6 : date.getDay() - 1; // Приводим к формату Пн=0, Вс=6
          acc[day]++;
        }
        return acc;
      }, Array(7).fill(0));

      const ctx = chartRef.current.getContext('2d');

      chartInstanceRef.current = new Chart(ctx, {
        type: 'line',
        data: {
          labels: dayNames,
          datasets: [{
            label: 'Зарегистрированные пользователи',
            data: userRegistrationCounts,
            borderColor: 'rgb(75, 192, 192)',
            backgroundColor: 'rgba(75, 192, 192, 0.2)',
            tension: 0.1,
            fill: true
          }]
        },
        options: {
          responsive: true,
          plugins: {
            title: {
              display: true,
              text: 'Регистрации пользователей по дням недели'
            },
            legend: {
              display: true,
              position: 'top'
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                stepSize: 1
              }
            }
          }
        }
      });
    }
  }, [section, users]);

  const Sidebar = () => (
    <VStack className="sidebar" w="250px" bg="gray.800" color="white" h="100vh" p={4} spacing={2} align="stretch">
      <Text fontSize="xl" fontWeight="bold" mb={4} textAlign="center">Панель управления</Text>
      {[
        { icon: FaChartBar, label: 'Дашборд', section: 'dashboard' },
        { icon: FaUsers, label: 'Пользователи', section: 'users' },
        { icon: FaCalendarAlt, label: 'Бронирования', section: 'bookings' },
        { icon: FaTags, label: 'Тарифы', section: 'tariffs' },
        { icon: FaCopy, label: 'Промокоды', section: 'promocodes' },
        { icon: FaTicketAlt, label: 'Заявки', section: 'tickets' },
        { icon: FaBell, label: 'Уведомления', section: 'notifications' },
        { icon: FaEnvelope, label: 'Рассылка', section: 'newsletters' }
      ].map(({ icon: Icon, label, section: sec }) => (
        <Button
          key={sec}
          leftIcon={<Icon />}
          variant={section === sec ? 'solid' : 'ghost'}
          colorScheme={section === sec ? 'blue' : 'gray'}
          w="full"
          justifyContent="flex-start"
          onClick={() => setSection(sec)}
          _hover={{ bg: section === sec ? 'blue.600' : 'gray.600' }}
          color={section === sec ? 'white' : 'gray.300'}
        >
          {label}
        </Button>
      ))}
      <Spacer />
      <Button colorScheme="red" variant="outline" w="full" onClick={handleLogout} _hover={{ bg: 'red.600', color: 'white' }}>
        Выйти
      </Button>
    </VStack>
  );

  const Navbar = () => (
    <Flex className="navbar" bg="white" p={4} shadow="sm" align="center" borderBottomWidth="1px" borderColor="gray.200">
      <Text fontSize="lg" fontWeight="semibold" color="gray.700">
        Административная панель
      </Text>
      <Spacer />
      <Popover>
        <PopoverTrigger>
          <Box position="relative" cursor="pointer">
            <IconButton
              icon={<FaBell />}
              variant="ghost"
              colorScheme="gray"
              fontSize="20px"
              _hover={{ bg: 'gray.100' }}
            />
            {notifications.filter(n => !n.is_read).length > 0 && (
              <Badge
                position="absolute"
                top="-1"
                right="-1"
                px={2}
                py={1}
                fontSize="0.8em"
                colorScheme="red"
                borderRadius="full"
              >
                {notifications.filter(n => !n.is_read).length}
              </Badge>
            )}
          </Box>
        </PopoverTrigger>
        <PopoverContent maxW="400px">
          <PopoverArrow />
          <PopoverCloseButton />
          <PopoverHeader fontWeight="semibold">Уведомления</PopoverHeader>
          <PopoverBody maxH="400px" overflowY="auto">
            <VStack spacing={2} align="stretch">
              {notifications.length === 0 ? (
                <Text color="gray.500" textAlign="center" py={4}>
                  Нет уведомлений
                </Text>
              ) : (
                notifications.slice(0, 5).map(n => (
                  <Box
                    key={n.id}
                    p={3}
                    bg={n.is_read ? 'gray.50' : 'blue.50'}
                    borderRadius="md"
                    cursor="pointer"
                    borderLeftWidth={n.is_read ? 0 : 4}
                    borderLeftColor="blue.500"
                    onClick={() => markNotificationRead(n.id, n.target_url)}
                    _hover={{ bg: n.is_read ? 'gray.100' : 'blue.100' }}
                  >
                    <Text fontSize="sm" fontWeight={n.is_read ? 'normal' : 'semibold'}>
                      {n.message}
                    </Text>
                    <Text fontSize="xs" color="gray.500" mt={1}>
                      {new Date(n.created_at).toLocaleString('ru-RU')}
                    </Text>
                  </Box>
                ))
              )}
              {notifications.length > 0 && (
                <Button
                  size="sm"
                  colorScheme="blue"
                  variant="outline"
                  onClick={markAllNotificationsRead}
                  mt={2}
                >
                  Пометить все как прочитанные
                </Button>
              )}
            </VStack>
          </PopoverBody>
        </PopoverContent>
      </Popover>
    </Flex>
  );

  const Dashboard = () => (
    <VStack spacing={6} align="stretch" className="fade-in">
      <Heading size="lg" color="gray.700">Дашборд</Heading>

      <HStack spacing={4} className="dashboard-stats">
        <Card flex={1} bg="linear-gradient(135deg, #667eea 0%, #764ba2 100%)">
          <CardBody textAlign="center" color="white">
            <VStack>
              <Text fontSize="3xl" fontWeight="bold">{users.length}</Text>
              <Text fontSize="lg" opacity={0.9}>Всего пользователей</Text>
            </VStack>
          </CardBody>
        </Card>

        <Card flex={1} bg="linear-gradient(135deg, #f093fb 0%, #f5576c 100%)">
          <CardBody textAlign="center" color="white">
            <VStack>
              <Text fontSize="3xl" fontWeight="bold">{bookings.length}</Text>
              <Text fontSize="lg" opacity={0.9}>Всего бронирований</Text>
            </VStack>
          </CardBody>
        </Card>

        <Card flex={1} bg="linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)">
          <CardBody textAlign="center" color="white">
            <VStack>
              <Text fontSize="3xl" fontWeight="bold">{tickets.length}</Text>
              <Text fontSize="lg" opacity={0.9}>Всего заявок</Text>
            </VStack>
          </CardBody>
        </Card>
      </HStack>

      <Card className="chart-container">
        <CardBody>
          <Heading size="md" mb={4} color="gray.700">
            Статистика регистраций пользователей
          </Heading>
          <Box height="400px">
            <canvas ref={chartRef} width="400" height="200"></canvas>
          </Box>
        </CardBody>
      </Card>
    </VStack>
  );

  const renderSection = () => {
    switch (section) {
      case 'dashboard': return <Dashboard />;
      case 'users': return <Box p={4}><Heading size="md">Пользователи</Heading>{users.map(user => <Text key={user.id}>{user.full_name}</Text>)}</Box>;
      case 'bookings': return <Box p={4}><Heading size="md">Бронирования</Heading>{bookings.map(b => <Text key={b.id}>{b.visit_date}</Text>)}</Box>;
      case 'tariffs': return <Box p={4}><Heading size="md">Тарифы</Heading>{tariffs.map(t => <Text key={t.id}>{t.name}</Text>)}</Box>;
      case 'promocodes': return <Box p={4}><Heading size="md">Промокоды</Heading>{promocodes.map(p => <Text key={p.id}>{p.name}</Text>)}</Box>;
      case 'tickets': return <Box p={4}><Heading size="md">Заявки</Heading>{tickets.map(t => <Text key={t.id}>{t.description}</Text>)}</Box>;
      case 'notifications': return <Box p={4}><Heading size="md">Уведомления</Heading>{notifications.map(n => <Text key={n.id}>{n.message}</Text>)}</Box>;
      case 'newsletters': return <Box p={4}><Heading size="md">Рассылка</Heading>{newsletters.map(n => <Text key={n.id}>{n.message}</Text>)}</Box>;
      default: return <Dashboard />;
    }
  };

  if (!isAuthenticated) {
    return (
      <ChakraProvider>
        <Login
          login={login}
          setLogin={setLogin}
          password={password}
          setPassword={setPassword}
          handleLogin={handleLogin}
        />
      </ChakraProvider>
    );
  }

  return (
    <ChakraProvider>
      <Flex h="100vh" bg="gray.50">
        <Sidebar />
        <Box flex={1} display="flex" flexDirection="column">
          <Navbar />
          <Box flex={1} p={6} overflowY="auto">
            {renderSection()}
          </Box>
        </Box>
      </Flex>
    </ChakraProvider>
  );
}

export default App;