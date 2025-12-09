import React from 'react';
import { Box, Flex, Button, Icon } from '@chakra-ui/react';
import { FiChevronRight, FiChevronLeft } from 'react-icons/fi';
import Sidebar from './Sidebar';
import Navbar from './Navbar';
import { Breadcrumbs } from './Breadcrumbs';
import { styles, colors, sizes } from '../styles/styles';

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
  onToggleNotificationSound,
  isSidebarCollapsed,
  toggleSidebar,
  isSidebarHovered,
  setIsSidebarHovered
}) => {
  return (
    <Flex minH={styles.layout.minHeight} bg={styles.layout.bg} position="relative">
      {/* Фиксированный сайдбар */}
      <Box
        position="fixed"
        top="0"
        left="0"
        h="100vh"
        zIndex="100"
      >
        <Sidebar
          section={section}
          setSection={setSection}
          handleLogout={handleLogout}
          currentAdmin={currentAdmin}
          isCollapsed={isSidebarCollapsed}
          isHovered={isSidebarHovered}
          setIsHovered={setIsSidebarHovered}
        />

        {/* Кнопка Toggle */}
        <Box
          position="absolute"
          left={
            isSidebarCollapsed && isSidebarHovered
              ? `calc(${sizes.sidebar.width} - 16px)`
              : isSidebarCollapsed
              ? `calc(${sizes.sidebar.collapsedWidth} - 16px)`
              : `calc(${sizes.sidebar.width} - 16px)`
          }
          top="40px"
          zIndex="200"
          transition="left 0.3s ease"
        >
          <Button
            onClick={toggleSidebar}
            size="sm"
            w={sizes.sidebar.toggleButtonSize}
            h={sizes.sidebar.toggleButtonSize}
            minW="auto"
            borderRadius="full"
            bg={colors.sidebar.bg}
            color={colors.sidebar.text}
            border="2px solid"
            borderColor={colors.sidebar.borderColor}
            _hover={{
              bg: colors.sidebar.hoverBg,
              borderColor: 'purple.500',
            }}
            boxShadow="lg"
            p={0}
          >
            <Icon
              as={isSidebarCollapsed && !isSidebarHovered ? FiChevronRight : FiChevronLeft}
              boxSize={4}
              transition="all 0.3s ease"
            />
          </Button>
        </Box>
      </Box>

      {/* Основной контент с отступом для сайдбара */}
      <Box
        flex={1}
        ml={isSidebarCollapsed ? sizes.sidebar.collapsedWidth : sizes.sidebar.width}
        position="relative"
        transition="margin-left 0.3s ease"
      >
        {/* Фиксированный Navbar */}
        <Box
          position="sticky"
          top="0"
          zIndex="5"
          bg={colors.background.card}
        >
          <Navbar
            section={section}
            setSection={setSection}
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

        {/* Breadcrumbs */}
        <Breadcrumbs section={section} setSection={setSection} />

        {/* Прокручиваемый контент */}
        <Box>
          {children}
        </Box>
      </Box>
    </Flex>
  );
};

export default Layout;