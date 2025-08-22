/**
 * Production-ready logging utility для frontend
 * Автоматически отключает отладочные логи в production
 */

// Определяем среду выполнения
const isDevelopment = import.meta.env.MODE === 'development';
const isProduction = import.meta.env.MODE === 'production';

// Получаем уровень логирования из переменных окружения
const LOG_LEVEL = import.meta.env.VITE_LOG_LEVEL || (isProduction ? 'ERROR' : 'DEBUG');

// Уровни логирования по приоритету
const LOG_LEVELS = {
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3,
  OFF: 4
};

// Текущий уровень логирования
const currentLogLevel = LOG_LEVELS[LOG_LEVEL] || LOG_LEVELS.DEBUG;

/**
 * Безопасный логгер, который отключается в production
 */
class ProductionLogger {
  constructor(context = 'App') {
    this.context = context;
    this.isDevelopment = isDevelopment;
    this.isProduction = isProduction;
  }

  /**
   * Проверяет, нужно ли выводить лог данного уровня
   */
  _shouldLog(level) {
    return LOG_LEVELS[level] >= currentLogLevel;
  }

  /**
   * Форматирует сообщение с контекстом
   */
  _formatMessage(message, data = null) {
    const timestamp = new Date().toISOString();
    const prefix = `[${timestamp}] [${this.context}]`;
    
    if (data) {
      return [prefix, message, data];
    }
    return [prefix, message];
  }

  /**
   * Отправляет логи на бэкенд (для production error tracking)
   */
  async _sendToBackend(level, message, data = null, error = null) {
    if (!isProduction || level === 'DEBUG' || level === 'INFO') {
      return; // Отправляем только WARNING, ERROR в production
    }

    try {
      const logData = {
        timestamp: new Date().toISOString(),
        level,
        context: this.context,
        message,
        data,
        user_agent: navigator.userAgent,
        url: window.location.href,
        stack: error?.stack || new Error().stack,
        environment: import.meta.env.MODE
      };

      // Отправляем на бэкенд (если есть endpoint)
      fetch('/api/frontend-logs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(logData)
      }).catch(() => {
        // Игнорируем ошибки отправки логов, чтобы не создавать циклы
      });
    } catch (err) {
      // Игнорируем ошибки логирования
    }
  }

  /**
   * DEBUG логирование - только в development
   */
  debug(message, data = null) {
    if (!this._shouldLog('DEBUG')) return;

    const args = this._formatMessage(message, data);
    console.debug(...args);
  }

  /**
   * INFO логирование - в development и если явно включено в production
   */
  info(message, data = null) {
    if (!this._shouldLog('INFO')) return;

    const args = this._formatMessage(message, data);
    console.info(...args);
    
    this._sendToBackend('INFO', message, data);
  }

  /**
   * WARNING логирование - во всех средах
   */
  warn(message, data = null) {
    if (!this._shouldLog('WARN')) return;

    const args = this._formatMessage(message, data);
    console.warn(...args);
    
    this._sendToBackend('WARN', message, data);
  }

  /**
   * ERROR логирование - во всех средах + отправка на бэкенд
   */
  error(message, error = null, data = null) {
    if (!this._shouldLog('ERROR')) return;

    const args = this._formatMessage(message, data);
    if (error) {
      console.error(...args, error);
    } else {
      console.error(...args);
    }
    
    this._sendToBackend('ERROR', message, data, error);
  }

  /**
   * API ошибки - специальное логирование для API вызовов
   */
  apiError(endpoint, method, status, message, responseData = null) {
    const errorMessage = `API Error: ${method} ${endpoint} -> ${status}`;
    const errorData = {
      endpoint,
      method,
      status,
      message,
      response: responseData
    };

    this.error(errorMessage, null, errorData);
  }

  /**
   * User actions - логирование действий пользователей
   */
  userAction(action, details = null) {
    if (isProduction && LOG_LEVEL !== 'DEBUG') {
      return; // В production не логируем пользовательские действия кроме DEBUG режима
    }

    this.info(`User Action: ${action}`, details);
  }

  /**
   * Performance metrics
   */
  performance(metric, value, context = null) {
    if (!this._shouldLog('INFO')) return;

    const perfData = {
      metric,
      value,
      context,
      timestamp: performance.now()
    };

    this.info(`Performance: ${metric} = ${value}ms`, perfData);
  }
}

// Создаем основной логгер
const logger = new ProductionLogger('Frontend');

// Для обратной совместимости создаем безопасные версии console методов
const safeConsole = {
  log: isDevelopment ? console.log.bind(console) : () => {},
  debug: isDevelopment ? console.debug.bind(console) : () => {},
  info: isDevelopment ? console.info.bind(console) : () => {},
  warn: console.warn.bind(console), // Warnings показываем всегда
  error: console.error.bind(console), // Errors показываем всегда
};

/**
 * Создать логгер для конкретного компонента/модуля
 */
export const createLogger = (context) => {
  return new ProductionLogger(context);
};

/**
 * Основной логгер приложения
 */
export default logger;

/**
 * Безопасная замена для console
 */
export { safeConsole as console };

/**
 * Utility функции для замены console.* в коде
 */
export const log = {
  debug: logger.debug.bind(logger),
  info: logger.info.bind(logger),
  warn: logger.warn.bind(logger),
  error: logger.error.bind(logger),
  apiError: logger.apiError.bind(logger),
  userAction: logger.userAction.bind(logger),
  performance: logger.performance.bind(logger),
};

/**
 * Error boundary logging helper
 */
export const logErrorBoundary = (error, errorInfo, componentName) => {
  logger.error(
    `React Error Boundary: Component ${componentName} crashed`,
    error,
    {
      componentName,
      componentStack: errorInfo.componentStack,
      errorBoundary: true
    }
  );
};

/**
 * Startup логирование
 */
export const logStartup = () => {
  logger.info('🚀 Frontend application starting', {
    environment: import.meta.env.MODE,
    logLevel: LOG_LEVEL,
    development: isDevelopment,
    production: isProduction,
    userAgent: navigator.userAgent
  });
};

// Автоматически логируем startup
if (typeof window !== 'undefined') {
  logStartup();
}

/**
 * Глобальная обработка unhandled errors
 */
if (typeof window !== 'undefined') {
  window.addEventListener('error', (event) => {
    logger.error('Unhandled JavaScript error', event.error, {
      message: event.message,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
      type: 'unhandled_error'
    });
  });

  window.addEventListener('unhandledrejection', (event) => {
    logger.error('Unhandled Promise rejection', event.reason, {
      type: 'unhandled_promise_rejection'
    });
  });
}