import pygame
import sys
import math
import random
import os
from collections import deque
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        # exe打包后，临时解压文件夹
        base_path = sys._MEIPASS
    else:
        # PyCharm直接运行，用代码所在文件夹
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
pygame.init()
icon_img = pygame.image.load(resource_path("gameicon.png"))
pygame.display.set_icon(icon_img)
# 处理pyinstaller的--splash启动画面
try:
    import pyi_splash
    pyi_splash.close()   # 强制关闭打包自带splash窗口
except ImportError:
    pass  # 在python直接运行的时候没有这个模块，直接跳过

# ========== 窗口与世界 ==========
WINDOW_W, WINDOW_H = 1200, 800
screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
pygame.display.set_caption("CubeEscape")

TILE = 40
GRID_W, GRID_H = 101, 101          # 必须奇数，递归回溯算法要求
WORLD_W, WORLD_H = GRID_W * TILE, GRID_H * TILE

# ========== 颜色 ==========
WHITE  = (255, 255, 255)
RED    = (255, 40, 40)
YELLOW = (255, 210, 0)
PURPLE = (200, 60, 255)
SPIKE  = (255, 130, 30)
GRAY   = (80, 80, 80)
BLACK  = (0, 0, 0)
TEXT_C = (255, 255, 0)
GREEN = (40, 255, 60)

# ========== 实体尺寸 ==========
PLAYER_SIZE = 24
ENEMY_SIZE  = 28
TURRET_SIZE = 32
PHANTOM_SIZE = 26

player_speed = 5
enemy_speed  = 2.0
turret_speed = 1.0
spike_speed  = 6
shoot_interval = 55

phantom_charge_interval = 120    # 每2秒锁定一次
phantom_charge_speed = 7         # 冲刺速度

# ========== 全局变量 ==========
maze = None
walls = []
player = None
enemies = []
turrets = []
phantoms = []
spikes = []
game_over = False
win_flag = False
camera_x = 0
camera_y = 0
goal = pygame.Rect(0, 0, 30, 30)

# ========== 工具函数 ==========
def generate_maze(w, h):
    """递归回溯算法生成迷宫，1=墙，0=路"""
    maze = [[1]*w for _ in range(h)]
    stack = [(1, 1)]
    maze[1][1] = 0
    dirs = [(0,2),(0,-2),(2,0),(-2,0)]
    while stack:
        cx, cy = stack[-1]
        nb = []
        for dx, dy in dirs:
            nx, ny = cx+dx, cy+dy
            if 0 <= nx < w and 0 <= ny < h and maze[ny][nx] == 1:
                nb.append((nx, ny, dx, dy))
        if nb:
            nx, ny, dx, dy = random.choice(nb)
            maze[cy+dy//2][cx+dx//2] = 0
            maze[ny][nx] = 0
            stack.append((nx, ny))
        else:
            stack.pop()
    # 额外挖掉一些墙，让迷宫不那么死，增加四通八达
    for _ in range(600):
        rx = random.randint(1, w-2)
        ry = random.randint(1, h-2)
        if maze[ry][rx] == 1:
            maze[ry][rx] = 0
    return maze

def free_cells(maze):
    cells = []
    for y in range(len(maze)):
        for x in range(len(maze[0])):
            if maze[y][x] == 0:
                cells.append((x, y))
    return cells

def cell_center(cx, cy, size):
    """格子中心生成一个居中的Rect"""
    return pygame.Rect(
        cx*TILE + (TILE - size)//2,
        cy*TILE + (TILE - size)//2,
        size, size
    )

def bfs_path(maze, start_cell, goal_cell):
    """BFS寻路，返回格子路径列表[(x,y),...]"""
    h, w = len(maze), len(maze[0])
    if start_cell == goal_cell:
        return [start_cell]
    q = deque([start_cell])
    prev = {start_cell: None}
    dirs = [(0,1),(0,-1),(1,0),(-1,0)]
    found = False
    while q:
        cx, cy = q.popleft()
        if (cx, cy) == goal_cell:
            found = True
            break
        for dx, dy in dirs:
            nx, ny = cx+dx, cy+dy
            if (0 <= nx < w and 0 <= ny < h
                and maze[ny][nx] == 0
                and (nx, ny) not in prev):
                prev[(nx, ny)] = (cx, cy)
                q.append((nx, ny))
    if not found:
        return []
    path = []
    cur = goal_cell
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path

def rect_cell(rect):
    """把屏幕上的Rect中心换算成格子坐标"""
    return (rect.centerx // TILE, rect.centery // TILE)

def collide_walls(rect, wall_list):
    for w in wall_list:
        if rect.colliderect(w):
            return True
    return False

# ========== 重置游戏 ==========
def reset_game():
    global maze, walls, player, enemies, turrets, phantoms, spikes, game_over, win_flag, goal
    maze = generate_maze(GRID_W, GRID_H)
    walls = []
    for y in range(GRID_H):
        for x in range(GRID_W):
            if maze[y][x] == 1:
                walls.append(pygame.Rect(x*TILE, y*TILE, TILE, TILE))

    cells = free_cells(maze)
    random.shuffle(cells)
    idx = 0

    # 玩家
    player = cell_center(*cells[idx], PLAYER_SIZE); idx += 1

    # 10个红敌人
    enemies = []
    for _ in range(10):
        enemies.append(cell_center(*cells[idx], ENEMY_SIZE)); idx += 1

    # 7个黄炮塔
    turrets = []
    for _ in range(7):
        turrets.append({
            "rect": cell_center(*cells[idx], TURRET_SIZE),
            "cooldown": random.randint(0, shoot_interval)
        })
        idx += 1

    # 3个紫幻影
    phantoms = []
    for _ in range(3):
        phantoms.append({
            "rect": cell_center(*cells[idx], PHANTOM_SIZE),
            "idle": random.randint(0, phantom_charge_interval),
            "path": [],
            "path_i": 0,
            "charging": False
        })
        idx += 1
    #绿色终点
    goal = cell_center(*cells[idx], 30); idx += 1

    spikes = []
    game_over = False
    win_flag = False

reset_game()

clock = pygame.time.Clock()
big_font = pygame.font.SysFont(None, 80)
sm_font = pygame.font.SysFont(None, 28)

# ========== 主循环 ==========
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit(); sys.exit()
        # 死亡/胜利后按任意键重开
        if event.type == pygame.KEYDOWN and game_over:
            reset_game()

    if not game_over:
        # ---- 玩家移动 ----
        keys = pygame.key.get_pressed()
        dx, dy = 0, 0
        if keys[pygame.K_LEFT]:  dx -= player_speed
        if keys[pygame.K_RIGHT]: dx += player_speed
        if keys[pygame.K_UP]:    dy -= player_speed
        if keys[pygame.K_DOWN]:  dy += player_speed

        player.x += dx
        if collide_walls(player, walls): player.x -= dx
        player.y += dy
        if collide_walls(player, walls): player.y -= dy

        # 终点碰撞检测
        if goal is not None and player.colliderect(goal):
            game_over = True
            win_flag = True

        # ---- 10个红敌人追击 ----
        for e in enemies:
            ox = e.x
            if e.centerx < player.centerx: e.x += enemy_speed
            elif e.centerx > player.centerx: e.x -= enemy_speed
            if collide_walls(e, walls): e.x = ox
            oy = e.y
            if e.centery < player.centery: e.y += enemy_speed
            elif e.centery > player.centery: e.y -= enemy_speed
            if collide_walls(e, walls): e.y = oy
            if player.colliderect(e): game_over = True

        # ---- 7个黄炮塔 ----
        for t in turrets:
            r = t["rect"]
            ox = r.x
            if r.centerx < player.centerx: r.x += turret_speed
            elif r.centerx > player.centerx: r.x -= turret_speed
            if collide_walls(r, walls): r.x = ox
            oy = r.y
            if r.centery < player.centery: r.y += turret_speed
            elif r.centery > player.centery: r.y -= turret_speed
            if collide_walls(r, walls): r.y = oy
            if player.colliderect(r): game_over = True

            t["cooldown"] += 1
            if t["cooldown"] >= shoot_interval:
                t["cooldown"] = 0
                dx_d = player.centerx - r.centerx
                dy_d = player.centery - r.centery
                d = math.hypot(dx_d, dy_d)
                if d > 0:
                    vx = dx_d/d*spike_speed
                    vy = dy_d/d*spike_speed
                    sp = pygame.Rect(r.centerx-5, r.centery-5, 10, 10)
                    spikes.append([sp, vx, vy])

        # ---- 子弹（穿墙） ----
        for s in spikes[:]:
            sr, vx, vy = s
            sr.x += vx; sr.y += vy
            if (sr.right < 0 or sr.left > WORLD_W or
                sr.bottom < 0 or sr.top > WORLD_H):
                spikes.remove(s); continue
            if sr.colliderect(player): game_over = True

        # ---- 紫幻影：锁定+寻路+冲刺 ----
        for p in phantoms:
            r = p["rect"]
            if not p["charging"]:
                p["idle"] -= 1
                if p["idle"] <= 0:
                    # 锁定玩家当前格子
                    target_cell = rect_cell(player)
                    start = rect_cell(r)
                    path = bfs_path(maze, start, target_cell)
                    if len(path) >= 2:
                        p["path"] = path
                        p["path_i"] = 0
                        p["charging"] = True
                    else:
                        p["idle"] = phantom_charge_interval
            else:
                # 沿路径冲刺到下一个格子中心
                if p["path_i"] < len(p["path"]):
                    tx, ty = p["path"][p["path_i"]]
                    target_x = tx*TILE + TILE//2
                    target_y = ty*TILE + TILE//2
                    dx_d = target_x - r.centerx
                    dy_d = target_y - r.centery
                    d = math.hypot(dx_d, dy_d)
                    if d < phantom_charge_speed:
                        r.centerx = target_x
                        r.centery = target_y
                        p["path_i"] += 1
                    else:
                        r.centerx += dx_d/d*phantom_charge_speed
                        r.centery += dy_d/d*phantom_charge_speed
                else:
                    # 冲完一段，进入冷却
                    p["charging"] = False
                    p["idle"] = phantom_charge_interval

            if player.colliderect(r): game_over = True

        # ---- 摄像头跟随 ----
        tcx = player.centerx - WINDOW_W//2
        tcy = player.centery - WINDOW_H//2
        camera_x = max(0, min(tcx, WORLD_W - WINDOW_W))
        camera_y = max(0, min(tcy, WORLD_H - WINDOW_H))

    # ========== 绘制 ==========
    screen.fill(BLACK)
    for w in walls:
        pygame.draw.rect(screen, GRAY, w.move(-camera_x, -camera_y))
    #绘制绿色终点
    pygame.draw.rect(screen, GREEN, goal.move(-camera_x, -camera_y))
    for t in turrets:
        pygame.draw.rect(screen, YELLOW, t["rect"].move(-camera_x, -camera_y))
    for e in enemies:
        pygame.draw.rect(screen, RED, e.move(-camera_x, -camera_y))
    for p in phantoms:
        pygame.draw.rect(screen, PURPLE, p["rect"].move(-camera_x, -camera_y))
    for sr, _, _ in spikes:
        pygame.draw.rect(screen, SPIKE, sr.move(-camera_x, -camera_y))
    pygame.draw.rect(screen, WHITE, player.move(-camera_x, -camera_y))

    if game_over:
        if win_flag:
            text = big_font.render("You Win", True, GREEN)
        else:
            text = big_font.render("GAME OVER!", True, TEXT_C)
        screen.blit(text, (WINDOW_W//2-180, WINDOW_H//2-40))
        t2 = sm_font.render("Press any key to restart", True, WHITE)
        screen.blit(t2, (WINDOW_W//2-140, WINDOW_H//2+40))

    info = sm_font.render(
        f"FPS:{int(clock.get_fps())} | Enemies:{len(enemies)} "
        f"Turrets:{len(turrets)} Phantoms:{len(phantoms)} Spikes:{len(spikes)}",
        True, (200,200,200))
    screen.blit(info, (10, 10))

    pygame.display.flip()
    clock.tick(60)
