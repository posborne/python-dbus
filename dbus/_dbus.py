"""Implementation for dbus.Bus. Not to be imported directly."""

# Copyright (C) 2003, 2004, 2005, 2006 Red Hat Inc. <http://www.redhat.com/>
# Copyright (C) 2003 David Zeuthen
# Copyright (C) 2004 Rob Taylor
# Copyright (C) 2005, 2006 Collabora Ltd. <http://www.collabora.co.uk/>
#
# Licensed under the Academic Free License version 2.1
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from __future__ import generators

__all__ = ('Bus', 'SystemBus', 'SessionBus', 'StarterBus')
__docformat__ = 'reStructuredText'

import os
import sys
import weakref
from traceback import print_exc

from dbus.exceptions import DBusException
from _dbus_bindings import BUS_DAEMON_NAME, BUS_DAEMON_PATH,\
                           BUS_DAEMON_IFACE, UTF8String,\
                           validate_member_name, validate_interface_name,\
                           validate_bus_name, validate_object_path,\
                           BUS_SESSION, BUS_SYSTEM, BUS_STARTER,\
                           DBUS_START_REPLY_SUCCESS, \
                           DBUS_START_REPLY_ALREADY_RUNNING, \
                           SignalMessage,\
                           HANDLER_RESULT_NOT_YET_HANDLED,\
                           HANDLER_RESULT_HANDLED
from dbus.bus import BusConnection

try:
    import thread
except ImportError:
    import dummy_thread as thread


class Bus(BusConnection):
    """A connection to one of three possible standard buses, the SESSION,
    SYSTEM, or STARTER bus. This class manages shared connections to those
    buses.

    If you're trying to subclass `Bus`, you may be better off subclassing
    `BusConnection`, which doesn't have all this magic.
    """

    _shared_instances = {}

    def __new__(cls, bus_type=BusConnection.TYPE_SESSION, private=False,
                mainloop=None):
        """Constructor, returning an existing instance where appropriate.

        The returned instance is actually always an instance of `SessionBus`,
        `SystemBus` or `StarterBus`.

        :Parameters:
            `bus_type` : cls.TYPE_SESSION, cls.TYPE_SYSTEM or cls.TYPE_STARTER
                Connect to the appropriate bus
            `private` : bool
                If true, never return an existing shared instance, but instead
                return a private connection
            `mainloop` : dbus.mainloop.NativeMainLoop
                The main loop to use. The default is to use the default
                main loop if one has been set up, or raise an exception
                if none has been.
        :ToDo:
            - There is currently no way to connect this class to a custom
              address.
            - Some of this functionality should be available on
              peer-to-peer D-Bus connections too.
        :Changed: in dbus-python 0.80:
            converted from a wrapper around a Connection to a Connection
            subclass.
        """
        if (not private and bus_type in cls._shared_instances):
            return cls._shared_instances[bus_type]

        # this is a bit odd, but we create instances of the subtypes
        # so we can return the shared instances if someone tries to
        # construct one of them (otherwise we'd eg try and return an
        # instance of Bus from __new__ in SessionBus). why are there
        # three ways to construct this class? we just don't know.
        if bus_type == BUS_SESSION:
            subclass = SessionBus
        elif bus_type == BUS_SYSTEM:
            subclass = SystemBus
        elif bus_type == BUS_STARTER:
            subclass = StarterBus
        else:
            raise ValueError('invalid bus_type %s' % bus_type)

        bus = BusConnection.__new__(subclass, bus_type, mainloop=mainloop)

        bus._bus_type = bus_type

        if not private:
            cls._shared_instances[bus_type] = bus

        return bus

    def close(self):
        t = self._bus_type
        if self.__class__._shared_instances[t] is self:
            del self.__class__._shared_instances[t]
        super(Bus, self).close()

    def get_connection(self):
        """Return self, for backwards compatibility with earlier dbus-python
        versions where Bus was not a subclass of Connection.

        :Deprecated: since 0.80.0
        """
        return self
    _connection = property(get_connection, None, None,
                           """self._connection == self, for backwards
                           compatibility with earlier dbus-python versions
                           where Bus was not a subclass of Connection.""")

    def get_session(private=False):
        """Static method that returns a connection to the session bus.

        :Parameters:
            `private` : bool
                If true, do not return a shared connection.
        """
        return SessionBus(private=private)

    get_session = staticmethod(get_session)

    def get_system(private=False):
        """Static method that returns a connection to the system bus.

        :Parameters:
            `private` : bool
                If true, do not return a shared connection.
        """
        return SystemBus(private=private)

    get_system = staticmethod(get_system)


    def get_starter(private=False):
        """Static method that returns a connection to the starter bus.

        :Parameters:
            `private` : bool
                If true, do not return a shared connection.
        """
        return StarterBus(private=private)

    get_starter = staticmethod(get_starter)

    def __repr__(self):
        if self._bus_type == BUS_SESSION:
            name = 'session'
        elif self._bus_type == BUS_SYSTEM:
            name = 'system'
        elif self._bus_type == BUS_STARTER:
            name = 'starter'
        else:
            name = 'unknown bus type'

        return '<%s.%s (%s) at %#x>' % (self.__class__.__module__,
                                        self.__class__.__name__,
                                        name, id(self))
    __str__ = __repr__


# FIXME: Drop the subclasses here? I can't think why we'd ever want
# polymorphism
class SystemBus(Bus):
    """The system-wide message bus."""
    def __new__(cls, private=False, mainloop=None):
        """Return a connection to the system bus.

        :Parameters:
            `private` : bool
                If true, never return an existing shared instance, but instead
                return a private connection.
            `mainloop` : dbus.mainloop.NativeMainLoop
                The main loop to use. The default is to use the default
                main loop if one has been set up, or raise an exception
                if none has been.
        """
        return Bus.__new__(cls, Bus.TYPE_SYSTEM, mainloop=mainloop,
                           private=private)

class SessionBus(Bus):
    """The session (current login) message bus."""
    def __new__(cls, private=False, mainloop=None):
        """Return a connection to the session bus.

        :Parameters:
            `private` : bool
                If true, never return an existing shared instance, but instead
                return a private connection.
            `mainloop` : dbus.mainloop.NativeMainLoop
                The main loop to use. The default is to use the default
                main loop if one has been set up, or raise an exception
                if none has been.
        """
        return Bus.__new__(cls, Bus.TYPE_SESSION, private=private,
                           mainloop=mainloop)

class StarterBus(Bus):
    """The bus that activated this process (only valid if
    this process was launched by DBus activation).
    """
    def __new__(cls, private=False, mainloop=None):
        """Return a connection to the bus that activated this process.

        :Parameters:
            `private` : bool
                If true, never return an existing shared instance, but instead
                return a private connection.
            `mainloop` : dbus.mainloop.NativeMainLoop
                The main loop to use. The default is to use the default
                main loop if one has been set up, or raise an exception
                if none has been.
        """
        return Bus.__new__(cls, Bus.TYPE_STARTER, private=private,
                           mainloop=mainloop)


if 'DBUS_PYTHON_NO_DEPRECATED' not in os.environ:

    class _DBusBindingsEmulation:
        """A partial emulation of the dbus_bindings module."""
        def __str__(self):
            return '_DBusBindingsEmulation()'
        def __repr__(self):
            return '_DBusBindingsEmulation()'
        def __getattr__(self, attr):
            global dbus_bindings
            import dbus.dbus_bindings as m
            dbus_bindings = m
            return getattr(m, attr)

    dbus_bindings = _DBusBindingsEmulation()
    """Deprecated, don't use."""
