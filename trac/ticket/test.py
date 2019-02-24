# -*- coding: utf-8 -*-
#
# Copyright (C) 2017-2019 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.org/wiki/TracLicense.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/log/.

from trac.ticket.model import Ticket


def insert_ticket(env, **props):
    """Insert a ticket to the database with properties specified in the
    keyword arguments. The creation time can be specified as a timestamp
    in the `when` argument.
    """
    when = props.pop('when', None)
    ticket = Ticket(env)
    for k, v in props.items():
        ticket[k] = v
    ticket.insert(when)
    return ticket
