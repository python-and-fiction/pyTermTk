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

__all__ = ['TTkTerminalView']

import os, pty, threading
import struct, fcntl, termios

from dataclasses import dataclass

import re
from select import select
from TermTk.TTkCore.canvas import TTkCanvas
from TermTk.TTkCore.color import TTkColor
from TermTk.TTkCore.log import TTkLog
from TermTk.TTkCore.constant import TTkK
from TermTk.TTkCore.cfg import TTkCfg
from TermTk.TTkCore.string import TTkString
from TermTk.TTkCore.signal import pyTTkSignal, pyTTkSlot
from TermTk.TTkCore.helper import TTkHelper
from TermTk.TTkGui.clipboard import TTkClipboard
from TermTk.TTkGui.textwrap1 import TTkTextWrap
from TermTk.TTkGui.textcursor import TTkTextCursor
from TermTk.TTkGui.textdocument import TTkTextDocument
from TermTk.TTkLayouts.gridlayout import TTkGridLayout
from TermTk.TTkAbstract.abstractscrollarea import TTkAbstractScrollArea
from TermTk.TTkAbstract.abstractscrollview import TTkAbstractScrollView, TTkAbstractScrollViewGridLayout
from TermTk.TTkWidgets.widget import TTkWidget

from TermTk.TTkWidgets.TTkTerminal.terminal_screen  import _TTkTerminalScreen
from TermTk.TTkWidgets.TTkTerminal.mode             import TTkTerminalModes

from TermTk.TTkWidgets.TTkTerminal.vt102 import TTkVT102

from TermTk.TTkCore.TTkTerm.colors import TTkTermColor
from TermTk.TTkCore.TTkTerm.colors_ansi_map import ansiMap16, ansiMap256

from .terminalview_CSI_DEC import _TTkTerminal_CSI_DEC

class _termLog():
    # debug = TTkLog.debug
    # info  = TTkLog.info
    error = TTkLog.error
    warn  = TTkLog.warn
    fatal = TTkLog.fatal
    # mouse = TTkLog.error

    debug = lambda _:None
    info  = lambda _:None
    # error = lambda _:None
    # warn  = lambda _:None
    # fatal = lambda _:None
    mouse = lambda _:None

class TTkTerminalView(TTkAbstractScrollView, _TTkTerminal_CSI_DEC):
    @dataclass
    class _Terminal():
        bracketedMode: bool = False
        DCSstring: str = ""
        IRM: bool = False

    @dataclass
    class _Keyboard():
        flags: int = 0

    @dataclass
    class _Mouse():
        reportPress: bool = False
        reportDrag:  bool = False
        reportMove:  bool = False
        sgrMode:     bool = False

    __slots__ = ('_shell', '_fd', '_inout', '_proc',
                 '_quit_pipe', '_resize_pipe',
                 '_mode_normal'
                 '_clipboard',
                 '_buffer_lines', '_buffer_screen',
                 '_keyboard', '_mouse', '_terminal',
                 '_screen_current', '_screen_normal', '_screen_alt',
                 # Signals
                 'titleChanged', 'bell')
    def __init__(self, *args, **kwargs):
        self.bell = pyTTkSignal()
        self.titleChanged = pyTTkSignal(str)

        self._shell = os.environ.get('SHELL', 'sh')
        self._fd = None
        self._proc = None
        self._mode_normal = True
        self._quit_pipe = None
        self._resize_pipe = None
        self._terminal = TTkTerminalView._Terminal()
        self._keyboard = TTkTerminalView._Keyboard()
        self._mouse = TTkTerminalView._Mouse()
        self._buffer_lines = [TTkString()]
        # self._screen_normal  = _TTkTerminalNormalScreen()
        self._screen_normal  = _TTkTerminalScreen()
        self._screen_alt     = _TTkTerminalScreen()
        self._screen_current = self._screen_normal
        self._clipboard = TTkClipboard()

        # self._screen_normal.bell.connect(lambda : _termLog.debug("BELL!!! 🔔🔔🔔"))
        # self._screen_alt.bell.connect(   lambda : _termLog.debug("BELL!!! 🔔🔔🔔"))
        self._screen_normal.bell.connect(self.bell.emit)
        self._screen_alt.bell.connect(   self.bell.emit)

        super().__init__(*args, **kwargs)

        # self._screen_alt._CSI_MAP     |= self._CSI_MAP
        # self._screen_current._CSI_MAP |= self._CSI_MAP

        w,h = self.size()
        self._screen_alt.resize(w,h)
        self._screen_normal.resize(w,h)

        self.setFocusPolicy(TTkK.ClickFocus + TTkK.TabFocus)
        self.enableWidgetCursor()
        TTkHelper.quitEvent.connect(self._quit)
        self.viewChanged.connect(self._viewChangedHandler)
        self._screen_normal.bufferedLinesChanged.connect(self._screenChanged)
        self._screen_alt.bufferedLinesChanged.connect(self._screenChanged)

    @pyTTkSlot()
    def _screenChanged(self):
        self.viewMoveTo(0, len(self._screen_current._bufferedLines))
        self.viewChanged.emit()

    @pyTTkSlot()
    def _viewChangedHandler(self):
        self.update()

    def viewFullAreaSize(self) -> (int, int):
        w,h = self.size()
        h += len(self._screen_current._bufferedLines)
        return w,h

    def viewDisplayedSize(self) -> (int, int):
        return self.size()

    def _resizeScreen(self):
        w,h = self.size()
        self._screen_current.resize(w,h)
        if self._fd:
            # s = struct.pack('HHHH', 0, 0, 0, 0)
            # t = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, s)
            # print(struct.unpack('HHHH', t))
            s = struct.pack('HHHH', h, w, 0, 0)
            t = fcntl.ioctl(self._fd, termios.TIOCSWINSZ, s)
            # termios.tcsetwinsize(self._fd,(h,w))

    def resizeEvent(self, w: int, h: int):

        if self._resize_pipe:
            os.write(self._resize_pipe[1], b'resize')

        # self._screen_alt.resize(w,h)
        # self._screen_normal.resize(w,h)

        _termLog.info(f"Resize Terminal: {w=} {h=}")
        return super().resizeEvent(w, h)

    def runShell(self, program=None):
        self._shell = program if program else self._shell

        pid, self._fd = pty.fork()

        if pid == 0:
            def _spawnTerminal(argv=[self._shell], env=os.environ):
                os.execvpe(argv[0], argv, env)
            threading.Thread(target=_spawnTerminal).start()
            TTkHelper.quit()
            import sys
            sys.exit()
            # os.execvpe(argv[0], argv, env)
            # os.execvpe(argv[0], argv, env)
            # self._proc = subprocess.Popen(self._shell)
            # _termLog.debug(f"Terminal PID={self._proc.pid=}")
            # self._proc.wait()
        else:
            self._inout = os.fdopen(self._fd, "w+b", 0)
            name = os.ttyname(self._fd)
            _termLog.debug(f"{pid=} {self._fd=} {name}")

            self._quit_pipe = os.pipe()
            self._resize_pipe = os.pipe()

            threading.Thread(target=self.loop,args=[self]).start()
            w,h = self.size()
            self.resizeEvent(w,h)

    # xterm escape sequences from:
    # https://invisible-island.net/xterm/ctlseqs/ctlseqs.html
    # https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Functions-using-CSI-_-ordered-by-the-final-character_s_
    re_CURSOR      = re.compile('^\[((\d*)(;(\d*))*)([@^`A-Za-z])')
    # https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Functions-using-CSI-_-ordered-by-the-final-character_s_
    # Basic Re for CSI Ps matches:
    #   CSI : Control Sequence Introducer "<ESC>[" = '\033['
    #   Ps  : A single (usually optional) numeric parameter, composed of one or more digits.
    #   fn  : the single char defining the function
    re_CSI_Ps_fu    = re.compile('^\[(\d*)([@ABCDEFGIJKLMPSTXZ^`abcdeghinqx])')
    re_CSI_Ps_Ps_fu = re.compile('^\[(\d*);(\d*)([Hf])')

    re_DEC_SET_RST  = re.compile('^\[(\??)(\d+)([lh])')
    # re_CURSOR_1    = re.compile(r'^(\d+)([ABCDEFGIJKLMPSTXZHf])')

    re_OSC_ps_Pt    = re.compile('^(\d*);(.*)$')

    re_XTWINOPS     = re.compile('^')

    @pyTTkSlot()
    def _quit(self):
        if self._quit_pipe:
            os.write(self._quit_pipe[1], b'quit')

    def _inputGenerator(self):
        while rs := select( [self._inout,self._quit_pipe[0],self._resize_pipe[0]], [], [])[0]:
            if self._quit_pipe[0] in rs:
                return

            if self._resize_pipe[0] in rs:
                self._resizeScreen()

            if self._inout not in rs:
                continue

            # _termLog.debug(f"Select - {rs=}")
            for r in rs:
                if r is not self._inout:
                    continue

                try:
                    _fl = fcntl.fcntl(self._inout, fcntl.F_GETFL)
                    fcntl.fcntl(self._inout, fcntl.F_SETFL, _fl | os.O_NONBLOCK) # Set the input as NONBLOCK to read the full sequence
                    out = b""
                    while _out := self._inout.read():
                        out += _out
                    fcntl.fcntl(self._inout, fcntl.F_SETFL, _fl)
                except Exception as e:
                    _termLog.error(f"Error: {e=}")
                    return

                # out = out.decode('utf-8','ignore')
                try:
                    out = out.decode()
                except Exception as e:
                    _termLog.error(f"{e=}")
                    _termLog.error(f"Failed to decode {out}")
                    out = out.decode('utf-8','ignore')

                yield out

    def loop(self, _):
        SGR_SET = TTkTermColor.SGR_SET # Precacing those variables to
        SGR_RST = TTkTermColor.SGR_RST # speedup the search
        inputgenerator = self._inputGenerator()
        leftUnhandled = ""
        for out in inputgenerator:
            sout = (leftUnhandled+out).split('\033')
            _termLog.debug(f"{leftUnhandled=} - {sout[0]=}")

            # The first element is not an escaped sequence
            if sout[0]:
                self._screen_current.pushLine(sout[0],irm=self._terminal.IRM)

            escapeGenerator = (i for i in sout[1:])
            for slice in escapeGenerator:
                leftUnhandled = ""
                ssss = slice.replace('\033','<ESC>').replace('\n','\\n').replace('\r','\\r')
                _termLog.debug(f"slice: '{ssss}'")

                ################################################
                # CSI Modes
                #   CSI Pm h
                #       Set Mode (SM).
                #   CSI Pm l
                #       Reset Mode (RM).
                #   CSI ? Pm h
                #      DEC Private Mode Set (DECSET).
                #   CSI ? Pm l
                #      DEC Private Mode Reset (DECRST).
                ################################################
                if m := TTkTerminalView.re_DEC_SET_RST.match(slice):
                    en = m.end()
                    qm = m.group(1) == '?'
                    ps = int(m.group(2))
                    sr = (m.group(3) == 'h')
                    if qm:
                        self._CSI_DEC_SET_RST(ps,sr)
                    else:
                        self._CSI_SM_RM(ps,sr)
                    slice = slice[en:]

                ################################################
                # CSI Color Functions
                #   CSI Pm ; Pm ; ... m
                ################################################
                elif ((m      := TTkTerminalView.re_CURSOR.match(slice)) and
                      (mg     := m.groups()) and
                       mg[-1] == 'm' ):
                    # _termLog.debug(f"Handle color {mg[0]=}")
                    en = m.end()

                    color=TTkColor.RST

                    if mg[0] not in ['0','']:
                        values = mg[0].split(';')
                        color = self._screen_current.color()
                        fg = color._fg
                        bg = color._bg
                        mod = color._mod
                        clean = False

                        while values:
                            s = int(values.pop(0))
                            if s==0: # Reset Color/Format
                                fg = None
                                bg = None
                                mod = 0
                                clean = True
                            elif s==39: # Ps = 3 9  ⇒  Set foreground color to default, ECMA-48 3rd.
                                fg = None
                            elif s==49: # Ps = 4 9  ⇒  Set background color to default, ECMA-48 3rd.
                                bg = None
                            elif ( # Ansi 16 colors
                                30  <= s <= 37 or   # fg [ 30 -  37]
                                90  <= s <= 97 ):   # fg [ 90 -  97] Bright
                                fg = ansiMap16.get(s)
                            elif ( # Ansi 16 colors
                                40  <= s <= 47 or   # bg [ 40 -  47]
                                100 <= s <= 107 ) : # bg [100 - 107] Bright
                                bg = ansiMap16.get(s)
                            elif s == 38:
                                t =  int(values.pop(0))
                                if t == 5:# 256 fg
                                    fg = ansiMap256.get(int(values.pop(0)))
                                if t == 2:# 24 bit fg
                                    fg = (int(values.pop(0)),int(values.pop(0)),int(values.pop(0)))
                            elif s == 48:
                                t =  int(values.pop(0))
                                if t == 5:# 256 bg
                                    bg = ansiMap256.get(int(values.pop(0)))
                                if t == 2:# 24 bit bg
                                    bg = (int(values.pop(0)),int(values.pop(0)),int(values.pop(0)))
                            elif _sgr:=SGR_SET.get(s,None):
                                mod |= _sgr
                            elif _sgr:=SGR_RST.get(s,None):
                                mod &= _sgr
                            else:
                                _termLog.warn(f"Unhandled color: <ESC>{slice}")
                        color = TTkColor(fg=fg, bg=bg, mod=mod, clean=clean)

                    self._screen_alt.setColor(color)
                    self._screen_normal.setColor(color)

                    # _termLog.debug(TTkString(f"color - <ESC>[{mg[0]}",color).toAnsi())
                    slice = slice[en:]

                ################################################
                # CSI Common Functions
                #   CSI Pm ; Pm ; ... X
                ################################################
                elif m:
                    en = m.end()
                    fn = m.group(5)
                    defval = self._CSI_Default_MAP.get(fn,(1,1))
                    y  = ps = int(y) if (y:=m.group(2)) else defval[0]
                    sep = m.group(3)
                    x =       int(x) if (x:=m.group(4)) else defval[1]
                    _termLog.debug(f"{mg[0]}{fn} = ps:{y=} {sep=} {x=} {fn=}")
                    if fn in ['n']:
                        # Handle the non screen related functions
                        _ex = self._CSI_MAP.get(
                                fn,
                                lambda a,b,c: _termLog.error(f"Unhandled <ESC>[{mg[0]}{fn} = ps:{y=} {sep=} {x=} {fn=}"))
                        _ex(self,y,x)
                    else:
                        # Handle the screen related functions
                        _ex = self._screen_current._CSI_MAP.get(
                                fn,
                                lambda a,b,c: _termLog.error(f"Unhandled <ESC>[{mg[0]}{fn} = ps:{y=} {sep=} {x=} {fn=}"))
                        _ex(self._screen_current,y,x)
                    slice = slice[en:]

                ################################################
                # ESC =     Application Keypad (DECKPAM).
                ################################################
                elif slice and slice[0] in ['=','>']:
                    # ESC =     Application Keypad (DECKPAM).
                    if slice[0] == '=':
                        self._keyboard.flags |= TTkTerminalModes.MODE_DECKPAM
                        _termLog.warn("Unhandled <ESC> = (DECKPAM)")
                    # ESC >     Normal Keypad (DECKPNM), VT100.
                    elif slice[0] == '>':
                        self._keyboard.flags &= ~TTkTerminalModes.MODE_DECKPAM
                        _termLog.warn("Unhandled <ESC> > (DECKPNM)")
                    slice = slice[1:]

                ################################################
                # ESC P
                #   Device Control String (DCS  is 0x90).
                # ESC \
                #   String Terminator (ST  is 0x9c).
                #
                #   ESC P Pt ESC \
                #     Device Control String (DCS) xterm implements no DCS functions; Pt is ignored. Pt need not be printable characters.
                #
                # NOTE:
                #    DCS is an escape sequence that does not happen often
                #    So far I saw it only during vim initialization and
                #    only to check if the TERM=screen is capable to handle DCS
                #    I try to keep everything related in a self contained place
                ################################################
                elif slice and slice[0] == 'P':
                    # Sarting DCS (ESC P) and wait for ST (ESC \)
                    self._terminal.DCSstring = slice[1:]
                    slice = ""

                    # I am using a closure in order to exit the routine at the end
                    def __processDCSEscapeGenerator():
                        for dcs in escapeGenerator:
                            if dcs[0] == '\\':
                                _termLog.warn(f"DCS: {self._terminal.DCSstring} - Not Handled")
                                self._terminal.DCSstring = ""
                                return True, dcs[1:]
                            self._terminal.DCSstring += dcs
                        return False, ""

                    def __processDCSInputGenerator(slice):
                        # If the terminator is not in the current escaped slices
                        # I need to fetch from the input until I got all of them
                        # This is not the nicest thing but it save a bunch of extra
                        # hcecks at any input just to find if we are in DCS mode or not
                        for out in inputgenerator:
                            sout = out.split('\033')
                            self._terminal.DCSstring += sout[0]
                            escapeGenerator = (i for i in sout[1:])
                            ret, slice =  __processDCSEscapeGenerator()
                            if ret:
                                return escapeGenerator, slice

                    ret, slice =  __processDCSEscapeGenerator()

                    if not ret:
                        escapeGenerator, slice = __processDCSInputGenerator()

                    if not slice:
                        continue

                # Operating System Commands = <ESC> ]
                #
                # OSC Ps ; Pt BEL
                #
                # OSC Ps ; Pt ST
                #           Set Text Parameters.  Some control sequences return
                #           information:
                #           o   For colors and font, if Pt is a "?", the control sequence
                #               elicits a response which consists of the control sequence
                #               which would set the corresponding value.
                #           o   The dtterm control sequences allow you to determine the
                #               icon name and window title.
                #
                #           XTerm accepts either BEL  or ST  for terminating OSC
                #           sequences, and when returning information, uses the same
                #           terminator used in a query.  While the latter is preferred,
                #           the former is supported for legacy applications:
                #           o   Although documented in the changes for X.V10R4 (December
                #               1986), BEL  as a string terminator dates from X11R4
                #               (December 1989).
                #           o   Since XFree86-3.1.2Ee (August 1996), xterm has accepted ST
                #               (the documented string terminator in ECMA-48).
                #
                #           Ps specifies the type of operation to perform:
                #             Ps = 0  -> Change Icon Name and Window Title to Pt.
                #             Ps = 1  -> Change Icon Name to Pt.
                #             Ps = 2  -> Change Window Title to Pt.
                #             Ps = 3  -> Set X property on top-level window.  Pt should be
                #           in the form "prop=value", or just "prop" to delete the
                #           property.
                #             Ps = 4 ; c ; spec -> Change Color Number c to the color
                #           specified by spec.
                #
                #           The spec can be a name or RGB specification as per
                #           XParseColor.  Any number of c/spec pairs may be given.  The
                #           color numbers correspond to the ANSI colors 0-7, their bright
                #           versions 8-15, and if supported, the remainder of the 88-color
                #           or 256-color table.
                #
                #           If a "?" is given rather than a name or RGB specification,
                #           xterm replies with a control sequence of the same form which
                #           can be used to set the corresponding color.  Because more than
                #           one pair of color number and specification can be given in one
                #           control sequence, xterm can make more than one reply.
                #
                #             Ps = 5 ; c ; spec -> Change Special Color Number c to the
                #           color specified by spec.
                #
                #           The spec parameter can be a name or RGB specification as per
                #           XParseColor.  Any number of c/spec pairs may be given.  The
                #           special colors can also be set by adding the maximum number of
                #           colors (e.g., 88 or 256) to these codes in an OSC 4  control:
                #
                #               Pc = 0  <- resource colorBD (BOLD).
                #               Pc = 1  <- resource colorUL (UNDERLINE).
                #               Pc = 2  <- resource colorBL (BLINK).
                #               Pc = 3  <- resource colorRV (REVERSE).
                #               Pc = 4  <- resource colorIT (ITALIC).
                #
                #             Ps = 6 ; c ; f -> Enable/disable Special Color Number c.
                #           The second parameter tells xterm to enable the corresponding
                #           color mode if nonzero, disable it if zero.  OSC 6  is the same
                #           as OSC 1 0 6 .
                #
                #           If no parameters are given, this control has no effect.
                #
                #           The 10 colors (below) which may be set or queried using 1 0
                #           through 1 9  are denoted dynamic colors, since the
                #           corresponding control sequences were the first means for
                #           setting xterm's colors dynamically, i.e., after it was
                #           started.  They are not the same as the ANSI colors (however,
                #           the dynamic text foreground and background colors are used
                #           when ANSI colors are reset using SGR 3 9  and 4 9 ,
                #           respectively).  These controls may be disabled using the
                #           allowColorOps resource.  At least one parameter is expected
                #           for Pt.  Each successive parameter changes the next color in
                #           the list.  The value of Ps tells the starting point in the
                #           list.  The colors are specified by name or RGB specification
                #           as per XParseColor.
                #
                #           If a "?" is given rather than a name or RGB specification,
                #           xterm replies with a control sequence of the same form which
                #           can be used to set the corresponding dynamic color.  Because
                #           more than one pair of color number and specification can be
                #           given in one control sequence, xterm can make more than one
                #           reply.
                #
                #             Ps = 1 0  -> Change VT100 text foreground color to Pt.
                #             Ps = 1 1  -> Change VT100 text background color to Pt.
                #             Ps = 1 2  -> Change text cursor color to Pt.
                #             Ps = 1 3  -> Change pointer foreground color to Pt.
                #             Ps = 1 4  -> Change pointer background color to Pt.
                #             Ps = 1 5  -> Change Tektronix foreground color to Pt.
                #             Ps = 1 6  -> Change Tektronix background color to Pt.
                #             Ps = 1 7  -> Change highlight background color to Pt.
                #             Ps = 1 8  -> Change Tektronix cursor color to Pt.
                #             Ps = 1 9  -> Change highlight foreground color to Pt.
                #
                #             Ps = 2 2  -> Change pointer cursor to Pt.
                #
                #             Ps = 4 6  -> Change Log File to Pt.  This is normally
                #           disabled by a compile-time option.
                #
                #             Ps = 5 0  -> Set Font to Pt.  These controls may be disabled
                #           using the allowFontOps resource.  If Pt begins with a "#",
                #           index in the font menu, relative (if the next character is a
                #           plus or minus sign) or absolute.  A number is expected but not
                #           required after the sign (the default is the current entry for
                #           relative, zero for absolute indexing).
                #
                #           The same rule (plus or minus sign, optional number) is used
                #           when querying the font.  The remainder of Pt is ignored.
                #
                #           A font can be specified after a "#" index expression, by
                #           adding a space and then the font specifier.
                #
                #           If the TrueType Fonts menu entry is set (the renderFont
                #           resource), then this control sets/queries the faceName
                #           resource.
                #
                #             Ps = 5 1  -> reserved for Emacs shell.
                #
                #             Ps = 5 2  -> Manipulate Selection Data.  These controls may
                #           be disabled using the allowWindowOps resource.  The parameter
                #           Pt is parsed as
                #                Pc ; Pd
                #
                #           The first, Pc, may contain zero or more characters from the
                #           set c , p , q , s , 0 , 1 , 2 , 3 , 4 , 5 , 6 , and 7 .  It is
                #           used to construct a list of selection parameters for
                #           clipboard, primary, secondary, select, or cut-buffers 0
                #           through 7 respectively, in the order given.  If the parameter
                #           is empty, xterm uses s 0 , to specify the configurable
                #           primary/clipboard selection and cut-buffer 0.
                #
                #           The second parameter, Pd, gives the selection data.  Normally
                #           this is a string encoded in base64 (RFC-4648).  The data
                #           becomes the new selection, which is then available for pasting
                #           by other applications.
                #
                #           If the second parameter is a ? , xterm replies to the host
                #           with the selection data encoded using the same protocol.  It
                #           uses the first selection found by asking successively for each
                #           item from the list of selection parameters.
                #
                #           If the second parameter is neither a base64 string nor ? ,
                #           then the selection is cleared.
                #
                #             Ps = 6 0  -> Query allowed features (XTQALLOWED).  XTerm
                #           replies with
                #
                #             OSC 6 0  ; Pt ST
                #
                #           where Pt is a comma-separated list of the allowed optional
                #           runtime features, i.e., zero or more of these resource names:
                #
                #             allowColorOps
                #             allowFontOps
                #             allowMouseOps
                #             allowPasteControls
                #             allowTcapOps
                #             allowTitleOps
                #             allowWindowOps
                #
                #             Ps = 6 1  -> Query disallowed features (XTQDISALLOWED).  The
                #           second parameter (i.e., the main feature) must be one of the
                #           resource names returned by OSC 6 0 .  XTerm replies with
                #
                #             OSC 6 1  ; Pt ST
                #
                #           where Pt is a comma-separated list of the optional runtime
                #           features which would be disallowed if the main feature is
                #           disabled.
                #
                #             Ps = 1 0 4 ; c -> Reset Color Number c.  It is reset to the
                #           color specified by the corresponding X resource.  Any number
                #           of c parameters may be given.  These parameters correspond to
                #           the ANSI colors 0-7, their bright versions 8-15, and if
                #           supported, the remainder of the 88-color or 256-color table.
                #           If no parameters are given, the entire table will be reset.
                #
                #             Ps = 1 0 5 ; c -> Reset Special Color Number c.  It is reset
                #           to the color specified by the corresponding X resource.  Any
                #           number of c parameters may be given.  These parameters
                #           correspond to the special colors which can be set using an OSC
                #           5  control (or by adding the maximum number of colors using an
                #           OSC 4  control).
                #
                #           If no parameters are given, all special colors will be reset.
                #
                #             Ps = 1 0 6 ; c ; f -> Enable/disable Special Color Number c.
                #           The second parameter tells xterm to enable the corresponding
                #           color mode if nonzero, disable it if zero.
                #
                #               Pc = 0  <- resource colorBDMode (BOLD).
                #               Pc = 1  <- resource colorULMode (UNDERLINE).
                #               Pc = 2  <- resource colorBLMode (BLINK).
                #               Pc = 3  <- resource colorRVMode (REVERSE).
                #               Pc = 4  <- resource colorITMode (ITALIC).
                #               Pc = 5  <- resource colorAttrMode (Override ANSI).
                #
                #           If no parameters are given, this control has no effect.
                #
                #           The dynamic colors can also be reset to their default
                #           (resource) values:
                #             Ps = 1 1 0  -> Reset VT100 text foreground color.
                #             Ps = 1 1 1  -> Reset VT100 text background color.
                #             Ps = 1 1 2  -> Reset text cursor color.
                #             Ps = 1 1 3  -> Reset pointer foreground color.
                #             Ps = 1 1 4  -> Reset pointer background color.
                #             Ps = 1 1 5  -> Reset Tektronix foreground color.
                #             Ps = 1 1 6  -> Reset Tektronix background color.
                #             Ps = 1 1 7  -> Reset highlight color.
                #             Ps = 1 1 8  -> Reset Tektronix cursor color.
                #             Ps = 1 1 9  -> Reset highlight foreground color.
                #
                #             Ps = I  ; c -> Set icon to file.  Sun shelltool, CDE dtterm.
                #           The file is expected to be XPM format, and uses the same
                #           search logic as the iconHint resource.
                #
                #             Ps = l  ; c -> Set window title.  Sun shelltool, CDE dtterm.
                #
                #             Ps = L  ; c -> Set icon label.  Sun shelltool, CDE dtterm.
                elif slice and slice[0] == ']':
                    # Sarting OSC (ESC ]) and wait for ST (ESC \) or BEL (\a)
                    slice = slice[1:]
                    oscString = ""

                    def __checkOSCBell(__osc:str, __oscString:str):
                        if '\a' in __osc: # BEL (Ctrl-G) (\a) as terminator
                            belIndex = __osc.index('\a')
                            __oscString += __osc[:belIndex]
                            return True, __osc[belIndex+1:], __oscString
                        __oscString += __osc
                        return False, "", __oscString

                    # I am using a closure in order to exit the routine at the end
                    def __processOSCEscapeGenerator(__oscString:str):
                        _slice = ""
                        for __osc in escapeGenerator:
                            if __osc[0] == '\\': # ST (0x9c) (<ESC> \) as terminator
                                return True, __osc[1:], __oscString
                            ret, _slice = __checkOSCBell(__osc, __oscString)
                            if ret:
                                return ret, _slice, __oscString
                        return False, "", __oscString

                    def __processOSCInputGenerator(__oscString:str):
                        # If the terminator is not in the current escaped slices
                        # I need to fetch from the input until I got all of them
                        # This is not the nicest thing but it save a bunch of extra
                        # hcecks at any input just to find if we are in OSC mode or not
                        for out in inputgenerator:
                            sout = out.split('\033')
                            self._terminal.DCSstring += sout[0]
                            escapeGenerator = (i for i in sout[1:])
                            ret, _slice, __oscString =  __processOSCEscapeGenerator(__oscString)
                            if ret:
                                return escapeGenerator, slice, __oscString

                    ret, slice, oscString = __checkOSCBell(slice,oscString)

                    if not ret:
                        ret, slice, oscString = __processOSCEscapeGenerator(oscString)

                    if not ret:
                        escapeGenerator, slice, oscString = __processOSCInputGenerator(oscString)

                    _termLog.info(f"OSC: {oscString}")

                    if m := TTkTerminalView.re_OSC_ps_Pt.match(oscString):
                        en = m.end()
                        ps = int(m.group(1))
                        pt = m.group(2)
                            # Ps specifies the type of operation to perform:
                            #   Ps = 0  -> Change Icon Name and Window Title to Pt.
                            #   Ps = 1  -> Change Icon Name to Pt.
                            #   Ps = 2  -> Change Window Title to Pt.
                        if ps in (0,1,2):
                            self.titleChanged.emit(pt)
                    else:
                        _termLog.warn(f"OSC: {oscString} - Not Recognised - yet")

                    if not slice:
                        continue

                # C1 Escape Codes
                #   ESC E   Next Line
                #   ESC D   Index = '\n'
                #   ESC M   Reverse Index
                #   ESC H   Horizontal Tab Set
                elif slice and slice[0] in ('D','E','H','M','O','P','V','W','X','Z'):
                    # Handle the screen related functions
                    _ex = self._screen_current._C1_MAP.get(
                            slice[0],
                            lambda : _termLog.error(f"Unhandled C1 <ESC>{slice[0]}"))
                    _ex(self._screen_current)
                    slice = slice[1:]
                ################################################
                # Everything else
                ################################################
                else:
                    _termLog.warn(f"Unhandled Slice:'<ESC>{slice}'".replace('\n','\\n'))
                    leftUnhandled = "\033"+slice
                    continue

                self._screen_current.pushLine(slice,irm=self._terminal.IRM)

            self.update()
            self.setWidgetCursor(pos=self._screen_current.getCursor())
            _termLog.debug(f"wc:{self._screen_current.getCursor()} {self._proc=}")

    def pasteEvent(self, txt:str):
        if self._terminal.bracketedMode:
            txt = "\033[200~"+txt+"\033[201~"
        self._inout.write(txt.encode())
        return True

    def keyEvent(self, evt):
        # _termLog.debug(f"Key: {evt.code=}")
        _termLog.debug(f"Key: {str(evt)=}")
        if evt.type == TTkK.SpecialKey:
            if evt.mod == TTkK.ControlModifier and evt.key == TTkK.Key_V:
                txt = self._clipboard.text()
                self.pasteEvent(str(txt))
                return True
            if self._keyboard.flags & TTkTerminalModes.MODE_DECCKM:
                if code := {TTkK.Key_Up:    b"\033OA",
                            TTkK.Key_Down:  b"\033OB",
                            TTkK.Key_Right: b"\033OC",
                            TTkK.Key_Left:  b"\033OD"}.get(evt.key):
                    self._inout.write(code)
                    return True
            if evt.key == TTkK.Key_Enter:
                _termLog.debug(f"Key: Enter")
                # self._inout.write(b'\n')
                # self._inout.write(evt.code.encode())
        else: # Input char
            _termLog.debug(f"Key: {evt.key=}")
            # self._inout.write(evt.key.encode())
        self._inout.write(evt.code.encode())
        return True

    # Extended coordinates
    # The original X10 mouse protocol limits the Cx and Cy ordinates to 223
    # (=255 - 32).  XTerm supports more than one scheme for extending this
    # range, by changing the protocol encoding:
    #
    # UTF-8 (1005)
    #           This enables UTF-8 encoding for Cx and Cy under all tracking
    #           modes, expanding the maximum encodable position from 223 to
    #           2015.  For positions less than 95, the resulting output is
    #           identical under both modes.  Under extended mouse mode,
    #           positions greater than 95 generate "extra" bytes which will
    #           confuse applications which do not treat their input as a UTF-8
    #           stream.  Likewise, Cb will be UTF-8 encoded, to reduce
    #           confusion with wheel mouse events.
    #
    #           Under normal mouse mode, positions outside (160,94) result in
    #           byte pairs which can be interpreted as a single UTF-8
    #           character; applications which do treat their input as UTF-8
    #           will almost certainly be confused unless extended mouse mode
    #           is active.
    #
    #           This scheme has the drawback that the encoded coordinates will
    #           not pass through luit(1) unchanged, e.g., for locales using
    #           non-UTF-8 encoding.
    #
    # SGR (1006)
    #           The normal mouse response is altered to use
    #
    #           o   CSI < followed by semicolon-separated
    #
    #           o   encoded button value,
    #
    #           o   Px and Py ordinates and
    #
    #           o   a final character which is M  for button press and m  for
    #               button release.
    #
    #           The encoded button value in this case does not add 32 since
    #           that was useful only in the X10 scheme for ensuring that the
    #           byte containing the button value is a printable code.
    #
    #           o   The modifiers are encoded in the same way.
    #
    #           o   A different final character is used for button release to
    #               resolve the X10 ambiguity regarding which button was
    #               released.
    #
    #           The highlight tracking responses are also modified to an SGR-
    #           like format, using the same SGR-style scheme and button-
    #           encodings.
    #
    # URXVT (1015)
    #           The normal mouse response is altered to use
    #
    #           o   CSI followed by semicolon-separated
    #
    #           o   encoded button value,
    #
    #           o   the Px and Py ordinates and final character M .
    #
    #           This uses the same button encoding as X10, but printing it as
    #           a decimal integer rather than as a single byte.
    #
    #           However, CSI M  can be mistaken for DL (delete lines), while
    #           the highlight tracking CSI T  can be mistaken for SD (scroll
    #           down), and the Window manipulation controls.  For these
    #           reasons, the 1015 control is not recommended; it is not an
    #           improvement over 1006.
    #
    # SGR-Pixels (1016)
    #           Use the same mouse response format as the 1006 control, but
    #           report position in pixels rather than character cells.

    def _sendMouse(self, evt):
        if   not self._mouse.reportPress:
            return False
        if ( not self._mouse.reportDrag and
            evt.evt in (TTkK.Drag, TTkK.Move)):
            # _termLog.mouse(f"{self._mouse.reportDrag=} {evt.evt in (TTkK.Drag, TTkK.Move)=}")
            return False

        x,y = evt.x+1, evt.y+1
        if self._mouse.sgrMode:
            k = {
                TTkK.NoButton     : 3,
                TTkK.AllButtons   : 0,
                TTkK.LeftButton   : 0,
                TTkK.RightButton  : 2,
                TTkK.MidButton    : 1,
                TTkK.MiddleButton : 1,
                TTkK.Wheel        : 64,
            }.get(evt.key, 0)

            k,km,pr = {
                TTkK.Press:     (k,  0,'M'),
                TTkK.Release:   (k,  0,'m'),
                TTkK.Move:      (35, 0,'M'),
                TTkK.Drag:      (k, 32,'M'),
                TTkK.WHEEL_Up:  (k,  0,'M'),
                TTkK.WHEEL_Down:(k,  1,'M')}.get(
                    evt.evt,(0,0,'M'))
            # _termLog.mouse(f'Mouse: <ESC>[<{k+km};{x};{y}{pr}')
            self._inout.write(f'\033[<{k+km};{x};{y}{pr}'.encode())
        else:
            head = {
                TTkK.Press:     b'\033[M ',
                TTkK.Release:   b'\033[M#',
                TTkK.Move:      b'\033[MC',
                TTkK.Drag:      b'\033[M@',
                TTkK.WHEEL_Up:  b'\033[M`',
                TTkK.WHEEL_Down:b'\033[Ma'}.get(
                    evt.evt,
                    b'')
            bah = bytearray(head)
            bah.append((x+32)%0xff)
            bah.append((y+32)%0xff)
            # _termLog.mouse(f'Mouse: '+bah.decode().replace('\033','<ESC>'))
            self._inout.write(bah)
        return True

    def mousePressEvent(self, evt):   return self._sendMouse(evt) | True
    def mouseReleaseEvent(self, evt): return self._sendMouse(evt)
    def mouseDragEvent(self, evt):    return self._sendMouse(evt)
    def wheelEvent(self, evt):        return True if self._sendMouse(evt) else super().wheelEvent(evt)
    def mouseTapEvent(self, evt):     return self._sendMouse(evt)
    def mouseDoubleClickEvent(self, evt): return self._sendMouse(evt)
    def mouseMoveEvent(self, evt):
        if self._mouse.reportMove:
            return self._sendMouse(evt)
        return False

    def paintEvent(self, canvas: TTkCanvas):
        w,h = self.size()
        ox,oy = self.getViewOffsets()
        self._screen_current.paintEvent(canvas,w,h,ox,oy)



    # This map include the default values in case Ps or Row/Col are empty
    # Since almost all the CSI use 1 as default, I am including here only
    # the ones that are different
    _CSI_Default_MAP = {
        'J' : (0,None),
        'K' : (0,None)
    }


    # CSI Ps n  Device Status Report (DSR).
    #             Ps = 5  ⇒  Status Report.
    #           Result ("OK") is CSI 0 n
    #             Ps = 6  ⇒  Report Cursor Position (CPR) [row;column].
    #           Result is CSI r ; c R
    #
    #           Note: it is possible for this sequence to be sent by a
    #           function key.  For example, with the default keyboard
    #           configuration the shifted F1 key may send (with shift-,
    #           control-, alt-modifiers)
    #
    #             CSI 1 ; 2  R , or
    #             CSI 1 ; 5  R , or
    #             CSI 1 ; 6  R , etc.
    #
    #           The second parameter encodes the modifiers; values range from
    #           2 to 16.  See the section PC-Style Function Keys for the
    #           codes.  The modifyFunctionKeys and modifyKeyboard resources
    #           can change the form of the string sent from the modified F1
    #           key.
    def _CSI_n_DSR(self, ps, _):
        x,y = self._screen_current.getCursor()
        if ps==6:
            self._inout.write(f"\033[{y+1};{x+1}R".encode())
        elif ps==5:
            self._inout.write(f"\033[0n".encode())

    # CSI Ps ; Ps ; Ps t
    #           Window manipulation (XTWINOPS), dtterm, extended by xterm.
    #           These controls may be disabled using the allowWindowOps
    #           resource.
    #
    #           xterm uses Extended Window Manager Hints (EWMH) to maximize
    #           the window.  Some window managers have incomplete support for
    #           EWMH.  For instance, fvwm, flwm and quartz-wm advertise
    #           support for maximizing windows horizontally or vertically, but
    #           in fact equate those to the maximize operation.
    #
    #           Valid values for the first (and any additional parameters)
    #           are:
    #             Ps = 1  ⇒  De-iconify window.
    #             Ps = 2  ⇒  Iconify window.
    #             Ps = 3 ;  x ;  y ⇒  Move window to [x, y].
    #             Ps = 4 ;  height ;  width ⇒  Resize the xterm window to
    #           given height and width in pixels.  Omitted parameters reuse
    #           the current height or width.  Zero parameters use the
    #           display's height or width.
    #             Ps = 5  ⇒  Raise the xterm window to the front of the
    #           stacking order.
    #             Ps = 6  ⇒  Lower the xterm window to the bottom of the
    #           stacking order.
    #             Ps = 7  ⇒  Refresh the xterm window.
    #             Ps = 8 ;  height ;  width ⇒  Resize the text area to given
    #           height and width in characters.  Omitted parameters reuse the
    #           current height or width.  Zero parameters use the display's
    #           height or width.
    #             Ps = 9 ;  0  ⇒  Restore maximized window.
    #             Ps = 9 ;  1  ⇒  Maximize window (i.e., resize to screen
    #           size).
    #             Ps = 9 ;  2  ⇒  Maximize window vertically.
    #             Ps = 9 ;  3  ⇒  Maximize window horizontally.
    #             Ps = 1 0 ;  0  ⇒  Undo full-screen mode.
    #             Ps = 1 0 ;  1  ⇒  Change to full-screen.
    #             Ps = 1 0 ;  2  ⇒  Toggle full-screen.
    #             Ps = 1 1  ⇒  Report xterm window state.
    #           If the xterm window is non-iconified, it returns CSI 1 t .
    #           If the xterm window is iconified, it returns CSI 2 t .
    #             Ps = 1 3  ⇒  Report xterm window position.
    #           Note: X Toolkit positions can be negative, but the reported
    #           values are unsigned, in the range 0-65535.  Negative values
    #           correspond to 32768-65535.
    #           Result is CSI 3 ; x ; y t
    #             Ps = 1 3 ;  2  ⇒  Report xterm text-area position.
    #           Result is CSI 3 ; x ; y t
    #             Ps = 1 4  ⇒  Report xterm text area size in pixels.
    #           Result is CSI  4 ;  height ;  width t
    #             Ps = 1 4 ;  2  ⇒  Report xterm window size in pixels.
    #           Normally xterm's window is larger than its text area, since it
    #           includes the frame (or decoration) applied by the window
    #           manager, as well as the area used by a scroll-bar.
    #           Result is CSI  4 ;  height ;  width t
    #             Ps = 1 5  ⇒  Report size of the screen in pixels.
    #           Result is CSI  5 ;  height ;  width t
    #             Ps = 1 6  ⇒  Report xterm character cell size in pixels.
    #           Result is CSI  6 ;  height ;  width t
    #             Ps = 1 8  ⇒  Report the size of the text area in characters.
    #           Result is CSI  8 ;  height ;  width t
    #             Ps = 1 9  ⇒  Report the size of the screen in characters.
    #           Result is CSI  9 ;  height ;  width t
    #             Ps = 2 0  ⇒  Report xterm window's icon label.
    #           Result is OSC  L  label ST
    #             Ps = 2 1  ⇒  Report xterm window's title.
    #           Result is OSC  l  label ST
    #             Ps = 2 2 ; 0  ⇒  Save xterm icon and window title on stack.
    #             Ps = 2 2 ; 1  ⇒  Save xterm icon title on stack.
    #             Ps = 2 2 ; 2  ⇒  Save xterm window title on stack.
    #             Ps = 2 3 ; 0  ⇒  Restore xterm icon and window title from
    #           stack.
    #             Ps = 2 3 ; 1  ⇒  Restore xterm icon title from stack.
    #             Ps = 2 3 ; 2  ⇒  Restore xterm window title from stack.
    #             Ps >= 2 4  ⇒  Resize to Ps lines (DECSLPP), VT340 and VT420.
    #           xterm adapts this by resizing its window.
    def _CSI_t_XTWINOPS(self, ps, _):
        pass

    _CSI_MAP = {
        'n': _CSI_n_DSR,
    }

    # CSI Pm h  Set Mode (SM).
    #             Ps = 2  ⇒  Keyboard Action Mode (KAM).
    #             Ps = 4  ⇒  Insert Mode (IRM).
    #             Ps = 1 2  ⇒  Send/receive (SRM).
    #             Ps = 2 0  ⇒  Automatic Newline (LNM).
    #             Ps = 3 4  ⇒  Normal Cursor Visibility
    # CSI Pm l  Reset Mode (RM).
    #             Ps = 2  ⇒  Keyboard Action Mode (KAM).
    #             Ps = 4  ⇒  Replace Mode (IRM).
    #             Ps = 1 2  ⇒  Send/receive (SRM).
    #             Ps = 2 0  ⇒  Normal Linefeed (LNM).
    #             Ps = 3 4  ⇒  Normal Cursor Visibility
    def _CSI_SM_RM(self, ps, s):
        if ps == 4: # Insert/Replace Mode
            self._terminal.IRM = s
        elif ps == 34:
            _termLog.warn(f"Unhandled (SM) <ESC>{ps}{'h' if s else 'l'} Normal Cursor Visibility")
        else:
            _termLog.error(f"Unhandled (SM) <ESC>{ps}{'h' if s else 'l'}")

    def _CSI_DEC_SET_RST(self, ps, s):
        _dec = self._CSI_DEC_SET_RST_MAP.get(
                ps,
                lambda a,b: _termLog.error(f"Unhandled (DEC) <ESC>[{ps}{'h' if s else 'l'}"))
        _dec(self, s)
