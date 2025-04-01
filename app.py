from flask import Flask, render_template, request, jsonify, session
from wordconnect import get_starting_word, get_ai_word_and_clue, check_word_guess, DIFFICULTY_LEVELS
import time
from datetime import datetime
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# MongoDB connection
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGODB_URI)
db = client.wordconnect
high_scores = db.high_scores

def init_db():
    try:
        # Create indexes for better query performance
        high_scores.create_index([("score", -1)])
    except Exception as e:
        print(f"Database initialization error: {e}")

def save_high_score(player_name, score, difficulty):
    try:
        high_scores.insert_one({
            'player_name': player_name,
            'score': score,
            'difficulty': difficulty,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        print(f"Error saving score: {e}")

def get_high_scores(limit=10):
    try:
        return list(high_scores.find(
            {},
            {'_id': 0, 'player_name': 1, 'score': 1, 'difficulty': 1, 'date': 1}
        ).sort('score', -1).limit(limit))
    except Exception as e:
        print(f"Error getting high scores: {e}")
        return []

@app.route('/')
def index():
    # Clear the session when returning to home screen
    session.clear()
    high_scores = get_high_scores()
    return render_template('index.html', 
                         difficulties=DIFFICULTY_LEVELS, 
                         high_scores=high_scores)

@app.route('/save_score', methods=['POST'])
def save_score():
    try:
        data = request.get_json()
        player_name = data.get('player_name', 'Anonymous')
        score = data.get('score', 0)
        difficulty = data.get('difficulty', 'easy')
        
        save_high_score(player_name, score, difficulty)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error saving score: {str(e)}")
        return jsonify({'error': "Failed to save score"}), 500

@app.route('/start_game', methods=['POST'])
def start_game():
    difficulty = request.json.get('difficulty')
    if difficulty not in DIFFICULTY_LEVELS:
        return jsonify({'error': 'Invalid difficulty'}), 400
    
    # Initialize game state
    session['score'] = 0
    session['word_history'] = []
    session['difficulty'] = difficulty
    session['start_time'] = time.time()
    
    # Get starting word
    previous_word = get_starting_word()
    word_to_guess, current_clue = get_ai_word_and_clue(
        previous_word,
        DIFFICULTY_LEVELS[difficulty]['prompt_modifier'],
        DIFFICULTY_LEVELS[difficulty]['clue_style'],
        [],
        DIFFICULTY_LEVELS[difficulty]['min_letters'],
        DIFFICULTY_LEVELS[difficulty]['max_letters'],
        DIFFICULTY_LEVELS[difficulty]['word_relation']
    )
    
    if not word_to_guess or not current_clue:
        return jsonify({'error': 'Failed to get starting word'}), 500
    
    session['previous_word'] = previous_word
    session['current_word'] = word_to_guess
    session['current_clue'] = current_clue
    session['word_history'].append(word_to_guess)
    
    return jsonify({
        'previous_word': previous_word.upper(),
        'clue': current_clue,
        'time_limit': DIFFICULTY_LEVELS[difficulty]['time_limit']
    })

@app.route('/check_guess', methods=['POST'])
def check_guess():
    try:
        data = request.get_json()
        guess = data.get('guess', '').strip().lower()
        
        # Get current game state
        current_word = session.get('current_word', '')
        word_history = session.get('word_history', [])
        score = session.get('score', 0)
        difficulty = session.get('difficulty', 'easy')
        
        if not current_word:
            return jsonify({
                'correct': False,
                'message': "Game session expired. Please start a new game.",
                'score': score,
                'word_history': word_history
            })

        # Check if time is up
        time_limit = DIFFICULTY_LEVELS[difficulty]['time_limit']
        elapsed_time = time.time() - session['start_time']
        if elapsed_time > time_limit:
            return jsonify({
                'correct': False,
                'message': "Time's up!",
                'correct_word': current_word.upper(),
                'score': score,
                'word_history': word_history,
                'game_over': True
            })

        # Check the guess
        if check_word_guess(guess, current_word):
            score += 1
            session['score'] = score
            
            # Get next word with proper difficulty settings
            previous_word = current_word
            next_word, next_clue = get_ai_word_and_clue(
                previous_word,
                DIFFICULTY_LEVELS[difficulty]['prompt_modifier'],
                DIFFICULTY_LEVELS[difficulty]['clue_style'],
                word_history,
                DIFFICULTY_LEVELS[difficulty]['min_letters'],
                DIFFICULTY_LEVELS[difficulty]['max_letters'],
                DIFFICULTY_LEVELS[difficulty]['word_relation']
            )
            
            if not next_word or next_word in word_history:
                return jsonify({
                    'correct': True,
                    'message': 'Victory! The AI couldn\'t think of another word!',
                    'score': score,
                    'word_history': word_history,
                    'game_over': True
                })
            
            # Update session with new word
            session['previous_word'] = previous_word
            session['current_word'] = next_word
            session['current_clue'] = next_clue
            session['word_history'].append(next_word)
            session['start_time'] = time.time()
            
            return jsonify({
                'correct': True,
                'message': 'Correct!',
                'score': score,
                'previous_word': previous_word.upper(),
                'clue': next_clue,
                'game_over': False
            })
        
        return jsonify({
            'correct': False,
            'message': 'Game Over!',
            'correct_word': current_word.upper(),
            'score': score,
            'word_history': word_history,
            'game_over': True
        })
        
    except Exception as e:
        print(f"Error in check_guess: {str(e)}")
        return jsonify({
            'error': "An error occurred while processing your guess."
        })

# Initialize database on startup
init_db()

# For Vercel deployment
app = app

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5005) 