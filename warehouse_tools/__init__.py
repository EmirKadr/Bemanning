"""Shared warehouse/WMS tools used by Bemanning.

This package owns the long-term runtime for the Bearbeta, Dela and Harleda
views. Lightweight UI metadata lives in `catalog` and native flows should be
added as small modules. The vendored engine remains only as a compatibility
bridge while individual flows are moved in-house.
"""
