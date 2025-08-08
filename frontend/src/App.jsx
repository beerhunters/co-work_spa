// App.jsx
import React, { useState, useEffect, useRef } from 'react';
import { ChakraProvider, useToast, useDisclosure } from '@chakra-ui/react';
import axios from 'axios';

// Компоненты
import Login from './components/Login';
import Layout from './components/Layout';
import DetailModal from './components/DetailModal';

// Секции
import Dashboard from './sections/Dashboard';
import Users from './sections/Users';
import Bookings from './sections/Bookings';
import Tariffs from './sections/Tariffs';
import Promocodes from './sections/Promocodes';
import Tickets from './sections/Tickets';
import Notifications from './sections/Notifications';
import Newsletters from './sections/Newsletters';

// Утилиты
import {getAuthToken, removeAuthToken, verifyToken} from './utils/auth.js';
import {fetchSectionData, fetchInitialData, notificationApi, dashboardApi, userApi} from './utils/api.js';

function App() {
  // Состояния
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [section, setSection] = useState('dashboard');

  // Данные
  const [users, setUsers] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [tariffs, setTariffs] = useState([]);
  const [promocodes, setPromocodes] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [newsletters, setNewsletters] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);
  const [dashboardStats, setDashboardStats] = useState({
    total_users: 0,
    total_bookings: 0,
    open_tickets: 0
  });

  // UI состояния
  const [hasNewNotifications, setHasNewNotifications] = useState(false);
  const [lastNotificationId, setLastNotificationId] = useState(0);
  const [isChartInitialized, setIsChartInitialized] = useState(false);

  // Refs и hooks
  const toast = useToast();
  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const { isOpen, onOpen, onClose } = useDisclosure();

  // Объект с сеттерами для удобства
  const dataSetters = {
    users: setUsers,
    bookings: setBookings,
    tariffs: setTariffs,
    promocodes: setPromocodes,
    tickets: setTickets,
    notifications: setNotifications,
    newsletters: setNewsletters,
    dashboardStats: setDashboardStats
  };

  // Проверка валидности токена при загрузке
  useEffect(() => {
  const checkAuth = async () => {
    const token = getAuthToken();
    if (token) {
      try {
        await verifyToken(); // теперь используем функцию
        setIsAuthenticated(true);
        setSection('dashboard');
        await fetchInitialData(dataSetters, setLastNotificationId, toast);
      } catch (error) {
        removeAuthToken(); // если есть такая функция
        setIsAuthenticated(false);
      }
    }
    setIsCheckingAuth(false);
  };
  checkAuth();
}, []);

  // При смене вкладки загружаем данные
  useEffect(() => {
    if (isAuthenticated) {
      fetchSectionData(section, dataSetters);
    }
  }, [section, isAuthenticated]);

  // Auto-refresh для уведомлений
  useEffect(() => {
    if (isAuthenticated) {
      const fetchUpdates = async () => {
        try {
          const res = await notificationApi.checkNew(lastNotificationId);
          const newNotifications = res.recent_notifications?.filter(n => !n.is_read) || [];

          if (newNotifications.length > 0) {
            setNotifications(prev => [...newNotifications, ...prev]);
            setLastNotificationId(Math.max(...res.recent_notifications.map(n => n.id), lastNotificationId));
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
          // 📊 Статистика дашборда — только если активна вкладка
          if (section === 'dashboard') {
            const stats = await dashboardApi.getStats();
            setDashboardStats(stats);
          }
        } catch (err) {
          console.error('Ошибка получения уведомлений:', err);
        }
      };

      const interval = setInterval(fetchUpdates, 10000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, lastNotificationId]);

  // Обновляем индикатор новых уведомлений
  useEffect(() => {
    const unreadCount = notifications.filter(n => !n.is_read).length;
    setHasNewNotifications(unreadCount > 0);
  }, [notifications]);

  // Обработчики
  const handleLogin = async () => {
    setIsLoading(true);
    try {
      const res = await axios.post('http://localhost/api/login', { login, password }, { withCredentials: true });
      localStorage.setItem('authToken', res.data.access_token);
      setIsAuthenticated(true);
      setSection('dashboard');
      await fetchInitialData(dataSetters, setLastNotificationId, toast);
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

      if (chartInstanceRef.current) {
        chartInstanceRef.current.destroy();
        chartInstanceRef.current = null;
        setIsChartInitialized(false);
      }

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
      await notificationApi.markRead(notificationId); // заменили axios на API-метод

      setNotifications(prev =>
        prev.map(n => (n.id === notificationId ? { ...n, is_read: true } : n))
      );

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
      await notificationApi.markAllRead(); // заменили axios на API-метод

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

  const openDetailModal = (item, type) => {
    setSelectedItem({ ...item, type });
    onOpen();
  };

  // Рендер секций
  const renderSection = () => {
    const sectionProps = {
      openDetailModal,
      fetchData: () => fetchSectionData(section, dataSetters)
    };

    switch (section) {
      case 'dashboard':
        return (
          <Dashboard
            stats={dashboardStats}
            users={users}
            chartRef={chartRef}
            chartInstanceRef={chartInstanceRef}
            isChartInitialized={isChartInitialized}
            setIsChartInitialized={setIsChartInitialized}
            section={section}
          />
        );
      case 'users':
        return <Users users={users} {...sectionProps} />;
      case 'bookings':
        return <Bookings bookings={bookings} {...sectionProps} />;
      case 'tariffs':
        return <Tariffs tariffs={tariffs} {...sectionProps} />;
      case 'promocodes':
        return <Promocodes promocodes={promocodes} {...sectionProps} />;
      case 'tickets':
        return <Tickets tickets={tickets} {...sectionProps} />;
      case 'notifications':
        return <Notifications notifications={notifications} />;
      case 'newsletters':
        return <Newsletters newsletters={newsletters} />;
      default:
        return (
          <Dashboard
            stats={dashboardStats}
            users={users}
            chartRef={chartRef}
            chartInstanceRef={chartInstanceRef}
            isChartInitialized={isChartInitialized}
            setIsChartInitialized={setIsChartInitialized}
            section={section}
          />
        );
    }
  };

  const handleUpdate = async () => {
    await fetchSectionData('users', dataSetters);
    if (selectedItem?.id) {
      try {

        // const res = await axios.get(`http://localhost/api$/users/{selectedItem.id}`);
        // const updatedUser = res.data;
        const updatedUser = await userApi.getById(selectedItem.id);
        setSelectedItem(prev => ({ ...updatedUser, type: prev.type }));
        return updatedUser; // ✅ вернуть объект
      } catch (error) {
        console.error('Ошибка обновления пользователя:', error);
        return null; // ✅ явно вернуть null при ошибке
      }
    }
    return null;
  };



  // Проверка аутентификации
  if (isCheckingAuth) {
    return (
      <ChakraProvider>
        <Login isLoading={true} />
      </ChakraProvider>
    );
  }

  // Страница логина
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

  // Основное приложение
  return (
    <ChakraProvider>
      <Layout
        section={section}
        setSection={setSection}
        handleLogout={handleLogout}
        login={login}
        notifications={notifications}
        hasNewNotifications={hasNewNotifications}
        markNotificationRead={markNotificationRead}
        markAllNotificationsRead={markAllNotificationsRead}
      >
        {renderSection()}
      </Layout>
      <DetailModal
        isOpen={isOpen}
        onClose={onClose}
        selectedItem={selectedItem}
        onUpdate={handleUpdate}
      />
    </ChakraProvider>
  );
}

export default App;