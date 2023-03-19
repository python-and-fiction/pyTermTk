# MIT License
#
# Copyright (c) 2023 Eugenio Parodi <ceccopierangiolieugenio AT googlemail DOT com>
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

from TermTk.TTkCore.string import TTkString
from TermTk.TTkLayouts.layout import TTkLayout
from TermTk.TTkWidgets.widget import TTkWidget

TTkWidgetProperties = {
    'properties' : {
        # 'X' : {
        #         'init': {'name':'x', 'type':int } ,
        #         'get':  { 'cb':x,    'type':int } },
        # 'Y' : {
        #         'init': {'name':'y', 'type':int } ,
        #         'get':  { 'cb':y,    'type':int } },
        'Position' : {
                'init': {'name':'pos', 'type': [
                                { 'name': 'x', 'type':int } ,
                                { 'name': 'y', 'type':int } ] },
                'get':  { 'cb':TTkWidget.pos,    'type': [
                                { 'name': 'x', 'type':int } ,
                                { 'name': 'y', 'type':int } ] },
                'set':  { 'cb':TTkWidget.move,   'type': [
                                { 'name': 'x', 'type':int } ,
                                { 'name': 'y', 'type':int } ] } },
        'Size' : {
                'init': {'name':'size', 'type': [
                                { 'name': 'width', 'type':int  } ,
                                { 'name': 'height', 'type':int } ] },
                'get':  { 'cb':TTkWidget.size,    'type': [
                                { 'name': 'width', 'type':int  } ,
                                { 'name': 'height', 'type':int } ] },
                'set':  { 'cb':TTkWidget.resize,   'type': [
                                { 'name': 'width', 'type':int  } ,
                                { 'name': 'height', 'type':int } ] } },
        # 'Width' : {
        #         'init': {'name':'width', 'type':int } ,
        #         'get':  { 'cb':width,    'type':int } },
        # 'Height' : {
        #         'init': {'name':'height', 'type':int } ,
        #         'get':  { 'cb':height,    'type':int } },
        'Min Width' : {
                'init': {'name':'minWidth',    'type':int } ,
                'get':  { 'cb':TTkWidget.minimumWidth,   'type':int } ,
                'set':  { 'cb':TTkWidget.setMinimumWidth,'type':int } },
        'Min Height' : {
                'init': {'name':'minHeight',    'type':int } ,
                'get':  { 'cb':TTkWidget.minimumHeight,   'type':int } ,
                'set':  { 'cb':TTkWidget.setMinimumHeight,'type':int } },
        'Max Width' : {
                'init': {'name':'maxWidth',    'type':int } ,
                'get':  { 'cb':TTkWidget.maximumWidth,   'type':int } ,
                'set':  { 'cb':TTkWidget.setMaximumWidth,'type':int } },
        'Max Height' : {
                'init': {'name':'maxHeight',    'type':int } ,
                'get':  { 'cb':TTkWidget.maximumHeight,   'type':int } ,
                'set':  { 'cb':TTkWidget.setMaximumHeight,'type':int } },
        'Padding': {
                'get':  { 'cb':TTkWidget.getPadding,    'type': [
                                { 'name': 'top',    'type':int  } ,
                                { 'name': 'bottom', 'type':int  } ,
                                { 'name': 'left',   'type':int  } ,
                                { 'name': 'right',  'type':int } ] },
                'set':  { 'cb':TTkWidget.setPadding,   'type': [
                                { 'name': 'top',    'type':int  } ,
                                { 'name': 'bottom', 'type':int  } ,
                                { 'name': 'left',   'type':int  } ,
                                { 'name': 'right',  'type':int } ] } },
        'Layout' : {
                'init': {'name':'layout', 'type':TTkLayout} ,
                'get':  { 'cb':TTkWidget.layout,    'type':TTkLayout} ,
                'set':  { 'cb':TTkWidget.setLayout, 'type':TTkLayout} },
        'Name' : {
                'init': {'name':'name', 'type':str } ,
                'get':  { 'cb':TTkWidget.name,       'type':str} },
        'Visible' : {
                'init': {'name':'visible', 'type':bool } ,
                'get':  { 'cb':TTkWidget.isVisible,   'type':bool } ,
                'set':  { 'cb':TTkWidget.setVisible,  'type':bool } },
        'Enabled' : {
                'init': {'name':'enabled', 'type':bool } ,
                'get':  { 'cb':TTkWidget.isEnabled,   'type':bool } ,
                'set':  { 'cb':TTkWidget.setEnabled,  'type':bool } },
        'ToolTip' : {
                'init': {'name':'toolTip', 'type':TTkString } ,
                'get':  { 'cb':TTkWidget.toolTip,    'type':TTkString } ,
                'set':  { 'cb':TTkWidget.setToolTip, 'type':TTkString } },
    },'signals' : {
        'focusChanged(bool)'   : {'name' : 'focusChanged', 'type':bool},
        'sizeChanged(int,int)' : {'name' : 'sizeChanged',  'type':(int, int)}
    },'slots' : {
        'show()' :           {'cb': TTkWidget.show,       'type':None},
        'hide()' :           {'cb': TTkWidget.hide,       'type':None},
        'close()' :          {'cb': TTkWidget.close,      'type':None},
        'setFocus()' :       {'cb': TTkWidget.setFocus,   'type':None},
        'setVisible(bool)' : {'cb': TTkWidget.setVisible, 'type':bool},
        'setEnabled(bool)':  {'cb': TTkWidget.setEnabled, 'type':bool},
        'setDisabled(bool)': {'cb': TTkWidget.setDisabled,'type':bool},
        'raiseWidget()' :    {'cb': TTkWidget.raiseWidget,'type':None},
        'lowerWidget()' :    {'cb': TTkWidget.lowerWidget,'type':None},
    }
}
