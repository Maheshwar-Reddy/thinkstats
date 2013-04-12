"""This file contains code for use with "Think Bayes",
by Allen B. Downey, available from greenteapress.com

Copyright 2012 Allen B. Downey
License: GNU GPLv3 http://www.gnu.org/licenses/gpl.html
"""

import thinkbayes
import myplot

from thinkbayes import Pmf, Percentile
from dice import Dice


class Train(Dice):
    """The likelihood function for the train problem is the same as
    for the Dice problem."""


class Train2(Dice):
    """The likelihood function for the train problem is the same as
    for the Dice problem."""

    def __init__(self, hypos, alpha=1.0):
        """Initializes the hypotheses with a power law distribution.

        hypos: sequence of hypotheses
        """
        Pmf.__init__(self)
        for hypo in hypos:
            self.Set(hypo, hypo**(-alpha))
        self.Normalize()


def MakePosterior(high, dataset, constructor):
    """Makes and updates a Suite.

    high: upper bound on the range of hypotheses
    dataset: observed data to use for the update

    Returns: posterior Suite
    """
    hypos = xrange(1, high+1)
    suite = constructor(hypos)
    suite.name = str(high)

    for data in dataset:
        suite.Update(data)

    return suite


def ComparePriors():
    dataset = [60]
    high = 1000

    myplot.Clf()
    myplot.PrePlot(num=2)

    constructors = [Train, Train2]
    labels = ['uniform', 'power law']

    for constructor, label in zip(constructors, labels):
        suite = MakePosterior(high, dataset, constructor)
        suite.name = label
        myplot.Pmf(suite)

    myplot.Save(root='train4',
                xlabel='Number of trains',
                ylabel='Probability')

def main():
    ComparePriors()

    dataset = [30, 60, 90]

    myplot.Clf()
    myplot.PrePlot(num=3)

    for high in [500, 1000, 2000]:
        suite = MakePosterior(high, dataset, Train2)
        print high, suite.Mean()

    myplot.Save(root='train3',
                xlabel='Number of trains',
                ylabel='Probability')

    interval = Percentile(suite, 5), Percentile(suite, 95)
    print interval

    cdf = thinkbayes.MakeCdfFromPmf(suite)
    interval = cdf.Percentile(5), cdf.Percentile(95)
    print interval

if __name__ == '__main__':
    main()