console.log('🔧 Service Worker запущен');

const CACHE_NAME = 'coworking-admin-v1';

// Установка Service Worker
self.addEventListener('install', (event) => {
  console.log('🔧 Service Worker: Установка');
  self.skipWaiting(); // Активируем сразу
});

// Активация Service Worker
self.addEventListener('activate', (event) => {
  console.log('🔧 Service Worker: Активация');
  event.waitUntil(self.clients.claim()); // Берем контроль над всеми клиентами
});

// Обработка кликов по уведомлениям
self.addEventListener('notificationclick', (event) => {
  console.log('👆 Service Worker: Клик по уведомлению');

  event.notification.close();

  // Открываем или фокусируем окно приложения
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then((clientList) => {
      // Ищем уже открытое окно
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          console.log('🎯 Фокусируем существующее окно');
          return client.focus();
        }
      }

      // Открываем новое окно, если не найдено
      if (clients.openWindow) {
        console.log('🆕 Открываем новое окно');
        return clients.openWindow('/');
      }
    })
  );
});

// Обработка закрытия уведомлений
self.addEventListener('notificationclose', (event) => {
  console.log('📪 Service Worker: Уведомление закрыто');
});

// Обработка сообщений от основного потока
self.addEventListener('message', (event) => {
  console.log('💬 Service Worker: Получено сообщение', event.data);

  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

console.log('✅ Service Worker готов к работе');