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


// Работа с токеном в localStorage
export const getAuthToken = () => localStorage.getItem('authToken');
export const setAuthToken = (token) => localStorage.setItem('authToken', token);
export const removeAuthToken = () => localStorage.removeItem('authToken');

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

  // RESPONSE: обработка 401 и истекших токенов
  boundClient.interceptors.response.use(
    (response) => response,
    (error) => {
      const status = error?.response?.status;
      const url = error?.config?.url || '';
      const errorMessage = error?.response?.data?.detail || '';

      // Обрабатываем 401 ошибки (включая истекшие токены)
      if (status === 401 && !url.includes('/login')) {
        console.log('🚨 Token expired or unauthorized - logging out', { url, errorMessage });
        
        // Очищаем токен из localStorage
        removeAuthToken();
        
        // Для периодических запросов (уведомления) не показываем alert
        if (!url.includes('/notifications/check_new')) {
          console.warn('Сессия истекла. Необходимо повторно авторизоваться.');
        }
        
        // Редиректим на главную страницу для повторного логина
        window.location.href = '/';
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


export const login = async (loginData) => {
  try {
    const client = ensureClient();
    const response = await client.post('/login', loginData, { withCredentials: true });
    if (response.data?.access_token) {
      setAuthToken(response.data.access_token);
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
