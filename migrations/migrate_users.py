#!/usr/bin/env python3
"""
Скрипт миграции пользователей из db.sqlite3 в data/coworking.db
"""

import sqlite3
import sys
from datetime import datetime

def check_conflicts(source_conn, target_conn):
    """Проверяет конфликты по telegram_id"""
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()
    
    # Получаем все telegram_id из источника
    source_cursor.execute("SELECT tg_id FROM users")
    source_tg_ids = set(row[0] for row in source_cursor.fetchall())
    
    # Получаем все telegram_id из целевой БД
    target_cursor.execute("SELECT telegram_id FROM users")
    target_tg_ids = set(row[0] for row in target_cursor.fetchall())
    
    # Находим пересечения
    conflicts = source_tg_ids.intersection(target_tg_ids)
    
    if conflicts:
        print(f"ВНИМАНИЕ: Найдены конфликты по telegram_id:")
        for tg_id in sorted(conflicts):
            # Получаем информацию о пользователе из источника
            source_cursor.execute("SELECT name, tg_username FROM users WHERE tg_id = ?", (tg_id,))
            source_user = source_cursor.fetchone()
            
            # Получаем информацию о пользователе из целевой БД
            target_cursor.execute("SELECT full_name, username FROM users WHERE telegram_id = ?", (tg_id,))
            target_user = target_cursor.fetchone()
            
            print(f"  telegram_id: {tg_id}")
            print(f"    Источник: {source_user[0]} (@{source_user[1]})")
            print(f"    Целевая БД: {target_user[0]} (@{target_user[1]})")
            print()
    
    return conflicts

def migrate_users(source_db_path, target_db_path, skip_conflicts=False):
    """Выполняет миграцию пользователей"""
    
    # Подключаемся к базам данных
    try:
        source_conn = sqlite3.connect(source_db_path)
        target_conn = sqlite3.connect(target_db_path)
        
        print(f"Подключение к источнику: {source_db_path}")
        print(f"Подключение к целевой БД: {target_db_path}")
        
        # Проверяем конфликты
        conflicts = check_conflicts(source_conn, target_conn)
        
        if conflicts and not skip_conflicts:
            print(f"\nОбнаружено {len(conflicts)} конфликтов.")
            print("Запустите скрипт с параметром --skip-conflicts для пропуска конфликтующих записей")
            return False
        
        # Получаем пользователей из источника
        source_cursor = source_conn.cursor()
        source_cursor.execute("""
            SELECT id, reg_date, tg_id, tg_username, name, contact, email, 
                   successful_bookings, language_code 
            FROM users 
            ORDER BY id
        """)
        
        source_users = source_cursor.fetchall()
        print(f"\nНайдено {len(source_users)} пользователей в источнике")
        
        # Подготавливаем запрос для вставки
        target_cursor = target_conn.cursor()
        
        migrated_count = 0
        skipped_count = 0
        
        for user in source_users:
            (id_, reg_date, tg_id, tg_username, name, contact, email, 
             successful_bookings, language_code) = user
            
            # Пропускаем конфликтующие записи
            if skip_conflicts and tg_id in conflicts:
                skipped_count += 1
                continue
            
            # Подготавливаем данные для вставки
            try:
                target_cursor.execute("""
                    INSERT INTO users (
                        telegram_id, first_join_time, full_name, phone, email,
                        username, successful_bookings, language_code, 
                        invited_count, reg_date, agreed_to_terms, avatar, referrer_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tg_id,                           # telegram_id
                    reg_date,                        # first_join_time (используем reg_date)
                    name,                           # full_name
                    contact,                        # phone
                    email,                          # email
                    tg_username,                    # username
                    successful_bookings or 0,       # successful_bookings
                    language_code or 'ru',          # language_code (по умолчанию 'ru')
                    0,                              # invited_count (по умолчанию 0)
                    reg_date,                       # reg_date
                    True,                           # agreed_to_terms (по умолчанию TRUE)
                    None,                           # avatar (NULL)
                    None                            # referrer_id (NULL)
                ))
                migrated_count += 1
                
            except sqlite3.IntegrityError as e:
                print(f"Ошибка при вставке пользователя {tg_id}: {e}")
                skipped_count += 1
                continue
        
        # Сохраняем изменения
        target_conn.commit()
        
        print(f"\nМиграция завершена:")
        print(f"  Перенесено: {migrated_count} пользователей")
        print(f"  Пропущено: {skipped_count} пользователей")
        
        # Проверяем итоговое количество
        target_cursor.execute("SELECT COUNT(*) FROM users")
        total_users = target_cursor.fetchone()[0]
        print(f"  Всего в целевой БД: {total_users} пользователей")
        
        return True
        
    except sqlite3.Error as e:
        print(f"Ошибка базы данных: {e}")
        return False
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        return False
    finally:
        if 'source_conn' in locals():
            source_conn.close()
        if 'target_conn' in locals():
            target_conn.close()

def main():
    source_db = "db.sqlite3"
    target_db = "data/coworking.db"
    
    skip_conflicts = "--skip-conflicts" in sys.argv
    
    print("=" * 60)
    print("МИГРАЦИЯ ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 60)
    print(f"Источник: {source_db}")
    print(f"Целевая БД: {target_db}")
    print(f"Пропуск конфликтов: {'Да' if skip_conflicts else 'Нет'}")
    print("=" * 60)
    
    success = migrate_users(source_db, target_db, skip_conflicts)
    
    if success:
        print("\n✅ Миграция выполнена успешно!")
    else:
        print("\n❌ Миграция завершилась с ошибками")
        sys.exit(1)

if __name__ == "__main__":
    main()