import os
import sys
import yaml
import math
import time
import ctypes
import pickle
import random
import argparse
import threading
import multiprocessing


FORWARD_DOP = 3
BACKWARD_DOP = -1

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

class UselessClock:
    def __init__(self):
        pass
    def tick(self, _):
        pass


def hardCopy(object):
    return pickle.loads(pickle.dumps(object))



class Item:
    def __init__(self, xpos, ypos, orientation, type, image, box_type = None):
        self.xpos = xpos
        self.ypos = ypos
        self.image = image
        self.type = type
        self.box_type = box_type
        self.orientation = orientation

        # pré-calcule l'image pivotée de l'objet
        if image:
            self.image = pygame.transform.rotate(image, orientation)
        
        if type == 'tree':
            self.ttl = 1
        elif type == 'wall':
            self.ttl = 10
        else:
            self.ttl = math.inf
    
    def __eq__(self, obj):
        return type(obj) == Item and (self.xpos, self.ypos, self.type) == (obj.xpos, obj.ypos, obj.type)
    
    def display(self, game):
        rect = self.image.get_rect(center = game.nc(self.xpos,self.ypos))
        game.screen.blit(self.image, rect.topleft)



class Bullet:
    def __init__(self, xpos, ypos, orientation, player, image, ttl = 30):
        self.xpos = xpos
        self.ypos = ypos
        self.ttl = ttl
        self.orientation = orientation
        self.player = player
        self.alive = True
        if image:
            self.image = pygame.transform.rotate(image, orientation)
    
    def one_step(self, game): # le projectile fait une étape de mouvement. renvoie True si le projectile disparaît au cours de cette étape de mouvement
        self.ttl -= 1
        
        dop = self.ttl/1.5
        self.xpos += math.cos(self.orientation/180*math.pi) * dop
        self.ypos -= math.sin(self.orientation/180*math.pi) * dop

        if game.update_objects(self.player, self.xpos, self.ypos) or self.ttl <= 0: # on peut arreter notre petite vie de projectile
            self.alive = False
        
    def display(self, game):
        rect = self.image.get_rect(center = game.nc(self.xpos,self.ypos))
        game.screen.blit(self.image, rect.topleft)





class Tank:
    def __init__(self, xpos, ypos, file, image, name, bullets = 200, bricks = 0):
        self.xpos = xpos
        self.ypos = ypos
        self.file = file
        self.nb_bullets = bullets
        self.nb_bricks = bricks
        self.orientation = random.randint(0,360)
        self.health = 100
        self.image = image
        self.name = name
        self.lastshot = 0
        self.process = None


        # Précalcul de l'image du tank pour toutes les orientations
        if self.image: # On ne précalcule les rotations que si self.image est une image valide
            self.angles = [pygame.transform.rotate(self.image, angle) for angle in range(360)]
    
    def is_close(self, obj):
        return distance(self.xpos, self.ypos, obj.xpos, obj.ypos) < 60

    def display(self, game):
        # display the sprite
        rotated_image = self.angles[int(self.orientation)%360]
        rect = rotated_image.get_rect(center = game.nc(self.xpos,self.ypos))
        game.screen.blit(rotated_image, rect.topleft)

        # Affichage du nom du joueur

        # Création de l'objet Font
        font = pygame.font.Font(None, game.nx(30))
        font.bold = False

        # Création de l'objet texte
        text = font.render(self.name, False, (0, 0, 0))
        x_text = game.nx(self.xpos) - text.get_width()/2
        y_text = game.ny(self.ypos) - game.ny(50)

        # Ajout d'un rectangle transparent en dessous
        bg = pygame.Surface((text.get_width()+4, text.get_height()+2), pygame.SRCALPHA)
        bg.fill((0, 255, 0, 70)) # noir semi-transparent
        game.screen.blit(bg, (x_text-2, y_text-1))
        game.screen.blit(text, (x_text, y_text))

        # Affichage de la barre de vie
        bar_width = 70
        bar_height = 5

        # Calcul des coordonnées normalisées de la barre
        x_rect, y_rect = game.nx(self.xpos - bar_width/2), game.ny(self.ypos - 5) + self.image.get_height()

        # Normalisation des dimensions de la barre
        bar_width_n, bar_height_n = game.nc(bar_width, bar_height)

        # la couleur de fond
        color = pygame.Color(0, 100, 0, 0)
        rect = pygame.Rect(x_rect, y_rect, bar_width_n, bar_height_n)
        pygame.draw.rect(game.screen, color, rect)

        # la couleur de points de vie
        color = pygame.Color(0, 200, 0, 0)
        rect = pygame.Rect(x_rect, y_rect, self.health * bar_width_n / 100, bar_height_n)
        pygame.draw.rect(game.screen, color, rect)

        # rectangle noir autour
        color = pygame.Color(0, 0, 0, 0)
        coord = (x_rect, y_rect, bar_width_n, bar_height_n)
        pygame.draw.rect(game.screen, color, coord, 1)





class Request:
    def __init__(self, name, requestEntry, responseEnd):
        self.requestEntry = requestEntry
        self.responseEnd = responseEnd
        self.name = name
    
    def __getstate__(self):
        return {"name": self.name, "requestEntry": self.requestEntry, "responseEnd": self.responseEnd}
    
    def make_request(*args):
        self = args[0]
        self.requestEntry.send(args[1:])
        return self.responseEnd.recv()

    def make_unidirectional_request(*args): # pour les requêtes n'attendant pas de réponse
        self = args[0]
        self.requestEntry.send(args[1:])
    
    def add_wall(self):
        return self.make_request("add_wall")
    
    def getItems(self):
        return self.make_request("getItems")
    
    def getTanks(self):
        return self.make_request("getTanks")
    
    def get_position(self):
        return self.make_request("get_position")
    
    def get_orientation(self):
        return self.make_request("get_orientation")
    
    def get_health(self):
        return self.make_request("get_health")
    
    def get_nb_bricks(self):
        return self.make_request("get_nb_bricks")
    
    def get_nb_bullets(self):
        return self.make_request("get_nb_bullets")
    
    def move(self):
        self.make_unidirectional_request("move")
    
    def back(self):
        self.make_unidirectional_request("back")
    
    def rotate_right(self):
        self.make_unidirectional_request("rotate_right")
    
    def rotate_left(self):
        self.make_unidirectional_request("rotate_left")
    
    def fire(self):
        return self.make_request("fire")
    
    def grab_box(self):
        return self.make_request("grab_box")
    
    def detect(self):
        return self.make_request("detect")
    
    def listen(self):
        return self.make_request("listen")
    
    def suicide(self):
        self.make_unidirectional_request("suicide")



def serverFunction(requestEnd, responseEntry, game, name):
    tank = game.tanks[name]

    while True:
        # Attente d'une requête
        request = requestEnd.recv()

        reqType = request[0]
        args = request[1:]
        
        if reqType == "suicide" or tank.health < 0:
            responseEntry.close()
            requestEnd.close()
            tank.request.responseEnd.close()
            tank.request.requestEntry.close()
            if tank.process.is_alive():
                tank.process.kill()
            del game.tanks[tank.name]
            return
        
        elif reqType == "add_wall":
            dx = math.cos(tank.orientation/180*math.pi) * 50
            dy = -math.sin(tank.orientation/180*math.pi) * 50
            wall_x, wall_y = tank.xpos + dx, tank.ypos + dy
            
            if tank.nb_bricks > 0 and game.validate_position(wall_x, wall_y, wall_x, wall_y):
                tank.nb_bricks -= 1
                game.items.append(Item(wall_x, wall_y, tank.orientation, 'wall', game.item_images['wall']))
                responseEntry.send(True)
            else:
                responseEntry.send(False)
        
        elif reqType == "get_position":
            responseEntry.send((tank.xpos, tank.ypos))
        
        elif reqType == "get_orientation":
            responseEntry.send(tank.orientation)
        
        elif reqType == "get_health":
            responseEntry.send(tank.health)
        
        elif reqType == "get_nb_bricks":
            responseEntry.send(tank.nb_bricks)
        
        elif reqType == "get_nb_bullets":
            responseEntry.send(tank.nb_bullets)
        
        elif reqType == "move":
            dx = math.cos(tank.orientation/180*math.pi) * FORWARD_DOP
            dy = -math.sin(tank.orientation/180*math.pi) * FORWARD_DOP
            if game.validate_position(tank.xpos, tank.ypos, tank.xpos + dx, tank.ypos + dy): # permet de tester les collisions
                tank.xpos += dx
                tank.ypos += dy
                game.clock.tick(60)
        
        elif reqType == "back":
            dx = math.cos(tank.orientation/180*math.pi) * BACKWARD_DOP
            dy = -math.sin(tank.orientation/180*math.pi) * BACKWARD_DOP
            if game.validate_position(tank.xpos, tank.ypos, tank.xpos + dx, tank.ypos + dy): # permet de tester les collisions
                tank.xpos += dx
                tank.ypos += dy
                game.clock.tick(200)
        
        elif reqType == "rotate_right":
            dtheta = 1
            tank.orientation = (tank.orientation - 1) % 360
            game.clock.tick(250)
        
        elif reqType == "rotate_left":
            dtheta = 1
            tank.orientation = (tank.orientation + 1) % 360
            game.clock.tick(250)
        
        elif reqType == "fire":
            if tank.nb_bullets <= 0 or time.monotonic() - tank.lastshot < 0.3 :
                responseEntry.send(False) # on ne peut plus tirer, il n'y a plus de projectiles
            else:
                tank.nb_bullets -= 1
                tank.lastshot = time.monotonic()
                game.bullets.append(Bullet(tank.xpos, tank.ypos, tank.orientation, tank.name, game.bullet_image))
                responseEntry.send(True)
        
        elif reqType == "grab_box":
            items = game.items.copy()
            response = False
            
            for obj in items:
                if obj.type == 'box' and distance(tank.xpos, tank.ypos, obj.xpos, obj.ypos) < 20: # la boite peut être attrapée
                    game.items.remove(obj)
                    if obj.box_type == 'bullets':
                        tank.nb_bullets += 200
                    elif obj.box_type == 'bricks':
                        tank.nb_bricks += 20
                    response = True
            
            responseEntry.send(response)
        
        elif reqType == "detect":
            # calcul de la droite de vision du tank
            if tank.orientation in (90, 270):
                on_trajectory = lambda x, y : x == tank.xpos
            else:
                coeff_dir = -math.tan(math.radians(tank.orientation))
                ordon_orig = tank.ypos - coeff_dir * tank.xpos
                on_trajectory = lambda x, y : abs(coeff_dir * x + ordon_orig - y) < 30
            
            # calcul de la zone dans laquelle on voit les objets
            if tank.orientation <= 90: # 1er cadran
                check_area = lambda obj : (obj.xpos >= tank.xpos and obj.ypos <= tank.ypos) or tank.is_close(obj)
            elif tank.orientation <= 180: # deuxième cadran
                check_area = lambda obj : (obj.xpos <= tank.xpos and obj.ypos <= tank.ypos) or tank.is_close(obj)
            elif tank.orientation <= 270: # troisième cadran
                check_area = lambda obj : (obj.xpos <= tank.xpos and obj.ypos >= tank.ypos) or tank.is_close(obj)
            else: # dernier cadran
                check_area = lambda obj : (obj.xpos >= tank.xpos and obj.ypos >= tank.ypos) or tank.is_close(obj)
            
            # parcours des objets
            items = filter(check_area, game.items)
            tanks = filter(check_area, game.get_tanks())
            
            # Liste des objets détectés
            detected = []

            for item in items:
                if collision(tank.xpos, tank.ypos, item) or diff_collision(tank, item) or on_trajectory(item.xpos, item.ypos):
                    detected.append((item.type, distance(tank.xpos, tank.ypos, item.xpos, item.ypos)))
            
            for other_tank in tanks:
                if other_tank.name != tank.name and (collision_tank(tank.xpos, tank.ypos, other_tank.xpos, other_tank.ypos) or
                diff_collision_tank(tank, other_tank) or on_trajectory(other_tank.xpos, other_tank.ypos)):
                    detected.append(('tank', distance(tank.xpos, tank.ypos, other_tank.xpos, other_tank.ypos)))

            responseEntry.send(detected)
        
        elif reqType == "listen":
            s = 0
            for bullet in game.bullets.copy():
                s += math.exp(-(dist_obj(tank, bullet)/200)**2) * 100
            
            responseEntry.send(int(s))





def clientFunction(code, request):
    # Copie de la requête avant l'envoi pour conserver une requête intègre
    sentRequest = hardCopy(request)
    variables = {
        "fire":             sentRequest.fire,
        "get_position":     sentRequest.get_position,
        "get_health":       sentRequest.get_health,
        "get_orientation":  sentRequest.get_orientation,
        "get_nb_bullets":   sentRequest.get_nb_bullets,
        "get_nb_bricks":    sentRequest.get_nb_bricks,
        "move":             sentRequest.move,
        "back":             sentRequest.back,
        "rotate_right":     sentRequest.rotate_right,
        "rotate_left":      sentRequest.rotate_left,
        "grab_box":         sentRequest.grab_box,
        "add_wall":         sentRequest.add_wall,
        "detect":           sentRequest.detect,
        "listen":           sentRequest.listen,
        "distance":         distance,
        "math":             math,
        "time":             time,
        "random":           random,
        "__playername":     sentRequest.name
    }

    try:
        exec(code, variables)
    except:
        print(f"{variables['__playername']} a crashé")
    
    request.suicide()




# Charger le fichier YAML
def load_map(filename): # renvoie les données de la map
    with open(filename, 'r') as file:
        return yaml.safe_load(file)


def load_image(path):
    try:
        return pygame.image.load(path + '.png').convert_alpha()
    except:
        return pygame.image.load(path + '.bmp').convert_alpha()


# Charger les images
def load_item_images(nc_func, graphics): # renvoie la liste des sprites nécessaires au dessin de la map
    items = ['tree', 'rock', 'tower', 'bullet', 'box', 'wall']

    if graphics:
        images = {item: load_image(f"assets/{item}") for item in items}
        # Rescales the images with the nc_func scaling function
        for (key, item) in images.items():
            images[key] = pygame.transform.scale(images[key], nc_func(images[key].get_width(), images[key].get_height()))
    else:
        images = {item:None for item in items}

    return images



def load_tank_image(color, nc_func, graphics):
    if graphics:
        image = load_image(os.path.join('assets', color))
        return pygame.transform.scale(image, nc_func(image.get_width(), image.get_height()))
    else:
        return None


def load_players(filename): # charge le dictionnaire contenant les données de chaque joueur (position, orientation, ...)
    file = open(filename, 'r')
    data = yaml.safe_load(file)
    file.close()
    
    return data



def distance(xa, ya, xb, yb):
    return math.sqrt((xa-xb)**2 + (ya-yb)**2)


def dist_obj(obj1, obj2):
    return distance(obj1.xpos, obj1.ypos, obj2.xpos, obj2.ypos)



def collision_tank(x,y, xo, yo):
    return distance(x,y,xo,yo) < 40





def collision(x,y,obj):
    xo,yo = obj.xpos, obj.ypos
    
    if obj.type == 'tree':
        return distance(x, y, xo, yo) < 35
    
    elif obj.type == 'rock':
        return distance(x, y, xo, yo) < 35
    
    elif obj.type == 'tower':
        return distance(x, y, xo, yo) < 55
    
    elif obj.type == 'wall':
        return distance(x, y, xo, yo) < 20
    
    return False




def diff_collision(tank, obj):
    dx = math.cos(tank.orientation/180*math.pi) * FORWARD_DOP * 1.5
    dy = -math.sin(tank.orientation/180*math.pi) * FORWARD_DOP * 1.5
    return collision(tank.xpos + dx, tank.ypos + dy, obj)


def diff_collision_tank(tank, tank2):
    dx = math.cos(tank.orientation/180*math.pi) * FORWARD_DOP * 1.5
    dy = -math.sin(tank.orientation/180*math.pi) * FORWARD_DOP * 1.5
    return collision_tank(tank.xpos + dx, tank.ypos + dy, tank2.xpos, tank2.ypos)


# Lit la map et crée les objets
# Les dimensions des objets sont normalisées avec la fonction nc_func
def read_map(map, nc_func, graphics):
    items = [] # liste de tous les objets immobiles de la map (arbres, cailloux, tours et caisses)

    # Charger la map
    map_data = load_map(map)
    item_images = load_item_images(nc_func, graphics)

    if 'objects' in map_data:
        for object in map_data['objects']:
            if 'orientation' in object:
                orientation = object['orientation']
            else:
                orientation = 0
            
            if object['type'] == 'box':
                box_type = random.choice(['bullets', 'bricks'])
            else:
                box_type = None
            
            items.append(Item(object['position'][0], object['position'][1], orientation, object['type'], item_images[object['type']], box_type))
    
    return items, map_data['start'], item_images, map_data['bullets'], map_data['bricks']


def load_tanks(players, start_pos, nb_bullets, nb_bricks, get_free_coord, nc_func, graphics):
    if len(players) > len(start_pos):
        while len(start_pos) < len(players):
            start_pos.append(get_free_coord())
    
    tanks = {}
    players_data = load_players(players)
    for player, coord in zip(players_data, start_pos):
        if coord == 'random':
            coord = get_free_coord()
        tanks[player['name']] = Tank(coord[0], coord[1], player['program'], load_tank_image(player['color'], nc_func, graphics), player['name'], bullets = nb_bullets, bricks = nb_bricks)
    
    return tanks



class Game:
    def __init__(self, players, map, graphics, fullscreen):
        # Initialisation des graphiques
        # Initialisation de Pygame en plein écran
        self.graphics = graphics

        if self.graphics:
            pygame.init()
            self.clock = pygame.time.Clock()

            # Résolution actuelle de l'écran
            infoObject = pygame.display.Info()

            # Ouverture d'une fenêtre
            if fullscreen:
                self.screen = pygame.display.set_mode(flags=pygame.FULLSCREEN)
                self.screen_width, self.screen_height = infoObject.current_w, infoObject.current_h
            else:
                frac = 0.8
                self.screen_width, self.screen_height = int(infoObject.current_w * frac), int(infoObject.current_h * frac)
                self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.RESIZABLE)


            pygame.display.set_caption("Sinfourmis")

            pygame.display.flip()

            # Charger et redimensionner l'image de fond
            self.background = load_image(os.path.join('assets', 'background'))
            self.background = pygame.transform.scale(self.background, (self.screen_width, self.screen_height))
        else:
            self.clock = UselessClock()
            self.screen_width, self.screen_height = 1920, 1080
            self.screen = None

        # Dimensions de référence pour les coordonnées normalisées
        self.reference_width, self.reference_height = 1920, 1080
        
        # Initialisation des objets
        self.items, start_pos, self.item_images, nb_bullets, nb_bricks = read_map(map, self.nc, self.graphics)

        # Initialisation des tanks
        self.tanks = {}
        self.tanks = load_tanks(players, start_pos, nb_bullets, nb_bricks, self.get_free_coord, self.nc, self.graphics)

        self.nb_players = len(self.tanks)

        # Liste de tous les projectiles actuellement sur l'écran
        self.bullets = []

        self.box_image = self.item_images['box']
        self.bullet_image = self.item_images['bullet']
    

    def resize_window(self, new_w, new_h):
        self.screen_width, self.screen_height = new_w, new_h

        # Charger et redimensionner l'image de fond
        self.background = load_image(os.path.join('assets', 'background'))
        self.background = pygame.transform.scale(self.background, (self.screen_width, self.screen_height))
    

    def get_tanks(self):
        return list(self.tanks.values()).copy()

    def kill(self, tank):
        tank.request.suicide()

    def validate_position(self, xp, yp, x, y): # renvoie si une certaine position est correcte d'un point de vue de collision
        # (xp, yp) est la position actuelle du joueur si c'est un joueur et (x, y) est la position visée
        # calcule la distance avec tous les objets
        
        if x > self.reference_width - 20 or x < 20 or y > self.reference_height - 20 or y < 20:
            return False

        # Premier filtre pour calculer moins de distances
        close_items = filter(lambda obj : distance(x, y, obj.xpos, obj.ypos) < 100, self.items)

        # Calcul des collisions sur les objets proches
        for obj in close_items:
            if collision(x, y, obj): # on a trouvé un truc trop près
                return False
        
        tanks = self.get_tanks()
        for tank in tanks: # pour ne pas entrer en collision avec un autre tank
            if (tank.xpos, tank.ypos) != (xp,yp) and tank.health >= 0 and collision_tank(x, y, tank.xpos, tank.ypos):
                return False
        return True
    
    def get_free_coord(self):
        xmin, xmax, ymin, ymax = 10, self.screen_width - 10, 10, self.screen_height - 10
        x,y = random.randint(xmin, xmax), random.randint(ymin, ymax)
        while not self.validate_position(x,y,x,y):
            x,y = random.randint(xmin, xmax), random.randint(ymin, ymax)
        return x, y

    def add_box(self):
        x, y = self.get_free_coord()
        orientation = random.randint(0, 360)
        # on a récupéré les coordonées de la caisse
        box_type = random.choice(['bullets', 'bricks'])
        self.items.append(Item(x, y, orientation, 'box', self.box_image, box_type))


    def update_objects(self, tankname, x, y): # enlève les objets que rencontre le projectile. Si le projectile en a rencontrés, la fonction renvoie True
        for obj in self.items:            
            if collision(x,y,obj):
                obj.ttl -= 1
                if obj.ttl < 0: # l'objet disparait
                    self.items.remove(obj)
                
                return True
        
        tanks = self.get_tanks()
        for tank in tanks: # pour ne pas entrer en collision avec un autre tank
            if tank.name != tankname and tank.health >= 0 and collision_tank(x, y, tank.xpos, tank.ypos):
                tank.health -= 10 # on inflige des dégâts au tank
                
                if tank.health < 0: # le tank va mourir, mais il va mourir de lui-même lorsqu'il verra que sa vie sera < 0
                    tank.request.suicide()
                    print(tank.name, "s'est fait tuer par", tankname)
                return True
        
        return False




    def update_bullets(self): # Cette méthode met à jour les projectiles et les affiche
        new_bullets = []
        for bullet in self.bullets:
            bullet.one_step(self)

            if bullet.alive:
                new_bullets.append(bullet)
        
        self.bullets = new_bullets





    def nc(self, x, y): # calcule les coordonnées réelles à afficher sur l'écran
        normalized_x = int(x * self.screen_width / self.reference_width)
        normalized_y = int(y * self.screen_height / self.reference_height)
        return normalized_x, normalized_y
    
    def nx(self, x):
        normalized_x = int(x * self.screen_width / self.reference_width)
        return normalized_x
    
    def ny(self, y):
        normalized_y = int(y * self.screen_height / self.reference_height)
        return normalized_y

    def draw_text(self, string):
        if self.graphics:
            font = pygame.font.Font(None, self.nx((75 - len(string))*3))
            text = font.render(string, True, (255, 255, 255))
            x, y = self.nx(960) - text.get_width()/2, self.ny(540) - text.get_height()/2
            self.screen.blit(text, (x, y))

    def draw_screen(self): # dessine la map
        
        self.update_bullets()

        if self.graphics:
            # Afficher l'image de fond
            self.screen.blit(self.background, (0, 0))
            
            for obj in self.items:
                obj.display(self)

            tanks = self.get_tanks()
            for tank in tanks:
                tank.display(self)
            
            for bullet in self.bullets:
                bullet.display(self)
            
            # affiche le gagnant s'il y en a un
            if winner := self.winner():
                self.draw_text("Le gagnant est " + winner.name)

            pygame.display.flip()
            self.clock.tick(30)
        else:
            return self.winner()
        

    def nb_alive(self):
        c = 0
        tanks = self.get_tanks()
        for tank in tanks:
            c += tank.health >= 0
        return c
    
    def winner(self):
        if self.nb_alive() != 1 or self.nb_players < 2:
            return None
        else:
            tanks = self.get_tanks()
            for tank in tanks:
                if tank.health >= 0:
                    return tank
    
    def close(self):
        w = self.winner()

        if w != None:
            print("Le gagnant est", w.name)
        
        tanks = self.get_tanks()
        for tank in tanks:
            self.kill(tank)
        
    def wait_key(self):
        if self.graphics:
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.KEYDOWN:
                        return


    def countdown(self):
        if self.graphics:
            self.draw_text("Êtes vous prêts ?")
            pygame.display.flip()

            self.wait_key()

            self.draw_screen()
            self.draw_text("Le jeu va commencer dans...")
            pygame.display.flip()

            time.sleep(1)
            
            self.draw_screen()
            self.draw_text("3")
            pygame.display.flip()

            time.sleep(1)

            self.draw_screen()
            self.draw_text("2")
            pygame.display.flip()

            time.sleep(1)

            self.draw_screen()
            self.draw_text("1")
            pygame.display.flip()

            time.sleep(1)



    def launch_players(self):
        # lancement des programmes associés à chaque joueur
        tanks = self.get_tanks()
        for tank in tanks:
            # récupère le code à exécuter pour ce tank
            f = open('computers/' + tank.file, 'r')
            code = f.read()
            f.close()
            
            # pipes de connextion entre le processus et son thread
            requestEnd, requestEntry = multiprocessing.Pipe(duplex = False)
            responseEnd, responseEntry = multiprocessing.Pipe(duplex = False)
            tank.request = Request(tank.name, requestEntry, responseEnd)

            # certaines plateformes d'exécution (autres que Linux) ne supportent pas bien le multiprocessing
            tank.process = multiprocessing.Process(target = clientFunction, args = (code, tank.request)) # crée le fil d'exécution de ce joueur
            tank.process.start()
            
            # démarrage du serveur
            serverThread = threading.Thread(target = serverFunction, args = (requestEnd, responseEntry, self, tank.name))
            serverThread.start()




def launch_game(players, map, graphics, fullscreen, countdown):
    # ignore le facteur d'agrandissement d'interface de windows
    if 'win' in sys.platform:
        ctypes.windll.user32.SetProcessDPIAware()

    game = Game(players, map, graphics, fullscreen)
    
    if countdown:
        game.countdown()

    game.launch_players()

    # Boucle principale du jeu
    running = True

    t0 = time.monotonic()
    apparition_box = 40 # temps d'apparition des caisses

    while running:
        if graphics:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    game.resize_window(event.w, event.h)

                elif event.type == pygame.WINDOWSIZECHANGED:
                    game.resize_window(event.x, event.y)

        # Dessiner la map
        winner = game.draw_screen()

        if not graphics and winner:
            break
        
        if time.monotonic() - t0 > apparition_box:
            game.add_box()
            t0 = time.monotonic()


    # finit tous les threads
    game.close()
    if graphics:
        pygame.quit()
    sys.exit()




if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--map', nargs = 1, default = ["settings/map.yaml"], help = "YAML file to use for the map")
    parser.add_argument('--players', nargs = 1, default = ["settings/players.yaml"], help = "YAML file to use for the players")
    parser.add_argument('--nographics', nargs = '?', const = True, help = "Disables graphics")
    parser.add_argument('--fullscreen', nargs = '?', const = True, help = "Opens the game in fullscreen mode")
    parser.add_argument('--countdown', nargs = '?', const = True, help = "Plays a countdown before launching game")

    args = parser.parse_args()

    map = args.map[0]
    players = args.players[0]
    graphics = args.nographics is None
    fullscreen = not (args.fullscreen is None)
    countdown = not (args.countdown is None)

    if graphics:
        import pygame
    
    try:
        launch_game(players, map, graphics, fullscreen, countdown)
    except KeyboardInterrupt:
        pass
