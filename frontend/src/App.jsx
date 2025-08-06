import { useState, useEffect } from 'react';
import axios from 'axios';
import { ChakraProvider, Box, Flex, VStack, HStack, Text, Icon, Button, Tabs, TabList, Tab, TabPanels, TabPanel, Grid, GridItem, Heading, useToast, IconButton, Menu, MenuButton, MenuList, MenuItem, Badge } from '@chakra-ui/react';
import { FaTachometerAlt, FaUsers, FaCalendarCheck, FaTags, FaGift, FaTicketAlt, FaBell, FaEnvelope, FaSignOutAlt, FaBuilding } from 'react-icons/fa';
import Chart from 'chart.js/auto';
import './App.css';

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

  // Загрузка данных
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
            setLastNotificationId(Math.max(...data.map(n => n.id), 0));
          }
        },
        { url: '/newsletters', setter: setNewsletters }
      ];
      await Promise.all(endpoints.map(async ({ url, setter }) => {
        const res = await axios.get(`http://localhost/api${url}`, { withCredentials: true });
        setter(res.data);
      }));
    } catch (err) {
      console.error('Ошибка загрузки данных:', err);
      toast({ title: 'Ошибка', description: 'Не удалось загрузить данные', status: 'error', duration: 5000, isClosable: true });
    }
  };

  // Проверка новых уведомлений
  const fetchNotifications = async () => {
    try {
      const res = await axios.get(`http://localhost/api/notifications/check_new?since_id=${lastNotificationId}`, { withCredentials: true });
      if (res.data.status === 'success' && res.data.recent_notifications.length > 0) {
        const newNotifications = res.data.recent_notifications.filter(n => !n.is_read);
        setNotifications(prev => [...newNotifications, ...prev]);
        setLastNotificationId(Math.max(...res.data.recent_notifications.map(n => n.id), lastNotificationId));
        newNotifications.forEach(n => {
          toast({
            title: 'Новое уведомление',
            description: n.message,
            status: n.type === 'user' ? 'success' : n.type === 'booking' ? 'info' : n.type === 'ticket' ? 'warning' : 'info',
            duration: 5000,
            isClosable: true,
            icon: n.type === 'user' ? <FaUsers /> : n.type === 'booking' ? <FaCalendarCheck /> : n.type === 'ticket' ? <FaTicketAlt /> : <FaBell />
          });
        });
      }
    } catch (err) {
      console.error('Ошибка получения уведомлений:', err);
    }
  };

  // Авторизация
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

  // Выход
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

  // Пометка уведомления как прочитанного
  const markNotificationRead = async (notificationId, targetUrl) => {
    try {
      await axios.post(`http://localhost/api/notifications/mark_read/${notificationId}`, {}, { withCredentials: true });
      setNotifications(prev => prev.map(n => n.id === notificationId ? { ...n, is_read: true } : n));
      if (targetUrl && targetUrl !== '#') {
        window.location.href = targetUrl;
      }
    } catch (error) {
      console.error('Ошибка при пометке уведомления:', error);
      toast({ title: 'Ошибка', description: 'Не удалось пометить уведомление как прочитанное', status: 'error', duration: 5000, isClosable: true });
    }
  };

  // Пометка всех уведомлений как прочитанных
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

  // Инициализация при загрузке
  useEffect(() => {
    if (isAuthenticated) {
      fetchData();
      const interval = setInterval(fetchNotifications, 10000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated]);

  // Инициализация графика
  useEffect(() => {
    if (section === 'dashboard' && isAuthenticated) {
      const ctx = document.getElementById('bookingsChart')?.getContext('2d');
      if (ctx) {
        const bookingsData = {
          labels: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
          counts: bookings.reduce((acc, b) => {
            const date = new Date(b.visit_date);
            const day = date.getDay() === 0 ? 6 : date.getDay() - 1;
            acc[day] = (acc[day] || 0) + 1;
            return acc;
          }, Array(7).fill(0)),
          userCounts: users.reduce((acc, u) => {
            const date = new Date(u.created_at);
            const day = date.getDay() === 0 ? 6 : date.getDay() - 1;
            acc[day] = (acc[day] || 0) + 1;
            return acc;
          }, Array(7).fill(0))
        };
        new Chart(ctx, {
          type: 'line',
          data: {
            labels: bookingsData.labels,
            datasets: [
              {
                label: 'Бронирования',
                data: bookingsData.counts,
                borderColor: 'rgba(99, 102, 241, 1)',
                backgroundColor: 'rgba(99, 102, 241, 0.2)',
                fill: true,
                tension: 0.4
              },
              {
                label: 'Новые пользователи',
                data: bookingsData.userCounts,
                borderColor: 'rgba(34, 197, 94, 1)',
                backgroundColor: 'rgba(34, 197, 94, 0.2)',
                fill: true,
                tension: 0.4
              }
            ]
          },
          options: {
            responsive: true,
            plugins: {
              legend: { display: true, position: 'top' },
              tooltip: { mode: 'index', intersect: false }
            },
            scales: {
              y: { beginAtZero: true, ticks: { precision: 0 } }
            }
          }
        });
      }
    }
  }, [bookings, users, section]);

  // Компонент боковой панели
  const Sidebar = () => (
    <VStack className="sidebar" spacing={2} p={4} bg="white" borderRight="1px" borderColor="var(--border-color)" minH="calc(100vh - 76px)" position="sticky" top="76px">
      {[
        { icon: FaTachometerAlt, label: 'Дашборд', section: 'dashboard' },
        { icon: FaUsers, label: 'Пользователи', section: 'users' },
        { icon: FaCalendarCheck, label: 'Бронирования', section: 'bookings' },
        { icon: FaTags, label: 'Тарифы', section: 'tariffs' },
        { icon: FaGift, label: 'Промокоды', section: 'promocodes' },
        { icon: FaTicketAlt, label: 'Заявки', section: 'tickets' },
        { icon: FaBell, label: 'Уведомления', section: 'notifications' },
        { icon: FaEnvelope, label: 'Рассылка', section: 'newsletters' }
      ].map(({ icon, label, section: sec }) => (
        <Button
          key={sec}
          className={`nav-link ${section === sec ? 'active' : ''}`}
          leftIcon={<Icon as={icon} />}
          variant="ghost"
          w="full"
          justifyContent="flex-start"
          onClick={() => setSection(sec)}
        >
          {label}
        </Button>
      ))}
    </VStack>
  );

  // Компонент навигации
  const Navbar = () => (
    <Flex className="navbar" justify="space-between" align="center" p={4} bgGradient="linear(to-r, #667eea, #764ba2)" color="white" position="sticky" top={0} zIndex={1020}>
      <HStack spacing={4}>
        <Icon as={FaBuilding} />
        <Text fontWeight="bold">Админ-панель</Text>
      </HStack>
      <HStack spacing={4}>
        <Menu>
          <MenuButton as={IconButton} icon={<Icon as={FaBell} />} variant="ghost" className="bell-container">
            <Badge className="notification-badge" display={notifications.filter(n => !n.is_read).length > 0 ? 'inline' : 'none'}>
              {notifications.filter(n => !n.is_read).length}
            </Badge>
          </MenuButton>
          <MenuList bg="white" color="gray.800" maxH="500px" overflowY="auto">
            <HStack px={4} py={2} bgGradient="linear(to-r, #f8fafc, #e2e8f0)" justify="space-between">
              <Text fontWeight="semibold">Уведомления</Text>
              <Button size="sm" variant="outline" onClick={markAllNotificationsRead}>Пометить все как прочитанные</Button>
            </HStack>
            {notifications.length === 0 ? (
              <Text textAlign="center" p={4} color="gray.500">Нет уведомлений</Text>
            ) : (
              notifications.slice(0, 5).map(n => (
                <MenuItem
                  key={n.id}
                  bg={n.is_read ? 'white' : 'gray.50'}
                  color="gray.800"
                  className={`notification-item ${n.is_read ? 'read' : 'unread'}`}
                  onClick={() => markNotificationRead(n.id, n.target_url)}
                >
                  <HStack spacing={3}>
                    <Icon
                      as={n.type === 'user' ? FaUsers : n.type === 'booking' ? FaCalendarCheck : n.type === 'ticket' ? FaTicketAlt : FaBell}
                      color={n.type === 'user' ? 'green.500' : n.type === 'booking' ? 'blue.500' : n.type === 'ticket' ? 'yellow.500' : 'gray.500'}
                    />
                    <VStack align="start" spacing={0}>
                      <Text fontSize="sm">{n.message}</Text>
                      <Text fontSize="xs" color="gray.500">{new Date(n.created_at).toLocaleString('ru-RU')}</Text>
                    </VStack>
                  </HStack>
                </MenuItem>
              ))
            )}
            <MenuItem as="a" href="/notifications" textAlign="center" color="gray.800">Все уведомления</MenuItem>
          </MenuList>
        </Menu>
        <Button leftIcon={<Icon as={FaSignOutAlt} />} variant="ghost" onClick={handleLogout}>Выход</Button>
      </HStack>
    </Flex>
  );

  // Компонент дашборда
  const Dashboard = () => (
    <Box p={4}>
      <Heading size="lg" mb={4}>Обзор активности коворкинга</Heading>
      <Grid templateColumns={{ base: '1fr', md: 'repeat(4, 1fr)' }} gap={4} mb={4}>
        <GridItem className="card">
          <VStack p={4} textAlign="center">
            <Icon as={FaUsers} fontSize="2xl" color="blue.500" />
            <Text fontWeight="semibold">Пользователи</Text>
            <Text fontSize="2xl">{users.length}</Text>
            <Text fontSize="sm" color="gray.500">Всего зарегистрировано</Text>
          </VStack>
        </GridItem>
        <GridItem className="card">
          <VStack p={4} textAlign="center">
            <Icon as={FaCalendarCheck} fontSize="2xl" color="green.500" />
            <Text fontWeight="semibold">Бронирования</Text>
            <Text fontSize="2xl">{bookings.length}</Text>
            <Text fontSize="sm" color="gray.500">Активных за месяц</Text>
          </VStack>
        </GridItem>
        <GridItem className="card">
          <VStack p={4} textAlign="center">
            <Icon as={FaTicketAlt} fontSize="2xl" color="yellow.500" />
            <Text fontWeight="semibold">Заявки</Text>
            <Text fontSize="2xl">{tickets.length}</Text>
            <Text fontSize="sm" color="gray.500">Открытых заявок</Text>
          </VStack>
        </GridItem>
        <GridItem className="card">
          <VStack p={4} textAlign="center">
            <Icon as={FaGift} fontSize="2xl" color="cyan.500" />
            <Text fontWeight="semibold">Промокоды</Text>
            <Text fontSize="2xl">{promocodes.length}</Text>
            <Text fontSize="sm" color="gray.500">Активных промокодов</Text>
          </VStack>
        </GridItem>
      </Grid>
      <Box className="card">
        <Box p={4}>
          <Text fontWeight="semibold" mb={2}>Активность за неделю</Text>
          <canvas id="bookingsChart" height="100"></canvas>
        </Box>
      </Box>
    </Box>
  );

  // Компонент логина
  const Login = () => (
    <VStack maxW="400px" mx="auto" mt="10vh" spacing={4}>
      <Heading size="lg">Вход в админ-панель</Heading>
      <Box w="full">
        <Text mb={2}>Логин</Text>
        <input className="form-control" type="text" value={login} onChange={e => setLogin(e.target.value)} placeholder="Введите логин" />
      </Box>
      <Box w="full">
        <Text mb={2}>Пароль</Text>
        <input className="form-control" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Введите пароль" />
      </Box>
      <Button colorScheme="blue" onClick={handleLogin}>Войти</Button>
    </VStack>
  );

  // Рендеринг секций
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
      default: return <Login />;
    }
  };

  return (
    <ChakraProvider>
      <Box>
        {isAuthenticated && (
          <>
            <Navbar />
            <Flex>
              <Sidebar />
              <Box flex={1} p={4}>{renderSection()}</Box>
            </Flex>
          </>
        )}
        {!isAuthenticated && <Login />}
      </Box>
    </ChakraProvider>
  );
}

export default App;