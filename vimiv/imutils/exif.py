# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2020 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""Utility functions and classes for exif handling.

All exif related tasks are implemented in this module. The heavy lifting is done using
piexif (https://github.com/hMatoba/Piexif).
"""

import contextlib
from typing import Dict

from vimiv.utils import log, lazy
from vimiv import api

pyexiv2 = lazy.import_module("pyexiv2", optional=True)
piexif = lazy.import_module("piexif", optional=True)

_logger = log.module_logger(__name__)


def check_exif_dependancy(exif_handler, return_value=None):
    """Decorator for ExifHandler which require the optional py3exiv2 module.

    If py3exiv2 is available the class is left as it is. If py3exiv2 is not available
    but the depreciated piexif module is, a depreciation warning is given to the user
    and a ExifHandler class supporting piexif is returned. If none of the two modules
    is available, a dummy class or return_value is returned and a debug log is logged.

    Args:
        exif_handler: The ExifHandler class to be decorated.
        return_value: Value to return if neither py3exiv2 nor piexif is not available.
    """

    if pyexiv2:
        return exif_handler

    if piexif:

        class ExifHandlerPiexif(exif_handler):
            """Depreciated handler to load and copy exif information of a single image.

            This class provides several methods for interacting with metadata of a
            single image.

            Methods:
                get_formatted_exif: Get dict containing formatted exif values.
                copy_exif: Copies the metadata to the src image.
                exif_date_time: Get the datetime.

            Attributes:
                _metadata: Instance of the pyexiv2 metadata handler
            """

            def __init__(self, filename):
                super()
                self._metadata = None

                try:
                    self._metadata = piexif.load(filename)
                except FileNotFoundError:
                    _logger.debug("File %s not found", filename)
                    return

            def get_formatted_exif(self) -> Dict[str, str]:
                """Get a dict of the formatted exif value.

                Returns a dictionary contain formatted exif values for the exif tags
                defined in the config.
                """

                desired_keys = [
                    e.strip()
                    for e in api.settings.metadata.current_keyset.value.split(",")
                ]
                _logger.debug(f"Read metadata.current_keys {desired_keys}")

                exif = dict()

                try:

                    for ifd in self._metadata:
                        if ifd == "thumbnail":
                            continue

                        for tag in self._metadata[ifd]:
                            keyname = piexif.TAGS[ifd][tag]["name"]
                            keytype = piexif.TAGS[ifd][tag]["type"]
                            val = self._metadata[ifd][tag]
                            _logger.debug(
                                f"name: {keyname} type: {keytype} value: {val} tag: {tag}"
                            )
                            if keyname.lower() not in desired_keys:
                                _logger.debug(f"Ignoring key {keyname}")
                                continue
                            if keytype in (
                                piexif.TYPES.Byte,
                                piexif.TYPES.Short,
                                piexif.TYPES.Long,
                                piexif.TYPES.SByte,
                                piexif.TYPES.SShort,
                                piexif.TYPES.SLong,
                                piexif.TYPES.Float,
                                piexif.TYPES.DFloat,
                            ):  # integer and float
                                exif[keyname] = (keyname, val)
                            elif keytype in (
                                piexif.TYPES.Ascii,
                                piexif.TYPES.Undefined,
                            ):  # byte encoded
                                exif[keyname] = (keyname, val.decode())
                            elif keytype in (
                                piexif.TYPES.Rational,
                                piexif.TYPES.SRational,
                            ):  # (int, int) <=> numerator, denominator
                                exif[keyname] = (keyname, f"{val[0]}/{val[1]}")

                except (piexif.InvalidImageDataError, KeyError):
                    return None

                return exif

            def copy_exif(self, dest: str, reset_orientation: bool = True) -> None:
                """Copy exif information from current image to dest.

                Args:
                    dest: Path to write the exif information to.
                    reset_orientation: If true, reset the exif orientation tag to
                        normal.
                """

                try:
                    if reset_orientation:
                        with contextlib.suppress(KeyError):
                            self._metadata["0th"][
                                piexif.ImageIFD.Orientation
                            ] = ExifOrientation.Normal
                    exif_bytes = piexif.dump(self._metadata)
                    piexif.insert(exif_bytes, dest)
                    _logger.debug("Succesfully wrote exif data for '%s'", dest)
                except piexif.InvalidImageDataError:  # File is not a jpg
                    _logger.debug("File format for '%s' does not support exif", dest)
                except ValueError:
                    _logger.debug("No exif data in '%s'", dest)

            def exif_date_time(self) -> str:
                """Exif creation date and time of filename."""

                with contextlib.suppress(
                    piexif.InvalidImageDataError, FileNotFoundError, KeyError
                ):
                    return self._metadata["0th"][piexif.ImageIFD.DateTime].decode()
                return ""

        return ExifHandlerPiexif

    if return_value:
        return return_value

    # TODO: No exif support, return dummy class
    return None


@check_exif_dependancy
class ExifHandler:
    """Handler to load and copy exif information of a single image.

    This class provides several methods for interacting with metadata of a single image.

    Methods:
        get_formatted_exif: Get dict containing formatted exif values.
        copy_exif: Copies the metadata to the src image.
        exif_date_time: Get the datetime.

    Attributes:
        _metadata: Instance of the pyexiv2 metadata handler
    """

    def __init__(self, filename):

        try:
            self._metadata = pyexiv2.ImageMetadata(filename)
            self._metadata.read()

        except FileNotFoundError:
            _logger.debug("File %s not found", filename)
            return

    def get_formatted_exif(self) -> Dict[str, str]:
        """Get a dict of the formatted exif value.

        Returns a dictionary contain formatted exif values for the exif tags defined in
        the config.
        """

        desired_keys = [
            e.strip() for e in api.settings.metadata.current_keyset.value.split(",")
        ]
        _logger.debug(f"Read metadata.current_keys {desired_keys}")

        exif = dict()

        for key in desired_keys:
            try:
                exif[key] = (
                    self._metadata[key].name,
                    self._metadata[key].human_value,
                )
            except AttributeError:
                exif[key] = (
                    self._metadata[key].name,
                    self._metadata[key].raw_value,
                )
            except KeyError:
                _logger.debug("Key %s is invalid for the current image", key)

        return exif

    def copy_exif(self, dest: str, reset_orientation: bool = True) -> None:
        """Copy exif information from current image to dest.

        Args:
            dest: Path to write the exif information to.
            reset_orientation: If true, reset the exif orientation tag to normal.
        """

        if reset_orientation:
            with contextlib.suppress(KeyError):
                self._metadata["Exif.Image.Orientation"] = pyexiv2.ExifTag(
                    "Exif.Image.Orientation", ExifOrientation.Normal
                )
        self._metadata.copy(dest)
        _logger.debug("Succesfully wrote exif data for '%s'", dest)

    def exif_date_time(self) -> str:
        """Get exif creation date and time of filename."""

        with contextlib.suppress(
            piexif.InvalidImageDataError, FileNotFoundError, KeyError
        ):
            return self._metadata["Exif.Image.DateTime"].raw_value
        return ""


class ExifOrientation:
    """Namespace for exif orientation tags.

    For more information see: http://jpegclub.org/exif_orientation.html.
    """

    Unspecified = 0
    Normal = 1
    HorizontalFlip = 2
    Rotation180 = 3
    VerticalFlip = 4
    Rotation90HorizontalFlip = 5
    Rotation90 = 6
    Rotation90VerticalFlip = 7
    Rotation270 = 8
