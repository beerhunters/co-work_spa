import React, { useState } from 'react';
import {
  Box,
  VStack,
  Flex,
  Heading,
  Button,
  Icon,
  Spacer,
  Collapse,
  Text
} from '@chakra-ui/react';
import { FiHome, FiTrendingUp, FiUser, FiCalendar, FiTag, FiPercent, FiHelpCircle, FiBell, FiSend, FiMail, FiLogOut, FiShield, FiDatabase, FiActivity, FiLayers, FiCpu, FiKey, FiSettings, FiChevronRight, FiFileText, FiBriefcase } from 'react-icons/fi';
import { colors, sizes, styles, typography, spacing, animations } from '../styles/styles';

const Sidebar = ({ section, setSection, handleLogout, currentAdmin, isCollapsed, isHovered, setIsHovered }) => {
  const [isAdminAccordionOpen, setIsAdminAccordionOpen] = useState(false);

  // Основные пункты меню
  const mainMenuItems = [
    { icon: FiTrendingUp, label: 'Дашборд', section: 'dashboard', color: 'purple' },
    { icon: FiUser, label: 'Пользователи', section: 'users', color: 'blue' },
    { icon: FiCalendar, label: 'Бронирования', section: 'bookings', color: 'green' },
    { icon: FiTag, label: 'Тарифы', section: 'tariffs', color: 'cyan' },
    { icon: FiBriefcase, label: 'Офисы', section: 'offices', color: 'orange' },
    { icon: FiPercent, label: 'Промокоды', section: 'promocodes', color: 'orange' },
    { icon: FiHelpCircle, label: 'Заявки', section: 'tickets', color: 'yellow' },
    { icon: FiBell, label: 'Уведомления', section: 'notifications', color: 'pink' },
    { icon: FiSend, label: 'Рассылка (Telegram)', section: 'newsletters', color: 'teal' },
    // { icon: FiMail, label: 'Email Рассылки', section: 'emails', color: 'blue' },
    { icon: FiBell, label: 'Подписки на офисы', section: 'office-subscriptions', color: 'orange' },
  ];

  // Административные функции для super_admin
  const adminMenuItems = [
    { icon: FiActivity, label: 'Мониторинг системы', section: 'system-monitoring', color: 'purple' },
    { icon: FiCpu, label: 'Запланированные задачи', section: 'scheduled-tasks', color: 'cyan' },
    { icon: FiFileText, label: 'Логирование', section: 'logging', color: 'gray' },
    { icon: FiShield, label: 'IP Баны', section: 'ip-bans', color: 'red' },
    { icon: FiShield, label: 'Администраторы', section: 'admins', color: 'purple' },
    { icon: FiDatabase, label: 'Бэкапы', section: 'backups', color: 'red' },
  ];

  // Проверяем, выбран ли какой-либо административный раздел
  const isAdminSectionActive = adminMenuItems.some(item => item.section === section);

  // Проверяем, выбран ли какой-либо основной раздел
  const isMainSectionActive = mainMenuItems.some(item => item.section === section);

  // Управляем состоянием аккордеона автоматически
  React.useEffect(() => {
    if (isAdminSectionActive) {
      setIsAdminAccordionOpen(true);
    } else if (isMainSectionActive) {
      setIsAdminAccordionOpen(false);
    }
  }, [isAdminSectionActive, isMainSectionActive]);

  // Функция рендеринга содержимого sidebar (для переиспользования в overlay)
  const renderSidebarContent = (isFull = true) => (
    <Box p={spacing.md}>
      <VStack align="stretch" spacing={1}>
        {/* Заголовок */}
        {isFull ? (
          <Flex align="center" mb={6}>
            <Icon as={FiHome} boxSize={6} color="purple.400" mr={3} />
            <Heading
              size="md"
              fontWeight={typography.fontWeights.bold}
              color={colors.sidebar.text}
              fontSize={typography.fontSizes.lg}
            >
              Админ панель
            </Heading>
          </Flex>
        ) : (
          <Flex align="center" justify="center" mb={6}>
            <Icon as={FiHome} boxSize={6} color="purple.400" />
          </Flex>
        )}

        {/* Основные пункты меню */}
        {mainMenuItems.map(({ icon: ItemIcon, label, section: sec, color }) => (
          <Button
            key={sec}
            leftIcon={<ItemIcon />}
            iconSpacing={isFull ? 3 : 0}
            variant={section === sec ? 'solid' : 'ghost'}
            bg={section === sec ? `${color}.600` : 'transparent'}
            color={section === sec ? colors.sidebar.text : colors.sidebar.textMuted}
            justifyContent={isFull ? 'flex-start' : 'center'}
            onClick={() => setSection(sec)}
            borderRadius={sizes.button.borderRadius}
            px={isFull ? sizes.sidebar.buttonPadding.x : 0}
            py={sizes.sidebar.buttonPadding.y}
            fontSize={typography.fontSizes.md}
            fontWeight={typography.fontWeights.medium}
            h={sizes.button.height.md}
            transition={animations.transitions.normal}
            _hover={{
              bg: section === sec ? `${color}.700` : colors.sidebar.hoverBg,
              color: colors.sidebar.text,
              transform: 'translateX(2px)'
            }}
          >
            {isFull && label}
          </Button>
        ))}

        {/* Административный аккордеон для super_admin */}
        {currentAdmin?.role === 'super_admin' && (
          <Box mt={4}>
            {/* Заголовок аккордеона */}
            <Button
              variant="ghost"
              justifyContent={isFull ? 'flex-start' : 'center'}
              onClick={() => setIsAdminAccordionOpen(!isAdminAccordionOpen)}
              _hover={{
                bg: colors.sidebar.hoverBg,
                color: colors.sidebar.text,
              }}
              borderRadius={sizes.button.borderRadius}
              px={isFull ? sizes.sidebar.buttonPadding.x : 0}
              py={sizes.sidebar.buttonPadding.y}
              fontSize={typography.fontSizes.md}
              fontWeight={typography.fontWeights.medium}
              h={sizes.button.height.md}
              transition={animations.transitions.normal}
              w="full"
              leftIcon={<Icon as={FiSettings} color={colors.sidebar.accordionText} />}
              iconSpacing={isFull ? 3 : 0}
              rightIcon={
                isFull ? (
                  <Icon
                    as={FiChevronRight}
                    color={colors.sidebar.accordionText}
                    transition={animations.transitions.normal}
                    transform={isAdminAccordionOpen ? 'rotate(90deg)' : 'rotate(0deg)'}
                  />
                ) : null
              }
            >
              {isFull && (
                <Text color={colors.sidebar.accordionText} fontSize={typography.fontSizes.md} fontWeight={typography.fontWeights.medium}>
                  Администрирование
                </Text>
              )}
            </Button>

            {/* Содержимое аккордеона */}
            <Collapse in={isAdminAccordionOpen && isFull} animateOpacity>
              <VStack align="stretch" spacing={1} mt={2} pl={isFull ? 4 : 0}>
                {adminMenuItems.map(({ icon: ItemIcon, label, section: sec, color }) => (
                  <Button
                    key={sec}
                    leftIcon={<ItemIcon />}
                    iconSpacing={isFull ? 3 : 0}
                    variant={section === sec ? 'solid' : 'ghost'}
                    bg={section === sec ? `${color}.600` : 'transparent'}
                    color={section === sec ? colors.sidebar.text : colors.sidebar.textMuted}
                    justifyContent={isFull ? 'flex-start' : 'center'}
                    onClick={() => setSection(sec)}
                    _hover={{
                      bg: section === sec ? `${color}.700` : colors.sidebar.hoverBg,
                      color: colors.sidebar.text,
                      transform: 'translateX(2px)'
                    }}
                    borderRadius={sizes.button.borderRadius}
                    px={isFull ? sizes.sidebar.buttonPadding.x : 0}
                    py={sizes.sidebar.buttonPadding.y}
                    fontSize={typography.fontSizes.sm}
                    fontWeight={typography.fontWeights.medium}
                    h={sizes.button.height.sm}
                    transition={animations.transitions.normal}
                    size="sm"
                  >
                    {isFull && label}
                  </Button>
                ))}
              </VStack>
            </Collapse>
          </Box>
        )}

        <Spacer />

        {/* Кнопка выхода */}
        <Box mt={4} pt={4} borderTop="1px" borderColor={colors.sidebar.borderColor}>
          <Button
            leftIcon={<FiLogOut />}
            iconSpacing={isFull ? 3 : 0}
            variant="ghost"
            color="red.400"
            justifyContent={isFull ? 'flex-start' : 'center'}
            onClick={handleLogout}
            _hover={{
              bg: 'red.900',
              color: 'red.300',
              transform: 'translateX(2px)'
            }}
            borderRadius={sizes.button.borderRadius}
            px={isFull ? sizes.sidebar.buttonPadding.x : 0}
            py={sizes.sidebar.buttonPadding.y}
            w="full"
            fontSize={typography.fontSizes.md}
            fontWeight={typography.fontWeights.medium}
            h={sizes.button.height.md}
            transition={animations.transitions.normal}
          >
            {isFull && 'Выйти из системы'}
          </Button>
        </Box>
      </VStack>
    </Box>
  );

  return (
    <>
      {/* Основной sidebar */}
      <Box
        w={isCollapsed ? sizes.sidebar.collapsedWidth : sizes.sidebar.width}
        minW={isCollapsed ? sizes.sidebar.collapsedWidth : sizes.sidebar.width}
        maxW={isCollapsed ? sizes.sidebar.collapsedWidth : sizes.sidebar.width}
        bg={colors.sidebar.bg}
        color={colors.sidebar.text}
        h="100vh"
        display="flex"
        flexDirection="column"
        overflowY="auto"
        overflowX="hidden"
        position="relative"
        zIndex="1"
        transition="width 0.3s ease"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
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
        {/* Основной контент */}
        {renderSidebarContent(!isCollapsed)}
      </Box>

      {/* Overlay для hover - показываем полный sidebar поверх контента */}
      {isCollapsed && isHovered && (
        <Box
          position="fixed"
          left="0"
          top="0"
          w={sizes.sidebar.width}
          h="100vh"
          bg={colors.sidebar.bg}
          color={colors.sidebar.text}
          zIndex="50"
          overflowY="auto"
          overflowX="hidden"
          boxShadow="2xl"
          display="flex"
          flexDirection="column"
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          opacity={0}
          animation="slideIn 0.3s ease forwards"
          css={{
            '@keyframes slideIn': {
              from: {
                opacity: 0,
                transform: 'translateX(-10px)',
              },
              to: {
                opacity: 1,
                transform: 'translateX(0)',
              },
            },
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
          {renderSidebarContent(true)}
        </Box>
      )}
    </>
  );
};

export default Sidebar;
