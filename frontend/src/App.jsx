// App.jsx
import React, { useState, useEffect, useRef } from 'react';
import { ChakraProvider, useToast, useDisclosure } from '@chakra-ui/react';
import axios from 'axios';

// Компоненты
import Login from './components/Login';
import Layout from './components/Layout';
import {
  BookingDetailModal,
  PromocodeDetailModal,
  TariffDetailModal,
  TicketDetailModal,
  UserDetailModal
} from './components/modals';

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
import { getAuthToken, removeAuthToken, verifyToken } from './utils/auth.js';
import {
  fetchSectionData,
  fetchInitialData,
  notificationApi,
  dashboardApi,
  userApi,
  promocodeApi,
  tariffApi
} from './utils/api.js';

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
    notifications: (data) => {
      setNotifications(data);
      if (Array.isArray(data) && data.length > 0) {
        setLastNotificationId(Math.max(...data.map(n => n.id), 0));
      }
    },
    newsletters: setNewsletters,
    dashboardStats: setDashboardStats
  };

  // Проверка валидности токена при загрузке
  useEffect(() => {
    const checkAuth = async () => {
      const token = getAuthToken();
      if (token) {
        try {
          await verifyToken();
          setIsAuthenticated(true);
          setSection('dashboard');
          await fetchInitialData(dataSetters, setLastNotificationId, toast);
        } catch (error) {
          removeAuthToken();
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

  // Отдельный useEffect для статистики дашборда
  useEffect(() => {
    if (isAuthenticated && section === 'dashboard') {
      const fetchDashboardStats = async () => {
        try {
          const stats = await dashboardApi.getStats();
          setDashboardStats(stats);
        } catch (err) {
          console.error('Ошибка получения статистики дашборда:', err);
        }
      };

      // Загружаем статистику сразу при переходе на дашборд
      fetchDashboardStats();

      // Обновляем статистику каждые 30 секунд только для дашборда
      const statsInterval = setInterval(fetchDashboardStats, 30000);
      return () => clearInterval(statsInterval);
    }
  }, [isAuthenticated, section]);

  // Auto-refresh ТОЛЬКО для уведомлений
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
        } catch (err) {
          console.error('Ошибка получения уведомлений:', err);
        }
      };

      // Обновляем уведомления каждые 10 секунд
      const notificationsInterval = setInterval(fetchUpdates, 10000);
      return () => clearInterval(notificationsInterval);
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
      await notificationApi.markRead(notificationId);

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
      await notificationApi.markAllRead();

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

  // ИСПРАВЛЕННАЯ функция handleUpdate
  const handleUpdate = async (updatedData = null) => {
    try {
      if (selectedItem?.type === 'ticket' && updatedData) {
        setSelectedItem(prev => ({ ...updatedData, type: prev.type }));
        setTickets(prev => prev.map(ticket =>
          ticket.id === updatedData.id ? updatedData : ticket
        ));
      } else if (selectedItem?.type === 'promocode') {
        // Для промокодов всегда перезагружаем список
        await fetchSectionData('promocodes', dataSetters);
        if (selectedItem?.id) {
          try {
            const updatedPromocode = await promocodeApi.getById(selectedItem.id);
            setSelectedItem(prev => ({ ...updatedPromocode, type: prev.type }));
          } catch (error) {
            // Промокод мог быть удален
            console.log('Промокод не найден, возможно был удален');
          }
        }
      } else if (selectedItem?.type === 'tariff') {
        // Для тарифов всегда перезагружаем список
        await fetchSectionData('tariffs', dataSetters);
        if (selectedItem?.id) {
          try {
            const updatedTariff = await tariffApi.getById(selectedItem.id);
            setSelectedItem(prev => ({ ...updatedTariff, type: prev.type }));
          } catch (error) {
            console.log('Тариф не найден, возможно был удален');
          }
        }
      } else if (selectedItem?.type === 'user') {
        await fetchSectionData('users', dataSetters);
        const updatedUser = await userApi.getById(selectedItem.id);
        setSelectedItem(prev => ({ ...updatedUser, type: prev.type }));
      } else {
        await fetchSectionData(section, dataSetters);
      }
    } catch (error) {
      console.error('Ошибка обновления:', error);
    }
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
            tickets={tickets}
            bookings={bookings}
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
        return (
          <Tariffs
            tariffs={tariffs}
            openDetailModal={openDetailModal}
            onUpdate={() => fetchSectionData('tariffs', dataSetters)}
          />
        );
      case 'promocodes':
        return (
          <Promocodes
            promocodes={promocodes}
            openDetailModal={openDetailModal}
            onUpdate={() => fetchSectionData('promocodes', dataSetters)}
          />
        );
      case 'tickets':
        return <Tickets tickets={tickets} {...sectionProps} />;
      case 'notifications':
        return (
          <Notifications
            notifications={notifications}
            openDetailModal={openDetailModal}
            setSection={setSection}
            onRefresh={() => fetchSectionData('notifications', dataSetters)}
          />
        );
      case 'newsletters':
        return <Newsletters newsletters={newsletters} />;
      default:
        return (
          <Dashboard
            stats={dashboardStats}
            users={users}
            tickets={tickets}
            bookings={bookings}
            chartRef={chartRef}
            chartInstanceRef={chartInstanceRef}
            isChartInitialized={isChartInitialized}
            setIsChartInitialized={setIsChartInitialized}
            section={section}
          />
        );
    }
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

      {/* Модальные окна для разных типов элементов */}
      {selectedItem?.type === 'user' && (
        <UserDetailModal
          isOpen={isOpen}
          onClose={onClose}
          user={selectedItem}
          onUpdate={handleUpdate}
        />
      )}

      {selectedItem?.type === 'booking' && (
        <BookingDetailModal
          isOpen={isOpen}
          onClose={onClose}
          booking={selectedItem}
        />
      )}

      {selectedItem?.type === 'tariff' && (
        <TariffDetailModal
          isOpen={isOpen}
          onClose={onClose}
          tariff={selectedItem}
          onUpdate={() => fetchSectionData('tariffs', dataSetters)}
        />
      )}

      {selectedItem?.type === 'promocode' && (
        <PromocodeDetailModal
          isOpen={isOpen}
          onClose={onClose}
          promocode={selectedItem}
          onUpdate={() => fetchSectionData('promocodes', dataSetters)}
        />
      )}

      {selectedItem?.type === 'ticket' && (
        <TicketDetailModal
          isOpen={isOpen}
          onClose={onClose}
          ticket={selectedItem}
          onUpdate={handleUpdate}
        />
      )}
    </ChakraProvider>
  );
}

export default App;