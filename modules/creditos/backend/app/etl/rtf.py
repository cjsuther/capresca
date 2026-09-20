"""Conversión RTF → texto plano para migrar los memos del legacy (H-165).

Los campos memo de Despacho (TEXTO de resoluciones, MODELO de rtf) guardan Rich Text Format. Para
mostrarlos en la app los pasamos a texto plano. Implementación del algoritmo clásico de `striprtf`
(dominio público, Gareth Gilson): maneja grupos anidados, destinos ignorables, `\\uN`, `\\'xx` y los
caracteres especiales usuales.
"""
import re

_PATTERN = re.compile(
    r"\\([a-z]{1,32})(-?\d{1,10})?[ ]?|\\'([0-9a-f]{2})|\\([^a-z])|([{}])|[\r\n]+|(.)",
    re.IGNORECASE,
)

# Destinos cuyo contenido NO es texto del documento (se ignoran).
_DESTINATIONS = frozenset((
    "aftncn", "aftnsep", "aftnsepc", "annotation", "atnauthor", "atndate", "atnicn", "atnid",
    "atnparent", "atnref", "atntime", "atrfend", "atrfstart", "author", "background", "bkmkcolf",
    "bkmkcoll", "bkmkend", "bkmkstart", "buptim", "category", "colorschememapping", "colortbl",
    "comment", "company", "creatim", "datafield", "datastore", "defchp", "defpap", "do", "doccomm",
    "docvar", "dptxbxtext", "ebcend", "ebcstart", "factoidname", "falt", "fchars", "ffdeftext",
    "ffentrymcr", "ffexitmcr", "ffformat", "ffhelptext", "ffl", "ffname", "ffstattext", "field",
    "file", "filetbl", "fldinst", "fldrslt", "fldtype", "fname", "fontemb", "fontfile", "fonttbl",
    "footer", "footerf", "footerl", "footerr", "footnote", "formfield", "ftncn", "ftnsep", "ftnsepc",
    "g", "generator", "gridtbl", "header", "headerf", "headerl", "headerr", "hl", "hlfr", "hlinkbase",
    "hlloc", "hlsrc", "hsv", "htmltag", "info", "keycode", "keywords", "latentstyles", "lchars",
    "levelnumbers", "leveltext", "lfolevel", "linkval", "list", "listlevel", "listname", "listoverride",
    "listoverridetable", "listpicture", "liststylename", "listtable", "listtext", "lsdlockedexcept",
    "macc", "maccPr", "mailmerge", "maln", "malnScr", "manager", "margPr", "mbar", "mbarPr", "mbaseJc",
    "mbegChr", "mborderBox", "mborderBoxPr", "mbox", "mboxPr", "mchr", "mcount", "mctrlPr", "md",
    "mdeg", "mdegHide", "mden", "mdiff", "mdPr", "me", "mendChr", "meqArr", "meqArrPr", "mf", "mfName",
    "mfPr", "mfunc", "mfuncPr", "mgroupChr", "mgroupChrPr", "mgrow", "mhideBot", "mhideLeft",
    "mhideRight", "mhideTop", "mhtmltag", "mlim", "mlimloc", "mlimlow", "mlimlowPr", "mlimupp",
    "mlimuppPr", "mm", "mmaddfieldname", "mmath", "mmathPict", "mmathPr", "mmaxdist", "mmc", "mmcJc",
    "mmconnectstr", "mmconnectstrdata", "mmcPr", "mmcs", "mmdatasource", "mmheadersource", "mmmailsubject",
    "mmodso", "mmodsofilter", "mmodsofldmpdata", "mmodsomappedname", "mmodsoname", "mmodsorecipdata",
    "mmodsosort", "mmodsosrc", "mmodsotable", "mmodsoudl", "mmodsoudldata", "mmodsouniquetag", "mmPr",
    "mmquery", "mmr", "mnary", "mnaryPr", "mnoBreak", "mnum", "mobjDist", "moMath", "moMathPara",
    "moMathParaPr", "mopEmu", "mphant", "mphantPr", "mplcHide", "mpos", "mr", "mrad", "mradPr",
    "mrPr", "msepChr", "mshow", "mshp", "msPre", "msPrePr", "msSub", "msSubPr", "msSubSup", "msSubSupPr",
    "msSup", "msSupPr", "mstrikeBLTR", "mstrikeH", "mstrikeTLBR", "mstrikeV", "msub", "msubHide",
    "msup", "msupHide", "mtransp", "mtype", "mvertJc", "mvfmf", "mvfml", "mvtof", "mvtol", "mzeroAsc",
    "mzeroDesc", "mzeroWid", "nesttableprops", "nextfile", "nonesttables", "objalias", "objclass",
    "objdata", "object", "objname", "objsect", "objtime", "oldcprops", "oldpprops", "oldsprops",
    "oldtprops", "oleclsid", "operator", "panose", "password", "passwordhash", "pgp", "pgptbl",
    "picprop", "pict", "pn", "pnseclvl", "pntext", "pntxta", "pntxtb", "printim", "private",
    "propname", "protend", "protstart", "protusertbl", "pxe", "result", "revtbl", "revtim", "rsidtbl",
    "rxe", "shp", "shpgrp", "shpinst", "shppict", "shprslt", "shptxt", "sn", "sp", "staticval",
    "stylesheet", "subject", "sv", "svb", "tc", "template", "themedata", "title", "txe", "ud",
    "upr", "userprops", "wgrffmtfilter", "windowcaption", "writereservation", "writereservhash",
    "xe", "xform", "xmlattrname", "xmlattrvalue", "xmlclose", "xmlname", "xmlnstbl", "xmlopen",
))

_SPECIAL = {
    "par": "\n", "sect": "\n\n", "page": "\n\n", "line": "\n", "tab": "\t",
    "emdash": "\u2014", "endash": "\u2013", "emspace": "\u2003", "enspace": "\u2002",
    "qmspace": "\u2005", "bullet": "\u2022", "lquote": "\u2018", "rquote": "\u2019",
    "ldblquote": "\u201C", "rdblquote": "\u201D",
}


def rtf_a_texto(text: str) -> str:
    """Devuelve el texto plano de un memo RTF (o el string tal cual si no es RTF)."""
    if not text:
        return ""
    if "\\rtf" not in text[:20]:
        return text.strip()                     # no es RTF (algún memo viejo puede ser texto plano)
    stack: list[tuple[int, bool]] = []
    ignorable = False
    ucskip = 1
    curskip = 0
    out: list[str] = []
    for m in _PATTERN.finditer(text):
        word, arg, hexcode, char, brace, tchar = m.groups()
        if brace:
            if brace == "{":
                stack.append((ucskip, ignorable))
            elif brace == "}" and stack:
                ucskip, ignorable = stack.pop()
        elif char:                              # símbolo de control \x
            if char == "~" and not ignorable:
                out.append("\u00A0")
            elif char in "{}\\" and not ignorable:
                out.append(char)
            elif char == "*":
                ignorable = True
        elif word:                              # palabra de control \word
            if word in _DESTINATIONS:
                ignorable = True
            elif ignorable:
                pass
            elif word in _SPECIAL:
                out.append(_SPECIAL[word])
            elif word == "uc":
                ucskip = int(arg or 1)
            elif word == "u":
                c = int(arg)
                if c < 0:
                    c += 0x10000
                out.append(chr(c) if c <= 0x10FFFF else "?")
                curskip = ucskip
        elif hexcode:                           # \'xx
            if not ignorable:
                if curskip > 0:
                    curskip -= 1
                else:
                    out.append(bytes([int(hexcode, 16)]).decode("cp1252", "ignore"))
        elif tchar:                             # carácter suelto
            if curskip > 0:
                curskip -= 1
            elif not ignorable:
                out.append(tchar)
    s = "".join(out)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _esc_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rtf_a_html(text: str) -> str:
    """RTF → HTML preservando negrita, cursiva, subrayado y alineación por párrafo (para el editor
    mini-Word y el export a Word). Los párrafos centrados y en negrita quedan como títulos naturales."""
    if not text:
        return ""
    if "\\rtf" not in text[:20]:
        # texto plano → párrafos (líneas en blanco separan; saltos simples con <br>)
        return "".join(f"<p>{_esc_html(b).strip().replace(chr(10), '<br>')}</p>"
                       for b in text.split("\n\n") if b.strip())

    stack: list[tuple] = []
    ignorable = False
    ucskip = 1
    curskip = 0
    bold = italic = under = False
    align = "left"
    paras: list[tuple[str, list]] = []          # [(align, [(txt,b,i,u), ...])]
    runs: list[tuple] = []
    buf: list[str] = []

    def flush_run():
        nonlocal buf
        if buf:
            runs.append(("".join(buf), bold, italic, under))
            buf = []

    def flush_par():
        nonlocal runs
        flush_run()
        if any(t.strip() for t, *_ in runs):
            paras.append((align, runs))
        runs = []

    for m in _PATTERN.finditer(text):
        word, arg, hexcode, char, brace, tchar = m.groups()
        if brace:
            if brace == "{":
                stack.append((ucskip, ignorable, bold, italic, under, align))
            elif brace == "}" and stack:
                flush_run()
                ucskip, ignorable, bold, italic, under, align = stack.pop()
        elif char:
            if char == "~" and not ignorable:
                buf.append(" ")
            elif char in "{}\\" and not ignorable:
                buf.append(char)
            elif char == "*":
                ignorable = True
        elif word:
            if word in _DESTINATIONS:
                ignorable = True
            elif ignorable:
                pass
            elif word in ("par", "sect", "line"):
                flush_par()
            elif word == "pard":
                flush_par(); align = "left"; flush_run(); bold = italic = under = False
            elif word in ("qc", "qr", "qj", "ql"):
                align = {"qc": "center", "qr": "right", "qj": "justify", "ql": "left"}[word]
            elif word == "b":
                flush_run(); bold = (arg != "0")
            elif word == "i":
                flush_run(); italic = (arg != "0")
            elif word in ("ul", "ulnone"):
                flush_run(); under = (word == "ul")
            elif word == "uc":
                ucskip = int(arg or 1)
            elif word == "u":
                c = int(arg)
                if c < 0:
                    c += 0x10000
                buf.append(chr(c) if c <= 0x10FFFF else "?")
                curskip = ucskip
            elif word in _SPECIAL and _SPECIAL[word] not in ("\n", "\n\n"):
                buf.append(_SPECIAL[word])
        elif hexcode:
            if not ignorable:
                if curskip > 0:
                    curskip -= 1
                else:
                    buf.append(bytes([int(hexcode, 16)]).decode("cp1252", "ignore"))
        elif tchar:
            if curskip > 0:
                curskip -= 1
            elif not ignorable:
                buf.append(tchar)
    flush_par()

    html: list[str] = []
    for al, rns in paras:
        style = "" if al == "left" else f' style="text-align:{al}"'
        inner = []
        for txt, b, i, u in rns:
            t = _esc_html(txt)
            if not t:
                continue
            if b: t = f"<b>{t}</b>"
            if i: t = f"<i>{t}</i>"
            if u: t = f"<u>{t}</u>"
            inner.append(t)
        if inner:
            html.append(f"<p{style}>{''.join(inner)}</p>")
    return "".join(html)
