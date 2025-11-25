import React, { createContext, useContext, useState, useEffect } from 'react';
import Joyride, { ACTIONS, EVENTS, STATUS } from 'react-joyride';
import { useColorModeValue } from '@chakra-ui/react';

const OnboardingContext = createContext();

export const useOnboarding = () => {
  const context = useContext(OnboardingContext);
  if (!context) {
    throw new Error('useOnboarding must be used within OnboardingProvider');
  }
  return context;
};

// Шаги онбординга для разных разделов админ-панели
const tourSteps = {
  dashboard: [
    {
      target: '[data-tour="dashboard-stats"]',
      content: 'Здесь отображается основная статистика: активные пользователи, бронирования и доходы.',
      disableBeacon: true,
      placement: 'bottom',
    },
    {
      target: '[data-tour="dashboard-charts"]',
      content: 'Графики показывают динамику бронирований и доходов за выбранный период.',
      placement: 'top',
    },
    {
      target: '[data-tour="dashboard-filter"]',
      content: 'Используйте фильтры для просмотра данных за разные периоды времени.',
      placement: 'left',
    },
  ],
  users: [
    {
      target: '[data-tour="users-search"]',
      content: 'Поиск пользователей по имени, email или Telegram ID.',
      disableBeacon: true,
      placement: 'bottom',
    },
    {
      target: '[data-tour="users-filters"]',
      content: 'Фильтруйте пользователей по статусу или другим критериям.',
      placement: 'bottom',
    },
    {
      target: '[data-tour="users-actions"]',
      content: 'Действия над пользователями: просмотр деталей, блокировка, редактирование.',
      placement: 'left',
    },
  ],
  bookings: [
    {
      target: '[data-tour="bookings-list"]',
      content: 'Список всех бронирований с информацией о пользователях и статусах.',
      disableBeacon: true,
      placement: 'bottom',
    },
    {
      target: '[data-tour="bookings-status"]',
      content: 'Меняйте статусы бронирований: ожидание, подтверждено, отменено.',
      placement: 'left',
    },
  ],
  tickets: [
    {
      target: '[data-tour="tickets-list"]',
      content: 'Тикеты поддержки от пользователей. Здесь можно просмотреть все обращения.',
      disableBeacon: true,
      placement: 'bottom',
    },
    {
      target: '[data-tour="tickets-filters"]',
      content: 'Фильтруйте тикеты по статусу: открытые, в работе, закрытые.',
      placement: 'bottom',
    },
  ],
  emails: [
    {
      target: '[data-tour="emails-create"]',
      content: 'Создавайте email кампании для массовых рассылок пользователям.',
      disableBeacon: true,
      placement: 'bottom',
    },
    {
      target: '[data-tour="emails-template"]',
      content: 'Используйте редактор для создания красивых email писем с персонализацией.',
      placement: 'top',
    },
  ],
  notifications: [
    {
      target: '[data-tour="notifications-filters"]',
      content: 'Фильтруйте уведомления по статусу и типу.',
      disableBeacon: true,
      placement: 'bottom',
    },
    {
      target: '[data-tour="notifications-grouping"]',
      content: 'Группируйте уведомления по дате или типу для удобного просмотра.',
      placement: 'bottom',
    },
    {
      target: '[data-tour="notifications-actions"]',
      content: 'Отмечайте уведомления как прочитанные или удаляйте их.',
      placement: 'left',
    },
  ],
};

export const OnboardingProvider = ({ children }) => {
  const [runTour, setRunTour] = useState(false);
  const [currentSection, setCurrentSection] = useState('dashboard');
  const [stepIndex, setStepIndex] = useState(0);
  const [completedTours, setCompletedTours] = useState([]);

  // Цвета для Joyride (адаптируются под светлую/темную тему)
  const bgColor = useColorModeValue('#fff', '#2D3748');
  const textColor = useColorModeValue('#000', '#fff');
  const primaryColor = useColorModeValue('#805AD5', '#B794F4');
  const arrowColor = useColorModeValue('#fff', '#2D3748');

  // Загрузка завершенных туров из localStorage
  useEffect(() => {
    const saved = localStorage.getItem('onboarding_completed');
    if (saved) {
      try {
        setCompletedTours(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to load onboarding state:', e);
      }
    }
  }, []);

  // Сохранение завершенных туров в localStorage
  const saveCompletedTours = (tours) => {
    localStorage.setItem('onboarding_completed', JSON.stringify(tours));
    setCompletedTours(tours);
  };

  // Запуск тура для определенной секции
  const startTour = (section = 'dashboard') => {
    if (tourSteps[section]) {
      setCurrentSection(section);
      setStepIndex(0);
      setRunTour(true);
    }
  };

  // Остановка тура
  const stopTour = () => {
    setRunTour(false);
  };

  // Перезапуск всех туров (сброс)
  const resetTours = () => {
    localStorage.removeItem('onboarding_completed');
    setCompletedTours([]);
  };

  // Проверка, был ли пройден тур для секции
  const isTourCompleted = (section) => {
    return completedTours.includes(section);
  };

  // Автозапуск тура при первом посещении секции
  const autoStartTour = (section) => {
    if (!isTourCompleted(section) && tourSteps[section]) {
      // Задержка для загрузки компонентов
      setTimeout(() => {
        startTour(section);
      }, 500);
    }
  };

  // Обработчик событий Joyride
  const handleJoyrideCallback = (data) => {
    const { action, index, status, type } = data;

    if ([EVENTS.STEP_AFTER, EVENTS.TARGET_NOT_FOUND].includes(type)) {
      // Переход к следующему шагу
      setStepIndex(index + (action === ACTIONS.PREV ? -1 : 1));
    } else if ([STATUS.FINISHED, STATUS.SKIPPED].includes(status)) {
      // Тур завершен или пропущен
      setRunTour(false);

      // Отмечаем тур как завершенный
      if (status === STATUS.FINISHED && !completedTours.includes(currentSection)) {
        saveCompletedTours([...completedTours, currentSection]);
      }
    }
  };

  // Настройки стиля для Joyride
  const joyrideStyles = {
    options: {
      arrowColor: arrowColor,
      backgroundColor: bgColor,
      overlayColor: 'rgba(0, 0, 0, 0.5)',
      primaryColor: primaryColor,
      textColor: textColor,
      width: 360,
      zIndex: 10000,
    },
    buttonNext: {
      backgroundColor: primaryColor,
      fontSize: 14,
      borderRadius: 8,
      padding: '8px 16px',
    },
    buttonBack: {
      color: primaryColor,
      fontSize: 14,
      marginRight: 10,
    },
    buttonSkip: {
      color: textColor,
      fontSize: 14,
    },
    tooltip: {
      borderRadius: 8,
      padding: 20,
    },
    tooltipContent: {
      padding: '10px 0',
      fontSize: 14,
      lineHeight: 1.5,
    },
    tooltipTitle: {
      fontSize: 16,
      fontWeight: 600,
      marginBottom: 10,
    },
  };

  const currentSteps = tourSteps[currentSection] || [];

  return (
    <OnboardingContext.Provider
      value={{
        startTour,
        stopTour,
        resetTours,
        isTourCompleted,
        autoStartTour,
        completedTours,
      }}
    >
      {children}

      <Joyride
        steps={currentSteps}
        run={runTour}
        stepIndex={stepIndex}
        continuous
        showProgress
        showSkipButton
        callback={handleJoyrideCallback}
        styles={joyrideStyles}
        locale={{
          back: 'Назад',
          close: 'Закрыть',
          last: 'Завершить',
          next: 'Далее',
          skip: 'Пропустить',
        }}
        floaterProps={{
          disableAnimation: false,
        }}
      />
    </OnboardingContext.Provider>
  );
};
