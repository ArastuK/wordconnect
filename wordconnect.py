import google.generativeai as genai
import os
import time
import threading
import sys
import select # For non-blocking input check (more reliable timer)
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
API_KEY = os.getenv('GOOGLE_API_KEY')

if not API_KEY:
    print("Error: GOOGLE_API_KEY not set in environment variables.")
    print("Please set your Google API Key in the .env file.")
    sys.exit(1)

# Configure the API
genai.configure(api_key=API_KEY)

# --- Constants ---
# Safety settings for Gemini (adjust as needed)
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

# Generation configuration (adjust temperature for creativity vs. predictability)
GENERATION_CONFIG = {
    "temperature": 0.7,  # Lower for more predictable, higher for more creative
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 100,  # Increased for longer sentences
}

# Initialize the model
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=GENERATION_CONFIG,
    safety_settings=SAFETY_SETTINGS
)

# Game settings
TIME_LIMIT_SECONDS = 15  # Time player has to answer

# Word list for fallback and validation
word_list = [
    # Nature
    "sun", "moon", "star", "wind", "rain", "tree", "leaf", "wave", "sand", "snow",
    "cloud", "storm", "river", "ocean", "mountain", "forest", "flower", "grass", "desert", "island",
    # Elements
    "fire", "water", "earth", "air", "light", "dark", "gold", "iron", "ice", "mist",
    "steam", "smoke", "dust", "metal", "crystal", "stone", "wood", "flame", "spark", "frost",
    # Emotions
    "love", "hope", "joy", "dream", "smile", "laugh", "peace", "calm", "wish", "trust",
    "fear", "rage", "pride", "shame", "grief", "zeal", "care", "hate", "pity", "pride",
    # Actions
    "jump", "spin", "dance", "sing", "flow", "grow", "rise", "fall", "soar", "dive",
    "swim", "run", "walk", "fly", "leap", "roll", "sway", "bend", "twist", "turn",
    # Qualities
    "soft", "warm", "cool", "swift", "bold", "wise", "pure", "wild", "free", "true",
    "bright", "dark", "sharp", "smooth", "rough", "light", "heavy", "fast", "slow", "deep",
    # Time
    "dawn", "dusk", "noon", "night", "time", "hour", "year", "day", "age", "now",
    "week", "month", "season", "moment", "past", "future", "today", "tomorrow", "yesterday", "eternity",
    # Space
    "star", "moon", "void", "path", "road", "gate", "door", "room", "zone", "spot",
    "space", "world", "earth", "sky", "land", "sea", "shore", "coast", "field", "garden",
    # Colors
    "blue", "gold", "pink", "jade", "ruby", "rose", "teal", "sage", "rust", "coal",
    "crimson", "azure", "amber", "ivory", "ebony", "scarlet", "emerald", "sapphire", "coral", "pearl",
    # Sounds
    "song", "beat", "tune", "hum", "buzz", "ring", "echo", "tone", "note", "drum",
    "chime", "whisper", "shout", "roar", "sigh", "laugh", "cry", "call", "sound", "voice",
    # Objects
    "book", "pen", "lamp", "door", "wall", "roof", "floor", "chair", "table", "desk",
    "clock", "phone", "glass", "paper", "cloth", "rope", "tool", "key", "lock", "box",
    # Animals
    "bird", "fish", "lion", "bear", "wolf", "deer", "frog", "snake", "duck", "goat",
    "cat", "dog", "horse", "sheep", "cow", "pig", "rabbit", "fox", "owl", "hawk",
    # Food
    "bread", "fruit", "meat", "fish", "rice", "corn", "bean", "nut", "egg", "milk",
    "cake", "soup", "pie", "tea", "wine", "beer", "juice", "salt", "sugar", "honey"
]

DIFFICULTY_LEVELS = {
    "1": {
        "name": "Easy",
        "prompt_modifier": "Use a common, simple word that can be used in everyday sentences.",
        "time_limit": 20,
        "clue_style": "very descriptive and obvious",
        "min_letters": 3,
        "max_letters": 5,
        "word_relation": "directly or indirectly related"
    },
    "2": {
        "name": "Medium",
        "prompt_modifier": "Use a moderately common word that requires some thinking.",
        "time_limit": 15,
        "clue_style": "moderately descriptive with some hints",
        "min_letters": 3,
        "max_letters": 5,
        "word_relation": "directly or indirectly related"
    },
    "3": {
        "name": "Hard",
        "prompt_modifier": "Use a less common but still understandable word.",
        "time_limit": 12,
        "clue_style": "minimal with subtle hints",
        "min_letters": 3,
        "max_letters": 5,
        "word_relation": "directly or indirectly related"
    }
}

# --- Global Variables ---
player_input = None
input_event = threading.Event()  # To signal when input is received

# --- Helper Functions ---

def display_countdown(timeout):
    """Displays a countdown timer while waiting for input."""
    start_time = time.time()
    while time.time() - start_time < timeout and not input_event.is_set():
        remaining = int(timeout - (time.time() - start_time))
        print(f"Time remaining: {remaining}s")
        time.sleep(1)

def get_timed_input(prompt, timeout):
    """Gets input from the player within a specified time limit."""
    global player_input, input_event
    player_input = None
    input_event.clear()

    # Start input thread
    input_thread = threading.Thread(target=wait_for_input, args=(prompt,))
    input_thread.daemon = True
    input_thread.start()

    # Wait for input or timeout
    input_event.wait(timeout)

    if player_input is not None:
        return player_input
    else:
        print("\nTime's up!")
        return None

def wait_for_input(prompt):
    """Target function for the input thread."""
    global player_input, input_event
    try:
        player_input = input(prompt)
    except EOFError:
        player_input = None
    input_event.set()

def ask_gemini(prompt_text, is_clue=False):
    """Sends a prompt to Gemini and returns the text response."""
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=GENERATION_CONFIG,
            safety_settings=SAFETY_SETTINGS
        )
        response = model.generate_content(prompt_text)
        
        # Handle potential blocks or empty responses
        if not response.parts:
            if response.prompt_feedback.block_reason:
                print(f"\n[AI Error] Blocked: {response.prompt_feedback.block_reason}")
            else:
                print("\n[AI Error] Received an empty response.")
            return None

        # Get the raw response
        ai_response = response.text.strip()
        
        if is_clue:
            # For clues, return the full sentence
            return ai_response
        else:
            # For words, clean up and get the first word
            # Remove punctuation and extra whitespace, get the first word if multiple given
            cleaned_response = ''.join(c for c in ai_response if c.isalnum() or c.isspace())
            cleaned_response = cleaned_response.split()[0] if cleaned_response else None
            return cleaned_response.lower() if cleaned_response else None

    except Exception as e:
        print(f"\n[AI Error] An error occurred while contacting Gemini: {e}")
        return None

def get_letter_hints(word, num_hints):
    """Generates letter hints for the word based on the number of hints requested."""
    import random
    word_length = len(word)
    
    # Ensure we don't try to show more hints than there are letters
    num_hints = min(num_hints, word_length)
    
    # Create a list of positions to show
    positions = random.sample(range(word_length), num_hints)
    
    # Create the hint string with underscores for hidden letters
    hint = list('_' * word_length)
    for pos in positions:
        hint[pos] = word[pos]
    
    return ''.join(hint)

def get_contextual_clue(word, model, difficulty_settings=None):
    # Create a prompt that asks for a contextual clue
    prompt = f"""Generate a single sentence that uses the word '{word}' in context, but replace the word with <BLANK>. 
    The sentence should be natural and help the player guess the word.
    The sentence should be clear and concise.
    Do not use the word or any variations of it elsewhere in the sentence.
    Format your response as a single sentence with <BLANK> where the word should be."""

    try:
        response = model.generate_content(prompt)
        clue = response.text.strip()
        
        # Get letter hints based on difficulty
        hint = '_' * len(word)  # Default to all hidden
        if difficulty_settings:
            if difficulty_settings['name'] == 'Easy':
                hint = get_letter_hints(word, 2)  # Show 2 letters for Easy
            elif difficulty_settings['name'] == 'Medium':
                hint = get_letter_hints(word, 1)  # Show 1 letter for Medium
        
        # Create properly spaced hint
        masked_word = ' '.join(hint)
        clue = clue.replace('<BLANK>', f'<span class="hidden-word">{masked_word}</span>')
        
        # Ensure the clue ends with proper punctuation
        if not clue[-1] in '.!?':
            clue += '.'
            
        return clue
        
    except Exception as e:
        print(f"Error generating clue: {e}")
        # Create a more descriptive fallback clue with proper hints
        hint = '_' * len(word)
        if difficulty_settings:
            if difficulty_settings['name'] == 'Easy':
                hint = get_letter_hints(word, 2)
            elif difficulty_settings['name'] == 'Medium':
                hint = get_letter_hints(word, 1)
        return f'Think of a {len(word)}-letter word that means <span class="hidden-word">{" ".join(hint)}</span>.'

def get_ai_word_and_clue(previous_word, prompt_modifier, clue_style, word_history, min_letters, max_letters, word_relation):
    """Get a word and clue from the AI with improved uniqueness checks."""
    max_attempts = 5  # Increased from 3 to 5 attempts
    
    # Get difficulty settings from the prompt modifier
    difficulty_settings = None
    for level in DIFFICULTY_LEVELS.values():
        if level['prompt_modifier'] == prompt_modifier:
            difficulty_settings = level
            break
    
    for attempt in range(max_attempts):
        try:
            # Create a more specific prompt for word selection
            prompt = f"""Generate a single word that:
1. Is different from all these previously used words: {', '.join(word_history)}
2. Is different from the previous word: {previous_word}
3. Is not a variation or semantically close to any previous words
4. Has a logical connection to the previous word: {previous_word}
5. Is between {min_letters} and {max_letters} letters long
6. Is a valid English word
7. Has a clear relationship with the previous word ({word_relation})

{prompt_modifier}

Return ONLY the word, nothing else."""

            response = model.generate_content(prompt)
            new_word = response.text.strip().lower()
            
            # Basic validation
            if not new_word or not new_word.isalpha():
                print(f"Attempt {attempt + 1}: Invalid word format")
                continue
                
            if len(new_word) < min_letters or len(new_word) > max_letters:
                print(f"Attempt {attempt + 1}: Word length outside range")
                continue
                
            # Check for direct repetition
            if new_word in word_history or new_word == previous_word:
                print(f"Attempt {attempt + 1}: Word already used")
                continue
                
            # Check for similarity with previous words (more lenient)
            too_similar = False
            for word in word_history:
                # Check for shared letters (if same length)
                if len(word) == len(new_word):
                    shared_letters = sum(1 for a, b in zip(word, new_word) if a == b)
                    if shared_letters / len(word) > 0.8:  # Increased from 0.7 to 0.8
                        too_similar = True
                        break
                # Check for similar length words
                elif abs(len(word) - len(new_word)) <= 2:
                    shared_letters = sum(1 for a, b in zip(word, new_word) if a == b)
                    if shared_letters / min(len(word), len(new_word)) > 0.7:  # Increased from 0.6 to 0.7
                        too_similar = True
                        break
            if too_similar:
                print(f"Attempt {attempt + 1}: Word too similar to previous words")
                continue
            
            # Get the clue using get_contextual_clue with difficulty settings
            clue = get_contextual_clue(new_word, model, difficulty_settings)
            if not clue:
                print(f"Attempt {attempt + 1}: Failed to generate clue")
                continue
                
            return new_word, clue
            
        except Exception as e:
            print(f"Attempt {attempt + 1}: Error - {str(e)}")
            continue
    
    print("All attempts failed to generate a valid word and clue")
    return None, None

def check_word_guess(guess, correct_word):
    """Checks if the player's guess matches the correct word."""
    return guess.strip().lower() == correct_word.lower()

def get_starting_word():
    """Gets a random starting word for the game."""
    # Expanded list of starting words organized by themes
    starting_words = {
        "nature": ["sun", "moon", "star", "wind", "rain", "tree", "leaf", "wave", "sand", "snow", 
                  "cloud", "storm", "river", "ocean", "mountain", "forest", "flower", "grass", "desert", "island"],
        "elements": ["fire", "water", "earth", "air", "light", "dark", "gold", "iron", "ice", "mist",
                    "steam", "smoke", "dust", "metal", "crystal", "stone", "wood", "flame", "spark", "frost"],
        "emotions": ["love", "hope", "joy", "dream", "smile", "laugh", "peace", "calm", "wish", "trust",
                    "fear", "rage", "pride", "shame", "grief", "zeal", "care", "hate", "pity", "pride"],
        "actions": ["jump", "spin", "dance", "sing", "flow", "grow", "rise", "fall", "soar", "dive",
                   "swim", "run", "walk", "fly", "leap", "roll", "sway", "bend", "twist", "turn"],
        "qualities": ["soft", "warm", "cool", "swift", "bold", "wise", "pure", "wild", "free", "true",
                     "bright", "dark", "sharp", "smooth", "rough", "light", "heavy", "fast", "slow", "deep"],
        "time": ["dawn", "dusk", "noon", "night", "time", "hour", "year", "day", "age", "now",
                "week", "month", "season", "moment", "past", "future", "today", "tomorrow", "yesterday", "eternity"],
        "space": ["star", "moon", "void", "path", "road", "gate", "door", "room", "zone", "spot",
                 "space", "world", "earth", "sky", "land", "sea", "shore", "coast", "field", "garden"],
        "colors": ["blue", "gold", "pink", "jade", "ruby", "rose", "teal", "sage", "rust", "coal",
                  "crimson", "azure", "amber", "ivory", "ebony", "scarlet", "emerald", "sapphire", "coral", "pearl"],
        "sounds": ["song", "beat", "tune", "hum", "buzz", "ring", "echo", "tone", "note", "drum",
                  "chime", "whisper", "shout", "roar", "sigh", "laugh", "cry", "call", "sound", "voice"],
        "objects": ["book", "pen", "lamp", "door", "wall", "roof", "floor", "chair", "table", "desk",
                   "clock", "phone", "glass", "paper", "cloth", "rope", "tool", "key", "lock", "box"],
        "animals": ["bird", "fish", "lion", "bear", "wolf", "deer", "frog", "snake", "duck", "goat",
                   "cat", "dog", "horse", "sheep", "cow", "pig", "rabbit", "fox", "owl", "hawk"],
        "food": ["bread", "fruit", "meat", "fish", "rice", "corn", "bean", "nut", "egg", "milk",
                "cake", "soup", "pie", "tea", "wine", "beer", "juice", "salt", "sugar", "honey"]
    }
    
    try:
        # Select a random theme and then a random word from that theme
        theme = random.choice(list(starting_words.keys()))
        word = random.choice(starting_words[theme])
        
        # Validate the word
        if not word or not word.isalpha():
            raise ValueError("Invalid word generated")
            
        return word.lower()
        
    except Exception as e:
        print(f"Error in get_starting_word: {str(e)}")
        # Fallback to a simple list of reliable starting words
        fallback_words = ["sun", "moon", "star", "wind", "rain", "tree", "leaf", "wave", "sand", "snow"]
        return random.choice(fallback_words)

def validate_word(word, previous_word, word_history, min_letters, max_letters):
    """Validate a word based on game rules."""
    # Basic validation
    if not word or not word.isalpha():
        return False
        
    # Check length
    if len(word) < min_letters or len(word) > max_letters:
        return False
        
    # Check if word is already used
    if word in word_history or word == previous_word:
        return False
        
    # Check for anagrams
    if sorted(word) == sorted(previous_word):
        return False
        
    # Check for similarity with previous word
    shared_letters = sum(1 for a, b in zip(word, previous_word) if a == b)
    max_shared = max(len(word), len(previous_word))
    similarity_ratio = shared_letters / max_shared
    
    # More lenient similarity check
    if similarity_ratio > 0.8:  # Allow up to 80% similarity
        return False
        
    return True

# --- Main Game Logic ---

def play_game():
    """Runs the main game loop."""
    score = 0
    word_history = set()  # Use a set for fast checking of used words

    # --- Difficulty Selection ---
    print("\nSelect Difficulty:")
    for key, value in DIFFICULTY_LEVELS.items():
        print(f"{key}: {value['name']}")

    difficulty_choice = ""
    while difficulty_choice not in DIFFICULTY_LEVELS:
        difficulty_choice = input("Enter difficulty number (1-3): ").strip()
        if difficulty_choice not in DIFFICULTY_LEVELS:
            print("Invalid choice. Please enter 1, 2, or 3.")

    selected_difficulty = DIFFICULTY_LEVELS[difficulty_choice]
    difficulty_name = selected_difficulty["name"]
    difficulty_modifier = selected_difficulty["prompt_modifier"]
    clue_style = selected_difficulty["clue_style"]
    time_limit = selected_difficulty["time_limit"]
    min_letters = selected_difficulty["min_letters"]
    max_letters = selected_difficulty["max_letters"]
    word_relation = selected_difficulty["word_relation"]
    
    print(f"\nDifficulty set to: {difficulty_name}")
    print(f"You have {time_limit} seconds to guess each word.")
    print(f"You'll see {min_letters}-{max_letters} letters in each clue.")

    # --- Initial Word ---
    print("\nGetting the first word from the AI...")
    previous_word = get_starting_word()
    word_to_guess, current_clue = get_ai_word_and_clue(previous_word, difficulty_modifier, clue_style, word_history, min_letters, max_letters, word_relation)

    if not word_to_guess or not current_clue:
        print("Failed to get starting word from AI. Exiting.")
        return

    print("-" * 30)
    print(f"Game Start!")
    print(f"Connected word: {previous_word.upper()}")
    print(f"Clue: {current_clue}")
    word_history.add(word_to_guess)

    # --- Game Loop ---
    while True:
        # Player's Turn
        player_guess = get_timed_input("\nEnter your guess (or type 'quit'): ", time_limit)

        if player_guess is None:
            print(f"\n--- Time's up! The word was: {word_to_guess.upper()} ---")
            break

        player_guess = player_guess.strip().lower()

        if not player_guess:
            print("Empty input is not allowed. Try again.")
            continue

        if player_guess == 'quit':
            print("\n--- Game Over! You quit the game. ---")
            break

        # Check if guess is correct
        if check_word_guess(player_guess, word_to_guess):
            score += 1
            print(f"\nCorrect! Score: {score}")
            
            # Get next word and clue
            print("\nAI is thinking of the next word...")
            previous_word = word_to_guess
            next_word, next_clue = get_ai_word_and_clue(previous_word, difficulty_modifier, clue_style, word_history, min_letters, max_letters, word_relation)
            
            if not next_word or not next_clue:
                print("\n--- Victory! The AI couldn't think of another word! ---")
                break
                
            if next_word in word_history:
                print(f"\n--- Victory! The AI repeated the word '{next_word.upper()}'! ---")
                break
                
            word_to_guess = next_word
            current_clue = next_clue
            word_history.add(word_to_guess)
            print(f"\nConnected word: {previous_word.upper()}")
            print(f"Clue: {current_clue}")
        else:
            print(f"\n--- Game Over! The word was: {word_to_guess.upper()} ---")
            break

    # --- End of Game ---
    print("-" * 30)
    print(f"Final Score: {score}")
    print("Words used in this chain:")
    print(", ".join(sorted(list(word_history))))
    print("-" * 30)

# --- Main Execution ---
if __name__ == "__main__":
    print("*" * 40)
    print(" Welcome to Word Chain Challenge! ")
    print("*" * 40)
    print("✨ Rules: ✨")
    print("1. The AI gives you a fill-in-the-blank sentence! 🎯")
    print("2. Guess the missing word within the time limit! ⏰")
    print("3. If correct, you get a new clue for a related word! 🎉")
    print("4. Keep guessing until you make a mistake or run out of time! 💪")
    print("Let's begin! Bestie, you got this! 💖")

    play_game()

    print("\nThanks for playing!")