# -*- coding: utf-8 -*-
# Copyright (C) Scott Coughlin (2017-)
#
# This file is part of the XPypeline python package.
#
# hveto is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# hveto is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with hveto.  If not, see <http://www.gnu.org/licenses/>.

# ---- Import standard modules to the python path.
import numpy as np
from collections import OrderedDict
from gwpy.frequencyseries import FrequencySeries
import copy

__author__ = 'Scott Coughlin <scott.coughlin@ligo.org>'
__all__ = ['XFrequencySeriesDict', 'convert_to_dominant_polarization_frame']

class XFrequencySeriesDict(OrderedDict):
    def project_onto_antenna_patterns(self, antenna_responses,
                                      to_dominant_polarization_frame=False):
        """Shift timeseries by assosciated time delay

            Parameters
            ----------
            antenna_responses : `dict`
                key-wise pair of
                OrderedDict([('f_plus',
                              OrderedDict([('H1', array([-0.02424373])),
                                           ('L1', array([0.3089992]))])),
                             ('f_cross',
                              OrderedDict([('H1', array([-0.5677237])),
                                           ('L1', array([0.52872644]))])),
                             ('f_scalar',
                              OrderedDict([('H1', array([0.12427263])),
                                           ('L1', array([-0.30016348]))]))])

            to_dominant_polarization_frame " `bool`
                This boolean determines whether or not to calculate the
                relevant angle parameter that would project the data into
                the orthogonal cross plus polarization frame.
        """
        antenna_response_asds = OrderedDict()
        for pattern, responses in antenna_responses.items():
            antenna_weighted_asds = XFrequencySeriesDict()
            for det, asd in self.items():
                abbr_det = det.split(':')[0]
                antenna_weighted_asds[det] = responses[abbr_det] / asd

            antenna_response_asds[pattern] = antenna_weighted_asds


        if to_dominant_polarization_frame:
            wfp = antenna_response_asds['f_plus'].to_array()
            wfc = antenna_response_asds['f_cross'].to_array()
            FpDP, FcDP, psi = convert_to_dominant_polarization_frame(wfp, wfc)
            tmp = copy.deepcopy(antenna_response_asds)
            for detidx, idet in enumerate(tmp['f_plus']):
                antenna_response_asds['f_plus'][idet] = (
                    np.cos(2*psi[:,detidx]) * tmp['f_plus'][idet] +
                    np.sin(2*psi[:,detidx]) * tmp['f_cross'][idet]
                    )
                antenna_response_asds['f_cross'][idet] = (
                    -np.sin(2*psi[:,detidx]) * tmp['f_plus'][idet] +
                    np.cos(2*psi[:,detidx]) * tmp['f_cross'][idet]
                    )
            

        return antenna_response_asds


    def to_array(self):
        """Convert to number of freq bins by number of detctors array
        """
        number_of_frequencies = list(self.values())[0].size
        number_of_detectors = len(self)
        array = np.zeros([number_of_frequencies, number_of_detectors])
        for idx, asd in enumerate(self.values()):
            array[:, idx] = asd

        return array


    def to_m_ab(self):
        """Matrix M_AB components.

           These are the dot products of wFp, with
           themselves and each other, for each frequency, computed in
           the DP frame.
        """
        return np.sum(self.to_array()**2, 1)


    def slice_frequencies(self, indices):
        """select a subset of frequencies from XFrequencySeriesDict

           Parameters:
               indices (array):
                   an array of indexs to select from all elements
                   of `XFrequencySeriesDict`

           Returns:
               `XFrequencySeriesDict`
        """
        asd_subset = XFrequencySeriesDict()
        for det, asd in self.items():
            asd_subset[det] = self[det][indices]

        return asd_subset


def convert_to_dominant_polarization_frame(Fp, Fc):
    """Take in stream of fplus and ≈f_cross and convert to DPF

       DPF is the Dominant Polarization Frame

        Parameters
        ----------
            Fp : `float`
            Fc :  `float`
    """
    # ---- Compute rotation needed to reach DP frame.
    psi = np.zeros([len(Fp), 1])
    psi[:, 0] = 1/4*np.arctan(2*(np.sum(Fp*Fc, 1))/(
                    np.sum(Fp*Fp, 1)-np.sum(Fc*Fc, 1))
                    )
    psi = psi.repeat(Fp.shape[1], 1)

    # ---- Rotate to DP frame.
    FpDP = np.cos(2*psi)*Fp + np.sin(2*psi)*Fc
    FcDP = -np.sin(2*psi)*Fp + np.cos(2*psi)*Fc

    # ---- Further rotate polarization by pi/4 if |Fp|<|Fc|.
    swapindex = (FpDP**2).sum(1) < (FcDP**2).sum(1)
    FpDP[swapindex, :] = FcDP[swapindex, :]
    FcDP[swapindex, :] = -FpDP[swapindex, :]
    psi[swapindex, :] = psi[swapindex, :] + np.pi/4

    return FpDP, FcDP, psi
