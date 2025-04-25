from settings import *
from timer import Timer
import textwrap
from llm_chat import TextInputBox

class DialogTree:
    def __init__(self, character, player, all_sprites, font, end_dialog):
        self.player = player
        self.character = character
        self.font = font
        self.all_sprites = all_sprites
        self.end_dialog = end_dialog

        # Get dialog (could be empty if using LLM only)
        raw_lines = character.get_dialog()  # should return a list or []
        full_text = " ".join(raw_lines)
        self.dialog = self.paginate_text(full_text) if full_text else []

        self.dialog_num = len(self.dialog)
        self.dialog_index = 0

        if self.dialog:
            self.current_dialog = DialogSprite(self.dialog[self.dialog_index], self.character, self.all_sprites, self.font)
        else:
            self.current_dialog = None
            self.end_dialog(self.character)  # Immediately end if no dialog

        self.dialog_timer = Timer(500, autostart=True)

    def paginate_text(self, text, wrap_width=30, max_lines=3):
        import textwrap
        wrapped_lines = textwrap.wrap(text, width=wrap_width)
        chunks = []
        for i in range(0, len(wrapped_lines), max_lines):
            chunk = "\n".join(wrapped_lines[i:i+max_lines])
            chunks.append(chunk)
        return chunks

    def input(self):
        if self.player.game.awaiting_llm_input:
            return

        keys = pygame.key.get_just_pressed()

        if keys[pygame.K_ESCAPE] and not self.dialog_timer.active:
            print("[DEBUG] Conversation ended by player (ESC)")
            self.end_dialog(self.character)
            return

        if keys[pygame.K_SPACE] and not self.dialog_timer.active:
            print("[DEBUG] Player pressed SPACE to continue conversation")
            if self.current_dialog:
                self.current_dialog.kill()

            self.dialog_index += 1
            
            if self.dialog_index < self.dialog_num:
                print(f"[DEBUG] Showing dialog page {self.dialog_index + 1}/{self.dialog_num}")
                self.current_dialog = DialogSprite(
                    self.dialog[self.dialog_index],
                    self.character,
                    self.all_sprites,
                    self.font
                )
                self.dialog_timer.activate()
            else:
                # End of dialog pages — back to input
                print("[DEBUG] Dialog finished, returning to input")
                self.player.game.text_input_box = TextInputBox(100, 650, 1080, 40, self.font)
                self.player.game.awaiting_llm_input = True

    def update(self):
        self.dialog_timer.update()
        self.input()

class DialogSprite(pygame.sprite.Sprite):
    def __init__(self, message, character, groups, font):
        super().__init__(groups)
        self.z = WORLD_LAYERS['top']

        # Dialog bubble settings
        max_width = 500
        padding = 10
        line_height = 28
        wrap_width = 45  # Adjust for best look

        # Wrap text
        wrapped_lines = textwrap.wrap(message, width=wrap_width)
        text_surfaces = [font.render(line, True, COLORS['black']) for line in wrapped_lines]

        # Calculate size
        width = max(surf.get_width() for surf in text_surfaces) + padding * 2
        height = len(text_surfaces) * line_height + padding * 2

        # Create bubble surface
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(surf, COLORS['pure white'], surf.get_frect(topleft=(0, 0)), 0, 6)

        # Blit each line
        for i, text_surf in enumerate(text_surfaces):
            surf.blit(text_surf, (padding, padding + i * line_height))

        self.image = surf

        # 📍 Position above character's head
        self.rect = self.image.get_frect(midbottom=character.rect.midtop + vector(0, -10))
     
class CommandMenu:
    def __init__(self, x, y, font, options):
        self.rect = pygame.Rect(x, y, 300, 100)
        self.font = font
        self.options = options
        self.selected = 0
        self.active = True
        self.selection_made = False

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(self.options)
            elif event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(self.options)
            elif event.key == pygame.K_SPACE:
                self.selection_made = True
                return self.options[self.selected]
        return None

    def draw(self, surface):
        pygame.draw.rect(surface, COLORS['pure white'], self.rect, 0, 5)
        for i, option in enumerate(self.options):
            color = COLORS['black'] if i != self.selected else COLORS['blue']
            text_surf = self.font.render(option, True, color)
            surface.blit(text_surf, (self.rect.x + 10, self.rect.y + 10 + i * 30))
