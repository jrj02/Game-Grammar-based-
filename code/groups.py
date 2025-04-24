from settings import *
from support import import_image
from os.path import join
from entities import Entity

class AllSprites(pygame.sprite.Group):
    def __init__(self):
        super().__init__()
        self.display_surface = pygame.display.get_surface()
        self.offset = vector()
        self.shadow_surf = import_image(join('graphics', 'other', 'shadow'))
        self.noticed_surf = import_image(join('graphics', 'ui', 'notice'))
        
    def draw(self, player):
        self.offset.x = -(player.rect.centerx - WINDOW_WIDTH / 2)
        self.offset.y = -(player.rect.centery - WINDOW_HEIGHT / 2)
        
        bg_sprites = [sprite for sprite in self if sprite.z < WORLD_LAYERS['main']]
        main_sprites = sorted([sprite for sprite in self if sprite.z == WORLD_LAYERS['main']], key = lambda sprite: sprite.y_sort)
        fg_sprites = [sprite for sprite in self if sprite.z > WORLD_LAYERS['main']]
        
        for layer in (bg_sprites, main_sprites, fg_sprites):
                for sprite in layer:
                    if isinstance(sprite, Entity):
                        self.display_surface.blit(self.shadow_surf, sprite.rect.topleft + self.offset + vector(40, 110))
                    self.display_surface.blit(sprite.image, sprite.rect.topleft + self.offset)
                    if sprite == player and player.noticed:
                        rect = self.noticed_surf.get_frect(midbottom = sprite.rect.midtop)
                        self.display_surface.blit(self.noticed_surf, rect.topleft + self.offset)