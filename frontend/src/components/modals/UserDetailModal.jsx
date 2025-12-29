import React, { useState, useEffect } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  VStack,
  HStack,
  Text,
  Button,
  Input,
  Textarea,
  FormControl,
  FormLabel,
  FormErrorMessage,
  FormHelperText,
  Badge,
  useToast,
  Modal as ChakraModal,
  ModalFooter,
  Box,
  Image,
  Link,
  Icon,
  Heading,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper
} from '@chakra-ui/react';
import { FiEdit, FiTrash2, FiUpload, FiExternalLink, FiUserX, FiUserCheck } from 'react-icons/fi';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { userUpdateSchema } from '../../utils/validationSchemas';
import { userApi, openspaceApi, bookingApi } from '../../utils/api';
import { getStatusColor } from '../../styles/styles';

// Определяем базовый URL в зависимости от окружения
const getApiBaseUrl = () => {
  // Если переменная окружения задана, используем её
  if (process.env.REACT_APP_API_BASE_URL) {
    return process.env.REACT_APP_API_BASE_URL;
  }
  
  // Иначе определяем автоматически по текущему хосту
  const protocol = window.location.protocol;
  const hostname = window.location.hostname;
  
  // Для локальной разработки
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost/api';
  }
  
  // Для продакшена используем тот же домен с HTTPS
  return `${protocol}//${hostname}/api`;
};

const API_BASE_URL = getApiBaseUrl();

// Утилита для получения URL аватара с защитой от кэширования
const getAvatarUrl = (avatar, forceRefresh = false) => {
  // ИСПРАВЛЕНИЕ: Если аватар отсутствует или null, всегда возвращаем placeholder
  if (!avatar || avatar === 'placeholder_avatar.png' || avatar === null) {
    return `/avatars/placeholder_avatar.png?v=${Date.now()}`;
  }

  // Добавляем timestamp для предотвращения кэширования
  const timestamp = forceRefresh ? Date.now() : new Date().getTime();
  return `/avatars/${avatar}?v=${timestamp}`;
};

const UserDetailModal = ({ isOpen, onClose, user, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({});
  const [avatarFile, setAvatarFile] = useState(null);
  const [isAvatarModalOpen, setAvatarModalOpen] = useState(false);
  const [isDownloadingAvatar, setIsDownloadingAvatar] = useState(false);
  const [avatarVersion, setAvatarVersion] = useState(Date.now()); // Для форсированного обновления
  const [currentUser, setCurrentUser] = useState(user); // Локальное состояние пользователя
  const [isBanModalOpen, setIsBanModalOpen] = useState(false);
  const [banReason, setBanReason] = useState('');
  const [isBanning, setIsBanning] = useState(false);
  const [referrer, setReferrer] = useState(null);  // Пригласивший
  const [invitedUsers, setInvitedUsers] = useState([]);  // Список приглашенных
  const [loadingReferrals, setLoadingReferrals] = useState(false);  // Загрузка реферальных данных

  // Опенспейс аренда
  const [openspaceInfo, setOpenspaceInfo] = useState(null);
  const [bookingHistory, setBookingHistory] = useState([]);
  const [isOpenspaceModalOpen, setOpenspaceModalOpen] = useState(false);
  const [openspaceFormData, setOpenspaceFormData] = useState({
    rental_type: 'one_day',
    price: 0,
    start_date: new Date().toISOString().split('T')[0],
    duration_months: 1,
    workplace_number: '',
    admin_reminder_enabled: false,
    admin_reminder_days: 5,
    tenant_reminder_enabled: false,
    tenant_reminder_days: 5,
    notes: '',
    // Поля для почасовых бронирований
    visit_time: '',
    duration: 1
  });
  const [activeTariffs, setActiveTariffs] = useState([]);

  const toast = useToast();

  // Инициализация react-hook-form с Zod валидацией
  const {
    register,
    handleSubmit: handleFormSubmit,
    formState: { errors },
    reset,
    setValue: setFormValue,
  } = useForm({
    resolver: zodResolver(userUpdateSchema),
    mode: 'onBlur', // Валидация при потере фокуса
  });

  useEffect(() => {
    if (user) {
      setCurrentUser(user); // Обновляем локальное состояние
      const userData = {
        full_name: user.full_name || '',
        phone: user.phone || '',
        email: user.email || '',
        language_code: user.language_code || 'ru',
        admin_comment: user.admin_comment || '',
        birth_date: user.birth_date || ''
      };
      setFormData(userData);

      // Синхронизируем с react-hook-form
      reset(userData);

      // Обновляем версию при изменении пользователя
      setAvatarVersion(Date.now());

      // Загружаем данные параллельно
      fetchOpenspaceInfo(user.id);
      fetchBookingHistory(user.id);
      fetchReferralData(user.id);
      fetchActiveTariffs();
    }
  }, [user, reset]); // eslint-disable-line react-hooks/exhaustive-deps

  // Автоматический выбор первого тарифа при открытии модального окна аренды
  useEffect(() => {
    if (isOpenspaceModalOpen && activeTariffs && activeTariffs.length > 0) {
      const firstTariff = activeTariffs[0];
      const rentalType = getTariffRentalType(firstTariff);

      // Определяем длительность по названию тарифа для почасовых
      let duration = 1;
      if (rentalType === 'hourly') {
        const match = firstTariff.name.match(/(\d+)\s*час/i);
        if (match) {
          duration = parseInt(match[1]);
        }
      }

      setOpenspaceFormData({
        rental_type: `tariff_${firstTariff.id}`,
        tariff_id: firstTariff.id,
        price: firstTariff.price,
        start_date: new Date().toISOString().split('T')[0],
        duration_months: 1,
        workplace_number: rentalType === 'monthly_fixed' ? '' : '',
        admin_reminder_enabled: false,
        admin_reminder_days: 5,
        tenant_reminder_enabled: false,
        tenant_reminder_days: 5,
        notes: '',
        visit_time: '',
        duration: duration
      });
    }
  }, [isOpenspaceModalOpen, activeTariffs]); // eslint-disable-line react-hooks/exhaustive-deps

  // ИСПРАВЛЕНИЕ: Проверяем локальное состояние пользователя
  const isPlaceholderAvatar = !currentUser?.avatar || currentUser.avatar === 'placeholder_avatar.png' || currentUser.avatar === null;

  // URL аватара с версионированием - используем локальное состояние
  const avatarUrl = avatarFile
    ? URL.createObjectURL(avatarFile)
    : getAvatarUrl(currentUser?.avatar, true);

  // Формирование ссылок
  const getTelegramUrl = (username) => {
    if (!username) return null;
    const cleanUsername = username.startsWith('@') ? username.slice(1) : username;
    return `https://t.me/${cleanUsername}`;
  };

  const getMailtoUrl = (email) => {
    if (!email) return null;
    return `mailto:${email}`;
  };

  const handleDownloadTelegramAvatar = async () => {
    setIsDownloadingAvatar(true);
    try {
      console.log('Начинаем скачивание аватара из Telegram для пользователя:', currentUser.id);

      const result = await userApi.downloadTelegramAvatar(currentUser.id);
      console.log('Аватар успешно скачан:', result);

      // ИСПРАВЛЕНИЕ: Обновляем локальное состояние пользователя
      setCurrentUser(prev => ({
        ...prev,
        avatar: result.avatar_filename
      }));

      // Форсируем обновление версии для перезагрузки изображения
      setAvatarVersion(Date.now());

      // Обновляем данные пользователя
      await onUpdate();

      // Закрываем модальное окно аватара
      setAvatarModalOpen(false);

      toast({
        title: 'Аватар загружен',
        description: 'Аватар успешно скачан из Telegram и сохранен',
        status: 'success',
        duration: 4000,
        isClosable: true,
      });

    } catch (error) {
      console.error('Ошибка при скачивании аватара:', error);

      let errorMessage = 'Произошла ошибка при скачивании аватара из Telegram';
      let toastStatus = 'error';
      let duration = 6000;

      if (error.message) {
        errorMessage = error.message;
        
        // Для определенных ошибок меняем статус и заголовок
        if (error.message.includes('нет фото профиля') || 
            error.message.includes('недоступно для загрузки')) {
          toastStatus = 'info';
          duration = 4000;
          // Более дружелюбное сообщение
          toast({
            title: 'Аватар недоступен',
            description: 'У пользователя нет фото профиля в Telegram, либо настройки приватности не позволяют его загрузить',
            status: toastStatus,
            duration: duration,
            isClosable: true,
            position: 'top',
          });
          return;
        } else if (error.message.includes('не указан Telegram ID')) {
          toastStatus = 'warning';
          duration = 4000;
          toast({
            title: 'Telegram ID отсутствует',
            description: 'У пользователя не указан Telegram ID, поэтому нельзя загрузить аватар',
            status: toastStatus,
            duration: duration,
            isClosable: true,
            position: 'top',
          });
          return;
        }
      }

      toast({
        title: 'Ошибка загрузки аватара',
        description: errorMessage,
        status: toastStatus,
        duration: duration,
        isClosable: true,
        position: 'top',
      });
    } finally {
      setIsDownloadingAvatar(false);
    }
  };

  // Функция загрузки реферальных данных
  const fetchReferralData = async (userId) => {
    if (!userId) return;

    setLoadingReferrals(true);
    try {
      // Загружаем параллельно
      const [referrerData, invitedData] = await Promise.all([
        userApi.getReferrer(userId),
        userApi.getInvitedUsers(userId)
      ]);

      setReferrer(referrerData);
      setInvitedUsers(invitedData || []);
    } catch (error) {
      console.error('Error fetching referral data:', error);
      toast({
        title: 'Ошибка загрузки реферальных данных',
        description: error.message || 'Не удалось загрузить реферальную информацию',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setLoadingReferrals(false);
    }
  };

  // Функция загрузки информации об аренде опенспейса
  const fetchOpenspaceInfo = async (userId) => {
    if (!userId) return;

    try {
      const data = await openspaceApi.getUserInfo(userId);
      setOpenspaceInfo(data);
    } catch (error) {
      console.error('Error fetching openspace info:', error);
      // Устанавливаем fallback структуру, чтобы UI отображался
      setOpenspaceInfo({
        has_active_rental: false,
        active_rental: null,
        rental_history: []
      });

      // Показываем toast с предупреждением
      toast({
        title: 'Не удалось загрузить данные опенспейса',
        description: 'Попробуйте обновить страницу или обратитесь к администратору',
        status: 'warning',
        duration: 5000,
        isClosable: true
      });
    }
  };

  // Функция загрузки истории бронирований
  const fetchBookingHistory = async (userId) => {
    if (!userId) return;

    try {
      // Получаем все бронирования пользователя
      const response = await bookingApi.getAllDetailed({ per_page: 100 });

      // Фильтруем бронирования по user_id
      const userBookings = (response.bookings || []).filter(
        booking => booking.user_id === userId
      );

      setBookingHistory(userBookings);
    } catch (error) {
      console.error('Error fetching booking history:', error);
      setBookingHistory([]);
    }
  };

  // Функция загрузки активных тарифов
  const fetchActiveTariffs = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/tariffs/active`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        throw new Error('Не удалось загрузить тарифы');
      }

      const data = await response.json();

      // Фильтруем тарифы для опенспейса (включая тарифы coworking)
      const openspaceTariffs = data.filter(t =>
        t.purpose === 'openspace' ||
        t.purpose === 'coworking' ||
        t.name.toLowerCase().includes('опенспейс') ||
        t.name.toLowerCase().includes('тестовый день')
      );

      setActiveTariffs(openspaceTariffs);
    } catch (error) {
      console.error('Error fetching active tariffs:', error);
      setActiveTariffs([]);
    }
  };

  // Группирует тарифы по типу
  const groupTariffsByType = () => {
    const grouped = {
      one_day_openspace: null,
      one_day_test: null,
      monthly_floating: null,
      monthly_fixed: null
    };

    activeTariffs.forEach(tariff => {
      const nameLower = tariff.name.toLowerCase();

      if (nameLower.includes('тестовый день') || nameLower.includes('тест')) {
        grouped.one_day_test = tariff;
      } else if (nameLower.includes('на день') && nameLower.includes('опенспейс')) {
        grouped.one_day_openspace = tariff;
      } else if (nameLower.includes('месяц') && nameLower.includes('фикс') && !nameLower.includes('нефикс')) {
        grouped.monthly_fixed = tariff;
      } else if (nameLower.includes('месяц') && (nameLower.includes('нефикс') || !nameLower.includes('фикс'))) {
        grouped.monthly_floating = tariff;
      }
    });

    return grouped;
  };

  // Определяет тип аренды по тарифу
  const getTariffRentalType = (tariff) => {
    if (!tariff) return 'one_day';

    const nameLower = tariff.name.toLowerCase();

    // Почасовые тарифы (3 часа и т.д.)
    if (nameLower.includes('час')) {
      return 'hourly';
    }

    // Месячные тарифы
    if (nameLower.includes('месяц')) {
      if (nameLower.includes('фикс') && !nameLower.includes('нефикс')) {
        return 'monthly_fixed';
      }
      return 'monthly_floating';
    }

    // По умолчанию однодневный
    return 'one_day';
  };

  // Получает тип аренды текущего выбранного тарифа
  const getCurrentRentalType = () => {
    const rentalType = openspaceFormData.rental_type;

    // Если формат tariff_ID
    if (rentalType && rentalType.startsWith('tariff_')) {
      const tariffId = parseInt(rentalType.replace('tariff_', ''));
      const selectedTariff = activeTariffs.find(t => t.id === tariffId);
      if (selectedTariff) {
        return getTariffRentalType(selectedTariff);
      }
    }

    // Старый формат
    if (rentalType === 'monthly_fixed') return 'monthly_fixed';
    if (rentalType === 'monthly_floating') return 'monthly_floating';
    if (rentalType && rentalType.includes('one_day')) return 'one_day';

    return 'one_day';
  };

  // Функция навигации к профилю пользователя
  const navigateToUserProfile = async (user) => {
    if (!user || !user.id) return;

    // Обновляем currentUser и перезагружаем данные
    setCurrentUser(user);

    // Загружаем свежие данные пользователя
    try {
      const userData = await userApi.getById(user.id);
      setCurrentUser(userData);
      await fetchReferralData(user.id);
    } catch (error) {
      console.error('Error navigating to user profile:', error);
      toast({
        title: 'Ошибка загрузки профиля',
        description: error.message || 'Не удалось загрузить профиль пользователя',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleSave = async () => {
    try {
      await userApi.update(currentUser.id, formData);

      if (avatarFile) {
        const uploadResult = await userApi.uploadAvatar(currentUser.id, avatarFile);
        setAvatarFile(null);

        // ИСПРАВЛЕНИЕ: Обновляем локальное состояние пользователя
        setCurrentUser(prev => ({
          ...prev,
          avatar: uploadResult.filename
        }));

        // Форсируем обновление версии
        setAvatarVersion(Date.now());
      }

      await onUpdate();

      toast({
        title: 'Пользователь обновлён',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      setIsEditing(false);
    } catch (error) {
      console.error('Ошибка при сохранении:', error);
      toast({
        title: 'Ошибка при сохранении',
        description: error.response?.data?.detail || 'Произошла ошибка',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const handleAvatarDelete = async () => {
    try {
      console.log('Удаляем аватар для пользователя:', currentUser.id);

      const result = await userApi.deleteAvatar(currentUser.id);
      console.log('Результат удаления аватара:', result);

      setAvatarFile(null);

      // ИСПРАВЛЕНИЕ: Сразу обновляем локальное состояние пользователя
      setCurrentUser(prev => ({
        ...prev,
        avatar: null
      }));

      // Форсируем обновление версии
      setAvatarVersion(Date.now());

      // Обновляем общие данные
      await onUpdate();

      toast({
        title: 'Аватар удалён',
        description: 'Аватар пользователя успешно удален',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      setAvatarModalOpen(false);
    } catch (error) {
      console.error('Ошибка при удалении аватара:', error);
      toast({
        title: 'Ошибка при удалении аватара',
        description: error.response?.data?.detail || 'Произошла ошибка',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Функция для форсированной перезагрузки изображения
  const handleImageError = (e) => {
    console.log('Ошибка загрузки изображения, используем fallbackSrc');
    // Предотвращаем бесконечный цикл - не меняем src, полагаемся на fallbackSrc
    e.preventDefault();
  };

  // Обработчик открытия модального окна бана
  const handleOpenBanModal = () => {
    setBanReason('');
    setIsBanModalOpen(true);
  };

  // Обработчик бана пользователя
  const handleBanUser = async () => {
    if (!banReason.trim()) {
      toast({
        title: 'Ошибка',
        description: 'Необходимо указать причину бана',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsBanning(true);
    try {
      await userApi.banUser(currentUser.id, banReason);

      // Закрываем модальное окно с баном
      setIsBanModalOpen(false);
      setBanReason('');

      // Показываем уведомление
      toast({
        title: 'Пользователь забанен',
        description: 'Пользователь успешно забанен. Обновляем данные...',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Обновляем данные и закрываем модалку
      await onUpdate();

      // Обновляем локальное состояние
      setCurrentUser(prev => ({
        ...prev,
        is_banned: true,
        ban_reason: banReason,
      }));

      // Закрываем главное модальное окно после обновления
      onClose();
    } catch (error) {
      console.error('Ошибка при бане пользователя:', error);
      toast({
        title: 'Ошибка при бане',
        description: error.response?.data?.detail || 'Произошла ошибка',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsBanning(false);
    }
  };

  // Обработчик разбана пользователя
  const handleUnbanUser = async () => {
    setIsBanning(true);
    try {
      await userApi.unbanUser(currentUser.id);

      // Показываем уведомление
      toast({
        title: 'Пользователь разбанен',
        description: 'Пользователь успешно разбанен. Обновляем данные...',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Обновляем данные и закрываем модалку
      await onUpdate();

      // Обновляем локальное состояние
      setCurrentUser(prev => ({
        ...prev,
        is_banned: false,
        ban_reason: null,
        banned_at: null,
        banned_by: null,
      }));

      // Закрываем модальное окно после обновления
      onClose();
    } catch (error) {
      console.error('Ошибка при разбане пользователя:', error);
      toast({
        title: 'Ошибка при разбане',
        description: error.response?.data?.detail || 'Произошла ошибка',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsBanning(false);
    }
  };

  // Обработчики опенспейса
  const handleCreateRental = async () => {
    try {
      const currentType = getCurrentRentalType();

      // Почасовые тарифы создаём через Booking API
      if (currentType === 'hourly') {
        // Валидация обязательных полей для почасовых тарифов
        if (!openspaceFormData.visit_time) {
          toast({
            title: 'Ошибка',
            description: 'Укажите время начала для почасового тарифа',
            status: 'error',
            duration: 5000,
            isClosable: true
          });
          return;
        }

        const bookingData = {
          user_id: currentUser.id,
          tariff_id: parseInt(openspaceFormData.tariff_id),
          visit_date: openspaceFormData.start_date,
          visit_time: openspaceFormData.visit_time,
          duration: parseInt(openspaceFormData.duration) || 1,
          amount: parseFloat(openspaceFormData.price),
          paid: true,
          confirmed: true
        };

        console.log('Создание почасового бронирования:', bookingData);

        await bookingApi.create(bookingData);

        toast({
          title: 'Бронирование создано',
          description: 'Почасовое бронирование успешно создано',
          status: 'success',
          duration: 3000,
          isClosable: true
        });

        setOpenspaceModalOpen(false);
        // Обновляем данные пользователя
        if (onUpdate) {
          await onUpdate();
        }
        return;
      }

      // Остальные тарифы создаём через Openspace API
      // Определяем реальный rental_type для backend
      let backendRentalType = openspaceFormData.rental_type;

      // Если формат tariff_ID, определяем тип по тарифу
      if (openspaceFormData.rental_type.startsWith('tariff_')) {
        backendRentalType = currentType;
      } else {
        // Старая логика: конвертируем one_day_* в one_day для backend
        if (openspaceFormData.rental_type.startsWith('one_day')) {
          backendRentalType = 'one_day';
        }
      }

      const dataToSend = {
        rental_type: backendRentalType,
        start_date: `${openspaceFormData.start_date}T00:00:00`,
        price: parseFloat(openspaceFormData.price),
        notes: openspaceFormData.notes || null
      };

      if (openspaceFormData.tariff_id) {
        dataToSend.tariff_id = parseInt(openspaceFormData.tariff_id);
      }

      if (backendRentalType === 'monthly_fixed') {
        dataToSend.workplace_number = openspaceFormData.workplace_number;
      }

      if (backendRentalType !== 'one_day') {
        dataToSend.duration_months = parseInt(openspaceFormData.duration_months) || 1;
        dataToSend.admin_reminder_enabled = openspaceFormData.admin_reminder_enabled;
        dataToSend.admin_reminder_days = parseInt(openspaceFormData.admin_reminder_days) || 5;
        dataToSend.tenant_reminder_enabled = openspaceFormData.tenant_reminder_enabled;
        dataToSend.tenant_reminder_days = parseInt(openspaceFormData.tenant_reminder_days) || 5;
      }

      console.log('Отправка данных аренды опенспейса:', dataToSend);

      await openspaceApi.create(currentUser.id, dataToSend);

      toast({
        title: 'Аренда создана',
        status: 'success',
        duration: 3000,
        isClosable: true
      });

      setOpenspaceModalOpen(false);
      fetchOpenspaceInfo(currentUser.id);
    } catch (error) {
      console.error('Ошибка создания аренды:', error);
      toast({
        title: 'Ошибка',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    }
  };

  const handlePayRental = async (rentalId) => {
    try {
      await openspaceApi.recordPayment(rentalId);

      toast({
        title: 'Платеж записан',
        status: 'success',
        duration: 3000,
        isClosable: true
      });

      fetchOpenspaceInfo(currentUser.id);
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    }
  };

  const handleDeactivateRental = async (rentalId) => {
    if (!window.confirm('Вы уверены, что хотите завершить аренду?')) return;

    try {
      await openspaceApi.deactivate(rentalId);

      toast({
        title: 'Аренда завершена',
        status: 'success',
        duration: 3000,
        isClosable: true
      });

      fetchOpenspaceInfo(currentUser.id);
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    }
  };

  const getRentalTypeLabel = (type) => {
    const labels = {
      'one_day': 'Один день',  // Для старых записей
      'monthly_fixed': 'Опенспейс на месяц(фикс)',
      'monthly_floating': 'Опенспейс на месяц'
    };
    return labels[type] || type;
  };

  const getPaymentStatusColor = (status) => {
    const colors = {
      'pending': 'orange',
      'paid': 'green',
      'overdue': 'red'
    };
    return colors[status] || 'gray';
  };

  if (!currentUser) return null;

  const telegramUrl = getTelegramUrl(currentUser.username);
  const mailtoUrl = getMailtoUrl(currentUser.email);

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Пользователь #{currentUser.id}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              {/* Аватар с версионированием */}
              <Box textAlign="center">
                <Image
                  key={`avatar-${currentUser.id}-${avatarVersion}`} // Ключ для форсированного обновления
                  src={`${avatarUrl}&t=${avatarVersion}`} // Дополнительный параметр времени
                  alt="Аватар пользователя"
                  boxSize="120px"
                  borderRadius="full"
                  objectFit="cover"
                  fallbackSrc={`/avatars/placeholder_avatar.png?v=${Date.now()}`}
                  mx="auto"
                  mb={4}
                  cursor="pointer"
                  onClick={() => setAvatarModalOpen(true)}
                  onError={handleImageError}
                  _hover={{ boxShadow: 'md', transform: 'scale(1.05)', transition: '0.2s' }}
                  loading="eager" // Отключаем lazy loading
                />

                {/* Кнопка загрузки аватара из Telegram */}
                {isPlaceholderAvatar && (
                  <Button
                    leftIcon={<FiUpload />}
                    colorScheme="blue"
                    variant="outline"
                    size="sm"
                    onClick={handleDownloadTelegramAvatar}
                    isLoading={isDownloadingAvatar}
                    loadingText="Загружаем..."
                    mt={2}
                  >
                    Загрузить из Telegram
                  </Button>
                )}

                <VStack spacing={2}>
                  <Text fontSize="lg" fontWeight="bold">
                    {currentUser.full_name || 'Не указано'}
                  </Text>

                  {currentUser.username ? (
                    <Link
                      href={telegramUrl}
                      isExternal
                      color="blue.500"
                      fontSize="sm"
                      _hover={{
                        color: 'blue.600',
                        textDecoration: 'underline'
                      }}
                      display="flex"
                      alignItems="center"
                      gap={1}
                    >
                      @{currentUser.username}
                      <FiExternalLink size={12} />
                    </Link>
                  ) : (
                    <Text fontSize="sm" color="gray.500">
                      @Не указано
                    </Text>
                  )}

                  <Badge colorScheme="blue">
                    ID: {currentUser.telegram_id}
                  </Badge>
                </VStack>
              </Box>

              {/* Форма редактирования */}
              {isEditing ? (
                <VStack spacing={3} align="stretch">
                  <FormControl isInvalid={!!errors.full_name}>
                    <FormLabel>Полное имя</FormLabel>
                    <Input
                      {...register('full_name', {
                        onChange: (e) => setFormData({...formData, full_name: e.target.value})
                      })}
                      placeholder="Введите полное имя"
                    />
                    <FormErrorMessage>{errors.full_name?.message}</FormErrorMessage>
                  </FormControl>

                  <FormControl isInvalid={!!errors.phone}>
                    <FormLabel>Телефон</FormLabel>
                    <Input
                      {...register('phone', {
                        onChange: (e) => setFormData({ ...formData, phone: e.target.value })
                      })}
                      placeholder="Введите телефон (например: +79991234567)"
                    />
                    <FormErrorMessage>{errors.phone?.message}</FormErrorMessage>
                  </FormControl>

                  <FormControl isInvalid={!!errors.email}>
                    <FormLabel>Email</FormLabel>
                    <Input
                      type="email"
                      {...register('email', {
                        onChange: (e) => setFormData({ ...formData, email: e.target.value })
                      })}
                      placeholder="Введите email (например: user@example.com)"
                    />
                    <FormErrorMessage>{errors.email?.message}</FormErrorMessage>
                  </FormControl>

                  <FormControl>
                    <FormLabel>Язык</FormLabel>
                    <Input
                      {...register('language_code', {
                        onChange: (e) => setFormData({ ...formData, language_code: e.target.value })
                      })}
                      placeholder="Код языка"
                    />
                  </FormControl>

                  <FormControl>
                    <FormLabel>Новый аватар</FormLabel>
                    <Input
                      type="file"
                      accept="image/*"
                      onChange={(e) => setAvatarFile(e.target.files[0])}
                    />
                  </FormControl>

                  <FormControl isInvalid={!!errors.admin_comment}>
                    <FormLabel>
                      Комментарий администратора
                      <Text as="span" fontSize="sm" color="gray.500" ml={2}>
                        ({formData.admin_comment?.length || 0}/500)
                      </Text>
                    </FormLabel>
                    <Textarea
                      {...register('admin_comment', {
                        onChange: (e) => {
                          if (e.target.value.length <= 500) {
                            setFormData({ ...formData, admin_comment: e.target.value });
                          }
                        }
                      })}
                      placeholder="Введите комментарий о пользователе..."
                      rows={4}
                      resize="vertical"
                    />
                    <FormErrorMessage>{errors.admin_comment?.message}</FormErrorMessage>
                  </FormControl>

                  <FormControl isInvalid={!!errors.birth_date}>
                    <FormLabel>Дата рождения</FormLabel>
                    <Input
                      type="text"
                      {...register('birth_date', {
                        onChange: (e) => setFormData({ ...formData, birth_date: e.target.value })
                      })}
                      placeholder="ДД.ММ или ДД.ММ.ГГГГ (например, 25.12 или 25.12.1990)"
                      maxLength={10}
                    />
                    <FormHelperText>
                      Опциональное поле. Год можно не указывать. Используется для автоматических поздравлений.
                    </FormHelperText>
                    <FormErrorMessage>{errors.birth_date?.message}</FormErrorMessage>
                  </FormControl>
                </VStack>
              ) : (
                <VStack spacing={3} align="stretch">
                  <HStack justify="space-between">
                    <Text fontWeight="bold">Телефон:</Text>
                    <Text>{currentUser.phone || 'Не указано'}</Text>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Email:</Text>
                    {currentUser.email && mailtoUrl ? (
                      <Link
                        href={mailtoUrl}
                        color="blue.500"
                        _hover={{
                          color: 'blue.600',
                          textDecoration: 'underline'
                        }}
                        display="flex"
                        alignItems="center"
                        gap={1}
                      >
                        {currentUser.email}
                        <FiExternalLink size={12} />
                      </Link>
                    ) : (
                      <Text>Не указано</Text>
                    )}
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Язык:</Text>
                    <Text>{currentUser.language_code}</Text>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Успешных броней:</Text>
                    <Badge colorScheme="green">{currentUser.successful_bookings}</Badge>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Приглашено:</Text>
                    <Badge colorScheme="purple">{currentUser.invited_count}</Badge>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Дата регистрации:</Text>
                    <Text>{new Date(currentUser.reg_date || currentUser.first_join_time).toLocaleDateString('ru-RU')}</Text>
                  </HStack>

                  {currentUser.birth_date && (
                    <HStack justify="space-between">
                      <Text fontWeight="bold">Дата рождения:</Text>
                      <Text>
                        {currentUser.birth_date}
                        {(() => {
                          // Если указан год (формат DD.MM.YYYY), показываем возраст
                          const parts = currentUser.birth_date.split('.');
                          if (parts.length === 3) {
                            const [day, month, year] = parts.map(Number);
                            const today = new Date();
                            let age = today.getFullYear() - year;
                            const monthDiff = today.getMonth() + 1 - month;

                            if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < day)) {
                              age--;
                            }

                            return (
                              <Badge colorScheme="purple" ml={2}>
                                {age} лет
                              </Badge>
                            );
                          }
                          return null;
                        })()}
                      </Text>
                    </HStack>
                  )}

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Согласие с условиями:</Text>
                    <Badge colorScheme={currentUser.agreed_to_terms ? 'green' : 'red'}>
                      {currentUser.agreed_to_terms ? 'Да' : 'Нет'}
                    </Badge>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Статус:</Text>
                    <Badge colorScheme={currentUser.is_banned ? 'red' : 'green'}>
                      {currentUser.is_banned ? 'Забанен' : 'Активен'}
                    </Badge>
                  </HStack>

                  {/* Информация о бане */}
                  {currentUser.is_banned && (
                    <Box
                      bg="red.50"
                      borderLeft="4px solid"
                      borderColor="red.500"
                      p={3}
                      borderRadius="md"
                    >
                      <Text fontWeight="bold" color="red.700" mb={2}>
                        Информация о бане:
                      </Text>
                      <VStack align="stretch" spacing={1}>
                        <Text fontSize="sm" color="gray.700">
                          <Text as="span" fontWeight="semibold">Причина:</Text> {currentUser.ban_reason}
                        </Text>
                        {currentUser.banned_by && (
                          <Text fontSize="sm" color="gray.700">
                            <Text as="span" fontWeight="semibold">Забанил:</Text> {currentUser.banned_by}
                          </Text>
                        )}
                        {currentUser.banned_at && (
                          <Text fontSize="sm" color="gray.700">
                            <Text as="span" fontWeight="semibold">Дата:</Text> {new Date(currentUser.banned_at).toLocaleString('ru-RU')}
                          </Text>
                        )}
                      </VStack>
                    </Box>
                  )}

                  {/* Комментарий администратора */}
                  <Box
                    bg="yellow.50"
                    borderLeft="4px solid"
                    borderColor="yellow.400"
                    p={3}
                    borderRadius="md"
                  >
                    <Text fontWeight="bold" mb={2}>
                      Комментарий администратора:
                    </Text>
                    <Text color="gray.700" whiteSpace="pre-wrap">
                      {currentUser.admin_comment || 'Комментарий отсутствует'}
                    </Text>
                  </Box>

                  {/* Реферальная информация */}
                  <Box
                    bg="purple.50"
                    border="1px solid"
                    borderColor="purple.200"
                    p={4}
                    borderRadius="md"
                  >
                    <Heading size="sm" mb={3} color="purple.700">
                      Реферальная информация
                    </Heading>

                    <VStack align="stretch" spacing={3}>
                      {/* Кто пригласил */}
                      <Box>
                        <Text fontSize="sm" fontWeight="semibold" color="gray.700" mb={2}>
                          Пригласил:
                        </Text>
                        {loadingReferrals ? (
                          <Text fontSize="sm" color="gray.500">Загрузка...</Text>
                        ) : referrer ? (
                          <HStack spacing={2} flexWrap="wrap">
                            <Link
                              color="blue.500"
                              fontSize="sm"
                              fontWeight="medium"
                              cursor="pointer"
                              onClick={() => navigateToUserProfile(referrer)}
                              _hover={{
                                color: 'blue.600',
                                textDecoration: 'underline'
                              }}
                              display="flex"
                              alignItems="center"
                              gap={1}
                            >
                              {referrer.full_name || `Пользователь ${referrer.telegram_id}`}
                              <Icon as={FiExternalLink} boxSize={3} />
                            </Link>
                            <Badge colorScheme="purple" fontSize="xs">
                              ID: {referrer.telegram_id}
                            </Badge>
                          </HStack>
                        ) : (
                          <Text fontSize="sm" color="gray.500">-</Text>
                        )}
                      </Box>

                      {/* Кого пригласил */}
                      <Box>
                        <Text fontSize="sm" fontWeight="semibold" color="gray.700" mb={2}>
                          Приглашено пользователей: {currentUser.invited_count || 0}
                        </Text>
                        {loadingReferrals ? (
                          <Text fontSize="sm" color="gray.500">Загрузка...</Text>
                        ) : invitedUsers.length > 0 ? (
                          <VStack
                            align="stretch"
                            spacing={2}
                            maxH={invitedUsers.length > 2 ? "150px" : "auto"}
                            overflowY={invitedUsers.length > 2 ? "auto" : "visible"}
                            bg="white"
                            p={3}
                            borderRadius="md"
                            border="1px solid"
                            borderColor="gray.200"
                          >
                            {invitedUsers.map((invitedUser, index) => (
                              <HStack
                                key={invitedUser.id}
                                spacing={2}
                                p={2}
                                bg="gray.50"
                                borderRadius="md"
                                border="1px solid"
                                borderColor="gray.200"
                                _hover={{ bg: 'gray.100' }}
                                transition="all 0.2s"
                              >
                                <Text fontSize="sm" color="gray.500" minW="20px">
                                  {index + 1}.
                                </Text>
                                <Link
                                  color="blue.500"
                                  fontSize="sm"
                                  fontWeight="medium"
                                  cursor="pointer"
                                  onClick={() => navigateToUserProfile(invitedUser)}
                                  _hover={{
                                    color: 'blue.600',
                                    textDecoration: 'underline'
                                  }}
                                  display="flex"
                                  alignItems="center"
                                  gap={1}
                                  flex={1}
                                >
                                  {invitedUser.full_name || `Пользователь ${invitedUser.telegram_id}`}
                                  <Icon as={FiExternalLink} boxSize={3} />
                                </Link>
                                <Badge colorScheme="blue" fontSize="xs">
                                  ID: {invitedUser.telegram_id}
                                </Badge>
                              </HStack>
                            ))}
                          </VStack>
                        ) : (
                          <Text fontSize="sm" color="gray.500">Никого не пригласил</Text>
                        )}
                      </Box>
                    </VStack>
                  </Box>

                  {/* Секция аренды опенспейса */}
                  {openspaceInfo && (
                    <Box mt={4}>
                      <Heading size="sm" mb={3}>🪑 Аренда опенспейса</Heading>

                      {openspaceInfo.has_active_rental && openspaceInfo.active_rental && (
                        <Box p={4} borderWidth="1px" borderRadius="lg" borderColor="blue.200" bg="blue.50" mb={3}>
                          <VStack align="stretch" spacing={2}>
                            <HStack justify="space-between">
                              <Text fontWeight="bold">Активная аренда</Text>
                              <Badge colorScheme="green">Активна</Badge>
                            </HStack>
                            <Text fontSize="sm">Тип: {getRentalTypeLabel(openspaceInfo.active_rental.rental_type)}</Text>
                            {openspaceInfo.active_rental.workplace_number && (
                              <Text fontSize="sm">Место: {openspaceInfo.active_rental.workplace_number}</Text>
                            )}
                            <Text fontSize="sm">Цена: {openspaceInfo.active_rental.price} ₽</Text>
                            <Text fontSize="sm">
                              Период: {new Date(openspaceInfo.active_rental.start_date).toLocaleDateString()} -
                              {openspaceInfo.active_rental.end_date ? new Date(openspaceInfo.active_rental.end_date).toLocaleDateString() : 'Не указан'}
                            </Text>
                            {openspaceInfo.active_rental.payment_status && (
                              <HStack>
                                <Text fontSize="sm">Статус оплаты:</Text>
                                <Badge colorScheme={getPaymentStatusColor(openspaceInfo.active_rental.payment_status)}>
                                  {openspaceInfo.active_rental.payment_status}
                                </Badge>
                              </HStack>
                            )}
                            <HStack spacing={2} mt={2}>
                              {/* Кнопка "Оплачено" только для месячных с pending статусом */}
                              {!openspaceInfo.active_rental.rental_type.includes('one_day') &&
                               openspaceInfo.active_rental.payment_status !== 'paid' && (
                                <Button size="sm" colorScheme="green" onClick={() => handlePayRental(openspaceInfo.active_rental.id)}>
                                  Оплачено
                                </Button>
                              )}

                              {/* Кнопка "Завершить" только для месячных аренд */}
                              {!openspaceInfo.active_rental.rental_type.includes('one_day') && (
                                <Button size="sm" colorScheme="red" variant="outline" onClick={() => handleDeactivateRental(openspaceInfo.active_rental.id)}>
                                  Завершить
                                </Button>
                              )}
                            </HStack>
                          </VStack>
                        </Box>
                      )}

                      {/* УБРАНО: Кнопка создания аренды согласно новым требованиям */}
                      {/* Теперь все бронирования создаются только через раздел Бронирования */}

                      {/* История бронирований */}
                      {bookingHistory && bookingHistory.length > 0 && (
                        <Box mt={4}>
                          <Text fontWeight="bold" fontSize="sm" mb={2}>История бронирований</Text>
                          <VStack align="stretch" spacing={2} maxH="300px" overflowY="auto">
                            {bookingHistory.slice(0, 20).map((booking) => (
                              <Box key={booking.id} p={2} borderWidth="1px" borderRadius="md" fontSize="sm" bg={booking.confirmed ? 'green.50' : 'gray.50'}>
                                <HStack justify="space-between">
                                  <Text fontWeight="medium">{booking.tariff?.name || 'Неизвестный тариф'}</Text>
                                  <HStack spacing={1}>
                                    <Badge colorScheme={booking.paid ? 'green' : 'yellow'}>
                                      {booking.paid ? 'Оплачено' : 'Не оплачено'}
                                    </Badge>
                                    <Badge colorScheme={booking.confirmed ? 'blue' : 'gray'}>
                                      {booking.confirmed ? 'Подтверждено' : 'Не подтверждено'}
                                    </Badge>
                                  </HStack>
                                </HStack>
                                <Text fontSize="xs" color="gray.600">
                                  📅 {new Date(booking.visit_date).toLocaleDateString()}
                                  {booking.visit_time && ` в ${booking.visit_time.slice(0, 5)}`}
                                  {booking.duration && ` (${booking.duration} ч.)`}
                                </Text>
                                <Text fontSize="xs" color="gray.600">
                                  💰 {booking.amount} ₽
                                </Text>
                              </Box>
                            ))}
                          </VStack>
                        </Box>
                      )}
                    </Box>
                  )}
                </VStack>
              )}
            </VStack>
          </ModalBody>

          <ModalFooter>
            {isEditing ? (
              <HStack spacing={3}>
                <Button onClick={() => setIsEditing(false)}>Отмена</Button>
                <Button colorScheme="purple" onClick={handleSave}>
                  Сохранить
                </Button>
              </HStack>
            ) : (
              <HStack spacing={3}>
                <Button leftIcon={<FiEdit />} colorScheme="purple" onClick={() => setIsEditing(true)}>
                  Редактировать
                </Button>

                {currentUser.is_banned ? (
                  <Button
                    leftIcon={<FiUserCheck />}
                    colorScheme="green"
                    onClick={handleUnbanUser}
                    isLoading={isBanning}
                  >
                    Разбанить
                  </Button>
                ) : (
                  <Button
                    leftIcon={<FiUserX />}
                    colorScheme="red"
                    variant="outline"
                    onClick={handleOpenBanModal}
                  >
                    Забанить
                  </Button>
                )}

                {telegramUrl && (
                  <Button
                    as={Link}
                    href={telegramUrl}
                    isExternal
                    leftIcon={<FiExternalLink />}
                    colorScheme="blue"
                    variant="outline"
                    size="sm"
                  >
                    Telegram
                  </Button>
                )}

                {mailtoUrl && (
                  <Button
                    as={Link}
                    href={mailtoUrl}
                    leftIcon={<FiExternalLink />}
                    colorScheme="green"
                    variant="outline"
                    size="sm"
                  >
                    Email
                  </Button>
                )}
              </HStack>
            )}
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Модальное окно для аватара */}
      <ChakraModal isOpen={isAvatarModalOpen} onClose={() => setAvatarModalOpen(false)} size="2xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Аватар пользователя</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <Image
                key={`modal-avatar-${currentUser.id}-${avatarVersion}`}
                src={`${avatarUrl}&t=${avatarVersion}`}
                alt="Аватар в полном размере"
                boxSize="500px"
                objectFit="contain"
                fallbackSrc={`/avatars/placeholder_avatar.png?v=${Date.now()}`}
                mx="auto"
                onError={handleImageError}
                loading="eager"
              />

              <HStack spacing={3}>
                {currentUser.avatar && !isPlaceholderAvatar && (
                  <Button
                    leftIcon={<FiTrash2 />}
                    colorScheme="red"
                    variant="outline"
                    onClick={handleAvatarDelete}
                  >
                    Удалить
                  </Button>
                )}

                {isPlaceholderAvatar && (
                  <Button
                    leftIcon={<FiUpload />}
                    colorScheme="blue"
                    variant="outline"
                    onClick={handleDownloadTelegramAvatar}
                    isLoading={isDownloadingAvatar}
                    loadingText="Загружаем..."
                  >
                    Загрузить из Telegram
                  </Button>
                )}
              </HStack>

              <input
                id="avatar-upload"
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={(e) => setAvatarFile(e.target.files[0])}
              />
            </VStack>
          </ModalBody>
        </ModalContent>
      </ChakraModal>

      {/* Модальное окно для указания причины бана */}
      <ChakraModal isOpen={isBanModalOpen} onClose={() => setIsBanModalOpen(false)} size="md">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Забанить пользователя</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Text fontSize="sm" color="gray.600">
                Укажите причину бана пользователя <Text as="span" fontWeight="bold">{currentUser.full_name}</Text>
              </Text>
              <FormControl isRequired>
                <FormLabel>Причина бана</FormLabel>
                <Textarea
                  value={banReason}
                  onChange={(e) => setBanReason(e.target.value)}
                  placeholder="Введите причину бана..."
                  rows={4}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <HStack spacing={3}>
              <Button onClick={() => setIsBanModalOpen(false)}>
                Отмена
              </Button>
              <Button
                colorScheme="red"
                onClick={handleBanUser}
                isLoading={isBanning}
                isDisabled={!banReason.trim()}
              >
                Забанить
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </ChakraModal>

      {/* Модальное окно создания аренды опенспейса */}
      <ChakraModal isOpen={isOpenspaceModalOpen} onClose={() => setOpenspaceModalOpen(false)} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Добавить аренду опенспейса</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <FormControl isRequired>
                <FormLabel>Тип аренды</FormLabel>
                <select
                  value={openspaceFormData.rental_type}
                  onChange={(e) => {
                    const newValue = e.target.value;

                    // Если выбран тариф (формат: tariff_ID)
                    if (newValue.startsWith('tariff_')) {
                      const tariffId = parseInt(newValue.replace('tariff_', ''));
                      const selectedTariff = activeTariffs.find(t => t.id === tariffId);

                      if (selectedTariff) {
                        const rentalType = getTariffRentalType(selectedTariff);

                        // Определяем длительность по названию тарифа для почасовых
                        let duration = 1;
                        if (rentalType === 'hourly') {
                          const match = selectedTariff.name.match(/(\d+)\s*час/i);
                          if (match) {
                            duration = parseInt(match[1]);
                          }
                        }

                        setOpenspaceFormData({
                          ...openspaceFormData,
                          rental_type: newValue,
                          tariff_id: selectedTariff.id,
                          price: selectedTariff.price,
                          workplace_number: rentalType === 'monthly_fixed' ? openspaceFormData.workplace_number : '',
                          duration_months: (rentalType === 'one_day' || rentalType === 'hourly') ? null : (openspaceFormData.duration_months || 1),
                          visit_time: '',
                          duration: duration
                        });
                      }
                    } else {
                      // Старая логика для обратной совместимости
                      const grouped = groupTariffsByType();

                      setOpenspaceFormData({
                        ...openspaceFormData,
                        rental_type: newValue,
                        workplace_number: newValue === 'monthly_fixed' ? openspaceFormData.workplace_number : '',
                        duration_months: newValue.includes('one_day') ? null : (openspaceFormData.duration_months || 1)
                      });

                      // Автозаполнение цены и tariff_id
                      let selectedTariff = null;
                      if (newValue === 'one_day_openspace') {
                        selectedTariff = grouped.one_day_openspace;
                      } else if (newValue === 'one_day_test') {
                        selectedTariff = grouped.one_day_test;
                      } else if (newValue === 'monthly_floating') {
                        selectedTariff = grouped.monthly_floating;
                      } else if (newValue === 'monthly_fixed') {
                        selectedTariff = grouped.monthly_fixed;
                      }

                      if (selectedTariff) {
                        setOpenspaceFormData(prev => ({
                          ...prev,
                          price: selectedTariff.price,
                          tariff_id: selectedTariff.id
                        }));
                      }
                    }
                  }}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #E2E8F0' }}
                >
                  {(() => {
                    if (activeTariffs && activeTariffs.length > 0) {
                      // Группируем тарифы по типу для удобства отображения
                      const hourlyTariffs = activeTariffs.filter(t => t.name.toLowerCase().includes('час'));
                      const dailyTariffs = activeTariffs.filter(t =>
                        (t.name.toLowerCase().includes('день') || t.name.toLowerCase().includes('тест')) &&
                        !t.name.toLowerCase().includes('час')
                      );
                      const monthlyTariffs = activeTariffs.filter(t =>
                        t.name.toLowerCase().includes('месяц') &&
                        !t.name.toLowerCase().includes('час')
                      );
                      const otherTariffs = activeTariffs.filter(t =>
                        !hourlyTariffs.includes(t) &&
                        !dailyTariffs.includes(t) &&
                        !monthlyTariffs.includes(t)
                      );

                      return (
                        <>
                          {/* Почасовые тарифы */}
                          {hourlyTariffs.length > 0 && (
                            <optgroup label="Почасовые тарифы">
                              {hourlyTariffs.map(tariff => (
                                <option key={`tariff_${tariff.id}`} value={`tariff_${tariff.id}`}>
                                  {tariff.name} ({tariff.price} ₽)
                                </option>
                              ))}
                            </optgroup>
                          )}

                          {/* Однодневные тарифы */}
                          {dailyTariffs.length > 0 && (
                            <optgroup label="Однодневные тарифы">
                              {dailyTariffs.map(tariff => (
                                <option key={`tariff_${tariff.id}`} value={`tariff_${tariff.id}`}>
                                  {tariff.name} ({tariff.price} ₽)
                                </option>
                              ))}
                            </optgroup>
                          )}

                          {/* Месячные тарифы */}
                          {monthlyTariffs.length > 0 && (
                            <optgroup label="Месячные тарифы">
                              {monthlyTariffs.map(tariff => (
                                <option key={`tariff_${tariff.id}`} value={`tariff_${tariff.id}`}>
                                  {tariff.name} ({tariff.price} ₽)
                                </option>
                              ))}
                            </optgroup>
                          )}

                          {/* Прочие тарифы */}
                          {otherTariffs.length > 0 && (
                            <optgroup label="Другие тарифы">
                              {otherTariffs.map(tariff => (
                                <option key={`tariff_${tariff.id}`} value={`tariff_${tariff.id}`}>
                                  {tariff.name} ({tariff.price} ₽)
                                </option>
                              ))}
                            </optgroup>
                          )}
                        </>
                      );
                    }

                    // Fallback если нет тарифов
                    return (
                      <>
                        <option value="one_day">Один день</option>
                        <option value="monthly_floating">Нефикс месяц</option>
                        <option value="monthly_fixed">Фикс месяц</option>
                      </>
                    );
                  })()}
                </select>
              </FormControl>

              {getCurrentRentalType() === 'monthly_fixed' && (
                <FormControl isRequired>
                  <FormLabel>Номер рабочего места</FormLabel>
                  <Input
                    value={openspaceFormData.workplace_number}
                    onChange={(e) => setOpenspaceFormData({ ...openspaceFormData, workplace_number: e.target.value })}
                    placeholder="Например: A-12"
                  />
                </FormControl>
              )}

              <FormControl isRequired>
                <FormLabel>Дата начала</FormLabel>
                <Input
                  type="date"
                  value={openspaceFormData.start_date}
                  onChange={(e) => setOpenspaceFormData({ ...openspaceFormData, start_date: e.target.value })}
                />
              </FormControl>

              {(() => {
                const currentType = getCurrentRentalType();
                return (currentType === 'monthly_fixed' || currentType === 'monthly_floating');
              })() && (
                <FormControl isRequired>
                  <FormLabel>Длительность (месяцев)</FormLabel>
                  <Input
                    type="number"
                    min="1"
                    max="12"
                    value={openspaceFormData.duration_months}
                    onChange={(e) => setOpenspaceFormData({ ...openspaceFormData, duration_months: parseInt(e.target.value) })}
                  />
                </FormControl>
              )}

              <FormControl isRequired>
                <FormLabel>Цена (₽)</FormLabel>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={openspaceFormData.price}
                  onChange={(e) => setOpenspaceFormData({ ...openspaceFormData, price: parseFloat(e.target.value) })}
                />
              </FormControl>

              {/* Поля для почасовых тарифов */}
              {getCurrentRentalType() === 'hourly' && (
                <>
                  <FormControl isRequired>
                    <FormLabel>Время начала</FormLabel>
                    <Input
                      type="time"
                      value={openspaceFormData.visit_time}
                      onChange={(e) => setOpenspaceFormData({ ...openspaceFormData, visit_time: e.target.value })}
                    />
                    <FormHelperText>
                      Укажите время начала аренды
                    </FormHelperText>
                  </FormControl>

                  <FormControl>
                    <FormLabel>Длительность (часов)</FormLabel>
                    <NumberInput
                      min={1}
                      max={24}
                      value={openspaceFormData.duration}
                      onChange={(valueString) => setOpenspaceFormData({
                        ...openspaceFormData,
                        duration: parseInt(valueString) || 1
                      })}
                    >
                      <NumberInputField />
                      <NumberInputStepper>
                        <NumberIncrementStepper />
                        <NumberDecrementStepper />
                      </NumberInputStepper>
                    </NumberInput>
                    <FormHelperText>
                      Длительность аренды в часах
                    </FormHelperText>
                  </FormControl>
                </>
              )}

              {(() => {
                const currentType = getCurrentRentalType();
                return (currentType === 'monthly_fixed' || currentType === 'monthly_floating');
              })() && (
                <>
                  <FormControl>
                    <FormLabel>Напоминания администратору</FormLabel>
                    <HStack>
                      <input
                        type="checkbox"
                        checked={openspaceFormData.admin_reminder_enabled}
                        onChange={(e) => setOpenspaceFormData({ ...openspaceFormData, admin_reminder_enabled: e.target.checked })}
                      />
                      <Text fontSize="sm" ml={2}>Включить напоминания</Text>
                    </HStack>
                    {openspaceFormData.admin_reminder_enabled && (
                      <HStack mt={2}>
                        <Text fontSize="sm">За сколько дней напомнить:</Text>
                        <NumberInput
                          size="sm"
                          maxW={20}
                          min={1}
                          max={30}
                          value={openspaceFormData.admin_reminder_days}
                          onChange={(valueString) => setOpenspaceFormData({
                            ...openspaceFormData,
                            admin_reminder_days: parseInt(valueString) || 5
                          })}
                        >
                          <NumberInputField />
                          <NumberInputStepper>
                            <NumberIncrementStepper />
                            <NumberDecrementStepper />
                          </NumberInputStepper>
                        </NumberInput>
                      </HStack>
                    )}
                  </FormControl>

                  <FormControl>
                    <FormLabel>Напоминания пользователю</FormLabel>
                    <HStack>
                      <input
                        type="checkbox"
                        checked={openspaceFormData.tenant_reminder_enabled}
                        onChange={(e) => setOpenspaceFormData({ ...openspaceFormData, tenant_reminder_enabled: e.target.checked })}
                      />
                      <Text fontSize="sm" ml={2}>Включить напоминания</Text>
                    </HStack>
                    {openspaceFormData.tenant_reminder_enabled && (
                      <HStack mt={2}>
                        <Text fontSize="sm">За сколько дней напомнить:</Text>
                        <NumberInput
                          size="sm"
                          maxW={20}
                          min={1}
                          max={30}
                          value={openspaceFormData.tenant_reminder_days}
                          onChange={(valueString) => setOpenspaceFormData({
                            ...openspaceFormData,
                            tenant_reminder_days: parseInt(valueString) || 5
                          })}
                        >
                          <NumberInputField />
                          <NumberInputStepper>
                            <NumberIncrementStepper />
                            <NumberDecrementStepper />
                          </NumberInputStepper>
                        </NumberInput>
                      </HStack>
                    )}
                  </FormControl>
                </>
              )}

              <FormControl>
                <FormLabel>Комментарий</FormLabel>
                <Textarea
                  value={openspaceFormData.notes}
                  onChange={(e) => setOpenspaceFormData({ ...openspaceFormData, notes: e.target.value })}
                  placeholder="Дополнительная информация..."
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <HStack spacing={3}>
              <Button onClick={() => setOpenspaceModalOpen(false)}>Отмена</Button>
              <Button colorScheme="blue" onClick={handleCreateRental}>
                Создать
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </ChakraModal>
    </>
  );
};

export default UserDetailModal;