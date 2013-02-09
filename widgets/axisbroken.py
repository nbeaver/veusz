#    Copyright (C) 2013 Jeremy S. Sanders
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
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc.,
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
##############################################################################

'''An axis which can be broken in places.'''

import numpy as N

import veusz.qtall as qt4
import veusz.setting as setting
import veusz.document as document

import axis
import controlgraph

def _(text, disambiguation=None, context='BrokenAxis'):
    '''Translate text.'''
    return unicode( 
        qt4.QCoreApplication.translate(context, text, disambiguation))

class AxisBroken(axis.Axis):
    '''An axis widget which can have gaps in it.'''

    typename = 'axis-broken'
    description = 'Axis with breaks in it'

    def __init__(self, parent, name=None):
        """Initialise axis."""
        axis.Axis.__init__(self, parent, name=name)
        self.rangeswitch = None

    @classmethod
    def addSettings(klass, s):
        '''Construct list of settings.'''
        axis.Axis.addSettings(s)

        s.add( setting.FloatList(
                'breakPoints',
                [],
                descr = _('Pairs of values to start and stop breaks'),
                usertext = _('Break pairs'),
                ) )
        s.add( setting.FloatList(
                'breakPosns',
                [],
                descr = _('Positions (fractions) along axis where to break'),
                usertext = _('Break positions'),
                ) )

    def switchBreak(self, num, posn, otherposition=None):
        """Switch to break given (or None to disable)."""
        self.rangeswitch = num
        if num is None:
            self.plottedrange = self.orig_plottedrange
        else:
            self.plottedrange = [self.breakvstarts[num], self.breakvstops[num]]
        self.updateAxisLocation(posn, otherposition=otherposition)

    def updateAxisLocation(self, bounds, otherposition=None):
        """Recalculate broken axis positions."""

        s = self.settings

        bounds = list(bounds)
        if self.rangeswitch is None:
            pass
        else:
            if s.direction == 'horizontal':
                d = bounds[2]-bounds[0]
                n0 = bounds[0] + d*self.posstarts[self.rangeswitch]
                n2 = bounds[0] + d*self.posstops[self.rangeswitch]
                bounds[0] = n0
                bounds[2] = n2
            else:
                d = bounds[1]-bounds[3]
                n1 = bounds[3] + d*self.posstops[self.rangeswitch]
                n3 = bounds[3] + d*self.posstarts[self.rangeswitch]
                bounds[1] = n1
                bounds[3] = n3

        axis.Axis.updateAxisLocation(self, bounds, otherposition=otherposition)

        # actually start and stop values on axis
        points = s.breakPoints
        num = len(points) / 2
        posns = list(s.breakPosns)
        posns.sort()

        # add on more break positions if not specified
        if len(posns) < num:
            start = 0.
            if len(posns) != 0:
                start = posns[-1]
            posns = posns + list(
                N.arange(1,num-len(posns)+1) *
                ( (1.-start) / (num-len(posns)+1) + start ))

        # fractional difference between starts and stops
        breakgap = 0.05

        # collate fractional positions for starting and stopping
        self.posstarts = starts = [0.]
        self.posstops = stops = []

        for pos in posns:
            stops.append( pos - breakgap/2. )
            starts.append( pos + breakgap/2. )

        stops.append(1.)

    def computePlottedRange(self):

        axis.Axis.computePlottedRange(self)

        self.orig_plottedrange = self.plottedrange
        points = self.settings.breakPoints
        self.breakvnum = num = len(points)/2 + 1
        self.breakvlist = [self.plottedrange[0]] + points[:len(points)/2*2] + [
            self.plottedrange[1]]

        # axis values for starting and stopping
        self.breakvstarts = [ self.breakvlist[i*2] for i in xrange(num) ]
        self.breakvstops = [ self.breakvlist[i*2+1] for i in xrange(num) ]

        # compute ticks for each range
        self.minorticklist = []
        self.majorticklist = []
        for i in xrange(self.breakvnum):
            self.plottedrange = [self.breakvstarts[i], self.breakvstops[i]]
            self.computeTicks(allowauto=False)
            self.minorticklist.append(self.minortickscalc)
            self.majorticklist.append(self.majortickscalc)

        self.plottedrange = self.orig_plottedrange

    def _autoMirrorDraw(self, posn, painter):
        """Mirror axis to opposite side of graph if there isn't an
        axis there already."""

        if not self._shouldAutoMirror():
            return

        # swap axis to other side
        s = self.settings
        if s.otherPosition < 0.5:
            otheredge = 1.
        else:
            otheredge = 0.

        # temporarily change position of axis to other side for drawing
        self.updateAxisLocation(posn, otherposition=otheredge)
        if not s.Line.hide:
            self._drawAxisLine(painter)

        for i in xrange(self.breakvnum):
            self.switchBreak(i, posn, otherposition=otheredge)

            # plot coordinates of ticks
            coordticks = self._graphToPlotter(self.majorticklist[i])
            coordminorticks = self._graphToPlotter(self.minorticklist[i])

            if not s.MinorTicks.hide:
                self._drawMinorTicks(painter, coordminorticks)
            if not s.MajorTicks.hide:
                self._drawMajorTicks(painter, coordticks)

        self.switchBreak(None, posn)

    def _axisDraw(self, posn, parentposn, outerbounds, painter, phelper):
        """Main drawing routine of axis."""

        s = self.settings

        # multiplication factor if reflection on the axis is requested
        sign = 1
        if s.direction == 'vertical':
            sign *= -1
        if self.coordReflected:
            sign *= -1

        # keep track of distance from axis
        # text to output
        texttorender = []

        # plot the line along the axis
        if not s.Line.hide:
            self._drawAxisLine(painter)

        max_delta = 0
        for i in xrange(self.breakvnum):
            self.switchBreak(i, posn)
            self.computeTicks(allowauto=False)

            # plot coordinates of ticks
            coordticks = self._graphToPlotter(self.majorticklist[i])
            coordminorticks = self._graphToPlotter(self.minorticklist[i])

            self._delta_axis = 0

            # plot minor ticks
            if not s.MinorTicks.hide:
                self._drawMinorTicks(painter, coordminorticks)

            # plot major ticks
            if not s.MajorTicks.hide:
                self._drawMajorTicks(painter, coordticks)

            # plot tick labels
            suppresstext = self._suppressText(painter, parentposn, outerbounds)
            if not s.TickLabels.hide and not suppresstext:
                self._drawTickLabels(phelper, painter, coordticks, sign,
                                     outerbounds, texttorender)

            # this is the maximum delta of any of the breaks
            max_delta = max(max_delta, self._delta_axis)

        self.switchBreak(None, posn)
        self._delta_axis = max_delta

        # draw an axis label
        if not s.Label.hide and not suppresstext:
            self._drawAxisLabel(painter, sign, outerbounds, texttorender)


        # mirror axis at other side of plot
        if s.autoMirror:
            self._autoMirrorDraw(posn, painter)

        self._drawTextWithoutOverlap(painter, texttorender)

        # make control item for axis
        phelper.setControlGraph(self, [ controlgraph.ControlAxisLine(
                    self, self.settings.direction, self.coordParr1,
                    self.coordParr2, self.coordPerp, posn) ])

# allow the factory to instantiate an image
document.thefactory.register( AxisBroken )
