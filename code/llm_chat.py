from settings import *
from os.path import join

from llama_cpp import Llama
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

model_path = join("models", "mistral", "mistral-7b-instruct-v0.1.Q4_K_M.gguf")
llm = Llama(model_path=model_path, n_ctx=2048, n_threads=6)

def get_npc_response(player_prompt: str, system_prompt: str, history=None) -> tuple[str, str]:
    if history is None:
        history = []

    history.append(("user", player_prompt))

    full_system_prompt = (
        f"{GLOBAL_SYSTEM_PROMPT}\n{system_prompt}\n"
        "When responding, always include your mood like this:\n"
        "Mood: <your current mood>\nReply: <your response>"
    )

    full_prompt = (
        f"[INST] {full_system_prompt}\nPlayer says: {player_prompt} [/INST]"
    )

    print("[DEBUG] Sending to model:", full_prompt.encode('utf-8', errors='replace'))

    try:
        output = llm(full_prompt, max_tokens=150)
        raw = output['choices'][0]['text'].strip()

        # Post-process and extract mood + reply
        mood, reply = "neutral", ""
        for line in raw.splitlines():
            if line.lower().startswith("mood:"):
                mood = line.split(":", 1)[1].strip()
            elif line.lower().startswith("reply:"):
                reply = line.split(":", 1)[1].strip()

        # Fallback if reply is empty
        if not reply:
            print("[WARNING] No valid reply detected. Using fallback.")
            reply = "Hmm... I need a moment to think."

        # Optional: detect out-of-character replies
        if is_bad_response(reply):
            print("[WARNING] Detected out-of-character response. Using fallback.")
            reply = "Uh... what were we talking about again?"

        history.append(("assistant", reply))
        return reply, mood

    except Exception as e:
        print(f"[ERROR] Mistral call failed: {e}")
        return "Sorry, I can't talk right now.", "neutral"

def is_bad_response(text: str) -> bool:
    lowered = text.lower()
    return any(bad.lower() in lowered for bad in BAD_OUTPUT_KEYWORDS)

def is_negative_sentiment(mood):
        analyzer = SentimentIntensityAnalyzer()
        
        # Get the sentiment scores for the mood (NPC's response)
        sentiment_score = analyzer.polarity_scores(mood)
        
        # If the compound score is negative, it's a negative sentiment
        if sentiment_score['compound'] < -0.1:  # You can adjust the threshold if needed
            return True
        return False

class TextInputBox:
    def __init__(self, x, y, width, height, font, color_active=pygame.Color('black'), color_inactive=pygame.Color('gray'), bg_color=pygame.Color('white')):
        self.rect = pygame.Rect(x, y, width, height)  # Set position and size based on WINDOW_WIDTH and WINDOW_HEIGHT
        self.color_active = color_active
        self.color_inactive = color_inactive
        self.color = self.color_active  # Text color
        self.text = ''
        self.font = font
        self.active = True
        self.done = False
        self.bg_color = bg_color  # Background color for the box

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
            self.color = self.color_active if self.active else self.color_inactive

        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                self.done = True
                return self.text
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_SPACE:
                self.text += ' '
            else:
                self.text += event.unicode
        return None

    def draw(self, surface):
        pygame.draw.rect(surface, self.bg_color, self.rect)

        txt_surface = self.font.render(self.text, True, self.color)
        surface.blit(txt_surface, (self.rect.x + 5, self.rect.y + 5))


        pygame.draw.rect(surface, self.color, self.rect, 2)
