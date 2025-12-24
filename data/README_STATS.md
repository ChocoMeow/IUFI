# IUFI Log Stats Documentation

We parsed IUFI log files to generate comprehensive statistics for user activity and global game trends. The output is saved in two JSON files: `user_stats.json` and `global_stats.json`.

## 1. User Statistics (`user_stats.json`)

This file stores detailed statistics for each individual user, keyed by their unique Discord User ID.

### Data Structure

```json
{
  "USER_ID": {
    "first_roll_date": "YYYY-MM-DD HH:MM:SS",
    "first_high_rarity_date": "YYYY-MM-DD HH:MM:SS",
    "first_high_rarity_card_id": "CARD_ID",
    "first_high_rarity_rarity": "RARITY_SYMBOL",
    "rolls_until_high_rarity": 42,
    "active_days_count": 100,
    "longest_streak": 10,
    "most_collected_card": "CARD_ID",
    "most_active_day": {
        "date": "YYYY-MM-DD",
        "count": 50
    },
    "highest_reaction_gallery_post": {
        "msg_id": "MESSAGE_ID",
        "count": 5
    },
    "room_command_counts": {
      "ROOM_NAME": {
        "COMMAND_NAME": 123
      }
    },
    "iufi_chat_msgs": 50,
    "game_room_msgs": 10,
    "iufi_chat_reactions_given": 5,
    "gallery_posts": 2,
    "gallery_reactions_received": 10,
    "cards_collected_count": 200,
    "rarity_counts": {
      "RARITY_SYMBOL": 150
    }
  }
}
```

### Field Descriptions

* **first_roll_date**: The timestamp of the user's first roll command.
* **first_high_rarity_...**: Details about the user's first collection of a high-rarity card (🦄 or 💫).
* **most_active_day**: The specific date where the user issued the highest number of commands.
* **highest_reaction_gallery_post**: The message ID and reaction count of the user's most popular gallery post.
* **game_room_msgs**: Number of messages sent in game rooms that were NOT commands (non-`q` messages).

---

## 2. Global Statistics (`global_stats.json`)

This file stores aggregated statistics across all users, rooms, and interactions found in the logs.

### Data Structure

```json
{
  "total_gallery_posts": 169,
  "total_gallery_reactions": 2413,
  "total_chat_msgs": 55973,
  "total_chat_reactions": 8765,
  "total_game_commands": 366993,
  "total_game_chat_msgs": 53421,
  "total_cards_collected": 107143,
  "most_collected_card_id": "06539",
  "active_days_count": 358,
  "total_rarity_counts": {
    "🥬": 65949,
    "🌸": 32521
  },
  "total_room_command_counts": {
    "ROOM_NAME": {
      "COMMAND_NAME": 5000
    }
  }
}
```

### Field Descriptions

* **total_game_commands**: The sum of all 'q' commands issued by all users in all rooms.
* **total_game_chat_msgs**: The sum of all non-command messages sent in game rooms.
* **total_room_command_counts**: A nested breakdown of every command used in every room globally.
* **active_days_count**: The number of unique days where any activity was recorded.
