#!/usr/bin/env python3

# MIT License
#
# Copyright (c) 2021 Eugenio Parodi <ceccopierangiolieugenio AT googlemail DOT com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from TermTk.TTkCore.cfg import *
from TermTk.TTkCore.helper import TTkHelper
from TermTk.TTkCore.color import TTkColor
from TermTk.TTkCore.log import TTkLog
from TermTk.TTkCore.signal import pyTTkSignal, pyTTkSlot
from TermTk.TTkCore.string import TTkString
from TermTk.TTkWidgets.button import TTkButton
from TermTk.TTkWidgets.listwidget import TTkListWidget, TTkAbstractListItem
from TermTk.TTkLayouts.layout import TTkLayout
from TermTk.TTkLayouts.boxlayout import TTkHBoxLayout
from TermTk.TTkWidgets.menu import TTkMenu, TTkMenuButton, _TTkMenuSpacer

class TTkMenuBarButton(TTkMenuButton):
    classStyle = TTkMenuButton.classStyle | {
                'default': TTkMenuButton.classStyle['default'] | {'borderColor':TTkColor.RST, 'shortcutColor': TTkColor.fg("#dddddd") + TTkColor.UNDERLINE},
                'clicked': TTkMenuButton.classStyle['clicked'] | {'color': TTkColor.fg("#ffff88")},
            }

    __slots__=('_shortcut')
    def __init__(self, *, text=..., data=None, checkable=False, checked=False, **kwargs):
        self._shortcut = []
        super().__init__(text=text, data=data, checkable=checkable, checked=checked, **kwargs)
        while self.text().find('&') != -1:
            index = self.text().find('&')
            shortcut = self.text().charAt(index+1)
            TTkHelper.addShortcut(self, shortcut)
            self._shortcut.append(index)
            self.setText(self.text().substring(to=index)+self.text().substring(fr=index+1))
        txtlen = self.text().termWidth()
        self.resize(txtlen+2,1)
        self.setMinimumSize(txtlen+2,1)
        self.setMaximumSize(txtlen+2,1)

    def setBorderColor(self, color):
        style = self.style()
        style['default'] |= {'borderColor':color}
        self.setStyle(style)

    def paintEvent(self, canvas):
        style = self.currentStyle()
        borderColor = style['borderColor']
        textColor   = style['color']
        scColor     = style['shortcutColor']
        canvas.drawMenuBarButton(
                        pos=(0,0),text=self.text(),
                        width=self.width(),
                        shortcuts=self._shortcut,
                        border=True,
                        submenu=len(self._submenu)>0,
                        color=textColor,
                        borderColor=borderColor,
                        shortcutColor=scColor )

class TTkMenuBarLayout(TTkHBoxLayout):
    '''TTkMenuBarLayout'''
    __slots__ = ('_borderColor', '_itemsLeft', '_itemsCenter', '_itemsRight', '_buttons')
    def __init__(self, *args, **kwargs):
        self._buttons = []
        TTkHBoxLayout.__init__(self, *args, **kwargs)
        self._borderColor = kwargs.get('borderColor', TTkCfg.theme.frameBorderColor )
        self._itemsLeft   = TTkHBoxLayout()
        self._itemsCenter = TTkHBoxLayout()
        self._itemsRight  = TTkHBoxLayout()
        self.addItem(self._itemsLeft)
        self.addItem(TTkLayout())
        self.addItem(self._itemsCenter)
        self.addItem(TTkLayout())
        self.addItem(self._itemsRight)

    def setBorderColor(self, color):
        self._borderColor = color
        for b in self._buttons:
            b.setBorderColor(color)
        self.update()

    def addMenu(self, text, alignment=TTkK.LEFT_ALIGN):
        '''addMenu'''
        button = TTkMenuBarButton(text=text, borderColor=self._borderColor, border=True)
        # button = TTkMenuButton(text=text, borderColor=self._borderColor, border=True)
        self._mbItems(alignment).addWidget(button)
        self._buttons.append(button)
        self.update()
        return button

    def _menus(self, alignment=TTkK.LEFT_ALIGN):
        return [w.widget() for w in self._mbItems(alignment).children()]

    def _mbItems(self, alignment=TTkK.LEFT_ALIGN):
        return {
            TTkK.LEFT_ALIGN:   self._itemsLeft   ,
            TTkK.CENTER_ALIGN: self._itemsCenter ,
            TTkK.RIGHT_ALIGN:  self._itemsRight
        }.get(alignment, self._itemsLeft)

    def clear(self):
        self._buttons = []
        self._itemsLeft.removeItems(self._itemsLeft.children())
        self._itemsCenter.removeItems(self._itemsCenter.children())
        self._itemsRight.removeItems(self._itemsRight.children())
