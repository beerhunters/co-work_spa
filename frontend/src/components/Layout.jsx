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
    <Flex minH={styles.layout.minHeight} bg={styles.layout.bg}>
      <Sidebar
        section={section}
        setSection={setSection}
        handleLogout={handleLogout}
      />
      <Box flex={1}>
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
        {children}
      </Box>
    </Flex>
  );
};

export default Layout;