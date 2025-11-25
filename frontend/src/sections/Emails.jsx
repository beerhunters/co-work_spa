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
  Button,
  FormControl,
  FormLabel,
  FormHelperText,
  Input,
  Textarea,
  Select,
  Badge,
  useToast,
  Divider,
  SimpleGrid,
  Spinner,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Tooltip,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  useDisclosure,
  Collapse,
  IconButton,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  useColorModeValue,
  useBreakpointValue,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Checkbox,
  CheckboxGroup,
  Stack,
} from '@chakra-ui/react';
import {
  FiMail,
  FiSend,
  FiClock,
  FiEye,
  FiMousePointer,
  FiChevronDown,
  FiChevronRight,
  FiEdit,
  FiTrash2,
  FiBarChart2,
  FiUsers,
} from 'react-icons/fi';
import EmailEditor from '../components/EmailEditor';
import api from '../utils/api';

const Emails = ({ currentAdmin }) => {
  const [campaigns, setCampaigns] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [users, setUsers] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);

  // Форма создания кампании
  const [campaignName, setCampaignName] = useState('');
  const [subject, setSubject] = useState('');
  const [htmlContent, setHtmlContent] = useState('');
  const [unlayerDesign, setUnlayerDesign] = useState('');
  const [recipientType, setRecipientType] = useState('all');
  const [selectedUserIds, setSelectedUserIds] = useState([]);
  const [segmentType, setSegmentType] = useState('active');
  const [customEmails, setCustomEmails] = useState('');

  // Раскрытие секций
  const [isNewCampaignOpen, setIsNewCampaignOpen] = useState(true);
  const [isCampaignsListOpen, setIsCampaignsListOpen] = useState(true);

  // Модалки
  const { isOpen: isStatsOpen, onOpen: onStatsOpen, onClose: onStatsClose } = useDisclosure();
  const { isOpen: isTestEmailOpen, onOpen: onTestEmailOpen, onClose: onTestEmailClose } = useDisclosure();
  const { isOpen: isUserModalOpen, onOpen: onUserModalOpen, onClose: onUserModalClose } = useDisclosure();
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [campaignAnalytics, setCampaignAnalytics] = useState(null);
  const [testEmail, setTestEmail] = useState('');

  const toast = useToast();
  const bgColor = useColorModeValue('gray.50', 'gray.900');
  const cardBg = useColorModeValue('white', 'gray.800');

  // Responsive breakpoint для адаптивного отображения
  const isMobile = useBreakpointValue({ base: true, md: false });

  useEffect(() => {
    fetchCampaigns();
    fetchTemplates();
    fetchUsers();
  }, []);

  const fetchCampaigns = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/emails', {
        params: { limit: 100, offset: 0 }
      });
      setCampaigns(response.data.items || []);
    } catch (error) {
      console.error('Error fetching campaigns:', error);
      toast({
        title: 'Ошибка загрузки кампаний',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const fetchTemplates = async () => {
    try {
      const response = await api.get('/emails/templates');
      setTemplates(response.data || []);
    } catch (error) {
      console.error('Error fetching templates:', error);
    }
  };

  const fetchUsers = async () => {
    try {
      const response = await api.get('/users', {
        params: { page: 1, per_page: 1000 }
      });
      setUsers(response.data || []);
    } catch (error) {
      console.error('Error fetching users:', error);
    }
  };

  const handleEditorSave = (data) => {
    setUnlayerDesign(data.design);
    setHtmlContent(data.html);
    toast({
      title: 'Дизайн сохранен',
      description: 'Email дизайн успешно сохранен',
      status: 'success',
      duration: 2000,
    });
  };

  const handleCreateCampaign = async () => {
    try {
      if (!campaignName || !subject || !htmlContent) {
        toast({
          title: 'Заполните все поля',
          description: 'Название, тема и контент обязательны',
          status: 'warning',
          duration: 3000,
        });
        return;
      }

      setIsSending(true);

      // Обработка custom emails - разделяем по запятым/пробелам и очищаем
      const customEmailsList = recipientType === 'custom' && customEmails
        ? customEmails.split(/[,\s]+/).filter(email => email.trim())
        : null;

      const payload = {
        name: campaignName,
        subject: subject,
        html_content: htmlContent,
        unlayer_design: unlayerDesign || null,
        recipient_type: recipientType,
        recipient_ids: recipientType === 'selected' ? selectedUserIds : null,
        segment_type: recipientType === 'segment' ? segmentType : null,
        segment_params: null,
        custom_emails: customEmailsList,
        is_ab_test: false,
        ab_test_percentage: null,
        ab_variant_b_subject: null,
        ab_variant_b_content: null,
      };

      const response = await api.post('/emails', payload);

      toast({
        title: 'Кампания создана',
        description: `Кампания "${campaignName}" успешно создана`,
        status: 'success',
        duration: 3000,
      });

      // Очистка формы
      setCampaignName('');
      setSubject('');
      setHtmlContent('');
      setUnlayerDesign('');
      setSelectedUserIds([]);

      fetchCampaigns();
    } catch (error) {
      console.error('Error creating campaign:', error);
      toast({
        title: 'Ошибка создания кампании',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsSending(false);
    }
  };

  const handleSendCampaign = async (campaignId) => {
    try {
      setIsSending(true);

      const payload = {
        send_now: true,
        scheduled_at: null,
      };

      const response = await api.post(`/emails/${campaignId}/send`, payload);

      toast({
        title: 'Отправка запущена',
        description: response.data.message || 'Кампания отправляется',
        status: 'success',
        duration: 5000,
      });

      fetchCampaigns();
    } catch (error) {
      console.error('Error sending campaign:', error);
      toast({
        title: 'Ошибка отправки',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsSending(false);
    }
  };

  const handleShowAnalytics = async (campaign) => {
    try {
      setSelectedCampaign(campaign);
      setCampaignAnalytics(null);
      onStatsOpen();

      const response = await api.get(`/emails/${campaign.id}/analytics`);
      setCampaignAnalytics(response.data);
    } catch (error) {
      console.error('Error fetching analytics:', error);
      toast({
        title: 'Ошибка загрузки аналитики',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleSendTestEmail = async () => {
    if (!selectedCampaign || !testEmail) {
      toast({
        title: 'Укажите email',
        description: 'Введите email для тестовой отправки',
        status: 'warning',
        duration: 3000,
      });
      return;
    }

    try {
      setIsSending(true);

      await api.post(`/emails/${selectedCampaign.id}/test`, {
        test_email: testEmail,
      });

      toast({
        title: 'Тестовое письмо отправлено',
        description: `Письмо отправлено на ${testEmail}`,
        status: 'success',
        duration: 3000,
      });

      onTestEmailClose();
      setTestEmail('');
    } catch (error) {
      console.error('Error sending test email:', error);
      toast({
        title: 'Ошибка отправки',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsSending(false);
    }
  };

  const handleDeleteCampaign = async (campaignId) => {
    if (!window.confirm('Вы уверены, что хотите удалить эту кампанию?')) {
      return;
    }

    try {
      await api.delete(`/emails/${campaignId}`);

      toast({
        title: 'Кампания удалена',
        status: 'success',
        duration: 2000,
      });

      fetchCampaigns();
    } catch (error) {
      console.error('Error deleting campaign:', error);
      toast({
        title: 'Ошибка удаления',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleClearHistory = async () => {
    const sentCount = campaigns.filter(c => c.status === 'sent' || c.status === 'failed').length;

    if (sentCount === 0) {
      toast({
        title: 'Нет кампаний для удаления',
        description: 'История уже пуста',
        status: 'info',
        duration: 3000,
      });
      return;
    }

    if (!window.confirm(`Вы уверены, что хотите очистить историю?\n\nБудет удалено кампаний: ${sentCount}\n(отправленные и провалившиеся)`)) {
      return;
    }

    try {
      setIsLoading(true);
      const response = await api.post('/emails/clear-history');

      toast({
        title: 'История очищена',
        description: response.data.message,
        status: 'success',
        duration: 3000,
      });

      fetchCampaigns();
    } catch (error) {
      console.error('Error clearing history:', error);
      toast({
        title: 'Ошибка очистки истории',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'draft':
        return 'gray';
      case 'scheduled':
        return 'blue';
      case 'sending':
        return 'orange';
      case 'sent':
        return 'green';
      case 'failed':
        return 'red';
      default:
        return 'gray';
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'draft':
        return 'Черновик';
      case 'scheduled':
        return 'Запланировано';
      case 'sending':
        return 'Отправляется';
      case 'sent':
        return 'Отправлено';
      case 'failed':
        return 'Ошибка';
      default:
        return status;
    }
  };

  const usersWithEmail = useMemo(() => users.filter(u => u.email), [users]);

  const handleSelectedUsersChange = useCallback((newSelectedUserIds) => {
    setSelectedUserIds(newSelectedUserIds);
  }, []);

  // Компонент модального окна для выбора пользователей
  const UserSelectionModal = React.memo(({
    isOpen,
    onClose,
    users,
    selectedUserIds,
    onSelectedUserIdsChange,
    totalUsersWithEmail
  }) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [localSelectedUserIds, setLocalSelectedUserIds] = useState(selectedUserIds);

    // Синхронизация локального состояния с родительским при открытии модалки
    useEffect(() => {
      if (isOpen) {
        setLocalSelectedUserIds(selectedUserIds);
      }
    }, [isOpen, selectedUserIds]);

    // Фильтрация пользователей по поисковому запросу
    const filteredUsers = useMemo(() => {
      if (!searchQuery.trim()) return users;
      const query = searchQuery.toLowerCase();
      return users.filter(user =>
        user.full_name?.toLowerCase().includes(query) ||
        user.username?.toLowerCase().includes(query) ||
        user.email?.toLowerCase().includes(query)
      );
    }, [users, searchQuery]);

    // Выбрать всех отфильтрованных пользователей
    const handleSelectAll = useCallback(() => {
      const allUserIds = filteredUsers
        .filter(user => user.email)
        .map(user => user.id.toString());
      setLocalSelectedUserIds(allUserIds);
    }, [filteredUsers]);

    // Снять выделение со всех
    const handleDeselectAll = useCallback(() => {
      setLocalSelectedUserIds([]);
    }, []);

    // Применить выбор (обновить родительский компонент)
    const handleApply = useCallback(() => {
      // Преобразуем строки обратно в числа для selectedUserIds
      const userIdsAsNumbers = localSelectedUserIds.map(id => parseInt(id));
      onSelectedUserIdsChange(userIdsAsNumbers);
      setSearchQuery('');
      onClose();
    }, [localSelectedUserIds, onSelectedUserIdsChange, onClose]);

    return (
      <Modal isOpen={isOpen} onClose={onClose} size={{ base: "full", md: "xl" }}>
        <ModalOverlay />
        <ModalContent maxH="80vh">
          <ModalHeader>Выбор получателей</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack align="stretch" spacing={4}>
              <Input
                placeholder="Поиск по имени, username или email..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <HStack>
                <Button onClick={handleSelectAll} size="sm">
                  Выбрать всех
                </Button>
                <Button onClick={handleDeselectAll} size="sm">
                  Снять выделение
                </Button>
              </HStack>
              <Box maxH="400px" overflowY="auto" border="1px" borderColor="gray.200" borderRadius="md" p={2}>
                <CheckboxGroup value={localSelectedUserIds} onChange={setLocalSelectedUserIds}>
                  <VStack align="stretch" spacing={2}>
                    {filteredUsers.length === 0 ? (
                      <Text color="gray.500" textAlign="center" py={4}>
                        Пользователи не найдены
                      </Text>
                    ) : (
                      filteredUsers.map(user => (
                        <Checkbox
                          key={user.id}
                          value={user.id.toString()}
                          isDisabled={!user.email}
                        >
                          <VStack align="start" spacing={0} maxW="100%">
                            <Text fontWeight="medium" isTruncated maxW="100%">
                              {user.full_name || user.username || 'Без имени'}
                            </Text>
                            <Text fontSize="sm" color="gray.600" isTruncated maxW="100%">
                              {user.email}
                            </Text>
                          </VStack>
                        </Checkbox>
                      ))
                    )}
                  </VStack>
                </CheckboxGroup>
              </Box>
              <Text fontSize="sm" color="gray.600">
                Выбрано: {localSelectedUserIds.length} из {totalUsersWithEmail}
              </Text>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Отмена
            </Button>
            <Button
              colorScheme="blue"
              onClick={handleApply}
            >
              Применить
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    );
  }, (prevProps, nextProps) => {
    // Предотвращаем ненужные ре-рендеры
    return (
      prevProps.isOpen === nextProps.isOpen &&
      prevProps.users === nextProps.users &&
      prevProps.totalUsersWithEmail === nextProps.totalUsersWithEmail
    );
  });

  return (
    <Box bg={bgColor} minH="100vh" p={6}>
      <VStack spacing={6} align="stretch">
        {/* Заголовок */}
        <Card bg={cardBg}>
          <CardHeader>
            <Stack
              direction={{ base: "column", md: "row" }}
              justify="space-between"
              spacing={{ base: 3, md: 0 }}
              align={{ base: "stretch", md: "center" }}
            >
              <Heading size={{ base: "md", md: "lg" }}>📧 Email Рассылки</Heading>
              <Box>
                <Stat textAlign={{ base: "left", md: "right" }} size="sm">
                  <StatLabel>Пользователей с email</StatLabel>
                  <StatNumber>{usersWithEmail.length}</StatNumber>
                </Stat>
              </Box>
            </Stack>
          </CardHeader>
        </Card>

        {/* Новая кампания */}
        <Card bg={cardBg}>
          <CardHeader cursor="pointer" onClick={() => setIsNewCampaignOpen(!isNewCampaignOpen)}>
            <HStack justify="space-between">
              <Heading size="md">
                <HStack>
                  <IconButton
                    icon={isNewCampaignOpen ? <FiChevronDown /> : <FiChevronRight />}
                    size="sm"
                    variant="ghost"
                  />
                  <Text>Новая кампания</Text>
                </HStack>
              </Heading>
            </HStack>
          </CardHeader>

          <Collapse in={isNewCampaignOpen}>
            <CardBody>
              <VStack spacing={4} align="stretch">
                <FormControl>
                  <FormLabel>Название кампании</FormLabel>
                  <Input
                    placeholder="Например: Акция на рабочие места"
                    value={campaignName}
                    onChange={(e) => setCampaignName(e.target.value)}
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Тема письма</FormLabel>
                  <Input
                    placeholder="Специальное предложение только для вас!"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Получатели</FormLabel>
                  <Select
                    value={recipientType}
                    onChange={(e) => setRecipientType(e.target.value)}
                  >
                    <option value="all">Все пользователи с email</option>
                    <option value="segment">Сегмент</option>
                    <option value="selected">Выбранные пользователи</option>
                    <option value="custom">Ручной ввод email адресов</option>
                  </Select>
                </FormControl>

                {recipientType === 'segment' && (
                  <FormControl>
                    <FormLabel>Тип сегмента</FormLabel>
                    <Select
                      value={segmentType}
                      onChange={(e) => setSegmentType(e.target.value)}
                    >
                      <option value="all">Все</option>
                      <option value="active">Активные пользователи</option>
                      <option value="new_users">Новые пользователи (7 дней)</option>
                      <option value="vip">VIP (10+ бронирований)</option>
                      <option value="inactive">Неактивные</option>
                    </Select>
                  </FormControl>
                )}

                {recipientType === 'selected' && (
                  <FormControl>
                    <FormLabel>Выбранные пользователи</FormLabel>
                    <Button
                      leftIcon={<FiUsers />}
                      onClick={onUserModalOpen}
                      variant="outline"
                      colorScheme="purple"
                      width="full"
                    >
                      Выбрать ({selectedUserIds.length})
                    </Button>
                    <FormHelperText>
                      Выбрано: {selectedUserIds.length} из {usersWithEmail.length} пользователей с email
                    </FormHelperText>
                  </FormControl>
                )}

                {recipientType === 'custom' && (
                  <FormControl>
                    <FormLabel>Email адреса</FormLabel>
                    <Textarea
                      placeholder="example1@email.com, example2@email.com&#10;или каждый адрес с новой строки"
                      value={customEmails}
                      onChange={(e) => setCustomEmails(e.target.value)}
                      rows={5}
                    />
                    <FormHelperText>
                      Введите email адреса через запятую или с новой строки
                    </FormHelperText>
                  </FormControl>
                )}

                <Divider />

                <FormControl>
                  <FormLabel>Дизайн письма</FormLabel>
                  <EmailEditor
                    initialDesign={unlayerDesign}
                    onSave={handleEditorSave}
                    height="500px"
                  />
                </FormControl>

                <Divider />

                <Stack direction={{ base: "column", sm: "row" }} spacing={3}>
                  <Button
                    colorScheme="blue"
                    leftIcon={<FiSend />}
                    onClick={handleCreateCampaign}
                    isLoading={isSending}
                    width={{ base: "full", sm: "auto" }}
                  >
                    Создать черновик
                  </Button>
                </Stack>
              </VStack>
            </CardBody>
          </Collapse>
        </Card>

        {/* Список кампаний */}
        <Card bg={cardBg}>
          <CardHeader cursor="pointer" onClick={() => setIsCampaignsListOpen(!isCampaignsListOpen)}>
            <HStack justify="space-between">
              <Heading size="md">
                <HStack>
                  <IconButton
                    icon={isCampaignsListOpen ? <FiChevronDown /> : <FiChevronRight />}
                    size="sm"
                    variant="ghost"
                  />
                  <Text>Все кампании ({campaigns.length})</Text>
                </HStack>
              </Heading>
              <HStack spacing={2}>
                <Tooltip label="Очистить историю (удалить отправленные и провалившиеся кампании)">
                  <IconButton
                    icon={<FiTrash2 />}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleClearHistory();
                    }}
                    colorScheme="red"
                    variant="ghost"
                    size="sm"
                  />
                </Tooltip>
                <IconButton
                  icon={<FiUsers />}
                  onClick={(e) => {
                    e.stopPropagation();
                    fetchCampaigns();
                  }}
                  isLoading={isLoading}
                  size="sm"
                />
              </HStack>
            </HStack>
          </CardHeader>

          <Collapse in={isCampaignsListOpen}>
            <CardBody>
              {isLoading ? (
                <Box textAlign="center" py={10}>
                  <Spinner size="xl" />
                </Box>
              ) : campaigns.length === 0 ? (
                <Text textAlign="center" py={10} color="gray.500">
                  Нет созданных кампаний
                </Text>
              ) : isMobile ? (
                // Карточный вид для мобильных устройств
                <VStack spacing={3} width="full">
                  {campaigns.map((campaign) => (
                    <Card key={campaign.id} width="full" size="sm">
                      <CardBody>
                        <VStack align="stretch" spacing={3}>
                          {/* Заголовок с названием и статусом */}
                          <HStack justify="space-between" align="start">
                            <VStack align="start" spacing={1} flex={1}>
                              <Text fontWeight="bold" fontSize="sm" noOfLines={2}>
                                {campaign.name}
                              </Text>
                              <Text fontSize="xs" color="gray.500" noOfLines={1}>
                                {campaign.subject}
                              </Text>
                            </VStack>
                            <Badge colorScheme={getStatusColor(campaign.status)} fontSize="xs">
                              {getStatusLabel(campaign.status)}
                            </Badge>
                          </HStack>

                          <Divider />

                          {/* Статистика в сетке 2x2 */}
                          <SimpleGrid columns={2} spacing={2} fontSize="xs">
                            <Box>
                              <Text color="gray.500">Получатели:</Text>
                              <Text fontWeight="medium">{campaign.total_count}</Text>
                            </Box>
                            <Box>
                              <Text color="gray.500">Отправлено:</Text>
                              <Text fontWeight="medium">{campaign.sent_count}</Text>
                            </Box>
                            <Box>
                              <HStack>
                                <FiEye size={12} />
                                <Text color="gray.500">Открыто:</Text>
                              </HStack>
                              <Text fontWeight="medium">{campaign.opened_count}</Text>
                            </Box>
                            <Box>
                              <HStack>
                                <FiMousePointer size={12} />
                                <Text color="gray.500">Клики:</Text>
                              </HStack>
                              <Text fontWeight="medium">{campaign.clicked_count}</Text>
                            </Box>
                          </SimpleGrid>

                          <Text fontSize="xs" color="gray.500">
                            Создано: {new Date(campaign.created_at).toLocaleDateString('ru-RU')}
                          </Text>

                          <Divider />

                          {/* Кнопки действий */}
                          <HStack spacing={2} justify="flex-end">
                            {campaign.status === 'draft' && (
                              <>
                                <Button
                                  leftIcon={<FiSend />}
                                  size="sm"
                                  colorScheme="green"
                                  onClick={() => handleSendCampaign(campaign.id)}
                                  isLoading={isSending}
                                  flex={1}
                                >
                                  Отправить
                                </Button>
                                <IconButton
                                  icon={<FiMail />}
                                  size="sm"
                                  colorScheme="blue"
                                  onClick={() => {
                                    setSelectedCampaign(campaign);
                                    onTestEmailOpen();
                                  }}
                                  aria-label="Тест"
                                />
                              </>
                            )}
                            {campaign.status === 'failed' && (
                              <Button
                                leftIcon={<FiSend />}
                                size="sm"
                                colorScheme="orange"
                                onClick={() => handleSendCampaign(campaign.id)}
                                isLoading={isSending}
                                flex={1}
                              >
                                Переотправить
                              </Button>
                            )}
                            <IconButton
                              icon={<FiBarChart2 />}
                              size="sm"
                              onClick={() => handleShowAnalytics(campaign)}
                              aria-label="Аналитика"
                            />
                            <IconButton
                              icon={<FiTrash2 />}
                              size="sm"
                              colorScheme="red"
                              variant="ghost"
                              onClick={() => handleDeleteCampaign(campaign.id)}
                              aria-label="Удалить"
                            />
                          </HStack>
                        </VStack>
                      </CardBody>
                    </Card>
                  ))}
                </VStack>
              ) : (
                // Табличный вид для планшетов и десктопов
                <TableContainer>
                  <Table variant="simple" size="sm">
                    <Thead>
                      <Tr>
                        <Th>Название</Th>
                        <Th>Тема</Th>
                        <Th>Статус</Th>
                        <Th>Получатели</Th>
                        <Th>Отправлено</Th>
                        <Th>Открыто</Th>
                        <Th>Клики</Th>
                        <Th>Дата создания</Th>
                        <Th>Действия</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {campaigns.map((campaign) => (
                        <Tr key={campaign.id}>
                          <Td>
                            <Tooltip label={campaign.name}>
                              <Text maxW="200px" isTruncated>
                                {campaign.name}
                              </Text>
                            </Tooltip>
                          </Td>
                          <Td>
                            <Tooltip label={campaign.subject}>
                              <Text maxW="200px" isTruncated>
                                {campaign.subject}
                              </Text>
                            </Tooltip>
                          </Td>
                          <Td>
                            <Badge colorScheme={getStatusColor(campaign.status)}>
                              {getStatusLabel(campaign.status)}
                            </Badge>
                          </Td>
                          <Td>{campaign.total_count}</Td>
                          <Td>{campaign.sent_count}</Td>
                          <Td>
                            <HStack>
                              <FiEye />
                              <Text>{campaign.opened_count}</Text>
                            </HStack>
                          </Td>
                          <Td>
                            <HStack>
                              <FiMousePointer />
                              <Text>{campaign.clicked_count}</Text>
                            </HStack>
                          </Td>
                          <Td>
                            {new Date(campaign.created_at).toLocaleDateString('ru-RU')}
                          </Td>
                          <Td>
                            <HStack spacing={{ base: 1, md: 2 }}>
                              {campaign.status === 'draft' && (
                                <Tooltip label="Отправить">
                                  <IconButton
                                    icon={<FiSend />}
                                    size={{ base: "xs", md: "sm" }}
                                    colorScheme="green"
                                    onClick={() => handleSendCampaign(campaign.id)}
                                    isLoading={isSending}
                                  />
                                </Tooltip>
                              )}

                              {campaign.status === 'failed' && (
                                <Tooltip label="Переотправить">
                                  <IconButton
                                    icon={<FiSend />}
                                    size={{ base: "xs", md: "sm" }}
                                    colorScheme="orange"
                                    onClick={() => handleSendCampaign(campaign.id)}
                                    isLoading={isSending}
                                  />
                                </Tooltip>
                              )}

                              {campaign.status === 'draft' && (
                                <Tooltip label="Тестовая отправка">
                                  <IconButton
                                    icon={<FiMail />}
                                    size={{ base: "xs", md: "sm" }}
                                    colorScheme="blue"
                                    onClick={() => {
                                      setSelectedCampaign(campaign);
                                      onTestEmailOpen();
                                    }}
                                  />
                                </Tooltip>
                              )}

                              <Tooltip label="Аналитика">
                                <IconButton
                                  icon={<FiBarChart2 />}
                                  size={{ base: "xs", md: "sm" }}
                                  onClick={() => handleShowAnalytics(campaign)}
                                />
                              </Tooltip>

                              <Tooltip label="Удалить">
                                <IconButton
                                  icon={<FiTrash2 />}
                                  size={{ base: "xs", md: "sm" }}
                                  colorScheme="red"
                                  variant="ghost"
                                  onClick={() => handleDeleteCampaign(campaign.id)}
                                />
                              </Tooltip>
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

      {/* Модалка аналитики */}
      <Modal isOpen={isStatsOpen} onClose={onStatsClose} size={{ base: "full", md: "xl" }}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            Аналитика: {selectedCampaign?.name}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {!campaignAnalytics ? (
              <Box textAlign="center" py={10}>
                <Spinner size="xl" />
              </Box>
            ) : (
              <VStack spacing={4} align="stretch">
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                  <Stat>
                    <StatLabel>Всего получателей</StatLabel>
                    <StatNumber>{campaignAnalytics.total_recipients}</StatNumber>
                  </Stat>

                  <Stat>
                    <StatLabel>Отправлено</StatLabel>
                    <StatNumber>{campaignAnalytics.sent}</StatNumber>
                    <StatHelpText>
                      Доставлено: {campaignAnalytics.delivered} ({campaignAnalytics.delivery_rate}%)
                    </StatHelpText>
                  </Stat>

                  <Stat>
                    <StatLabel>Открыто</StatLabel>
                    <StatNumber>{campaignAnalytics.opened}</StatNumber>
                    <StatHelpText>
                      Open Rate: {campaignAnalytics.open_rate}%
                    </StatHelpText>
                  </Stat>

                  <Stat>
                    <StatLabel>Клики</StatLabel>
                    <StatNumber>{campaignAnalytics.clicked}</StatNumber>
                    <StatHelpText>
                      CTR: {campaignAnalytics.click_rate}%
                    </StatHelpText>
                  </Stat>

                  <Stat>
                    <StatLabel>Ошибки</StatLabel>
                    <StatNumber>{campaignAnalytics.failed}</StatNumber>
                  </Stat>

                  <Stat>
                    <StatLabel>Bounce</StatLabel>
                    <StatNumber>{campaignAnalytics.bounced}</StatNumber>
                    <StatHelpText>
                      Bounce Rate: {campaignAnalytics.bounce_rate}%
                    </StatHelpText>
                  </Stat>
                </SimpleGrid>

                {campaignAnalytics.avg_time_to_open && (
                  <Box>
                    <Text fontWeight="bold">Среднее время до открытия:</Text>
                    <Text>{campaignAnalytics.avg_time_to_open} минут</Text>
                  </Box>
                )}

                {campaignAnalytics.top_links && campaignAnalytics.top_links.length > 0 && (
                  <Box>
                    <Text fontWeight="bold" mb={2}>Топ ссылок:</Text>
                    <VStack align="stretch" spacing={2}>
                      {campaignAnalytics.top_links.map((link, index) => (
                        <HStack key={index} justify="space-between">
                          <Text fontSize="sm" isTruncated maxW="300px">
                            {link.url}
                          </Text>
                          <Badge>{link.clicks} кликов</Badge>
                        </HStack>
                      ))}
                    </VStack>
                  </Box>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button onClick={onStatsClose}>Закрыть</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Модалка тестовой отправки */}
      <Modal isOpen={isTestEmailOpen} onClose={onTestEmailClose} size={{ base: "full", md: "md" }}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Тестовая отправка</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <FormControl>
              <FormLabel>Email для теста</FormLabel>
              <Input
                type="email"
                placeholder="test@example.com"
                value={testEmail}
                onChange={(e) => setTestEmail(e.target.value)}
              />
            </FormControl>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onTestEmailClose}>
              Отмена
            </Button>
            <Button
              colorScheme="blue"
              onClick={handleSendTestEmail}
              isLoading={isSending}
            >
              Отправить
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Модалка выбора пользователей */}
      <UserSelectionModal
        isOpen={isUserModalOpen}
        onClose={onUserModalClose}
        users={usersWithEmail}
        selectedUserIds={selectedUserIds}
        onSelectedUserIdsChange={handleSelectedUsersChange}
        totalUsersWithEmail={usersWithEmail.length}
      />
    </Box>
  );
};

export default Emails;
