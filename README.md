# IUFI

IUFI is a Discord bot designed for card collecting and mini-games specifically for the IU community. Built entirely with Python, this bot offers an engaging experience for users to collect cards and participate in fun mini-games.

## Screenshots
<img width="500" alt="Screenshot 2024-10-20 at 10 03 13 PM" src="https://github.com/user-attachments/assets/c6e315cf-2afa-48a4-a32a-bd4712f8b909">
<img width="400" alt="Screenshot 2024-10-20 at 10 05 59 PM" src="https://github.com/user-attachments/assets/76992956-ff11-481b-84bd-b957d8b3dfbb">+
<img width="400" alt="Screenshot 2024-10-20 at 10 05 13 PM" src="https://github.com/user-attachments/assets/09067d6a-705f-420f-b4c9-3b4b246ad52b">
<img width="400" alt="Screenshot 2024-10-20 at 10 03 48 PM" src="https://github.com/user-attachments/assets/0fa6b5de-35b8-45c2-ba5f-61a836f0ca29">
<img width="400" alt="Screenshot 2024-10-20 at 10 06 40 PM" src="https://github.com/user-attachments/assets/8d0be8f5-eaa0-4b15-9813-638c059ad8a6">


## Requirements
- Python 3.11 or above
- A `.env` file with the following variables:
```plaintext
TOKEN=DISCORD_BOT_TOKEN
MONGODB_URL=MONGODB_URL
MONGODB_NAME=MONGODB_NAME
```
- A `settings.json` file containing the bot settings. This file is pre-filled with values based on the IUCord server but can be modified as needed.

## Installation
1. Clone this repository:
```
git clone https://github.com/ChocoMeow/IUFI.git
```

2. Navigate to the project directory:
```
cd IUFI
```


3. Install the required Python packages. It is recommended to use a virtual environment:
```
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```

4. Create a .env file in the root directory and add your Discord bot token and MongoDB details.
5. Modify the settings.json file as needed to customize your bot settings.

## Running the Bot
To start the bot, run the following command:
```
python main.py
```

## Auto-Created Folders
Upon starting the bot, the following folders will be automatically created in the root directory:
- **images:** This folder stores card images. Inside, you should create your own category folders that match the configuration in your `settings.json`.
- **newImages:** Place any new card images you want to add to the bot in this folder. The bot will automatically update the database and move the images to the correct category folder in the images folder. Ensure that new card images follow the naming format category#.webp (e.g., common1.webp, common2.webp, rare1.webp, etc.).
- **musicTracks:** This folder will automatically download music tracks using `ytlib` when players are participating in the music quiz.


## Contributing
Contributions are welcome! If you have suggestions for improvements or features, feel free to submit a pull request.





