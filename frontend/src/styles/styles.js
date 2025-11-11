// styles/styles.js
// Все визуальные настройки в одном месте

export const colors = {
  // Основная цветовая палитра
  primary: {
    50: 'purple.50',
    100: 'purple.100',
    200: 'purple.200',
    300: 'purple.300',
    400: 'purple.400',
    500: 'purple.500',
    600: 'purple.600',
    700: 'purple.700',
    800: 'purple.800',
    900: 'purple.900'
  },
  secondary: {
    50: 'blue.50',
    500: 'blue.500',
    600: 'blue.600',
    700: 'blue.700'
  },
  accent: {
    500: 'orange.500',
    600: 'orange.600'
  },
  
  // Общие цвета для всего приложения
  background: {
    main: 'gray.50',
    card: 'white',
    overlay: 'blackAlpha.600'
  },
  text: {
    primary: 'gray.800',
    secondary: 'gray.600',
    muted: 'gray.500',
    light: 'gray.400',
    inverse: 'white',
    brand: 'purple.600'
  },
  border: {
    light: 'gray.100',
    medium: 'gray.200',
    dark: 'gray.300'
  },
  sidebar: {
    bg: 'gray.900',
    bgLight: 'gray.800',
    borderColor: 'gray.700',
    text: 'white',
    textSecondary: 'gray.300',
    textMuted: 'gray.400',
    textBright: 'gray.100',
    hoverBg: 'gray.800',
    activeBg: 'purple.600',
    accordionText: 'gray.100'
  },
  navbar: {
    bg: 'white',
    borderColor: 'gray.100',
    textColor: 'gray.800'
  },
  sections: {
    dashboard: { color: 'purple', icon: 'FiTrendingUp' },
    users: { color: 'blue', icon: 'FiUser' },
    bookings: { color: 'green', icon: 'FiCalendar' },
    tariffs: { color: 'cyan', icon: 'FiTag' },
    promocodes: { color: 'orange', icon: 'FiPercent' },
    tickets: { color: 'yellow', icon: 'FiHelpCircle' },
    notifications: { color: 'pink', icon: 'FiBell' },
    newsletters: { color: 'teal', icon: 'FiSend' }
  },
  stats: {
    users: {
      gradient: 'linear(to-br, blue.400, blue.600)',
      icon: 'FiUsers'
    },
    bookings: {
      gradient: 'linear(to-br, green.400, green.600)',
      icon: 'FiShoppingBag'
    },
    average_booking_value: {
      gradient: 'linear(to-br, purple.400, purple.600)',
      icon: 'FiDollarSign'
    },
    tickets: {
      gradient: 'linear(to-br, orange.400, orange.600)',
      icon: 'FiMessageCircle'
    }
  },
  notification: {
    indicatorBg: 'red.500',
    unreadBg: 'purple.50',
    unreadHover: 'purple.100',
    readBg: 'white',
    readHover: 'gray.50'
  },
  chart: {
    borderColor: 'rgb(147, 51, 234)',
    backgroundColor: 'rgba(147, 51, 234, 0.1)',
    pointColor: 'rgb(147, 51, 234)',
    gridColor: 'rgba(0, 0, 0, 0.05)'
  }
};

export const spacing = {
  xs: 2,
  sm: 4,
  md: 6,
  lg: 8,
  xl: 12,
  xxl: 16
};

export const sizes = {
  sidebar: {
    width: '280px',
    padding: spacing.md,
    buttonPadding: { x: spacing.sm, y: spacing.md }
  },
  navbar: {
    height: '70px',
    padding: { x: spacing.lg, y: spacing.sm }
  },
  content: {
    padding: spacing.lg,
    minHeight: 'calc(100vh - 70px)'
  },
  card: {
    borderRadius: 'xl',
    padding: spacing.md
  },
  button: {
    height: {
      sm: '32px',
      md: '40px',
      lg: '48px'
    },
    borderRadius: 'lg'
  }
};

export const typography = {
  fontSizes: {
    xs: '12px',
    sm: '14px',
    md: '16px',
    lg: '18px',
    xl: '20px',
    '2xl': '24px',
    '3xl': '30px'
  },
  fontWeights: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700
  },
  lineHeights: {
    normal: 1.5,
    relaxed: 1.625,
    loose: 2
  }
};

export const styles = {
  layout: {
    minHeight: '100vh',
    bg: colors.background.main
  },
  card: {
    bg: colors.background.card,
    borderRadius: 'xl',
    border: '1px solid',
    borderColor: colors.border.light,
    boxShadow: 'lg',
    p: spacing.md,
    transition: 'all 0.3s ease',
    _hover: {
      transform: 'translateY(-2px)',
      boxShadow: 'xl',
      borderColor: colors.border.medium
    },
    // Backward compatibility
    hoverTransform: 'translateY(-2px)',
    hoverShadow: 'xl'
  },
  button: {
    primary: {
      bg: colors.primary[600],
      color: colors.text.inverse,
      borderRadius: sizes.button.borderRadius,
      fontSize: typography.fontSizes.md,
      fontWeight: typography.fontWeights.medium,
      h: sizes.button.height.md,
      px: spacing.md,
      transition: 'all 0.2s ease',
      _hover: {
        bg: colors.primary[700],
        transform: 'translateY(-1px)',
        boxShadow: 'md'
      },
      _active: {
        transform: 'translateY(0)'
      }
    },
    secondary: {
      bg: 'transparent',
      color: colors.text.primary,
      border: '1px solid',
      borderColor: colors.border.medium,
      borderRadius: sizes.button.borderRadius,
      fontSize: typography.fontSizes.md,
      fontWeight: typography.fontWeights.medium,
      h: sizes.button.height.md,
      px: spacing.md,
      transition: 'all 0.2s ease',
      _hover: {
        bg: colors.background.main,
        borderColor: colors.primary[600],
        color: colors.primary[600]
      }
    },
    ghost: {
      bg: 'transparent',
      color: colors.text.secondary,
      borderRadius: sizes.button.borderRadius,
      fontSize: typography.fontSizes.md,
      fontWeight: typography.fontWeights.medium,
      h: sizes.button.height.md,
      px: spacing.md,
      transition: 'all 0.2s ease',
      _hover: {
        bg: colors.background.main,
        color: colors.text.primary
      }
    }
  },
  listItem: {
    padding: 4,
    borderRadius: 'lg',
    border: '1px',
    borderColor: 'gray.200',
    bg: 'white',
    cursor: 'pointer',
    transition: 'all 0.2s',
    hover: {
      bg: 'gray.50',
      transform: 'translateX(4px)'
    }
  },
  modal: {
    size: 'lg',
    borderRadius: 'xl'
  },
  login: {
    gradient: 'linear(to-br, blue.50, purple.50)',
    cardGradient: 'linear(to-r, blue.500, purple.600)',
    buttonGradient: 'linear(to-r, blue.500, purple.600)',
    buttonHoverGradient: 'linear(to-r, blue.600, purple.700)',
    inputFocusBorder: 'purple.500'
  },
  chart: {
    height: '350px',
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          padding: 12,
          cornerRadius: 8
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(0, 0, 0, 0.05)' }
        },
        x: {
          grid: { display: false }
        }
      }
    }
  }
};

export const animations = {
  transitions: {
    fast: 'all 0.15s ease',
    normal: 'all 0.2s ease',
    slow: 'all 0.3s ease'
  },
  effects: {
    hoverLift: {
      transform: 'translateY(-2px)',
      boxShadow: 'xl'
    },
    hoverSlide: {
      transform: 'translateX(4px)'
    },
    hoverButton: {
      transform: 'translateY(-1px)',
      boxShadow: 'md'
    },
    fadeIn: {
      opacity: 1,
      transition: 'opacity 0.3s ease'
    },
    slideIn: {
      transform: 'translateX(0)',
      transition: 'transform 0.3s ease'
    }
  }
};

export const shadows = {
  card: 'rgba(0, 0, 0, 0.1) 0px 1px 3px 0px, rgba(0, 0, 0, 0.06) 0px 1px 2px 0px',
  cardHover: 'rgba(0, 0, 0, 0.15) 0px 4px 12px 0px, rgba(0, 0, 0, 0.1) 0px 2px 4px 0px',
  button: 'rgba(0, 0, 0, 0.1) 0px 2px 4px 0px',
  modal: 'rgba(0, 0, 0, 0.25) 0px 8px 32px 0px'
};

export const getStatusColor = (status, type = 'badge') => {
  const statusColors = {
    // Заявки
    'OPEN': 'green',
    'IN_PROGRESS': 'yellow',
    'CLOSED': 'red',
    // Бронирования
    'paid': 'green',
    'unpaid': 'red',
    'confirmed': 'green',
    'pending': 'yellow',
    // Общие
    'active': 'green',
    'inactive': 'red',
    'read': 'gray',
    'unread': 'purple'
  };

  return statusColors[status] || 'gray';
};