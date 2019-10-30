import json
from typing import Type as Cls, TypeVar, IO, List, Dict, Union
from pathlib import Path

T = TypeVar('T')


def new(cls: Cls[T]) -> T:
    return cls.__new__(cls)


class Config:
    DEFAULT_DATA = {}

    def __init__(self, path: str):
        self.path = Path(path)
        if not self.path.exists():
            self.file: IO = self.path.open("w")
            self.file.write(json.dumps(self.DEFAULT_DATA, indent='    '))
        else:
            self.file = self.path.open("r+")
            try:
                json.loads(self.file.read())
            except json.JSONDecodeError:
                print("Corrupted")
                self.file.seek(0)
                self.file.write(json.dumps(self.DEFAULT_DATA, indent='    '))
        self.file: IO = open(path, "r+")

    def __setitem__(self, key: str, value):
        self.file.seek(0)
        data = json.loads(self.file.read())
        data[key] = value
        self.file.seek(0)
        self.file.write(json.dumps(data, indent='    '))

    def __getitem__(self, item: str):
        self.file.seek(0)
        data = json.loads(self.file.read())
        return data[item]

    def __contains__(self, item: str):
        self.file.seek(0)
        data = json.loads(self.file.read())
        return item in data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return
