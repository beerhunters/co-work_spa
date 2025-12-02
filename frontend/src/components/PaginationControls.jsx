import React from 'react';
import {
  Box,
  HStack,
  Button,
  Text,
  IconButton,
  Select,
  useBreakpointValue
} from '@chakra-ui/react';
import {
  FiChevronLeft,
  FiChevronRight,
  FiChevronsLeft,
  FiChevronsRight
} from 'react-icons/fi';

/**
 * Универсальный компонент пагинации с отображением диапазона элементов
 * @param {number} currentPage - Текущая страница (1-indexed)
 * @param {number} totalPages - Общее количество страниц
 * @param {number} totalItems - Общее количество элементов
 * @param {number} itemsPerPage - Количество элементов на странице
 * @param {function} onPageChange - Callback при изменении страницы
 * @param {function} onItemsPerPageChange - Callback при изменении количества элементов
 * @param {array} itemsPerPageOptions - Опции для выбора количества элементов (по умолчанию [10, 20, 50, 100])
 */
export const PaginationControls = ({
  currentPage,
  totalPages,
  totalItems,
  itemsPerPage,
  onPageChange,
  onItemsPerPageChange,
  itemsPerPageOptions = [10, 20, 50, 100]
}) => {
  // Адаптивность: на мобильных показываем меньше кнопок
  const maxVisiblePages = useBreakpointValue({ base: 3, md: 5, lg: 7 });

  // Вычисляем диапазон текущих элементов
  const startItem = totalItems === 0 ? 0 : (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalItems);

  // Функция для генерации массива номеров видимых страниц
  const getVisiblePages = () => {
    if (totalPages <= maxVisiblePages) {
      // Если страниц мало, показываем все
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }

    const pages = [];
    const halfVisible = Math.floor(maxVisiblePages / 2);

    // Всегда показываем первую страницу
    pages.push(1);

    let startPage = Math.max(2, currentPage - halfVisible);
    let endPage = Math.min(totalPages - 1, currentPage + halfVisible);

    // Корректируем диапазон если близко к началу или концу
    if (currentPage <= halfVisible + 1) {
      endPage = Math.min(maxVisiblePages - 1, totalPages - 1);
    }
    if (currentPage >= totalPages - halfVisible) {
      startPage = Math.max(2, totalPages - maxVisiblePages + 2);
    }

    // Добавляем многоточие после первой страницы если нужно
    if (startPage > 2) {
      pages.push('...');
    }

    // Добавляем средние страницы
    for (let i = startPage; i <= endPage; i++) {
      pages.push(i);
    }

    // Добавляем многоточие перед последней страницей если нужно
    if (endPage < totalPages - 1) {
      pages.push('...');
    }

    // Всегда показываем последнюю страницу
    if (totalPages > 1) {
      pages.push(totalPages);
    }

    return pages;
  };

  const visiblePages = getVisiblePages();

  return (
    <Box>
      <HStack
        spacing={4}
        justify="space-between"
        wrap="wrap"
        py={4}
        px={2}
      >
        {/* Информация о диапазоне */}
        <HStack spacing={2} flex="1" minW="200px">
          <Text fontSize="sm" color="gray.600" whiteSpace="nowrap">
            Показано {startItem}-{endItem} из {totalItems}
          </Text>

          {/* Выбор количества элементов на странице */}
          {onItemsPerPageChange && (
            <HStack spacing={2}>
              <Text fontSize="sm" color="gray.600" whiteSpace="nowrap">
                По:
              </Text>
              <Select
                size="sm"
                value={itemsPerPage}
                onChange={(e) => onItemsPerPageChange(Number(e.target.value))}
                width="80px"
                bg="white"
              >
                {itemsPerPageOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </Select>
            </HStack>
          )}
        </HStack>

        {/* Навигация по страницам */}
        {totalPages > 1 && (
          <HStack spacing={1}>
            {/* Кнопка на первую страницу */}
            <IconButton
              icon={<FiChevronsLeft />}
              size="sm"
              variant="outline"
              onClick={() => onPageChange(1)}
              isDisabled={currentPage === 1}
              aria-label="Первая страница"
              title="Первая страница"
            />

            {/* Кнопка на предыдущую страницу */}
            <IconButton
              icon={<FiChevronLeft />}
              size="sm"
              variant="outline"
              onClick={() => onPageChange(currentPage - 1)}
              isDisabled={currentPage === 1}
              aria-label="Предыдущая страница"
              title="Предыдущая страница"
            />

            {/* Номера страниц */}
            {visiblePages.map((page, index) => {
              if (page === '...') {
                return (
                  <Text
                    key={`ellipsis-${index}`}
                    px={2}
                    fontSize="sm"
                    color="gray.500"
                  >
                    ...
                  </Text>
                );
              }

              return (
                <Button
                  key={page}
                  size="sm"
                  variant={currentPage === page ? 'solid' : 'outline'}
                  colorScheme={currentPage === page ? 'purple' : 'gray'}
                  onClick={() => onPageChange(page)}
                  minW="40px"
                >
                  {page}
                </Button>
              );
            })}

            {/* Кнопка на следующую страницу */}
            <IconButton
              icon={<FiChevronRight />}
              size="sm"
              variant="outline"
              onClick={() => onPageChange(currentPage + 1)}
              isDisabled={currentPage === totalPages}
              aria-label="Следующая страница"
              title="Следующая страница"
            />

            {/* Кнопка на последнюю страницу */}
            <IconButton
              icon={<FiChevronsRight />}
              size="sm"
              variant="outline"
              onClick={() => onPageChange(totalPages)}
              isDisabled={currentPage === totalPages}
              aria-label="Последняя страница"
              title="Последняя страница"
            />
          </HStack>
        )}
      </HStack>
    </Box>
  );
};

export default PaginationControls;
