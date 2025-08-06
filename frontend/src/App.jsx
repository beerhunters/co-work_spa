import { useState, useEffect } from 'react';
import axios from 'axios';
import {
    ChakraProvider,
    Box,
    Button,
    Input,
    Heading,
    Container,
    VStack,
    HStack,
    Text,
} from '@chakra-ui/react';
import { Tabs, TabList, Tab, TabPanels, TabPanel } from '@chakra-ui/tabs';

/**
 * Основной компонент админ-панели
 * @returns {JSX.Element} Форма логина или дашборд
 */
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
    const [lastNotificationId, setLastNotificationId] = useState(null);

    /**
     * Обработка входа в систему
     */
    const handleLogin = async () => {
        try {
            await axios.post('http://localhost/api/login', { login, password }, { withCredentials: true });
            setIsAuthenticated(true);
            setSection('dashboard');
        } catch (error) {
            alert(`Ошибка входа: ${error.response?.data?.detail || error.message}`);
        }
    };

    /**
     * Обработка выхода из системы
     */
    const handleLogout = async () => {
        try {
            await axios.get('http://localhost/api/logout', { withCredentials: true });
            setIsAuthenticated(false);
            setSection('login');
        } catch (error) {
            console.error('Ошибка выхода:', error);
        }
    };

    /**
     * Получение уведомлений
     */
    const fetchNotifications = async () => {
        try {
            const res = await axios.get(
                `http://localhost/api/get_notifications${lastNotificationId ? `?since_id=${lastNotificationId}` : ''}`,
                { withCredentials: true }
            );
            if (res.data.length > 0) {
                setNotifications(prev => [...res.data, ...prev]);
                setLastNotificationId(Math.max(...res.data.map(n => n.id)));
            }
        } catch (error) {
            console.error('Ошибка получения уведомлений:', error);
        }
    };

    /**
     * Загрузка данных при авторизации
     */
    useEffect(() => {
        if (isAuthenticated) {
            axios.get('http://localhost/api/users', { withCredentials: true })
                .then(res => setUsers(res.data))
                .catch(err => console.error('Ошибка загрузки пользователей:', err));
            axios.get('http://localhost/api/bookings', { withCredentials: true })
                .then(res => setBookings(res.data))
                .catch(err => console.error('Ошибка загрузки бронирований:', err));
            axios.get('http://localhost/api/tariffs', { withCredentials: true })
                .then(res => setTariffs(res.data))
                .catch(err => console.error('Ошибка загрузки тарифов:', err));
            axios.get('http://localhost/api/promocodes', { withCredentials: true })
                .then(res => setPromocodes(res.data))
                .catch(err => console.error('Ошибка загрузки промокодов:', err));
            axios.get('http://localhost/api/tickets', { withCredentials: true })
                .then(res => setTickets(res.data))
                .catch(err => console.error('Ошибка загрузки тикетов:', err));
            axios.get('http://localhost/api/notifications', { withCredentials: true })
                .then(res => {
                    setNotifications(res.data);
                    setLastNotificationId(Math.max(...res.data.map(n => n.id), 0));
                })
                .catch(err => console.error('Ошибка загрузки уведомлений:', err));
            axios.get('http://localhost/api/newsletters', { withCredentials: true })
                .then(res => setNewsletters(res.data))
                .catch(err => console.error('Ошибка загрузки рассылок:', err));

            const interval = setInterval(fetchNotifications, 10000);
            return () => clearInterval(interval);
        }
    }, [isAuthenticated]);

    /**
     * Рендеринг формы логина
     * @returns {JSX.Element} Компонент формы логина
     */
    const renderLogin = () => (
        <Container maxW="container.sm" mt="8">
            <VStack spacing="6" align="stretch">
                <Heading textAlign="center">Вход в админ-панель</Heading>
                <Input
                    placeholder="Логин"
                    value={login}
                    onChange={e => setLogin(e.target.value)}
                    size="lg"
                />
                <Input
                    placeholder="Пароль"
                    type="password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    size="lg"
                />
                <Button colorScheme="blue" size="lg" onClick={handleLogin}>
                    Войти
                </Button>
            </VStack>
        </Container>
    );

    /**
     * Рендеринг дашборда
     * @returns {JSX.Element} Компонент дашборда
     */
    const renderDashboard = () => (
        <Container maxW="container.lg" py="4">
            <VStack spacing="4" align="stretch">
                <HStack justify="space-between">
                    <Heading size="lg">Админ-панель Parta</Heading>
                    <Button colorScheme="red" onClick={handleLogout}>
                        Выйти
                    </Button>
                </HStack>
                <Tabs
                    variant="enclosed"
                    onChange={index => setSection(['users', 'bookings', 'tariffs', 'promocodes', 'tickets', 'notifications', 'newsletters'][index])}
                >
                    <TabList>
                        <Tab>Пользователи</Tab>
                        <Tab>Брони</Tab>
                        <Tab>Тарифы</Tab>
                        <Tab>Промокоды</Tab>
                        <Tab>Тикеты</Tab>
                        <Tab>Уведомления</Tab>
                        <Tab>Рассылки</Tab>
                    </TabList>
                    <TabPanels>
                        <TabPanel>
                            <Box bg="white" p="4" rounded="md" shadow="md">
                                <Heading size="md" mb="4">Список пользователей</Heading>
                                {users.length > 0 ? (
                                    <VStack align="start" spacing="2">
                                        {users.map(user => (
                                            <Text key={user.id}>{user.name || 'Без имени'}</Text>
                                        ))}
                                    </VStack>
                                ) : (
                                    <Text color="gray.500">Нет данных</Text>
                                )}
                            </Box>
                        </TabPanel>
                        <TabPanel>
                            <Box bg="white" p="4" rounded="md" shadow="md">
                                <Heading size="md" mb="4">Список бронирований</Heading>
                                {bookings.length > 0 ? (
                                    <VStack align="start" spacing="2">
                                        {bookings.map(booking => (
                                            <Text key={booking.id}>{booking.title || 'Без названия'}</Text>
                                        ))}
                                    </VStack>
                                ) : (
                                    <Text color="gray.500">Нет данных</Text>
                                )}
                            </Box>
                        </TabPanel>
                        <TabPanel>
                            <Box bg="white" p="4" rounded="md" shadow="md">
                                <Heading size="md" mb="4">Список тарифов</Heading>
                                {tariffs.length > 0 ? (
                                    <VStack align="start" spacing="2">
                                        {tariffs.map(tariff => (
                                            <Text key={tariff.id}>{tariff.name || 'Без названия'}</Text>
                                        ))}
                                    </VStack>
                                ) : (
                                    <Text color="gray.500">Нет данных</Text>
                                )}
                            </Box>
                        </TabPanel>
                        <TabPanel>
                            <Box bg="white" p="4" rounded="md" shadow="md">
                                <Heading size="md" mb="4">Список промокодов</Heading>
                                {promocodes.length > 0 ? (
                                    <VStack align="start" spacing="2">
                                        {promocodes.map(promo => (
                                            <Text key={promo.id}>{promo.code || 'Без кода'}</Text>
                                        ))}
                                    </VStack>
                                ) : (
                                    <Text color="gray.500">Нет данных</Text>
                                )}
                            </Box>
                        </TabPanel>
                        <TabPanel>
                            <Box bg="white" p="4" rounded="md" shadow="md">
                                <Heading size="md" mb="4">Список тикетов</Heading>
                                {tickets.length > 0 ? (
                                    <VStack align="start" spacing="2">
                                        {tickets.map(ticket => (
                                            <Text key={ticket.id}>{ticket.title || 'Без названия'}</Text>
                                        ))}
                                    </VStack>
                                ) : (
                                    <Text color="gray.500">Нет данных</Text>
                                )}
                            </Box>
                        </TabPanel>
                        <TabPanel>
                            <Box bg="white" p="4" rounded="md" shadow="md">
                                <Heading size="md" mb="4">Список уведомлений</Heading>
                                {notifications.length > 0 ? (
                                    <VStack align="start" spacing="2">
                                        {notifications.map(notification => (
                                            <Text key={notification.id}>{notification.message || 'Без текста'}</Text>
                                        ))}
                                    </VStack>
                                ) : (
                                    <Text color="gray.500">Нет данных</Text>
                                )}
                            </Box>
                        </TabPanel>
                        <TabPanel>
                            <Box bg="white" p="4" rounded="md" shadow="md">
                                <Heading size="md" mb="4">Список рассылок</Heading>
                                {newsletters.length > 0 ? (
                                    <VStack align="start" spacing="2">
                                        {newsletters.map(newsletter => (
                                            <Text key={newsletter.id}>{newsletter.title || 'Без названия'}</Text>
                                        ))}
                                    </VStack>
                                ) : (
                                    <Text color="gray.500">Нет данных</Text>
                                )}
                            </Box>
                        </TabPanel>
                    </TabPanels>
                </Tabs>
            </VStack>
        </Container>
    );

    return (
        <ChakraProvider>
            {isAuthenticated ? renderDashboard() : renderLogin()}
        </ChakraProvider>
    );
}

export default App;