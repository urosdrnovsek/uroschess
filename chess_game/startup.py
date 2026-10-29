"""Run content preparation while the main thread services window events."""

import queue
import threading

import pygame


class StartupCancelled(Exception):
    """The player closed the window while content was being prepared."""


def run_startup_task(task, handle_event, redraw, clock):
    """Run a non-GUI task, keeping all SDL event handling on the caller thread."""
    results = queue.Queue()

    def work():
        try:
            results.put((task(), None))
        except Exception as error:
            results.put((None, error))

    redraw()
    threading.Thread(target=work, daemon=True).start()
    while True:
        for event in pygame.event.get():
            if handle_event(event) is False:
                raise StartupCancelled
        try:
            result, error = results.get_nowait()
        except queue.Empty:
            redraw()
            clock.tick(30)
            continue
        if error is not None:
            raise error
        return result
