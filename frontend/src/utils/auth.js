// utils/auth.js
import axios from 'axios';

// Базовый URL по умолчанию на случай fallback-инициализации
// const DEFAULT_API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost/api';
const DEFAULT_API_BASE_URL = 'https://parta.webhop.me/api';


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

  // RESPONSE: обработка 401
  boundClient.interceptors.response.use(
    (response) => response,
    (error) => {
      const status = error?.response?.status;
      const url = error?.config?.url || '';

      // Чтобы не мешать форме логина при неверных данных — не редиректим на / для /login
      if (status === 401 && !url.includes('/login')) {
        removeAuthToken();
        // Можно заменить на роутер-навигацию, если используешь react-router
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
