import React, { useRef, useEffect } from 'react';
import { Box, Button, HStack, useToast } from '@chakra-ui/react';
import EmailEditor from 'react-email-editor';

/**
 * Email редактор на базе Unlayer
 * Позволяет создавать email письма drag-and-drop методом
 */
const UnlayerEmailEditor = ({
  initialDesign = null,
  onSave,
  height = '600px',
  readOnly = false
}) => {
  const emailEditorRef = useRef(null);
  const toast = useToast();

  useEffect(() => {
    // Загружаем initial design если есть
    if (initialDesign && emailEditorRef.current) {
      try {
        const design = typeof initialDesign === 'string'
          ? JSON.parse(initialDesign)
          : initialDesign;

        // Даем редактору время на инициализацию
        setTimeout(() => {
          emailEditorRef.current.editor.loadDesign(design);
        }, 500);
      } catch (error) {
        console.error('Error loading design:', error);
        toast({
          title: 'Ошибка загрузки дизайна',
          description: 'Не удалось загрузить сохраненный дизайн',
          status: 'error',
          duration: 3000,
        });
      }
    }
  }, [initialDesign, toast]);

  const exportHtml = () => {
    return new Promise((resolve, reject) => {
      if (!emailEditorRef.current) {
        reject(new Error('Editor not initialized'));
        return;
      }

      emailEditorRef.current.editor.exportHtml((data) => {
        const { design, html } = data;
        resolve({ design, html });
      });
    });
  };

  const handleSave = async () => {
    try {
      const { design, html } = await exportHtml();

      if (onSave) {
        onSave({
          design: JSON.stringify(design),
          html: html
        });
      }

      toast({
        title: 'Успешно сохранено',
        description: 'Email дизайн сохранен',
        status: 'success',
        duration: 2000,
      });
    } catch (error) {
      console.error('Error saving email:', error);
      toast({
        title: 'Ошибка сохранения',
        description: error.message || 'Не удалось сохранить email',
        status: 'error',
        duration: 3000,
      });
    }
  };

  const onLoad = () => {
    // Редактор загружен
    console.log('Unlayer editor loaded');
  };

  const onReady = () => {
    // Редактор готов к работе
    console.log('Unlayer editor ready');
  };

  return (
    <Box>
      <Box
        borderWidth="1px"
        borderRadius="md"
        overflow="hidden"
        height={height}
      >
        <EmailEditor
          ref={emailEditorRef}
          onLoad={onLoad}
          onReady={onReady}
          minHeight={height}
          options={{
            displayMode: 'email',
            locale: 'ru-RU',
            appearance: {
              theme: 'light',
            },
            user: {
              id: 1,
              name: 'Admin',
            },
            mergeTags: {
              first_name: {
                name: 'Имя',
                value: '{{first_name}}',
              },
              last_name: {
                name: 'Фамилия',
                value: '{{last_name}}',
              },
              full_name: {
                name: 'Полное имя',
                value: '{{full_name}}',
              },
              email: {
                name: 'Email',
                value: '{{email}}',
              },
              phone: {
                name: 'Телефон',
                value: '{{phone}}',
              },
              successful_bookings: {
                name: 'Количество бронирований',
                value: '{{successful_bookings}}',
              },
              invited_count: {
                name: 'Приглашено людей',
                value: '{{invited_count}}',
              },
            },
          }}
        />
      </Box>

      {!readOnly && (
        <HStack mt={4} spacing={4}>
          <Button colorScheme="blue" onClick={handleSave}>
            Сохранить дизайн
          </Button>
        </HStack>
      )}
    </Box>
  );
};

export default UnlayerEmailEditor;
