import React, { useState } from 'react';
import {
  Box,
  Flex,
  Heading,
  HStack,
  Text,
  Button,
  Icon,
  IconButton,
  Avatar,
  Divider,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  VStack,
  Switch,
  FormControl,
  FormLabel,
  useToast,
  useColorModeValue
} from '@chakra-ui/react';
import { FiBell, FiBellOff, FiVolume2, FiSettings } from 'react-icons/fi';
import { colors, sizes } from '../styles/styles';
import notificationManager from '../utils/notifications';

const Navbar = ({
  section,
  login,
  notifications,
  hasNewNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  notificationStatus,
  soundEnabled,
  onToggleNotificationSound
}) => {
  const [soundTestLoading, setSoundTestLoading] = useState(false);
  const toast = useToast();

  const sectionTitles = {
    dashboard: 'Дашборд',
    users: 'Пользователи',
    bookings: 'Бронирования',
    tariffs: 'Тарифы',
    promocodes: 'Промокоды',
    tickets: 'Заявки',
    notifications: 'Уведомления',
    newsletters: 'Рассылка'
  };

  const handleTestNotification = async () => {
    console.log('🧪 Тест уведомления из Navbar');
    setSoundTestLoading(true);

    try {
      // Сначала проверяем статус
      const status = notificationManager.getStatus();
      console.log('📊 Текущий статус:', status);

      if (status.permission === 'granted') {
        // Показываем тестовое уведомление
        notificationManager.showNotification('🧪 Тестовое уведомление', {
          body: 'Если вы видите это уведомление, значит все работает отлично! 🎉',
          soundType: 'success',
          autoClose: 6000
        });

        toast({
          title: "Тест уведомления отправлен",
          description: "Проверьте уведомления в углу экрана",
          status: "success",
          duration: 3000,
        });
      } else if (status.permission === 'denied') {
        toast({
          title: "Уведомления заблокированы",
          description: "Разрешите уведомления в настройках браузера (иконка замка в адресной строке)",
          status: "warning",
          duration: 5000,
        });
      } else {
        toast({
          title: "Уведомления не настроены",
          description: "Сначала разрешите уведомления",
          status: "info",
          duration: 3000,
        });
      }
    } catch (error) {
      console.error('❌ Ошибка тестового уведомления:', error);
      toast({
        title: "Ошибка тестового уведомления",
        description: error.message,
        status: "error",
        duration: 3000,
      });
    } finally {
      setSoundTestLoading(false);
    }
  };

  const handleTestSound = () => {
    console.log('🔊 Тест звука из Navbar');

    try {
      // Проверяем аудио контекст
      const status = notificationManager.getStatus();
      console.log('🔊 Статус аудио:', status);

      notificationManager.playSound('success');

      toast({
        title: "Звук воспроизведен",
        description: "Если не слышите звук, проверьте громкость и разрешения",
        status: "info",
        duration: 2000,
      });
    } catch (error) {
      console.error('❌ Ошибка воспроизведения звука:', error);
      toast({
        title: "Ошибка звука",
        description: error.message,
        status: "error",
        duration: 3000,
      });
    }
  };

  const unreadCount = notifications.filter(n => !n.is_read).length;

  return (
    <Box
      bg={colors.navbar.bg}
      px={sizes.navbar.padding.x}
      py={sizes.navbar.padding.y}
      borderBottom="2px"
      borderColor={colors.navbar.borderColor}
      boxShadow="sm"
    >
      <Flex justify="space-between" align="center">
        <Heading size="lg" color={colors.navbar.textColor}>
          {sectionTitles[section] || ''}
        </Heading>

        <HStack spacing={4}>
          {/* Меню уведомлений с красивым дизайном */}
          <Menu>
            <MenuButton
              as={IconButton}
              icon={
                <Box position="relative">
                  <FiBell size={20} />
                  {hasNewNotifications && (
                    <Box
                      position="absolute"
                      top="-2px"
                      right="-2px"
                      w="10px"
                      h="10px"
                      bg={colors.notification.indicatorBg}
                      borderRadius="full"
                      border="2px solid white"
                    />
                  )}
                </Box>
              }
              variant="ghost"
              borderRadius="lg"
              _hover={{ bg: 'gray.100' }}
            />
            <MenuList
              maxH="500px"
              overflowY="auto"
              boxShadow="xl"
              borderRadius="xl"
              p={2}
            >
              <Box p={3}>
                <Flex justify="space-between" align="center" mb={3}>
                  <Text fontWeight="bold" fontSize="lg">Уведомления</Text>
                  {unreadCount > 0 && (
                    <Button
                      size="xs"
                      colorScheme="purple"
                      onClick={markAllNotificationsRead}
                      borderRadius="full"
                    >
                      Прочитать все
                    </Button>
                  )}
                </Flex>
              </Box>

              <Divider />

              {/* Настройки браузерных уведомлений */}
              <Box p={3}>
                <VStack spacing={3} align="stretch">
                  <HStack justify="space-between">
                    <Text fontSize="sm" fontWeight="bold" color="gray.600">
                      Настройки уведомлений
                    </Text>
                    <Icon as={FiSettings} color="gray.400" boxSize={4} />
                  </HStack>

                  <FormControl display="flex" alignItems="center" size="sm">
                    <FormLabel htmlFor="sound-notifications" mb="0" fontSize="sm" flex="1">
                      <HStack spacing={2}>
                        <Icon as={soundEnabled ? FiVolume2 : FiBellOff} boxSize={4} />
                        <Text>Звуковые уведомления</Text>
                      </HStack>
                    </FormLabel>
                    <Switch
                      id="sound-notifications"
                      isChecked={soundEnabled && notificationStatus?.permission === 'granted'}
                      onChange={(e) => onToggleNotificationSound(e.target.checked)}
                      isDisabled={notificationStatus?.permission !== 'granted'}
                      size="sm"
                      colorScheme="purple"
                    />
                  </FormControl>

                  <HStack spacing={2} w="full">
                    {notificationStatus?.permission === 'granted' ? (
                      <>
                        <Button
                          size="xs"
                          variant="outline"
                          leftIcon={<FiVolume2 size={12} />}
                          onClick={handleTestSound}
                          flex="1"
                        >
                          Тест звука
                        </Button>
                        <Button
                          size="xs"
                          variant="outline"
                          leftIcon={<FiBell size={12} />}
                          onClick={handleTestNotification}
                          isLoading={soundTestLoading}
                          flex="1"
                        >
                          Тест уведомления
                        </Button>
                      </>
                    ) : (
                      <Text fontSize="xs" color="orange.500" textAlign="center" py={2}>
                        {notificationStatus?.permission === 'denied'
                          ? 'Уведомления заблокированы в браузере'
                          : 'Уведомления не настроены'
                        }
                      </Text>
                    )}
                  </HStack>
                </VStack>
              </Box>

              <Divider />

              {/* Список уведомлений с сохранением оригинального стиля */}
              {notifications.length === 0 ? (
                <Box p={8} textAlign="center">
                  <Icon as={FiBell} boxSize={10} color="gray.300" mb={2} />
                  <Text color="gray.500">Нет уведомлений</Text>
                </Box>
              ) : (
                notifications.slice(0, 5).map(n => (
                  <MenuItem
                    key={n.id}
                    onClick={() => markNotificationRead(n.id, n.target_url)}
                    bg={n.is_read ? colors.notification.readBg : colors.notification.unreadBg}
                    borderRadius="lg"
                    mb={1}
                    p={3}
                    _hover={{
                      bg: n.is_read ? colors.notification.readHover : colors.notification.unreadHover,
                    }}
                  >
                    <VStack align="stretch" spacing={1} w="full">
                      <Text fontSize="sm" fontWeight="medium" noOfLines={2}>
                        {n.message}
                      </Text>
                      <Text fontSize="xs" color="gray.500">
                        {new Date(n.created_at).toLocaleString('ru-RU')}
                      </Text>
                    </VStack>
                  </MenuItem>
                ))
              )}
            </MenuList>
          </Menu>

          <Avatar
            size="md"
            name={login || 'Admin'}
            bg="purple.500"
            color="white"
          />
        </HStack>
      </Flex>
    </Box>
  );
};

export default Navbar;