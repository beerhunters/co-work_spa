import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box,
  Card,
  CardHeader,
  CardBody,
  Heading,
  VStack,
  HStack,
  Text,
  Icon,
  Button,
  FormControl,
  FormLabel,
  Select,
  Textarea,
  Badge,
  useToast,
  Divider,
  SimpleGrid,
  Image,
  IconButton,
  Checkbox,
  CheckboxGroup,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Spinner,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Tooltip,
  Input,
  FormHelperText,
  Alert,
  AlertIcon,
  AlertDescription,
  useColorModeValue,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure,
  Collapse,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Flex,
} from '@chakra-ui/react';
import {
  FiUsers,
  FiSend,
  FiImage,
  FiX,
  FiCheck,
  FiAlertCircle,
  FiBold,
  FiItalic,
  FiCode,
  FiUnderline,
  FiRefreshCw,
  FiTrash2,
  FiTrash,
  FiChevronDown,
  FiChevronRight,
  FiEye,
  FiLink,
  FiBarChart2,
  FiDownload,
  FiMail,
  FiCheckCircle,
  FiPercent
} from 'react-icons/fi';
import { newsletterApi, userApi } from '../utils/api';
import TelegramEditor from '../components/TelegramEditor';
import { sanitizeHtmlForTelegram } from '../utils/telegram-html-sanitizer';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

const Newsletters = ({ newsletters: initialNewsletters = [], currentAdmin }) => {
  const [newsletters, setNewsletters] = useState(initialNewsletters);
  const [users, setUsers] = useState([]);
  const [recipientType, setRecipientType] = useState('all');
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [message, setMessage] = useState('');
  const [photos, setPhotos] = useState([]);
  const [isSending, setIsSending] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isUserModalOpen, setUserModalOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  // Состояния для сегментации
  const [segmentType, setSegmentType] = useState('active_users');
  const [segmentParams, setSegmentParams] = useState({ days: 30 });

  // Состояния для фильтров истории
  const [filterStatus, setFilterStatus] = useState('');
  const [filterRecipientType, setFilterRecipientType] = useState('');
  const [filterSearch, setFilterSearch] = useState('');

  // Состояние для модального окна статистики
  const [selectedNewsletter, setSelectedNewsletter] = useState(null);
  const [isStatsModalOpen, setIsStatsModalOpen] = useState(false);
  const [recipientDetails, setRecipientDetails] = useState(null);
  const [isLoadingRecipients, setIsLoadingRecipients] = useState(false);

  // Состояния для аккордеонов
  const [isNewNewsletterOpen, setIsNewNewsletterOpen] = useState(() => {
    const saved = localStorage.getItem('newsletter_form_open');
    return saved !== null ? JSON.parse(saved) : true;
  });
  const [isAnalyticsOpen, setIsAnalyticsOpen] = useState(() => {
    const saved = localStorage.getItem('newsletter_analytics_open');
    return saved !== null ? JSON.parse(saved) : true;
  });
  const [isHistoryOpen, setIsHistoryOpen] = useState(() => {
    const saved = localStorage.getItem('newsletter_history_open');
    return saved !== null ? JSON.parse(saved) : true;
  });

  const toast = useToast();
  const bgColor = useColorModeValue('gray.50', 'gray.900');
  const cardBg = useColorModeValue('white', 'gray.800');

  // Мемоизируем количество пользователей для предотвращения ререндеров
  const totalUsersWithTelegram = React.useMemo(() => {
    return users.filter(u => u.telegram_id).length;
  }, [users]);

  // Аналитика рассылок
  const analyticsData = useMemo(() => {
    if (!newsletters || newsletters.length === 0) {
      return {
        kpis: {
          total: 0,
          successRate: 0,
          totalRecipients: 0,
          avgSuccessRate: 0,
        },
        statusDistribution: [],
        successRateOverTime: [],
        newslettersByDate: [],
      };
    }

    // KPI расчеты
    const total = newsletters.length;
    const successCount = newsletters.filter(n => n.status === 'success').length;
    const totalRecipients = newsletters.reduce((sum, n) => sum + (n.total_count || 0), 0);
    const totalSuccess = newsletters.reduce((sum, n) => sum + (n.success_count || 0), 0);
    const avgSuccessRate = totalRecipients > 0 ? ((totalSuccess / totalRecipients) * 100).toFixed(1) : 0;

    // Распределение по статусам для Pie Chart
    const statusCounts = newsletters.reduce((acc, n) => {
      acc[n.status] = (acc[n.status] || 0) + 1;
      return acc;
    }, {});

    const statusDistribution = [
      { name: 'Успешно', value: statusCounts['success'] || 0, color: '#48BB78' },
      { name: 'Частично', value: statusCounts['partial'] || 0, color: '#ECC94B' },
      { name: 'Ошибка', value: statusCounts['failed'] || 0, color: '#F56565' },
    ].filter(item => item.value > 0);

    // Успешность по времени для Line Chart (последние 30 дней)
    const last30Days = newsletters
      .slice(0, 30)
      .reverse()
      .map((n, index) => ({
        name: new Date(n.created_at).toLocaleDateString('ru-RU', { month: 'short', day: 'numeric' }),
        'Процент успеха': n.total_count > 0 ? ((n.success_count / n.total_count) * 100).toFixed(1) : 0,
        'Отправлено': n.total_count,
      }));

    // Количество рассылок по дням для Bar Chart
    const newslettersByDate = newsletters.reduce((acc, n) => {
      const date = new Date(n.created_at).toLocaleDateString('ru-RU', { month: 'short', day: 'numeric' });
      const existing = acc.find(item => item.date === date);
      if (existing) {
        existing.count += 1;
      } else {
        acc.push({ date, count: 1 });
      }
      return acc;
    }, []);

    // Сортируем и берем последние 14 дней
    const sortedByDate = newslettersByDate.slice(0, 14).reverse();

    return {
      kpis: {
        total,
        successRate: total > 0 ? ((successCount / total) * 100).toFixed(1) : 0,
        totalRecipients,
        avgSuccessRate,
      },
      statusDistribution,
      successRateOverTime: last30Days,
      newslettersByDate: sortedByDate,
    };
  }, [newsletters]);

  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure();
  const { isOpen: isClearOpen, onOpen: onClearOpen, onClose: onClearClose } = useDisclosure();
  const cancelRef = React.useRef();
  const fileInputRef = React.useRef(); // Ref для file input, чтобы сбрасывать после отправки

  // Мемоизированные callbacks для модального окна выбора пользователей
  const handleSelectedUsersChange = useCallback((newSelectedUsers) => {
    setSelectedUsers(newSelectedUsers);
  }, []);

  const handleCloseUserModal = useCallback(() => {
    setUserModalOpen(false);
  }, []);

  // Проверка прав доступа (мемоизировано для предотвращения лишних ре-рендеров)
  const canViewNewsletters = useMemo(() =>
    currentAdmin?.role === 'super_admin' ||
    (currentAdmin?.permissions && currentAdmin.permissions.includes('view_telegram_newsletters')),
    [currentAdmin]
  );

  const canSendNewsletters = useMemo(() =>
    currentAdmin?.role === 'super_admin' ||
    (currentAdmin?.permissions && currentAdmin.permissions.includes('send_telegram_newsletters')),
    [currentAdmin]
  );

  const canManageNewsletters = useMemo(() =>
    currentAdmin?.role === 'super_admin' ||
    (currentAdmin?.permissions && currentAdmin.permissions.includes('manage_telegram_newsletters')),
    [currentAdmin]
  );

  // Если нет прав на просмотр, показываем сообщение об ошибке
  if (!canViewNewsletters) {
    return (
      <Box p={6} textAlign="center">
        <Text fontSize="xl" color="red.500" mb={4}>
          Доступ запрещен
        </Text>
        <Text color="gray.500">
          У вас нет прав для просмотра рассылок
        </Text>
      </Box>
    );
  }

  // Загрузка данных при монтировании
  useEffect(() => {
    fetchNewsletters();
    if (canSendNewsletters) {
      fetchUsers();
    }
  }, [canSendNewsletters]);

  // Перезагрузка при изменении фильтров
  useEffect(() => {
    fetchNewsletters();
  }, [filterStatus, filterRecipientType, filterSearch]);

  // Сохранение состояний аккордеонов в localStorage
  useEffect(() => {
    localStorage.setItem('newsletter_form_open', JSON.stringify(isNewNewsletterOpen));
  }, [isNewNewsletterOpen]);

  useEffect(() => {
    localStorage.setItem('newsletter_analytics_open', JSON.stringify(isAnalyticsOpen));
  }, [isAnalyticsOpen]);

  useEffect(() => {
    localStorage.setItem('newsletter_history_open', JSON.stringify(isHistoryOpen));
  }, [isHistoryOpen]);

  // Загрузка детальной информации о получателях при открытии статистики
  useEffect(() => {
    if (selectedNewsletter && isStatsModalOpen) {
      const fetchRecipients = async () => {
        setIsLoadingRecipients(true);
        try {
          const data = await newsletterApi.getRecipients(selectedNewsletter.id);
          setRecipientDetails(data);
        } catch (error) {
          console.error('Ошибка загрузки получателей:', error);
          toast({
            title: 'Ошибка',
            description: 'Не удалось загрузить список получателей',
            status: 'error',
            duration: 3000,
          });
        } finally {
          setIsLoadingRecipients(false);
        }
      };
      fetchRecipients();
    }
  }, [selectedNewsletter, isStatsModalOpen]);



  const fetchUsers = async () => {
    try {
      const data = await userApi.getAll();
      setUsers(data);
    } catch (error) {
      console.error('Ошибка загрузки пользователей:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось загрузить список пользователей',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const fetchNewsletters = async () => {
    setIsLoading(true);
    try {
      // Формируем параметры запроса с фильтрами
      const params = {};
      if (filterStatus) params.status = filterStatus;
      if (filterRecipientType) params.recipient_type = filterRecipientType;
      if (filterSearch) params.search = filterSearch;

      const data = await newsletterApi.getHistory(params);
      setNewsletters(data);
    } catch (error) {
      console.error('Ошибка загрузки истории:', error);

      // Проверяем, не связана ли ошибка с правами доступа
      if (error.response?.status === 403) {
        toast({
          title: 'Доступ запрещен',
          description: 'У вас нет прав для просмотра истории рассылок',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      } else {
        toast({
          title: 'Ошибка',
          description: 'Не удалось загрузить историю рассылок',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Удаление конкретной рассылки
  const handleDeleteNewsletter = async (newsletter) => {
    setDeleteTarget(newsletter);
    onDeleteOpen();
  };

  const confirmDeleteNewsletter = async () => {
    if (!deleteTarget) return;

    setIsDeleting(true);
    try {
      await newsletterApi.delete(deleteTarget.id);

      toast({
        title: 'Успешно',
        description: 'Рассылка удалена',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Обновляем список
      await fetchNewsletters();

    } catch (error) {
      console.error('Ошибка удаления рассылки:', error);

      let errorMessage = 'Не удалось удалить рассылку';
      if (error.response?.status === 403) {
        errorMessage = 'У вас нет прав для удаления рассылок';
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }

      toast({
        title: 'Ошибка',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
      onDeleteClose();
    }
  };

  // Очистка всей истории
  const handleClearHistory = () => {
    onClearOpen();
  };

  const confirmClearHistory = async () => {
    setIsDeleting(true);
    try {
      await newsletterApi.clearHistory();

      toast({
        title: 'Успешно',
        description: 'История рассылок очищена',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Обновляем список
      setNewsletters([]);

    } catch (error) {
      console.error('Ошибка очистки истории:', error);

      let errorMessage = 'Не удалось очистить историю';
      if (error.response?.status === 403) {
        errorMessage = 'У вас нет прав для очистки истории рассылок';
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }

      toast({
        title: 'Ошибка',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsDeleting(false);
      onClearClose();
    }
  };

  // Открытие модального окна статистики
  const handleOpenStats = (newsletter) => {
    setSelectedNewsletter(newsletter);
    setIsStatsModalOpen(true);
  };

  const handleCloseStats = () => {
    setSelectedNewsletter(null);
    setIsStatsModalOpen(false);
    setRecipientDetails(null);
  };

  // Экспорт в CSV
  const handleExportCSV = async () => {
    try {
      // Формируем URL с фильтрами
      const params = new URLSearchParams();
      if (filterStatus) params.append('status', filterStatus);
      if (filterRecipientType) params.append('recipient_type', filterRecipientType);
      if (filterSearch) params.append('search', filterSearch);

      // Получаем токен из localStorage
      const token = localStorage.getItem('token');

      // Создаем ссылку для скачивания
      const url = `/api/newsletters/export-csv?${params.toString()}`;

      // Используем fetch для скачивания файла
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Ошибка при экспорте');
      }

      // Получаем blob
      const blob = await response.blob();

      // Создаём ссылку для скачивания
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `newsletters_export_${new Date().getTime()}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);

      toast({
        title: 'Успешно',
        description: 'История рассылок экспортирована',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

    } catch (error) {
      console.error('Ошибка экспорта:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось экспортировать историю',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Обработка загрузки фото
  const handlePhotoUpload = (e) => {
    const files = Array.from(e.target.files);

    if (photos.length + files.length > 10) {
      toast({
        title: 'Ограничение',
        description: 'Максимум 10 фотографий',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    const newPhotos = files.map(file => ({
      file,
      preview: URL.createObjectURL(file),
      id: Date.now() + Math.random()
    }));

    setPhotos([...photos, ...newPhotos]);
  };

  // Удаление фото
  const removePhoto = (photoId) => {
    const photo = photos.find(p => p.id === photoId);
    if (photo?.preview) {
      URL.revokeObjectURL(photo.preview);
    }
    const newPhotos = photos.filter(p => p.id !== photoId);
    setPhotos(newPhotos);

    // Сбросить input если все фото удалены
    if (newPhotos.length === 0 && fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };


  // Отправка рассылки
  const handleSendNewsletter = async () => {
    if (!message.trim()) {
      toast({
        title: 'Ошибка',
        description: 'Введите текст сообщения',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    if (recipientType === 'selected' && selectedUsers.length === 0) {
      toast({
        title: 'Ошибка',
        description: 'Выберите получателей',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsSending(true);

    try {
      // Очищаем HTML для Telegram перед отправкой
      const sanitizedMessage = sanitizeHtmlForTelegram(message);

      const formData = new FormData();
      formData.append('message', sanitizedMessage);
      formData.append('recipient_type', recipientType);

      if (recipientType === 'selected') {
        selectedUsers.forEach(userId => {
          formData.append('user_ids', userId);
        });
      }

      photos.forEach((photo) => {
        formData.append('photos', photo.file);
      });

      const result = await newsletterApi.send(formData);

      setIsSending(false);

      toast({
        title: 'Рассылка запущена',
        description: `Отправка ${result.total_count} сообщений в процессе... Результаты будут доступны в истории рассылок.`,
        status: 'info',
        duration: 5000,
        isClosable: true,
      });

      // Очищаем форму
      setMessage('');
      setPhotos([]);
      setSelectedUsers([]);
      setRecipientType('all');
      setSegmentType('active_users');
      setSegmentParams({ days: 30 });

      // Сбрасываем file input чтобы можно было выбрать те же файлы снова
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      // Обновляем историю
      await fetchNewsletters();

    } catch (error) {
      console.error('Ошибка отправки:', error);

      setIsSending(false);

      let errorMessage = 'Не удалось отправить рассылку';
      if (error.response?.status === 403) {
        errorMessage = 'У вас нет прав для отправки рассылок';
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }

      toast({
        title: 'Ошибка отправки',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Мемоизированный компонент выбора пользователей с изолированным поиском
  const UserSelectionModal = React.memo(({
    isOpen,
    onClose,
    users,
    selectedUsers,
    onSelectedUsersChange,
    totalUsersWithTelegram
  }) => {
    const [searchQuery, setSearchQuery] = useState('');
    // Локальное состояние для выбранных пользователей (не обновляет родителя при каждом клике)
    const [localSelectedUsers, setLocalSelectedUsers] = useState(selectedUsers);

    // Синхронизация локального состояния с родительским при открытии модального окна
    useEffect(() => {
      if (isOpen) {
        setLocalSelectedUsers(selectedUsers);
      }
    }, [isOpen, selectedUsers]);

    // Вычисляем cardBg внутри компонента, чтобы избежать пропса с нестабильной ссылкой
    const cardBg = useColorModeValue('white', 'gray.800');

    // Локальная фильтрация пользователей
    const filteredUsers = useMemo(() => {
      if (!searchQuery.trim()) return users;

      const query = searchQuery.toLowerCase();
      return users.filter(user => {
        return (
          user.full_name?.toLowerCase().includes(query) ||
          user.username?.toLowerCase().includes(query) ||
          user.email?.toLowerCase().includes(query) ||
          user.phone?.includes(query)
        );
      });
    }, [users, searchQuery]);

    // Обработчик изменения поиска
    const handleSearchChange = useCallback((e) => {
      setSearchQuery(e.target.value);
    }, []);

    // Сброс поиска при закрытии модального окна
    const handleCloseModal = useCallback(() => {
      setSearchQuery('');
      onClose();
    }, [onClose]);

    // Выбрать всех пользователей из отфильтрованного списка
    const handleSelectAll = useCallback(() => {
      const allUserIds = filteredUsers
        .filter(user => user.telegram_id)
        .map(user => user.telegram_id.toString());
      setLocalSelectedUsers(allUserIds);
    }, [filteredUsers]);

    // Снять выделение
    const handleDeselectAll = useCallback(() => {
      setLocalSelectedUsers([]);
    }, []);

    // Применить выбор пользователей (вызывается при нажатии "Применить")
    const handleApply = useCallback(() => {
      onSelectedUsersChange(localSelectedUsers);
      setSearchQuery('');
      onClose();
    }, [localSelectedUsers, onSelectedUsersChange, onClose]);

    return (
      <Modal isOpen={isOpen} onClose={handleCloseModal} size="xl">
        <ModalOverlay />
        <ModalContent maxH="80vh" bg={cardBg}>
          <ModalHeader>Выбор получателей</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Input
                placeholder="Поиск по имени, username, email или телефону..."
                value={searchQuery}
                onChange={handleSearchChange}
                mb={2}
              />

              <HStack spacing={2}>
                <Button
                  size="sm"
                  colorScheme="green"
                  variant="outline"
                  leftIcon={<Icon as={FiCheck} />}
                  onClick={handleSelectAll}
                >
                  Выбрать всех
                </Button>
                <Button
                  size="sm"
                  colorScheme="red"
                  variant="outline"
                  leftIcon={<Icon as={FiX} />}
                  onClick={handleDeselectAll}
                >
                  Снять выделение
                </Button>
              </HStack>

              <Box maxH="400px" overflowY="auto">
                <CheckboxGroup value={localSelectedUsers} onChange={setLocalSelectedUsers}>
                  <VStack align="stretch" spacing={2}>
                    {filteredUsers.map(user => (
                      <Checkbox
                        key={user.id}
                        value={user.telegram_id?.toString()}
                        isDisabled={!user.telegram_id}
                      >
                        <HStack spacing={3} flex={1}>
                          <Text fontWeight="medium">
                            {user.full_name || 'Без имени'}
                          </Text>
                          {user.username && (
                            <Badge colorScheme="blue">@{user.username}</Badge>
                          )}
                          {!user.telegram_id && (
                            <Badge colorScheme="red">Нет Telegram ID</Badge>
                          )}
                        </HStack>
                      </Checkbox>
                    ))}
                  </VStack>
                </CheckboxGroup>
              </Box>

              <Text fontSize="sm" color="gray.600">
                Выбрано: {localSelectedUsers.length} из {totalUsersWithTelegram} пользователей
              </Text>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={handleCloseModal}>
              Отмена
            </Button>
            <Button colorScheme="purple" onClick={handleApply}>
              Применить
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    );
  }, (prevProps, nextProps) => {
    // Кастомная функция сравнения для предотвращения лишних ре-рендеров
    // Возвращаем true если пропсы НЕ изменились (компонент НЕ должен ре-рендериться)
    // selectedUsers теперь НЕ проверяется, т.к. используется локальное состояние

    return (
      prevProps.isOpen === nextProps.isOpen &&
      prevProps.users === nextProps.users &&
      prevProps.totalUsersWithTelegram === nextProps.totalUsersWithTelegram &&
      prevProps.onClose === nextProps.onClose &&
      prevProps.onSelectedUsersChange === nextProps.onSelectedUsersChange
    );
  });

  // Получение цвета статуса
  const getStatusColor = (status) => {
    switch (status) {
      case 'success':
        return 'green';
      case 'failed':
        return 'red';
      case 'partial':
        return 'orange';
      default:
        return 'gray';
    }
  };

  // Получение иконки статуса
  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
        return FiCheck;
      case 'failed':
        return FiAlertCircle;
      case 'partial':
        return FiAlertCircle;
      default:
        return FiAlertCircle;
    }
  };

  // Получение текста статуса
  const getStatusText = (status) => {
    switch (status) {
      case 'success':
        return 'Успешно';
      case 'failed':
        return 'Ошибка';
      case 'partial':
        return 'Частично';
      default:
        return 'Неизвестно';
    }
  };

  return (
    <Box p={6} bg={bgColor} minH="calc(100vh - 64px)">
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <Box>
          <Heading size="lg" mb={2}>
            <Icon as={FiMail} color="purple.500" mr={3} />
            Рассылки
          </Heading>
          <Text color="gray.600">
            Управление массовыми рассылками в Telegram
          </Text>
        </Box>

        {/* Statistics Cards */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Всего рассылок</StatLabel>
                <StatNumber>{analyticsData.kpis.total}</StatNumber>
                <StatHelpText>
                  <Icon as={FiMail} mr={1} />
                  Отправлено
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Успешность</StatLabel>
                <StatNumber color="green.500">{analyticsData.kpis.successRate}%</StatNumber>
                <StatHelpText>
                  <Icon as={FiCheckCircle} mr={1} />
                  Успешных рассылок
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Получателей</StatLabel>
                <StatNumber color="blue.500">{analyticsData.kpis.totalRecipients}</StatNumber>
                <StatHelpText>
                  <Icon as={FiUsers} mr={1} />
                  Всего получили
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Средняя доставка</StatLabel>
                <StatNumber color="purple.500">{analyticsData.kpis.avgSuccessRate}%</StatNumber>
                <StatHelpText>
                  <Icon as={FiPercent} mr={1} />
                  По всем рассылкам
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        <Divider />

        {/* Форма отправки - показываем только если есть права */}
        {canSendNewsletters && (
          <Card bg={cardBg} borderRadius="lg" boxShadow="sm">
            <CardHeader 
              cursor="pointer"
              onClick={() => setIsNewNewsletterOpen(!isNewNewsletterOpen)}
              _hover={{ bg: useColorModeValue('gray.50', 'gray.700') }}
              transition="all 0.2s"
            >
              <HStack justify="space-between" align="center">
                <Heading size="md" color="purple.600">
                  <HStack>
                    <Icon as={FiSend} />
                    <Text>Новая рассылка</Text>
                  </HStack>
                </Heading>
                <Icon 
                  as={isNewNewsletterOpen ? FiChevronDown : FiChevronRight} 
                  color="gray.500"
                  transition="transform 0.2s"
                />
              </HStack>
            </CardHeader>
            <Collapse in={isNewNewsletterOpen} animateOpacity>
              <CardBody>
              <VStack spacing={4} align="stretch">
                {/* Выбор получателей */}
                <FormControl>
                  <FormLabel>Получатели</FormLabel>
                  <HStack spacing={3}>
                    <Select
                      value={recipientType}
                      onChange={(e) => setRecipientType(e.target.value)}
                      maxW="200px"
                    >
                      <option value="all">Все пользователи</option>
                      <option value="selected">Выбранные</option>
                    </Select>

                    {recipientType === 'selected' && (
                      <>
                        <Button
                          size="sm"
                          leftIcon={<FiUsers />}
                          onClick={() => setUserModalOpen(true)}
                          variant="outline"
                          colorScheme="purple"
                        >
                          Выбрать ({selectedUsers.length})
                        </Button>
                        {selectedUsers.length > 0 && (
                          <Button
                            size="sm"
                            variant="ghost"
                            colorScheme="red"
                            onClick={() => setSelectedUsers([])}
                          >
                            Очистить
                          </Button>
                        )}
                      </>
                    )}
                  </HStack>

                  <FormHelperText>
                    {recipientType === 'all' && `Будет отправлено всем ${totalUsersWithTelegram} пользователям`}
                    {recipientType === 'selected' && `Выбрано ${selectedUsers.length} получателей`}
                  </FormHelperText>
                </FormControl>

                {/* Сообщение с форматированием */}
                {/* Визуальный редактор сообщения с форматированием */}
                <TelegramEditor
                  label="Сообщение"
                  value={message}
                  onChange={setMessage}
                  placeholder="Введите текст сообщения... Используйте панель инструментов для форматирования"
                  maxLength={4096}
                  helperText="Форматирование отображается сразу. Telegram поддерживает: жирный, курсив, подчеркнутый, код, ссылки"
                  isInvalid={message.length > 4096}
                />

                {/* Загрузка фото */}
                <FormControl>
                  <FormLabel>Фотографии (до 10 штук)</FormLabel>
                  <VStack align="stretch" spacing={3}>
                    <Input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      multiple
                      onChange={handlePhotoUpload}
                      display="none"
                      id="photo-upload"
                    />
                    <Button
                      as="label"
                      htmlFor="photo-upload"
                      leftIcon={<FiImage />}
                      variant="outline"
                      cursor="pointer"
                      isDisabled={photos.length >= 10}
                      colorScheme="blue"
                    >
                      Добавить фото ({photos.length}/10)
                    </Button>

                    {photos.length > 0 && (
                      <SimpleGrid columns={5} spacing={2}>
                        {photos.map(photo => (
                          <Box key={photo.id} position="relative">
                            <Image
                              src={photo.preview}
                              alt="Preview"
                              boxSize="100px"
                              objectFit="cover"
                              borderRadius="md"
                              border="1px solid"
                              borderColor="gray.200"
                            />
                            <IconButton
                              icon={<FiX />}
                              size="xs"
                              position="absolute"
                              top={1}
                              right={1}
                              colorScheme="red"
                              onClick={() => removePhoto(photo.id)}
                            />
                          </Box>
                        ))}
                      </SimpleGrid>
                    )}
                  </VStack>
                </FormControl>

                {/* Предупреждение */}
                {message.includes('<') && (
                  <Alert status="info" borderRadius="md">
                    <AlertIcon />
                    <AlertDescription>
                      Убедитесь, что HTML-теги закрыты правильно для корректного отображения
                    </AlertDescription>
                  </Alert>
                )}

                {/* Кнопки отправки и предпросмотра */}
                <HStack spacing={3} width="full">
                  <Button
                    leftIcon={<FiEye />}
                    variant="outline"
                    colorScheme="blue"
                    size="lg"
                    onClick={() => setIsPreviewOpen(true)}
                    isDisabled={!message.trim() || isSending}
                    flex={1}
                  >
                    Предпросмотр
                  </Button>
                  <Button
                    leftIcon={<FiSend />}
                    colorScheme="purple"
                    size="lg"
                    onClick={handleSendNewsletter}
                    isLoading={isSending}
                    loadingText="Отправка..."
                    isDisabled={!message.trim() || isSending}
                    flex={2}
                  >
                    Отправить рассылку
                  </Button>
                </HStack>
              </VStack>
              </CardBody>
            </Collapse>
          </Card>
        )}

        {/* Аналитика рассылок */}
        <Card bg={cardBg} borderRadius="lg" boxShadow="sm" mb={6}>
          <CardHeader
            cursor="pointer"
            onClick={() => setIsAnalyticsOpen(!isAnalyticsOpen)}
            _hover={{ bg: useColorModeValue('gray.50', 'gray.700') }}
            transition="all 0.2s"
          >
            <HStack justify="space-between">
              <HStack>
                <Heading size="md" color="green.500">
                  <HStack>
                    <Icon as={FiBarChart2} />
                    <Text>Аналитика и статистика</Text>
                  </HStack>
                </Heading>
              </HStack>
              <Icon
                as={isAnalyticsOpen ? FiChevronDown : FiChevronRight}
                boxSize={6}
                color="gray.400"
              />
            </HStack>
          </CardHeader>
          <Collapse in={isAnalyticsOpen}>
            <CardBody>
              {newsletters.length === 0 ? (
                <Box textAlign="center" py={8}>
                  <Text color="gray.500">Нет данных для аналитики</Text>
                  <Text color="gray.400" fontSize="sm" mt={2}>
                    Отправьте несколько рассылок, чтобы увидеть статистику
                  </Text>
                </Box>
              ) : (
                <VStack spacing={6} align="stretch">
                  {/* KPI Карточки */}
                  <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
                    <Card bg={useColorModeValue('purple.50', 'purple.900')} boxShadow="sm">
                      <CardBody>
                        <VStack align="start" spacing={1}>
                          <Text fontSize="sm" color={useColorModeValue('purple.600', 'purple.300')}>
                            Всего рассылок
                          </Text>
                          <Heading size="xl" color={useColorModeValue('purple.700', 'purple.200')}>
                            {analyticsData.kpis.total}
                          </Heading>
                        </VStack>
                      </CardBody>
                    </Card>

                    <Card bg={useColorModeValue('green.50', 'green.900')} boxShadow="sm">
                      <CardBody>
                        <VStack align="start" spacing={1}>
                          <Text fontSize="sm" color={useColorModeValue('green.600', 'green.300')}>
                            Процент успеха
                          </Text>
                          <Heading size="xl" color={useColorModeValue('green.700', 'green.200')}>
                            {analyticsData.kpis.successRate}%
                          </Heading>
                        </VStack>
                      </CardBody>
                    </Card>

                    <Card bg={useColorModeValue('blue.50', 'blue.900')} boxShadow="sm">
                      <CardBody>
                        <VStack align="start" spacing={1}>
                          <Text fontSize="sm" color={useColorModeValue('blue.600', 'blue.300')}>
                            Всего получателей
                          </Text>
                          <Heading size="xl" color={useColorModeValue('blue.700', 'blue.200')}>
                            {analyticsData.kpis.totalRecipients}
                          </Heading>
                        </VStack>
                      </CardBody>
                    </Card>

                    <Card bg={useColorModeValue('orange.50', 'orange.900')} boxShadow="sm">
                      <CardBody>
                        <VStack align="start" spacing={1}>
                          <Text fontSize="sm" color={useColorModeValue('orange.600', 'orange.300')}>
                            Средняя доставка
                          </Text>
                          <Heading size="xl" color={useColorModeValue('orange.700', 'orange.200')}>
                            {analyticsData.kpis.avgSuccessRate}%
                          </Heading>
                        </VStack>
                      </CardBody>
                    </Card>
                  </SimpleGrid>

                  {/* Графики */}
                  <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
                    {/* Pie Chart - Распределение по статусам */}
                    <Card boxShadow="sm">
                      <CardHeader>
                        <Heading size="sm">Распределение по статусам</Heading>
                      </CardHeader>
                      <CardBody>
                        <ResponsiveContainer width="100%" height={250}>
                          <PieChart>
                            <Pie
                              data={analyticsData.statusDistribution}
                              cx="50%"
                              cy="50%"
                              labelLine={false}
                              label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                              outerRadius={80}
                              fill="#8884d8"
                              dataKey="value"
                            >
                              {analyticsData.statusDistribution.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.color} />
                              ))}
                            </Pie>
                            <RechartsTooltip />
                          </PieChart>
                        </ResponsiveContainer>
                      </CardBody>
                    </Card>

                    {/* Bar Chart - Количество рассылок по дням */}
                    <Card boxShadow="sm">
                      <CardHeader>
                        <Heading size="sm">Рассылок по дням (последние 14)</Heading>
                      </CardHeader>
                      <CardBody>
                        <ResponsiveContainer width="100%" height={250}>
                          <BarChart data={analyticsData.newslettersByDate}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="date" angle={-45} textAnchor="end" height={80} />
                            <YAxis />
                            <RechartsTooltip />
                            <Bar dataKey="count" fill="#805AD5" name="Количество" />
                          </BarChart>
                        </ResponsiveContainer>
                      </CardBody>
                    </Card>

                    {/* Line Chart - Успешность по времени */}
                    <Card boxShadow="sm">
                      <CardHeader>
                        <Heading size="sm">Процент успеха (последние 30)</Heading>
                      </CardHeader>
                      <CardBody>
                        <ResponsiveContainer width="100%" height={250}>
                          <LineChart data={analyticsData.successRateOverTime}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} />
                            <YAxis />
                            <RechartsTooltip />
                            <Legend />
                            <Line type="monotone" dataKey="Процент успеха" stroke="#48BB78" strokeWidth={2} />
                          </LineChart>
                        </ResponsiveContainer>
                      </CardBody>
                    </Card>

                    {/* Line Chart - Количество отправленных */}
                    <Card boxShadow="sm">
                      <CardHeader>
                        <Heading size="sm">Отправлено сообщений (последние 30)</Heading>
                      </CardHeader>
                      <CardBody>
                        <ResponsiveContainer width="100%" height={250}>
                          <LineChart data={analyticsData.successRateOverTime}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} />
                            <YAxis />
                            <RechartsTooltip />
                            <Legend />
                            <Line type="monotone" dataKey="Отправлено" stroke="#3182CE" strokeWidth={2} />
                          </LineChart>
                        </ResponsiveContainer>
                      </CardBody>
                    </Card>
                  </SimpleGrid>
                </VStack>
              )}
            </CardBody>
          </Collapse>
        </Card>

        {/* История рассылок */}
        <Card bg={cardBg} borderRadius="lg" boxShadow="sm">
          <CardHeader 
            cursor="pointer"
            onClick={() => setIsHistoryOpen(!isHistoryOpen)}
            _hover={{ bg: useColorModeValue('gray.50', 'gray.700') }}
            transition="all 0.2s"
          >
            <HStack justify="space-between">
              <HStack>
                <Heading size="md" color="blue.500">
                  <HStack>
                    <Icon as={FiUsers} />
                    <Text>История рассылок</Text>
                  </HStack>
                </Heading>
                <Icon 
                  as={isHistoryOpen ? FiChevronDown : FiChevronRight} 
                  color="gray.500"
                  transition="transform 0.2s"
                />
              </HStack>
              <HStack spacing={2} onClick={(e) => e.stopPropagation()}>
                <IconButton
                  icon={<FiRefreshCw />}
                  size="sm"
                  variant="ghost"
                  onClick={fetchNewsletters}
                  isLoading={isLoading}
                  colorScheme="blue"
                  aria-label="Обновить"
                />
                {newsletters.length > 0 && (
                  <Button
                    leftIcon={<FiDownload />}
                    size="sm"
                    variant="outline"
                    colorScheme="green"
                    onClick={handleExportCSV}
                  >
                    Экспорт CSV
                  </Button>
                )}
                {canManageNewsletters && newsletters.length > 0 && (
                  <Button
                    leftIcon={<FiTrash />}
                    size="sm"
                    variant="outline"
                    colorScheme="red"
                    onClick={handleClearHistory}
                  >
                    Очистить историю
                  </Button>
                )}
              </HStack>
            </HStack>
          </CardHeader>
          <Collapse in={isHistoryOpen} animateOpacity>
            <CardBody>
            {/* Фильтры */}
            <VStack spacing={4} mb={6} align="stretch">
              <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
                <FormControl>
                  <FormLabel fontSize="sm">Статус</FormLabel>
                  <Select
                    size="sm"
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    placeholder="Все статусы"
                  >
                    <option value="success">Успешно</option>
                    <option value="partial">Частично</option>
                    <option value="failed">Ошибка</option>
                  </Select>
                </FormControl>

                <FormControl>
                  <FormLabel fontSize="sm">Тип получателей</FormLabel>
                  <Select
                    size="sm"
                    value={filterRecipientType}
                    onChange={(e) => setFilterRecipientType(e.target.value)}
                    placeholder="Все типы"
                  >
                    <option value="all">Все пользователи</option>
                    <option value="selected">Выбранные</option>
                  </Select>
                </FormControl>

                <FormControl>
                  <FormLabel fontSize="sm">Поиск по тексту</FormLabel>
                  <Input
                    size="sm"
                    placeholder="Введите текст..."
                    value={filterSearch}
                    onChange={(e) => setFilterSearch(e.target.value)}
                  />
                </FormControl>
              </SimpleGrid>

              {/* Кнопка сброса фильтров */}
              {(filterStatus || filterRecipientType || filterSearch) && (
                <Button
                  size="sm"
                  variant="ghost"
                  colorScheme="gray"
                  onClick={() => {
                    setFilterStatus('');
                    setFilterRecipientType('');
                    setFilterSearch('');
                  }}
                  alignSelf="flex-start"
                >
                  Сбросить фильтры
                </Button>
              )}
            </VStack>

            <Divider mb={4} />

            {isLoading ? (
              <Box textAlign="center" py={8}>
                <Spinner size="lg" color="purple.500" />
                <Text mt={4} color="gray.500">Загрузка истории рассылок...</Text>
              </Box>
            ) : newsletters.length === 0 ? (
              <Box textAlign="center" py={8}>
                <Text color="gray.500" fontSize="lg">История рассылок пуста</Text>
                {canSendNewsletters && (
                  <Text color="gray.400" fontSize="sm" mt={2}>
                    Отправьте первую рассылку, чтобы увидеть её здесь
                  </Text>
                )}
              </Box>
            ) : (
              <TableContainer>
                <Table variant="simple" size="sm">
                  <Thead>
                    <Tr>
                      <Th>Дата отправки</Th>
                      <Th>Статус</Th>
                      <Th>Получатели</Th>
                      <Th>Сообщение</Th>
                      <Th>Фото</Th>
                      <Th>Действия</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {newsletters.map(newsletter => (
                      <Tr key={newsletter.id}>
                        <Td>
                          <Text fontSize="sm">
                            {new Date(newsletter.created_at).toLocaleString('ru-RU')}
                          </Text>
                        </Td>
                        <Td>
                          <Badge colorScheme={getStatusColor(newsletter.status)}>
                            <HStack spacing={1}>
                              <Icon as={getStatusIcon(newsletter.status)} />
                              <Text>{getStatusText(newsletter.status)}</Text>
                            </HStack>
                          </Badge>
                        </Td>
                        <Td>
                          <VStack align="start" spacing={1}>
                            <Text fontSize="sm" fontWeight="medium">
                              {newsletter.success_count}/{newsletter.total_count}
                            </Text>
                            <HStack spacing={1}>
                              {newsletter.recipient_type === 'all' && (
                                <Badge size="xs" colorScheme="purple">Все</Badge>
                              )}
                              {newsletter.recipient_type === 'selected' && (
                                <Badge size="xs" colorScheme="blue">Выбранные</Badge>
                              )}
                            </HStack>
                          </VStack>
                        </Td>
                        <Td maxW="300px">
                          <Tooltip label={newsletter.message} hasArrow>
                            <Text fontSize="sm" noOfLines={2}>
                              {newsletter.message}
                            </Text>
                          </Tooltip>
                        </Td>
                        <Td>
                          {newsletter.photo_count > 0 && (
                            <Badge colorScheme="blue">
                              <HStack spacing={1}>
                                <Icon as={FiImage} />
                                <Text>{newsletter.photo_count}</Text>
                              </HStack>
                            </Badge>
                          )}
                        </Td>
                        <Td>
                          <HStack spacing={1}>
                            <Tooltip label="Подробная статистика">
                              <IconButton
                                icon={<FiBarChart2 />}
                                size="sm"
                                variant="ghost"
                                colorScheme="blue"
                                onClick={() => handleOpenStats(newsletter)}
                                aria-label="Просмотр статистики"
                              />
                            </Tooltip>
                            {canManageNewsletters && (
                              <Tooltip label="Удалить рассылку">
                                <IconButton
                                  icon={<FiTrash2 />}
                                  size="sm"
                                  variant="ghost"
                                  colorScheme="red"
                                  onClick={() => handleDeleteNewsletter(newsletter)}
                                  aria-label="Удалить рассылку"
                                />
                              </Tooltip>
                            )}
                          </HStack>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </TableContainer>
            )}
            </CardBody>
          </Collapse>
        </Card>
      </VStack>

      {/* Модальное окно выбора пользователей */}
      {canSendNewsletters && (
        <UserSelectionModal
          isOpen={isUserModalOpen}
          onClose={handleCloseUserModal}
          users={users}
          selectedUsers={selectedUsers}
          onSelectedUsersChange={handleSelectedUsersChange}
          totalUsersWithTelegram={totalUsersWithTelegram}
        />
      )}

      {/* Диалог подтверждения удаления рассылки */}
      <AlertDialog
        isOpen={isDeleteOpen}
        leastDestructiveRef={cancelRef}
        onClose={onDeleteClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Удалить рассылку
            </AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите удалить эту рассылку?
              <Box mt={2} p={3} bg="gray.50" borderRadius="md">
                <Text fontSize="sm" fontWeight="medium">
                  {deleteTarget?.message.substring(0, 100)}
                  {deleteTarget?.message.length > 100 ? '...' : ''}
                </Text>
                <Text fontSize="xs" color="gray.500" mt={1}>
                  Отправлено: {deleteTarget && new Date(deleteTarget.created_at).toLocaleString('ru-RU')}
                </Text>
              </Box>
              <Text mt={2} color="red.500" fontSize="sm">
                Это действие нельзя отменить.
              </Text>
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteClose}>
                Отмена
              </Button>
              <Button
                colorScheme="red"
                onClick={confirmDeleteNewsletter}
                ml={3}
                isLoading={isDeleting}
                loadingText="Удаление..."
              >
                Удалить
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      {/* Диалог подтверждения очистки истории */}
      <AlertDialog
        isOpen={isClearOpen}
        leastDestructiveRef={cancelRef}
        onClose={onClearClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Очистить всю историю рассылок
            </AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите удалить <strong>все рассылки</strong> из истории?
              <Box mt={2} p={3} bg="red.50" borderRadius="md" borderLeft="4px solid" borderColor="red.400">
                <Text fontSize="sm" color="red.700">
                  ⚠️ Будет удалено {newsletters.length} рассылок
                </Text>
                <Text fontSize="xs" color="red.600" mt={1}>
                  Это действие нельзя отменить!
                </Text>
              </Box>
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onClearClose}>
                Отмена
              </Button>
              <Button
                colorScheme="red"
                onClick={confirmClearHistory}
                ml={3}
                isLoading={isDeleting}
                loadingText="Очистка..."
              >
                Очистить всё
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      {/* Модальное окно детальной статистики */}
      <Modal isOpen={isStatsModalOpen} onClose={handleCloseStats} size="xl">
        <ModalOverlay />
        <ModalContent maxH="90vh" bg={cardBg}>
          <ModalHeader>
            <HStack>
              <Icon as={FiBarChart2} color="blue.500" />
              <Text>Детальная статистика рассылки</Text>
            </HStack>
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody overflowY="auto">
            {selectedNewsletter && (
              <VStack spacing={4} align="stretch">
                {/* Общая информация */}
                <Box p={4} bg={useColorModeValue('gray.50', 'gray.700')} borderRadius="md">
                  <Text fontSize="sm" fontWeight="bold" mb={2} color="gray.600">
                    Общая информация
                  </Text>
                  <SimpleGrid columns={2} spacing={3}>
                    <Box>
                      <Text fontSize="xs" color="gray.500">Дата отправки</Text>
                      <Text fontSize="sm" fontWeight="medium">
                        {new Date(selectedNewsletter.created_at).toLocaleString('ru-RU')}
                      </Text>
                    </Box>
                    <Box>
                      <Text fontSize="xs" color="gray.500">Статус</Text>
                      <Badge colorScheme={getStatusColor(selectedNewsletter.status)} mt={1}>
                        <HStack spacing={1}>
                          <Icon as={getStatusIcon(selectedNewsletter.status)} />
                          <Text>{getStatusText(selectedNewsletter.status)}</Text>
                        </HStack>
                      </Badge>
                    </Box>
                  </SimpleGrid>
                </Box>

                {/* Статистика доставки */}
                <Box p={4} bg={useColorModeValue('blue.50', 'blue.900')} borderRadius="md">
                  <Text fontSize="sm" fontWeight="bold" mb={3} color="blue.700">
                    Статистика доставки
                  </Text>
                  <SimpleGrid columns={3} spacing={3}>
                    <Box textAlign="center">
                      <Text fontSize="2xl" fontWeight="bold" color="blue.600">
                        {selectedNewsletter.total_count}
                      </Text>
                      <Text fontSize="xs" color="gray.600">Всего получателей</Text>
                    </Box>
                    <Box textAlign="center">
                      <Text fontSize="2xl" fontWeight="bold" color="green.600">
                        {selectedNewsletter.success_count}
                      </Text>
                      <Text fontSize="xs" color="gray.600">Доставлено</Text>
                    </Box>
                    <Box textAlign="center">
                      <Text fontSize="2xl" fontWeight="bold" color="red.600">
                        {selectedNewsletter.total_count - selectedNewsletter.success_count}
                      </Text>
                      <Text fontSize="xs" color="gray.600">Не доставлено</Text>
                    </Box>
                  </SimpleGrid>

                  {/* Процент успеха */}
                  <Box mt={4}>
                    <HStack justify="space-between" mb={1}>
                      <Text fontSize="xs" color="gray.600">Процент успешной доставки</Text>
                      <Text fontSize="sm" fontWeight="bold" color="green.600">
                        {((selectedNewsletter.success_count / selectedNewsletter.total_count) * 100).toFixed(1)}%
                      </Text>
                    </HStack>
                    <Box w="full" bg="gray.200" borderRadius="full" h="8px">
                      <Box
                        w={`${(selectedNewsletter.success_count / selectedNewsletter.total_count) * 100}%`}
                        bg="green.500"
                        borderRadius="full"
                        h="8px"
                        transition="width 0.3s"
                      />
                    </Box>
                  </Box>
                </Box>

                {/* Информация о получателях */}
                <Box p={4} bg={useColorModeValue('purple.50', 'purple.900')} borderRadius="md">
                  <Text fontSize="sm" fontWeight="bold" mb={2} color="purple.700">
                    Информация о получателях
                  </Text>
                  <VStack align="stretch" spacing={2}>
                    <HStack justify="space-between">
                      <Text fontSize="sm" color="gray.600">Тип получателей:</Text>
                      <Badge colorScheme="purple">
                        {selectedNewsletter.recipient_type === 'all' && 'Все пользователи'}
                        {selectedNewsletter.recipient_type === 'selected' && 'Выбранные пользователи'}
                      </Badge>
                    </HStack>

                    {selectedNewsletter.photo_count > 0 && (
                      <HStack justify="space-between">
                        <Text fontSize="sm" color="gray.600">Фотографий:</Text>
                        <Badge colorScheme="blue">
                          <HStack spacing={1}>
                            <Icon as={FiImage} />
                            <Text>{selectedNewsletter.photo_count}</Text>
                          </HStack>
                        </Badge>
                      </HStack>
                    )}
                  </VStack>
                </Box>

                {/* Текст сообщения */}
                <Box p={4} bg={useColorModeValue('gray.50', 'gray.700')} borderRadius="md">
                  <Text fontSize="sm" fontWeight="bold" mb={2} color="gray.600">
                    Текст сообщения
                  </Text>
                  <Box
                    p={3}
                    bg={useColorModeValue('white', 'gray.800')}
                    borderRadius="md"
                    border="1px solid"
                    borderColor={useColorModeValue('gray.200', 'gray.600')}
                    maxH="300px"
                    overflowY="auto"
                  >
                    <Text
                      fontSize="sm"
                      whiteSpace="pre-wrap"
                      dangerouslySetInnerHTML={{ __html: selectedNewsletter.message }}
                    />
                  </Box>
                  <Text fontSize="xs" color="gray.500" mt={2}>
                    Длина: {selectedNewsletter.message.length} символов
                  </Text>
                </Box>

                {/* Детальная информация о получателях */}
                <Box p={4} bg={useColorModeValue('orange.50', 'orange.900')} borderRadius="md">
                  <HStack justify="space-between" mb={3}>
                    <Text fontSize="sm" fontWeight="bold" color="orange.700">
                      Детальная информация о получателях
                    </Text>
                    {isLoadingRecipients && (
                      <Spinner size="sm" color="orange.500" />
                    )}
                  </HStack>

                  {isLoadingRecipients ? (
                    <Box textAlign="center" py={4}>
                      <Spinner color="orange.500" />
                      <Text mt={2} fontSize="sm" color="gray.600">
                        Загрузка списка получателей...
                      </Text>
                    </Box>
                  ) : recipientDetails && recipientDetails.recipients ? (
                    <Box>
                      <Text fontSize="xs" color="gray.600" mb={2}>
                        Всего получателей: {recipientDetails.total_count}
                      </Text>

                      {/* Таблица получателей */}
                      <TableContainer maxH="300px" overflowY="auto">
                        <Table size="sm" variant="simple">
                          <Thead position="sticky" top={0} bg={useColorModeValue('white', 'gray.800')} zIndex={1}>
                            <Tr>
                              <Th>Получатель</Th>
                              <Th>Telegram ID</Th>
                              <Th>Статус</Th>
                              <Th>Ошибка</Th>
                            </Tr>
                          </Thead>
                          <Tbody>
                            {recipientDetails.recipients.map((recipient, idx) => (
                              <Tr key={recipient.id || idx}>
                                <Td>{recipient.full_name || 'Неизвестно'}</Td>
                                <Td>
                                  <code style={{ fontSize: '0.85em' }}>{recipient.telegram_id}</code>
                                </Td>
                                <Td>
                                  <Badge
                                    colorScheme={recipient.status === 'success' ? 'green' : 'red'}
                                    fontSize="xs"
                                  >
                                    <HStack spacing={1}>
                                      <Icon as={recipient.status === 'success' ? FiCheck : FiX} />
                                      <Text>{recipient.status === 'success' ? 'Доставлено' : 'Ошибка'}</Text>
                                    </HStack>
                                  </Badge>
                                </Td>
                                <Td>
                                  {recipient.error_message ? (
                                    <Tooltip label={recipient.error_message} placement="top">
                                      <Text fontSize="xs" color="red.600" isTruncated maxW="200px">
                                        {recipient.error_message}
                                      </Text>
                                    </Tooltip>
                                  ) : (
                                    <Text fontSize="xs" color="gray.500">—</Text>
                                  )}
                                </Td>
                              </Tr>
                            ))}
                          </Tbody>
                        </Table>
                      </TableContainer>

                      {/* Сводка по статусам */}
                      <HStack mt={3} spacing={4} justify="center">
                        <HStack spacing={1}>
                          <Icon as={FiCheck} color="green.500" />
                          <Text fontSize="xs" color="gray.600">
                            Успешно: {recipientDetails.recipients.filter(r => r.status === 'success').length}
                          </Text>
                        </HStack>
                        <HStack spacing={1}>
                          <Icon as={FiX} color="red.500" />
                          <Text fontSize="xs" color="gray.600">
                            Ошибки: {recipientDetails.recipients.filter(r => r.status === 'failed').length}
                          </Text>
                        </HStack>
                      </HStack>
                    </Box>
                  ) : (
                    <Text fontSize="sm" color="gray.500" textAlign="center">
                      Нет данных о получателях
                    </Text>
                  )}
                </Box>
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button onClick={handleCloseStats}>
              Закрыть
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Модальное окно предпросмотра */}
      <Modal isOpen={isPreviewOpen} onClose={() => setIsPreviewOpen(false)} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Предпросмотр сообщения</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack align="stretch" spacing={4}>
              {/* Предпросмотр текста с HTML форматированием */}
              <Box
                p={4}
                bg={useColorModeValue('gray.50', 'gray.700')}
                borderRadius="md"
                border="1px solid"
                borderColor={useColorModeValue('gray.200', 'gray.600')}
              >
                <Text fontWeight="bold" mb={2} fontSize="sm" color="gray.500">
                  Как увидят пользователи:
                </Text>
                <Box
                  dangerouslySetInnerHTML={{ __html: message }}
                  sx={{
                    '& b': { fontWeight: 'bold' },
                    '& i': { fontStyle: 'italic' },
                    '& u': { textDecoration: 'underline' },
                    '& code': {
                      fontFamily: 'monospace',
                      bg: useColorModeValue('gray.200', 'gray.600'),
                      px: 1,
                      borderRadius: 'sm'
                    },
                    '& a': { color: 'blue.500', textDecoration: 'underline' }
                  }}
                />
              </Box>

              {/* Предпросмотр фото */}
              {photos.length > 0 && (
                <Box>
                  <Text fontWeight="bold" mb={2} fontSize="sm" color="gray.500">
                    Фотографии ({photos.length}):
                  </Text>
                  <SimpleGrid columns={3} spacing={2}>
                    {photos.map(photo => (
                      <Image
                        key={photo.id}
                        src={photo.preview}
                        alt="Preview"
                        boxSize="120px"
                        objectFit="cover"
                        borderRadius="md"
                        border="1px solid"
                        borderColor="gray.200"
                      />
                    ))}
                  </SimpleGrid>
                </Box>
              )}

              {/* Информация о получателях */}
              <Box
                p={3}
                bg={useColorModeValue('blue.50', 'blue.900')}
                borderRadius="md"
              >
                <HStack justify="space-between">
                  <Text fontWeight="bold" fontSize="sm">
                    Получатели:
                  </Text>
                  <Badge colorScheme="blue">
                    {recipientType === 'all'
                      ? 'Все пользователи'
                      : `Выбрано: ${selectedUsers.length}`}
                  </Badge>
                </HStack>
              </Box>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={() => setIsPreviewOpen(false)}>
              Закрыть
            </Button>
            <Button
              colorScheme="purple"
              leftIcon={<FiSend />}
              onClick={() => {
                setIsPreviewOpen(false);
                handleSendNewsletter();
              }}
              isDisabled={!message.trim()}
            >
              Отправить сейчас
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default Newsletters;