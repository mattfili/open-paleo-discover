"""Horizon-scan visualisation functions, vendored verbatim from Relief Visualization
Toolbox (RVT_py).

    Source:    https://github.com/EarthObservation/RVT_py  (rvt/vis.py)
    Licence:   Apache License 2.0 — see NOTICE at the repository root.
    Credits:   Ziga Kokalj, Kristof Ostir, Klemen Zaksek, Peter Pehani,
               Klemen Cotar, Maja Somrak, Ziga Maroh, Nejc Coz
    Copyright: 2010-2020 Research Centre of the Slovenian Academy of Sciences and Arts
               2016-2020 University of Ljubljana, Faculty of Civil and Geodetic Engineering

WHY THIS IS VENDORED RATHER THAN INSTALLED
------------------------------------------
`Openness` is not in WhiteboxTools v2.4.0 open core — the binary answers "Unrecognized
tool name Openness" even though the Python wrapper exposes an `openness()` method, because
that wrapper is generated from the full manual including paid Whitebox Toolset Extension
tools. So midden computes openness itself.

`rvt-py` on PyPI caps at Python <3.12 and this project runs 3.14, but the cap comes from
`rvt.default`, which is the GDAL file-I/O layer. The maths in `rvt/vis.py` is pure numpy.
midden already reads rasters with rasterio and passes arrays around, so only the maths is
needed. spec.md §7 sanctions exactly this: "feed your own arrays to `rvt.vis`, or vendor
the single function."

DO NOT EDIT THE FUNCTIONS BELOW. They are a verbatim copy so they can be diffed against
upstream. midden's own wrappers live in `midden/terrain/detection.py`.

SIGN CONVENTION
---------------
`sky_view_factor_compute(..., compute_opns=True)["opns"]` returns *positive* openness in
degrees: 90 minus the mean horizon elevation angle over all directions. A flat plane is
exactly 90 degrees regardless of slope; convex forms (mounds, charcoal hearths, ridges)
are above 90. Negative openness is the same computation on a negated DEM, and it is not
the inverse of positive.
"""

from __future__ import annotations

import numpy as np

__all__ = ["horizon_shift_vector", "sky_view_factor_compute"]


def horizon_shift_vector(num_directions=16,
                         radius_pixels=10,
                         min_radius=1
                         ):
    """
    Calculates Sky-View determination movements.

    Parameters
    ----------
    num_directions : int
        Number of directions as input.
    radius_pixels : int
        Radius to consider in pixels (not in meters).
    min_radius : int
        Radius to start searching for horizon in pixels (not in meters).

    Returns
    -------
    shift : dict
        Dict with keys corresponding to the directions of search azimuths rounded to 1 decimal number
            - for each key, a subdict contains a key "shift":
                values for this key is a list of tuples prepared for np.roll - shift along lines and columns
            - the second key is "distance":
                values for this key is a list of search radius used for the computation of the elevation angle 
    """

    # Initialize the output dict
    shift = {}

    # Generate angles and corresponding normal shifts in X (columns)
    # and Y (lines) direction
    angles = (2 * np.pi / num_directions) * np.arange(num_directions)
    x = np.cos(angles)
    y = np.sin(angles)
    angles = np.round(np.degrees(angles), decimals=1)

    # Generate a range of radius values in pixels.
    # Make it finer for the selected scaling.
    # By adding the last constant we make sure that we do not start with
    # point (0,0).
    scale = 3.
    radii = np.arange((radius_pixels - min_radius) * scale + 1) / scale + min_radius

    # For each direction compute all possible horizon point position
    # and round them to integers
    for i in range(num_directions):
        x_int = np.round(x[i] * radii, decimals=0)
        y_int = np.round(y[i] * radii, decimals=0)
        # consider only the minimal number of points
        # use the trick with set and complex number as the input
        coord_complex = set(x_int + 1j * y_int)
        # to sort proportional with increasing radius, 
        # set has to be converted to numpy array
        shift_pairs = np.array([(k.real, k.imag) for k in coord_complex]).astype(int)
        distance = np.sqrt(np.sum(shift_pairs ** 2, axis=1))
        sort_index = np.argsort(distance)
        # write for each direction shifts and corresponding distances
        shift[angles[i]] = {
            "shift": [(k[0], k[1]) for k in shift_pairs[sort_index]],
            "distance": distance[sort_index],
        }

    return shift


def sky_view_factor_compute(height_arr,
                            radius_max=10,
                            radius_min=1,
                            num_directions=16,
                            compute_svf=True,
                            compute_opns=False,
                            compute_asvf=False,
                            a_main_direction=315.,
                            a_poly_level=4,
                            a_min_weight=0.4
                            ):
    """
    Calculates horizon based visualizations: Sky-view factor, Anisotropic SVF and Openness.

    SVF processing is using search radius, that looks at values beyond the edge of an array. Consider using a buffered
    array as an input, with the buffer size equal to the radius_max.
    To prevent erosion of the edge, function applies mirrored padding in all four directions, however, this means that
    edge values are "averaged over half of the hemisphere". Similarly, the edges of the dataset (i.e. areas with NaN
    values), will be considered as fully open (SFV angle 0, Openness angle -90).

    Input array should use np.nan as nodata value.

    Parameters
    ----------
    height_arr : numpy.ndarray
        Elevation (DEM) as 2D numpy array.
    radius_max : int
        Maximal search radius in pixels/cells (not in meters).
    radius_min : int
        Minimal search radius in pixels/cells (not in meters), for noise reduction.
    num_directions : int
        Number of directions as input.
    compute_svf : bool
        If true it computes and outputs svf.
    compute_asvf : bool
        If true it computes and outputs asvf.
    compute_opns : bool
        If true it computes and outputs opns.
    a_main_direction : int or float
        Main direction of anisotropy.
    a_poly_level : int
        Level of polynomial that determines the anisotropy.
    a_min_weight : float
        Weight to consider anisotropy:
                 0 - low anisotropy, 
                 1 - high  anisotropy (no illumination from the direction opposite the main direction)

    Returns
    -------
    dict_out : dictionary
        Return {"svf": svf_out, "asvf": asvf_out, "opns": opns_out};
        svf_out, skyview factor : 2D numpy array (numpy.ndarray) of skyview factor;
        asvf_out, anisotropic skyview factor : 2D numpy array (numpy.ndarray) of anisotropic skyview factor;
        opns_out, openness : 2D numpy array (numpy.ndarray) openness (elevation angle of horizon).
    """

    # Pad the array for the radius_max on all 4 sides
    height = np.pad(height_arr, radius_max, mode='reflect')

    # Compute the vector of movement and corresponding distances
    move = horizon_shift_vector(num_directions=num_directions, radius_pixels=radius_max, min_radius=radius_min)

    # Initiate the output for SVF
    if compute_svf:
        svf_out = height * 0  # Multiply with 0 instead of using np.zeros to preserve nodata
    else:
        svf_out = None

    # Initiate the output for azimuth dependent SVF
    if compute_asvf:
        asvf_out = height * 0  # Multiply with 0 instead of using np.zeros to preserve nodata
        w_m = a_min_weight
        w_a = np.deg2rad(a_main_direction)
        weight = np.arange(num_directions) * (2 * np.pi / num_directions)
        weight = (1 - w_m) * (np.cos((weight - w_a) / 2)) ** a_poly_level + w_m
    else:
        asvf_out = None
        weight = None

    # Initiate the output for Openness
    if compute_opns:
        opns_out = height * 0  # Multiply with 0 instead of using np.zeros to preserve nodata
    else:
        opns_out = None

    # Search for horizon in each direction...
    for i_dir, direction in enumerate(move):
        # Reset maximum at each iteration (i.e. at the start of new direction),
        # smallest possible elevation angle is -1000 rad (i.e. -90 deg)
        max_slope = np.zeros(height.shape, dtype=np.float32) - 1000

        # ... and for each search radius
        for i_rad, radius in enumerate(move[direction]["distance"]):
            # Get shift index from move dictionary
            shift_indx = move[direction]["shift"][i_rad]
            # Estimate the slope
            _ = (np.roll(height, shift_indx, axis=(0, 1)) - height) / radius
            # Compare to the previous max slope and keep the largest values (element wise). Use np.fmax to prevent NaN
            # values contaminating the edge of the image (if one of the elements is NaN, pick non-NaN element)
            max_slope = np.fmax(max_slope, _)

        # Convert to angle in radians and compute directional output
        max_slope = np.arctan(max_slope)

        # Sum max angle for all directions
        if compute_svf:
            # For SVF minimum possible angle is 0 (hemisphere), use np.fmax() to change NaNs to 0
            svf_out = svf_out + (1 - np.sin(np.fmax(max_slope, 0)))
        if compute_asvf:
            # For SVF minimum possible angle is 0 (hemisphere), use np.fmax() to change NaNs to 0
            asvf_out = asvf_out + (1 - np.sin(np.fmax(max_slope, 0))) * weight[i_dir]
        if compute_opns:
            # For Openness taking the entire sphere
            opns_out = opns_out + max_slope

    # Cut to original extent and average the directional output over all directions
    if compute_svf:
        svf_out = svf_out[radius_max:-radius_max, radius_max:-radius_max] / num_directions
    if compute_asvf:
        asvf_out = asvf_out[radius_max:-radius_max, radius_max:-radius_max] / np.sum(weight)
    if compute_opns:
        opns_out = np.rad2deg(0.5 * np.pi - (opns_out[radius_max:-radius_max, radius_max:-radius_max] / num_directions))

    # Return results within dict
    dict_svf_asvf_opns = {"svf": svf_out, "asvf": asvf_out, "opns": opns_out}
    dict_svf_asvf_opns = {k: v for k, v in dict_svf_asvf_opns.items() if v is not None}  # filter out none

    return dict_svf_asvf_opns
