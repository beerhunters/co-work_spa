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

// -------------------- API: Бронирования --------------------
export const bookingApi = {
  getAll: async (params = {}) => {
    const res = await apiClient.get('/bookings', { params });
    return res.data;
  },

  getById: async (bookingId) => {
    const res = await apiClient.get(`/bookings/${bookingId}`);
    return res.data;
  },

  create: async (bookingData) => {
    const res = await apiClient.post('/bookings', bookingData);
    return res.data;
  },

  update: async (bookingId, confirmed) => {
    const res = await apiClient.put(`/bookings/${bookingId}`, { confirmed });
    return res.data;
  },

  delete: async (bookingId) => {
    const res = await apiClient.delete(`/bookings/${bookingId}`);
    return res.data;
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