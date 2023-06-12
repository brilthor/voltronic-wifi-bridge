#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from setuptools import setup
import os

# Allow to run setup.py from another directory.
os.chdir(os.path.dirname(os.path.abspath(__file__)))


setup(
    name="voltronic-wifi-bridge",
    version="0.1.0",
    packages=['voltronic_wifi_bridge'],
    include_package_data=True,
    install_requires=[
        'paho-mqtt',
        ],
    entry_points={
        'console_scripts': [
            'voltronic-wifi-bridge = voltronic_wifi_bridge.main:main',
            ]
        },

)