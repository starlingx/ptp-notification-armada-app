# -*- coding: utf-8 -*-
#
# Copyright (c) 2021-2026 Wind River Systems, Inc.
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
    name='notificationservice-base-v2',
    version='0.2',
    description='',
    author='',
    author_email='',
    install_requires=[
        "watchdog",
    ],
    tests_require=[
        "mock",
        "watchdog",
    ],
    test_suite='notificationservice-base-v2',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages()
)
