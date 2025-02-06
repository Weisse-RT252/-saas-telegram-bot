import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()

async def inspect_database():
    pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
    
    # Общая статистика
    total = await pool.fetchval("SELECT COUNT(*) FROM knowledge_base")
    print(f"Всего записей: {total}")
    
    # Примеры записей
    print("\nПоследние 50 записей:")
    records = await pool.fetch("SELECT * FROM knowledge_base ORDER BY id DESC LIMIT 50")
    for r in records:
        print(f"\nID: {r['id']}\nКоллекция: {r['collection']}\nКонтент:\n{r['content']}\n{'-'*40}")
    
    # Поиск дубликатов
    duplicates = await pool.fetch("""
        SELECT content, COUNT(*) 
        FROM knowledge_base 
        GROUP BY content 
        HAVING COUNT(*) > 1
    """)
    print(f"\nНайдено дубликатов: {len(duplicates)}")
    
    await pool.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(inspect_database()) 