import React from 'react';
import {
  Box,
  HStack,
  Button,
  Text,
  Checkbox,
  Icon,
  useColorModeValue
} from '@chakra-ui/react';

/**
 * Универсальный компонент для панели массовых действий
 * @param {number} selectedCount - Количество выбранных элементов
 * @param {number} currentPageCount - Количество элементов на текущей странице
 * @param {array} actions - Массив действий [{label, icon, onClick, colorScheme, isLoading}]
 * @param {function} onSelectAll - Callback для выбора всех элементов на странице
 * @param {function} onDeselectAll - Callback для отмены выбора
 * @param {boolean} isAllSelected - Все ли элементы выбраны
 * @param {boolean} isIndeterminate - Частично выбраны
 * @param {string} entityName - Название сущности для отображения (например, "пользователей", "бронирований")
 */
export const BulkActionsBar = ({
  selectedCount,
  currentPageCount = 0,
  actions = [],
  onSelectAll,
  onDeselectAll,
  isAllSelected = false,
  isIndeterminate = false,
  entityName = 'элементов'
}) => {
  const bg = useColorModeValue('purple.50', 'purple.900');
  const borderColor = useColorModeValue('purple.200', 'purple.600');
  const textColor = useColorModeValue('purple.700', 'purple.200');

  const hasSelection = selectedCount > 0 || isIndeterminate;

  return (
    <Box
      bg={bg}
      borderWidth="1px"
      borderColor={borderColor}
      borderRadius="lg"
      p={4}
      mb={4}
    >
      <HStack justify="space-between" align="center" wrap="wrap" spacing={4}>
        {/* Левая часть: информация о выборе и checkbox */}
        <HStack spacing={4}>
          <Text fontSize="sm" fontWeight="medium" color={textColor}>
            {selectedCount > 0
              ? `Выбрано: ${selectedCount} ${entityName}`
              : `Выберите ${entityName} для действий`
            }
          </Text>

          {onSelectAll && (
            <Checkbox
              isChecked={isAllSelected}
              isIndeterminate={isIndeterminate}
              onChange={(e) => {
                if (e.target.checked) {
                  onSelectAll();
                } else {
                  onDeselectAll();
                }
              }}
              colorScheme="purple"
            >
              <Text fontSize="sm">
                Выбрать все на странице ({currentPageCount})
              </Text>
            </Checkbox>
          )}
        </HStack>

        {/* Правая часть: кнопки действий */}
        <HStack spacing={2} wrap="wrap">
          {!hasSelection && (
            <Text fontSize="sm" color="gray.500">
              Выберите записи для выполнения действий
            </Text>
          )}
          {actions.map((action, index) => (
            <Button
              key={index}
              leftIcon={action.icon ? <Icon as={action.icon} /> : null}
              onClick={action.onClick}
              colorScheme={action.colorScheme || 'gray'}
              size="sm"
              variant={action.variant || 'outline'}
              isLoading={action.isLoading}
              loadingText={action.loadingText}
              isDisabled={!hasSelection || action.isDisabled}
            >
              {action.label}
              {action.showCount && hasSelection && ` (${selectedCount})`}
            </Button>
          ))}
        </HStack>
      </HStack>
    </Box>
  );
};

export default BulkActionsBar;
