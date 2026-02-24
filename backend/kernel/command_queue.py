from collections import deque
from typing import Deque
from backend.kernel.commands import Command

class CommandQueue:
    def __init__(self):
        self.queue: Deque[Command] = deque()

    def add(self, command: Command):
        self.queue.append(command)

    def pop_all(self) -> Deque[Command]:
        commands = self.queue
        self.queue = deque()
        return commands

    def clear(self):
        self.queue.clear()
