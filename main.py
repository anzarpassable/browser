import socket
import ssl
import tkinter
import tkinter.font

# CONSTANTS
WIDTH = 800 # WINDOW
HEIGHT = 600 # WINDOW

HSTEP = 9 # TEXT RENDERING
VSTEP = 13 # TEXT RENDERING
FONTS = {} # TEXT RENDERING
SCROLL_STEP = 100 # TEXT SCROLLING

SELF_CLOSING_TAGS = ["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"] # HTML PARSING
HEAD_TAGS = ["base", "basefont", "bgsound", "noscript", "link", "meta", "title", "style", "script"] # HTML PARSING

class URL:
    def __init__(self, url):

        # TODO: See if I can find a way to default to http/https so you dont need to type it all out when starting

        self.scheme, url = url.split("://", 1) # ex: "http://example.com/" would become ["http", "example.com/"], self.scheme takes [0], url takes [1]
                                               # second arg of .split() defines the maximum number of splits to make

        assert self.scheme in ["http", "https"] # assert raises an error if the comparison evaluates to False
        if "/" not in url:
            url += "/"
        self.host, url = url.split("/", 1)
        self.path = "/" + url

        '''
        example url = "http://www.youtube.com/watch"
        self.scheme = http
        self.host = youtube.com
        self.path = /watch
        '''

        if ":" in self.host: # used to specify custom ports, such as http://example.org:8080/index.html
            self.host, port = self.host.split(":", 1)
            self.port = int(port)

        if self.scheme == "http": self.port = 80
        elif self.scheme == "https": self.port = 443

    def request(self):
        s = socket.socket(
            family = socket.AF_INET, # INET = internet
            type = socket.SOCK_STREAM, # SOCK_STREAM = both computers can send arbitrary amounts of data
            proto = socket.IPPROTO_TCP # using TCP/IP protocol
        )
        s.connect((self.host, self.port)) # connect() takes only one argument, a pair of a host and port, so we place them in a tuple.
        if self.scheme == "https":
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname = self.host)

        request = f"GET {self.path} HTTP/1.0\r\n"
        request += f"Host: {self.host}\r\n"
        request += f"User-Agent: MetaverseNavigator (syed.anzar234@gmail.com)\r\n"
        request += "\r\n"

        s.send(request.encode("utf8"))

        response = s.makefile("r", encoding = "utf8", newline = "\r\n") # makefile() converts the response from the server (which is in a bytestream)
                                                                        # into an in-memory-only file, using UTF-8 encoding and \r\n newline characters
        statusline = response.readline()
        version, status, explanation = statusline.split(" ", 2)

        response_headers = {}
        while True:
            line = response.readline()
            if line == "\r\n":
                break
            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip() # headers are case-insensitive, normalize to lower case. whitespace irrelevant, so strip it

        assert "transfer-encoding" not in response_headers # if present, the server is sending the response in "chunks" instead of one block
        assert "content-encoding" not in response_headers # if present, the server has compressed the response
        # both of the above encodings mean we have to do more work to parse the response, so better to just not deal with it

        content = response.read()
        s.close()

        return content
    
class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.window.title("MetaverseNavigator")
        self.window.iconbitmap("icon.ico")
        self.canvas = tkinter.Canvas(
            self.window,
            width = WIDTH,
            height = HEIGHT
        )
        self.chosenFont = tkinter.font.Font(
            family = "Roboto",
            size = 16
        )
        self.canvas.pack()

        self.scrolled = 0
        self.window.bind("<Down>", self.scrollDown)
        self.window.bind("<Up>", self.scrollUp)
        self.window.bind("<MouseWheel>", self.scrollWheel)

    def scrollDown(self, e):
        self.scrolled += SCROLL_STEP
        self.draw()

    def scrollUp(self, e):
        self.scrolled = max(0, self.scrolled - SCROLL_STEP)
        self.draw()

    def scrollWheel(self, e):        
        if self.scrolled - e.delta >= -20:
            self.scrolled -= e.delta
            self.draw()
        else:
            return

    def draw(self):
        documentHeight = max(y for x, y, c, font in self.displayList)
        maxScroll = max(0, documentHeight - (HEIGHT * 0.75))
        if self.scrolled < maxScroll:
            self.canvas.delete("all")
        else:
            self.scrolled = maxScroll
            return
        for x, y, c, font in self.displayList:
            if  y > self.scrolled + HEIGHT: continue
            if y + VSTEP < self.scrolled: continue
            self.scrolled = min(self.scrolled, maxScroll)
            self.canvas.create_text(x, y - self.scrolled, text = c, anchor = "nw", font = font)

    def load(self, url):
        body = url.request()
        self.nodes = HTMLParser(body).parse()
        self.displayList = Layout(self.nodes).displayList
        self.draw()
    
class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = [] # text nodes never have children, this field has been added to maintain consistency with Element
        self.parent = parent

    def __repr__(self):
        return repr(self.text)

class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent

    def __repr__(self):
        return f"<{self.tag}>"

class Layout:
    def __init__(self, tree):
        self.line = []
        self.displayList = []

        self.weight = "normal"
        self.style = "roman"
        self.size = 16

        self.cursorX = HSTEP
        self.cursorY = VSTEP

        self.recurse(tree)
        
        self.flush()

    def processWord(self, word):
        for word in word.split():
                font = getWordProperties(self.size, self.weight, self.style)
                w = font.measure(word)
                if self.cursorX + w > WIDTH - HSTEP: # checking to see if the width of the word makes it go past the edge of the window
                    #self.cursorY += font.metrics("linespace") * 1.25 # if it does, move the Y co-ord by the height of the font plus a little padding
                    #self.cursorX = HSTEP # reset X co-ord to start of line
                    self.flush()
                #self.displayList.append((self.cursorX, self.cursorY, word, font))
                self.line.append((self.cursorX, word, font))
                self.cursorX += w + font.measure(" ")

    def recurse(self, tree):
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.processWord(word)
        else:
            self.openTag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.closeTag(tree.tag)

    def flush(self):
        # this function aligns all words in a line to a given baseline and adds the words to displayList along with their new X and Y co-ords
        if not self.line: # if the line is empty
            return
        metrics = [font.metrics() for x, word, font in self.line]
        maxAscent = max([metric["ascent"] for metric in metrics]) # find the height of the tallest word in the line. height can change with <big> for example
        baseline = self.cursorY + (1.25 * maxAscent) # cursorY points to the top of the letter, baseline is 1.25*maxAscent units below the top
        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.displayList.append((x, y, word, font))
        maxDescent = max([metric["descent"] for metric in metrics])

        # reset X, Y, and line[]. ready to draw next line
        self.cursorY = baseline + (1.25 * maxDescent)
        self.cursorX = HSTEP
        self.line = []

    def openTag(self, tag):
        if tag == "i":
            self.style = "italic"
        elif tag == "b":
            self.weight = "bold"
        elif tag == "small":
            self.size -= 2
        elif tag == "big":
            self.size += 4
        elif tag == "p":
            self.flush()

    def closeTag(self, tag):
        if tag == "i":
            self.style = "roman"
        elif tag == "b":
            self.weight = "normal"
        elif tag == "small":
            self.size += 2
        elif tag == "big":
            self.size -= 4
        elif tag == "p":
            self.flush()
            self.cursorY += VSTEP * 2

class HTMLParser:
    def __init__(self, body):
        self.body = body
        self.unfinished = []

    def parse(self):
        text = ""
        inTag = False

        for c in self.body:
            if c == "<":
                tnTag = True
                if text:
                    self.addText(text)
                text = ""
            elif c == ">":
                inTag = False
                self.addTag(text)
                text = ""
            else:
                text += c
        
        if not inTag and text:
            self.addText(text)
        
        return self.finish()
    
    def addText(self, text):
        if text.isspace():
            return
        self.implicitTags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def addTag(self, tag):
        tag, attributes = self.getAttributes(tag)
        if tag.startswith("!"):
            return
        self.implicitTags(tag)
        if tag in SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
        elif tag.startswith("/"):
            if len(self.unfinished) == 1: # if only one tag left in unfinished[], it is probably the closing </html>, nothing needs to be done
                return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None # if unfinished[] is empty this is the first tag and so has no parent (usually <html>)
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)

    def finish(self):
        if not self.unfinished:
            self.implicitTags(None)
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()
    
    def getAttributes(self, text):
        parts = text.split()
        tag = parts[0].casefold()
        attributes = {}
        for attributeValuePair in parts[1:]:
            if "=" in attributeValuePair:
                key, value = attributeValuePair.split("=", 1)
                if len(value) > 2 and value[0] in ["'", "\""]: # remove quotation marks if present
                    value = value[1:-1]
                attributes[key.casefold()] = value
            else:
                attributes[attributeValuePair.casefold()] = ""
        return tag, attributes

    def implicitTags(self, tag):
        while True:
            openTags = [node.tag for node in self.unfinished]
            if openTags == [] and tag != "html":
                self.addTag("html")
            elif openTags == ["html"] and tag not in ["head", "body", "/html"]:
                if tag in HEAD_TAGS:
                    self.addTag("head")
                else:
                    self.addTag("body")
            elif openTags == ["html", "head"] and tag not in ["/head"] + HEAD_TAGS:
                self.addTag("/head")
            else:
                break

def printTree(node, indent = 0):
    print(" " * indent, node)
    for child in node.children:
        printTree(child, indent + 2)
    
def getWordProperties(size, weight, style): # returns words which we've already processed
    key = (size, weight, style)

    if key not in FONTS:
        font = tkinter.font.Font(
            family = "Roboto",
            size = size,
            weight = weight,
            slant = style
        )
        label = tkinter.Label(font = font)
        FONTS[key] = (font, label)
    
    return FONTS[key][0]

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1: # first argv is always script name, so we check if there are at least 2 args. if not, we load a default url
        Browser().load(URL(sys.argv[1]))
    else:
        inputURL = "https://www.browser.engineering/html.html"
        Browser().load(URL(inputURL))
    tkinter.mainloop()