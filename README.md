# AI WordConnect Game

A fun and engaging word chain game powered by Google's Gemini AI. Players connect words through creative clues and try to build the longest chain possible.

## Features

- Three difficulty levels (Easy, Medium, Hard)
- AI-generated word connections and clues
- Real-time scoring system
- High score tracking
- Beautiful UI with light/dark theme support
- Sound effects and animations
- Responsive design

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/wordconnect.git
cd wordconnect
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory and add your Google API key:
```
GOOGLE_API_KEY=your_api_key_here
```

5. Run the application:
```bash
python app.py
```

6. Open your browser and navigate to `http://localhost:5004`

## How to Play

1. Select a difficulty level
2. Read the AI-generated clue
3. Guess the word within the time limit
4. Keep the chain going as long as possible
5. Try to beat your high score!

## Technologies Used

- Python
- Flask
- Google Gemini AI
- SQLite
- HTML/CSS/JavaScript
- Tailwind CSS

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 