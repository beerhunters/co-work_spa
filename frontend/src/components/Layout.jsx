import React from 'react';
import { Box, Flex } from '@chakra-ui/react';
import Sidebar from './Sidebar';
import Navbar from './Navbar';
import { styles } from '../styles/styles';

const Layout = ({
  children,
  section,
  setSection,
  handleLogout,
  currentAdmin,
  login,
  notifications,
  hasNewNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  notificationStatus,
  soundEnabled,
  onToggleNotificationSound
}) => {
  return (
    <Flex minH="100vh" bg={styles.layout.bg} position="relative">
      {/* Фиксированный сайдбар */}
      <Box
        position="fixed"
        top="0"
        left="0"
        h="100vh"
        zIndex="10"
      >
        <Sidebar
          section={section}
          setSection={setSection}
          handleLogout={handleLogout}
          currentAdmin={currentAdmin}
        />
      </Box>

      {/* Основной контент с отступом для сайдбара */}
      <Box
        flex={1}
        ml="240px" // Отступ равный ширине сайдбара (из sizes.sidebar.width)
        position="relative"
      >
        {/* Фиксированный Navbar */}
        <Box
          position="sticky"
          top="0"
          zIndex="5"
          bg="white"
        >
          <Navbar
            section={section}
            login={login}
            notifications={notifications}
            hasNewNotifications={hasNewNotifications}
            markNotificationRead={markNotificationRead}
            markAllNotificationsRead={markAllNotificationsRead}
            notificationStatus={notificationStatus}
            soundEnabled={soundEnabled}
            onToggleNotificationSound={onToggleNotificationSound}
          />
        </Box>

        {/* Прокручиваемый контент */}
        <Box>
          {children}
        </Box>
      </Box>
    </Flex>
  );
};

export default Layout;