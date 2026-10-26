"""Portable text renderers for Python installations without Rich."""

import re
import shutil
import sys
import textwrap


def plain(value):
    return re.sub(r"\[/?(?:bold|dim|italic|green|red|yellow|cyan|white|blue|bright_red)[^\]]*\]", "", str(value))


class Console:
    def __init__(self, **kwargs):
        self.file = kwargs.get("file")

    @property
    def width(self):
        return shutil.get_terminal_size((80, 24)).columns

    def print(self, *values, **kwargs):
        stream = self.file or sys.stdout
        content = " ".join(plain(v) for v in values)
        content = "\n".join(textwrap.fill(line, max(10, self.width),
                            replace_whitespace=False) if line else ""
                            for line in content.split("\n"))
        encoding = getattr(stream, "encoding", None) or "utf-8"
        content = content.encode(encoding, errors="replace").decode(encoding)
        print(content, file=stream, end=kwargs.get("end", "\n"))


class Text:
    def __init__(self, text="", **kwargs):
        self.text = str(text)

    def append(self, text, **kwargs):
        self.text += str(text)

    def __str__(self):
        return self.text


class Panel:
    def __init__(self, content, title=None, **kwargs):
        self.content, self.title = content, title

    def __str__(self):
        return (plain(self.title) + "\n" if self.title else "") + str(self.content)


class Table:
    def __init__(self, title=None, **kwargs):
        self.title, self.headers, self.rows = title, [], []

    @classmethod
    def grid(cls, **kwargs):
        return cls(**kwargs)

    def add_column(self, header="", **kwargs):
        self.headers.append(header)

    def add_row(self, *values):
        self.rows.append(values)

    def __str__(self):
        lines = [str(self.title)] if self.title else []
        for row in self.rows:
            if any(self.headers):
                lines.extend(f"{key}: {value}" for key, value in zip(self.headers, row))
                lines.append("")
            else:
                lines.append(" ".join(map(str, row)))
        return "\n".join(lines)


class Columns:
    def __init__(self, values, **kwargs):
        self.values = values

    def __str__(self):
        return "\n\n".join(map(str, self.values))


class Padding:
    def __init__(self, content, *args, **kwargs):
        self.content = content

    def __str__(self):
        return str(self.content)


Constrain = Padding


class box:
    ROUNDED = None
