// utils/notifications.js - Утилиты для работы с браузерными уведомлениями

class BrowserNotificationManager {
  constructor() {
    this.permission = Notification.permission;
    this.audioContext = null;
    this.notificationSounds = new Map();
    this.isEnabled = false;
  }

  // Инициализация системы уведомлений
  async init() {
    // Проверяем поддержку уведомлений
    if (!('Notification' in window)) {
      console.warn('Браузер не поддерживает уведомления');
      return false;
    }

    // Проверяем поддержку Service Workers для фоновых уведомлений
    if ('serviceWorker' in navigator) {
      try {
        await navigator.serviceWorker.register('/sw.js');
        console.log('Service Worker зарегистрирован');
      } catch (error) {
        console.warn('Не удалось зарегистрировать Service Worker:', error);
      }
    }

    // Инициализируем аудио контекст для звуков
    this.initAudioContext();

    // Загружаем звуки уведомлений
    await this.loadNotificationSounds();

    return true;
  }

  // Запрос разрешения на уведомления
  async requestPermission() {
    if (this.permission === 'granted') {
      this.isEnabled = true;
      return true;
    }

    if (this.permission === 'denied') {
      return false;
    }

    try {
      const permission = await Notification.requestPermission();
      this.permission = permission;
      this.isEnabled = permission === 'granted';

      // Сохраняем настройку в localStorage
      localStorage.setItem('notificationsEnabled', this.isEnabled);

      return this.isEnabled;
    } catch (error) {
      console.error('Ошибка при запросе разрешения на уведомления:', error);
      return false;
    }
  }

  // Инициализация аудио контекста
  initAudioContext() {
    try {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    } catch (error) {
      console.warn('Не удалось инициализировать аудио контекст:', error);
    }
  }

  // Загрузка звуков уведомлений
  async loadNotificationSounds() {
    const sounds = {
      default: this.generateNotificationSound(800, 0.1), // Простой звук по умолчанию
      success: this.generateNotificationSound([523, 659, 784], 0.15), // До, Ми, Соль
      warning: this.generateNotificationSound([440, 440], 0.2), // Ля-Ля
      error: this.generateNotificationSound([349, 294], 0.25), // Фа, Ре
      message: this.generateNotificationSound([659, 523], 0.1) // Ми, До
    };

    for (const [type, audioBuffer] of Object.entries(sounds)) {
      this.notificationSounds.set(type, audioBuffer);
    }
  }

  // Генерация простого звука уведомления
  generateNotificationSound(frequencies, duration = 0.2) {
    if (!this.audioContext) return null;

    const freqArray = Array.isArray(frequencies) ? frequencies : [frequencies];
    const sampleRate = this.audioContext.sampleRate;
    const frameCount = sampleRate * duration;
    const audioBuffer = this.audioContext.createBuffer(1, frameCount, sampleRate);
    const channelData = audioBuffer.getChannelData(0);

    for (let i = 0; i < frameCount; i++) {
      let sample = 0;
      for (const freq of freqArray) {
        sample += Math.sin(2 * Math.PI * freq * i / sampleRate);
      }
      sample /= freqArray.length;

      // Применяем огибающую для плавного затухания
      const envelope = Math.max(0, 1 - (i / frameCount));
      channelData[i] = sample * envelope * 0.1; // Уменьшаем громкость
    }

    return audioBuffer;
  }

  // Воспроизведение звука
  playSound(type = 'default') {
    if (!this.audioContext || !this.notificationSounds.has(type)) return;

    try {
      const source = this.audioContext.createBufferSource();
      const gainNode = this.audioContext.createGain();

      source.buffer = this.notificationSounds.get(type);
      source.connect(gainNode);
      gainNode.connect(this.audioContext.destination);

      // Устанавливаем громкость
      gainNode.gain.value = 0.3;

      source.start();
    } catch (error) {
      console.error('Ошибка воспроизведения звука:', error);
    }
  }

  // Показ уведомления
  showNotification(title, options = {}) {
    if (!this.isEnabled || this.permission !== 'granted') {
      console.warn('Уведомления отключены или нет разрешения');
      return null;
    }

    const defaultOptions = {
      icon: '/static/favicon.ico',
      badge: '/static/apple-touch-icon.png',
      dir: 'auto',
      lang: 'ru',
      renotify: true,
      requireInteraction: false,
      silent: false, // Не отключаем системный звук полностью
      timestamp: Date.now(),
      ...options
    };

    try {
      // Воспроизводим собственный звук
      if (options.soundType && !defaultOptions.silent) {
        this.playSound(options.soundType);
      }

      // Создаем уведомление
      const notification = new Notification(title, defaultOptions);

      // Добавляем обработчики событий
      notification.onclick = (event) => {
        event.preventDefault();
        window.focus();

        if (options.onClick) {
          options.onClick(event);
        }

        notification.close();
      };

      notification.onerror = (error) => {
        console.error('Ошибка уведомления:', error);
      };

      // Автоматически закрываем через 5 секунд, если не указано иное
      if (!options.requireInteraction) {
        setTimeout(() => notification.close(), options.autoClose || 5000);
      }

      return notification;
    } catch (error) {
      console.error('Ошибка создания уведомления:', error);
      return null;
    }
  }

  // Обработка различных типов уведомлений из вашего приложения
  handleNotification(notificationData) {
    const { message, target_url, notification_type } = notificationData;

    let title = 'Coworking Admin';
    let soundType = 'default';
    let icon = '/static/favicon.ico';

    // Определяем тип уведомления по URL или типу
    if (target_url?.includes('/tickets')) {
      title = '🎫 Новое обращение';
      soundType = 'warning';
      icon = '/static/favicon.ico';
    } else if (target_url?.includes('/bookings')) {
      title = '📅 Новое бронирование';
      soundType = 'success';
      icon = '/static/favicon.ico';
    } else if (target_url?.includes('/users')) {
      title = '👤 Новый пользователь';
      soundType = 'message';
      icon = '/static/favicon.ico';
    }

    return this.showNotification(title, {
      body: message,
      soundType: soundType,
      icon: icon,
      tag: `notification-${notificationData.id}`, // Предотвращаем дубликаты
      data: notificationData,
      onClick: () => {
        // Переходим на соответствующую страницу
        if (target_url) {
          const urlParts = target_url.split('/');
          if (urlParts.length > 1) {
            // Здесь нужно будет интегрировать с вашим роутингом
            window.location.hash = `#${urlParts[1]}`;
          }
        }
      }
    });
  }

  // Проверка статуса уведомлений
  getStatus() {
    return {
      permission: this.permission,
      isEnabled: this.isEnabled,
      isSupported: 'Notification' in window,
      hasServiceWorker: 'serviceWorker' in navigator
    };
  }

  // Отключение уведомлений
  disable() {
    this.isEnabled = false;
    localStorage.setItem('notificationsEnabled', 'false');
  }

  // Включение уведомлений (если есть разрешение)
  enable() {
    if (this.permission === 'granted') {
      this.isEnabled = true;
      localStorage.setItem('notificationsEnabled', 'true');
      return true;
    }
    return false;
  }
}

// Создаем глобальный экземпляр
const notificationManager = new BrowserNotificationManager();

export default notificationManager;