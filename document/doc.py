# document.py
# A module to handle documents

#    Copyright (C) 2004 Jeremy S. Sanders
#    Email: Jeremy Sanders <jeremy@jeremysanders.net>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
##############################################################################

# $Id$

import os
import os.path
import time
import numarray
import random
import string
import itertools

import qt

import widgets
import utils

def _cnvt_numarray(a):
    """Convert to a numarray if possible (doing copy)."""
    if a == None:
        return None
    elif type(a) != type(numarray.arange(1)):
        return numarray.array(a, type=numarray.Float64)
    else:
        return a.astype(numarray.Float64)

class Dataset:
    '''Represents a dataset.'''

    def __init__(self, data = None, serr = None, nerr = None, perr = None):
        '''Initialse storage.'''
        self.data = _cnvt_numarray(data)
        self.serr = self.nerr = self.perr = None

        # adding data*0 ensures types of errors are the same
        if self.data != None:
            if serr != None:
                self.serr = serr + self.data*0.
            if nerr != None:
                self.nerr = nerr + self.data*0.
            if perr != None:
                self.perr = perr + self.data*0.

    def hasErrors(self):
        '''Whether errors on dataset'''
        return self.serr != None or self.nerr != None or self.perr != None

    def getPointRanges(self):
        '''Get range of coordinates for each point in the form
        (minima, maxima).'''

        minvals = self.data.copy()
        maxvals = self.data.copy()

        if self.serr != None:
            minvals -= self.serr
            maxvals += self.serr

        if self.nerr != None:
            minvals += self.nerr

        if self.perr != None:
            maxvals += self.perr

        return (minvals, maxvals)

    def getRange(self):
        '''Get total range of coordinates.'''
        minvals, maxvals = self.getPointRanges()
        return ( numarray.minimum.reduce(minvals),
                 numarray.maximum.reduce(maxvals) )

    def empty(self):
        '''Is the data defined?'''
        return self.data == None or len(self.data) == 0

    # TODO implement mathematical operations on this type

    def saveToFile(self, file, name):
        '''Save data to file.'''

        # build up descriptor
        datasets = [self.data]
        descriptor = name
        if self.serr != None:
            descriptor += ',+-'
            datasets.append(self.serr)
        if self.perr != None:
            descriptor += ',+'
            datasets.append(self.perr)
        if self.nerr != None:
            descriptor += ',-'
            datasets.append(self.nerr)

        file.write( "ImportString('%s','''\n" % descriptor )

        # write line line-by-line
        format = '%e ' * len(datasets)
        format = format[:-1] + '\n'
        for line in itertools.izip( *datasets ):
            file.write( format % line )

        file.write( "''')\n" )

class Document( qt.QObject ):
    """Document class for holding the graph data.

    Emits: sigModified when the document has been modified
           sigWiped when document is wiped
    """

    def __init__(self):
        """Initialise the document."""
        qt.QObject.__init__( self )

        self.changeset = 0
        self.wipe()

    def wipe(self):
        """Wipe out any stored data."""

        self.data = {}
        self.basewidget = widgets.Root(None)
        self.basewidget.document = self
        self.setModified()
        self.emit( qt.PYSIGNAL("sigWiped"), () )

    def setData(self, name, dataset):
        """Set data to val, with symmetric or negative and positive errors."""
        self.data[name] = dataset
        self.setModified()

    def getData(self, name):
        """Get data with name"""
        return self.data[name]

    def hasData(self, name):
        """Whether dataset is defined."""
        return name in self.data

    def setModified(self, ismodified=True):
        """Set the modified flag on the data, and inform views."""

        # useful for tracking back modifications
        # import traceback
        # traceback.print_stack()

        self.modified = ismodified
        self.changeset += 1
        self.emit( qt.PYSIGNAL("sigModified"), ( ismodified, ) )

    def isModified(self):
        """Return whether modified flag set."""
        return self.modified
    
    def getSize(self):
        """Get the size of the main plot widget."""
        s = self.basewidget.settings
        return (s.width, s.height)

    def printTo(self, printer, pages, scaling = 1.):
        """Print onto printing device."""

        painter = qt.QPainter()
        painter.begin( printer )

        painter.veusz_scaling = scaling

        # work out how many pixels correspond to the given size
        width, height = utils.cnvtDists(self.getSize(), painter)
        children = self.basewidget.children

        # This all assumes that only pages can go into the root widget
        i = 0
        no = len(pages)

        for p in pages:
            c = children[p]
            c.draw( (0, 0, width, height), painter )

            # start new pages between each page
            if i < no-1:
                printer.newPage()
            i += 1

        painter.end()

    def getNumberPages(self):
        """Return the number of pages in the document."""
        return len(self.basewidget.children)

    def saveToFile(self, file):
        """Save the text representing a document to a file."""

        file.write('# Veusz saved document (version %s)\n' % utils.version())
        try:
            file.write('# User: %s\n' % os.environ['LOGNAME'] )
        except KeyError:
            pass
        file.write('# Date: %s\n\n' % time.strftime(
            "%a, %d %b %Y %H:%M:%S +0000", time.gmtime()) )
        
        for name, dataset in self.data.items():
            dataset.saveToFile(file, name)
        file.write(self.basewidget.getSaveText())
        
        self.setModified(False)

    def export(self, filename, pagenumber, color=True):
        """Export the figure to the filename."""

        ext = os.path.splitext(filename)[1]

        if ext == '.eps':
            # write eps file
            p = qt.QPrinter(qt.QPrinter.HighResolution)
            p.setCreator('Veusz %s' % utils.version())
            p.setOutputToFile(True)
            p.setOutputFileName(filename)
            p.setColorMode( (qt.QPrinter.GrayScale, qt.QPrinter.Color)[color] )
            p.setCreator('Veusz %s' % utils.version())
            p.newPage()
            self.printTo( p, [pagenumber] )

        elif ext == '.png':
            # write png file
            # unfortunately we need to pass QPrinter the name of an eps
            # file: no secure way we can produce the file. FIXME INSECURE

            fdir = os.path.dirname(os.path.abspath(filename))
            while 1:
                digits = string.digits + string.ascii_letters
                rndstr = ''
                for i in xrange(40):
                    rndstr += random.choice(digits)
                tmpfilename = "%s/tmp_%s.eps" % (fdir, rndstr)
                try:
                    os.stat(tmpfilename)
                except OSError:
                    break
            
            # write eps file
            p = qt.QPrinter(qt.QPrinter.HighResolution)
            p.setOutputToFile(True)
            p.setOutputFileName(tmpfilename)
            p.setColorMode( (qt.QPrinter.GrayScale, qt.QPrinter.Color)[color] )
            p.newPage()
            self.printTo( p, [pagenumber] )

            # now use ghostscript to convert the file into the relevent type
            cmdline = ( 'gs -sDEVICE=pngalpha -dEPSCrop -dBATCH -dNOPAUSE'
                        ' -sOutputFile="%s" "%s"' % (filename, tmpfilename) )
            stdin, stdout, stderr = os.popen3(cmdline)
            stdin.close()

            # if anything goes to stderr, then report it
            text = stderr.read().strip()
            if len(text) != 0:
                raise RuntimeError, text

            os.unlink(tmpfilename)

        else:
            raise RuntimeError, "File type '%s' not supported" % ext
        
