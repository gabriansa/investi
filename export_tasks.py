import os
import csv
import json
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def export_tasks_to_csv():
    """Export tasks table to CSV file."""
    DATABASE_URL = os.getenv('DATABASE_URL')
    output_file = 'tasks_export.csv'
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        rows = await conn.fetch("SELECT * FROM tasks ORDER BY created_at")
        
        if not rows:
            print("No tasks found in database")
            return
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'task_id', 'telegram_user_id', 'created_at', 'ticker_symbol',
                'role', 'description', 'task_datetime', 'is_active',
                'trigger_type', 'trigger_config', 'related_note_ids',
                'related_task_ids', 'related_watchlist_ids'
            ])
            
            for row in rows:
                writer.writerow([
                    row['task_id'],
                    row['telegram_user_id'],
                    row['created_at'],
                    row['ticker_symbol'],
                    row['role'],
                    row['description'],
                    row['task_datetime'],
                    row['is_active'],
                    row['trigger_type'],
                    json.dumps(row['trigger_config']) if row['trigger_config'] else None,
                    json.dumps(row['related_note_ids']) if row['related_note_ids'] else None,
                    json.dumps(row['related_task_ids']) if row['related_task_ids'] else None,
                    json.dumps(row['related_watchlist_ids']) if row['related_watchlist_ids'] else None,
                ])
        
        print(f"Exported {len(rows)} tasks to {output_file}")
    
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(export_tasks_to_csv())

