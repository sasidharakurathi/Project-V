import aiosqlite
import os
from datetime import datetime

# Database path in the same directory as memory.py
DB_PATH = os.path.join(os.path.dirname(__file__), "vega_sessions.db")

async def init_db():
    """Initializes the episodic_memory table if it doesn't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS episodic_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                timestamp TEXT,
                user_input TEXT,
                vega_response TEXT,
                active_scene TEXT,
                summary TEXT
            )
        """)
        await db.commit()

async def save_memory(user_id, user_input, vega_response, active_scene=""):
    """
    Saves a conversation interaction to the episodic_memory table.
    Generates a one-line summary and uses the current ISO timestamp.
    """
    await init_db()
    
    # Generate summary: first 50 chars of input + " → " + first 50 chars of response
    summary = f"{user_input[:50]} → {vega_response[:50]}"
    timestamp = datetime.now().isoformat()
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO episodic_memory (user_id, timestamp, user_input, vega_response, active_scene, summary)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, timestamp, user_input, vega_response, active_scene, summary))
        await db.commit()

async def retrieve_relevant_memories(user_id, current_input, limit=5):
    """
    Retrieves up to 'limit' relevant memories for a user.
    Scores the last 20 memories by counting how many words from current_input appear in the summary.
    Returns a single formatted string.
    """
    await init_db()
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT timestamp, user_input, vega_response, summary 
            FROM episodic_memory 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 20
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            
    if not rows:
        return ""
    
    # Score memories
    input_words = current_input.lower().split()
    scored_memories = []
    
    for row in rows:
        summary_lower = row['summary'].lower()
        # Count how many words from current_input appear in the summary
        score = sum(1 for word in input_words if word in summary_lower)
        scored_memories.append((score, row))
        
    # Sort by score descending
    scored_memories.sort(key=lambda x: x[0], reverse=True)
    
    # Take top 'limit' (default 5)
    top_results = scored_memories[:limit]
    
    # Format results: "[timestamp]: user said X → vega said Y"
    formatted_memories = [
        f"[{row['timestamp']}]: user said {row['user_input']} → vega said {row['vega_response']}"
        for _, row in top_results
    ]
    
    return "\n".join(formatted_memories)
