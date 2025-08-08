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

// API для уведомлений
export const notificationApi = {
  checkNew: async (sinceId) => {
    const res = await apiClient.get(`/notifications/check_new`, {
      params: { since_id: sinceId }
    });
    return res.data;
  },

  markRead: async (notificationId) => {
    const res = await apiClient.post(`/notifications/mark_read/${notificationId}`, {});
    return res.data;
  },

  markAllRead: async () => {
    const res = await apiClient.post('/notifications/mark_all_read', {});
    return res.data;
  }
};

// API для пользователей
export const userApi = {
  getAll: async (page = 1, perPage = 20) => {
    const res = await apiClient.get('/users', {
      params: { page, per_page: perPage }
    });
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

  getAvatar: (userId) => {
    return `${API_BASE_URL}/users/${userId}/avatar`;
  },

  uploadAvatar: async (userId, file) => {
    const formData = new FormData();
    formData.append('file', file);

    const res = await apiClient.post(`/users/${userId}/avatar`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    return res.data;
  }
};

// API для бронирований
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

// API для тарифов
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

  delete: async (tariffId) => {
    const res = await apiClient.delete(`/tariffs/${tariffId}`);
    return res.data;
  }
};

// API для промокодов
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

  delete: async (promocodeId) => {
    const res = await apiClient.delete(`/promocodes/${promocodeId}`);
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
  update: async (ticketId, status, comment) => {
    const res = await apiClient.put(`/tickets/${ticketId}`, { status, comment });
    return res.data;
  },
  delete: async (ticketId) => {
    const res = await apiClient.delete(`/tickets/${ticketId}`);
    return res.data;
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