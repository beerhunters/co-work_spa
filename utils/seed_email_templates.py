"""
Скрипт для создания готовых email шаблонов в базе данных.
Запуск: python -m utils.seed_email_templates
"""

from datetime import datetime
from models.models import DatabaseManager, EmailTemplate
from utils.logger import get_logger

logger = get_logger(__name__)

# Готовые email шаблоны
EMAIL_TEMPLATES = [
    {
        "name": "Приветственное письмо",
        "description": "Письмо для новых пользователей при регистрации",
        "subject": "Добро пожаловать в наш коворкинг, {{first_name}}!",
        "category": "welcome",
        "html_content": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Добро пожаловать</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f4f4f4; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: bold;">Добро пожаловать!</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Здравствуйте, <strong>{{first_name}}</strong>!
                            </p>
                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Спасибо за регистрацию в нашем коворкинге! Мы рады приветствовать вас в нашем сообществе профессионалов.
                            </p>
                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Теперь вам доступны:
                            </p>
                            <ul style="margin: 0 0 20px 0; padding-left: 20px; font-size: 16px; line-height: 28px; color: #333333;">
                                <li>Бронирование рабочих мест</li>
                                <li>Доступ к переговорным комнатам</li>
                                <li>Участие в мероприятиях</li>
                                <li>Специальные предложения для участников</li>
                            </ul>
                            <p style="margin: 0 0 30px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Ваш email для входа: <strong>{{email}}</strong>
                            </p>

                            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://t.me/your_bot" style="display: inline-block; padding: 15px 40px; background-color: #667eea; color: #ffffff; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold;">Начать работу</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e0e0e0;">
                            <p style="margin: 0 0 10px 0; font-size: 14px; color: #666666;">
                                С уважением,<br>Команда коворкинга
                            </p>
                            <p style="margin: 0; font-size: 12px; color: #999999;">
                                Если у вас есть вопросы, свяжитесь с нами через Telegram бот
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    },

    {
        "name": "Подтверждение бронирования",
        "description": "Подтверждение успешного бронирования рабочего места",
        "subject": "Ваше бронирование подтверждено - {{booking_date}}",
        "category": "booking",
        "html_content": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Подтверждение бронирования</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f4f4f4; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: bold;">✓ Бронирование подтверждено</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Здравствуйте, <strong>{{first_name}}</strong>!
                            </p>
                            <p style="margin: 0 0 30px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Ваше бронирование успешно подтверждено. Ждем вас в коворкинге!
                            </p>

                            <!-- Booking Details -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8f9fa; border-radius: 5px; margin-bottom: 30px;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <h3 style="margin: 0 0 15px 0; font-size: 18px; color: #333333;">Детали бронирования:</h3>
                                        <table width="100%" cellpadding="5" cellspacing="0" border="0">
                                            <tr>
                                                <td style="font-size: 14px; color: #666666; width: 40%;">Дата:</td>
                                                <td style="font-size: 14px; color: #333333; font-weight: bold;">{{booking_date}}</td>
                                            </tr>
                                            <tr>
                                                <td style="font-size: 14px; color: #666666;">Тариф:</td>
                                                <td style="font-size: 14px; color: #333333; font-weight: bold;">{{tariff_name}}</td>
                                            </tr>
                                            <tr>
                                                <td style="font-size: 14px; color: #666666;">Статус:</td>
                                                <td style="font-size: 14px; color: #28a745; font-weight: bold;">Подтверждено</td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                <strong>Что взять с собой:</strong>
                            </p>
                            <ul style="margin: 0 0 20px 0; padding-left: 20px; font-size: 14px; line-height: 24px; color: #666666;">
                                <li>Ноутбук и зарядное устройство</li>
                                <li>Личные вещи</li>
                                <li>Хорошее настроение 😊</li>
                            </ul>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e0e0e0;">
                            <p style="margin: 0 0 10px 0; font-size: 14px; color: #666666;">
                                До встречи в коворкинге!
                            </p>
                            <p style="margin: 0; font-size: 12px; color: #999999;">
                                Если нужно отменить или изменить бронирование, свяжитесь с нами через Telegram бот
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    },

    {
        "name": "Напоминание о продлении",
        "description": "Напоминание о необходимости продления бронирования",
        "subject": "Не забудьте продлить бронирование - {{booking_date}}",
        "category": "reminder",
        "html_content": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Напоминание о продлении</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f4f4f4; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: bold;">⏰ Время продлить бронирование</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Здравствуйте, <strong>{{first_name}}</strong>!
                            </p>
                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Ваше бронирование подходит к концу. Чтобы продолжить пользоваться коворкингом, необходимо продлить бронирование.
                            </p>

                            <!-- Booking Info -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #fff3cd; border-left: 4px solid #ffc107; margin-bottom: 30px;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <p style="margin: 0 0 10px 0; font-size: 14px; color: #856404;">
                                            <strong>Текущее бронирование:</strong>
                                        </p>
                                        <p style="margin: 0; font-size: 14px; color: #856404;">
                                            Дата окончания: <strong>{{booking_end_date}}</strong>
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 30px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Продлите бронирование прямо сейчас и получите специальное предложение!
                            </p>

                            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://t.me/your_bot" style="display: inline-block; padding: 15px 40px; background-color: #f5576c; color: #ffffff; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold;">Продлить бронирование</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e0e0e0;">
                            <p style="margin: 0 0 10px 0; font-size: 14px; color: #666666;">
                                С уважением,<br>Команда коворкинга
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    },

    {
        "name": "Промо-акция",
        "description": "Шаблон для рекламных акций и специальных предложений",
        "subject": "🎉 Специальное предложение только для вас!",
        "category": "promotion",
        "html_content": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Специальное предложение</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f4f4f4; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0 0 10px 0; color: #ffffff; font-size: 32px; font-weight: bold;">🎉 Специальное предложение!</h1>
                            <p style="margin: 0; color: #ffffff; font-size: 18px;">Только до конца месяца</p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Здравствуйте, <strong>{{first_name}}</strong>!
                            </p>
                            <p style="margin: 0 0 30px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Мы подготовили для вас эксклюзивное предложение:
                            </p>

                            <!-- Offer Box -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-bottom: 30px;">
                                <tr>
                                    <td style="padding: 30px; text-align: center;">
                                        <h2 style="margin: 0 0 15px 0; color: #ffffff; font-size: 36px; font-weight: bold;">-30%</h2>
                                        <p style="margin: 0; color: #ffffff; font-size: 18px;">на все тарифы</p>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                <strong>Что входит в предложение:</strong>
                            </p>
                            <ul style="margin: 0 0 30px 0; padding-left: 20px; font-size: 16px; line-height: 28px; color: #333333;">
                                <li>Скидка 30% на первый месяц</li>
                                <li>Бесплатный доступ к переговорным комнатам</li>
                                <li>Приглашение на закрытые мероприятия</li>
                                <li>Бонусные баллы в программе лояльности</li>
                            </ul>

                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 20px;">
                                <tr>
                                    <td align="center">
                                        <a href="https://t.me/your_bot" style="display: inline-block; padding: 18px 50px; background-color: #667eea; color: #ffffff; text-decoration: none; border-radius: 5px; font-size: 18px; font-weight: bold;">Воспользоваться предложением</a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0; font-size: 12px; line-height: 18px; color: #999999; text-align: center;">
                                Предложение действительно до 31 декабря 2025 года
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e0e0e0;">
                            <p style="margin: 0 0 10px 0; font-size: 14px; color: #666666;">
                                Не упустите возможность!
                            </p>
                            <p style="margin: 0; font-size: 12px; color: #999999;">
                                Если у вас есть вопросы, свяжитесь с нами через Telegram бот
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    },

    {
        "name": "Новости и обновления",
        "description": "Рассылка новостей и обновлений коворкинга",
        "subject": "📰 Новости коворкинга - {{month}}",
        "category": "newsletter",
        "html_content": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Новости коворкинга</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f4f4f4; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: bold;">📰 Новости коворкинга</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Здравствуйте, <strong>{{first_name}}</strong>!
                            </p>
                            <p style="margin: 0 0 30px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Делимся с вами последними новостями и обновлениями нашего коворкинга.
                            </p>

                            <!-- News Item 1 -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 30px;">
                                <tr>
                                    <td style="border-left: 4px solid #4facfe; padding-left: 20px;">
                                        <h3 style="margin: 0 0 10px 0; font-size: 18px; color: #333333;">Новое оборудование</h3>
                                        <p style="margin: 0; font-size: 14px; line-height: 22px; color: #666666;">
                                            Мы установили новые эргономичные кресла и мониторы в главном зале. Теперь работать стало еще комфортнее!
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <!-- News Item 2 -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 30px;">
                                <tr>
                                    <td style="border-left: 4px solid #00f2fe; padding-left: 20px;">
                                        <h3 style="margin: 0 0 10px 0; font-size: 18px; color: #333333;">Расширение площади</h3>
                                        <p style="margin: 0; font-size: 14px; line-height: 22px; color: #666666;">
                                            С 1 числа следующего месяца открывается второй этаж с дополнительными рабочими местами и зоной отдыха.
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <!-- News Item 3 -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 30px;">
                                <tr>
                                    <td style="border-left: 4px solid #4facfe; padding-left: 20px;">
                                        <h3 style="margin: 0 0 10px 0; font-size: 18px; color: #333333;">Предстоящие мероприятия</h3>
                                        <p style="margin: 0; font-size: 14px; line-height: 22px; color: #666666;">
                                            15 числа - мастер-класс по тайм-менеджменту<br>
                                            22 числа - нетворкинг для стартаперов<br>
                                            29 числа - презентация новых проектов
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://t.me/your_bot" style="display: inline-block; padding: 15px 40px; background-color: #4facfe; color: #ffffff; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold;">Узнать больше</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e0e0e0;">
                            <p style="margin: 0 0 10px 0; font-size: 14px; color: #666666;">
                                Следите за новостями в нашем Telegram канале
                            </p>
                            <p style="margin: 0; font-size: 12px; color: #999999;">
                                Вы получили это письмо, так как являетесь участником коворкинга
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    },

    {
        "name": "Отмена бронирования",
        "description": "Уведомление об отмене бронирования",
        "subject": "Бронирование отменено - {{booking_date}}",
        "category": "cancellation",
        "html_content": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отмена бронирования</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f4f4f4; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background-color: #6c757d; padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: bold;">Бронирование отменено</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Здравствуйте, <strong>{{first_name}}</strong>!
                            </p>
                            <p style="margin: 0 0 30px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Ваше бронирование было отменено.
                            </p>

                            <!-- Cancellation Details -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8f9fa; border-radius: 5px; margin-bottom: 30px;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <h3 style="margin: 0 0 15px 0; font-size: 18px; color: #333333;">Детали отмененного бронирования:</h3>
                                        <table width="100%" cellpadding="5" cellspacing="0" border="0">
                                            <tr>
                                                <td style="font-size: 14px; color: #666666; width: 40%;">Дата:</td>
                                                <td style="font-size: 14px; color: #333333;">{{booking_date}}</td>
                                            </tr>
                                            <tr>
                                                <td style="font-size: 14px; color: #666666;">Тариф:</td>
                                                <td style="font-size: 14px; color: #333333;">{{tariff_name}}</td>
                                            </tr>
                                            <tr>
                                                <td style="font-size: 14px; color: #666666;">Причина:</td>
                                                <td style="font-size: 14px; color: #333333;">{{cancellation_reason}}</td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 30px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Если отмена была произведена по ошибке или у вас есть вопросы, пожалуйста, свяжитесь с нами.
                            </p>

                            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://t.me/your_bot" style="display: inline-block; padding: 15px 40px; background-color: #667eea; color: #ffffff; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold;">Создать новое бронирование</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e0e0e0;">
                            <p style="margin: 0 0 10px 0; font-size: 14px; color: #666666;">
                                Надеемся увидеть вас снова!
                            </p>
                            <p style="margin: 0; font-size: 12px; color: #999999;">
                                Свяжитесь с нами через Telegram бот, если у вас есть вопросы
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    },

    {
        "name": "Благодарственное письмо",
        "description": "Письмо с благодарностью постоянным клиентам",
        "subject": "Спасибо за то, что вы с нами, {{first_name}}!",
        "category": "thank_you",
        "html_content": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Спасибо!</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f4f4f4; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 32px; font-weight: bold;">❤️ Спасибо!</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Дорогой <strong>{{first_name}}</strong>!
                            </p>
                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Хотим поблагодарить вас за то, что вы выбираете наш коворкинг!
                            </p>
                            <p style="margin: 0 0 30px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                За время вашего пребывания с нами вы:
                            </p>

                            <!-- Stats -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 30px;">
                                <tr>
                                    <td width="33%" align="center" style="padding: 20px; background-color: #f8f9fa; border-radius: 5px;">
                                        <h2 style="margin: 0 0 5px 0; color: #667eea; font-size: 32px; font-weight: bold;">{{visit_count}}</h2>
                                        <p style="margin: 0; font-size: 14px; color: #666666;">визитов</p>
                                    </td>
                                    <td width="2%"></td>
                                    <td width="33%" align="center" style="padding: 20px; background-color: #f8f9fa; border-radius: 5px;">
                                        <h2 style="margin: 0 0 5px 0; color: #667eea; font-size: 32px; font-weight: bold;">{{hours_worked}}</h2>
                                        <p style="margin: 0; font-size: 14px; color: #666666;">часов работы</p>
                                    </td>
                                    <td width="2%"></td>
                                    <td width="33%" align="center" style="padding: 20px; background-color: #f8f9fa; border-radius: 5px;">
                                        <h2 style="margin: 0 0 5px 0; color: #667eea; font-size: 32px; font-weight: bold;">{{events_attended}}</h2>
                                        <p style="margin: 0; font-size: 14px; color: #666666;">мероприятий</p>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                В знак благодарности мы дарим вам:
                            </p>

                            <!-- Gift Box -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-bottom: 30px;">
                                <tr>
                                    <td style="padding: 30px; text-align: center;">
                                        <h2 style="margin: 0 0 10px 0; color: #ffffff; font-size: 28px; font-weight: bold;">🎁 Бесплатный день</h2>
                                        <p style="margin: 0; color: #ffffff; font-size: 16px;">в нашем коворкинге</p>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 30px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Продолжайте работать и развиваться вместе с нами!
                            </p>

                            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://t.me/your_bot" style="display: inline-block; padding: 15px 40px; background-color: #f5576c; color: #ffffff; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold;">Активировать подарок</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e0e0e0;">
                            <p style="margin: 0 0 10px 0; font-size: 14px; color: #666666;">
                                С любовью и благодарностью,<br>Команда коворкинга
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    },

    {
        "name": "Запрос обратной связи",
        "description": "Письмо с просьбой оставить отзыв или оценку",
        "subject": "Поделитесь вашим мнением о коворкинге",
        "category": "feedback",
        "html_content": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Обратная связь</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f4f4f4; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #333333; font-size: 28px; font-weight: bold;">💭 Ваше мнение важно для нас</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Здравствуйте, <strong>{{first_name}}</strong>!
                            </p>
                            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Вы уже некоторое время пользуетесь нашим коворкингом, и нам очень важно узнать ваше мнение!
                            </p>
                            <p style="margin: 0 0 30px 0; font-size: 16px; line-height: 24px; color: #333333;">
                                Пожалуйста, уделите пару минут и ответьте на несколько вопросов. Это поможет нам стать лучше для вас.
                            </p>

                            <!-- Questions -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8f9fa; border-radius: 5px; margin-bottom: 30px;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <h3 style="margin: 0 0 15px 0; font-size: 18px; color: #333333;">Что мы хотим узнать:</h3>
                                        <ul style="margin: 0; padding-left: 20px; font-size: 14px; line-height: 24px; color: #666666;">
                                            <li>Насколько вы довольны нашим сервисом?</li>
                                            <li>Что вам нравится больше всего?</li>
                                            <li>Что мы можем улучшить?</li>
                                            <li>Порекомендуете ли вы нас друзьям?</li>
                                        </ul>
                                    </td>
                                </tr>
                            </table>

                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 20px;">
                                <tr>
                                    <td align="center">
                                        <a href="https://forms.google.com/your-form" style="display: inline-block; padding: 18px 50px; background-color: #667eea; color: #ffffff; text-decoration: none; border-radius: 5px; font-size: 18px; font-weight: bold;">Оставить отзыв</a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0; font-size: 14px; line-height: 22px; color: #999999; text-align: center;">
                                Заполнение формы займет не более 3 минут
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e0e0e0;">
                            <p style="margin: 0 0 10px 0; font-size: 14px; color: #666666;">
                                Спасибо за ваше время и доверие!
                            </p>
                            <p style="margin: 0; font-size: 12px; color: #999999;">
                                Команда коворкинга
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    },
]


def seed_templates():
    """Создает готовые email шаблоны в базе данных."""
    try:
        logger.info(f"Starting email templates seeding. Total templates: {len(EMAIL_TEMPLATES)}")

        def _seed_operation(session):
            created_count = 0
            updated_count = 0

            for template_data in EMAIL_TEMPLATES:
                # Проверяем, существует ли шаблон с таким именем
                existing_template = session.query(EmailTemplate).filter(
                    EmailTemplate.name == template_data["name"]
                ).first()

                if existing_template:
                    # Обновляем существующий шаблон
                    existing_template.description = template_data["description"]
                    existing_template.subject = template_data["subject"]
                    existing_template.html_content = template_data["html_content"]
                    existing_template.category = template_data["category"]
                    existing_template.updated_at = datetime.utcnow()
                    updated_count += 1
                    logger.info(f"Updated template: {template_data['name']}")
                else:
                    # Создаем новый шаблон
                    new_template = EmailTemplate(
                        name=template_data["name"],
                        description=template_data["description"],
                        subject=template_data["subject"],
                        html_content=template_data["html_content"],
                        unlayer_design=None,  # Простые HTML шаблоны без Unlayer дизайна
                        category=template_data["category"],
                        is_active=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    session.add(new_template)
                    created_count += 1
                    logger.info(f"Created template: {template_data['name']}")

            session.commit()
            return created_count, updated_count

        created, updated = DatabaseManager.safe_execute(_seed_operation)

        logger.info(f"Email templates seeding completed successfully!")
        logger.info(f"Created: {created} templates")
        logger.info(f"Updated: {updated} templates")
        logger.info(f"Total: {created + updated} templates processed")

        print(f"\n✅ Email templates seeding completed!")
        print(f"   - Created: {created} templates")
        print(f"   - Updated: {updated} templates")
        print(f"   - Total: {created + updated} templates in database\n")

        # Выводим список созданных шаблонов
        print("📧 Available email templates:")
        for i, template in enumerate(EMAIL_TEMPLATES, 1):
            print(f"   {i}. {template['name']} ({template['category']})")
        print()

    except Exception as e:
        logger.error(f"Error seeding email templates: {str(e)}", exc_info=True)
        print(f"\n❌ Error seeding email templates: {str(e)}\n")
        raise


if __name__ == "__main__":
    print("\n" + "="*60)
    print("EMAIL TEMPLATES SEEDING")
    print("="*60 + "\n")
    seed_templates()
