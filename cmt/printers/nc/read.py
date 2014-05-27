#! /usr/bin/env python

from .constants import open_netcdf
from .ugrid_read import (NetcdfRectilinearFieldReader,
                         NetcdfStructuredFieldReader,
                         NetcdfUnstructuredFieldReader, )
from cmt.grids.grid_type import (GridTypeRectilinear, GridTypeStructured,
                                 GridTypeUnstructured, )


_NETCDF_MESH_TYPE = {
    'rectilinear': GridTypeRectilinear(),
    'structured': GridTypeStructured(),
    'unstructured': GridTypeUnstructured(),
}

_NETCDF_READERS = {
    'rectilinear': NetcdfRectilinearFieldReader,
    'structured': NetcdfStructuredFieldReader,
    'unstructured': NetcdfUnstructuredFieldReader,
}


def query_netcdf_mesh_type(path, format='NETCDF4'):
    root = open_netcdf(path, mode='r', format=format)

    try:
        type_string = root.variables['mesh'].type
    except AttributeError:
        raise AttributeError('netcdf file is missing type attribute')
    except KeyError:
        raise AttributeError('netcdf file is missing mesh attribute')
    finally:
        root.close()

    try:
        mesh_type = _NETCDF_MESH_TYPE[type_string]
    except KeyError:
        raise TypeError('%s: mesh type not understood' % mesh_type)

    return mesh_type


def field_fromfile(path, format='NETCDF4'):
    mesh_type = query_netcdf_mesh_type(path)

    try:
        reader = _NETCDF_READERS[str(mesh_type)]
    except KeyError:
        raise TypeError('%s: no reader available for file' % mesh_type)
    else:
        nc_file = reader(path, format=format)

    if len(nc_file._time) > 0:
        return (nc_file._field, nc_file._time)
    else:
        return nc_file._field
