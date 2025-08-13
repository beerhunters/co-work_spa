class BrowserNotificationManager {
  constructor() {
    this.permission = Notification.permission;
    this.isEnabled = false;
    this.audioContext = null;
    this.isInitialized = false;
  }

  // Инициализация менеджера уведомлений
  async init() {
    console.log('🔔 Инициализация менеджера уведомлений...');

    if (!('Notification' in window)) {
      console.warn('❌ Браузер не поддерживает уведомления');
      return false;
    }

    // Инициализируем аудио контекст после пользовательского взаимодействия
    this.initAudioContext();

    // Проверяем сохраненную настройку
    const savedSetting = localStorage.getItem('notificationsEnabled');
    if (savedSetting === 'true' && this.permission === 'granted') {
      this.isEnabled = true;
      console.log('✅ Уведомления включены из сохраненных настроек');
    }

    this.isInitialized = true;
    console.log('✅ Менеджер уведомлений инициализирован');
    return true;
  }

  // Инициализация аудио контекста
  initAudioContext() {
    try {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      console.log('🔊 Аудио контекст создан');
    } catch (error) {
      console.warn('⚠️ Не удалось создать аудио контекст:', error);
    }
  }

  // Запрос разрешения на уведомления
  async requestPermission() {
    console.log('🔔 Запрос разрешения на уведомления...');

    if (this.permission === 'granted') {
      this.isEnabled = true;
      localStorage.setItem('notificationsEnabled', 'true');
      console.log('✅ Разрешение уже предоставлено');
      return true;
    }

    if (this.permission === 'denied') {
      console.log('❌ Разрешение отклонено ранее');
      return false;
    }

    try {
      const permission = await Notification.requestPermission();
      this.permission = permission;
      this.isEnabled = permission === 'granted';

      if (this.isEnabled) {
        localStorage.setItem('notificationsEnabled', 'true');
        console.log('✅ Разрешение получено!');
      } else {
        console.log('❌ Разрешение отклонено');
      }

      return this.isEnabled;
    } catch (error) {
      console.error('❌ Ошибка при запросе разрешения:', error);
      return false;
    }
  }

  // Воспроизведение громкого звука
  playSound(type = 'default') {
    console.log(`🔊 Воспроизведение звука: ${type}`);

    // Если аудио контекст в состоянии suspended, пытаемся возобновить
    if (this.audioContext && this.audioContext.state === 'suspended') {
      this.audioContext.resume().then(() => {
        this.playActualSound(type);
      });
    } else {
      this.playActualSound(type);
    }
  }

  // Фактическое воспроизведение звука
  playActualSound(type) {
    try {
      if (!this.audioContext) {
        this.initAudioContext();
      }

      if (!this.audioContext) {
        console.warn('⚠️ Аудио контекст недоступен');
        return;
      }

      const oscillator = this.audioContext.createOscillator();
      const gainNode = this.audioContext.createGain();
      const compressor = this.audioContext.createDynamicsCompressor();

      // Настройки для разных типов звуков
      let frequencies = [800];
      let duration = 0.3;

      switch (type) {
        case 'success':
          frequencies = [523, 659, 784]; // До, Ми, Соль (мажорный аккорд)
          duration = 0.4;
          break;
        case 'warning':
          frequencies = [440, 554]; // Ля, До# (напряженный интервал)
          duration = 0.5;
          break;
        case 'error':
          frequencies = [349, 294]; // Фа, Ре (нисходящий)
          duration = 0.6;
          break;
        case 'message':
          frequencies = [659, 523]; // Ми, До (приятный спуск)
          duration = 0.3;
          break;
      }

      // Подключаем узлы
      oscillator.connect(gainNode);
      gainNode.connect(compressor);
      compressor.connect(this.audioContext.destination);

      // Настройки осциллятора
      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(frequencies[0], this.audioContext.currentTime);

      // Если несколько частот, создаем мелодию
      if (frequencies.length > 1) {
        const noteDuration = duration / frequencies.length;
        frequencies.forEach((freq, index) => {
          const time = this.audioContext.currentTime + (index * noteDuration);
          oscillator.frequency.setValueAtTime(freq, time);
        });
      }

      // ГРОМКОСТЬ! Делаем звук заметным но не оглушающим
      gainNode.gain.setValueAtTime(0, this.audioContext.currentTime);
      gainNode.gain.linearRampToValueAtTime(0.4, this.audioContext.currentTime + 0.1); // Быстрый подъем
      gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + duration);

      // Настройки компрессора для более насыщенного звука
      compressor.threshold.setValueAtTime(-24, this.audioContext.currentTime);
      compressor.knee.setValueAtTime(30, this.audioContext.currentTime);
      compressor.ratio.setValueAtTime(12, this.audioContext.currentTime);
      compressor.attack.setValueAtTime(0.003, this.audioContext.currentTime);
      compressor.release.setValueAtTime(0.25, this.audioContext.currentTime);

      oscillator.start();
      oscillator.stop(this.audioContext.currentTime + duration);

      console.log(`✅ Звук ${type} воспроизведен`);
    } catch (error) {
      console.error('❌ Ошибка воспроизведения звука:', error);
    }
  }

  // Показ браузерного уведомления
  showNotification(title, options = {}) {
    console.log(`🔔 Показ уведомления: ${title}`);

    if (!this.isEnabled || this.permission !== 'granted') {
      console.warn('⚠️ Уведомления отключены или нет разрешения');
      return null;
    }

    const defaultOptions = {
      icon: '/static/favicon.ico',
      badge: '/static/apple-touch-icon.png',
      dir: 'auto',
      lang: 'ru',
      requireInteraction: false,
      silent: false, // Разрешаем системный звук
      vibrate: [200, 100, 200], // Вибрация на мобильных
      timestamp: Date.now(),
      ...options
    };

    try {
      // Сначала воспроизводим наш звук
      if (options.soundType && !defaultOptions.silent) {
        this.playSound(options.soundType);
      }

      // Создаем уведомление
      const notification = new Notification(title, defaultOptions);

      // Обработчики событий
      notification.onclick = (event) => {
        console.log('👆 Клик по уведомлению');
        event.preventDefault();

        // Фокусируем окно
        if (window.focus) {
          window.focus();
        }

        // Вызываем коллбек если есть
        if (options.onClick) {
          options.onClick(event);
        }

        notification.close();
      };

      notification.onshow = () => {
        console.log('✅ Уведомление показано');
      };

      notification.onerror = (error) => {
        console.error('❌ Ошибка уведомления:', error);
      };

      notification.onclose = () => {
        console.log('📪 Уведомление закрыто');
      };

      // Автоматическое закрытие
      if (!options.requireInteraction) {
        setTimeout(() => {
          notification.close();
        }, options.autoClose || 8000); // Увеличиваем время до 8 секунд
      }

      return notification;
    } catch (error) {
      console.error('❌ Ошибка создания уведомления:', error);
      return null;
    }
  }

  // Обработка уведомлений из приложения
  handleNotification(notificationData) {
    console.log('📢 Обработка уведомления:', notificationData);

    const { message, target_url, id } = notificationData;

    let title = 'Coworking Admin';
    let soundType = 'default';
    let icon = '/static/favicon.ico';

    // Определяем тип уведомления по URL
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
      icon: icon,
      tag: `notification-${id}`, // Предотвращаем дубликаты
      renotify: true, // Показываем даже если такой tag уже есть
      data: notificationData,
      onClick: () => {
        console.log('🔗 Переход по уведомлению:', target_url);
        // Здесь можно добавить логику навигации
      }
    });
  }

  // Получение статуса
  getStatus() {
    const status = {
      permission: this.permission,
      isEnabled: this.isEnabled,
      isSupported: 'Notification' in window,
      audioContext: !!this.audioContext,
      isInitialized: this.isInitialized
    };

    console.log('ℹ️ Статус уведомлений:', status);
    return status;
  }

  // Включение уведомлений
  enable() {
    if (this.permission === 'granted') {
      this.isEnabled = true;
      localStorage.setItem('notificationsEnabled', 'true');
      console.log('✅ Уведомления включены');
      return true;
    }
    console.warn('⚠️ Нельзя включить - нет разрешения');
    return false;
  }

  // Отключение уведомлений
  disable() {
    this.isEnabled = false;
    localStorage.setItem('notificationsEnabled', 'false');
    console.log('❌ Уведомления отключены');
  }
}

// Создаем глобальный экземпляр
const notificationManager = new BrowserNotificationManager();

// Инициализируем при загрузке
document.addEventListener('DOMContentLoaded', () => {
  notificationManager.init();
});

export default notificationManager;