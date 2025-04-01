from flask import Flask, render_template, request, jsonify, session
from wordconnect import get_starting_word, get_ai_word_and_clue, check_word_guess, DIFFICULTY_LEVELS
import time
import sqlite3
from datetime import datetime
import uuid
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

def init_db():
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

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5004) 