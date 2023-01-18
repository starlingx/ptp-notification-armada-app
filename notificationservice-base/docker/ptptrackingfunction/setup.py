# -*- coding: utf-8 -*-
#
# Copyright (c) 2021-2023 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name='ptptrackingfunction',
    version='0.1',
    description='',
    author='',
    author_email='',
    install_requires=[
        "",
    ],
    test_suite='ptptrackingfunction',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
)
