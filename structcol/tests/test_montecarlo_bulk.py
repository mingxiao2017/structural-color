# Copyright 2016, Vinothan N. Manoharan, Victoria Hwang
#
# This file is part of the structural-color python package.
#
# This package is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This package is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this package. If not, see <http://www.gnu.org/licenses/>.
"""
Tests for the montecarlo bulk model

.. moduleauthor:: Anna B. Stephenson <stephenson@g.harvard.edu>
.. moduleauthor:: Victoria Hwang <vhwang@g.harvard.edu>
.. moduleauthor:: Vinothan N. Manoharan <vnm@seas.harvard.edu>
"""

import numpy as np
import structcol as sc
import structcol.refractive_index as ri
from structcol import montecarlo as mc
from structcol import detector as det
from structcol import phase_func_sphere as pfs
from numpy.testing import assert_equal, assert_almost_equal

### Set parameters ###

# Properties of source
wavelength = sc.Quantity('600 nm') # wavelengths at which to calculate reflectance

# Geometric properties of sample
particle_radius = sc.Quantity('0.130 um')        # radius of the sphere particles 
volume_fraction_particles = sc.Quantity(0.6, '') # volume fraction of the particles in the sphere boundary
volume_fraction_bulk = sc.Quantity(0.55,'')      # volume fraction of the spheres in the bulk film
sphere_boundary_diameter = sc.Quantity(10,'um')  # diameter of the sphere boundary
boundary = 'sphere'
boundary_bulk = 'film'

# Refractive indices
n_particle = ri.n('vacuum', wavelength)    # refractive index of particle
n_matrix = ri.n('polystyrene', wavelength) # refractive index of matrix
n_matrix_bulk = ri.n('vacuum', wavelength) # refractive index of the bulk matrix
n_medium = ri.n('vacuum', wavelength)      # refractive index of medium outside the bulk sample. 

# Monte Carlo parameters
ntrajectories = 2000         # number of trajectories to run with a spherical boundary
nevents = 300                # number of scattering events for each trajectory in a spherical boundary

# Properties that should not need to be changed
z_low = sc.Quantity('0.0 um') # sets trajectories starting point


def calc_sphere_mc():
    
    # caculate the effective index of the sample
    n_sample = ri.n_eff(n_particle, n_matrix, volume_fraction_particles)
    
    # Calculate the phase function and scattering and absorption coefficients 
    #from the single scattering model
    # (this absorption coefficient is of the scatterer, not of an absorber 
    #added to the system)
    p, mu_scat, mu_abs = mc.calc_scat(particle_radius, n_particle, n_sample,
                                      volume_fraction_particles, wavelength)
    
    # Initialize the trajectories
    r0, k0, W0 = mc.initialize(nevents, ntrajectories, n_matrix_bulk, 
                                      n_sample, boundary, 
                                      sample_diameter = sphere_boundary_diameter)
    r0 = sc.Quantity(r0, 'um')
    k0 = sc.Quantity(k0, '')
    W0 = sc.Quantity(W0, '')
    
    # Create trajectories object
    trajectories = mc.Trajectory(r0, k0, W0)
    
    # Generate a matrix of all the randomly sampled angles first 
    sintheta, costheta, sinphi, cosphi, _, _ = mc.sample_angles(nevents, 
                                                                ntrajectories, 
                                                                p)
    
    # Create step size distribution
    step = mc.sample_step(nevents, ntrajectories, mu_scat)
    
    # Run photons
    trajectories.absorb(mu_abs, step)                         
    trajectories.scatter(sintheta, costheta, sinphi, cosphi)         
    trajectories.move(step)
    
    # Calculate reflection and transmition 
    (refl_indices, 
     trans_indices, 
     _, _, _, 
     refl_per_traj, trans_per_traj,
     _,_,_,_,
     reflectance_sphere, 
     _,_, norm_refl, norm_trans) = det.calc_refl_trans(trajectories, sphere_boundary_diameter,
                                  n_matrix_bulk, n_sample, boundary, 
                                  p=p, mu_abs=mu_abs, mu_scat=mu_scat,  
                                  run_fresnel_traj = False, 
                                  return_extra = True)
             
    return (refl_indices, trans_indices, refl_per_traj, trans_per_traj, 
            reflectance_sphere, norm_refl, norm_trans)
        
    ### Calculate phase function and lscat ###
    # use output of calc_refl_trans to calculate phase function, mu_scat, 
    # and mu_abs for the bulk
    p_bulk, mu_scat_bulk, mu_abs_bulk = pfs.calc_scat_bulk(refl_per_traj, 
                                                           trans_per_traj, 
                                                           trans_indices, 
                                                           norm_refl, norm_trans, 
                                                           volume_fraction_bulk, 
                                                           sphere_boundary_diameter)
    return p_bulk, mu_scat_bulk, mu_abs_bulk

def test_mu_scat_abs_bulk():
    
    # make sure there is no absorption when all refractive indices are real
    (refl_indices, trans_indices, 
     refl_per_traj, trans_per_traj, 
     reflectance_sphere, 
     norm_refl, norm_trans) = calc_sphere_mc()
    
    _, _, mu_abs_bulk = pfs.calc_scat_bulk(refl_per_traj, 
                                           trans_per_traj, 
                                           trans_indices, 
                                           norm_refl, norm_trans, 
                                           volume_fraction_bulk, 
                                           sphere_boundary_diameter)
    
    assert_almost_equal(mu_abs_bulk.magnitude, 0)
    
    
    # make sure mu_abs reaches limit when there is no scattering
    _, mu_scat_bulk, mu_abs_bulk = pfs.calc_scat_bulk(np.zeros((ntrajectories)), 
                                                      np.zeros((ntrajectories)), 
                                                      trans_indices, 
                                                      norm_refl, norm_trans, 
                                                      volume_fraction_bulk, 
                                                      sphere_boundary_diameter)

    number_density = volume_fraction_bulk.magnitude/(4/3*np.pi*
                                        (sphere_boundary_diameter.magnitude/2)**3)
    mu_abs_max = number_density*2*np.pi*(sphere_boundary_diameter.magnitude/2)**2
    
    assert_almost_equal(mu_abs_bulk.magnitude, mu_abs_max)
    
    # check that mu_scat_bulk is 0 when no scattering
    assert_almost_equal(mu_scat_bulk.magnitude, 0)
    
    # check the mu_scat_bulk reaches limit when there is only scattering
    _, mu_scat_bulk, _ = pfs.calc_scat_bulk(0.5/ntrajectories*np.ones((ntrajectories)), 
                                            0.5/ntrajectories*np.ones((ntrajectories)), 
                                            np.ones(ntrajectories)+3, 
                                            norm_refl, norm_trans, 
                                            volume_fraction_bulk, 
                                            sphere_boundary_diameter)

    number_density = volume_fraction_bulk.magnitude/(4/3*np.pi*
                                        (sphere_boundary_diameter.magnitude/2)**3)
    mu_scat_max = number_density*2*np.pi*(sphere_boundary_diameter.magnitude/2)**2
    
    assert_almost_equal(mu_scat_bulk.magnitude, mu_scat_max)
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    