import { z } from 'zod';

/**
 * Validation schema для формы входа (Login)
 */
export const loginSchema = z.object({
  login: z
    .string()
    .min(3, 'Логин должен содержать минимум 3 символа')
    .max(50, 'Логин не может быть длиннее 50 символов')
    .trim(),

  password: z
    .string()
    .min(5, 'Пароль должен содержать минимум 5 символов')
    .max(100, 'Пароль не может быть длиннее 100 символов'),
});

/**
 * Validation schema для создания/редактирования пользователя
 */
export const userSchema = z.object({
  full_name: z
    .string()
    .min(3, 'ФИО должно содержать минимум 3 символа')
    .max(100, 'ФИО не может быть длиннее 100 символов')
    .regex(/^[а-яА-ЯёЁa-zA-Z\s-]+$/, 'ФИО может содержать только буквы, пробелы и дефисы')
    .trim(),

  phone: z
    .string()
    .regex(
      /^\+?[1-9]\d{9,14}$/,
      'Неверный формат телефона. Пример: +79991234567'
    )
    .trim(),

  email: z
    .string()
    .email('Неверный формат email. Пример: user@example.com')
    .max(100, 'Email не может быть длиннее 100 символов')
    .trim()
    .toLowerCase(),

  telegram_id: z
    .union([
      z.string().regex(/^\d+$/, 'Telegram ID должен содержать только цифры'),
      z.number().int().positive('Telegram ID должен быть положительным числом'),
    ])
    .optional()
    .or(z.literal('')),

  username: z
    .string()
    .max(50, 'Username не может быть длиннее 50 символов')
    .optional()
    .or(z.literal('')),

  admin_comment: z
    .string()
    .max(500, 'Комментарий не может быть длиннее 500 символов')
    .optional()
    .or(z.literal('')),

  birth_date: z
    .string()
    .refine(
      (val) => {
        if (!val || val === '') return true;

        // Проверка формата DD.MM или DD.MM.YYYY
        const dateRegex = /^\d{2}\.\d{2}(\.\d{4})?$/;
        if (!dateRegex.test(val)) return false;

        // Проверка валидности дня, месяца и опционально года
        const parts = val.split('.').map(Number);
        const [day, month, year] = parts;

        if (day < 1 || day > 31) return false;
        if (month < 1 || month > 12) return false;

        // Если год указан, проверяем что он в разумных пределах
        if (year !== undefined) {
          const currentYear = new Date().getFullYear();
          if (year < 1900 || year > currentYear) return false;
        }

        return true;
      },
      {
        message: 'Дата рождения должна быть в формате ДД.ММ или ДД.ММ.ГГГГ (например, 25.12 или 25.12.1990)',
      }
    )
    .optional()
    .or(z.literal('')),
});

/**
 * Validation schema для редактирования пользователя (частичное обновление)
 * Все поля опциональные
 */
export const userUpdateSchema = userSchema.partial();

/**
 * Validation schema для регистрационных данных пользователя
 * Используется когда пользователь регистрируется через бота
 */
export const userRegistrationSchema = z.object({
  full_name: z
    .string()
    .min(3, 'ФИО должно содержать минимум 3 символа')
    .max(100, 'ФИО не может быть длиннее 100 символов')
    .trim(),

  phone: z
    .string()
    .regex(
      /^\+?[1-9]\d{9,14}$/,
      'Неверный формат телефона. Используйте международный формат: +79991234567'
    )
    .trim(),

  email: z
    .string()
    .email('Неверный формат email. Используйте формат: user@example.com')
    .trim()
    .toLowerCase(),
});

/**
 * Helper функция для получения сообщений об ошибках из Zod
 * @param {ZodError} error - Zod validation error
 * @returns {Object} - Объект с ошибками по полям
 */
export const getZodErrors = (error) => {
  const errors = {};
  error.issues.forEach((issue) => {
    const path = issue.path.join('.');
    errors[path] = issue.message;
  });
  return errors;
};

/**
 * Helper функция для валидации данных с использованием схемы
 * @param {ZodSchema} schema - Zod schema
 * @param {Object} data - Данные для валидации
 * @returns {Object} - { success: boolean, data?: validData, errors?: errorObject }
 */
export const validateData = (schema, data) => {
  try {
    const validData = schema.parse(data);
    return { success: true, data: validData };
  } catch (error) {
    return { success: false, errors: getZodErrors(error) };
  }
};
