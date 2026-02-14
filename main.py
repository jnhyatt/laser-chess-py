import asyncio
import pygame
import sys

from client import GamePresenter, LocalClient
from draw import Drawable
from logic import load_board_state
from server import LocalServer


# Workaround for pygame circular import bug. See https://github.com/pygame/pygame/issues/4170 and
# https://github.com/pygame/pygame/pull/4607. The issue is fixed, the maintainers just have to push
# the button. In the meantime, we're going to do this wild patch.
def _patch_pygame_sysfont():
    import sys
    import types

    # Pre-load a stub for pygame.font so sysfont's top-level
    # `from pygame.font import Font` doesn't trigger the real import cycle.
    stub = types.ModuleType("pygame.font")
    stub.Font = None
    sys.modules["pygame.font"] = stub

    # sysfont can now import without a cycle
    import pygame.sysfont

    # Remove the stub so the real font module loads fresh
    del sys.modules["pygame.font"]
    import pygame.font

    # Patch the two references that were bound to the stub's None
    pygame.sysfont.Font = pygame.font.Font

    def _patched_font_constructor(fontpath, size, bold, italic):
        from pygame.font import Font

        font = Font(fontpath, size)
        if bold:
            font.set_bold(True)
        if italic:
            font.set_italic(True)
        return font

    pygame.sysfont.font_constructor = _patched_font_constructor


_patch_pygame_sysfont()


async def main() -> None:
    pygame.init()
    pygame.mixer.init()
    surface = pygame.display.set_mode((1280, 720))

    laser_fire_sound = pygame.mixer.Sound("laserSmall_002.ogg")
    mirror_hit_sound = pygame.mixer.Sound("impactGlass_light_001.ogg")

    red = LocalClient()
    blue = LocalClient()
    server = LocalServer(load_board_state("classic.json"))
    presenter = GamePresenter(local_players={"red", "blue"}, red=red, blue=blue)

    async def start_game() -> None:
        server_task = server.start(red, blue)
        presenter_task = presenter.start(server)
        await asyncio.gather(server_task, presenter_task)

    render_state: list[Drawable] = []

    async def sync_render_state() -> None:
        while True:
            render_state[:] = await presenter.render_state.get()

    asyncio.create_task(start_game())
    asyncio.create_task(sync_render_state())

    while True:
        for event in pygame.event.get():
            presenter.on_event(event)
            if event.type == pygame.constants.QUIT:
                pygame.quit()
                sys.exit()

        surface.fill((28, 72, 28))

        # Drain and play any queued sound effects
        while not presenter.sound_effects.empty():
            effect = presenter.sound_effects.get_nowait()
            match effect:
                case "laser_fire":
                    laser_fire_sound.play()
                case "mirror_hit":
                    mirror_hit_sound.play()

        for y in range(0, 8):
            for x in range(0, 10):
                color = (180, 180, 128) if (x + y) % 2 == 0 else (24, 24, 24)
                pygame.draw.rect(surface, color, (x * 90 + 190, y * 90, 90, 90))

        for drawable in render_state:
            drawable.draw(surface)

        pygame.display.flip()
        await asyncio.sleep(1 / 60)  # yield to event loop


if __name__ == "__main__":
    asyncio.run(main())
