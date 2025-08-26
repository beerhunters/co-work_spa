import axios from 'axios';
import { initAuth } from './auth';
import { createLogger } from './logger.js';

const logger = createLogger('API');

export const API_BASE_URL = 'http://localhost/api';

// Создание axios instance с базовыми настройками
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true
});

// Инициализация авторизации
initAuth(apiClient);

// Загрузка начальных данных
export const fetchInitialData = async (dataSetters, setLastNotificationId, toast) => {
  const endpoints = [
    { url: '/users?per_page=1000', setter: dataSetters.users },
    { url: '/bookings/detailed?per_page=500', setter: (data) => dataSetters.bookings(data.bookings || []) },
    { url: '/tariffs', setter: dataSetters.tariffs },
    { url: '/promocodes', setter: dataSetters.promocodes },
    { url: '/tickets/detailed?per_page=100', setter: (data) => dataSetters.tickets(data.tickets || []) },
    { url: '/newsletters', setter: dataSetters.newsletters },
    {
      url: '/notifications',
      setter: (data) => {
        dataSetters.notifications(data);
        if (Array.isArray(data) && data.length > 0) {
          setLastNotificationId(Math.max(...data.map(n => n.id), 0));
        }
      }
    },
    { url: '/dashboard/stats', setter: dataSetters.dashboardStats }
  ];

  try {
    await Promise.all(
      endpoints.map(async ({ url, setter }) => {
        try {
          const res = await apiClient.get(url);
          setter(res.data);
        } catch (error) {
          logger.apiError(url, 'GET', error.response?.status || 'unknown', error.message, error.response?.data);
        }
      })
    );
  } catch (err) {
    logger.error('Ошибка загрузки данных:', err);
    if (toast) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось загрузить данные',
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    }
  }
};

// Загрузка данных для конкретной секции
export const fetchSectionData = async (sectionName, dataSetters) => {
  const sectionEndpoints = {
    'users': { url: '/users?per_page=1000', setter: dataSetters.users },
    'bookings': { url: '/bookings/detailed?per_page=500', setter: (data) => dataSetters.bookings(data.bookings || []) },
    'tariffs': { url: '/tariffs', setter: dataSetters.tariffs },
    'promocodes': { url: '/promocodes', setter: dataSetters.promocodes },
    'tickets': { url: '/tickets/detailed?per_page=100', setter: (data) => dataSetters.tickets(data.tickets || []) },
    'notifications': { url: '/notifications', setter: dataSetters.notifications },
    'newsletters': { url: '/newsletters', setter: dataSetters.newsletters },
    'dashboard': { url: '/dashboard/stats', setter: dataSetters.dashboardStats },
    'admins': { url: '/admins', setter: dataSetters.admins },
  };

  const endpoint = sectionEndpoints[sectionName];

  if (endpoint) {
    try {
      const res = await apiClient.get(endpoint.url);
      endpoint.setter(res.data);
    } catch (error) {
      logger.apiError(endpoint.url, 'GET', error.response?.status || 'unknown', `Ошибка загрузки данных для ${sectionName}`, error.response?.data);
      throw error;
    }
  }
};

// -------------------- API: Уведомления --------------------
export const notificationApi = {
  getAll: async (params = {}) => {
    try {
      const res = await apiClient.get('/notifications', { params });
      return res.data;
    } catch (error) {
      // Обработка специфичных ошибок БД
      if (error.response?.status === 503) {
        logger.warn('Database temporarily unavailable, retrying...');

        // Ждем и повторяем попытку
        await new Promise(resolve => setTimeout(resolve, 2000));
        const res = await apiClient.get('/notifications', { params });
        return res.data;
      }
      throw error;
    }
  },

  checkNew: async (sinceId) => {
    try {
      const res = await apiClient.get(`/notifications/check_new`, {
        params: { since_id: sinceId }
      });
      return res.data;
    } catch (error) {
      if (error.response?.status === 503) {
        logger.warn('Database temporarily unavailable for notifications check');
        return { has_new: false, recent_notifications: [] };
      }
      throw error;
    }
  },

  markRead: async (notificationId) => {
    const res = await apiClient.post(`/notifications/mark_read/${notificationId}`, {});
    return res.data;
  },

  markAllRead: async () => {
    const res = await apiClient.post('/notifications/mark_all_read', {});
    return res.data;
  },

  clearAll: async () => {
    const res = await apiClient.delete('/notifications/clear_all');
    return res.data;
  },

  delete: async (notificationId) => {
    const res = await apiClient.delete(`/notifications/${notificationId}`);
    return res.data;
  },

  create: async (notificationData) => {
    const res = await apiClient.post('/notifications/create', notificationData);
    return res.data;
  },

  // Получение связанного объекта для навигации
  getRelatedObject: async (notification) => {
    try {
      if (notification.ticket_id) {
        const res = await apiClient.get(`/tickets/${notification.ticket_id}`);
        return { type: 'ticket', data: res.data };
      } else if (notification.booking_id) {
        const res = await apiClient.get(`/bookings/${notification.booking_id}`);
        return { type: 'booking', data: res.data };
      } else if (notification.user_id) {
        const res = await apiClient.get(`/users/${notification.user_id}`);
        return { type: 'user', data: res.data };
      }
      return null;
    } catch (error) {
      logger.warn('Could not fetch related object:', error);
      return null;
    }
  }
};

// -------------------- API: Пользователи (обновленный) --------------------
export const userApi = {
  getAll: async () => {
    // Запрашиваем всех пользователей (per_page=1000 включает режим "все пользователи")
    const res = await apiClient.get('/users?per_page=1000');
    return res.data;
  },

  getById: async (userId) => {
    const res = await apiClient.get(`/users/${userId}`);
    return res.data;
  },

  update: async (userId, userData) => {
    const res = await apiClient.put(`/users/${userId}`, userData);
    return res.data;
  },

  delete: async (userId) => {
    try {
      logger.debug(`Удаление пользователя ${userId}`);

      const res = await apiClient.delete(`/users/${userId}`);

      logger.info('Пользователь успешно удален:', { userId, result: res.data });
      return res.data;
    } catch (error) {
      logger.apiError(`/users/${userId}`, 'DELETE', error.response?.status || 'unknown', 'Ошибка удаления пользователя', error.response?.data);

      if (error.response?.status === 404) {
        throw new Error('Пользователь не найден');
      }

      throw new Error(error.response?.data?.detail || 'Не удалось удалить пользователя');
    }
  },

  deleteAvatar: async (userId) => {
    const res = await apiClient.delete(`/users/${userId}/avatar`);
    return res.data;
  },

  uploadAvatar: async (userId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await apiClient.post(`/users/${userId}/avatar`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    // Безопасная предзагрузка изображения
    if (res.data.avatar_url) {
      try {
        const img = document.createElement('img');
        img.src = `/api${res.data.avatar_url}`;
        img.style.display = 'none';
        document.body.appendChild(img);
        // Удаляем элемент после загрузки
        img.onload = () => {
          document.body.removeChild(img);
        };
        img.onerror = () => {
          document.body.removeChild(img);
        };
      } catch (e) {
        logger.debug('Не удалось предзагрузить аватар:', e);
      }
    }

    return res.data;
  },

  // Скачивание аватара из Telegram
  downloadTelegramAvatar: async (userId) => {
    try {
      logger.debug(`Запрос скачивания аватара из Telegram для пользователя ${userId}`);
      const res = await apiClient.post(`/users/${userId}/download-telegram-avatar`);
      logger.info('Аватар успешно скачан', { userId, avatarPath: res.data?.avatar_path });

      // Безопасная предзагрузка изображения
      if (res.data.avatar_url) {
        try {
          const img = document.createElement('img');
          img.src = `/api${res.data.avatar_url}`;
          img.style.display = 'none';
          document.body.appendChild(img);
          // Удаляем элемент после загрузки
          img.onload = () => {
            document.body.removeChild(img);
          };
          img.onerror = () => {
            document.body.removeChild(img);
          };
        } catch (e) {
          logger.debug('Не удалось предзагрузить аватар:', e);
        }
      }

      return res.data;
    } catch (error) {
      logger.apiError(`/users/${userId}/download-telegram-avatar`, 'POST', error.response?.status || 'unknown', 'Ошибка скачивания аватара из Telegram', error.response?.data);

      // Детальная обработка ошибок
      if (error.response?.status === 404) {
        if (error.response.data?.detail?.includes('no profile photo')) {
          throw new Error('У пользователя нет фото профиля в Telegram или оно недоступно');
        } else if (error.response.data?.detail?.includes('User not found')) {
          throw new Error('Пользователь не найден');
        }
      } else if (error.response?.status === 400) {
        throw new Error('У пользователя нет Telegram ID');
      } else if (error.response?.status === 503) {
        throw new Error('Бот Telegram недоступен');
      }

      throw new Error(error.response?.data?.detail || 'Не удалось скачать аватар из Telegram');
    }
  },
};
// -------------------- API: Бронирования (обновленный с фильтрацией) --------------------
export const bookingApi = {
  getAll: async (params = {}) => {
    try {
      console.log('bookingApi.getAll вызван с параметрами:', params);
      const res = await apiClient.get('/bookings', { params });
      return res.data;
    } catch (error) {
      console.error('Ошибка получения бронирований:', error);
      throw error;
    }
  },

  // ОСНОВНОЙ метод для получения детальных бронирований с фильтрацией
  getAllDetailed: async (params = {}) => {
    try {
      // Логируем параметры запроса
      console.log('Запрос детальных бронирований с параметрами:', params);

      // Подготавливаем параметры для запроса
      const queryParams = {};

      // Пагинация
      if (params.page) queryParams.page = params.page;
      if (params.per_page) queryParams.per_page = params.per_page;

      // Фильтрация
      if (params.status_filter && params.status_filter !== 'all') {
        queryParams.status_filter = params.status_filter;
      }

      if (params.tariff_filter && params.tariff_filter !== 'all') {
        queryParams.tariff_filter = params.tariff_filter;
      }

      if (params.user_query && params.user_query.trim()) {
        queryParams.user_query = params.user_query.trim();
      }

      if (params.date_query && params.date_query.trim()) {
        queryParams.date_query = params.date_query.trim();
      }

      console.log('Финальные параметры запроса:', queryParams);

      const res = await apiClient.get('/bookings/detailed', { params: queryParams });

      console.log('Ответ сервера:', {
        bookingsCount: res.data.bookings?.length || 0,
        totalCount: res.data.total_count,
        page: res.data.page,
        totalPages: res.data.total_pages
      });

      return res.data;
    } catch (error) {
      console.error('Ошибка получения детальных бронирований:', error);

      // Детальная обработка различных типов ошибок
      if (error.response?.status === 422) {
        console.error('422 Ошибка валидации:', error.response.data);
        throw new Error('Ошибка валидации данных: ' + JSON.stringify(error.response.data));
      }

      if (error.response?.status === 404) {
        console.warn('Endpoint не найден, используем fallback');
        const res = await apiClient.get('/bookings', { params });
        return {
          bookings: res.data,
          total_count: res.data.length,
          page: params.page || 1,
          per_page: params.per_page || 20,
          total_pages: Math.ceil(res.data.length / (params.per_page || 20))
        };
      }

      throw error;
    }
  },

  getById: async (bookingId) => {
    try {
      const id = String(bookingId);
      const res = await apiClient.get(`/bookings/${id}`);
      return res.data;
    } catch (error) {
      console.error(`Ошибка получения бронирования ${bookingId}:`, error);
      throw error;
    }
  },

  getByIdDetailed: async (bookingId) => {
    try {
      const id = String(bookingId);

      if (!id || id === 'undefined' || id === 'null') {
        throw new Error('Invalid booking ID');
      }

      console.log(`Запрос детального бронирования ID: ${id}`);

      const res = await apiClient.get(`/bookings/${id}/detailed`);
      return res.data;
    } catch (error) {
      console.error(`Ошибка получения детального бронирования ${bookingId}:`, error);

      if (error.response?.status === 422) {
        console.error('422 Ошибка при получении детального бронирования:', error.response.data);
        if (error.response.data?.detail?.includes('booking ID')) {
          throw new Error(`Неверный формат ID бронирования: ${bookingId}`);
        }
        throw new Error('Ошибка валидации: ' + JSON.stringify(error.response.data));
      }

      if (error.response?.status === 404) {
        console.warn('Детальный endpoint недоступен, используем fallback');
        return await bookingApi.getById(bookingId);
      }

      throw error;
    }
  },

  validateId: async (bookingId) => {
    try {
      const id = String(bookingId);
      const res = await apiClient.get(`/bookings/${id}/validate`);
      return res.data;
    } catch (error) {
      console.error(`Ошибка валидации ID ${bookingId}:`, error);
      return { exists: false, error: error.message };
    }
  },

  create: async (bookingData) => {
    try {
      const validatedData = {
        ...bookingData,
        user_id: Number(bookingData.user_id),
        tariff_id: Number(bookingData.tariff_id),
        amount: Number(bookingData.amount),
        paid: Boolean(bookingData.paid),
        confirmed: Boolean(bookingData.confirmed)
      };

      const res = await apiClient.post('/bookings', validatedData);
      return res.data;
    } catch (error) {
      console.error('Ошибка создания бронирования:', error);

      if (error.response?.status === 422) {
        console.error('422 Ошибка при создании:', error.response.data);
        throw new Error('Ошибка валидации данных: ' + JSON.stringify(error.response.data));
      }

      throw error;
    }
  },

  updateBooking: async (bookingId, updateData) => {
    try {
      const id = String(bookingId);

      console.log(`Обновление бронирования ${id} с данными:`, updateData);

      const validatedData = {};

      if ('confirmed' in updateData) {
        validatedData.confirmed = Boolean(updateData.confirmed);
      }

      if ('paid' in updateData) {
        validatedData.paid = Boolean(updateData.paid);
      }

      if ('amount' in updateData) {
        validatedData.amount = Number(updateData.amount);
      }

      const res = await apiClient.put(`/bookings/${id}`, validatedData);
      return res.data;
    } catch (error) {
      console.error(`Ошибка обновления бронирования ${bookingId}:`, error);

      if (error.response?.status === 404) {
        throw new Error('Бронирование не найдено');
      }

      if (error.response?.status === 422) {
        console.error('422 Ошибка валидации при обновлении:', error.response.data);
        throw new Error('Ошибка валидации данных: ' + (error.response.data?.detail || 'неизвестная ошибка'));
      }

      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }

      throw new Error('Не удалось обновить бронирование');
    }
  },

  // Метод для подтверждения бронирования (legacy - для совместимости)
  update: async (bookingId, confirmed) => {
    console.warn('bookingApi.update deprecated, используйте bookingApi.updateBooking');
    return await bookingApi.updateBooking(bookingId, { confirmed: Boolean(confirmed) });
  },

  // Удобные методы для конкретных действий
  markAsPaid: async (bookingId) => {
    return await bookingApi.updateBooking(bookingId, { paid: true });
  },

  markAsUnpaid: async (bookingId) => {
    return await bookingApi.updateBooking(bookingId, { paid: false });
  },

  confirm: async (bookingId) => {
    return await bookingApi.updateBooking(bookingId, { confirmed: true });
  },

  unconfirm: async (bookingId) => {
    return await bookingApi.updateBooking(bookingId, { confirmed: false });
  },

  confirmAndMarkPaid: async (bookingId) => {
    return await bookingApi.updateBooking(bookingId, {
      confirmed: true,
      paid: true
    });
  },

  delete: async (bookingId) => {
    try {
      const id = String(bookingId);
      const res = await apiClient.delete(`/bookings/${id}`);
      return res.data;
    } catch (error) {
      console.error(`Ошибка удаления бронирования ${bookingId}:`, error);

      if (error.response?.status === 404) {
        throw new Error('Бронирование не найдено');
      }

      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }

      throw new Error('Не удалось удалить бронирование');
    }
  },

  getStats: async () => {
    try {
      const res = await apiClient.get('/bookings/stats');
      return res.data;
    } catch (error) {
      console.warn('Статистика бронирований недоступна:', error);

      return {
        total_bookings: 0,
        paid_bookings: 0,
        confirmed_bookings: 0,
        total_revenue: 0,
        current_month_bookings: 0,
        current_month_revenue: 0,
        top_tariffs: []
      };
    }
  },

  // Метод для массовых операций
  bulkUpdate: async (bookingIds, updateData) => {
    try {
      console.log(`Массовое обновление ${bookingIds.length} бронирований:`, updateData);

      const promises = bookingIds.map(id =>
        bookingApi.updateBooking(id, updateData)
      );

      const results = await Promise.allSettled(promises);

      const successful = results.filter(r => r.status === 'fulfilled');
      const failed = results.filter(r => r.status === 'rejected');

      console.log(`✅ Успешно обновлено: ${successful.length}`);
      if (failed.length > 0) {
        console.log(`❌ Ошибок при обновлении: ${failed.length}`);
        failed.forEach((result, index) => {
          console.error(`Ошибка для ID ${bookingIds[index]}:`, result.reason);
        });
      }

      return {
        successful: successful.length,
        failed: failed.length,
        results: results
      };
    } catch (error) {
      console.error('Ошибка массового обновления:', error);
      throw error;
    }
  }
};

// -------------------- API: Тарифы --------------------
export const tariffApi = {
  getAll: async () => {
    const res = await apiClient.get('/tariffs');
    return res.data;
  },

  getById: async (tariffId) => {
    const res = await apiClient.get(`/tariffs/${tariffId}`);
    return res.data;
  },

  create: async (tariffData) => {
    const res = await apiClient.post('/tariffs', tariffData);
    return res.data;
  },

  update: async (tariffId, tariffData) => {
    const res = await apiClient.put(`/tariffs/${tariffId}`, tariffData);
    return res.data;
  },

  delete: async (tariffId) => {
    const res = await apiClient.delete(`/tariffs/${tariffId}`);
    return res.data;
  },

  getActive: async () => {
    const res = await apiClient.get('/tariffs/active');
    return res.data;
  }
};

// -------------------- API: Промокоды --------------------
export const promocodeApi = {
  getAll: async () => {
    const res = await apiClient.get('/promocodes');
    return res.data;
  },

  getById: async (promocodeId) => {
    const res = await apiClient.get(`/promocodes/${promocodeId}`);
    return res.data;
  },

  create: async (promocodeData) => {
    const res = await apiClient.post('/promocodes', promocodeData);
    return res.data;
  },

  update: async (promocodeId, promocodeData) => {
    const res = await apiClient.put(`/promocodes/${promocodeId}`, promocodeData);
    return res.data;
  },

  delete: async (promocodeId) => {
    const res = await apiClient.delete(`/promocodes/${promocodeId}`);
    return res.data;
  },

  getByName: async (name) => {
    const res = await apiClient.get(`/promocodes/by_name/${name}`);
    return res.data;
  },

  use: async (promocodeId) => {
    const res = await apiClient.post(`/promocodes/${promocodeId}/use`);
    return res.data;
  }
};

// -------------------- API: Заявки (обновленный с фильтрацией) --------------------
export const ticketApi = {
  // ОСНОВНОЙ метод для получения тикетов с фильтрацией
  getAllDetailed: async (params = {}) => {
    try {
      console.log('Запрос тикетов с параметрами:', params);

      // Подготавливаем параметры для запроса
      const queryParams = {};

      // Пагинация
      if (params.page) queryParams.page = params.page;
      if (params.per_page) queryParams.per_page = params.per_page;

      // Фильтрация
      if (params.status && params.status !== 'all') {
        queryParams.status = params.status;
      }

      if (params.user_query && params.user_query.trim()) {
        queryParams.user_query = params.user_query.trim();
      }

      console.log('Финальные параметры запроса тикетов:', queryParams);

      const res = await apiClient.get('/tickets/detailed', { params: queryParams });

      console.log('Ответ сервера для тикетов:', {
        ticketsCount: res.data.tickets?.length || 0,
        totalCount: res.data.total_count,
        page: res.data.page,
        totalPages: res.data.total_pages
      });

      return res.data;
    } catch (error) {
      console.error('Ошибка получения детальных тикетов:', error);

      // Fallback на обычный эндпоинт
      if (error.response?.status === 404) {
        console.warn('Эндпоинт /tickets/detailed не найден, используем fallback');
        const res = await apiClient.get('/tickets', { params });
        return {
          tickets: res.data,
          total_count: res.data.length,
          page: params.page || 1,
          per_page: params.per_page || 20,
          total_pages: Math.ceil(res.data.length / (params.per_page || 20))
        };
      }

      throw error;
    }
  },

  getAll: async (params = {}) => {
    try {
      console.log('ticketApi.getAll вызван с параметрами:', params);
      const res = await apiClient.get('/tickets', { params });
      return res.data;
    } catch (error) {
      console.error('Ошибка получения тикетов:', error);
      throw error;
    }
  },

  getById: async (ticketId) => {
    try {
      const res = await apiClient.get(`/tickets/${ticketId}`);
      return res.data;
    } catch (error) {
      console.error(`Ошибка получения тикета ${ticketId}:`, error);
      throw error;
    }
  },

  create: async (ticketData) => {
    try {
      const res = await apiClient.post('/tickets', ticketData);
      return res.data;
    } catch (error) {
      console.error('Ошибка создания тикета:', error);
      throw error;
    }
  },

  update: async (ticketId, status, comment, responsePhoto = null) => {
    try {
      // Если есть фото, отправляем его пользователю с комментарием и статусом
      if (responsePhoto) {
        const photoResult = await ticketApi.sendPhotoToUser(ticketId, responsePhoto, comment, status);
        console.log('Фото с комментарием отправлено пользователю:', photoResult);

        // Возвращаем обновленный тикет из ответа
        return photoResult.updated_ticket;
      } else {
        // Обычное обновление без фото
        const updateData = { status, comment };
        const res = await apiClient.put(`/tickets/${ticketId}`, updateData);
        return res.data;
      }
    } catch (error) {
      console.error('Ошибка обновления тикета:', error);
      throw error;
    }
  },

  delete: async (ticketId) => {
    try {
      const res = await apiClient.delete(`/tickets/${ticketId}`);
      return res.data;
    } catch (error) {
      console.error(`Ошибка удаления тикета ${ticketId}:`, error);
      throw error;
    }
  },

  // Отправка фото пользователю с комментарием и статусом
  sendPhotoToUser: async (ticketId, file, comment = null, status = null) => {
    try {
      const formData = new FormData();
      formData.append('file', file);

      if (comment && comment.trim()) {
        formData.append('comment', comment.trim());
      }

      if (status) {
        formData.append('status', status);
      }

      const res = await apiClient.post(`/tickets/${ticketId}/photo`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return res.data;
    } catch (error) {
      console.error('Ошибка отправки фото пользователю:', error);
      throw error;
    }
  },

  // Получение фото в base64 (рекомендуемый)
  getPhotoBase64: async (ticketId) => {
    try {
      const res = await apiClient.get(`/tickets/${ticketId}/photo-base64`);
      return res.data.photo_url; // Возвращает data URL
    } catch (error) {
      console.error('Ошибка получения фото:', error);
      return null;
    }
  },

  // Получение статистики тикетов
  getStats: async () => {
    try {
      const res = await apiClient.get('/tickets/stats');
      return res.data;
    } catch (error) {
      console.warn('Статистика тикетов недоступна:', error);
      return {
        total_tickets: 0,
        open_tickets: 0,
        in_progress_tickets: 0,
        closed_tickets: 0,
        avg_response_time: 0
      };
    }
  },

  // Устаревшие методы для совместимости
  getPhotoUrl: (ticketId) => {
    const token = localStorage.getItem('token');
    return `${apiClient.defaults.baseURL}/tickets/${ticketId}/photo?token=${encodeURIComponent(token)}`;
  },

  uploadResponsePhoto: async (ticketId, file) => {
    console.warn('uploadResponsePhoto deprecated, используйте sendPhotoToUser');
    return await ticketApi.sendPhotoToUser(ticketId, file);
  },

  getPhoto: async (ticketId) => {
    console.warn('getPhoto deprecated, используйте getPhotoBase64');
    return await ticketApi.getPhotoBase64(ticketId);
  }
};

// -------------------- API: Рассылки --------------------
export const newsletterApi = {
  // Отправка рассылки
  send: async (formData) => {
    try {
      console.log('Отправка рассылки...');
      const res = await apiClient.post('/newsletters/send', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      console.log('Рассылка отправлена:', res.data);
      return res.data;
    } catch (error) {
      console.error('Ошибка отправки рассылки:', error);

      const detail = error.response?.data?.detail;
      if (detail?.includes('Message cannot be empty')) {
        throw new Error('Сообщение не может быть пустым');
      } else if (detail?.includes('No users selected')) {
        throw new Error('Не выбраны получатели');
      } else if (detail?.includes('Maximum 10 photos')) {
        throw new Error('Максимум 10 фотографий');
      } else if (detail?.includes('No valid recipients')) {
        throw new Error('Не найдено подходящих получателей');
      } else if (error.response?.status === 503) {
        throw new Error('Telegram бот недоступен');
      }

      throw new Error(error.response?.data?.detail || 'Не удалось отправить рассылку');
    }
  },

  // Получение истории рассылок
  getHistory: async (limit = 50, offset = 0) => {
    try {
      const res = await apiClient.get('/newsletters/history', {
        params: { limit, offset }
      });
      return res.data;
    } catch (error) {
      console.error('Ошибка получения истории рассылок:', error);
      throw new Error(error.response?.data?.detail || 'Не удалось загрузить историю рассылок');
    }
  },

  // Получение деталей рассылки
  getDetail: async (newsletterId) => {
    try {
      const res = await apiClient.get(`/newsletters/${newsletterId}`);
      return res.data;
    } catch (error) {
      console.error('Ошибка получения деталей рассылки:', error);

      if (error.response?.status === 404) {
        throw new Error('Рассылка не найдена');
      }

      throw new Error(error.response?.data?.detail || 'Не удалось загрузить детали рассылки');
    }
  },

  // Удаление рассылки
  delete: async (newsletterId) => {
    try {
      const res = await apiClient.delete(`/newsletters/${newsletterId}`);
      console.log('Рассылка удалена:', res.data);
      return res.data;
    } catch (error) {
      console.error('Ошибка удаления рассылки:', error);
      throw new Error(error.response?.data?.detail || 'Не удалось удалить рассылку');
    }
  },

  // Очистка всей истории рассылок
  clearHistory: async () => {
    try {
      const res = await apiClient.delete('/newsletters/clear-history');
      console.log('История рассылок очищена:', res.data);
      return res.data;
    } catch (error) {
      console.error('Ошибка очистки истории рассылок:', error);
      throw new Error(error.response?.data?.detail || 'Не удалось очистить историю рассылок');
    }
  },

  // Валидация сообщения
  validateMessage: (message) => {
    const allowedTags = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'code', 'pre', 'a'];
    const tagRegex = /<\/?([a-z][a-z0-9]*)\b[^>]*>/gi;
    const openTags = [];
    let match;

    while ((match = tagRegex.exec(message)) !== null) {
      const isClosing = match[0].startsWith('</');
      const tagName = match[1].toLowerCase();

      if (!allowedTags.includes(tagName)) {
        return {
          isValid: false,
          error: `Недопустимый тег: <${tagName}>`
        };
      }

      if (isClosing) {
        const lastOpen = openTags.pop();
        if (lastOpen !== tagName) {
          return {
            isValid: false,
            error: `Неправильно закрытый тег: </${tagName}>`
          };
        }
      } else if (!match[0].endsWith('/>')) {
        openTags.push(tagName);
      }
    }

    if (openTags.length > 0) {
      return {
        isValid: false,
        error: `Незакрытые теги: ${openTags.map(t => `<${t}>`).join(', ')}`
      };
    }

    return { isValid: true };
  },

  // Форматирование текста
  formatText: (text, format) => {
    const formatters = {
      bold: (t) => `<b>${t}</b>`,
      italic: (t) => `<i>${t}</i>`,
      underline: (t) => `<u>${t}</u>`,
      strike: (t) => `<s>${t}</s>`,
      code: (t) => `<code>${t}</code>`,
      pre: (t) => `<pre>${t}</pre>`,
      link: (t, url) => `<a href="${url}">${t}</a>`
    };

    return formatters[format] ? formatters[format](text) : text;
  }
};
// -------------------- API: Дашборд --------------------
export const dashboardApi = {
  getStats: async () => {
    const res = await apiClient.get('/dashboard/stats');
    return res.data;
  }
};

// --------------------- API: Админы ---------------------
export const adminApi = {
  // Получение списка всех администраторов
  getAll: async () => {
    try {
      const res = await apiClient.get('/admins');
      return res.data;
    } catch (error) {
      console.error('Ошибка получения списка администраторов:', error);
      throw new Error(error.response?.data?.detail || 'Не удалось загрузить администраторов');
    }
  },

  // Получение информации о конкретном администраторе
  getById: async (adminId) => {
    try {
      const res = await apiClient.get(`/admins/${adminId}`);
      return res.data;
    } catch (error) {
      console.error('Ошибка получения администратора:', error);

      if (error.response?.status === 404) {
        throw new Error('Администратор не найден');
      }

      throw new Error(error.response?.data?.detail || 'Не удалось загрузить данные администратора');
    }
  },

  // Создание нового администратора
  create: async (adminData) => {
    try {
      const res = await apiClient.post('/admins', adminData);
      console.log('Администратор создан:', res.data);
      return res.data;
    } catch (error) {
      console.error('Ошибка создания администратора:', error);

      const detail = error.response?.data?.detail;
      if (detail?.includes('уже существует')) {
        throw new Error('Администратор с таким логином уже существует');
      }

      throw new Error(error.response?.data?.detail || 'Не удалось создать администратора');
    }
  },

  // Обновление администратора
  update: async (adminId, adminData) => {
    try {
      const res = await apiClient.put(`/admins/${adminId}`, adminData);
      console.log('Администратор обновлен:', res.data);
      return res.data;
    } catch (error) {
      console.error('Ошибка обновления администратора:', error);

      const detail = error.response?.data?.detail;
      if (detail?.includes('уже существует')) {
        throw new Error('Администратор с таким логином уже существует');
      } else if (detail?.includes('супер админа')) {
        throw new Error('Нельзя редактировать главного администратора');
      }

      throw new Error(error.response?.data?.detail || 'Не удалось обновить администратора');
    }
  },

  // Удаление администратора
  delete: async (adminId) => {
    try {
      const res = await apiClient.delete(`/admins/${adminId}`);
      console.log('Администратор удален:', res.data);
      return res.data;
    } catch (error) {
      console.error('Ошибка удаления администратора:', error);

      const detail = error.response?.data?.detail;
      if (detail?.includes('супер админа')) {
        throw new Error('Нельзя удалить главного администратора');
      } else if (detail?.includes('самого себя')) {
        throw new Error('Нельзя удалить самого себя');
      } else if (error.response?.status === 404) {
        throw new Error('Администратор не найден');
      }

      throw new Error(error.response?.data?.detail || 'Не удалось удалить администратора');
    }
  },

  // Получение доступных разрешений
  getAvailablePermissions: async () => {
    try {
      const res = await apiClient.get('/admins/permissions');
      return res.data;
    } catch (error) {
      console.error('Ошибка получения разрешений:', error);
      throw new Error(error.response?.data?.detail || 'Не удалось загрузить список разрешений');
    }
  },

  // Смена пароля текущего администратора
  changePassword: async (passwordData) => {
    try {
      const res = await apiClient.post('/admins/change-password', passwordData);
      console.log('Пароль изменен:', res.data);
      return res.data;
    } catch (error) {
      console.error('Ошибка смены пароля:', error);

      const detail = error.response?.data?.detail;
      if (detail?.includes('Неверный текущий пароль')) {
        throw new Error('Неверный текущий пароль');
      }

      throw new Error(error.response?.data?.detail || 'Не удалось изменить пароль');
    }
  },

  // Получение текущего профиля
  getCurrentProfile: async () => {
    try {
      const res = await apiClient.get('/admins/current/profile');
      return res.data;
    } catch (error) {
      console.error('Ошибка получения профиля:', error);
      throw new Error(error.response?.data?.detail || 'Не удалось загрузить профиль');
    }
  }
};

export default apiClient;