"""Window events must be serviced while content loading is still pending."""
import os
import threading

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
import pytest

from chess_game.startup import StartupCancelled, run_startup_task


def test_loading_handles_resize_and_quit_before_the_task_finishes():
    pygame.init()
    pygame.display.set_mode((360, 320))
    pygame.event.clear()
    release = threading.Event()
    started = threading.Event()
    finished = threading.Event()
    seen = []

    def load():
        started.set()
        try:
            assert release.wait(2)
            return 'loaded'
        finally:
            finished.set()

    def redraw():
        pygame.event.post(pygame.event.Event(pygame.VIDEORESIZE, w=420, h=720))
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def handle(event):
        assert started.wait(1)
        assert not finished.is_set()
        seen.append(event.type)
        return event.type != pygame.QUIT

    try:
        with pytest.raises(StartupCancelled):
            run_startup_task(load, handle, redraw, pygame.time.Clock())
        assert seen == [pygame.VIDEORESIZE, pygame.QUIT]
    finally:
        release.set()
        assert finished.wait(1)
        pygame.quit()


def test_loading_delivers_the_value_and_propagates_errors():
    pygame.init()
    pygame.display.set_mode((360, 320))
    try:
        main_thread = threading.get_ident()
        worker_threads = []
        def load():
            worker_threads.append(threading.get_ident())
            return 'library'
        def redraw():
            assert threading.get_ident() == main_thread
        assert run_startup_task(load, lambda event: True, redraw,
                                pygame.time.Clock()) == 'library'
        assert worker_threads[0] != main_thread
        def fail():
            raise ValueError('content failed')
        with pytest.raises(ValueError, match='content failed'):
            run_startup_task(fail, lambda event: True, redraw, pygame.time.Clock())
    finally:
        pygame.quit()
