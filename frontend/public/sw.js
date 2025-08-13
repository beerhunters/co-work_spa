// public/sw.js - Service Worker для фоновых уведомлений

const CACHE_NAME = 'coworking-admin-v1';
const urlsToCache = [
  '/',
  '/static/favicon.ico',
  '/static/apple-touch-icon.png'
];

// Установка Service Worker
self.addEventListener('install', (event) => {
  console.log('Service Worker: Установка');

  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Service Worker: Кэширование файлов');
        return cache.addAll(urlsToCache);
      })
      .then(() => self.skipWaiting()) // Активируем сразу
  );
});

// Активация Service Worker
self.addEventListener('activate', (event) => {
  console.log('Service Worker: Активация');

  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('Service Worker: Удаляем старый кэш', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim()) // Берем контроль над всеми клиентами
  );
});

// Обработка fetch запросов (базовое кэширование)
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Возвращаем кэшированную версию или делаем запрос
        return response || fetch(event.request);
      }
    )
  );
});

// Обработка push уведомлений (для будущего расширения)
self.addEventListener('push', (event) => {
  console.log('Service Worker: Получено push уведомление');

  const options = {
    body: 'У вас новое уведомление!',
    icon: '/static/favicon.ico',
    badge: '/static/apple-touch-icon.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'explore',
        title: 'Открыть',
        icon: '/static/favicon.ico'
      },
      {
        action: 'close',
        title: 'Закрыть',
        icon: '/static/favicon.ico'
      }
    ]
  };

  event.waitUntil(
    self.registration.showNotification('Coworking Admin', options)
  );
});

// Обработка кликов по уведомлениям
self.addEventListener('notificationclick', (event) => {
  console.log('Service Worker: Клик по уведомлению');

  event.notification.close();

  if (event.action === 'close') {
    return;
  }

  // Открываем или фокусируем окно приложения
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then((clientList) => {
      // Ищем уже открытое окно
      for (const client of clientList) {
        if (client.url === self.location.origin && 'focus' in client) {
          return client.focus();
        }
      }

      // Открываем новое окно, если не найдено
      if (clients.openWindow) {
        return clients.openWindow('/');
      }
    })
  );
});

// Обработка закрытия уведомлений
self.addEventListener('notificationclose', (event) => {
  console.log('Service Worker: Уведомление закрыто');
});

// Синхронизация в фоне (для offline поддержки в будущем)
self.addEventListener('sync', (event) => {
  console.log('Service Worker: Фоновая синхронизация');

  if (event.tag === 'background-sync') {
    event.waitUntil(
      // Здесь можно добавить логику для синхронизации данных
      Promise.resolve()
    );
  }
});

// Обработка сообщений от основного потока
self.addEventListener('message', (event) => {
  console.log('Service Worker: Получено сообщение', event.data);

  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  // Отправляем ответ обратно
  event.ports[0].postMessage({
    type: 'SW_RESPONSE',
    message: 'Service Worker готов'
  });
});