// utils/notifications.js - Компактная версия для браузерных уведомлений

class BrowserNotificationManager {
  constructor() {
    this.permission = Notification.permission;
    this.isEnabled = false;
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
      return this.isEnabled;
    } catch (error) {
      console.error('Ошибка при запросе разрешения на уведомления:', error);
      return false;
    }
  }

  // Воспроизведение простого звука
  playSound(type = 'default') {
    try {
      // Создаем аудио контекст для воспроизведения звука
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();

      let frequency = 800; // По умолчанию

      // Разные частоты для разных типов
      switch (type) {
        case 'success': frequency = 659; break; // Ми
        case 'warning': frequency = 440; break; // Ля
        case 'error': frequency = 349; break;   // Фа
        case 'message': frequency = 523; break; // До
      }

      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      oscillator.frequency.value = frequency;
      oscillator.type = 'sine';

      gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);

      oscillator.start();
      oscillator.stop(audioContext.currentTime + 0.2);
    } catch (error) {
      console.error('Ошибка воспроизведения звука:', error);
    }
  }

  // Показ уведомления
  showNotification(title, options = {}) {
    if (!this.isEnabled || this.permission !== 'granted') {
      return null;
    }

    const defaultOptions = {
      icon: '/static/favicon.ico',
      badge: '/static/apple-touch-icon.png',
      dir: 'auto',
      lang: 'ru',
      requireInteraction: false,
      silent: false,
      ...options
    };

    try {
      // Воспроизводим звук если не отключен
      if (options.soundType && !defaultOptions.silent) {
        this.playSound(options.soundType);
      }

      const notification = new Notification(title, defaultOptions);

      notification.onclick = (event) => {
        event.preventDefault();
        window.focus();

        if (options.onClick) {
          options.onClick(event);
        }

        notification.close();
      };

      // Автоматически закрываем через 5 секунд
      if (!options.requireInteraction) {
        setTimeout(() => notification.close(), options.autoClose || 5000);
      }

      return notification;
    } catch (error) {
      console.error('Ошибка создания уведомления:', error);
      return null;
    }
  }

  // Обработка уведомлений из приложения
  handleNotification(notificationData) {
    const { message, target_url } = notificationData;

    let title = 'Coworking Admin';
    let soundType = 'default';

    // Определяем тип уведомления
    if (target_url?.includes('/tickets')) {
      title = '🎫 Новое обращение';
      soundType = 'warning';
    } else if (target_url?.includes('/bookings')) {
      title = '📅 Новое бронирование';
      soundType = 'success';
    } else if (target_url?.includes('/users')) {
      title = '👤 Новый пользователь';
      soundType = 'message';
    }

    return this.showNotification(title, {
      body: message,
      soundType: soundType,
      tag: `notification-${notificationData.id}`
    });
  }

  // Проверка статуса
  getStatus() {
    return {
      permission: this.permission,
      isEnabled: this.isEnabled,
      isSupported: 'Notification' in window
    };
  }

  // Управление состоянием
  disable() {
    this.isEnabled = false;
  }

  enable() {
    if (this.permission === 'granted') {
      this.isEnabled = true;
      return true;
    }
    return false;
  }

  // Инициализация (упрощенная версия)
  async init() {
    if (!('Notification' in window)) {
      console.warn('Браузер не поддерживает уведомления');
      return false;
    }

    // Проверяем сохраненную настройку
    const savedSetting = localStorage.getItem('notificationsEnabled');
    if (savedSetting === 'true' && this.permission === 'granted') {
      this.isEnabled = true;
    }

    return true;
  }
}

const notificationManager = new BrowserNotificationManager();

export default notificationManager;