import React from 'react';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  Box,
  Icon,
  useColorModeValue
} from '@chakra-ui/react';
import { FiChevronRight, FiHome } from 'react-icons/fi';

// Карта секций на breadcrumb пути
const breadcrumbsMap = {
  dashboard: ['Главная', 'Дашборд'],
  users: ['Главная', 'Пользователи'],
  bookings: ['Главная', 'Бронирования'],
  tariffs: ['Главная', 'Тарифы'],
  offices: ['Главная', 'Офисы'],
  promocodes: ['Главная', 'Промокоды'],
  tickets: ['Главная', 'Заявки поддержки'],
  notifications: ['Главная', 'Уведомления'],
  newsletters: ['Главная', 'Рассылки'],
  emails: ['Главная', 'Email рассылки'],
  officesubscriptions: ['Главная', 'Подписки на офисы'],
  admins: ['Главная', 'Администрирование', 'Администраторы'],
  backups: ['Главная', 'Администрирование', 'Бэкапы'],
  'system-monitoring': ['Главная', 'Администрирование', 'Мониторинг системы'],
  'scheduled-tasks': ['Главная', 'Администрирование', 'Запланированные задачи'],
  logging: ['Главная', 'Администрирование', 'Логирование'],
  'ip-bans': ['Главная', 'Администрирование', 'IP баны'],
};

// Карта секций на их ключи для навигации
const sectionKeyMap = {
  'Главная': 'dashboard',
  'Дашборд': 'dashboard',
  'Пользователи': 'users',
  'Бронирования': 'bookings',
  'Тарифы': 'tariffs',
  'Офисы': 'offices',
  'Промокоды': 'promocodes',
  'Заявки поддержки': 'tickets',
  'Уведомления': 'notifications',
  'Рассылки': 'newsletters',
  'Email рассылки': 'emails',
  'Подписки на офисы': 'officesubscriptions',
  'Администрирование': 'admins',
  'Администраторы': 'admins',
  'Бэкапы': 'backups',
  'Мониторинг системы': 'system-monitoring',
  'Запланированные задачи': 'scheduled-tasks',
  'Логирование': 'logging',
  'IP баны': 'ip-bans',
};

/**
 * Компонент навигационных хлебных крошек (breadcrumbs)
 * @param {string} section - Текущая активная секция
 * @param {function} setSection - Функция для изменения активной секции
 */
export const Breadcrumbs = ({ section, setSection }) => {
  const bg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const linkColor = useColorModeValue('purple.600', 'purple.300');
  const currentColor = useColorModeValue('gray.600', 'gray.400');

  // Получаем путь breadcrumbs для текущей секции
  const breadcrumbPath = breadcrumbsMap[section] || ['Главная', 'Дашборд'];

  // Функция обработки клика по breadcrumb
  const handleBreadcrumbClick = (label, index) => {
    // Последний элемент не кликабельный (текущая страница)
    if (index === breadcrumbPath.length - 1) return;

    // Получаем ключ секции для навигации
    const sectionKey = sectionKeyMap[label];
    if (sectionKey && setSection) {
      setSection(sectionKey);
    }
  };

  return (
    <Box
      bg={bg}
      borderBottomWidth="1px"
      borderColor={borderColor}
      px={6}
      py={3}
    >
      <Breadcrumb
        spacing="8px"
        separator={<Icon as={FiChevronRight} color="gray.400" />}
      >
        {breadcrumbPath.map((label, index) => {
          const isLast = index === breadcrumbPath.length - 1;
          const isFirst = index === 0;

          return (
            <BreadcrumbItem key={index} isCurrentPage={isLast}>
              <BreadcrumbLink
                onClick={() => !isLast && handleBreadcrumbClick(label, index)}
                cursor={isLast ? 'default' : 'pointer'}
                color={isLast ? currentColor : linkColor}
                fontWeight={isLast ? 'semibold' : 'normal'}
                _hover={isLast ? {} : { textDecoration: 'underline' }}
                display="flex"
                alignItems="center"
                gap={1}
              >
                {isFirst && <Icon as={FiHome} boxSize={4} />}
                {label}
              </BreadcrumbLink>
            </BreadcrumbItem>
          );
        })}
      </Breadcrumb>
    </Box>
  );
};

export default Breadcrumbs;
