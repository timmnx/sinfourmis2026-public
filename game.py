import os
import sys
import yaml
import math
import time
import ctypes
import random
import argparse
import threading
import multiprocessing
if __name__ != '__main__':
    import pygame

FORWARD_DOP = 3
BACKWARD_DOP = -1
LEGAL_CHEATING_SCORE = 500
MAX_CHEATING_SCORE = 2000


if 'linux' in sys.platform:
    import signal
    multiprocessing.set_start_method("fork")


def platformSpecificExit():
    if 'linux' in sys.platform:
        os.kill(os.getpid(), 9)
    else:
        sys.exit()


class UselessClock:
    def __init__(self):
        pass
    def tick(self, _):
        pass



class Wrapper:
    def __init__(self, function):
        self.function = function
    
    def call(self, *args, **kwargs):
        return super().__getattribute__('function')(*args, **kwargs)

    def __getattribute__(self, name):
        if name == 'call':
            return super().__getattribute__('call')

def make_func(function, request, clock):
    name = ''.join([chr(random.randint(97, 122)) for _ in range(random.randint(100, 200))])
    code = \
        "class " + name + """:
            def __init__(self, function, request, clock = None):
                self.__function = function
                self.__request = request
                self.__clock = clock
            
            def call(self, *args, **kwargs):
                return self.__function(self.__request, self.__clock, *args, *kwargs)"""
    
    namespace = {}
    exec(code, namespace)
    obj_call = namespace[name](function, request, clock).call

    def func(*args):
        return obj_call(*args)

    return Wrapper(func).call





class Item:
    def __init__(self, xpos, ypos, orientation, type, image, box_type):
        self.xpos = xpos
        self.ypos = ypos
        self.image = image
        self.type = type
        self.box_type = box_type
        self.orientation = orientation
        
        if type == 'tree':
            self.ttl = 1
        elif type == 'wall':
            self.ttl = 10
        else:
            self.ttl = math.inf
    
    def __eq__(self, obj):
        return type(obj) == Item and (self.xpos, self.ypos, self.type) == (obj.xpos, obj.ypos, obj.type)
    
    def display(self, game):
        rotated_image = pygame.transform.rotate(self.image, self.orientation)
        rect = rotated_image.get_rect(center = game.nc(self.xpos,self.ypos))
        game.screen.blit(rotated_image, rect.topleft)



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





def skip_request(reqType, tank):
    return random.random() <= tank.cheating_proba() and reqType in ("setState", "addBullet", "addWall")




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
        self.cheating_score = 0
        self.nb_requests = 0

        # Précalcul de l'image du tank pour toutes les orientations
        if self.image: # On ne précalcule les rotations que si self.image est une image valide
            self.angles = [pygame.transform.rotate(self.image, angle) for angle in range(360)]
    

    def update_cheating_score(self, args1, args2, norm):
        self.cheating_score = (self.cheating_score * self.nb_requests + cheating_score(args1, args2, norm))/(self.nb_requests + 1)
        self.nb_requests += 1
    
    def cheating_proba(self):
        if self.cheating_score < LEGAL_CHEATING_SCORE:
            return 0
        elif self.cheating_score > MAX_CHEATING_SCORE:
            return 1
        else:
            # probabilité que l'on n'exécute pas une requête
            proba = (self.cheating_score - LEGAL_CHEATING_SCORE)/(MAX_CHEATING_SCORE - LEGAL_CHEATING_SCORE)
            return proba
    
    def display(self, game):
        # display the sprite
        rotated_image = self.angles[int(self.orientation)%360]
        rect = rotated_image.get_rect(center = game.nc(self.xpos,self.ypos))
        game.screen.blit(rotated_image, rect.topleft)

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
    def __init__(self, requestEntry, responseEnd):
        self.requestEntry = requestEntry
        self.responseEnd = responseEnd
    
    def safe_recv(self):
        try:
            response = self.responseEnd.recv()
        except:
            response = "DIEPLZ"
        
        if response == "DIEPLZ":
            #self.responseEnd.close()
            self.requestEntry.send("OKIMDEAD")
            #self.requestEntry.close()
            platformSpecificExit()
        else:
            return response
    
    def make_request(*args):
        self = args[0]
        self.requestEntry.send(args[1:])
        return self.safe_recv()

    def make_unidirectional_request(*args): # pour les requêtes n'attendant pas de réponse
        self = args[0]
        self.requestEntry.send(args[1:])
    
    def validate_position(self, xp, yp, x, y):
        return self.make_request("validatePosition", xp, yp, x, y)

    def getState(self): # renvoie un tuple (xpos, ypos, orientation, health, nb_bullets, nb_bricks, lastshot)
        return self.make_request("getState")
    
    def setState(self, xpos, ypos, orientation, health, nb_bullets, nb_bricks, lastshot): # attend en argument un tuple (xpos, ypos, orientation, health, nb_bullets)
        return self.make_unidirectional_request("setState", xpos, ypos, orientation, health, nb_bullets, nb_bricks, lastshot)
    
    def addBullet(self, x, y, orientation, ttl = 30):
        return self.make_unidirectional_request("addBullet", x, y, orientation, ttl)
    
    def removeBox(self, x, y):
        return self.make_unidirectional_request("removeBox", x, y)
    
    def addWall(self, x, y, theta):
        return self.make_unidirectional_request("addWall", x, y, theta)
    
    def getItems(self):
        return self.make_request("getItems")
    
    def getTanks(self):
        return self.make_request("getTanks")



def cheating_score(args1, args2, norm):
    assert len(args1) == len(args2)
    score = sum([abs(arg1-arg2)*10000/max_value for (arg1, arg2, max_value) in zip(args1, args2, norm)])/len(args1)
    return score



def serverFunction(requestEnd, responseEntry, game, name):
    tank = game.tanks[name]

    while True:
        # Si le tank est mort, on close la connexion pour qu'il soit au courant qu'il est mort, et on arrête le serveur de requêtes
        if tank.health < 0:
            responseEntry.send("DIEPLZ")
            #responseEntry.close()
            
            response = None
            while response != "OKIMDEAD":
                try:
                    response = requestEnd.recv()
                except:
                    break
            #requestEnd.close()
            del game.tanks[name]
            return

        # Attente d'une requête
        try:
            request = requestEnd.recv()
        except:
            return

        reqType = request[0]
        args = request[1:]
        
        # Liste des requêtes "critiques", que l'on s'autorise à skipper
        if skip_request(reqType, tank):
            continue

        if reqType == "getState":
            ret = (tank.xpos, tank.ypos, tank.orientation, tank.health, tank.nb_bullets, tank.nb_bricks, tank.lastshot)
            responseEntry.send(ret)
        
        elif reqType == "setState":
            tank.update_cheating_score(
                [tank.xpos, tank.ypos, tank.orientation, tank.health],
                args[:-3],
                [1920, 1080, 360, 100]
            )

            tank.xpos, tank.ypos, tank.orientation, tank.health, tank.nb_bullets, tank.nb_bricks, tank.lastshot = args

        elif reqType == "addBullet":
            xpos, ypos, orientation, ttl = args
            tank.update_cheating_score(
                [xpos, ypos, orientation, ttl**2],
                [tank.xpos, tank.ypos, tank.orientation, 30**2],
                [1920, 1080, 360, 100]
            )
            game.bullets.append(Bullet(xpos, ypos, orientation, name, game.bullet_image, ttl))
        
        elif reqType == "addWall":
            xpos, ypos, theta = args
            tank.update_cheating_score(
                [xpos, ypos, theta],
                [tank.xpos, tank.ypos, tank.orientation],
                [1920, 1080, 360]
            )
            game.items.append(Item(xpos, ypos, theta, 'wall', game.item_images['wall'], None))
        

        elif reqType == "removeBox":
            x, y = args            
            for i, it in enumerate(game.items):
                if it.type == 'box' and (it.xpos, it.ypos) == (x, y):
                    del game.items[i]
                    break
            
        elif reqType == "getItems":
            responseEntry.send([Item(item.xpos, item.ypos, item.orientation, item.type, None, item.box_type) for item in game.items])
            
        elif reqType == "getTanks":
            tanks = game.get_tanks()
            responseEntry.send([Tank(tank.xpos, tank.ypos, None, None, tank.name) for tank in tanks])
        
        elif reqType == "validatePosition":
            xp, yp, x, y = args
            responseEntry.send(game.validate_position(xp, yp, x, y))







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



def diff_collision(x, y, angle, obj):
    dx = math.cos(angle/180*math.pi) * FORWARD_DOP
    dy = -math.sin(angle/180*math.pi) * FORWARD_DOP
    return collision(x+dx, y+dy, obj)


def diff_collision_tank(x,y,angle,xo, yo):
    dx = math.cos(angle/180*math.pi) * FORWARD_DOP
    dy = -math.sin(angle/180*math.pi) * FORWARD_DOP
    return collision_tank(x+dx, y+dy, xo, yo)
    

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







def diff_angle(theta0, theta1): # estime à quel point deux angles sont différents
    diff = abs(theta0 - theta1)
    return diff if diff < math.pi/2 else math.pi - diff





def on_trajectory(x, y, theta0, x2, y2):    
    
    if x != x2:
        angle_coeff = math.atan(-(y-y2)/(x-x2))
    else:
        angle_coeff = math.pi/2
    # calcule l'angle formé entre player et l'objet
    
    theta = theta0 * math.pi/180
    if theta > math.pi:
        theta = theta - 2*math.pi
    # theta est entre pi et -pi
    if theta > math.pi/2:
        theta -= math.pi
    elif theta < -math.pi/2:
        theta += math.pi
        
    # vérifie que l'objet est sur la bonne droite
    bo = diff_angle(theta, angle_coeff) < 0.1 # en radians
    
    # on a vérifié les histoires de direction, maintenant, on vérifie que c'est le bon sens
    if theta0 <= 90: # 1er cadran
        return bo and x2 >= x and y2 <= y
    elif theta0 <= 180:#deuxième cadran
        return bo and x2 <= x and y2 <= y
    elif theta0 <= 270: # troisième cadran
        return bo and x2 <= x and y2 >= y
    else:#dernier cadran
        return bo and x2 >= x and y2 >= y


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
            items.append(Item(object['position'][0], object['position'][1], orientation, object['type'], item_images[object['type']], None))
    
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



    def validate_position(self, xp, yp, x, y): # renvoie si une certaine position est correcte d'un point de vue de collision
        # (xp, yp) est la position actuelle du joueur si c'est un joueur et (x, y) est la position visée
        # calcule la distance avec tous les objets
        
        if x > self.reference_width-20 or x < 20 or y > self.reference_height-20 or y < 20:
            return False

        for obj in self.items:
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
                    print(tank.name, "s'est fait tuer par", tankname)
                    print(f"{tank.name} est estimé à {int(tank.cheating_proba()*100)}% comme étant un tricheur\n")
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
            print(f"{w.name} est estimé à {int(w.cheating_proba()*100)}% comme étant un tricheur\n")
        
        tanks = self.get_tanks()
        for tank in tanks:
            tank.health = -1


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
        for name in self.tanks:
            # récupère le code à exécuter pour ce tank
            f = open('computers/' + self.tanks[name].file, 'r')
            code = f.read()
            f.close()
            
            # pipes de connextion entre le processus et son thread
            requestEnd, requestEntry = multiprocessing.Pipe(duplex = False)
            responseEnd, responseEntry = multiprocessing.Pipe(duplex = False)
            request = Request(requestEntry, responseEnd)

            variables = {
                "fire":             make_func(fire, request, self.clock),
                "get_position":     make_func(get_position, request, self.clock),
                "get_health":       make_func(get_health, request, self.clock),
                "get_orientation":  make_func(get_orientation, request, self.clock),
                "get_nb_bullets":   make_func(get_nb_bullets, request, self.clock),
                "get_nb_bricks":    make_func(get_nb_bricks, request, self.clock),
                "move":             make_func(move, request, self.clock),
                "back":             make_func(back, request, self.clock),
                "rotate_right":     make_func(rotate_right, request, self.clock),
                "rotate_left":      make_func(rotate_left, request, self.clock),
                "grab_box":         make_func(grab_box, request, self.clock),
                "add_wall":         make_func(add_wall, request, self.clock),
                "detect":           make_func(detect, request, self.clock),
                "distance":         distance,
                "time":             time,
                "math":             math,
                "random":           random,
                "__playername":     name
            }

            # certaines plateformes d'exécution (autres que Linux) ne supportent pas bien le multiprocessing
            if 'linux' in sys.platform:
                tankProcess = multiprocessing.Process(target = exec, args = (code, variables)) # crée le fil d'exécution de ce joueur
            else:
                tankProcess = threading.Thread(target = exec, args = (code, variables)) # crée le fil d'exécution de ce joueur
            
            tankProcess.start()
            
            # démarrage du serveur
            serverThread = threading.Thread(target = serverFunction, args = (requestEnd, responseEntry, self, name))
            serverThread.start()



######################## FONCTIONS D'INTERFACE DES TANKS #############################

'''
Ces fonction s'exécutent dans le processus du tank qui les lancent,
elles utilisent des pipes pour communiquer avec leur thread serveur
'''

def get_position(request, clock):
    xpos, ypos, _, _, _, _, _ = request.getState()
    return xpos, ypos
    

def get_health(request, clock):
    _, _, _, health, _, _, _ = request.getState()
    return health


def get_orientation(request, clock):
    _, _, orientation, _, _, _, _ = request.getState()
    return orientation

def get_nb_bricks(request, clock):
    _, _, _, _, _, nb_bricks, _ = request.getState()
    return nb_bricks


def get_nb_bullets(request, clock):
    _, _, _, _, nb_bullets, _, _ = request.getState()
    return nb_bullets


# bibliothèque de déplacement des joueurs
def move(request, clock):    
    x, y, theta, health, nb_bullets, nb_bricks, lastshot = request.getState()

    dx = math.cos(theta/180*math.pi) * FORWARD_DOP
    dy = -math.sin(theta/180*math.pi) * FORWARD_DOP
    if request.validate_position(x, y, x+dx, y+dy): # permet de tester les collisions
        request.setState(x+dx, y+dy, theta, health, nb_bullets, nb_bricks, lastshot)
    
    clock.tick(60)
    





def back(request, clock):    
    x, y, theta, health, nb_bullets, nb_bricks, lastshot = request.getState()

    dx = math.cos(theta/180*math.pi) * BACKWARD_DOP
    dy = -math.sin(theta/180*math.pi) * BACKWARD_DOP
    if request.validate_position(x, y, x+dx, y+dy): # permet de tester les collisions
        request.setState(x+dx, y+dy, theta, health, nb_bullets, nb_bricks, lastshot)
    
    clock.tick(200)



def rotate_right(request, clock):    
    x, y, theta, health, nb_bullets, nb_bricks, lastshot = request.getState()

    dtheta = 1
    theta -= dtheta
    if theta < 0:
        theta += 360
    
    request.setState(x, y, theta, health, nb_bullets, nb_bricks, lastshot)
    clock.tick(250)
    



def rotate_left(request, clock):
    x, y, theta, health, nb_bullets, nb_bricks, lastshot = request.getState()

    dtheta = 1
    theta += dtheta
    if theta > 360:
        theta -= 360
    
    request.setState(x, y, theta, health, nb_bullets, nb_bricks, lastshot)

    clock.tick(250)
    



def fire(request, clock):
    x, y, theta, health, nb_bullets, nb_bricks, lastshot = request.getState()

    if nb_bullets <= 0 or time.monotonic() - lastshot < 0.3 :
        return False # on ne peut plus tirer, il n'y a plus de projectiles
    
    request.setState(x, y, theta, health, nb_bullets - 1, nb_bricks, time.monotonic())
    request.addBullet(x, y, theta)
    return True




def detect(request, clock): # chaque tank est doté d'un capteur qui pointe devant lui et renvoie une liste des objets rencontrés et leur distance
    x, y, theta, health, _, _, _ = request.getState()

    items = request.getItems()
    tanks = request.getTanks()
    
    detected = []
    # boucle sur les objets pour savoir si un objet se situe sur l'hypoténuse du triangle rectangle formé par les coordonnées du tank
    for obj in items:
        if diff_collision(x,y,theta,obj) or on_trajectory(x, y, theta, obj.xpos, obj.ypos):
            detected.append((obj.type, distance(x,y,obj.xpos,obj.ypos)))
    
    for tank in tanks:
        xo, yo = tank.xpos, tank.ypos
        if (xo,yo) != (x,y) and tank.health >= 0 and (diff_collision_tank(x,y,theta,xo,yo) or on_trajectory(x, y, theta, xo, yo)): # en collision avec le tank ou il est devant
            detected.append(('tank', distance(x,y,xo,yo)))
    
    return detected
    





def grab_box(request, clock):    
    xpos, ypos, theta, health, nb_bullets, nb_bricks, lastshot = request.getState()

    items = request.getItems()
    
    for obj in items:
        if obj.type == 'box' and distance(xpos, ypos, obj.xpos, obj.ypos) < 20: # la boite peut être attrapée
            request.removeBox(obj.xpos, obj.ypos)
            if obj.box_type == 'bullets':
                request.setState(xpos, ypos, theta, health, nb_bullets + 200, nb_bricks, lastshot)
            elif obj.box_type == 'bricks':
                request.setState(xpos, ypos, theta, health, nb_bullets, nb_bricks + 20, lastshot)
            return True
    
    return False


def add_wall(request, clock):    
    xpos, ypos, theta, health, nb_bullets, nb_bricks, lastshot = request.getState()
    dx = math.cos(theta/180*math.pi) * 50
    dy = -math.sin(theta/180*math.pi) * 50
    wall_x, wall_y = xpos + dx, ypos + dy
    
    if nb_bricks > 0 and request.validate_position(wall_x, wall_y, wall_x, wall_y):
        request.setState(xpos, ypos, theta, health, nb_bullets, nb_bricks - 1, lastshot)
        request.addWall(wall_x, wall_y, theta)
        return True
    else:
        return False


################################ FIN FONCTION INTERFACE TANKS ############################



def launch_game(players, map, graphics, fullscreen):
    # ignore le facteur d'agrandissement d'interface de windows
    if 'win' in sys.platform:
        ctypes.windll.user32.SetProcessDPIAware()

    game = Game(players, map, graphics, fullscreen)
    #game.countdown()

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

    args = parser.parse_args()

    map = args.map[0]
    players = args.players[0]
    graphics = args.nographics is None
    fullscreen = not (args.fullscreen is None)

    if graphics:
        import pygame

    launch_game(players, map, graphics, fullscreen)