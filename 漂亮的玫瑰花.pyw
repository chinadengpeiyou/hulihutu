import os
import sys
import math
import random
import ctypes
import pygame

# ============================================================
# 1. 初始化
# ============================================================
pygame.init()

WIDTH, HEIGHT = 800, 800
TRANSPARENT_COLOR = (0, 0, 0)  # Windows 窗口抠除色

# 获取屏幕尺寸
info = pygame.display.Info()
screen_w, screen_h = info.current_w, info.current_h

# 计算窗口居中坐标（先保存，透明设置完再移动窗口）
window_x = (screen_w - WIDTH) // 2
window_y = (screen_h - HEIGHT) // 2

# 关键：先把窗口创建到屏幕外面，避免透明生效前的闪烁
os.environ["SDL_VIDEO_WINDOW_POS"] = "-32000,-32000"

# 硬件加速 + 双缓冲 + 无边框
screen = pygame.display.set_mode(
    (WIDTH, HEIGHT),
    pygame.NOFRAME | pygame.HWSURFACE | pygame.DOUBLEBUF
)
pygame.display.set_caption("Vivid Natural Rose")
clock = pygame.time.Clock()
CENTER = (WIDTH // 2, HEIGHT // 2 + 20)


# ============================================================
# 2. Windows 透明窗口（修复闪烁版）
# ============================================================
def make_window_transparent(x, y, win_w, win_h):
    hwnd = pygame.display.get_wm_info()["window"]
    user32 = ctypes.windll.user32

    # 常量定义
    SW_HIDE = 0
    SW_SHOW = 5
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    LWA_COLORKEY = 0x00000001

    # 第一步：立刻隐藏窗口，双重保险
    user32.ShowWindow(hwnd, SW_HIDE)

    # 第二步：设置分层窗口属性
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)

    # 设置透明色
    color_key = (
        TRANSPARENT_COLOR[0]
        | (TRANSPARENT_COLOR[1] << 8)
        | (TRANSPARENT_COLOR[2] << 16)
    )
    user32.SetLayeredWindowAttributes(hwnd, color_key, 0, LWA_COLORKEY)

    # 第三步：移动窗口到居中位置
    user32.MoveWindow(hwnd, x, y, win_w, win_h, True)

    # 第四步：属性全部生效后再显示窗口
    user32.ShowWindow(hwnd, SW_SHOW)


# 传入居中坐标，设置透明并移动窗口
make_window_transparent(window_x, window_y, WIDTH, HEIGHT)

# 提前渲染第一帧透明背景，确保显示时就是透明状态
screen.fill(TRANSPARENT_COLOR)
pygame.display.flip()


# ============================================================
# 3. 预计算玫瑰花瓣点
# ============================================================
def init_rose_points(max_petals=2800):
    points = []
    golden_angle = math.pi * (3 - math.sqrt(5))
    petal_lobes = 5

    for i in range(1, max_petals + 1):
        theta = i * golden_angle
        t = i / max_petals

        lobe_mod = 1 + 0.32 * math.sin(theta * petal_lobes) * t
        base_r = t * lobe_mod

        # 鲜艳自然的红玫瑰渐变
        if t < 0.18:
            # 花心：深酒红
            k = t / 0.18
            r_col = int(110 + 90 * k)
            g_col = int(15 + 25 * k)
            b_col = int(35 + 35 * k)
        elif t < 0.45:
            # 中层：鲜红玫瑰色
            k = (t - 0.18) / 0.27
            r_col = int(200 + 50 * k)
            g_col = int(40 + 70 * k)
            b_col = int(70 + 60 * k)
        elif t < 0.75:
            # 外层：高饱和玫红
            k = (t - 0.45) / 0.30
            r_col = 255
            g_col = int(110 + 50 * k)
            b_col = int(130 + 40 * k)
        else:
            # 边缘：亮粉高光
            k = (t - 0.75) / 0.25
            r_col = 255
            g_col = int(160 + 60 * k)
            b_col = int(180 + 50 * k)

        size = 1.2 + 2.8 * t

        points.append({
            "theta": theta,
            "t": t,
            "base_r": base_r,
            "color": (r_col, g_col, b_col),
            "size": size
        })

    return points


ROSE_POINTS = init_rose_points(max_petals=2800)


# ============================================================
# 4. 烟花粒子（带表面缓存）
# ============================================================
class Particle:
    _surface_cache = {}

    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color

        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(2, 9)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed

        self.alpha = 255
        self.decay = random.uniform(2.5, 5)
        self.gravity = 0.12
        self.size = random.uniform(2, 4)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        self.vx *= 0.98
        self.alpha -= self.decay
        return self.alpha > 0

    def draw(self, surface):
        if self.alpha <= 0:
            return

        cache_key = (int(self.size * 2), self.color)
        if cache_key not in Particle._surface_cache:
            s = pygame.Surface(
                (int(self.size * 2), int(self.size * 2)),
                pygame.SRCALPHA
            )
            pygame.draw.circle(
                s, self.color,
                (int(self.size), int(self.size)),
                self.size
            )
            Particle._surface_cache[cache_key] = s
        else:
            s = Particle._surface_cache[cache_key]

        s.set_alpha(max(0, int(self.alpha)))
        surface.blit(s, (self.x - self.size, self.y - self.size))


class Firework:
    def __init__(self, x, y):
        base_colors = [
            (255, 105, 180),
            (255, 215, 0),
            (0, 255, 255),
            (255, 69, 0),
            (147, 112, 219),
            (255, 192, 203)
        ]
        color = random.choice(base_colors)
        self.particles = [
            Particle(x, y, color)
            for _ in range(random.randint(60, 100))
        ]

    def update_and_draw(self, surface):
        self.particles = [p for p in self.particles if p.update()]
        for p in self.particles:
            p.draw(surface)
        return len(self.particles) > 0


# ============================================================
# 5. 玫瑰绘制
# ============================================================
def draw_rose(surface, bloom_stage, time_tick, scale_base=170):
    max_t = min(1.0, bloom_stage * 1.25)
    bloom_scale = 0.28 + 0.72 * bloom_stage

    for p in ROSE_POINTS:
        t = p["t"]
        if t > max_t:
            break

        theta = p["theta"]

        # 外层花瓣更晚展开，形成自然重瓣开放节奏
        radial_bloom = min(1.0, bloom_stage * (1.6 - t * 0.9))

        # 花瓣边缘轻微翻卷
        curl = 1.0
        if t > 0.6:
            curl = 1.0 + 0.18 * math.sin(time_tick * 0.018 + theta * 3) * (t - 0.6)

        r = p["base_r"] * scale_base * bloom_scale * radial_bloom * curl

        # 自然摇曳：外层幅度大，内层幅度小
        sway = math.sin(time_tick * 0.012 + t * 4.5) * 1.8 * t

        x = CENTER[0] + r * math.cos(theta) + sway
        y = CENTER[1] - r * math.sin(theta) - (t * 35 * bloom_stage)

        pygame.draw.circle(
            surface, p["color"],
            (int(x), int(y)),
            int(p["size"])
        )

    # 花蕊：绽放25%后逐渐显现
    if bloom_stage > 0.25:
        stamen_alpha = min(1.0, (bloom_stage - 0.25) / 0.35)
        stamen_count = 14
        stamen_r = 9 * bloom_stage
        yellow = (255, 230, 120)

        for i in range(stamen_count):
            angle = i * (2 * math.pi / stamen_count) + time_tick * 0.006
            sx = CENTER[0] + math.cos(angle) * stamen_r
            sy = CENTER[1] + math.sin(angle) * stamen_r * 0.9
            pygame.draw.circle(surface, yellow, (int(sx), int(sy)), 2)


# ============================================================
# 6. 花茎与叶片
# ============================================================
def draw_stem_and_leaves(surface, bloom_stage):
    if bloom_stage < 0.1:
        return

    alpha_factor = min(1.0, (bloom_stage - 0.1) / 0.45)

    stem_color = (
        int(20 * alpha_factor),
        int(110 * alpha_factor),
        int(20 * alpha_factor)
    )

    points = []
    start_y = CENTER[1] + 20
    stem_length = 280

    for y_off in range(0, stem_length, 4):
        x_off = math.sin(y_off * 0.022) * 13
        points.append((CENTER[0] + x_off, start_y + y_off))

    if len(points) > 1:
        pygame.draw.lines(surface, stem_color, False, points, 5)

    # 两片互生叶片
    if bloom_stage > 0.3:
        leaf_alpha = min(1.0, (bloom_stage - 0.3) / 0.35)
        leaf_color = (
            int(45 * leaf_alpha),
            int(160 * leaf_alpha),
            int(55 * leaf_alpha)
        )

        # 左上叶
        leaf1_y = start_y + 85
        leaf1_x = CENTER[0] - 10
        pygame.draw.ellipse(
            surface, leaf_color,
            pygame.Rect(leaf1_x - 45, leaf1_y - 10, 45, 20),
            0
        )
        pygame.draw.line(
            surface, stem_color,
            (leaf1_x, leaf1_y),
            (leaf1_x - 40, leaf1_y - 5),
            1
        )

        # 右下叶
        leaf2_y = start_y + 170
        leaf2_x = CENTER[0] + 10
        pygame.draw.ellipse(
            surface, leaf_color,
            pygame.Rect(leaf2_x, leaf2_y - 10, 45, 20),
            0
        )
        pygame.draw.line(
            surface, stem_color,
            (leaf2_x, leaf2_y),
            (leaf2_x + 40, leaf2_y + 5),
            1
        )


# ============================================================
# 7. 主程序
# ============================================================
def main():
    bloom_stage = 0.0
    fireworks = []
    time_tick = 0
    running = True

    while running:
        clock.tick(60)
        time_tick += 1

        # 事件处理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # 清屏（纯黑会被Windows抠除为透明）
        screen.fill(TRANSPARENT_COLOR)

        # 玫瑰绽放逻辑
        if bloom_stage < 1.0:
            bloom_stage += 0.0032
        else:
            # 完全绽放后随机生成烟花
            if random.random() < 0.06:
                fx = random.randint(100, WIDTH - 100)
                fy = random.randint(80, HEIGHT // 2 + 100)
                fireworks.append(Firework(fx, fy))

        # 绘制顺序：茎→玫瑰→烟花
        draw_stem_and_leaves(screen, bloom_stage)
        draw_rose(screen, bloom_stage, time_tick)
        fireworks = [fw for fw in fireworks if fw.update_and_draw(screen)]

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()