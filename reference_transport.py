import math

import numpy as np


def solve_slab(thickness, sigma_total=1.0, scatter_ratio=0.8, cells=256, positive_directions=64):
    if not math.isfinite(thickness) or thickness <= 0 or not math.isfinite(sigma_total) or sigma_total <= 0:
        raise ValueError("Thickness and total cross section must be positive and finite.")
    if not math.isfinite(scatter_ratio) or not 0 <= scatter_ratio < 1:
        raise ValueError("The scattering ratio must be finite and in [0, 1).")
    if isinstance(cells, bool) or not isinstance(cells, int) or cells < 4:
        raise ValueError("Use an integer number of spatial cells of at least four.")
    if isinstance(positive_directions, bool) or not isinstance(positive_directions, int) or positive_directions < 4:
        raise ValueError("Use an integer number of positive directions of at least four.")
    nodes, weights = np.polynomial.legendre.leggauss(positive_directions)
    directions = (nodes + 1) / 2
    weights = weights / 2
    width = thickness / cells
    optical_step = sigma_total * width
    angle_steps = optical_step / directions
    attenuation = np.exp(-angle_steps)
    removed = -np.expm1(-angle_steps)
    average_factor = removed / angle_steps
    kernel = np.empty(cells)
    kernel[0] = scatter_ratio * np.dot(weights, 1 - average_factor)
    powers = attenuation[:, None] ** np.arange(cells - 1)[None, :]
    kernel[1:] = scatter_ratio / 2 * np.sum((weights * average_factor * removed)[:, None] * powers, axis=0)
    separations = np.abs(np.arange(cells)[:, None] - np.arange(cells)[None, :])
    uncollided_average = np.exp(-optical_step * np.arange(cells)) * (-math.expm1(-optical_step) / optical_step)
    scalar_flux = np.linalg.solve(np.eye(cells) - kernel[separations], uncollided_average)
    escape_weights = scatter_ratio / 2 * np.sum((weights * directions * removed)[:, None] * attenuation[:, None] ** np.arange(cells)[None, :], axis=0)
    uncollided_exit = math.exp(-sigma_total * thickness)
    reflection = float(np.dot(escape_weights, scalar_flux))
    transmission = uncollided_exit + float(np.dot(escape_weights[::-1], scalar_flux))
    absorption = (1 - scatter_ratio) * sigma_total * width * float(scalar_flux.sum())
    return {
        "thickness_cm": thickness,
        "sigma_t_per_cm": sigma_total,
        "scatter_ratio": scatter_ratio,
        "spatial_cells": cells,
        "positive_directions": positive_directions,
        "total_directions": 2 * positive_directions,
        "transmission": transmission,
        "uncollided_transmission": uncollided_exit,
        "reflection": reflection,
        "absorption": absorption,
        "particle_balance": transmission + reflection + absorption,
        "method": "Analytic uncollided beam plus constant-source step characteristics with double Gauss-Legendre angular integration and a direct scalar-flux linear solve.",
    }
