from settings import *
from pytmx.util_pygame import load_pygame
from os.path import join
import time
import threading
from random import randint

from sprite import *
from entities import Player, Character
from groups import AllSprites
from support import *
from game_data import *
from dialog import *
from battle import Battle
from monster_index import MonsterIndex
from timer import Timer
from evolutions import Evolution
from monster import Monster

from llm_chat import *
from llm_evaluation import *

class Game:
    def __init__(self):
        pygame.init()
        self.display_surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption('Monster Hunter 7')
        self.clock = pygame.time.Clock()
        self.encounter_timer = Timer(2000, func = self.monster_encounter)
        
        # player monsters 
        self.player_monsters = {
            0: Monster('Ivieron', 32),
            1: Monster('Atrox', 15),
            2: Monster('Cindrill', 16),
            3: Monster('Atrox', 10),
            4: Monster('Sparchu', 11),
            5: Monster('Gulfin', 9),
            6: Monster('Jacana', 10),
        }
        for monster in self.player_monsters.values():
            monster.xp += randint(0,monster.level * 100)
        self.test_monsters = {
            0: Monster('Finsta', 15),
            1: Monster('Pouch', 13),
            2: Monster('Larvea', 12),
        }
        
        # groups
        self.all_sprites = AllSprites()
        self.collision_sprites = pygame.sprite.Group()
        self.character_sprites = pygame.sprite.Group()
        self.transition_sprites = pygame.sprite.Group()
        self.monster_sprites = pygame.sprite.Group()
        
        # transition
        self.transition_target = None
        self.tint_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.tint_mode = 'untint'
        self.tint_progress = 0
        self.tint_direction = -1
        self.tint_speed = 600 
        self.queued_battle = False
        
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
        self.audio['overworld'].play(-1)
        
        self.dialog_tree = None
        self.monster_index = MonsterIndex(self.player_monsters, self.fonts, self.monster_frames)
        self.index_open = False
        self.battle = None
        self.evolution = None
    
    def import_assets(self):
        self.tmx_maps = tmx_importer(join('data', 'maps'))
        
        self.overworld_frames = {
            'water' : import_folder(join('graphics', 'tilesets', 'water')),
            'coast' : coast_importer(24, 12, join('graphics', 'tilesets', 'coast')),
            'characters' : all_character_import(join('graphics', 'characters'))
        }
        
        self.monster_frames = {
            'icons': import_folder_dict(join( 'graphics', 'icons')),
            'monsters': monster_importer(4,2, join('graphics', 'monsters')),
            'ui': import_folder_dict(join('graphics', 'ui')),
            'attacks': attack_importer(join('graphics', 'attacks'))
        }
        self.monster_frames['outlines'] = outline_creator(self.monster_frames['monsters'], 4)
        
        self.fonts = {
            'dialog' : pygame.font.Font(join('graphics', 'fonts', 'PixeloidSans.ttf'), 30),
            'regular': pygame.font.Font(join('graphics', 'fonts', 'PixeloidSans.ttf'), 18),
			'small': pygame.font.Font(join('graphics', 'fonts', 'PixeloidSans.ttf'), 14),
			'bold': pygame.font.Font(join('graphics', 'fonts', 'dogicapixelbold.otf'), 20),
        }
        self.bg_frames = import_folder_dict(join('graphics', 'backgrounds'))
        self.start_animation_frames = import_folder(join('graphics', 'other', 'star animation'))
        
        self.audio = audio_importer(join('audio'))
        
        for sound in self.audio.values():
            sound.set_volume(0.10)
        
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
            MonsterPatchSprite((obj.x, obj.y), obj.image, (self.all_sprites, self.monster_sprites), obj.properties['biome'], obj.properties['monsters'], obj.properties['level'])
            
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
                    radius = obj.properties['radius'],
                    notice_sound = self.audio['notice'])
    
    def input(self):
        if self.awaiting_llm_input or self.in_conversation:
            return

        keys = pygame.key.get_just_pressed()
        if keys[pygame.K_SPACE]:
            for character in self.character_sprites:
                if check_connections(100, self.player, character):
                    print("[DEBUG] Connected to NPC:", character.character_data)
                    self.player.block()  # Block movement while in conversation
                    character.change_facing_direction(self.player.rect.center)
                    
                    # Check if the character is defeated, and prevent battle initiation if so
                    if character.character_data.get('defeated', False):
                        print(f"[DEBUG] {character.character_data['name']} is defeated. No battle can be initiated.")
                        return

                    self.in_conversation = True
                    self.character_for_llm = character
                    self.text_input_box = TextInputBox(0, WINDOW_HEIGHT - 120, WINDOW_WIDTH, 120, self.fonts['dialog'], bg_color=pygame.Color('white'))
                    self.awaiting_llm_input = True  # Wait for player input in the text box

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
    
    def end_battle(self, character):
        # Stop battle music
        self.audio['battle'].stop()
        self.transition_target = 'level'
        self.tint_mode = 'tint'

        if character:
            # Mark the character as defeated AFTER the battle
            print("[DEBUG] Marking character as defeated after battle.")
            character.character_data['defeated'] = True  # Set the defeated flag here
            print(f"[DEBUG] Character defeated state: {character.character_data['defeated']}")  # Log the defeated state

        elif not self.evolution:
            self.player.unblock()  # Unblock the player after the battle ends
            self.check_evolution()

        # End the dialog after the battle
        if self.queued_battle:
            print("[DEBUG] Ending dialog after battle")
            self.end_dialog(character)  # End the conversation after the battle

        # After battle ends, ensure player can move again
        self.in_conversation = False
        self.awaiting_llm_input = False
        self.text_input_box = None  # Clear any leftover text input box
        self.audio['overworld'].play(-1)
        
        # Ensure the player is unblocked and can move again
        self.player.unblock()
        print("[DEBUG] Player unblocked and ready to move")

    def check_monster(self):
        if [sprite for sprite in self.monster_sprites if sprite.rect.colliderect(self.player.hitbox)] and not self.battle and self.player.direction:
            if not self.encounter_timer.active:
                self.encounter_timer.activate()
    
    def monster_encounter(self):
        sprites = [sprite for sprite in self.monster_sprites if sprite.rect.colliderect(self.player.hitbox)]
        if sprites and self.player.direction:
            self.encounter_timer.duration = randint(800, 2500)
            self.player.block()
            self.audio['overworld'].stop()
            self.audio['battle'].play(-1)
            self.transition_target = Battle(
                player_monsters = self.player_monsters, 
                opponent_monsters = {index:Monster(monster, sprites[0].level + randint(-3,3)) for index, monster in enumerate(sprites[0].monsters)}, 
                monster_frames = self.monster_frames, 
                bg_surf = self.bg_frames[sprites[0].biome], 
                fonts = self.fonts, 
                end_battle = self.end_battle,
                character = None, 
                sounds = self.audio)
            self.tint_mode = 'tint'
        
    def check_evolution(self):
        for index, monster in self.player_monsters.items():
            if monster.evolution:
                if monster.level == monster.evolution[1]:
                    self.audio['evolution'].play()
                    self.player.block()
                    self.evolution = Evolution(self.monster_frames['monsters'], monster.name, monster.evolution[0], self.fonts['bold'], self.end_evolution, self.start_animation_frames)
                    self.player_monsters[index] = Monster(monster.evolution[0], monster.level)
        if not self.evolution:
            self.audio['overworld'].play(-1)

    def end_evolution(self):
        self.evolution = None
        self.player.unblock()
        self.audio['evolution'].stop()
        self.audio['overworld'].play(-1)
    
    def handle_llm_input(self, text):
        print(f"[DEBUG] TextInputBox result: {text}")
        self.awaiting_llm_input = False
        self.text_input_box = None
        self.player.block()

        # Prepare system prompt and history
        character_data = self.character_for_llm.character_data
        character_name = character_data.get("name", "Character")

        # Check if the character is defeated and set the appropriate prompt
        if self.character_for_llm.character_data.get('defeated', False):
            base_prompt = self.character_for_llm.character_data.get('defeated_prompt', '')  # Use defeated prompt
            print(f"[DEBUG] Using defeated prompt: {base_prompt}")
        else:
            base_prompt = character_data.get("prompt", f"You are {character_name}, an NPC in a fantasy RPG game.")
            print(f"[DEBUG] Using default prompt: {base_prompt}")

        current_mood = getattr(self.character_for_llm, "mood", "neutral")

        # Construct the full system prompt to send to Mistral
        local_prompt = f"{base_prompt}\nCurrent mood: {current_mood}"
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
            "...", self.character_for_llm, self.all_sprites, self.fonts['dialog']
        )

        #Start background LLM call
        def run_llm():
            start_time = time.time()

            # Get both reply and inferred mood
            reply, mood = get_npc_response(text, local_prompt=local_prompt, history=history)

            # Timing
            end_time = time.time()
            print(f"[DEBUG] Model responded in {end_time - start_time:.2f} seconds")
            print(f"[DEBUG] Mood inferred: {mood}")  # Still useful for dialog, not for battle anymore

            # Perform sentiment analysis on the reply FIRST (avoid recalculating it multiple times)
            sentiment_score = analyzer.polarity_scores(reply)  # Use the pre-initialized analyzer
            print(f"[DEBUG] Sentiment score for reply: {sentiment_score}")

            # If the compound score is negative, trigger battle (before proceeding with the rest)
            if sentiment_score['compound'] < -0.1 or sentiment_score['neg'] > 0.2 and self.in_conversation:
                print(f"[DEBUG] Negative sentiment detected! Triggering battle.")
                self.queued_battle = True  # Queue the battle

            # Update mood + memory
            self.character_for_llm.mood = mood
            self.character_for_llm.chat_history.append(f"Player said: {text}")
            self.character_for_llm.chat_history.append(f"{character_name} replied: {reply}")
            self.character_for_llm.chat_history = self.character_for_llm.chat_history[-6:]

            # Store response for processing in run()
            self.llm_result = reply
            self.llm_waiting = False

            # **Check for empty or malformed response** before proceeding with evaluation
            if not reply or len(reply.strip()) == 0:
                print("[DEBUG] Empty or malformed response detected. Skipping evaluation.")
                return

            print("[DEBUG] Model response:", reply)  # Print the model's response for debugging

            # **Evaluate both perplexity, BLEU, METEOR, Distinct** for the last response
            try:
                # Perplexity evaluation
                perplexity_score = evaluate_perplexity(reply, text, self.character_for_llm.character_data)

                # BLEU evaluation
                bleu_score = evaluate_bleu(text, reply)

                # METEOR evaluation
                meteor_score = evaluate_meteor(text, reply)

                # Distinct evaluation
                distinct_score = evaluate_distinct(reply, n=1)

            except Exception as e:
                print(f"[ERROR] Error in evaluation: {e}")
                print("[DEBUG] Skipping evaluation due to error.")

            # After everything is set up, proceed with dialogue processing (do this after triggering battle)
            self.llm_waiting = False
        

        #Start background thread for LLM response generation
        self.llm_thread = threading.Thread(target=run_llm)
        self.llm_thread.start()
        self.llm_waiting = True

    def trigger_battle_with_character(self, character):
        # Prevent battle initiation if character is defeated
        if character.character_data.get('defeated', False):
            print(f"[DEBUG] {character.character_data['name']} is defeated. Battle cannot be triggered.")
            return  # Exit the method if the character is defeated

        print(f"[DEBUG] Starting a battle with {character.character_data['name']}...")

        self.audio['overworld'].stop()
        self.audio['battle'].play(-1)

        # Set up the battle
        # Use the level from the monsters directly, not from character.character_data
        opponent_monsters = {
            index: Monster(monster[0], monster[1])  # monster[0] is the name, monster[1] is the level
            for index, monster in enumerate(character.character_data['monsters'].values())
        }

        self.transition_target = Battle(
            player_monsters=self.player_monsters, 
            opponent_monsters=opponent_monsters, 
            monster_frames=self.monster_frames, 
            bg_surf=self.bg_frames[character.character_data['biome']], 
            fonts=self.fonts, 
            end_battle=self.end_battle,
            character=character, 
            sounds=self.audio
        )
        self.tint_mode = 'tint'
        self.player.block()  # Block the player until the battle is over
    
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
                if type(self.transition_target) == Battle:
                    self.battle = self.transition_target
                elif self.transition_target == 'level':
                    self.battle = None
                else:
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
            
            self.encounter_timer.update()
            self.input()
            self.transition_check()
            self.all_sprites.update(dt)
            self.check_monster()
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
                
            # overlays 
            if self.dialog_tree: self.dialog_tree.update()
            if self.index_open:  self.monster_index.update(dt)
            if self.battle:      self.battle.update(dt)
            if self.evolution:   self.evolution.update(dt)
                
            self.tint_screen(dt)
            pygame.display.update()

if __name__ == '__main__':
    game = Game()
    game.run()

if __name__ == '__main__':
    game = Game()
    game.run()
        