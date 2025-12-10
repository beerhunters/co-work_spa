import React, { useState, useEffect, useRef, useCallback, lazy, Suspense } from 'react';
import { ChakraProvider, useToast, useDisclosure, Spinner, Center } from '@chakra-ui/react';

// Eager load: Login and Layout (critical path - always needed)
import Login from './components/Login';
import Layout from './components/Layout';
import NotificationPermissionModal from './components/NotificationPermission';
import GlobalLoadingBar from './components/GlobalLoadingBar';
import { GlobalLoadingProvider, useGlobalLoading } from './hooks/useGlobalLoading';

// Lazy load: Modals (P-MED-4 - load only when opened)
// Performance: ~50KB saved from initial bundle
const BookingDetailModal = lazy(() => import('./components/modals').then(m => ({ default: m.BookingDetailModal })));
const PromocodeDetailModal = lazy(() => import('./components/modals').then(m => ({ default: m.PromocodeDetailModal })));
const TariffDetailModal = lazy(() => import('./components/modals').then(m => ({ default: m.TariffDetailModal })));
const OfficeDetailModal = lazy(() => import('./components/modals/OfficeDetailModal'));
const TicketDetailModal = lazy(() => import('./components/modals').then(m => ({ default: m.TicketDetailModal })));
const UserDetailModal = lazy(() => import('./components/modals').then(m => ({ default: m.UserDetailModal })));
const AdminDetailModal = lazy(() => import('./components/modals').then(m => ({ default: m.AdminDetailModal })));

// Lazy load: All sections (P-MED-4 - route-based code splitting)
// Performance: ~950KB deferred, only ~150KB initial load
const Dashboard = lazy(() => import('./sections/Dashboard'));
const Users = lazy(() => import('./sections/Users'));
const Bookings = lazy(() => import('./sections/Bookings'));
const Tariffs = lazy(() => import('./sections/Tariffs'));
const Offices = lazy(() => import('./sections/Offices'));
const Promocodes = lazy(() => import('./sections/Promocodes'));
const Tickets = lazy(() => import('./sections/Tickets'));
const Notifications = lazy(() => import('./sections/Notifications'));
const Newsletters = lazy(() => import('./sections/Newsletters'));
const Emails = lazy(() => import('./sections/Emails'));
const Admins = lazy(() => import('./sections/Admins'));
const Backups = lazy(() => import('./sections/Backups'));
const SystemMonitoring = lazy(() => import('./sections/SystemMonitoring'));
const Logging = lazy(() => import('./sections/Logging'));
const IPBans = lazy(() => import('./sections/IPBans'));

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
  officeApi,
  bookingApi,
  ticketApi,
  adminApi,
} from './utils/api.js';
import notificationManager from './utils/notifications';
import { createLogger } from './utils/logger.js';
import { OnboardingProvider, useOnboarding } from './contexts/OnboardingContext';

const logger = createLogger('App');

// Loading fallback component for Suspense (P-MED-4)
// Displayed while lazy-loaded components are being fetched
const LoadingFallback = () => (
  <Center h="100vh">
    <Spinner size="xl" color="blue.500" thickness="4px" />
  </Center>
);

function AppContent() {
  const { autoStartTour } = useOnboarding();
  const { isLoading: isGlobalLoading } = useGlobalLoading();

  // Защита от ошибок рендеринга
  if (typeof useState === 'undefined') {
    return <div>Loading...</div>;
  }
  // Основные состояния
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [section, setSection] = useState('dashboard');
  const [currentAdmin, setCurrentAdmin] = useState(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    const saved = localStorage.getItem('sidebarCollapsed');
    return saved === 'true';
  });
  const [isSidebarHovered, setIsSidebarHovered] = useState(false);

  // Данные приложения
  const [users, setUsers] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [bookingsMeta, setBookingsMeta] = useState({ total_count: 0, page: 1, per_page: 20, total_pages: 0 });
  const [tariffs, setTariffs] = useState([]);
  const [offices, setOffices] = useState([]);
  const [promocodes, setPromocodes] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [ticketsMeta, setTicketsMeta] = useState({ total_count: 0, page: 1, per_page: 20, total_pages: 0 });
  const [notifications, setNotifications] = useState([]);
  const [newsletters, setNewsletters] = useState([]);
  const [admins, setAdmins] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);
  const [dashboardStats, setDashboardStats] = useState({
    total_users: 0,
    total_bookings: 0,
    open_tickets: 0
  });

  // Фильтры
  const [bookingFilters, setBookingFilters] = useState({ page: 1, per_page: 20 });
  const [isBookingsLoading, setIsBookingsLoading] = useState(false);
  const [ticketFilters, setTicketFilters] = useState({ page: 1, per_page: 20 });
  const [isTicketsLoading, setIsTicketsLoading] = useState(false);

  // UI состояния
  const [hasNewNotifications, setHasNewNotifications] = useState(false);
  const [lastNotificationId, setLastNotificationId] = useState(0);
  const [isChartInitialized, setIsChartInitialized] = useState(false);
  const [isNotificationPermissionOpen, setNotificationPermissionOpen] = useState(false);
  const [notificationStatus, setNotificationStatus] = useState(null);
  const [soundEnabled, setSoundEnabled] = useState(true);

  // Refs и hooks
  const toast = useToast();
  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const { isOpen, onOpen, onClose } = useDisclosure();

  // Сеттеры данных
  const dataSetters = {
    users: setUsers,
    bookings: setBookings,
    bookingsMeta: setBookingsMeta,
    tariffs: setTariffs,
    offices: setOffices,
    promocodes: setPromocodes,
    tickets: setTickets,
    ticketsMeta: setTicketsMeta,
    notifications: (data) => {
      setNotifications(data);
      if (Array.isArray(data) && data.length > 0) {
        setLastNotificationId(Math.max(...data.map(n => n.id), 0));
      }
    },
    newsletters: setNewsletters,
    admins: setAdmins,
    dashboardStats: setDashboardStats
  };

  // Функция проверки прав доступа
    const hasPermission = useCallback((permission) => {
    // Защита от вызова до инициализации
    if (!currentAdmin) {
      logger.debug('hasPermission вызван до загрузки currentAdmin');
      return false;
    }

  // Супер админ имеет все права
  if (currentAdmin.role === 'super_admin') {
    return true;
  }

  // Проверяем наличие разрешений и самого разрешения
  if (!currentAdmin.permissions || !Array.isArray(currentAdmin.permissions)) {
    logger.debug('permissions не найдены или не являются массивом');
    return false;
  }

  return currentAdmin.permissions.includes(permission);
}, [currentAdmin]);

  // Загрузка профиля текущего администратора
  const loadCurrentAdminProfile = useCallback(async () => {
    try {
      const profile = await adminApi.getCurrentProfile();
      setCurrentAdmin(profile);
      logger.debug('Профиль текущего админа загружен:', profile);
    } catch (error) {
      logger.error('Ошибка загрузки профиля админа:', error);
      if (error.response?.status === 401) {
        removeAuthToken();
        setIsAuthenticated(false);
        setCurrentAdmin(null);
      }
    }
  }, []);

  // Функция переключения состояния sidebar
  const toggleSidebar = useCallback(() => {
    setIsSidebarCollapsed(prev => {
      const newState = !prev;
      localStorage.setItem('sidebarCollapsed', newState.toString());
      return newState;
    });
  }, []);

  // Загрузка тикетов с фильтрами и проверкой прав
  const loadTicketsWithFilters = useCallback(async (filters = ticketFilters) => {
    if (!hasPermission('view_tickets')) {
      toast({
        title: 'Доступ запрещен',
        description: 'У вас нет прав для просмотра тикетов',
        status: 'error',
        duration: 5000,
      });
      return;
    }

    setIsTicketsLoading(true);
    try {
      logger.debug('Загружаем тикеты с фильтрами:', filters);
      const response = await ticketApi.getAllDetailed(filters);

      logger.debug('Получен ответ тикетов:', {
        ticketsCount: response.tickets?.length || 0,
        totalCount: response.total_count,
        page: response.page,
        totalPages: response.total_pages
      });

      setTickets(response.tickets || []);
      setTicketsMeta({
        total_count: response.total_count || 0,
        page: response.page || 1,
        per_page: response.per_page || 20,
        total_pages: response.total_pages || 1
      });

    } catch (error) {
      logger.error('Ошибка загрузки тикетов:', error);

      try {
        logger.info('Пробуем резервный способ загрузки тикетов...');
        const fallbackData = await ticketApi.getAll(filters);
        logger.info('Резервная загрузка тикетов успешна', { count: fallbackData.length });

        setTickets(Array.isArray(fallbackData) ? fallbackData : []);
        setTicketsMeta({
          total_count: fallbackData.length,
          page: filters.page || 1,
          per_page: filters.per_page || 20,
          total_pages: Math.ceil(fallbackData.length / (filters.per_page || 20))
        });

        toast({
          title: 'Частичная загрузка',
          description: 'Тикеты загружены в упрощенном режиме',
          status: 'warning',
          duration: 3000,
        });
      } catch (fallbackError) {
        logger.error('Fallback ошибка тикетов:', fallbackError);
        setTickets([]);
        setTicketsMeta({ total_count: 0, page: 1, per_page: 20, total_pages: 0 });

        toast({
          title: 'Ошибка загрузки',
          description: 'Не удалось загрузить тикеты. Попробуйте обновить страницу.',
          status: 'error',
          duration: 7000,
          isClosable: true,
        });
      }
    } finally {
      setIsTicketsLoading(false);
    }
  }, [ticketFilters, toast, hasPermission]);

  // Обработчик изменения фильтров тикетов
  const handleTicketFiltersChange = useCallback((newFilters) => {
    logger.debug('Получены новые фильтры тикетов:', newFilters);

    const isDefaultFilters = (
      newFilters.page === 1 &&
      newFilters.per_page === 20 &&
      !newFilters.status &&
      !newFilters.user_query
    );

    if (isDefaultFilters) {
      logger.debug('Обнаружен сброс к дефолтным фильтрам тикетов');
      setTicketFilters({ page: 1, per_page: 20 });
    } else {
      setTicketFilters(prevFilters => {
        const updatedFilters = { ...prevFilters, ...newFilters };
        logger.debug('Обновленные фильтры тикетов:', updatedFilters);
        return updatedFilters;
      });
    }
  }, []);

  // Загрузка бронирований с фильтрами и проверкой прав
  const loadBookingsWithFilters = useCallback(async (filters = bookingFilters) => {
    if (!hasPermission('view_bookings')) {
      toast({
        title: 'Доступ запрещен',
        description: 'У вас нет прав для просмотра бронирований',
        status: 'error',
        duration: 5000,
      });
      return;
    }

    setIsBookingsLoading(true);
    try {
      logger.debug('Загружаем бронирования с фильтрами:', filters);
      const response = await bookingApi.getAllDetailed(filters);

      logger.debug('Получен ответ:', {
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
      logger.error('Ошибка загрузки бронирований:', error);

      if (error.message?.includes('422')) {
        logger.error('422 ошибка валидации при загрузке бронирований');
        toast({
          title: 'Ошибка валидации',
          description: 'Проблема с параметрами запроса бронирований',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }

      try {
        logger.info('Пробуем резервный способ загрузки...');
        const fallbackData = await bookingApi.getAll(filters);
        logger.info('Резервная загрузка успешна', { count: fallbackData.length });

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
        logger.error('Fallback ошибка:', fallbackError);
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
  }, [bookingFilters, toast, hasPermission]);

  // Обработчик изменения фильтров бронирований
  const handleBookingFiltersChange = useCallback((newFilters) => {
    logger.debug('Получены новые фильтры бронирований:', newFilters);

    const isDefaultFilters = (
      newFilters.page === 1 &&
      newFilters.per_page === 20 &&
      !newFilters.status_filter &&
      !newFilters.tariff_filter &&
      !newFilters.user_query
    );

    if (isDefaultFilters) {
      logger.debug('Обнаружен сброс к дефолтным фильтрам');
      setBookingFilters({ page: 1, per_page: 20 });
    } else {
      setBookingFilters(prevFilters => {
        const updatedFilters = { ...prevFilters, ...newFilters };
        logger.debug('Обновленные фильтры бронирований:', updatedFilters);
        return updatedFilters;
      });
    }
  }, []);

  // Загрузка данных секций с проверкой прав
  const fetchSectionDataEnhanced = async (sectionName, params = {}) => {
    try {
      const sectionPermissions = {
        users: 'view_users',
        bookings: 'view_bookings',
        tariffs: 'view_tariffs',
        offices: 'view_offices',
        promocodes: 'view_promocodes',
        tickets: 'view_tickets',
        notifications: 'view_notifications',
        newsletters: 'view_telegram_newsletters',
        emails: 'view_email_campaigns',
        admins: 'manage_admins',
        dashboard: 'view_dashboard'
      };

      const requiredPermission = sectionPermissions[sectionName];
      if (requiredPermission && !hasPermission(requiredPermission)) {
        toast({
          title: 'Доступ запрещен',
          description: `У вас нет прав для доступа к разделу "${sectionName}"`,
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
        return;
      }

      switch (sectionName) {
        case 'bookings':
          if (Object.keys(params).length > 0) {
            await loadBookingsWithFilters(params);
          } else {
            await loadBookingsWithFilters(bookingFilters);
          }
          break;

        case 'tickets':
          if (Object.keys(params).length > 0) {
            await loadTicketsWithFilters(params);
          } else {
            await loadTicketsWithFilters(ticketFilters);
          }
          break;

        case 'admins':
          if (currentAdmin?.role === 'super_admin') {
            await fetchSectionData(sectionName, dataSetters);
          } else {
            toast({
              title: 'Доступ запрещен',
              description: 'Только главный администратор может управлять администраторами',
              status: 'error',
              duration: 5000,
            });
          }
          break;

        default:
          await fetchSectionData(sectionName, dataSetters);
          break;
      }
    } catch (error) {
      logger.error(`Общая ошибка загрузки данных для ${sectionName}`, error);

      if (error.response?.status === 403) {
        toast({
          title: 'Доступ запрещен',
          description: 'У вас недостаточно прав для выполнения этого действия',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      } else {
        toast({
          title: 'Ошибка загрузки',
          description: `Не удалось загрузить данные для раздела ${sectionName}`,
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    }
  };

  // Effects для загрузки данных при изменении фильтров
  useEffect(() => {
    if (isAuthenticated && section === 'tickets' && currentAdmin) {
      logger.debug('Фильтры тикетов изменились, загружаем данные:', ticketFilters);
      loadTicketsWithFilters(ticketFilters);
    }
  }, [ticketFilters, isAuthenticated, section, currentAdmin, loadTicketsWithFilters]);

  useEffect(() => {
    if (isAuthenticated && section === 'bookings' && currentAdmin) {
      logger.debug('Фильтры бронирований изменились, загружаем данные:', bookingFilters);
      loadBookingsWithFilters(bookingFilters);
    }
  }, [bookingFilters, isAuthenticated, section, currentAdmin, loadBookingsWithFilters]);

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
        logger.error('Ошибка инициализации уведомлений:', error);
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

  // Проверка аутентификации при загрузке
  useEffect(() => {
    const checkAuth = async () => {
      const token = getAuthToken();
      if (token) {
        try {
          await verifyToken();
          setIsAuthenticated(true);
          setSection('dashboard');

          await loadCurrentAdminProfile();
          await fetchInitialData(dataSetters, setLastNotificationId, toast);
        } catch (error) {
          removeAuthToken();
          setIsAuthenticated(false);
          setCurrentAdmin(null);
        }
      }
      setIsCheckingAuth(false);
    };
    checkAuth();
  }, [loadCurrentAdminProfile]);

  // Загрузка данных при смене секции
  useEffect(() => {
    if (isAuthenticated && currentAdmin && section !== 'bookings' && section !== 'tickets') {
      fetchSectionDataEnhanced(section);
    }
  }, [section, isAuthenticated, currentAdmin]);

  // Загрузка статистики дашборда
  useEffect(() => {
    if (isAuthenticated && currentAdmin && section === 'dashboard' && hasPermission('view_dashboard')) {
      const fetchDashboardStats = async () => {
        try {
          const stats = await dashboardApi.getStats();
          setDashboardStats(stats);
        } catch (err) {
          logger.error('Ошибка получения статистики дашборда:', err);
          
          // Показываем уведомление пользователю только если это не ошибка авторизации
          if (err.response?.status !== 401) {
            toast({
              title: 'Ошибка загрузки статистики',
              description: 'Не удалось загрузить статистику дашборда. Попробуйте обновить страницу.',
              status: 'error',
              duration: 5000,
              isClosable: true,
              position: 'top-right',
            });
          }
          
          // Устанавливаем значения по умолчанию
          setDashboardStats({
            total_users: 0,
            total_bookings: 0,
            open_tickets: 0
          });
        }
      };

      fetchDashboardStats();
      const statsInterval = setInterval(fetchDashboardStats, 30000);
      return () => clearInterval(statsInterval);
    }
  }, [isAuthenticated, section, currentAdmin, toast, hasPermission]);

  // Auto-refresh уведомлений
  useEffect(() => {
    if (isAuthenticated && hasPermission('view_notifications')) {
      let retryCount = 0;
      const maxRetries = 3;
      
      const fetchUpdates = async () => {
        try {
          const res = await notificationApi.checkNew(lastNotificationId);
          const newNotifications = res.recent_notifications?.filter(n => !n.is_read) || [];

          // Сбрасываем счетчик ретраев при успешном запросе
          retryCount = 0;

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
          // Увеличиваем счетчик ретраев
          retryCount++;
          
          // Не логируем Network Error как ошибки - это обычные сетевые проблемы
          if (err.message === 'Network Error') {
            logger.debug(`Network Error при проверке уведомлений (попытка ${retryCount}/${maxRetries})`);
            
            // Не показываем toast при Network Error - это слишком шумно
            return;
          }
          
          logger.error('Ошибка получения уведомлений:', err);
          
          // Показываем уведомление пользователю только если это не ошибка авторизации 
          // и не Network Error, и мы исчерпали попытки
          if (err.response?.status !== 401 && retryCount >= maxRetries) {
            toast({
              title: 'Ошибка загрузки уведомлений',
              description: 'Не удалось загрузить новые уведомления. Проверьте соединение.',
              status: 'error',
              duration: 3000,
              isClosable: true,
              position: 'top-right',
            });
          }
        }
      };

      const notificationsInterval = setInterval(fetchUpdates, 10000);
      return () => clearInterval(notificationsInterval);
    }
  }, [isAuthenticated, lastNotificationId, currentAdmin]);

  // Обновление индикатора новых уведомлений
  useEffect(() => {
    const unreadCount = notifications.filter(n => !n.is_read).length;
    setHasNewNotifications(unreadCount > 0);
  }, [notifications]);

  // Автозапуск onboarding тура при первом входе
  useEffect(() => {
    if (isAuthenticated && currentAdmin && section === 'dashboard') {
      // Проверяем, был ли уже показан онбординг
      const hasSeenOnboarding = localStorage.getItem('onboarding_completed');

      if (!hasSeenOnboarding) {
        // Запускаем тур с задержкой в 2 секунды после загрузки дашборда
        const timer = setTimeout(() => {
          logger.info('Запуск onboarding тура для нового администратора');
          autoStartTour('dashboard');
        }, 2000);

        return () => clearTimeout(timer);
      }
    }
  }, [isAuthenticated, currentAdmin, section, autoStartTour]);

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

  // Обработчик входа
  const handleLogin = async () => {
    setIsLoading(true);
    try {
      await apiLogin({ login, password });
      setIsAuthenticated(true);
      setSection('dashboard');

      await loadCurrentAdminProfile();
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

  // Обработчик выхода
  const handleLogout = async () => {
    try {
      await apiLogout();
      setIsAuthenticated(false);
      setCurrentAdmin(null);
      setSection('login');
      setLogin('');
      setPassword('');

      setBookingFilters({ page: 1, per_page: 20 });
      setTicketFilters({ page: 1, per_page: 20 });

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
      logger.error('Ошибка выхода:', error);
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

  // Обработчик пометки уведомления как прочитанного
  const markNotificationRead = async (notificationId, targetUrl) => {
    try {
      await notificationApi.markRead(notificationId);

      setNotifications(prev =>
        prev.map(n => (n.id === notificationId ? { ...n, is_read: true } : n))
      );

      if (targetUrl) {
        const urlParts = targetUrl.split('/');
        if (urlParts.length >= 2) {
          const targetSection = urlParts[1];

          const sectionPermissions = {
            users: 'view_users',
            bookings: 'view_bookings',
            tariffs: 'view_tariffs',
            offices: 'view_offices',
            promocodes: 'view_promocodes',
            tickets: 'view_tickets',
            notifications: 'view_notifications',
            newsletters: 'view_telegram_newsletters',
            emails: 'view_email_campaigns',
            admins: 'manage_admins',
            dashboard: 'view_dashboard'
          };

          const requiredPermission = sectionPermissions[targetSection];
          if (!requiredPermission || hasPermission(requiredPermission)) {
            setSection(targetSection);
          } else {
            toast({
              title: 'Доступ запрещен',
              description: `У вас нет прав для доступа к разделу "${targetSection}"`,
              status: 'error',
              duration: 5000,
            });
          }
        }
      }
    } catch (error) {
      logger.error('Ошибка при пометке уведомления:', error);
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

  // Обработчик пометки всех уведомлений как прочитанных
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
      logger.error('Ошибка при пометке всех уведомлений:', error);
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

  // Обработчик открытия модального окна
  const openDetailModal = async (item, type) => {
    try {
      logger.debug('Открытие модального окна:', { type, id: item.id });

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

          logger.debug('Валидация пройдена, открываем модальное окно');
          setSelectedItem({ ...item, type });
        } catch (error) {
          logger.error('Ошибка валидации бронирования:', error);

          if (error.message?.includes('422')) {
            toast({
              title: 'Ошибка валидации',
              description: 'Неверный ID бронирования',
              status: 'error',
              duration: 5000,
            });
            return;
          }

          logger.info('Используем fallback для открытия модального окна');
          setSelectedItem({ ...item, type });
        }
      } else {
        setSelectedItem({ ...item, type });
      }

      onOpen();
    } catch (error) {
      logger.error('Ошибка открытия модального окна:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось открыть детальную информацию',
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Обработчик обновления данных
  const handleUpdate = async (updatedData = null) => {
    try {
      logger.debug('Обновление данных:', { type: selectedItem?.type, data: updatedData });

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
            logger.info('Промокод не найден, возможно был удален');
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
            logger.info('Тариф не найден, возможно был удален');
            onClose();
          }
        }
      } else if (selectedItem?.type === 'office') {
        await fetchSectionDataEnhanced('offices');
        if (selectedItem?.id) {
          try {
            const updatedOffice = await officeApi.getById(selectedItem.id);
            setSelectedItem(prev => ({ ...updatedOffice, type: prev.type }));
          } catch (error) {
            logger.info('Офис не найден, возможно был удален');
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
            logger.info('Пользователь не найден');
            onClose();
          }
        }
      } else if (selectedItem?.type === 'admin') {
        logger.debug('Обновление админов...');
        await fetchSectionDataEnhanced('admins');

        if (updatedData) {
          setSelectedItem(prev => ({ ...updatedData, type: prev.type }));
        } else if (selectedItem?.id) {
          try {
            const updatedAdmin = await adminApi.getById(selectedItem.id);
            setSelectedItem(prev => ({ ...updatedAdmin, type: prev.type }));
          } catch (error) {
            logger.info('Администратор не найден, возможно был удален');
            onClose();
          }
        }
      } else if (selectedItem?.type === 'booking') {
        logger.debug('Обновление списка бронирований...');
        await loadBookingsWithFilters(bookingFilters);

        if (selectedItem?.id) {
          try {
            logger.debug('Обновление детального бронирования:', { id: selectedItem.id });
            const updatedBooking = await bookingApi.getByIdDetailed(selectedItem.id);
            setSelectedItem(prev => ({ ...updatedBooking, type: prev.type }));
            logger.debug('Детальное бронирование обновлено');
          } catch (error) {
            logger.error('Ошибка обновления детального бронирования:', error);

            if (error.message?.includes('422')) {
              toast({
                title: 'Ошибка обновления',
                description: 'Проблема с загрузкой обновленных данных бронирования',
                status: 'error',
                duration: 5000,
              });
            } else {
              logger.info('Бронирование не найдено или удалено');
              onClose();
            }
          }
        }
      } else {
        await fetchSectionDataEnhanced(section);
      }

      logger.debug('Обновление завершено успешно');
    } catch (error) {
      logger.error('Ошибка обновления:', error);
      toast({
        title: 'Ошибка обновления',
        description: 'Не удалось обновить данные. Попробуйте еще раз.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Рендер секций с проверкой прав доступа
  const renderSection = () => {
    const sectionProps = {
      openDetailModal,
      fetchData: () => fetchSectionDataEnhanced(section)
    };

    // Проверка прав доступа для каждой секции
    const sectionPermissions = {
      dashboard: 'view_dashboard',
      users: 'view_users',
      bookings: 'view_bookings',
      tariffs: 'view_tariffs',
      offices: 'view_offices',
      promocodes: 'view_promocodes',
      tickets: 'view_tickets',
      notifications: 'view_notifications',
      newsletters: 'view_telegram_newsletters',
      emails: 'view_email_campaigns',
      admins: 'manage_admins',
      logging: 'view_logs',
      backups: 'manage_backups'
    };

    const requiredPermission = sectionPermissions[section];
    const hasAccess = !requiredPermission || hasPermission(requiredPermission);

    // Для админов и бэкапов дополнительная проверка на супер админа
    if ((section === 'admins' || section === 'backups') && currentAdmin?.role !== 'super_admin') {
      return (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <h2 style={{ color: '#e53e3e', fontSize: '1.5rem', marginBottom: '1rem' }}>
            Доступ запрещен
          </h2>
          <p style={{ color: '#666', fontSize: '1rem' }}>
            Только главный администратор может управлять администраторами и бэкапами.
          </p>
        </div>
      );
    }

    if (!hasAccess) {
      return (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <h2 style={{ color: '#e53e3e', fontSize: '1.5rem', marginBottom: '1rem' }}>
            Доступ запрещен
          </h2>
          <p style={{ color: '#666', fontSize: '1rem' }}>
            У вас недостаточно прав для просмотра этого раздела.
          </p>
        </div>
      );
    }

    switch (section) {
      case 'dashboard':
        return (
          <Dashboard
            stats={dashboardStats}
            users={users}
            tickets={tickets}
            bookings={bookings}
            offices={offices}
            chartRef={chartRef}
            chartInstanceRef={chartInstanceRef}
            isChartInitialized={isChartInitialized}
            setIsChartInitialized={setIsChartInitialized}
            section={section}
            setSection={setSection}
          />
        );
      case 'users':
        return <Users users={users} {...sectionProps} currentAdmin={currentAdmin} />;
      case 'bookings':
        return (
          <Bookings
            bookings={bookings}
            bookingsMeta={bookingsMeta}
            {...sectionProps}
            onRefresh={() => loadBookingsWithFilters(bookingFilters)}
            onFiltersChange={handleBookingFiltersChange}
            isLoading={isBookingsLoading}
            currentAdmin={currentAdmin}
            tariffs={tariffs}
            users={users}
          />
        );
      case 'tariffs':
        return (
          <Tariffs
            tariffs={tariffs}
            openDetailModal={openDetailModal}
            onUpdate={() => fetchSectionDataEnhanced('tariffs')}
            currentAdmin={currentAdmin}
          />
        );
      case 'offices':
        return (
          <Offices
            offices={offices}
            users={users}
            openDetailModal={openDetailModal}
            onUpdate={() => fetchSectionDataEnhanced('offices')}
            currentAdmin={currentAdmin}
          />
        );
      case 'promocodes':
        return (
          <Promocodes
            promocodes={promocodes}
            openDetailModal={openDetailModal}
            onUpdate={() => fetchSectionDataEnhanced('promocodes')}
            currentAdmin={currentAdmin}
          />
        );
      case 'tickets':
        return (
          <Tickets
            tickets={tickets}
            ticketsMeta={ticketsMeta}
            {...sectionProps}
            onRefresh={() => loadTicketsWithFilters(ticketFilters)}
            onFiltersChange={handleTicketFiltersChange}
            isLoading={isTicketsLoading}
            currentAdmin={currentAdmin}
          />
        );
      case 'notifications':
        return (
          <Notifications
            notifications={notifications}
            openDetailModal={openDetailModal}
            setSection={setSection}
            onRefresh={() => fetchSectionDataEnhanced('notifications')}
            currentAdmin={currentAdmin}
          />
        );
      case 'newsletters':
        return <Newsletters newsletters={newsletters} currentAdmin={currentAdmin} />;
      case 'emails':
        return <Emails currentAdmin={currentAdmin} />;
      case 'admins':
        return (
          <Admins
            admins={admins}
            openDetailModal={openDetailModal}
            onUpdate={() => fetchSectionDataEnhanced('admins')}
            currentAdmin={currentAdmin}
          />
        );
      case 'system-monitoring':
        return <SystemMonitoring currentAdmin={currentAdmin} />;
      case 'logging':
        return <Logging currentAdmin={currentAdmin} />;
      case 'ip-bans':
        return <IPBans currentAdmin={currentAdmin} />;
      case 'backups':
        return <Backups currentAdmin={currentAdmin} />;
      default:
        return (
          <Dashboard
            stats={dashboardStats}
            users={users}
            tickets={tickets}
            bookings={bookings}
            offices={offices}
            chartRef={chartRef}
            chartInstanceRef={chartInstanceRef}
            isChartInitialized={isChartInitialized}
            setIsChartInitialized={setIsChartInitialized}
            section={section}
            setSection={setSection}
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
      <GlobalLoadingBar isLoading={isGlobalLoading} />
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
        currentAdmin={currentAdmin}
        isSidebarCollapsed={isSidebarCollapsed}
        toggleSidebar={toggleSidebar}
        isSidebarHovered={isSidebarHovered}
        setIsSidebarHovered={setIsSidebarHovered}
      >
        {/* Suspense wrapper for lazy-loaded sections (P-MED-4) */}
        <Suspense fallback={<LoadingFallback />}>
          {renderSection()}
        </Suspense>
      </Layout>

      {/* Модальные окна для разных типов элементов (P-MED-4: lazy-loaded) */}
      <Suspense fallback={null}>
        {selectedItem?.type === 'user' && (
          <UserDetailModal
            isOpen={isOpen}
            onClose={onClose}
            user={selectedItem}
            onUpdate={handleUpdate}
            currentAdmin={currentAdmin}
          />
        )}

        {selectedItem?.type === 'booking' && (
          <BookingDetailModal
            isOpen={isOpen}
            onClose={onClose}
            booking={selectedItem}
            onUpdate={handleUpdate}
            currentAdmin={currentAdmin}
          />
        )}

        {selectedItem?.type === 'tariff' && (
          <TariffDetailModal
            isOpen={isOpen}
            onClose={onClose}
            tariff={selectedItem}
            onUpdate={() => fetchSectionDataEnhanced('tariffs')}
            currentAdmin={currentAdmin}
          />
        )}

        {selectedItem?.type === 'office' && (
          <OfficeDetailModal
            isOpen={isOpen}
            onClose={onClose}
            office={selectedItem}
            users={users}
            offices={offices}
            onUpdate={() => fetchSectionDataEnhanced('offices')}
            currentAdmin={currentAdmin}
          />
        )}

        {selectedItem?.type === 'promocode' && (
          <PromocodeDetailModal
            isOpen={isOpen}
            onClose={onClose}
            promocode={selectedItem}
            onUpdate={() => fetchSectionDataEnhanced('promocodes')}
            currentAdmin={currentAdmin}
          />
        )}

        {selectedItem?.type === 'ticket' && (
          <TicketDetailModal
            isOpen={isOpen}
            onClose={onClose}
            ticket={selectedItem}
            onUpdate={handleUpdate}
            currentAdmin={currentAdmin}
          />
        )}

        {selectedItem?.type === 'admin' && (
          <AdminDetailModal
            isOpen={isOpen}
            onClose={onClose}
            admin={selectedItem}
            onUpdate={handleUpdate}
            currentAdmin={currentAdmin}
          />
        )}
      </Suspense>

      {/* Модальное окно запроса разрешений на уведомления */}
      <NotificationPermissionModal
        isOpen={isNotificationPermissionOpen}
        onClose={() => setNotificationPermissionOpen(false)}
        onPermissionGranted={handleNotificationPermissionGranted}
      />
    </ChakraProvider>
  );
}

function App() {
  return (
    <GlobalLoadingProvider>
      <OnboardingProvider>
        <AppContent />
      </OnboardingProvider>
    </GlobalLoadingProvider>
  );
}

export default App;