# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

import pytest_bdd as bdd

from vimiv import plugins


bdd.scenarios("plugins.feature")


@bdd.when(bdd.parsers.parse("I load the {name} plugin"))
def load_plugin(name):
    plugins.load(name)
