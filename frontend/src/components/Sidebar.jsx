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
import { FiHome, FiTrendingUp, FiUser, FiCalendar, FiTag, FiPercent, FiHelpCircle, FiBell, FiSend, FiLogOut, FiShield, FiDatabase, FiActivity, FiLayers, FiCpu, FiKey, FiSettings, FiChevronDown, FiChevronRight, FiFileText } from 'react-icons/fi';
import { colors, sizes, styles, typography, spacing, animations } from '../styles/styles';

const Sidebar = ({ section, setSection, handleLogout, currentAdmin }) => {
  const [isAdminAccordionOpen, setIsAdminAccordionOpen] = useState(false);

  // Основные пункты меню
  const mainMenuItems = [
    { icon: FiTrendingUp, label: 'Дашборд', section: 'dashboard', color: 'purple' },
    { icon: FiUser, label: 'Пользователи', section: 'users', color: 'blue' },
    { icon: FiCalendar, label: 'Бронирования', section: 'bookings', color: 'green' },
    { icon: FiTag, label: 'Тарифы', section: 'tariffs', color: 'cyan' },
    { icon: FiPercent, label: 'Промокоды', section: 'promocodes', color: 'orange' },
    { icon: FiHelpCircle, label: 'Заявки', section: 'tickets', color: 'yellow' },
    { icon: FiBell, label: 'Уведомления', section: 'notifications', color: 'pink' },
    { icon: FiSend, label: 'Рассылка', section: 'newsletters', color: 'teal' },
  ];

  // Административные функции для super_admin
  const adminMenuItems = [
    { icon: FiActivity, label: 'Мониторинг', section: 'monitoring', color: 'green' },
    { icon: FiLayers, label: 'Кэш', section: 'cache', color: 'blue' },
    { icon: FiCpu, label: 'Производительность', section: 'performance', color: 'purple' },
    { icon: FiFileText, label: 'Логирование', section: 'logging', color: 'gray' },
    { icon: FiShield, label: 'IP Баны', section: 'ip-bans', color: 'red' },
    { icon: FiKey, label: 'API ключи', section: 'api-keys', color: 'orange' },
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
      // Если выбран административный раздел, открываем аккордеон
      setIsAdminAccordionOpen(true);
    } else if (isMainSectionActive) {
      // Если выбран основной раздел, закрываем аккордеон  
      setIsAdminAccordionOpen(false);
    }
  }, [isAdminSectionActive, isMainSectionActive]);

  return (
    <Box
      w={sizes.sidebar.width}
      minW={sizes.sidebar.width}
      maxW={sizes.sidebar.width}
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
      <Box p={spacing.md}>
        <VStack align="stretch" spacing={1}>
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

          {/* Основные пункты меню */}
          {mainMenuItems.map(({ icon: ItemIcon, label, section: sec, color }) => (
            <Button
              key={sec}
              leftIcon={<ItemIcon />}
              variant={section === sec ? 'solid' : 'ghost'}
              bg={section === sec ? `${color}.600` : 'transparent'}
              color={section === sec ? colors.sidebar.text : colors.sidebar.textMuted}
              justifyContent="flex-start"
              onClick={() => setSection(sec)}
              borderRadius={sizes.button.borderRadius}
              px={sizes.sidebar.buttonPadding.x}
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
              {label}
            </Button>
          ))}

          {/* Административный аккордеон для super_admin */}
          {currentAdmin?.role === 'super_admin' && (
            <Box mt={4}>
              {/* Заголовок аккордеона */}
              <Button
                variant="ghost"
                justifyContent="flex-start"
                onClick={() => setIsAdminAccordionOpen(!isAdminAccordionOpen)}
                _hover={{
                  bg: colors.sidebar.hoverBg,
                  color: colors.sidebar.text,
                }}
                borderRadius={sizes.button.borderRadius}
                px={sizes.sidebar.buttonPadding.x}
                py={sizes.sidebar.buttonPadding.y}
                fontSize={typography.fontSizes.md}
                fontWeight={typography.fontWeights.medium}
                h={sizes.button.height.md}
                transition={animations.transitions.normal}
                w="full"
                leftIcon={<Icon as={FiSettings} color={colors.sidebar.accordionText} />}
                rightIcon={
                  <Icon 
                    as={FiChevronRight} 
                    color={colors.sidebar.accordionText}
                    transition={animations.transitions.normal}
                    transform={isAdminAccordionOpen ? 'rotate(90deg)' : 'rotate(0deg)'}
                  />
                }
              >
                <Text color={colors.sidebar.accordionText} fontSize={typography.fontSizes.md} fontWeight={typography.fontWeights.medium}>
                  Администрирование
                </Text>
              </Button>

              {/* Содержимое аккордеона */}
              <Collapse in={isAdminAccordionOpen} animateOpacity>
                <VStack align="stretch" spacing={1} mt={2} pl={4}>
                  {adminMenuItems.map(({ icon: ItemIcon, label, section: sec, color }) => (
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
                        transform: 'translateX(2px)'
                      }}
                      borderRadius={sizes.button.borderRadius}
                      px={sizes.sidebar.buttonPadding.x}
                      py={sizes.sidebar.buttonPadding.y}
                      fontSize={typography.fontSizes.sm}
                      fontWeight={typography.fontWeights.medium}
                      h={sizes.button.height.sm}
                      transition={animations.transitions.normal}
                      size="sm"
                    >
                      {label}
                    </Button>
                  ))}
                </VStack>
              </Collapse>
            </Box>
          )}
        </VStack>
      </Box>

      <Spacer />

      <Box p={spacing.md} borderTop="1px" borderColor={colors.sidebar.borderColor}>
        <Button
          leftIcon={<FiLogOut />}
          variant="ghost"
          color="red.400"
          justifyContent="flex-start"
          onClick={handleLogout}
          _hover={{
            bg: 'red.900',
            color: 'red.300',
            transform: 'translateX(2px)'
          }}
          borderRadius={sizes.button.borderRadius}
          px={sizes.sidebar.buttonPadding.x}
          py={sizes.sidebar.buttonPadding.y}
          w="full"
          fontSize={typography.fontSizes.md}
          fontWeight={typography.fontWeights.medium}
          h={sizes.button.height.md}
          transition={animations.transitions.normal}
        >
          Выйти из системы
        </Button>
      </Box>
    </Box>
  );
};

export default Sidebar;