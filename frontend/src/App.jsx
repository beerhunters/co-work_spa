import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ChakraProvider, useToast, useDisclosure } from '@chakra-ui/react';

// Компоненты
import Login from './components/Login';
import Layout from './components/Layout';
import NotificationPermissionModal from './components/NotificationPermission';
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
import { getAuthToken, removeAuthToken, verifyToken, login as apiLogin, logout as apiLogout } from './utils/auth.js';
import {
  fetchSectionData,
  fetchInitialData,
  notificationApi,
  dashboardApi,
  userApi,
  promocodeApi,
  tariffApi,
  bookingApi
} from './utils/api.js';
import notificationManager from './utils/notifications';

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
  const [bookingsMeta, setBookingsMeta] = useState({ total_count: 0, page: 1, per_page: 20, total_pages: 0 });
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

  // НОВОЕ: Состояние для фильтров бронирований
  const [bookingFilters, setBookingFilters] = useState({
    page: 1,
    per_page: 20
  });
  const [isBookingsLoading, setIsBookingsLoading] = useState(false);

  // UI состояния
  const [hasNewNotifications, setHasNewNotifications] = useState(false);
  const [lastNotificationId, setLastNotificationId] = useState(0);
  const [isChartInitialized, setIsChartInitialized] = useState(false);

  // Состояния для браузерных уведомлений
  const [isNotificationPermissionOpen, setNotificationPermissionOpen] = useState(false);
  const [notificationStatus, setNotificationStatus] = useState(null);
  const [soundEnabled, setSoundEnabled] = useState(true);

  // Refs и hooks
  const toast = useToast();
  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const { isOpen, onOpen, onClose } = useDisclosure();

  // Объект с сеттерами для удобства
  const dataSetters = {
    users: setUsers,
    bookings: setBookings,
    bookingsMeta: setBookingsMeta,
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

  // НОВОЕ: Функция для загрузки бронирований с фильтрами
  const loadBookingsWithFilters = useCallback(async (filters = bookingFilters) => {
    setIsBookingsLoading(true);
    try {
      console.log('Загружаем бронирования с фильтрами:', filters);

      const response = await bookingApi.getAllDetailed(filters);

      console.log('Получен ответ:', {
        bookingsCount: response.bookings?.length || 0,
        totalCount: response.total_count,
        page: response.page,
        totalPages: response.total_pages
      });

      setBookings(response.bookings || []);
      setBookingsMeta({
        total_count: response.total_count || 0,
        page: response.page || 1,
        per_page: response.per_page || 20,
        total_pages: response.total_pages || 1
      });

    } catch (error) {
      console.error('Ошибка загрузки бронирований:', error);

      // Детальная обработка ошибок
      if (error.message?.includes('422')) {
        console.error('422 ошибка валидации при загрузке бронирований');
        toast({
          title: 'Ошибка валидации',
          description: 'Проблема с параметрами запроса бронирований',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }

      // Fallback
      try {
        console.log('Пробуем резервный способ загрузки...');
        const fallbackData = await bookingApi.getAll(filters);
        console.log('Резервная загрузка успешна:', fallbackData.length, 'записей');

        setBookings(Array.isArray(fallbackData) ? fallbackData : []);
        setBookingsMeta({
          total_count: fallbackData.length,
          page: filters.page || 1,
          per_page: filters.per_page || 20,
          total_pages: Math.ceil(fallbackData.length / (filters.per_page || 20))
        });

        toast({
          title: 'Частичная загрузка',
          description: 'Данные загружены в упрощенном режиме',
          status: 'warning',
          duration: 3000,
        });
      } catch (fallbackError) {
        console.error('Fallback ошибка:', fallbackError);

        setBookings([]);
        setBookingsMeta({ total_count: 0, page: 1, per_page: 20, total_pages: 0 });

        toast({
          title: 'Ошибка загрузки',
          description: 'Не удалось загрузить бронирования. Попробуйте обновить страницу.',
          status: 'error',
          duration: 7000,
          isClosable: true,
        });
      }
    } finally {
      setIsBookingsLoading(false);
    }
  }, [bookingFilters, toast]);

  // НОВОЕ: Обработчик изменения фильтров от компонента Bookings
  const handleBookingFiltersChange = useCallback((newFilters) => {
    console.log('Получены новые фильтры бронирований:', newFilters);

    // Проверяем, является ли это сбросом к дефолтным значениям
    const isDefaultFilters = (
      newFilters.page === 1 &&
      newFilters.per_page === 20 &&
      !newFilters.status_filter &&
      !newFilters.user_query
    );

    if (isDefaultFilters) {
      console.log('Обнаружен сброс к дефолтным фильтрам');
      setBookingFilters({ page: 1, per_page: 20 });
    } else {
      setBookingFilters(prevFilters => {
        const updatedFilters = { ...prevFilters, ...newFilters };
        console.log('Обновленные фильтры бронирований:', updatedFilters);
        return updatedFilters;
      });
    }
  }, []);

  // НОВОЕ: Загружаем бронирования при изменении фильтров
  useEffect(() => {
    if (isAuthenticated && section === 'bookings') {
      console.log('Фильтры бронирований изменились, загружаем данные:', bookingFilters);
      loadBookingsWithFilters(bookingFilters);
    }
  }, [bookingFilters, isAuthenticated, section, loadBookingsWithFilters]);

  // Улучшенная функция для загрузки данных секций
  const fetchSectionDataEnhanced = async (sectionName, params = {}) => {
    try {
      switch (sectionName) {
        case 'bookings':
          // Для бронирований используем новую функцию с фильтрами
          if (Object.keys(params).length > 0) {
            // Если переданы конкретные параметры, используем их
            await loadBookingsWithFilters(params);
          } else {
            // Иначе используем текущие фильтры
            await loadBookingsWithFilters(bookingFilters);
          }
          break;

        default:
          // Для остальных секций используем стандартную загрузку
          await fetchSectionData(sectionName, dataSetters);
          break;
      }
    } catch (error) {
      console.error(`Общая ошибка загрузки данных для ${sectionName}:`, error);

      toast({
        title: 'Ошибка загрузки',
        description: `Не удалось загрузить данные для раздела ${sectionName}`,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Инициализация браузерных уведомлений
  useEffect(() => {
    const initBrowserNotifications = async () => {
      if (!isAuthenticated) return;

      try {
        await notificationManager.init();
        const status = notificationManager.getStatus();
        setNotificationStatus(status);

        const hasAsked = localStorage.getItem('notificationPermissionAsked');
        const isEnabled = localStorage.getItem('notificationsEnabled');

        if (!hasAsked && status.isSupported && status.permission === 'default') {
          setTimeout(() => {
            setNotificationPermissionOpen(true);
            localStorage.setItem('notificationPermissionAsked', 'true');
          }, 3000);
        } else if (isEnabled === 'true' && status.permission === 'granted') {
          notificationManager.enable();
        }

        const savedSoundSetting = localStorage.getItem('notificationSoundEnabled');
        setSoundEnabled(savedSoundSetting !== 'false');
      } catch (error) {
        console.error('Ошибка инициализации уведомлений:', error);
      }
    };

    initBrowserNotifications();
  }, [isAuthenticated]);

  // Обработка новых уведомлений для браузерных уведомлений
  useEffect(() => {
    if (!isAuthenticated || !notificationStatus?.isEnabled || !notifications.length || !soundEnabled) return;

    const unreadNotifications = notifications.filter(n => !n.is_read);

    if (unreadNotifications.length > 0) {
      const shownNotifications = JSON.parse(localStorage.getItem('shownNotifications') || '[]');

      unreadNotifications.forEach(notification => {
        if (!shownNotifications.includes(notification.id)) {
          notificationManager.handleNotification(notification);
          shownNotifications.push(notification.id);
        }
      });

      localStorage.setItem('shownNotifications', JSON.stringify(shownNotifications.slice(-50)));
    }
  }, [notifications, notificationStatus, soundEnabled, isAuthenticated]);

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

  // При смене вкладки загружаем данные (исключая bookings - они загружаются через фильтры)
  useEffect(() => {
    if (isAuthenticated && section !== 'bookings') {
      fetchSectionDataEnhanced(section);
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

      fetchDashboardStats();
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

      const notificationsInterval = setInterval(fetchUpdates, 10000);
      return () => clearInterval(notificationsInterval);
    }
  }, [isAuthenticated, lastNotificationId]);

  // Обновляем индикатор новых уведомлений
  useEffect(() => {
    const unreadCount = notifications.filter(n => !n.is_read).length;
    setHasNewNotifications(unreadCount > 0);
  }, [notifications]);

  // Обработчики для браузерных уведомлений
  const handleNotificationPermissionGranted = () => {
    const status = notificationManager.getStatus();
    setNotificationStatus(status);
    toast({
      title: "Уведомления включены",
      description: "Теперь вы будете получать браузерные уведомления",
      status: "success",
      duration: 3000,
    });
  };

  const handleToggleNotificationSound = (enabled) => {
    setSoundEnabled(enabled);
    localStorage.setItem('notificationSoundEnabled', enabled.toString());

    if (enabled) {
      notificationManager.enable();
    } else {
      notificationManager.disable();
    }

    toast({
      title: enabled ? "Звуковые уведомления включены" : "Звуковые уведомления отключены",
      status: enabled ? "success" : "info",
      duration: 2000,
    });
  };

  // Обработчики
  const handleLogin = async () => {
    setIsLoading(true);
    try {
      await apiLogin({ login, password });
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
      await apiLogout();
      setIsAuthenticated(false);
      setSection('login');
      setLogin('');
      setPassword('');

      // Сбрасываем фильтры бронирований
      setBookingFilters({ page: 1, per_page: 20 });

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

  // Улучшенная функция openDetailModal с проверками
  const openDetailModal = async (item, type) => {
    try {
      console.log('Открытие модального окна:', type, item.id);

      if (type === 'booking') {
        try {
          const validation = await bookingApi.validateId(item.id);
          if (!validation.exists) {
            toast({
              title: 'Бронирование не найдено',
              description: 'Бронирование могло быть удалено',
              status: 'error',
              duration: 5000,
            });
            return;
          }

          console.log('Валидация пройдена, открываем модальное окно');
          setSelectedItem({ ...item, type });
        } catch (error) {
          console.error('Ошибка валидации бронирования:', error);

          if (error.message?.includes('422')) {
            toast({
              title: 'Ошибка валидации',
              description: 'Неверный ID бронирования',
              status: 'error',
              duration: 5000,
            });
            return;
          }

          console.log('Используем fallback для открытия модального окна');
          setSelectedItem({ ...item, type });
        }
      } else {
        setSelectedItem({ ...item, type });
      }

      onOpen();
    } catch (error) {
      console.error('Ошибка открытия модального окна:', error);

      toast({
        title: 'Ошибка',
        description: 'Не удалось открыть детальную информацию',
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Улучшенная функция handleUpdate с дополнительной валидацией
  const handleUpdate = async (updatedData = null) => {
    try {
      console.log('Обновление данных:', selectedItem?.type, updatedData);

      if (selectedItem?.type === 'ticket' && updatedData) {
        setSelectedItem(prev => ({ ...updatedData, type: prev.type }));
        setTickets(prev => prev.map(ticket =>
          ticket.id === updatedData.id ? updatedData : ticket
        ));
      } else if (selectedItem?.type === 'promocode') {
        await fetchSectionDataEnhanced('promocodes');
        if (selectedItem?.id) {
          try {
            const updatedPromocode = await promocodeApi.getById(selectedItem.id);
            setSelectedItem(prev => ({ ...updatedPromocode, type: prev.type }));
          } catch (error) {
            console.log('Промокод не найден, возможно был удален');
            onClose();
          }
        }
      } else if (selectedItem?.type === 'tariff') {
        await fetchSectionDataEnhanced('tariffs');
        if (selectedItem?.id) {
          try {
            const updatedTariff = await tariffApi.getById(selectedItem.id);
            setSelectedItem(prev => ({ ...updatedTariff, type: prev.type }));
          } catch (error) {
            console.log('Тариф не найден, возможно был удален');
            onClose();
          }
        }
      } else if (selectedItem?.type === 'user') {
        await fetchSectionDataEnhanced('users');
        if (selectedItem?.id) {
          try {
            const updatedUser = await userApi.getById(selectedItem.id);
            setSelectedItem(prev => ({ ...updatedUser, type: prev.type }));
          } catch (error) {
            console.log('Пользователь не найден');
            onClose();
          }
        }
      } else if (selectedItem?.type === 'booking') {
        // Обновляем список бронирований с текущими фильтрами
        console.log('Обновление списка бронирований...');
        await loadBookingsWithFilters(bookingFilters);

        if (selectedItem?.id) {
          try {
            console.log('Обновление детального бронирования:', selectedItem.id);
            const updatedBooking = await bookingApi.getByIdDetailed(selectedItem.id);
            setSelectedItem(prev => ({ ...updatedBooking, type: prev.type }));
            console.log('Детальное бронирование обновлено');
          } catch (error) {
            console.error('Ошибка обновления детального бронирования:', error);

            if (error.message?.includes('422')) {
              toast({
                title: 'Ошибка обновления',
                description: 'Проблема с загрузкой обновленных данных бронирования',
                status: 'error',
                duration: 5000,
              });
            } else {
              console.log('Бронирование не найдено или удалено');
              onClose();
            }
          }
        }
      } else {
        await fetchSectionDataEnhanced(section);
      }

      console.log('Обновление завершено успешно');
    } catch (error) {
      console.error('Ошибка обновления:', error);

      toast({
        title: 'Ошибка обновления',
        description: 'Не удалось обновить данные. Попробуйте еще раз.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Рендер секций
  const renderSection = () => {
    const sectionProps = {
      openDetailModal,
      fetchData: () => fetchSectionDataEnhanced(section)
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
        return (
          <Bookings
            bookings={bookings}
            bookingsMeta={bookingsMeta}
            {...sectionProps}
            onRefresh={() => loadBookingsWithFilters(bookingFilters)}
            onFiltersChange={handleBookingFiltersChange}
            isLoading={isBookingsLoading}
          />
        );
      case 'tariffs':
        return (
          <Tariffs
            tariffs={tariffs}
            openDetailModal={openDetailModal}
            onUpdate={() => fetchSectionDataEnhanced('tariffs')}
          />
        );
      case 'promocodes':
        return (
          <Promocodes
            promocodes={promocodes}
            openDetailModal={openDetailModal}
            onUpdate={() => fetchSectionDataEnhanced('promocodes')}
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
            onRefresh={() => fetchSectionDataEnhanced('notifications')}
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
        notificationStatus={notificationStatus}
        soundEnabled={soundEnabled}
        onToggleNotificationSound={handleToggleNotificationSound}
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
          onUpdate={handleUpdate}
        />
      )}

      {selectedItem?.type === 'tariff' && (
        <TariffDetailModal
          isOpen={isOpen}
          onClose={onClose}
          tariff={selectedItem}
          onUpdate={() => fetchSectionDataEnhanced('tariffs')}
        />
      )}

      {selectedItem?.type === 'promocode' && (
        <PromocodeDetailModal
          isOpen={isOpen}
          onClose={onClose}
          promocode={selectedItem}
          onUpdate={() => fetchSectionDataEnhanced('promocodes')}
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

      {/* Модальное окно запроса разрешений на уведомления */}
      <NotificationPermissionModal
        isOpen={isNotificationPermissionOpen}
        onClose={() => setNotificationPermissionOpen(false)}
        onPermissionGranted={handleNotificationPermissionGranted}
      />
    </ChakraProvider>
  );
}

export default App;