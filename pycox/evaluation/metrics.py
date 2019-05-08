'''
Some relevant metrics
'''
import warnings

import numpy as np
import scipy
import pandas as pd
import numba

from lifelines.utils import concordance_index
from lifelines import KaplanMeierFitter

def brier_score(times, prob_alive, durations, events):
    '''Compute the brier scores (for survival) at given times.

    For a specification on brier scores for survival data see e.g.:
    "Assessment of evaluation criteria for survival prediction from
    genomic data" by Bovelstad and Borgan.

    Parameters:
        times: Number or iterable with times where to compute the brier scores.
        prob_alive: Numpy array [len(times), len(durations)] with the estimated probabilities
            of each individual to be alive at each time in `times`. Each row represets
            a time in input array `times`.
        durations: Numpy array with time of events.
        events: Boolean numpy array indecating if dead/censored (True/False).

    Returns:
        Numpy array with brier scores.
    '''
    if not hasattr(times, '__iter__'):
        times = [times]
    assert prob_alive.__class__ is np.ndarray, 'Need numpy array'
    assert prob_alive.shape == (len(times), len(durations)),\
        'Need prob_alive to have dims [len(times), len(durations)].'
    kmf_censor = KaplanMeierFitter()
    kmf_censor.fit(durations, 1-events)
    # km_censor_at_durations = kmf_censor.predict(durations)
    km_censor_at_durations = kmf_censor.survival_function_.loc[durations].values.flatten()
    km_censor_at_times = kmf_censor.predict(times)

    def compute_score(time_, km_censor_at_time, prob_alive_):
        died = ((durations <= time_) & (events == True))
        survived = (durations > time_)
        event_part = (prob_alive_**2)[died] / km_censor_at_durations[died]
        survived_part = ((1 - prob_alive_)**2)[survived] / km_censor_at_time
        return (np.sum(event_part) + np.sum(survived_part)) / len(durations)

    b_scores = [compute_score(time_, km, pa)
                for time_, km, pa in zip(times, km_censor_at_times, prob_alive)]
    return np.array(b_scores)

def integrated_brier_score_numpy(times_grid, prob_alive, durations, events):
    '''Compute the integrated brier score (for survival).
    This funcion takes pre-computed probabilities, while the function integrated_brier_score
    takes a function and a grid instead.

    For a specification on brier scores for survival data see e.g.:
    "Assessment of evaluation criteria for survival prediction from
    genomic data" by Bovelstad and Borgan.

    Parameters:
        times_grid: Iterable with times where to compute the brier scores.
            Needs to be strictly increasing.
        prob_alive: Numpy array [len(times_grid), len(durations)] with the estimated
            probabilities of each individual to be alive at each time in `times_grid`.
            Each row represets a time in input array `times_grid`.
        durations: Numpy array with time of events.
        events: Boolean numpy array indecating if dead/censored (True/False).
    '''
    assert pd.Series(times_grid).is_monotonic_increasing,\
        'Need monotonic increasing times_grid.'
    b_scores = brier_score(times_grid, prob_alive, durations, events)
    is_finite = np.isfinite(b_scores)
    b_scores = b_scores[is_finite]
    times_grid = times_grid[is_finite]
    integral = scipy.integrate.simps(b_scores, times_grid)
    return integral / (times_grid[-1] - times_grid[0])

def integrated_brier_score(prob_alive_func, durations, events,
                           times_grid=None, n_grid_points=100):
    '''Compute the integrated brier score (for survival).
    This takes a function and a grid, while the function integrated_brier_score_numpy
    takes pre-computed probabilities instead.

    For a specification on brier scores for survival data see e.g.:
    "Assessment of evaluation criteria for survival prediction from
    genomic data" by Bovelstad and Borgan.

    Parameters:
        prob_alive_func: Function that takes an array of times and returns
            a matrix [len(times_grid), len(durations)] with survival probabilities.
        durations: Numpy array with time of events.
        events: Boolean numpy array indecating if dead/censored (True/False).
        times_grid: Specified time grid for integration. If None: use equidistant between
            smallest and largest value times of durations.
        n_grid_points: Only apply if grid is None. Gives number of grid poinst used
            in equidistant grid.
    '''
    if times_grid is None:
        times_grid = np.linspace(durations.min(), durations.max(), n_grid_points)
    prob_alive = prob_alive_func(times_grid)
    return integrated_brier_score_numpy(times_grid, prob_alive, durations, events)

def binomial_log_likelihood(times, prob_alive, durations, events, eps=1e-7):
    '''Compute the binomial log-likelihood for survival at given times.

    We compute binomial log-likelihood weighted by the inverse censoring distribution.
    This is the same weighting scheeme as for the brier score.

    Parameters:
        times: Number or iterable with times where to compute the brier scores.
        prob_alive: Numpy array [len(times), len(durations)] with the estimated probabilities
            of each individual to be alive at each time in `times`. Each row represets
            a time in input array `times`.
        durations: Numpy array with time of events.
        events: Boolean numpy array indecating if dead/censored (True/False).
        eps: Clip prob_alive at (eps, 1-eps).

    Returns:
        Numpy array with brier scores.
    '''
    if not hasattr(times, '__iter__'):
        times = [times]
    assert prob_alive.__class__ is np.ndarray, 'Need numpy array'
    assert prob_alive.shape == (len(times), len(durations)),\
        'Need prob_alive to have dims [len(times), len(durations)].'
    kmf_censor = KaplanMeierFitter()
    kmf_censor.fit(durations, 1-events)
    km_censor_at_durations = kmf_censor.survival_function_.loc[durations].values.flatten()
    km_censor_at_times = kmf_censor.predict(times)

    prob_alive = np.clip(prob_alive, eps, 1-eps)

    def compute_score(time_, km_censor_at_time, prob_alive_):
        died = ((durations <= time_) & (events == True))
        survived = (durations > time_)
        event_part = np.log(1 - prob_alive_[died]) / km_censor_at_durations[died]
        survived_part = np.log(prob_alive_[survived]) / km_censor_at_time
        return (np.sum(event_part) + np.sum(survived_part)) / len(durations)

    scores = [compute_score(time_, km, pa)
              for time_, km, pa in zip(times, km_censor_at_times, prob_alive)]
    return np.array(scores)

def integrated_binomial_log_likelihood_numpy(times_grid, prob_alive, durations, events):
    '''Compute the integrated brier score (for survival).
    This funcion takes pre-computed probabilities, while the function integrated_brier_score
    takes a function and a grid instead.

    For a specification on brier scores for survival data see e.g.:
    "Assessment of evaluation criteria for survival prediction from
    genomic data" by Bovelstad and Borgan.

    Parameters:
        times_grid: Iterable with times where to compute the brier scores.
            Needs to be strictly increasing.
        prob_alive: Numpy array [len(times_grid), len(durations)] with the estimated
            probabilities of each individual to be alive at each time in `times_grid`.
            Each row represets a time in input array `times_grid`.
        durations: Numpy array with time of events.
        events: Boolean numpy array indecating if dead/censored (True/False).
    '''
    assert pd.Series(times_grid).is_monotonic_increasing,\
        'Need monotonic increasing times_grid.'
    scores = binomial_log_likelihood(times_grid, prob_alive, durations, events)
    is_finite = np.isfinite(scores)
    scores = scores[is_finite]
    times_grid = times_grid[is_finite]
    integral = scipy.integrate.simps(scores, times_grid)
    return integral / (times_grid[-1] - times_grid[0])

@numba.jit(nopython=True)
def _is_comparable(t_i, t_j, d_i, d_j):
    #return ((t_i < t_j) & d_i) | ((t_i == t_j) & d_i & (d_j == 0))  # original
    return ((t_i < t_j) & d_i) | ((t_i == t_j) & (d_i | d_j))  # modified

@numba.jit(nopython=True)
def _is_comparable_antolini(t_i, t_j, d_i, d_j):
    return ((t_i < t_j) & d_i) | ((t_i == t_j) & d_i & (d_j == 0))

@numba.jit(nopython=True)
def _is_concordant(s_i, s_j, t_i, t_j, d_i, d_j):
    """ In the paper by Antolini et al. (2005), they only consider the part below
    marked as '# original'. We have added the other parts to ensure KM gives 0.5.
    """
    # return (s_i < s_j) & _is_comparable(t_i, t_j, d_i, d_j)  # original (with original '_is_comparable')
    conc = 0.
    if t_i < t_j:
        conc = (s_i < s_j) + (s_i == s_j) * 0.5
    elif t_i == t_j: 
        if d_i & d_j:
            conc = 1. - (s_i != s_j) * 0.5
        elif d_i:
            conc = (s_i < s_j) + (s_i == s_j) * 0.5  # different from RSF paper.
        elif d_j:
            conc = (s_i > s_j) + (s_i == s_j) * 0.5  # different from RSF paper.
    return conc * _is_comparable(t_i, t_j, d_i, d_j)

@numba.jit(nopython=True)
def _is_concordant_antolini(s_i, s_j, t_i, t_j, d_i, d_j):
    return (s_i < s_j) & _is_comparable_antolini(t_i, t_j, d_i, d_j)

@numba.jit(nopython=True, parallel=True)
def _sum_comparable(t, d, is_comparable_func):
    n = t.shape[0]
    count = 0.
    for i in numba.prange(n):
        for j in range(n):
            # count += _is_comparable(t[i], t[j], d[i], d[j])
            if j != i:
                count += is_comparable_func(t[i], t[j], d[i], d[j])
    return count

@numba.jit(nopython=True, parallel=True)
def _sum_concordant(s, t, d):
    n = len(t)
    count = 0.
    for i in numba.prange(n):
        for j in range(n):
            # count += _is_concordant(s[i, i], s[i, j], t[i], t[j], d[i], d[j])
            if j != i:
                count += _is_concordant(s[i, i], s[i, j], t[i], t[j], d[i], d[j])
    return count

@numba.jit(nopython=True, parallel=True)
def _sum_concordant_disc(s, t, d, s_idx, is_concordant_func):
    n = len(t)
    count = 0
    for i in numba.prange(n):
        idx = s_idx[i]
        for j in range(n):
            # count += _is_concordant(s[idx, i], s[idx, j], t[i], t[j], d[i], d[j])
            if j != i:
                count += is_concordant_func(s[idx, i], s[idx, j], t[i], t[j], d[i], d[j])
    return count

def concordance_td(durations, events, surv, surv_idx, method='adj_antolini'):
    """Time dependent concorance index from
    Antolini, L.; Boracchi, P.; and Biganzoli, E. 2005. A timedependent discrimination
    index for survival data. Statistics in Medicine 24:3927–3944.

    If 'method' is 'antolini', the concordance from Antolini et al. is computed.
    
    If 'method' is 'adj_antolini' (default) we have made a small modifications
    for ties in predictions and event times.
    We have followed step 3. in Sec 5.1. in Random Survial Forests paper, except for the last
    point with "T_i = T_j, but not both are deaths", as that doesn't make much sense.
    See '_is_concordant'.

    Arguments:
        durations {np.array[n]} -- Event times (or censoring times.)
        events {np.array[n]} -- Event indicators (0 is censoring).
        surv {np.array[n_times, n]} -- Survival function (each row is a duraratoin, and each col
            is an individual).
        surv_idx {np.array[n_test]} -- Mapping of survival_func s.t. 'surv_idx[i]' gives index in
            'surv' corresponding to the event time of individual 'i'.

    Keyword Arguments:
        method {str} -- Type of c-index 'antolini' or 'adj_antolini' (default {'adj_antolini'}).

    Returns:
        float -- Time dependent concordance index.
    """
    if np.isfortran(surv):
        surv = np.array(surv, order='C')
    if surv.shape[0] > surv.shape[1]:
        warnings.warn(f"consider using 'concordanace_td' when 'surv' has more rows than cols.")
    assert durations.shape[0] == surv.shape[1] == surv_idx.shape[0] == events.shape[0]
    assert type(durations) is type(events) is type(surv) is type(surv_idx) is np.ndarray
    if events.dtype in ('float', 'float32'):
        events = events.astype('int32')
    if method == 'adj_antolini':
        is_concordant = _is_concordant
        is_comparable = _is_comparable
        return (_sum_concordant_disc(surv, durations, events, surv_idx, is_concordant) /
                _sum_comparable(durations, events, is_comparable))
    elif method == 'antolini':
        is_concordant = _is_concordant_antolini
        is_comparable = _is_comparable_antolini
        return (_sum_concordant_disc(surv, durations, events, surv_idx, is_concordant) /
                _sum_comparable(durations, events, is_comparable))
    return ValueError(f"Need 'method' to be e.g. 'antolini', got '{method}'.")

concordance_td_disc = concordance_td # legacy

def partial_log_likelihood_ph(log_partial_hazards, durations, events, mean=True):
    """Partial log-likelihood for PH models.
    
    Arguments:
        log_partial_hazards {np.array} -- Log partial hazards (e.g. x^T beta).
        durations {np.array} -- Durations.
        events {np.array} -- Events.
    
    Keyword Arguments:
        mean {bool} -- Return the mean. (default: {True})
    
    Returns:
        pd.Series or float -- partial log-likelihood or mean.
    """

    df = pd.DataFrame(dict(duration=durations, event=events, lph=log_partial_hazards))
    pll = (df
           .sort_values('duration', ascending=False)
           .assign(cum_ph=(lambda x: x['lph']
                            .pipe(np.exp)
                            .cumsum()
                            .groupby(x['duration'])
                            .transform('max')))
           .loc[lambda x: x['event'] == 1]
           .assign(pll=lambda x: x['lph'] - np.log(x['cum_ph']))
           ['pll'])
    if mean:
        return pll.mean()
    return pll