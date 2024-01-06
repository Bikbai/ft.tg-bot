import array
import os
import msvcrt as m
import random
import struct


class Apple:
    _color: str
    _is_wormed: bool
    _freshness: int
    _size: int

    def __init__(self):
        self._size = 1
        self._color = 'green'
        self._is_wormed = False
        self._freshness = 0 # незрелое

    def grow(self):
        self._color = 'red'
        self._size += 1
        if self._size > 5 & self._size < 10:
            self._freshness = 1
        if self._size > 10:
            self._freshness = 2

    def get_freshness(self):
        return self._freshness


a = Apple()
b = Apple()

print(a.get_freshness())
print(b.get_freshness())

a.grow()

print(a.get_freshness())
print(b.get_freshness())



