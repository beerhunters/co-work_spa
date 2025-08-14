// utils/api.js
import axios from 'axios';
import { initAuth } from './auth';

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
    { url: '/users', setter: dataSetters.users },
    { url: '/bookings', setter: dataSetters.bookings },
    { url: '/tariffs', setter: dataSetters.tariffs },
    { url: '/promocodes', setter: dataSetters.promocodes },
    { url: '/tickets', setter: dataSetters.tickets },
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
          console.error(`Ошибка загрузки ${url}:`, error);
        }
      })
    );
  } catch (err) {
    console.error('Ошибка загрузки данных:', err);
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
    'users': { url: '/users', setter: dataSetters.users },
    'bookings': { url: '/bookings', setter: dataSetters.bookings },
    'tariffs': { url: '/tariffs', setter: dataSetters.tariffs },
    'promocodes': { url: '/promocodes', setter: dataSetters.promocodes },
    'tickets': { url: '/tickets', setter: dataSetters.tickets },
    'notifications': { url: '/notifications', setter: dataSetters.notifications },
    'newsletters': { url: '/newsletters', setter: dataSetters.newsletters },
    'dashboard': { url: '/dashboard/stats', setter: dataSetters.dashboardStats }
  };

  const endpoint = sectionEndpoints[sectionName];

  if (endpoint) {
    try {
      const res = await apiClient.get(endpoint.url);
      endpoint.setter(res.data);
    } catch (error) {
      console.error(`Ошибка загрузки данных для ${sectionName}:`, error);
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
        console.warn('Database temporarily unavailable, retrying...');

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
        console.warn('Database temporarily unavailable for notifications check');
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
      console.warn('Could not fetch related object:', error);
      return null;
    }
  }
};

// -------------------- API: Пользователи --------------------
export const userApi = {
  getAll: async () => {
    // Убираем параметры пагинации - получаем всех пользователей
    const res = await apiClient.get('/users');
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
    return res.data;
  },

};

// -------------------- API: Бронирования (обновленный) --------------------
// Улучшенный API для бронирований с обработкой ошибок
export const bookingApi = {
  getAll: async (params = {}) => {
    try {
      const res = await apiClient.get('/bookings', { params });
      return res.data;
    } catch (error) {
      console.error('Ошибка получения бронирований:', error);
      throw error;
    }
  },

  // Новый метод для получения детальных бронирований с улучшенной обработкой ошибок
  getAllDetailed: async (params = {}) => {
    try {
      // Логируем параметры запроса
      console.log('Запрос детальных бронирований с параметрами:', params);

      const res = await apiClient.get('/bookings/detailed', { params });
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
      // Убеждаемся, что ID передается как строка
      const id = String(bookingId);
      const res = await apiClient.get(`/bookings/${id}`);
      return res.data;
    } catch (error) {
      console.error(`Ошибка получения бронирования ${bookingId}:`, error);
      throw error;
    }
  },

  // Новый метод для получения детального бронирования с улучшенной обработкой
  getByIdDetailed: async (bookingId) => {
    try {
      // Убеждаемся, что ID передается как строка и валидный
      const id = String(bookingId);

      if (!id || id === 'undefined' || id === 'null') {
        throw new Error('Invalid booking ID');
      }

      console.log(`Запрос детального бронирования ID: ${id}`);

      const res = await apiClient.get(`/bookings/${id}/detailed`);
      return res.data;
    } catch (error) {
      console.error(`Ошибка получения детального бронирования ${bookingId}:`, error);

      // Детальная обработка ошибок 422
      if (error.response?.status === 422) {
        console.error('422 Ошибка при получении детального бронирования:', error.response.data);

        // Проверяем, является ли проблема в format ID
        if (error.response.data?.detail?.includes('booking ID')) {
          throw new Error(`Неверный формат ID бронирования: ${bookingId}`);
        }

        throw new Error('Ошибка валидации: ' + JSON.stringify(error.response.data));
      }

      // Fallback на обычный метод если детальный недоступен
      if (error.response?.status === 404) {
        console.warn('Детальный endpoint недоступен, используем fallback');
        return await bookingApi.getById(bookingId);
      }

      throw error;
    }
  },

  // Новый метод для валидации ID перед запросом
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
      // Валидируем данные перед отправкой
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

  update: async (bookingId, confirmed) => {
    try {
      const id = String(bookingId);
      const res = await apiClient.put(`/bookings/${id}`, {
        confirmed: Boolean(confirmed)
      });
      return res.data;
    } catch (error) {
      console.error(`Ошибка обновления бронирования ${bookingId}:`, error);
      throw error;
    }
  },

  delete: async (bookingId) => {
    try {
      const id = String(bookingId);
      const res = await apiClient.delete(`/bookings/${id}`);
      return res.data;
    } catch (error) {
      console.error(`Ошибка удаления бронирования ${bookingId}:`, error);
      throw error;
    }
  },

  // Новый метод для получения статистики с улучшенной обработкой ошибок
  getStats: async () => {
    try {
      const res = await apiClient.get('/bookings/stats');
      return res.data;
    } catch (error) {
      console.warn('Статистика бронирований недоступна:', error);

      // Возвращаем дефолтные значения если статистика недоступна
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

  // Вспомогательный метод для отладки
  debug: async (bookingId) => {
    try {
      const id = String(bookingId);
      console.group(`Отладка бронирования ID: ${id}`);

      // Проверяем валидность ID
      const validation = await bookingApi.validateId(id);
      console.log('Валидация ID:', validation);

      if (validation.exists) {
        // Пробуем получить базовую информацию
        try {
          const basic = await bookingApi.getById(id);
          console.log('Базовая информация:', basic);
        } catch (basicError) {
          console.error('Ошибка получения базовой информации:', basicError);
        }

        // Пробуем получить детальную информацию
        try {
          const detailed = await bookingApi.getByIdDetailed(id);
          console.log('Детальная информация:', detailed);
        } catch (detailedError) {
          console.error('Ошибка получения детальной информации:', detailedError);
        }
      }

      console.groupEnd();
      return validation;
    } catch (error) {
      console.error('Ошибка отладки:', error);
      return { error: error.message };
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

// -------------------- API: Заявки --------------------

export const ticketApi = {
  getAll: async (params = {}) => {
    const res = await apiClient.get('/tickets', { params });
    return res.data;
  },

  getById: async (ticketId) => {
    const res = await apiClient.get(`/tickets/${ticketId}`);
    return res.data;
  },

  create: async (ticketData) => {
    const res = await apiClient.post('/tickets', ticketData);
    return res.data;
  },

  update: async (ticketId, status, comment, responsePhoto = null) => {
    let updateData = { status, comment };

    // Если есть фото, сначала загружаем его
    if (responsePhoto) {
      try {
        const photoData = await ticketApi.uploadResponsePhoto(ticketId, responsePhoto);
        updateData.response_photo_id = photoData.photo_id;
      } catch (error) {
        console.error('Ошибка загрузки фото:', error);
        throw new Error('Не удалось загрузить фото к ответу');
      }
    }

    const res = await apiClient.put(`/tickets/${ticketId}`, updateData);
    return res.data;
  },

  delete: async (ticketId) => {
    const res = await apiClient.delete(`/tickets/${ticketId}`);
    return res.data;
  },

  // Загрузка фото в ответе администратора
  uploadResponsePhoto: async (ticketId, file) => {
    const formData = new FormData();
    formData.append('file', file);

    const res = await apiClient.post(`/tickets/${ticketId}/photo`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  // Получение фото пользователя (прикрепленного к тикету)
  getPhoto: async (ticketId) => {
    const res = await apiClient.get(`/tickets/${ticketId}/photo`, {
      responseType: 'blob'
    });
    return res.data;
  },

  // Получение URL для отображения фото
  getPhotoUrl: (ticketId) => {
    return `${apiClient.defaults.baseURL}/tickets/${ticketId}/photo`;
  }
};

// -------------------- API: Рассылки --------------------

export const newsletterApi = {
  getAll: async (page = 1, perPage = 20) => {
    const res = await apiClient.get('/newsletters', {
      params: { page, per_page: perPage }
    });
    return res.data;
  },
  create: async (message) => {
    const res = await apiClient.post('/newsletters', { message });
    return res.data;
  }
};

// -------------------- API: Дашборд --------------------

export const dashboardApi = {
  getStats: async () => {
    const res = await apiClient.get('/dashboard/stats');
    return res.data;
  }
};

export default apiClient;