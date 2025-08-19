import React from 'react';
import { Box, VStack, Flex, Heading, Button, Icon, Spacer } from '@chakra-ui/react';
import { FiHome, FiTrendingUp, FiUser, FiCalendar, FiTag, FiPercent, FiHelpCircle, FiBell, FiSend, FiLogOut, FiShield } from 'react-icons/fi';
import { colors, sizes, styles } from '../styles/styles';

const Sidebar = ({ section, setSection, handleLogout, currentAdmin }) => {
  // Сначала объявляем menuItems
  const menuItems = [
    { icon: FiTrendingUp, label: 'Дашборд', section: 'dashboard', color: 'purple' },
    { icon: FiUser, label: 'Пользователи', section: 'users', color: 'blue' },
    { icon: FiCalendar, label: 'Бронирования', section: 'bookings', color: 'green' },
    { icon: FiTag, label: 'Тарифы', section: 'tariffs', color: 'cyan' },
    { icon: FiPercent, label: 'Промокоды', section: 'promocodes', color: 'orange' },
    { icon: FiHelpCircle, label: 'Заявки', section: 'tickets', color: 'yellow' },
    { icon: FiBell, label: 'Уведомления', section: 'notifications', color: 'pink' },
    { icon: FiSend, label: 'Рассылка', section: 'newsletters', color: 'teal' },
    { icon: FiShield, label: 'Администраторы', section: 'admins', color: 'purple', requiresSuperAdmin: true },
  ];

  // Теперь фильтруем пункты меню в зависимости от роли
  const filteredMenuItems = menuItems.filter(item => {
    if (item.requiresSuperAdmin) {
      return currentAdmin?.role === 'super_admin';
    }
    return true;
  });

  return (
    <Box
      w={sizes.sidebar.width}
      bg={colors.sidebar.bg}
      color={colors.sidebar.text}
      h="100vh"
      display="flex"
      flexDirection="column"
      overflowY="auto"
      overflowX="hidden"
      css={{
        '&::-webkit-scrollbar': {
          width: '6px',
        },
        '&::-webkit-scrollbar-track': {
          background: 'rgba(0, 0, 0, 0.1)',
        },
        '&::-webkit-scrollbar-thumb': {
          background: 'rgba(0, 0, 0, 0.3)',
          borderRadius: '3px',
        },
        '&::-webkit-scrollbar-thumb:hover': {
          background: 'rgba(0, 0, 0, 0.5)',
        },
      }}
    >
      <Box p={sizes.sidebar.padding}>
        <VStack align="stretch" spacing={1}>
          <Flex align="center" mb={6}>
            <Icon as={FiHome} boxSize={6} color="purple.400" mr={3} />
            <Heading size="md" fontWeight="bold">
              Админ панель
            </Heading>
          </Flex>

          {filteredMenuItems.map(({ icon: ItemIcon, label, section: sec, color }) => (
            <Button
              key={sec}
              leftIcon={<ItemIcon />}
              variant={section === sec ? 'solid' : 'ghost'}
              bg={section === sec ? `${color}.600` : 'transparent'}
              color={section === sec ? colors.sidebar.text : colors.sidebar.textMuted}
              justifyContent="flex-start"
              onClick={() => setSection(sec)}
              _hover={{
                bg: section === sec ? `${color}.700` : colors.sidebar.hoverBg,
                color: colors.sidebar.text,
              }}
              borderRadius={styles.button.borderRadius}
              px={sizes.sidebar.buttonPadding.x}
              py={sizes.sidebar.buttonPadding.y}
              fontSize={styles.button.fontSize}
              transition={styles.button.transition}
            >
              {label}
            </Button>
          ))}
        </VStack>
      </Box>

      <Spacer />

      <Box p={sizes.sidebar.padding} borderTop="1px" borderColor={colors.sidebar.borderColor}>
        <Button
          leftIcon={<FiLogOut />}
          variant="ghost"
          color="red.400"
          justifyContent="flex-start"
          onClick={handleLogout}
          _hover={{
            bg: 'red.900',
            color: 'red.300',
          }}
          borderRadius={styles.button.borderRadius}
          px={sizes.sidebar.buttonPadding.x}
          py={sizes.sidebar.buttonPadding.y}
          w="full"
          fontSize={styles.button.fontSize}
          transition={styles.button.transition}
        >
          Выйти из системы
        </Button>
      </Box>
    </Box>
  );
};

export default Sidebar;