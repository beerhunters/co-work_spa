// components/Navbar.jsx
import React from 'react';
import { Box, Flex, Heading, HStack, Text, Button, Icon, IconButton, Avatar, Divider, Menu, MenuButton, MenuList, MenuItem, VStack } from '@chakra-ui/react';
import { FiBell } from 'react-icons/fi';
import { colors, sizes } from '../styles/styles';

const Navbar = ({
  section,
  login,
  notifications,
  hasNewNotifications,
  markNotificationRead,
  markAllNotificationsRead
}) => {
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
                  {notifications.filter(n => !n.is_read).length > 0 && (
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