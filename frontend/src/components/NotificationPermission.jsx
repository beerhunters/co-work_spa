// components/NotificationPermission.jsx - Компонент для запроса разрешений

import React, { useState, useEffect } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
  Text,
  VStack,
  HStack,
  Icon,
  useColorModeValue,
  Switch,
  FormControl,
  FormLabel,
  Alert,
  AlertIcon,
  Box
} from '@chakra-ui/react';
import { FiBell, FiBellOff, FiVolume2 } from 'react-icons/fi';
import notificationManager from '../utils/notifications';

const NotificationPermissionModal = ({ isOpen, onClose, onPermissionGranted }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [permissionDenied, setPermissionDenied] = useState(false);

  const handleRequestPermission = async () => {
    setIsLoading(true);
    setPermissionDenied(false);

    try {
      const granted = await notificationManager.requestPermission();

      if (granted) {
        onPermissionGranted?.();
        onClose();
      } else {
        setPermissionDenied(true);
      }
    } catch (error) {
      console.error('Ошибка при запросе разрешения:', error);
      setPermissionDenied(true);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTestSound = () => {
    notificationManager.playSound('success');
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} isCentered size="md">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>
          <HStack>
            <Icon as={FiBell} color="purple.500" />
            <Text>Включить уведомления</Text>
          </HStack>
        </ModalHeader>

        <ModalBody>
          <VStack spacing={4} align="stretch">
            <Text>
              Разрешите уведомления, чтобы получать важные сообщения о новых
              бронированиях, обращениях и пользователях даже когда вкладка неактивна.
            </Text>

            <Box p={4} bg={useColorModeValue('gray.50', 'gray.700')} rounded="md">
              <VStack spacing={3}>
                <Text fontSize="sm" fontWeight="bold">Что вы получите:</Text>
                <VStack spacing={2} align="start" fontSize="sm">
                  <Text>🎫 Уведомления о новых обращениях</Text>
                  <Text>📅 Сообщения о бронированиях</Text>
                  <Text>👤 Информация о новых пользователях</Text>
                  <Text>🔊 Звуковые сигналы для важных событий</Text>
                </VStack>
              </VStack>
            </Box>

            {permissionDenied && (
              <Alert status="warning" rounded="md">
                <AlertIcon />
                <VStack align="start" spacing={1}>
                  <Text fontSize="sm" fontWeight="bold">
                    Разрешение отклонено
                  </Text>
                  <Text fontSize="xs">
                    Вы можете включить уведомления в настройках браузера:
                    нажмите на иконку замка в адресной строке.
                  </Text>
                </VStack>
              </Alert>
            )}

            <HStack justify="center">
              <Button
                size="sm"
                variant="outline"
                leftIcon={<FiVolume2 />}
                onClick={handleTestSound}
              >
                Тест звука
              </Button>
            </HStack>
          </VStack>
        </ModalBody>

        <ModalFooter>
          <HStack>
            <Button variant="ghost" onClick={onClose}>
              Не сейчас
            </Button>
            <Button
              colorScheme="purple"
              isLoading={isLoading}
              loadingText="Запрос..."
              onClick={handleRequestPermission}
            >
              Разрешить уведомления
            </Button>
          </HStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

// Компонент настроек уведомлений в навбаре
export const NotificationSettings = ({ notifications, markNotificationRead, markAllNotificationsRead }) => {
  const [isPermissionModalOpen, setPermissionModalOpen] = useState(false);
  const [notificationStatus, setNotificationStatus] = useState(null);
  const [soundEnabled, setSoundEnabled] = useState(true);

  useEffect(() => {
    // Инициализируем менеджер уведомлений
    const initNotifications = async () => {
      await notificationManager.init();
      const status = notificationManager.getStatus();
      setNotificationStatus(status);

      // Проверяем, нужно ли показать модальное окно
      const hasAsked = localStorage.getItem('notificationPermissionAsked');
      const isEnabled = localStorage.getItem('notificationsEnabled');

      if (!hasAsked && status.isSupported && status.permission === 'default') {
        setTimeout(() => {
          setPermissionModalOpen(true);
          localStorage.setItem('notificationPermissionAsked', 'true');
        }, 3000); // Показываем через 3 секунды после загрузки
      } else if (isEnabled === 'true' && status.permission === 'granted') {
        notificationManager.enable();
      }
    };

    initNotifications();

    // Загружаем настройку звука
    const savedSoundSetting = localStorage.getItem('notificationSoundEnabled');
    setSoundEnabled(savedSoundSetting !== 'false');
  }, []);

  // Обрабатываем новые уведомления
  useEffect(() => {
    if (!notificationStatus?.isEnabled || !notifications.length) return;

    // Получаем последнее непрочитанное уведомление
    const latestUnread = notifications.find(n => !n.is_read);

    if (latestUnread) {
      // Проверяем, не показывали ли мы уже это уведомление
      const shownNotifications = JSON.parse(localStorage.getItem('shownNotifications') || '[]');

      if (!shownNotifications.includes(latestUnread.id)) {
        // Показываем браузерное уведомление только если включены звуки
        if (soundEnabled) {
          notificationManager.handleNotification(latestUnread);
        }

        // Сохраняем ID показанного уведомления
        shownNotifications.push(latestUnread.id);
        localStorage.setItem('shownNotifications', JSON.stringify(shownNotifications.slice(-50))); // Храним последние 50
      }
    }
  }, [notifications, notificationStatus, soundEnabled]);

  const handlePermissionGranted = () => {
    const status = notificationManager.getStatus();
    setNotificationStatus(status);
  };

  const handleToggleSound = (enabled) => {
    setSoundEnabled(enabled);
    localStorage.setItem('notificationSoundEnabled', enabled.toString());

    if (enabled) {
      notificationManager.enable();
    } else {
      notificationManager.disable();
    }
  };

  const handleTestNotification = () => {
    if (notificationStatus?.isEnabled) {
      notificationManager.showNotification('Тестовое уведомление', {
        body: 'Это тестовое уведомление для проверки работы системы',
        soundType: 'success',
        autoClose: 3000
      });
    }
  };

  if (!notificationStatus?.isSupported) {
    return null; // Браузер не поддерживает уведомления
  }

  return (
    <>
      {/* Дополнительные настройки уведомлений (можно добавить в меню) */}
      <VStack spacing={2} p={2}>
        <FormControl display="flex" alignItems="center" size="sm">
          <FormLabel htmlFor="sound-notifications" mb="0" fontSize="sm">
            <HStack>
              <Icon as={soundEnabled ? FiVolume2 : FiBellOff} />
              <Text>Звуковые уведомления</Text>
            </HStack>
          </FormLabel>
          <Switch
            id="sound-notifications"
            isChecked={soundEnabled && notificationStatus?.permission === 'granted'}
            onChange={(e) => handleToggleSound(e.target.checked)}
            isDisabled={notificationStatus?.permission !== 'granted'}
            size="sm"
          />
        </FormControl>

        {notificationStatus?.permission === 'granted' && (
          <Button size="xs" variant="outline" onClick={handleTestNotification}>
            Тест уведомления
          </Button>
        )}

        {notificationStatus?.permission === 'denied' && (
          <Text fontSize="xs" color="orange.500" textAlign="center">
            Уведомления заблокированы. Разрешите их в настройках браузера.
          </Text>
        )}
      </VStack>

      {/* Модальное окно запроса разрешений */}
      <NotificationPermissionModal
        isOpen={isPermissionModalOpen}
        onClose={() => setPermissionModalOpen(false)}
        onPermissionGranted={handlePermissionGranted}
      />
    </>
  );
};

export default NotificationPermissionModal;