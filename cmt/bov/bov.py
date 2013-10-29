#! /bin/env python

import os
import sys
import ConfigParser

import numpy as np

from cmt.grids import RasterField


class BovError(Exception):
    pass


class MissingRequiredKeyError(BovError):
    def __init__(self, opt):
        self.opt = opt

    def __str__(self):
        return '%s: Missing required key' % self.opt


class BadKeyValueError(BovError):
    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __str__(self):
        return '%s, %s: Bad value' % (self.key, self.value)


class ReadError(BovError):
    def __init__(self, file):
        self.file = file

    def __str__(self):
        return '%s: Unable to read' % (self.file)


class FileExists(BovError):
    def __init__(self, file):
        self.file = file

    def __str__(self):
        return '%s: Unable to write to file' % self.file


class BadFileExtension(BovError):
    def __init__(self, ext):
        self.ext = ext

    def __str__ (self):
        return "%s: Extension should be '.bov' or empty" % self.ext


_BOV_TO_NP_TYPE = {'BYTE': 'uint8', 'SHORT': 'int32', 'INT': 'int64',
                  'FLOAT': 'float32', 'DOUBLE': 'float64'}
_NP_TO_BOV_TYPE = dict(zip(_BOV_TO_NP_TYPE.values(), _BOV_TO_NP_TYPE.keys()))
_SYS_TO_BOV_ENDIAN = {'little': 'LITTLE', 'big': 'BIG'}


def array_to_str(array):
    s = [str(x) for x in array]
    return ' '.join(s)


def fromfile(file, allow_singleton=True):
    """
    >>> (grid, attrs) = fromfile ('test.bov')
    >>> grid.get_shape () #doctest: +NORMALIZE_WHITESPACE
    array([10, 10, 1])
    >>> data = grid.cell_data ('Elevation')
    >>> print data.max ()
    5.0
    >>> print data.min ()
    5.0
    >>> grid.get_spacing () #doctest: +NORMALIZE_WHITESPACE
    array([ 1., 1., 1.])
    >>> grid.get_shape () #doctest: +NORMALIZE_WHITESPACE
    array([10, 10, 1])
    >>> grid.get_origin () #doctest: +NORMALIZE_WHITESPACE
    array([ 0., 0., 0.])

    >>> grid = fromfile ('test.bov', allow_singleton=False)
    >>> grid.get_shape () #doctest: +NORMALIZE_WHITESPACE
    array([10, 10])
    >>> data = grid.cell_data ('Elevation')
    >>> print data.max ()
    5.0
    >>> print data.min ()
    5.0
    >>> grid.get_spacing () #doctest: +NORMALIZE_WHITESPACE
    array([ 1., 1.])
    >>> grid.get_shape () #doctest: +NORMALIZE_WHITESPACE
    array([10, 10])
    >>> grid.get_origin () #doctest: +NORMALIZE_WHITESPACE
    array([ 0., 0.])

    >>> grid = fromfile ('test_points.bov', allow_singleton=False)

    >>> data = grid.point_data ('Elevation')
    >>> print data.max ()
    5.0
    >>> print data.min ()
    5.0
    >>> data.shape
    (10, 10)

    """
    header = {}
    with open(file, 'r') as f:
        for line in f:
            try:
                (data, comment) = line.split('#')
            except ValueError:
                data = line
            try:
                (key, value) = data.split(':')
                header[key.strip()] = value.strip()
            except ValueError:
                pass

    keys_found = set(header.keys())
    keys_required = set(['DATA_SIZE', 'DATA_FORMAT', 'DATA_FILE',
                         'BRICK_ORIGIN', 'BRICK_SIZE', 'VARIABLE'])
    if not keys_required.issubset(keys_found):
        missing = ', '.join(keys_required-keys_found)
        raise MissingRequiredKeyError(missing)

    shape = header['DATA_SIZE'].split()
    header['DATA_SIZE'] = np.array([int(i) for i in shape], dtype=np.int64)

    origin = header['BRICK_ORIGIN'].split()
    header['BRICK_ORIGIN'] = np.array([float(i) for i in origin], dtype=np.float64)

    size = header['BRICK_SIZE'].split()
    header['BRICK_SIZE'] = np.array([float(i) for i in size], dtype=np.float64)

    if not allow_singleton:
        not_singleton = header['DATA_SIZE']>1
        header['DATA_SIZE'] = header['DATA_SIZE'][not_singleton]
        header['BRICK_SIZE'] = header['BRICK_SIZE'][not_singleton]
        header['BRICK_ORIGIN'] = header['BRICK_ORIGIN'][not_singleton]

    type_str = header['DATA_FORMAT']
    try:
        type = _BOV_TO_NP_TYPE[type_str]
    except KeyError as e:
        raise BadKeyValueError('DATA_FORMAT', type_str)

    dat_file = header['DATA_FILE']
    if not os.path.isabs(dat_file):
        dat_file = os.path.join(os.path.dirname(file), dat_file)

    try:
        data = np.fromfile(dat_file, dtype=type)
    except Exception as e:
        raise 

    try:
        data.shape = header['DATA_SIZE']
    except ValueError as e:
        raise BadKeyValueError('DATA_SIZE', '%d != %d' % (np.prod(header['DATA_SIZE']), data.size))

    try:
        header['TIME'] = float(header['TIME'])
    except KeyError:
        pass

    shape = header['DATA_SIZE']
    origin = header['BRICK_ORIGIN']
    spacing = header['BRICK_SIZE']/(shape-1)

    grid = RasterField(shape, spacing, origin, indexing='ij')
    if header.has_key('CENTERING') and header['CENTERING'] == 'zonal':
        grid.add_field(header['VARIABLE'], data, centering='zonal')
    else:
        grid.add_field(header['VARIABLE'], data, centering='point')

    return (grid, header)


def array_tofile(file, array, name='', spacing=(1., 1.), origin=(0., 0.),
                 no_clobber=False, options={}):
    files_written = []
    (base, ext) = os.path.splitext(file)
    if len(ext) > 0 and ext != '.bov':
        raise BadFileExtension(ext)

    spacing = np.array(spacing, dtype=np.float64)
    origin = np.array(origin, dtype=np.float64)
    shape = np.array(array.shape, dtype=np.int64)
    size = shape * spacing

    if len(shape) < 3:
        shape = np.append(shape, [1] * (3 - len(shape)))
    if len(origin) < 3:
        origin = np.append(origin, [1.] * (3 - len(origin)))
    if len(size) < 3:
        size = np.append(size, [1.] * (3 - len(size)))

    vars = [(name, array)]

    for (var, vals) in vars:
        dat_file = '%s_%s.dat' % (base, var)
        bov_file = '%s_%s.bov' % (base, var)

        if no_clobber:
            if os.path.isfile(bov_file):
                raise FileExists(bov_file)
            if os.path.isfile(dat_file):
                raise FileExists(dat_file)

        vals.tofile(dat_file)

        header = dict(DATA_FILE=dat_file,
                      DATA_SIZE=array_to_str(shape),
                      BRICK_ORIGIN=array_to_str(origin),
                      BRICK_SIZE=array_to_str(size),
                      DATA_ENDIAN=_SYS_TO_BOV_ENDIAN[sys.byteorder],
                      DATA_FORMAT=_NP_TO_BOV_TYPE[str(vals.dtype)],
                      VARIABLE=var)

        header.update(options)
        with open(bov_file, 'w') as f:
            for item in header.items():
                f.write('%s: %s\n' % item)

        files_written.append(bov_file)

    return files_written


def tofile(file, grid, var_name=None, no_clobber=False, options={}):
    """
    Write a grid-like object to a BOV file.

    :param file: Name of the BOV file to write
    :type file: string
    :param grid: A uniform rectilinear grid-like object
    :type grid: Grid-like

    Required methods for grid:
        * get_shape
        * get_origin
        * get_spacing
        * items
        * get_field

    :returns: A list of the files written.
    """
    files_written = []
    (base, ext) = os.path.splitext(file)
    if len(ext) > 0 and ext != '.bov':
        raise BadFileExtension(ext)

    try:
        shape = grid.get_shape()
        origin = grid.get_origin()
        size = grid.get_shape() * grid.get_spacing()
    except (AttributeError, TypeError):
        raise TypeError('\'%s\' object is not grid-like' % type(grid))

    if len(shape) < 3:
        shape = np.append(shape, [1] * (3 - len(shape)))
    if len(origin) < 3:
        origin = np.append(origin, [1.] * (3 - len(origin)))
    if len(size) < 3:
        size = np.append(size, [1.] * (3 - len(size)))

    if var_name is None:
        vars = grid.get_point_fields().items()
    else:
        vars = (var_name, grid.get_field(var_name))

    for (var, vals) in vars:
        dat_file = '%s.dat' % (base, )
        bov_file = '%s.bov' % (base, )

        if no_clobber:
            if os.path.isfile(bov_file):
                raise FileExists(bov_file)
            if os.path.isfile(dat_file):
                raise FileExists(dat_file)

        vals.tofile(dat_file)

        header = dict(DATA_FILE=dat_file,
                      DATA_SIZE=array_to_str(shape),
                      BRICK_ORIGIN=array_to_str(origin),
                      BRICK_SIZE=array_to_str(size),
                      DATA_ENDIAN=_SYS_TO_BOV_ENDIAN[sys.byteorder],
                      DATA_FORMAT=_NP_TO_BOV_TYPE[str(vals.dtype)],
                      VARIABLE=var)

        header.update(options)
        with open(bov_file, 'w') as opened_file:
            for item in header.items():
                opened_file.write('%s: %s\n' % item)

        files_written.append(bov_file)

    return files_written


class BovFile(RasterField):
    """
    >>> bov = BovFile ((400, 300), (2., 1.), (0., 0.))
    >>> x = bov.get_x_coordinates ()
    >>> y = bov.get_y_coordinates ()
    >>> (X, Y) = np.meshgrid (y[:-1], x[:-1])
    >>> z = np.sin (np.sqrt(X**2+Y**2)*np.pi/300)
    >>> bov.add_cell_data ('Elevation', z)
    >>> files = bov.tobov ('test', options=dict (TIME=1.23))
    >>> print files
    ['test_Elevation.bov']
    >>> bov.tobov ('test', no_clobber=True) # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    FileExists: test_Elevation.bov: Unable to write to file
    >>> bov.tobov ('test.txt') # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    BadFileExtension: .txt: Extension should be '.bov' or empty
    """

    def __init__(self, *args, **kwargs):
        super(BovFile, self).__init__(*args, **kwargs)
        self.attrs = {}

    def tobov(self, file, no_clobber=False, options={}):
        files_written = []
        (base, ext) = os.path.splitext(file)
        if len(ext) > 0 and ext is not '.bov':
            raise BadFileExtension(ext)

        for var in self.cell_data_vars():
            dat_file = '%s_%s.dat' % (base, var)
            bov_file = '%s_%s.bov' % (base, var)

            if no_clobber:
                if os.path.isfile(bov_file):
                    raise FileExists(bov_file)
                if os.path.isfile(dat_file):
                    raise FileExists(dat_file)

            vals = self.cell_data(var)
            vals.tofile(dat_file)

            shape = self.get_shape()
            if len(shape) < 3:
                shape = np.append(shape, [1] * (3 - len(shape)))

            origin = self.get_origin()
            if len(origin) < 3:
                origin = np.append(origin, [1.] * (3 - len(origin)))

            size = self.get_shape() * self.get_spacing()
            if len(size) < 3:
                size = np.append(size, [1.] * (3 - len(size)))

            header = dict(DATA_FILE=dat_file,
                          DATA_SIZE=array_to_str(shape),
                          BRICK_ORIGIN=array_to_str(origin),
                          BRICK_SIZE=array_to_str(size),
                          DATA_ENDIAN=_SYS_TO_BOV_ENDIAN[sys.byteorder],
                          DATA_FORMAT=_NP_TO_BOV_TYPE[str(vals.dtype)],
                          VARIABLE=var)

            header.update(options)
            with open(bov_file, 'w') as opened_file:
                for item in header.items():
                    opened_file.write('%s: %s\n' % item)

            files_written.append(bov_file)
        return files_written

    def set_attrs(self, attrs):
        self.attrs = attrs.copy()

    def get_attr(self, attr):
        return self.attrs[attr]


if __name__ == "__main__":
    import doctest
    doctest.testmod() 
