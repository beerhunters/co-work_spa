import React, { useMemo, useCallback } from 'react';
import ReactQuill from 'react-quill';
import 'react-quill/dist/quill.snow.css';
import { Box, FormControl, FormLabel, FormHelperText, Text, useColorModeValue } from '@chakra-ui/react';
import { getTextLength } from '../utils/telegram-html-sanitizer';

/**
 * WYSIWYG редактор для сообщений Telegram с поддержкой HTML форматирования
 * Поддерживает только теги разрешенные Telegram API: <b>, <i>, <u>, <code>, <a href="">
 */
const TelegramEditor = ({
  value = '',
  onChange,
  placeholder = 'Введите текст сообщения...',
  maxLength = 4096,
  label,
  helperText,
  isInvalid,
  errorMessage,
  ...props
}) => {
  // Цветовая схема для светлой/темной темы
  const editorBg = useColorModeValue('white', 'gray.700');
  const editorBorder = useColorModeValue('gray.200', 'gray.600');
  const editorFocusBorder = useColorModeValue('blue.500', 'blue.300');
  const toolbarBg = useColorModeValue('gray.50', 'gray.800');
  const textColor = useColorModeValue('gray.800', 'gray.100');

  // Конфигурация toolbar - только поддерживаемые Telegram теги
  const modules = useMemo(() => ({
    toolbar: [
      ['bold', 'italic', 'underline', 'code-block'], // Форматирование текста
      ['link'], // Ссылки
      ['clean'] // Очистить форматирование
    ],
    clipboard: {
      matchVisual: false, // Отключаем сложное форматирование при вставке
    }
  }), []);

  // Разрешенные форматы
  const formats = [
    'bold', 'italic', 'underline', 'code-block', 'link'
  ];

  // Обработчик изменения текста
  const handleChange = useCallback((content, delta, source, editor) => {
    // Проверяем длину текста (без HTML тегов)
    // НЕ применяем sanitization здесь, чтобы не конфликтовать с курсором Quill
    const textLength = getTextLength(content);

    // Если текст слишком длинный, не обновляем
    if (textLength > maxLength) {
      return;
    }

    // Вызываем onChange с исходным HTML (sanitization будет при отправке)
    onChange(content);
  }, [onChange, maxLength]);

  // Вычисляем текущую длину текста
  const currentLength = useMemo(() => getTextLength(value), [value]);
  const isOverLimit = currentLength > maxLength;

  return (
    <FormControl isInvalid={isInvalid || isOverLimit} {...props}>
      {label && <FormLabel>{label}</FormLabel>}

      <Box
        className="telegram-editor-wrapper"
        sx={{
          '& .quill': {
            backgroundColor: editorBg,
            borderRadius: 'md',
            border: '1px solid',
            borderColor: isInvalid || isOverLimit ? 'red.500' : editorBorder,
            transition: 'border-color 0.2s',

            '&:focus-within': {
              borderColor: isInvalid || isOverLimit ? 'red.500' : editorFocusBorder,
              boxShadow: `0 0 0 1px ${isInvalid || isOverLimit ? 'var(--chakra-colors-red-500)' : 'var(--chakra-colors-blue-500)'}`,
            },
          },

          '& .ql-toolbar': {
            backgroundColor: toolbarBg,
            borderTopLeftRadius: 'md',
            borderTopRightRadius: 'md',
            borderBottom: '1px solid',
            borderColor: editorBorder,
            padding: '8px',
          },

          '& .ql-container': {
            borderBottom: 'none',
            fontFamily: 'inherit',
            fontSize: 'md',
            minHeight: '150px',
            color: textColor,
          },

          '& .ql-editor': {
            minHeight: '150px',
            padding: '12px 15px',

            '&.ql-blank::before': {
              color: useColorModeValue('gray.400', 'gray.500'),
              fontStyle: 'normal',
            },
          },

          // Стили для кнопок toolbar
          '& .ql-stroke': {
            stroke: textColor,
          },

          '& .ql-fill': {
            fill: textColor,
          },

          '& .ql-picker-label': {
            color: textColor,
          },

          // Hover эффекты для кнопок
          '& .ql-toolbar button:hover, & .ql-toolbar button:focus': {
            backgroundColor: useColorModeValue('gray.100', 'gray.700'),
          },

          '& .ql-toolbar button.ql-active': {
            backgroundColor: useColorModeValue('blue.100', 'blue.900'),
          },
        }}
      >
        <ReactQuill
          theme="snow"
          value={value}
          onChange={handleChange}
          modules={modules}
          formats={formats}
          placeholder={placeholder}
          preserveWhitespace
        />
      </Box>

      {/* Счетчик символов */}
      <Box mt={2} display="flex" justifyContent="space-between" alignItems="center">
        <FormHelperText m={0}>
          {helperText || 'Поддерживается форматирование: жирный, курсив, подчеркнутый, код, ссылки'}
        </FormHelperText>

        <Text
          fontSize="sm"
          color={isOverLimit ? 'red.500' : currentLength > maxLength * 0.9 ? 'orange.500' : 'gray.500'}
          fontWeight={isOverLimit ? 'bold' : 'normal'}
        >
          {currentLength} / {maxLength}
        </Text>
      </Box>

      {/* Сообщение об ошибке */}
      {(isInvalid && errorMessage) && (
        <Text color="red.500" fontSize="sm" mt={2}>
          {errorMessage}
        </Text>
      )}

      {isOverLimit && (
        <Text color="red.500" fontSize="sm" mt={2}>
          Превышен лимит символов. Telegram поддерживает максимум {maxLength} символов.
        </Text>
      )}
    </FormControl>
  );
};

export default TelegramEditor;
