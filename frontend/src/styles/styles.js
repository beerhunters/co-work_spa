// styles/styles.js
// Все визуальные настройки в одном месте

export const colors = {
  sidebar: {
    bg: 'gray.900',
    borderColor: 'gray.700',
    text: 'white',
    textMuted: 'gray.400',
    hoverBg: 'gray.800'
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

export const sizes = {
  sidebar: {
    width: '260px',
    padding: 6,
    buttonPadding: { x: 4, y: 6 }
  },
  navbar: {
    padding: { x: 8, y: 4 }
  },
  content: {
    padding: 8,
    minHeight: 'calc(100vh - 80px)'
  }
};

export const styles = {
  layout: {
    minHeight: '100vh',
    bg: 'gray.50'
  },
  card: {
    borderRadius: 'xl',
    boxShadow: 'xl',
    transition: 'all 0.3s',
    hoverTransform: 'translateY(-4px)',
    hoverShadow: '2xl'
  },
  button: {
    borderRadius: 'lg',
    fontSize: 'md',
    transition: 'all 0.2s'
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
  transition: 'all 0.2s',
  transitionSlow: 'all 0.3s',
  hoverLift: {
    transform: 'translateY(-4px)',
    boxShadow: '2xl'
  },
  hoverSlide: {
    transform: 'translateX(4px)'
  },
  hoverButton: {
    transform: 'translateY(-2px)',
    boxShadow: 'lg'
  }
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