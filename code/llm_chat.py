from llama_cpp import Llama
from os.path import join
from settings import *

model_path = join("models", "mistral", "mistral-7b-instruct-v0.1.Q4_K_M.gguf")
llm = Llama(model_path=model_path, n_ctx=2048, n_threads=6)

def get_npc_response(prompt: str, character_name="NPC") -> str:
    
    prompt = prompt.replace('\n', ' ').replace('\r', ' ')

    full_prompt = f"[INST] You are {character_name}, an NPC in a fantasy RPG game. Player sends: {prompt} [/INST]"

    print("[DEBUG] Sending to model:", full_prompt.encode('utf-8', errors='replace'))

    try:
        output = llm(full_prompt, max_tokens=150)
        response = output['choices'][0]['text'].strip()
        print(f"[DEBUG] Mistral responded with:\n{response}")
        return response
    except Exception as e:
        print(f"[ERROR] Mistral call failed: {e}")
        return "Sorry, I can't talk right now."


class TextInputBox:
    def __init__(self, x, y, width, height, font, color_active=pygame.Color('white'), color_inactive=pygame.Color('gray')):
        self.rect = pygame.Rect(x, y, width, height)
        self.color_active = color_active
        self.color_inactive = color_inactive
        self.color = self.color_active
        self.text = ''
        self.font = font
        self.active = True
        self.done = False

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
        txt_surface = self.font.render(self.text, True, self.color)
        width = max(200, txt_surface.get_width() + 10)
        self.rect.w = width
        surface.blit(txt_surface, (self.rect.x + 5, self.rect.y + 5))
        pygame.draw.rect(surface, self.color, self.rect, 2)
