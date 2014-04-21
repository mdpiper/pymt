import os
import numpy as np
from numpy.testing import assert_array_equal
from nose.tools import assert_equal, assert_false, assert_almost_equal

from cmt.events.manager import EventManager
from cmt.events.port import PortMapEvent, PortEvent
from cmt.events.chain import ChainEvent
from cmt.testing.assertions import assert_isfile_and_remove

from cmt.testing import services


def assert_port_value_equal(port, name, value):
    assert_array_equal(port.get_grid_values(name), value)


def test_one_event():
    foo = PortMapEvent(src_port='air_port', dst_port='earth_port',
                       vars_to_map=[('earth_surface__temperature',
                                     'air__density'), ])

    foo._src.initialize()
    foo._dst.initialize()

    with EventManager(((foo, 1.), )) as mngr:
        assert_port_value_equal(foo._src, 'air__density', 0.)
        assert_port_value_equal(foo._dst, 'earth_surface__temperature', 0.)


def test_chain():
    air = services.get_port('air_port')
    earth = services.get_port('earth_port')

    foo = ChainEvent(
        [
            PortEvent(port=air),
            PortMapEvent(dst_port=air, src_port=earth,
                         vars_to_map=[('air__density',
                                       'earth_surface__temperature'),
                                     ]),
        ]
    )

    bar = PortEvent(port=earth)

    with EventManager(((foo, 1.), (bar, 1.2), )) as mngr:
        assert_port_value_equal(bar._port, 'earth_surface__temperature', 0.)
        assert_port_value_equal(air, 'air__density', 0.)

        mngr.run(1.)
        assert_port_value_equal(earth, 'earth_surface__temperature', 0.)
        assert_port_value_equal(air, 'air__density', 0.)

        mngr.run(2.)
        assert_port_value_equal(air, 'air__density', 1.2)
