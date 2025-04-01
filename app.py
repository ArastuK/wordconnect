from flask import Flask, render_template, request, jsonify, session
from wordconnect import get_starting_word, get_ai_word_and_clue, check_word_guess, DIFFICULTY_LEVELS
import time
import sqlite3
from datetime import datetime
import uuid
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')  # Use environment variable for secret key

def init_db():
    try:
        conn = sqlite3.connect('game.db')
        c = conn.cursor()
        
        # Create high scores table
        c.execute('''CREATE TABLE IF NOT EXISTS high_scores
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      player_name TEXT NOT NULL,
                      score INTEGER NOT NULL,
                      difficulty TEXT NOT NULL,
                      date TEXT NOT NULL)''')
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database initialization error: {e}")

def save_high_score(player_name, score, difficulty):
    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute('INSERT INTO high_scores (player_name, score, difficulty, date) VALUES (?, ?, ?, ?)',
              (player_name, score, difficulty, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

def get_high_scores(limit=10):
    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute('SELECT player_name, score, difficulty, date FROM high_scores ORDER BY score DESC LIMIT ?', (limit,))
    scores = c.fetchall()
    conn.close()
    return scores

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
    """Start a new game and get the first word and clue."""
    try:
        # Clear any existing game state
        session.clear()
        
        # Get and validate difficulty level
        difficulty = request.json.get('difficulty', '1')
        if difficulty not in DIFFICULTY_LEVELS:
            return jsonify({'error': 'Invalid difficulty level'}), 400
            
        difficulty_settings = DIFFICULTY_LEVELS[difficulty]
        
        # Get starting word and clue
        previous_word = get_starting_word()
        if not previous_word:
            return jsonify({'error': 'Failed to generate starting word'}), 500
            
        word_to_guess, clue = get_ai_word_and_clue(
            previous_word,
            difficulty_settings['prompt_modifier'],
            difficulty_settings['clue_style'],
            [],  # Empty word history for first word
            difficulty_settings['min_letters'],
            difficulty_settings['max_letters'],
            difficulty_settings['word_relation']
        )
        
        if not word_to_guess or not clue:
            return jsonify({'error': 'Failed to generate word and clue'}), 500
            
        # Store game state in session with timestamp
        session['current_word'] = word_to_guess
        session['previous_word'] = previous_word
        session['clue'] = clue
        session['score'] = 0
        session['word_history'] = [previous_word]  # Initialize with the first connected word
        session['difficulty'] = difficulty
        session['start_time'] = time.time()
        session['game_active'] = True
        session['last_activity'] = time.time()
        
        return jsonify({
            'word': word_to_guess,
            'clue': clue,
            'previous_word': previous_word,
            'score': 0,
            'time_limit': difficulty_settings['time_limit']
        })
        
    except Exception as e:
        print(f"Error in start_game: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/check_guess', methods=['POST'])
def check_guess():
    try:
        # Check if game is active
        if not session.get('game_active'):
            return jsonify({
                'error': "No active game session. Please start a new game.",
                'game_over': True
            }), 400

        # Update last activity
        session['last_activity'] = time.time()
        
        data = request.get_json()
        guess = data.get('guess', '').strip().lower()
        is_timeout = data.get('is_timeout', False)
        
        # Get current game state
        current_word = session.get('current_word')
        previous_word = session.get('previous_word')
        word_history = session.get('word_history', [])
        score = session.get('score', 0)
        difficulty = session.get('difficulty')
        start_time = session.get('start_time', 0)
        
        # Validate game state
        if not all([current_word, previous_word, difficulty]):
            session['game_active'] = False
            return jsonify({
                'error': "Invalid game state. Please start a new game.",
                'game_over': True
            }), 400

        # Check if time is up
        time_limit = DIFFICULTY_LEVELS[difficulty]['time_limit']
        elapsed_time = time.time() - start_time
        
        if elapsed_time > time_limit or is_timeout:
            session['game_active'] = False
            return jsonify({
                'correct': False,
                'message': f"Time's up! The word was: {current_word.upper()}",
                'correct_word': current_word.upper(),
                'score': score,
                'word_history': word_history,
                'game_over': True
            })

        # Validate guess length against difficulty settings
        if len(guess) < DIFFICULTY_LEVELS[difficulty]['min_letters'] or \
           len(guess) > DIFFICULTY_LEVELS[difficulty]['max_letters']:
            return jsonify({
                'error': f"Word must be between {DIFFICULTY_LEVELS[difficulty]['min_letters']} and {DIFFICULTY_LEVELS[difficulty]['max_letters']} letters long"
            }), 400

        # Check the guess
        if check_word_guess(guess, current_word):
            score += 1
            session['score'] = score
            
            # Get next word with proper difficulty settings
            difficulty_settings = DIFFICULTY_LEVELS[difficulty]
            next_word, next_clue = get_ai_word_and_clue(
                current_word,
                difficulty_settings['prompt_modifier'],
                difficulty_settings['clue_style'],
                word_history,
                difficulty_settings['min_letters'],
                difficulty_settings['max_letters'],
                difficulty_settings['word_relation']
            )
            
            if not next_word or next_word in word_history:
                session['game_active'] = False
                # Add the correctly guessed word to history before ending
                word_history.append(current_word)
                session['word_history'] = word_history
                return jsonify({
                    'correct': True,
                    'message': 'Victory! You completed the word chain!',
                    'score': score,
                    'word_history': word_history,
                    'game_over': True
                })
            
            # Add the correctly guessed word to history
            word_history.append(current_word)
            
            # Update session with new word
            session['previous_word'] = current_word
            session['current_word'] = next_word
            session['clue'] = next_clue
            session['word_history'] = word_history
            session['start_time'] = time.time()
            
            return jsonify({
                'correct': True,
                'message': 'Correct!',
                'score': score,
                'previous_word': current_word.upper(),
                'clue': next_clue,
                'time_limit': difficulty_settings['time_limit'],
                'game_over': False
            })
        
        # Wrong guess
        session['game_active'] = False
        return jsonify({
            'correct': False,
            'message': f'Game Over! The word was: {current_word.upper()}',
            'correct_word': current_word.upper(),
            'score': score,
            'word_history': word_history,
            'game_over': True
        })
        
    except Exception as e:
        print(f"Error in check_guess: {str(e)}")
        return jsonify({
            'error': "An error occurred while checking your guess. Please try again.",
            'game_over': True,
            'score': session.get('score', 0),
            'word_history': session.get('word_history', [])
        }), 500

# Initialize database on startup
init_db()

# For Vercel deployment
app = app

if __name__ == '__main__':
    app.run(debug=True, port=5005) 