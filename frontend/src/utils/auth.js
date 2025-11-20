// utils/auth.js
import axios from 'axios';

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

const DEFAULT_API_BASE_URL = getApiBaseUrl();


// Работа с токенами в localStorage
export const getAuthToken = () => localStorage.getItem('authToken');
export const setAuthToken = (token) => localStorage.setItem('authToken', token);
export const removeAuthToken = () => {
  localStorage.removeItem('authToken');
  localStorage.removeItem('refreshToken');
};

export const getRefreshToken = () => localStorage.getItem('refreshToken');
export const setRefreshToken = (token) => localStorage.setItem('refreshToken', token);
export const removeRefreshToken = () => localStorage.removeItem('refreshToken');

// Ссылка на axios instance, к которому привязаны интерцепторы
let boundClient = null;

/**
 * Инициализирует интерцепторы на переданном axios instance и
 * привязывает к нему auth-утилиты (login, logout, verify).
 */
export const initAuth = (axiosInstance) => {
  if (!axiosInstance || typeof axiosInstance.interceptors !== 'object') {
    throw new Error('initAuth: требуется валидный axios instance');
  }

  boundClient = axiosInstance;

  // REQUEST: подставляем токен в Authorization
  boundClient.interceptors.request.use(
    (config) => {
      const token = getAuthToken();
      if (!config.headers) config.headers = {};
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      } else {
        // На всякий случай убираем возможный предыдущий заголовок
        delete config.headers.Authorization;
      }
      return config;
    },
    (error) => Promise.reject(error)
  );

  // RESPONSE: обработка 401 и истекших токенов с автоматическим обновлением
  let isRefreshing = false;
  let failedQueue = [];

  const processQueue = (error, token = null) => {
    failedQueue.forEach(prom => {
      if (error) {
        prom.reject(error);
      } else {
        prom.resolve(token);
      }
    });
    failedQueue = [];
  };

  boundClient.interceptors.response.use(
    (response) => response,
    async (error) => {
      const status = error?.response?.status;
      const originalRequest = error.config;
      const url = originalRequest?.url || '';

      // Обрабатываем 401 ошибки (токен истек)
      if (status === 401 && !url.includes('/login') && !url.includes('/auth/refresh')) {
        const refreshToken = getRefreshToken();

        // Если нет refresh токена, разлогиниваем
        if (!refreshToken) {
          console.log('🚨 No refresh token available - logging out');
          removeAuthToken();
          window.location.href = '/';
          return Promise.reject(error);
        }

        // Если уже идет процесс обновления токена, добавляем запрос в очередь
        if (isRefreshing) {
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject });
          }).then(token => {
            originalRequest.headers['Authorization'] = 'Bearer ' + token;
            return boundClient(originalRequest);
          }).catch(err => {
            return Promise.reject(err);
          });
        }

        originalRequest._retry = true;
        isRefreshing = true;

        try {
          // Попытка обновить токен
          console.log('🔄 Attempting to refresh access token');
          const response = await axios.post(`${DEFAULT_API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken
          });

          if (response.data?.access_token) {
            setAuthToken(response.data.access_token);
          }
          if (response.data?.refresh_token) {
            setRefreshToken(response.data.refresh_token);
          }

          const newToken = response.data.access_token;
          console.log('✅ Token refreshed successfully');

          // Обновляем заголовок оригинального запроса
          originalRequest.headers['Authorization'] = 'Bearer ' + newToken;

          // Обрабатываем очередь ожидающих запросов
          processQueue(null, newToken);

          // Повторяем оригинальный запрос
          return boundClient(originalRequest);

        } catch (refreshError) {
          // Не удалось обновить токен - разлогиниваем пользователя
          console.log('❌ Failed to refresh token - logging out');
          processQueue(refreshError, null);
          removeAuthToken();

          // Показываем предупреждение только если это не фоновый запрос
          if (!url.includes('/notifications/check_new')) {
            console.warn('Сессия истекла. Необходимо повторно авторизоваться.');
          }

          window.location.href = '/';
          return Promise.reject(refreshError);

        } finally {
          isRefreshing = false;
        }
      }

      return Promise.reject(error);
    }
  );
};

// Вспомогательный ensure-клиент на случай прямого импорта auth.js без api.js
const ensureClient = () => {
  if (boundClient) return boundClient;

  // Fallback: создаём собственный instance и навешиваем те же интерцепторы
  const fallback = axios.create({
    baseURL: DEFAULT_API_BASE_URL,
    withCredentials: true
  });
  initAuth(fallback);
  return boundClient;
};

// ---- Операции авторизации, всегда используют один и тот же client ----
export const verifyToken = async () => {
  const token = getAuthToken();
  if (!token) {
    throw new Error('Нет токена для проверки');
  }

  try {
    const client = ensureClient();
    const response = await client.get('/verify_token');
    return response.data;
  } catch (error) {
    // При ошибке проверки токена всегда очищаем его
    if (error?.response?.status === 401) {
      console.log('🚨 Token verification failed - clearing token');
      removeAuthToken();
    }
    throw error;
  }
};

// Проверка валидности токена без выброса ошибок
export const isTokenValid = async () => {
  try {
    await verifyToken();
    return true;
  } catch (error) {
    return false;
  }
};

// Обновление access токена с помощью refresh токена
export const refreshAccessToken = async () => {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error('Нет refresh токена');
  }

  try {
    const client = ensureClient();
    const response = await client.post('/auth/refresh', { refresh_token: refreshToken });

    if (response.data?.access_token) {
      setAuthToken(response.data.access_token);
    }
    if (response.data?.refresh_token) {
      setRefreshToken(response.data.refresh_token);
    }

    return response.data;
  } catch (error) {
    // При ошибке обновления токена очищаем всё
    removeAuthToken();
    throw error;
  }
};


export const login = async (loginData) => {
  try {
    const client = ensureClient();
    const response = await client.post('/login', loginData, { withCredentials: true });
    if (response.data?.access_token) {
      setAuthToken(response.data.access_token);
    }
    if (response.data?.refresh_token) {
      setRefreshToken(response.data.refresh_token);
    }
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const logout = async () => {
  try {
    const client = ensureClient();
    await client.get('/logout', { withCredentials: true });
    removeAuthToken();
  } catch (error) {
    removeAuthToken();
    throw error;
  }
};
