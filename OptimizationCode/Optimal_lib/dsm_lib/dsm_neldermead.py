# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#  Copyright [2021] Optimal Control Suite
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

from OptimizationCode.Optimal_lib.dsm_lib.DirectSearchMethod  import DirectSearchMethod
from OptimizationCode.Optimal_lib.dsm_lib.NelderMeadStoppingCriteria import NelderMeadStoppingCriteria as NMSC

import numpy as np


class dsm_neldermead(DirectSearchMethod):
    """

    """

    def __init__(self, stp_criteria, dsm_options):
        """

        Parameters
        ----------
        stp_criteria
        dsm_options
        """
        super().__init__()
        # Active the parallelization for the firsts evaluations
        self.is_parallelized = dsm_options.setdefault("parallelization", False)
        self.is_adaptive = dsm_options.setdefault("is_adaptive", False)
        print(str(self.is_adaptive))
        # Stopping criteria object
        self.sc_obj = NMSC(stp_criteria)

    def run_dsm(self, func, x0, args=(), initial_simplex=None, callback=None, max_iterations_number=None):
        """

        Parameters
        ----------
        max_iterations_number
        func
        x0
        initial_simplex
        args
        callback

        Returns
        -------

        """

        # Creation of the communication function for the Optimizer object
        fcalls, func = self._get_wrapper(args, func)
        # The rmode is the way the function evaluation is carried out.
        rmode = "DumpEval"

        # Set to false is_converged
        self.sc_obj.is_converged = False

        # Update function evaluations number
        if max_iterations_number is not None:
            self.sc_obj.max_iterations_number = max_iterations_number

        # Initialize the iteration number
        iterations = 0

        # Landscape dimension
        dim = len(x0)

        # Hyper-parameters for adaptive and not adaptive NM
        if self.is_adaptive:
            f_dim = float(dim)
            [rho, chi, psi, sigma] = [1, 1 + 2 / f_dim, 0.75 - 1 / (2 * f_dim), 1 - 1 / f_dim ]
        else:
            [rho, chi, psi, sigma] = [1, 2, 0.5, 0.5]

        # Start simplex initialization
        if initial_simplex is None:
            nonzdelt = 0.05
            zdelt = 0.00025
            sim = np.zeros((dim + 1, dim), dtype=x0.dtype)
            for k in range(dim):
                y = np.array(x0, copy=True)
                if y[k] != 0:
                    y[k] = (1 + nonzdelt) * y[k]
                else:
                    y[k] = zdelt
                sim[k + 1] = y
        else:
            sim = initial_simplex.copy()

        # Function evaluation array
        fsim = np.zeros((dim + 1,), float)

        # Initial evaluation of the start simplex
        # TODO parallelization for start simplex initialization, i.e. send single data file for multiple evaluations!
        for k in range(dim + 1):
            fsim[k] = func(sim[k], iterations, rmode, None)

        # Sort the array by the lowest function value since we are performing a minimization
        ind = np.argsort(fsim)
        [sim, fsim] = [np.take(sim, ind, 0), np.take(fsim, ind, 0)]

        # Update NM function evaluation
        iterations = 1

        # Start loop for function evaluation
        while not self.sc_obj.is_converged:
            # Baricenter
            xbar = np.add.reduce(sim[:-1], 0) / dim
            # Reflection
            xr = (1 + rho) * xbar - rho * sim[-1]
            # 2nd reflection
            fxr = func(xr, iterations, rmode, None)
            # Shrinking
            doshrink = 0

            if fxr < fsim[0]:
                xe = (1 + rho * chi) * xbar - rho * chi * sim[-1]
                fxe = func(xe, iterations, rmode, None)

                if fxe < fxr:
                    sim[-1] = xe
                    fsim[-1] = fxe
                else:
                    sim[-1] = xr
                    fsim[-1] = fxr
            else:  # fsim[0] <= fxr
                if fxr < fsim[-2]:
                    sim[-1] = xr
                    fsim[-1] = fxr
                else:  # fxr >= fsim[-2]
                    # Perform contraction
                    if fxr < fsim[-1]:
                        xc = (1 + psi * rho) * xbar - psi * rho * sim[-1]
                        fxc = func(xc, iterations, rmode, None)
                        if fxc <= fxr:
                            sim[-1] = xc
                            fsim[-1] = fxc
                        else:
                            doshrink = 1
                    else:
                        # Perform an inside contraction
                        xcc = (1 - psi) * xbar + psi * sim[-1]
                        fxcc = func(xcc, iterations, rmode, None)

                        if fxcc < fsim[-1]:
                            sim[-1] = xcc
                            fsim[-1] = fxcc
                        else:
                            doshrink = 1

                    if doshrink:
                        for j in range(1, dim+1):
                            sim[j] = sim[0] + sigma * (sim[j] - sim[0])
                            fsim[j] = func(sim[j], iterations, rmode, None)

            ## Sort the array by the lowest function value since we are performing a minimization
            ind = np.argsort(fsim)
            [sim, fsim] = [np.take(sim, ind, 0), np.take(fsim, ind, 0)]

            # Increase the NM iteration
            iterations += 1

            # Update function evaluations number
            self.sc_obj.fnc_evals = fcalls[0]

            # TODO Use the callback function to check if any error occurs in the main process
            # Check for error in the communication method
            if callback is not None:
                callback(sim[0])

            # Check stopping criteria
            self.sc_obj.check_stp_criteria(sim, fsim, iterations)

        ### END of while loop

        # Fix the iteration number
        iterations = iterations - 1

        # Optimal parameters and value
        x = sim[0]
        fval = np.min(fsim)

        result_custom = {'F_min_val': fval, 'X_opti_vec': x, 'NitUsed': iterations,
                         'NfunevalsUsed': fcalls[0], "terminate_reason": self.sc_obj.terminate_reason}

        return result_custom
