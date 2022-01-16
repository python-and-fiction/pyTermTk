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

import os
import re
import datetime

from TermTk.TTkCore.color import TTkColor

from TermTk.TTkCore.constant import TTkK
from TermTk.TTkCore.log import TTkLog
from TermTk.TTkCore.cfg import TTkCfg
from TermTk.TTkCore.signal import pyTTkSlot, pyTTkSignal
from TermTk.TTkCore.string import TTkString
from TermTk.TTkWidgets.lineedit import TTkLineEdit
from TermTk.TTkWidgets.window import TTkWindow
from TermTk.TTkWidgets.splitter import TTkSplitter
from TermTk.TTkWidgets.combobox import TTkComboBox
from TermTk.TTkWidgets.button import TTkButton
from TermTk.TTkWidgets.label import TTkLabel
from TermTk.TTkWidgets.list_ import TTkList
from TermTk.TTkLayouts.gridlayout import TTkGridLayout
from TermTk.TTkWidgets.TTkModelView.filetree import TTkFileTree
from TermTk.TTkWidgets.TTkModelView.filetreewidgetitem import TTkFileTreeWidgetItem


'''
::

    +----------------------------------------+
    |  Look in: [--FULL-PATH-|v] [<] [>] [^] |
    | +-----------+------------------------+ |
    | | Bookmarks ║     File Tree          | |
    | |           ║                        | |
    | +-----------+------------------------+ |
    | File name:     [-----------]  [Open  ] |
    | Files of Type  [-----------]  [Cancel] |
    +--------------+-------------------------+
'''

class TTkFileDialogPicker(TTkWindow):
    __slots__ = ('_path', '_recentPath', '_recentPathId', '_filters', '_filter', '_caption',
                 # Widgets
                 '_fileTree', '_lookPath', '_btnPrev', '_btnNext', '_btnUp',
                 '_fileName', '_fileType', '_btnOpen', '_btnCancel',
                 # Signals
                 'filePicked')

    def __init__(self, *args, **kwargs):
        # Signals
        self.filePicked = pyTTkSignal(str)

        TTkWindow.__init__(self, *args, **kwargs)
        self._name = kwargs.get('name' , 'TTkFileDialogPicker' )

        self._recentPathId = -1
        self._recentPath = []

        self._path    = kwargs.get('path','.')
        self._filter  = '*'
        self._filters = kwargs.get('filter','All Files (*)')
        self._caption = kwargs.get('caption','File Dialog')

        self.setTitle(self._caption)
        self.setLayout(TTkGridLayout())

        # Top (absPath)
        topLayout = TTkGridLayout()
        self.layout().addItem(topLayout,0,0)

        self._lookPath = TTkComboBox(textAlign=TTkK.LEFT_ALIGN)
        self._btnPrev  = TTkButton(text="<",maxWidth=3, enabled=False)
        self._btnNext  = TTkButton(text=">",maxWidth=3, enabled=False)
        self._btnUp    = TTkButton(text="^",maxWidth=3, enabled=True)
        self._btnPrev.clicked.connect(self._openPrev)
        self._btnNext.clicked.connect(self._openNext)
        self._btnUp.clicked.connect(  self._openUp)

        topLayout.addWidget(TTkLabel(text="Look in:",maxWidth=14),      0,0)
        topLayout.addWidget(self._lookPath , 0,1)
        topLayout.addWidget(self._btnPrev  , 0,2)
        topLayout.addWidget(self._btnNext  , 0,3)
        topLayout.addWidget(self._btnUp    , 0,4)

        # Bottom (File Name, Controls)
        self._fileName  = TTkLineEdit()
        self._fileType  = TTkComboBox(textAlign=TTkK.LEFT_ALIGN)
        self._btnOpen   = TTkButton(text="Open",  maxWidth=8, enabled=False)
        self._btnCancel = TTkButton(text="Cancel",maxWidth=8)

        for f in self._filters.split(';;'):
            if m := re.match(".*\(.*\)",f):
                self._fileType.addItem(f)
        self._fileType.setCurrentIndex(0)
        self._fileType.currentTextChanged.connect(self._fileTypeChanged)

        self._btnOpen.clicked.connect(self._open)
        self._btnCancel.clicked.connect(self.close)

        self._fileName.returnPressed.connect(self._open)
        self._fileName.textChanged.connect(self._checkFileName)
        self._fileName.textEdited.connect(self._checkFileName)


        bottomLayout = TTkGridLayout()
        self.layout().addItem(bottomLayout,2,0)
        bottomLayout.addWidget(TTkLabel(text="File name:"     ,maxWidth=14),      0,0)
        bottomLayout.addWidget(TTkLabel(text="Files of type:" ,maxWidth=14),      1,0)
        bottomLayout.addWidget(self._fileName  , 0,1)
        bottomLayout.addWidget(self._fileType  , 1,1)
        bottomLayout.addWidget(self._btnOpen   , 0,2)
        bottomLayout.addWidget(self._btnCancel , 1,2)

        # Center (self._fileTree, Bookmarks)
        splitter = TTkSplitter(border=True)
        self.layout().addWidget(splitter,1,0)

        bookmarks = TTkList(parent=splitter)
        bookmarks.addItem(TTkString() + TTkCfg.theme.fileIconColor + TTkCfg.theme.fileIcon.computer + TTkColor.RST+" Computer", data='/')
        bookmarks.addItem(TTkString() + TTkCfg.theme.fileIconColor + TTkCfg.theme.fileIcon.home     + TTkColor.RST+" Home", data=os.path.expanduser("~"))
        def _bookmarksCallback(item):
            self._openNewPath(item.data)
        bookmarks.itemClicked.connect(_bookmarksCallback)

        # Home Folder (Win Compatible):
        #   os.path.expanduser("~")

        self._fileTree = TTkFileTree(parent=splitter)
        splitter.setSizes([10,self.width()-13])
        self._fileTree.setHeaderLabels(["Name", "Size", "Type", "Date Modified"])
        self._fileTree.itemExpanded.connect(self._updateChildren)
        self._fileTree.itemExpanded.connect(TTkFileDialogPicker._folderExpanded)
        self._fileTree.itemCollapsed.connect(TTkFileDialogPicker._folderCollapsed)

        self._fileTree.itemClicked.connect(self._selectedItem)
        self._fileTree.itemActivated.connect(self._activatedItem)

        self._lookPath.currentTextChanged.connect(self._openNewPath)
        self._openNewPath(self._path, True)

    @pyTTkSlot(str)
    def _fileTypeChanged(self, type):
        self._filter = re.match(".*\((.*)\)",type).group(1)
        self._fileTree.setFilter(self._filter)

    @pyTTkSlot(str)
    def _checkFileName(self, fileName):
        if os.path.exists(fileName) and os.path.isfile(fileName):
            self._btnOpen.setEnabled()
        else:
            self._btnOpen.setDisabled()

    @pyTTkSlot()
    def _open(self):
        fileName = self._fileName.text()
        if not os.path.exists(fileName): return
        self.filePicked.emit(fileName)
        self.close()

    @pyTTkSlot(TTkFileTreeWidgetItem, int)
    def _selectedItem(self, item, _):
        if item.getType() != item.FILE: return
        self._fileName.setText(item.path())

    @pyTTkSlot(TTkFileTreeWidgetItem, int)
    def _activatedItem(self, item, _):
        path = item.path()
        if os.path.isdir(path):
             self._openNewPath(path, True)
        elif os.path.isfile(path):
            self._open()

    def _openPrev(self):
        if self._recentPathId<=0 or self._recentPathId>=len(self._recentPath):
            self._btnPrev.setDisabled()
            return
        self._recentPathId -= 1
        self._openNewPath(self._recentPath[self._recentPathId],False)
        if self._recentPathId<=0:
            self._btnPrev.setDisabled()
        self._btnNext.setEnabled()

    def _openNext(self):
        if self._recentPathId<0 or self._recentPathId>=len(self._recentPath)-1:
            self._btnNext.setDisabled()
            return
        self._recentPathId += 1
        self._openNewPath(self._recentPath[self._recentPathId],False)
        if self._recentPathId>=len(self._recentPath)-1:
            self._btnNext.setDisabled()
        self._btnPrev.setEnabled()

    def _openUp(self):
        path = os.path.abspath(self._recentPath[self._recentPathId])
        path, e = os.path.split(path)
        if e:
            self._openNewPath(path, True)

    def _openNewPath(self, path, addToRecent=True):
        self._path = path
        if addToRecent:
            self._recentPathId = len(self._recentPath)
            self._recentPath.append(path)
            if self._recentPathId:
                self._btnPrev.setEnabled()
            self._btnNext.setDisabled()
        self._fileTree.openPath(path)
        self._lookPath.currentTextChanged.disconnect(self._openNewPath)
        self._lookPath.clear()
        self._lookPath.addItems(TTkFileDialogPicker._getListLook(self._path))
        self._lookPath.setCurrentIndex(0)
        self._lookPath.currentTextChanged.connect(self._openNewPath)

    @staticmethod
    def _getListLook(path):
        path = os.path.abspath(path)
        ret = [path]
        while True:
            path, e = os.path.split(path)
            if e:
                ret.append(path)
            if not path or path=='/':
                break
        return ret

    @staticmethod
    def _getFileItems(path):
        path = os.path.abspath(path)
        if not os.path.exists(path): return []
        dir_list = os.listdir(path)
        ret = []
        for n in dir_list:
            nodePath = os.path.join(path,n)

            def _getStat(_path):
                info = os.stat(_path)
                time = datetime.datetime.fromtimestamp(info.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
                if info.st_size > (1024*1024*1024):
                    size = f"{info.st_size/(1024*1024*1024):.2f} GB"
                if info.st_size > (1024*1024):
                    size = f"{info.st_size/(1024*1024):.2f} MB"
                elif info.st_size > 1024:
                    size = f"{info.st_size/1024:.2f} KB"
                else:
                    size = f"{info.st_size} bytes"
                return time, size, info.st_ctime, info.st_size

            if os.path.isdir(nodePath):
                if os.path.exists(nodePath):
                    time, _, rawTime, _ = _getStat(nodePath)
                    color = TTkCfg.theme.folderNameColor
                else:
                    time, _, rawTime, _ = ""
                    color = TTkCfg.theme.failNameColor

                if os.path.islink(nodePath):
                    name = TTkString()+TTkCfg.theme.linkNameColor+n+'/'+TTkColor.RST+' -> '+TTkCfg.theme.folderNameColor+os.readlink(nodePath)
                    typef = "Folder Link"
                else:
                    name = TTkString()+color+n+'/'
                    typef = "Folder"

                ret.append(TTkFileTreeWidgetItem(
                                [ name, "", typef, time],
                                raw = [ n , -1 , typef , rawTime ],
                                path=nodePath,
                                type=TTkFileTreeWidgetItem.DIR,
                                icon=TTkString() + TTkCfg.theme.folderIconColor + TTkCfg.theme.fileIcon.folderClose + TTkColor.RST,
                                childIndicatorPolicy=TTkK.ShowIndicator))

            elif os.path.isfile(nodePath) or os.path.islink(nodePath):
                if os.path.exists(nodePath):
                    time, size, rawTime, rawSize = _getStat(nodePath)
                    if os.access(nodePath, os.X_OK):
                        color = TTkCfg.theme.executableColor
                        typef="Exec"
                    else:
                        color = TTkCfg.theme.fileNameColor
                        typef="File"
                else:
                    time, size, rawTime, rawSize = "", "", 0, 0
                    color = TTkCfg.theme.failNameColor
                    typef="Broken"

                if os.path.islink(nodePath):
                    name = TTkString()+TTkCfg.theme.linkNameColor+n+TTkColor.RST+' -> '+color+os.readlink(nodePath)
                    typef += " Link"
                else:
                    name = TTkString()+color+n

                _, ext = os.path.splitext(n)
                if ext: ext = f"{ext[1:]} "
                ret.append(TTkFileTreeWidgetItem(
                                [ name, size, typef, time],
                                raw = [ n , rawSize , typef , rawTime ],
                                path=nodePath,
                                type=TTkFileTreeWidgetItem.FILE,
                                icon=TTkString() + TTkCfg.theme.fileIconColor + TTkCfg.theme.fileIcon.getIcon(n) + TTkColor.RST,
                                childIndicatorPolicy=TTkK.DontShowIndicator))
        return ret

    @staticmethod
    def _folderExpanded(item):
        item.setIcon(0, TTkString() + TTkCfg.theme.folderIconColor + TTkCfg.theme.fileIcon.folderOpen + TTkColor.RST,)

    @staticmethod
    def _folderCollapsed(item):
        item.setIcon(0, TTkString() + TTkCfg.theme.folderIconColor + TTkCfg.theme.fileIcon.folderClose + TTkColor.RST,)

    def _updateChildren(self, item):
        if item.children(): return
        for i in TTkFileDialogPicker._getFileItems(item.path()):
            item.addChild(i)
            # TODO: Find a better way than calling an internal function
            i._processFilter(self._filter)


'''
for (dirpath, dirnames, filenames) in walk('/tmp'):
    print(f"{dirpath} {dirnames} {filenames}")
    break
'''

class TTkFileDialog:
    def getOpenFileName(caption, dir=".", filter="All Files (*)", options=None):
        pass