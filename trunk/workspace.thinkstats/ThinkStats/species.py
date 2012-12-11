"""This file contains code used in "Think Bayes",
by Allen B. Downey, available from greenteapress.com

Copyright 2012 Allen B. Downey
License: GNU GPLv3 http://www.gnu.org/licenses/gpl.html
"""

import thinkbayes

import matplotlib.pyplot as pyplot
import myplot
import numpy

import csv
import math
import random
import sys
import time

formats = ['pdf', 'eps']

class Subject(object):
    """Represents a subject from the belly button study."""

    def __init__(self, code):
        self.code = code
        self.species = []

    def Add(self, species, count):
        """Add a species-count pair.

        species: string species/genus name
        count: int number of individuals
        """
        self.species.append((count, species))

    def Sort(self):
        self.species.sort()        
        
    def GetCounts(self):
        return [count for (count, _) in self.species]


def ReadData(filename='journal.pone.0047712.s001.csv'):
    """Reads a data file and returns a list of Subjects.

    Data from http://www.plosone.org/article/
    info%3Adoi%2F10.1371%2Fjournal.pone.0047712#s4
    """
    fp = open(filename)
    reader = csv.reader(fp)
    header = reader.next()
    
    subject = Subject('')
    subjects = []

    for t in reader:
        code = t[0]
        if code != subject.code:
            subject.Sort()
            subject = Subject(code)
            subjects.append(subject)

        species = t[1]
        count = int(t[2])
        subject.Add(species, count)

    return subjects


def PlotMixture(pmfs, show=False):
    for dist in pmfs.Values():
        xs, ys = dist.Render()
        pyplot.plot(xs, ys, color='blue', alpha=0.2)

    mix = Pmf.MakeMixture(pmfs)
    xs, ys = mix.Render()
    pyplot.plot(xs, ys, color='blue', alpha=0.9, linewidth=2)

    myplot.Save(show=show, clf=False,
                xlabel='prevalence',
                ylabel='prob',
                formats=formats,
                legend=False)


def JitterCurve(curve, dx=0.2, dy=0.3):
    """Adds random noise to the pairs in a curve.

    dx and dy control the amplitude of the noise in each dimension.
    """
    curve = [(x+random.uniform(-dx, dx), 
              y+random.uniform(-dy, dy)) for x, y in curve]
    return curve


def OffsetCurve(curve, i, n, dx=0.3, dy=0.3):
    """Adds random noise to the pairs in a curve.

    i is the index of the curve
    n is the number of curves

    dx and dy control the amplitude of the noise in each dimension.
    """
    xoff = -dx + 2 * dx * i / (n-1)
    yoff = -dy + 2 * dy * i / (n-1)
    curve = [(x+xoff, y+yoff) for x, y in curve]
    return curve


def PlotCurves(curves, root=None, clf=False):
    """Plots a set of curves.

    curves is a list of curves; each curve is a list of (x, y) pairs.
    """
    if root: 
        pyplot.clf()

    n = len(curves)
    for i, curve in enumerate(curves):
        curve = OffsetCurve(curve, i, n)
        xs, ys = zip(*curve)
        pyplot.plot(xs, ys, color='blue', alpha=0.2)

    myplot.Save(root=root,
                clf=clf,
                xlabel='# samples',
                ylabel='# taxa',
                formats=formats,
                legend=False)


class Species(thinkbayes.Suite):
    """Represents hypotheses about the number of species."""
    
    def __init__(self, ns, iterations=1000):
        hypos = [thinkbayes.Dirichlet(n) for n in ns]
        thinkbayes.Suite.__init__(self, hypos)
        self.iterations = iterations

    def Update(self, data):
        """Updates the suite based on the data.

        data: list of observed frequencies
        """
        # call Update in the parent class, which calls Likelihood
        thinkbayes.Suite.Update(self, data)

        # update the next level of the hierarchy
        for hypo in self.Values():
            hypo.Update(data)

    def Likelihood(self, hypo, data):
        """Computes the likelihood of the data under this hypothesis.

        hypo: Dirichlet object
        data: list of observed frequencies
        """
        dirichlet = hypo

        # draw sample Likelihoods from the hypothetical Dirichlet dist
        # and add them up
        like = 0
        for i in range(self.iterations):
            like += dirichlet.Likelihood(data)

        # correct for the number of ways the observed species
        # might as been chosen from all species
        m = len(data)
        like *= thinkbayes.BinomialCoef(dirichlet.n, m)

        return like

    def DistOfN(self):
        """Computes the distribution of n."""
        pmf = thinkbayes.Pmf()
        for hypo, prob in self.Items():
            pmf.Set(hypo.n, prob)
        return pmf
        

class Species2(object):
    """Represents hypotheses about the number of species.

    Combines two layers of the hierarchy into one object.

    ns and probs represent the distribution of N

    params represents the parameters of the Dirichlet distributions
    """
    
    def __init__(self, ns, iterations=1000):
        self.ns = ns
        self.probs = numpy.ones(len(ns), dtype=numpy.double)
        self.params = numpy.ones(self.ns[-1], dtype=numpy.int)
        self.iterations = iterations

    def Update(self, data):
        like = numpy.zeros(len(self.ns), dtype=numpy.double)
        for i in range(1000):
            like += self.SampleLikelihood(data)

        self.probs *= like
        self.probs /= self.probs.sum()

        m = len(data)
        self.params[:m] += data

    def SampleLikelihood(self, data):
        gammas = numpy.random.gamma(self.params)

        m = len(data)
        row = gammas[:m]
        col = numpy.cumsum(gammas)

        log_likes = []
        for n in self.ns:
            ps = row / col[n-1]
            terms = numpy.log(ps) * data
            log_like = terms.sum()
            log_likes.append(log_like)

        log_likes -= numpy.max(log_likes)
        likes = numpy.exp(log_likes)

        coefs = [thinkbayes.BinomialCoef(n, m) for n in self.ns]
        likes *= coefs

        return likes

    def DistOfN(self):
        """Computes the distribution of n."""
        pmf = thinkbayes.MakePmfFromDict(dict(zip(self.ns, self.probs)))
        return pmf

    def MarginalBeta(self, n, index):
        alpha0 = self.params[:n].sum()
        alpha = self.params[index]
        return thinkbayes.Beta(alpha, alpha0-alpha)

    def DistOfPrevalence(self, index):
        pmfs = thinkbayes.Pmf()

        for n, prob in zip(self.ns, self.probs):
            beta = self.MarginalBeta(n, index)
            pmf = beta.MakePmf()
            pmfs.Set(pmf, prob)

        return thinkbayes.MakeMixture(pmfs)
        

class Species3(Species2):
    """Represents hypotheses about the number of species."""
    
    def Update(self, data):
        """Updates the suite based on the data.

        data: list of observations
        """
        # sample the likelihoods and add them up
        like = numpy.zeros(len(self.ns), dtype=numpy.double)
        for i in range(self.iterations):
            like += self.SampleLikelihood(data)

        self.probs *= like
        self.probs /= self.probs.sum()

        m = len(data)
        self.params[:m] += data

    def SampleLikelihood(self, data):
        """Computes the likelihood of the data under all hypotheses.

        data: list of observations
        """
        # get a random sample
        gammas = numpy.random.gamma(self.params)

        # row is just the first m elements of gammas
        m = len(data)
        row = gammas[:m]

        # col is the cumulative sum of gammas
        col = numpy.cumsum(gammas)[self.ns[0]-1:]

        # each row of the array is a set of ps, normalized
        # for each hypothetical value of n
        array = row / col[:, numpy.newaxis]

        # computing the multinomial PDF under a log transform
        # take the log of the ps and multiply by the data
        terms = numpy.log(array) * data

        # add up the rows
        log_likes = terms.sum(axis=1)

        # before exponentiating, scale into a reasonable range
        log_likes -= numpy.max(log_likes)
        likes = numpy.exp(log_likes)

        # correct for the number of ways we could see m species
        # out of a possible n
        coefs = [thinkbayes.BinomialCoef(n, m) for n in self.ns]
        likes *= coefs

        return likes


class Species4(Species):
    """Represents hypotheses about the number of species."""
    
    def Update(self, data):
        """Updates the suite based on the data.

        data: list of observed frequencies
        """
        m = len(data)

        # loop through the species and update one at a time
        for i in range(m):
            one = numpy.zeros(i+1)
            one[i] = data[i]
            
            # call the parent class
            Species.Update(self, one)

    def Likelihood(self, hypo, data):
        """Computes the likelihood of the data under this hypothesis.

        Note: this only works correctly if we update one species at a time.

        hypo: Dirichlet object
        data: list of observed frequencies
        """
        dirichlet = hypo
        like = 0
        for i in range(self.iterations):
            like += dirichlet.Likelihood(data)

        # correct for the number of unseen species the new one
        # could have been
        m = len(data)
        num_unseen = dirichlet.n - m + 1
        like *= num_unseen

        return like


class Species5(Species2):
    """Represents hypotheses about the number of species.

    Combines two laters of the hierarchy into one object.

    ns and probs represent the distribution of N

    params represents the parameters of the Dirichlet distributions
    """
    
    def Update(self, data):
        """Updates the suite based on the data.

        data: list of observed frequencies
        """
        # loop through the species and update one at a time
        m = len(data)
        for i in range(m):
            self.UpdateOne(i+1, data[i])
            self.params[i] += data[i]

    def UpdateOne(self, m, count):
        """Updates the suite based on the data.

        Evaluates the likelihood for all values of n.

        m: which species was observed
        count: how many were observed
        """
        # sample the likelihoods and add them up
        likes = numpy.zeros(len(self.ns), dtype=numpy.double)
        for i in range(self.iterations):
            likes += self.SampleLikelihood(m, count)

        # correct for the number of unseen species the new one
        # could have been
        unseen_species = [n-m+1 for n in self.ns]
        likes *= unseen_species

        # multiply the priors by the likelihoods and renormalize
        self.probs *= likes
        self.probs /= self.probs.sum()

    def SampleLikelihood(self, m, count):
        """Computes the likelihood of the data under all hypotheses.

        m: which species was observed
        count: how many were observed
        """
        # get a random sample of p
        gammas = numpy.random.gamma(self.params)

        # sums is the cumulative sum of p, for each value of n
        sums = numpy.cumsum(gammas)[self.ns[0]-1:]

        # get p for the mth species, for each value of n
        ps = gammas[m-1] / sums
        log_likes = numpy.log(ps) * count

        # before exponentiating, scale into a reasonable range
        log_likes -= numpy.max(log_likes)
        likes = numpy.exp(log_likes)

        return likes


class Species6(Species):
    """Represents hypotheses about the number of species."""
    
    def __init__(self, ns):
        hypos = [OversampledDirichlet(n) for n in ns]
        thinkbayes.Suite.__init__(self, hypos)

    def Update(self, data):
        """Updates the suite based on the data.

        data: list of observed frequencies
        """
        for hypo in self.Values():
            hypo.Peek(data)

        # call Update in the parent class, which calls Likelihood
        thinkbayes.Suite.Update(self, data)

        for hypo in self.Values():
            hypo.Update(data)


class OversampledDirichlet(thinkbayes.Dirichlet):
    """Provides oversampled random selection from a Dirichlet distribution.

    By peeking at the posterior distribution, we can see where the
    non-negligible mass will be, then restrict the uniform prior to
    just this range.

    This version doesn't provide Update, because it only handles the
    special case when the prior distribution is still uniform.

    """
    
    def Likelihood(self, data):
        like = thinkbayes.Dirichlet.Likelihood(self, data)
        return like * self.weight

    def Peek(self, data):
        """Figures out the bounds in the posterior distribution that
        contain non-negligible mass.
        """
        m = len(data)
        priors = self.MakeConditionals(self.params)
        pmfs = [prior.MakePmf() for prior in priors]
        self.conditionals = pmfs

        self.TrimMarginals(data)

    def TrimMarginals(self, data):
        m = len(data)
        params = numpy.copy(self.params)
        params[:m] += data

        posteriors = self.MakeMarginals(params)
        cdfs = [beta.MakeCdf() for beta in posteriors]

        lows = [cdf.Percentile(2) for cdf in cdfs]
        highs = [cdf.Percentile(98) for cdf in cdfs]
        
        p_hit = 1
        pmfs = self.conditionals
        for pmf, low, high in zip(pmfs, lows, highs):
            mass = self.TrimMarginal(pmf, low, high)
            print self.n, low, high, mass
            p_hit *= mass

        self.weight = p_hit
        print self.n, self.weight
        conditionals = [thinkbayes.MakeCdfFromPmf(pmf) for pmf in pmfs]
        self.conditionals = conditionals

    def TrimMarginal(self, pmf, low, high):
        for val in pmf.Values():
            if val < low or val > high:
                pmf.Remove(val)
        return pmf.Normalize()

    def MakeMarginals(self, params):
        total = sum(params)
        betas = [thinkbayes.Beta(x, total-x) for x in params]
        return betas

    def MakeConditionals(self, params):
        total = sum(params)
        betas = []
        for x in params[:-1]:
            total -= x
            beta = thinkbayes.Beta(x, total)
            betas.append(beta)
        return betas

    def Random(self):
        """Generates a random variate from this distribution.

        Returns: normalized array of probabilities
        """
        fraction = 1.0
        ps = numpy.zeros(self.n)

        for i, cond in enumerate(self.conditionals):
            p = cond.Random()
            ps[i] = p * fraction
            fraction *= 1-p

        ps[-1] = fraction
        return ps


def MakePosterior(constructor, data, ns, iterations=1000):
    """Makes a suite, updates it and returns the PMF of N.

    Prints the elapsed time.

    data: observed species and their counts
    ns: sequence of hypothetical ns
    iterations: how many samples to draw
    """
    suite = constructor(ns, iterations)

    print constructor.__name__
    start = time.time()
    suite.Update(data)
    end = time.time()

    print end-start

    pmf = suite.DistOfN()
    return pmf


def PlotAllVersions():
    """Makes a graph of posterior distributions of N."""
    data = [1, 2, 3]
    m = len(data)
    n = 20
    ns = range(m, n)

    for constructor in [Species, Species2, Species3, Species4, Species5]:
        pmf = MakePosterior(constructor, data, ns)
        pmf.name = '%s' % (constructor.__name__)
        myplot.Pmf(pmf)

    myplot.Show()
    return

    myplot.Save(root='species3',
                xlabel='Number of species',
                ylabel='Prob')


def PlotMedium():
    """Makes a graph of posterior distributions of N."""
    data = [1, 1, 1, 1, 2, 3, 5, 9]
    m = len(data)
    n = 20
    ns = range(m, n)

    for constructor in [Species, Species2, Species3, Species4, Species5]:
        pmf = MakePosterior(constructor, data, ns)
        pmf.name = '%s' % (constructor.__name__)
        myplot.Pmf(pmf)

    myplot.Show()


def CompareHierarchicalExample():
    """Makes a graph of posterior distributions of N."""
    data = [3, 2, 1]
    m = len(data)
    n = 30
    ns = range(m, n)

    constructors = [Species, Species5]
    iterations = [1000, 100]

    for constructor, iterations in zip(constructors, iterations):
        pmf = MakePosterior(constructor, data, ns, iterations)
        pmf.name = '%s' % (constructor.__name__)
        myplot.Pmf(pmf)

    myplot.Show()


def SimpleDirichletExample():
    """Makes a plot showing posterior distributions for three species.

    This is the case where we know there are exactly three species.
    """
    names = ['lions',  'tigers', 'bears']
    data = [3, 2, 1]

    dirichlet = thinkbayes.Dirichlet(3)
    for i in range(3):
        beta = dirichlet.MarginalBeta(i)
        print 'mean', names[i], beta.Mean()

    dirichlet.Update(data)
    for i in range(3):
        beta = dirichlet.MarginalBeta(i)
        print 'mean', names[i], beta.Mean()

        pmf = beta.MakePmf(name=names[i])
        myplot.Pmf(pmf)

    myplot.Save(root='species1',
                xlabel='Prevalence',
                ylabel='Prob',
                formats=formats,
                )


def HierarchicalExample():
    """Shows the posterior distribution of n for lions, tigers and bears.
    """
    ns = range(3, 30)
    suite = Species(ns, iterations=8000)

    data = [3, 2, 1]
    suite.Update(data)

    pmf = suite.DistOfN()
    myplot.Pmf(pmf)
    myplot.Save(root='species2',
                xlabel='Number of species',
                ylabel='Prob',
                formats=formats,
                )


def TestOversampledDirichlet():
    dirichlet = OversampledDirichlet(3)
    dirichlet.Peek([3, 2, 1])
    sample = dirichlet.Random()
    print sample


def ProcessSubject(counts):

    m = len(counts)
    n = int(1.5 * m)
    ns = range(m, n)
    suite = Species5(ns, iterations=300)

    start = time.time()    
    suite.Update(counts)
    end = time.time()
    print 'time', end-start

    pmf = suite.DistOfN()
    return suite, pmf


def ProcessSubjects(indices):
    subjects = ReadData()
    pmfs = []
    for index in indices:
        subject = subjects[index]
        counts = subject.GetCounts()
        print subject.code, len(counts)
        print counts

        suite, pmf = ProcessSubject(counts)
        pmf.name = subject.code
        myplot.Pmf(pmf)

        pmfs.append(pmf)

    print 'ProbGreater', thinkbayes.PmfProbGreater(pmfs[0], pmfs[1])
    print 'ProbLess', thinkbayes.PmfProbLess(pmfs[0], pmfs[1])

    myplot.Save(root='species4',
                xlabel='Number of species',
                ylabel='Prob',
                formats=formats,
                )


def MakeFigures(subject):
    counts = subject.GetCounts()
    m = len(counts)
    print counts

    suite, pmf = ProcessSubject(counts)
    pmf.name = subject.code

    myplot.Clf()
    myplot.Pmf(pmf)
    root = 'species.ndist.%s' % subject.code
    myplot.Save(root=root,
                xlabel='Number of species',
                ylabel='Prob',
                formats=formats,
                )

    myplot.Clf()
    for index in range(m-1, m-6, -1):
        PlotPrevalence(subject, suite, index, counts[index])

    root = 'species.prev.%s' % subject.code
    myplot.Save(root=root,
                xlabel='Prevalence',
                ylabel='Prob',
                formats=formats,
                axis=[0, 0.3, 0, 1]
                )

def PlotPrevalence(subject, suite, index, count):
    pmf = suite.DistOfPrevalence(index)
    pmf.name = str(count)
    cdf = thinkbayes.MakeCdfFromPmf(pmf)
    #myplot.Pmf(pmf)
    myplot.Cdf(cdf)


def SummarizeData():
    subjects = ReadData()

    for subject in subjects:
        counts = subject.GetCounts()
        print subject.code, len(counts)

def main(script, *args):
    subjects = ReadData()
    MakeFigures(subjects[4])
    return

    ProcessSubjects([4])
    return

    SimpleDirichletExample()
    return

    SummarizeData()
    return

    CompareHierarchicalExample()
    return

    HierarchicalExample()
    return

    PlotMedium()
    return

    random.seed(17)
    PlotAllVersions()
    return

    pmf = MakePosterior(Species)
    myplot.Pmf(pmf)
    myplot.Show()
    return


    random.seed(17)
    p = dirichlet.Likelihood(data)
    print p

    random.seed(17)
    lp = dirichlet.LogLikelihood(data)
    print lp, math.exp(lp)

    return


    xs = []
    for i in range(ITERATIONS):
        x = dirichlet.Random()
        xs.append(x)

    cols = zip(*xs)
    for col in cols:
        cdf = thinkbayes.MakeCdfFromList(col)
        myplot.Cdf(cdf)

    myplot.Show()
    return


    beta = thinkbayes.Beta()
    beta.Update((140, 110))
    print beta.Mean()

    pmf = beta.MakePmf(101)
    myplot.Pmf(pmf)
    myplot.Show()
    return


    flag = int(flag)

    d = {
        0: [1],
        1: [9, 6],
        2: [8, 3],
        3: [11, 4, 2],
        4: [3, 2, 2, 1],
        5: [7, 3, 1, 1, 1, 1],
        6: [7, 2, 1],
        7: [4, 3, 9, 1, 1],
        8: [14, 5, 2, 2, 1,1,1,1,1,1],
        9: [11, 2, 1,1],
        }
    freqs = d[flag]

    sample = MakeSample(freqs)
    meta = MakeMeta(sample, n=31)

    meta.Print()

    root='rare%d' % flag
    MakeFigures(root, sample, meta)


if __name__ == '__main__':
    random.seed(17)

    profile = False
    if profile:
        import cProfile
        cProfile.run('main(*sys.argv)')
    else:
        main(*sys.argv)