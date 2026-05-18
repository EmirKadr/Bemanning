"""Minimal Tkinter fallback for server-side warehouse runtime imports.

The legacy runtime still contains GUI classes.  Render does not provide the
native `_tkinter` extension, but the API only uses pure calculation functions.
These dummies let class definitions import while keeping GUI construction a
clear runtime error if someone tries to use it on the server.
"""
from __future__ import annotations

from types import SimpleNamespace


class _HeadlessTkError(RuntimeError):
    pass


class _DummyVar:
    def __init__(self, *args, value=None, **kwargs):
        self._value = value

    def get(self):
        return self._value

    def set(self, value) -> None:
        self._value = value


class _DummyWidget:
    def __init__(self, *args, **kwargs):
        self.master = args[0] if args else None

    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            return None

        return _noop

    def __setitem__(self, key, value) -> None:
        return None

    def __getitem__(self, key):
        return None

    def configure(self, *args, **kwargs):
        return None

    config = configure


class _DummyTk(_DummyWidget):
    def mainloop(self, *args, **kwargs):
        raise _HeadlessTkError("Tkinter GUI kan inte startas i headless servermiljo.")


class _DummyStyle(_DummyWidget):
    pass


class _DummyMessageBox:
    @staticmethod
    def askyesno(*args, **kwargs) -> bool:
        return False

    @staticmethod
    def showinfo(*args, **kwargs) -> None:
        return None

    showwarning = showinfo
    showerror = showinfo


class _DummyFileDialog:
    @staticmethod
    def askopenfilename(*args, **kwargs) -> str:
        return ""

    @staticmethod
    def askopenfilenames(*args, **kwargs) -> tuple:
        return ()

    @staticmethod
    def asksaveasfilename(*args, **kwargs) -> str:
        return ""


tk = SimpleNamespace(
    Tk=_DummyTk,
    Toplevel=_DummyWidget,
    Canvas=_DummyWidget,
    Text=_DummyWidget,
    Widget=_DummyWidget,
    Label=_DummyWidget,
    Button=_DummyWidget,
    Menu=_DummyWidget,
    StringVar=_DummyVar,
    BooleanVar=_DummyVar,
    IntVar=_DummyVar,
    END="end",
    BOTH="both",
    LEFT="left",
    RIGHT="right",
    TOP="top",
    BOTTOM="bottom",
    X="x",
    Y="y",
    VERTICAL="vertical",
    HORIZONTAL="horizontal",
    DISABLED="disabled",
    NORMAL="normal",
)

ttk = SimpleNamespace(
    Style=_DummyStyle,
    Frame=_DummyWidget,
    LabelFrame=_DummyWidget,
    Label=_DummyWidget,
    Button=_DummyWidget,
    Entry=_DummyWidget,
    Checkbutton=_DummyWidget,
    Combobox=_DummyWidget,
    Progressbar=_DummyWidget,
    Panedwindow=_DummyWidget,
    Treeview=_DummyWidget,
    Scrollbar=_DummyWidget,
)

filedialog = _DummyFileDialog()
messagebox = _DummyMessageBox()
scrolledtext = SimpleNamespace(ScrolledText=_DummyWidget)

