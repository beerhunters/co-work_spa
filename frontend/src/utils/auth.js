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


// SECURITY: Используем sessionStorage вместо localStorage для повышения безопасности
// sessionStorage очищается при закрытии вкладки/окна, снижая риск кражи токенов
export const getAuthToken = () => sessionStorage.getItem('authToken');
export const setAuthToken = (token) => {
  sessionStorage.setItem('authToken', token);
  // Запускаем проактивное обновление токена при установке нового токена
  scheduleTokenRefresh(token);
};
export const removeAuthToken = () => {
  sessionStorage.removeItem('authToken');
  sessionStorage.removeItem('refreshToken');
  // Также очищаем из localStorage для backward compatibility
  localStorage.removeItem('authToken');
  localStorage.removeItem('refreshToken');
  clearTokenRefreshTimer();
};

export const getRefreshToken = () => sessionStorage.getItem('refreshToken');
export const setRefreshToken = (token) => sessionStorage.setItem('refreshToken', token);
export const removeRefreshToken = () => {
  sessionStorage.removeItem('refreshToken');
  localStorage.removeItem('refreshToken'); // Backward compatibility
};

// Декодирование JWT токена для получения payload
const decodeJWT = (token) => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    console.error('Failed to decode JWT:', e);
    return null;
  }
};

// Таймер для проактивного обновления токена
let tokenRefreshTimer = null;

// Очистка таймера обновления токена
const clearTokenRefreshTimer = () => {
  if (tokenRefreshTimer) {
    clearTimeout(tokenRefreshTimer);
    tokenRefreshTimer = null;
  }
};

// Планирование обновления токена до истечения срока
const scheduleTokenRefresh = (token) => {
  clearTokenRefreshTimer();

  const payload = decodeJWT(token);
  if (!payload || !payload.exp) {
    console.warn('Cannot schedule token refresh: invalid token payload');
    return;
  }

  const now = Math.floor(Date.now() / 1000);
  const expiresIn = payload.exp - now;

  // Обновляем токен за 2 минуты до истечения (или за 80% времени жизни для очень коротких токенов)
  const refreshBeforeExpiry = Math.min(120, Math.floor(expiresIn * 0.2));
  const refreshIn = expiresIn - refreshBeforeExpiry;

  if (refreshIn > 0) {
    console.log(`🕒 Token refresh scheduled in ${refreshIn} seconds (expires in ${expiresIn} seconds)`);
    tokenRefreshTimer = setTimeout(async () => {
      try {
        console.log('⏰ Proactive token refresh triggered');
        await refreshAccessToken();
        console.log('✅ Proactive token refresh successful');
      } catch (error) {
        console.error('❌ Proactive token refresh failed:', error);
        // Не разлогиниваем пользователя - ждем пока интерцептор обработает 401
      }
    }, refreshIn * 1000);
  } else {
    console.warn('Token already expired or expires very soon');
  }
};

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

  // Планируем обновление токена если он уже существует
  const existingToken = getAuthToken();
  if (existingToken) {
    scheduleTokenRefresh(existingToken);
  }

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
