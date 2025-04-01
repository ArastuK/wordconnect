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

# Initialize the model
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=GENERATION_CONFIG,
    safety_settings=SAFETY_SETTINGS
)

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

# Game settings
TIME_LIMIT_SECONDS = 15  # Time player has to answer

DIFFICULTY_LEVELS = {
    "1": {
        "name": "Easy",
        "prompt_modifier": "Use a very common, simple word that can be used in everyday sentences.",
        "time_limit": 20,
        "clue_style": "very descriptive and obvious",
        "min_letters": 3,
        "max_letters": 4,
        "word_relation": "directly related"
    },
    "2": {
        "name": "Medium",
        "prompt_modifier": "Use a moderately common word that requires some thinking.",
        "time_limit": 15,
        "clue_style": "moderately descriptive with some hints",
        "min_letters": 2,
        "max_letters": 3,
        "word_relation": "somewhat related"
    },
    "3": {
        "name": "Hard",
        "prompt_modifier": "Use a less common but still understandable word.",
        "time_limit": 12,  # Increased from 10 to 12 seconds
        "clue_style": "minimal with subtle hints",
        "min_letters": 2,  # Increased from 1 to 2 letters
        "max_letters": 3,  # Increased from 2 to 3 letters
        "word_relation": "somewhat related"  # Changed from "indirectly related" to "somewhat related"
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

def get_contextual_clue(word, difficulty='easy'):
    """Generate a contextual clue for the word."""
    word_length = len(word)
    
    # Create more varied masking patterns
    if word_length <= 3:
        # For very short words, show first letter
        masked_word = word[0] + '_' * (word_length - 1)
    elif word_length <= 4:
        # For 4-letter words, show first and last letter
        masked_word = word[0] + '_' * (word_length - 2) + word[-1]
    elif word_length <= 5:
        # For 5-letter words, show first, middle, and last letter
        middle_pos = word_length // 2
        masked_word = word[0] + '_' * (middle_pos - 1) + word[middle_pos] + '_' * (word_length - middle_pos - 2) + word[-1]
    else:
        # For longer words, show first letter, one random middle letter, and last letter
        # Ensure the middle letter is not too close to the start or end
        middle_pos = random.randint(2, word_length - 3)
        masked_word = word[0] + '_' * (middle_pos - 1) + word[middle_pos] + '_' * (word_length - middle_pos - 2) + word[-1]
    
    # Create a more creative and varied prompt for the AI
    prompt = f"""You are a creative puzzle maker. Create an engaging and imaginative clue for the word '{word}' in a word-guessing game.
    The word is {word_length} letters long and will be shown as: {masked_word}
    
    Guidelines for creating the perfect clue:
    1. Use vivid imagery and descriptive language
    2. Create an unexpected or surprising context
    3. Incorporate metaphors or analogies
    4. Make it playful and engaging
    5. Avoid obvious or direct hints
    6. Use varied sentence structures
    7. Make it appropriate for {difficulty} difficulty
    8. Keep it concise but memorable
    9. Use creative scenarios or settings
    10. Make it feel like a mini-story
    11. IMPORTANT: The word must be used in its correct grammatical form (noun, verb, adjective, etc.)
    12. The sentence must be grammatically correct and make logical sense
    13. The word should fit naturally in the sentence's context
    14. Vary the setting and context each time (e.g., fantasy, sci-fi, historical, modern, nature, urban, etc.)
    15. Use different narrative perspectives (first person, third person, omniscient)
    16. Include sensory details (sights, sounds, smells, textures)
    17. Create emotional resonance
    18. Use different literary devices (similes, personification, alliteration)
    19. Vary the tone (mysterious, humorous, dramatic, poetic)
    20. Make each clue unique and memorable
    
    Examples of creative clues:
    - For "wise": "The ancient sage's *w_s_e* counsel guided the village through difficult times."
    - For "owl": "In the moonlit forest, a silent *o_l* perched on the gnarled branch."
    - For "flow": "The crystal stream began to *f_o_w* through the ancient stones."
    - For "star": "In the digital realm, data points began to *s_a_r* like constellations."
    - For "time": "The quantum physicist watched as particles began to *t_m_e* in impossible ways."
    
    Format your clue as a complete sentence with the masked word in asterisks: *{masked_word}*
    Make sure your clue is DIFFERENT from these examples and creates a unique, imaginative scenario.
    
    Response should be ONLY the clue sentence, nothing else."""
    
    try:
        # Try up to 3 times to get a valid clue from the AI
        for attempt in range(3):
            clue = ask_gemini(prompt, is_clue=True)
            if clue and "*" in clue:
                # Validate that the masked word in the clue matches our pattern
                import re
                masked_pattern = re.search(r'\*(.*?)\*', clue)
                if masked_pattern and masked_pattern.group(1) == masked_word:
                    return clue
                else:
                    print(f"Attempt {attempt + 1}: AI returned incorrect masking pattern")
                    continue
            else:
                print(f"Attempt {attempt + 1}: AI response missing asterisks")
        
        # If we get here, all attempts failed
        print("All AI attempts failed, using fallback template")
        
        # Enhanced fallback templates with more variety and creativity
        fallback_templates = [
            # Fantasy themes
            f"In the enchanted forest, magical creatures began to *{masked_word}* with ethereal grace.",
            f"Within the wizard's spellbook, ancient words started to *{masked_word}* with forgotten power.",
            f"At the fairy's tea party, sugar cubes began to *{masked_word}* into impossible shapes.",
            
            # Sci-fi themes
            f"In the quantum laboratory, experimental particles began to *{masked_word}* in unexpected patterns.",
            f"Among the holographic displays, digital data started to *{masked_word}* through the network.",
            f"Inside the robot's neural core, electrical impulses began to *{masked_word}* with synthetic rhythm.",
            
            # Nature themes
            f"Deep beneath the ocean's surface, bioluminescent creatures would *{masked_word}* with ethereal grace.",
            f"In the ancient forest, sunlight began to *{masked_word}* through the canopy.",
            f"Across the desert sands, mirages started to *{masked_word}* in the heat haze.",
            
            # Urban themes
            f"In the bustling city streets, neon signs began to *{masked_word}* with electric energy.",
            f"Through the subway tunnels, echoes started to *{masked_word}* off the walls.",
            f"Among the skyscrapers, wind currents began to *{masked_word}* between buildings.",
            
            # Historical themes
            f"In the medieval castle, ancient tapestries began to *{masked_word}* with forgotten stories.",
            f"Among the Egyptian hieroglyphs, symbols started to *{masked_word}* with ancient wisdom.",
            f"Within the Roman forum, marble statues began to *{masked_word}* with timeless grace.",
            
            # Artistic themes
            f"On the painter's canvas, colors began to *{masked_word}* into impossible patterns.",
            f"In the musician's studio, notes started to *{masked_word}* through the air.",
            f"Among the sculptor's tools, marble began to *{masked_word}* into new forms.",
            
            # Everyday themes with a twist
            f"In the chef's experimental kitchen, flavors began to *{masked_word}* into extraordinary combinations.",
            f"Through the photographer's lens, moments started to *{masked_word}* into memories.",
            f"Within the gardener's greenhouse, plants began to *{masked_word}* in unexpected ways."
        ]
        return random.choice(fallback_templates)
    except Exception as e:
        print(f"Error generating clue: {str(e)}")
        return random.choice([
            f"In the quantum laboratory, the experimental particles began to *{masked_word}* in unexpected patterns.",
            f"Deep beneath the ocean's surface, bioluminescent creatures would *{masked_word}* with ethereal grace.",
            f"Among the ancient ruins, mysterious symbols started to *{masked_word}* with forgotten power."
        ])

def get_ai_word_and_clue(previous_word, prompt_modifier, clue_style, word_history, min_letters, max_letters, word_relation):
    """Get a word and clue from the AI with improved uniqueness checks."""
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
        
        # Enhanced validation
        if not new_word or len(new_word) < min_letters or len(new_word) > max_letters:
            return None, None
            
        # Check for direct repetition
        if new_word in word_history or new_word == previous_word:
            return None, None
            
        # Check for similarity with previous words
        for word in word_history:
            # Check for shared letters (if same length)
            if len(word) == len(new_word):
                shared_letters = sum(1 for a, b in zip(word, new_word) if a == b)
                if shared_letters / len(word) > 0.7:  # More than 70% shared letters
                    return None, None
            # Check for similar length words
            elif abs(len(word) - len(new_word)) <= 2:
                shared_letters = sum(1 for a, b in zip(word, new_word) if a == b)
                if shared_letters / min(len(word), len(new_word)) > 0.6:  # More than 60% shared letters
                    return None, None
        
        # Get the clue after confirming word uniqueness
        clue_prompt = f"""Given the word chain:
Previous word: {previous_word}
New word: {new_word}

Generate a {clue_style} clue that helps the player guess the word '{new_word}'.
The clue should be clear but not too obvious.
Return ONLY the clue, nothing else."""

        clue_response = model.generate_content(clue_prompt)
        clue = clue_response.text.strip()
        
        return new_word, clue
        
    except Exception as e:
        print(f"Error in get_ai_word_and_clue: {str(e)}")
        return None, None

def check_word_guess(guess, correct_word):
    """Checks if the player's guess matches the correct word."""
    return guess.strip().lower() == correct_word.lower()

def get_letter_hints(word, min_letters, max_letters):
    """Generates letter hints for the word."""
    import random
    word_length = len(word)
    # Determine how many letters to show
    num_letters = random.randint(min_letters, min(max_letters, word_length))
    
    # Create a list of positions to show
    positions = random.sample(range(word_length), num_letters)
    
    # Create the hint string with underscores for hidden letters
    hint = list('_' * word_length)
    for pos in positions:
        hint[pos] = word[pos]
    
    return ''.join(hint)

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
    
    # Select a random theme and then a random word from that theme
    theme = random.choice(list(starting_words.keys()))
    return random.choice(starting_words[theme])

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
    word_to_guess, current_clue = get_ai_word_and_clue(previous_word, difficulty_modifier, clue_style, [], min_letters, max_letters, word_relation)

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