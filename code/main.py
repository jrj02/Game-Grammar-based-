from settings import *
from pytmx.util_pygame import load_pygame
from os.path import join
import time
import threading

from sprite import *
from entities import Player, Character
from groups import AllSprites
from support import *
from game_data import *
from dialog import *

from llm_chat import get_npc_response, TextInputBox

class Game:
    def __init__(self):
        pygame.init()
        self.display_surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption('Monster Hunter 7')
        self.clock = pygame.time.Clock()
        
        # groups
        self.all_sprites = AllSprites()
        self.collision_sprites = pygame.sprite.Group()
        self.character_sprites = pygame.sprite.Group()
        self.transition_sprites = pygame.sprite.Group()
        
        # transition
        self.transition_target = None
        self.tint_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.tint_mode = 'untint'
        self.tint_progress = 0
        self.tint_direction = -1
        self.tint_speed = 600 
        
        # llm dialog
        self.text_input_box = None
        self.character_for_llm = None
        self.awaiting_llm_input = False
        self.llm_thread = None
        self.llm_result = None
        self.awaiting_llm_output = False
        
        self.in_conversation = False
        
        self.import_assets()
        self.setup(self.tmx_maps['world'], 'house')
        
        self.dialog_tree = None
    
    def import_assets(self):
        self.tmx_maps = {
            'world': load_pygame(join('data', 'maps', 'world.tmx')),
            'hospital': load_pygame(join('data', 'maps', 'hospital.tmx')),
            }
        
        self.overworld_frames = {
            'water' : import_folder(join('graphics', 'tilesets', 'water')),
            'coast' : coast_importer(24, 12, join('graphics', 'tilesets', 'coast')),
            'characters' : all_character_import(join('graphics', 'characters'))
        }
        
        self.fonts = {
            'dialog' : pygame.font.Font(join('graphics', 'fonts', 'PixeloidSans.ttf'), 30)
        }  
    
    def setup(self, tmx_map, player_start_pos):
        
        # clear map
        for group in (self.all_sprites, self.collision_sprites, self.transition_sprites, self.character_sprites):
            group.empty()
        
        # terrain
        for layer in ['Terrain', 'Terrain Top']:
            for x, y, surf in tmx_map.get_layer_by_name(layer).tiles():
                Sprite((x * TILE_SIZE, y * TILE_SIZE), surf, self.all_sprites, WORLD_LAYERS['bg'])
        
        # water
        for obj in tmx_map.get_layer_by_name('Water'):
            for x in range((int(obj.x)), int(obj.x + obj.width), TILE_SIZE):
                for y in range((int(obj.y)), int(obj.y + obj.height), TILE_SIZE):
                    AnimatedSprite((x,y), self.overworld_frames['water'], self.all_sprites, WORLD_LAYERS['water'])
                    
        # coast
        for obj in tmx_map.get_layer_by_name('Coast'):
            terrain = obj.properties['terrain']
            side = obj.properties['side']
            AnimatedSprite((obj.x, obj.y), self.overworld_frames['coast'][terrain][side], self.all_sprites, WORLD_LAYERS['bg'])
            
        # object
        for obj in tmx_map.get_layer_by_name('Objects'):
            if obj.name == 'top':
                Sprite((obj.x, obj.y), obj.image, self.all_sprites, WORLD_LAYERS['top'])
            else:
                CollidableSprite((obj.x, obj.y), obj.image, (self.all_sprites, self.collision_sprites))
        
        # transition objects
        for obj in tmx_map.get_layer_by_name('Transition'):
            TransitionSprite((obj.x, obj.y), (obj.width, obj.height), (obj.properties['target'], obj.properties['pos']), self.transition_sprites)
        
        # collision
        for obj in tmx_map.get_layer_by_name('Collisions'):
            BorderSprite((obj.x, obj.y), pygame.Surface((obj.width, obj.height)), self.collision_sprites)
        
        # grass
        for obj in tmx_map.get_layer_by_name('Monsters'):
            MonsterPatchSprite((obj.x, obj.y), obj.image, self.all_sprites, obj.properties['biome'])
            
        # entities
        for obj in tmx_map.get_layer_by_name('Entities'):
            if obj.name == 'Player':
                if obj.properties['pos'] == player_start_pos:
                    self.player = Player(
                        pos = (obj.x, obj.y), 
                        frames = self.overworld_frames['characters']['player'], 
                        groups = self.all_sprites,
                        facing_direction = obj.properties['direction'],
                        collision_sprites = self.collision_sprites)
                    self.player.game = self
            else:
                Character(
                    pos = (obj.x, obj.y), 
                    frames = self.overworld_frames['characters'][obj.properties['graphic']], 
                    groups = (self.all_sprites, self.collision_sprites, self.character_sprites),
                    facing_direction = obj.properties['direction'],
                    character_data = TRAINER_DATA[obj.properties['character_id']],
                    player = self.player,
                    create_dialog = self.create_dialog,
                    collision_sprites = self.collision_sprites,
                    radius = obj.properties['radius'])
    
    def input(self):
    # Block all overlapping interaction
        if self.awaiting_llm_input or self.in_conversation:
            return
        
        if not self.dialog_tree and not self.in_conversation and not self.awaiting_llm_input:
            keys = pygame.key.get_just_pressed()
            if keys[pygame.K_SPACE]:
                for character in self.character_sprites:
                    if check_connections(100, self.player, character):
                        print("[DEBUG] Connected to NPC:", character.character_data)
                        self.player.block()
                        character.change_facing_direction(self.player.rect.center)

                        self.in_conversation = True
                        self.character_for_llm = character
                        self.text_input_box = TextInputBox(100, 650, 1080, 40, self.fonts['dialog'])
                        self.awaiting_llm_input = True

    def create_dialog(self, character):
        if not self.dialog_tree:
            self.dialog_tree = DialogTree(character, self.player, self.all_sprites, self.fonts['dialog'], self.end_dialog)
    
    def end_dialog(self, character):
        self.clear_dialog_sprite()
        self.reset_dialog_state()
        self.player.unblock()

    def clear_dialog_sprite(self):
        if self.dialog_tree and self.dialog_tree.current_dialog:
            self.dialog_tree.current_dialog.kill()
        self.dialog_tree = None
    
    def reset_dialog_state(self):
        self.character_for_llm = None
        self.in_conversation = False
        self.awaiting_llm_input = False
        self.text_input_box = None
        self.command_menu = None
    
    def handle_llm_input(self, text):
        print(f"[DEBUG] TextInputBox result: {text}")
        self.awaiting_llm_input = False
        self.text_input_box = None
        self.player.block()

        # Prepare system prompt and history
        npc_data = self.character_for_llm.character_data
        npc_name = npc_data.get("name", "NPC")
        base_prompt = npc_data.get("prompt", f"You are {npc_name}, an NPC in a fantasy RPG game.")
        current_mood = getattr(self.character_for_llm, "mood", "neutral")  # use existing mood if present

        system_prompt = f"{base_prompt}\nCurrent mood: {current_mood}"
        history = self.character_for_llm.chat_history

        # Show temporary "Thinking..." dialog
        self.dialog_tree = DialogTree(
            character=self.character_for_llm,
            player=self.player,
            all_sprites=self.all_sprites,
            font=self.fonts['dialog'],
            end_dialog=self.no_op_end_dialog
        )
        self.dialog_tree.dialog = ["..."]
        self.dialog_tree.dialog_index = 0
        self.dialog_tree.dialog_num = 1
        self.dialog_tree.current_dialog = DialogSprite(
            "... Thinking", self.character_for_llm, self.all_sprites, self.fonts['dialog']
        )

        # Start background LLM call
        def run_llm():
            start_time = time.time()

            # 🎯 Get both reply and inferred mood
            reply, mood = get_npc_response(text, system_prompt=system_prompt, history=history)

            # ⏱ Timing
            end_time = time.time()
            print(f"[DEBUG] Model responded in {end_time - start_time:.2f} seconds")
            print(f"[DEBUG] Mood inferred: {mood}")

            # 🧠 Update mood + memory
            self.character_for_llm.mood = mood
            self.character_for_llm.chat_history.append(f"Player said: {text}")
            self.character_for_llm.chat_history.append(f"{npc_name} replied: {reply}")
            self.character_for_llm.chat_history = self.character_for_llm.chat_history[-6:]

            # 📨 Store response for processing in run()
            self.llm_result = reply
            self.llm_waiting = False

        # 🔁 Start background thread
        self.llm_thread = threading.Thread(target=run_llm)
        self.llm_thread.start()
        self.llm_waiting = True

    def no_op_end_dialog(self, character):
        pass
    
    def transition_check(self):
        sprites = [sprite for sprite in self.transition_sprites if sprite.rect.colliderect(self.player.hitbox)]
        if sprites:
            self.player.block()
            self.transition_target = sprites[0].target
            self.tint_mode = 'tint'
            
    def tint_screen(self, dt):
        if self.tint_mode == 'untint':
            self.tint_progress -= self.tint_speed * dt
        
        if self.tint_mode == 'tint':
            self.tint_progress += self.tint_speed * dt
            if self.tint_progress >= 255:
                self.setup(self.tmx_maps[self.transition_target[0]], self.transition_target[1])
                self.tint_mode = 'untint'
                self.transition_target = None
        
        self.tint_progress = max(0, min(self.tint_progress, 255))
        self.tint_surf.set_alpha(self.tint_progress)
        self.display_surface.blit(self.tint_surf, (0,0))
    
    def run(self):
        while True:
            dt = self.clock.tick() / 1000
            self.display_surface.fill('black')
            skip_frame = False

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self.awaiting_llm_input or self.in_conversation or self.dialog_tree:
                        print("[DEBUG] ESC pressed — exiting conversation")
                        self.end_dialog(self.character_for_llm)
                        skip_frame = True
                        continue

                if self.awaiting_llm_input and self.text_input_box:
                    result = self.text_input_box.handle_event(event)
                    if result is not None:
                        self.handle_llm_input(result)

            if skip_frame:
                continue

            self.input()
            self.transition_check()
            self.all_sprites.update(dt)

            self.all_sprites.draw(self.player)
            if self.awaiting_llm_input and self.text_input_box:
                self.text_input_box.draw(self.display_surface)
            if self.dialog_tree:
                self.dialog_tree.update()

            if self.awaiting_llm_output is False and self.llm_result is not None:
                # Replace Thinking... with paginated response
                pages = self.dialog_tree.paginate_text(self.llm_result)
                self.dialog_tree.dialog = pages
                self.dialog_tree.dialog_index = 0
                self.dialog_tree.dialog_num = len(pages)

                if self.dialog_tree.current_dialog:
                    self.dialog_tree.current_dialog.kill()

                self.dialog_tree.current_dialog = DialogSprite(
                    pages[0], self.character_for_llm, self.all_sprites, self.fonts['dialog']
                )

                self.llm_result = None
                
            self.tint_screen(dt)
            pygame.display.update()

if __name__ == '__main__':
    game = Game()
    game.run()

if __name__ == '__main__':
    game = Game()
    game.run()
        