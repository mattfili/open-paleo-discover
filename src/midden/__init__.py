"""midden — archaeological site-predictive modelling for Middle Tennessee.

See spec.md for architecture and CLAUDE.md for working conventions.
"""

__all__ = ["PROJECT_CRS", "__version__"]

__version__ = "0.1.0"

#: NAD83 / UTM zone 16N, metres. Middle Tennessee is entirely within zone 16.
#: Everything reprojects to this on intake. WhiteboxTools does not reproject and will
#: happily process degrees as if they were metres, which is why this is not negotiable.
PROJECT_CRS = "EPSG:26916"
