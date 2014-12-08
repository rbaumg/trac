# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Edgewall Software
# Copyright (C) 2010 Robert Corsaro
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.org/wiki/TracLicense.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/log/.

from datetime import datetime
from trac.util.datefmt import utc, to_utimestamp

__all__ = ['Subscription']



class Subscription(object):

    __slots__ = ('env', 'values')

    fields = ('id', 'sid', 'authenticated', 'distributor', 'format',
              'priority', 'adverb', 'class')

    def __init__(self, env):
        self.env = env
        self.values = {}

    def __getitem__(self, name):
        if name not in self.fields:
            raise KeyError(name)
        return self.values.get(name)

    def __setitem__(self, name, value):
        if name not in self.fields:
            raise KeyError(name)
        self.values[name] = value

    def _from_database(self, id, sid, authenticated, distributor, format,
                       priority, adverb, class_):
        self['id'] = id
        self['sid'] = sid
        self['authenticated'] = int(authenticated)
        self['distributor'] = distributor
        self['format'] = format
        self['priority'] = int(priority)
        self['adverb'] = adverb
        self['class'] = class_

    @classmethod
    def add(cls, env, subscription):
        """id and priority overwritten."""
        with env.db_transaction as db:
            priority = len(cls.find_by_sid_and_distributor(
                env, subscription['sid'], subscription['authenticated'],
                subscription['distributor'])) + 1
            now = to_utimestamp(datetime.now(utc))
            db("""
                INSERT INTO notify_subscription (time, changetime, sid,
                                                 authenticated, distributor,
                                                 format, priority, adverb,
                                                 class)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (now, now, subscription['sid'], int(subscription['authenticated']),
             subscription['distributor'], subscription['format'],
             int(priority), subscription['adverb'],
             subscription['class']))

    @classmethod
    def delete(cls, env, rule_id):
        with env.db_transaction as db:
            cursor = db.cursor()
            cursor.execute("SELECT sid, authenticated, distributor "
                           "FROM notify_subscription WHERE id=%s",
                           (rule_id,))
            sid, authenticated, distributor = cursor.fetchone()
            cursor.execute("DELETE FROM notify_subscription WHERE id = %s""",
                           (rule_id,))
            i = 1
            for s in cls.find_by_sid_and_distributor(env, sid, authenticated,
                                                     distributor):
                s['priority'] = i
                s._update_priority()
                i += 1

    @classmethod
    def move(cls, env, rule_id, priority):
        with env.db_transaction as db:
            cursor = db.cursor()
            cursor.execute("""
                SELECT sid, authenticated, distributor
                  FROM notify_subscription
                 WHERE id=%s
            """, (rule_id,))
            sid, authenticated, distributor = cursor.fetchone()
            subs = cls.find_by_sid_and_distributor(env, sid, authenticated,
                                                   distributor)
            if priority > len(subs):
                return
            i = 1
            for s in subs:
                if int(s['id']) == int(rule_id):
                    s['priority'] = priority
                    s._update_priority()
                    i -= 1
                elif i == priority:
                    i += 1
                    s['priority'] = i
                    s._update_priority()
                else:
                    s['priority'] = i
                    s._update_priority()
                i += 1

    @classmethod
    def update_format_by_distributor_and_sid(cls, env, distributor, sid,
                                             authenticated, format):
        with env.db_transaction as db:
            db("""
                UPDATE notify_subscription
                   SET format=%s
                 WHERE distributor=%s
                   AND sid=%s
                   AND authenticated=%s
            """, (format, distributor, sid, int(authenticated)))

    @classmethod
    def _find(cls, env, order=None, **kwargs):
        with env.db_query as db:
            conditions = []
            args = []
            for name, value in sorted(kwargs.iteritems()):
                if name.endswith('_'):
                    name = name[:-1]
                conditions.append(db.quote(name) + '=%s')
                args.append(value)
            query = 'SELECT id, sid, authenticated, distributor, format, ' \
                    'priority, adverb, class FROM notify_subscription'
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
            if order:
                if not isinstance(order, (tuple, list)):
                    order = (order,)
                query += ' ORDER BY ' + \
                         ', '.join(db.quote(name) for name in order)
            cursor = db.cursor()
            cursor.execute(query, args)
            for row in cursor:
                sub = Subscription(env)
                sub._from_database(*row)
                yield sub

    @classmethod
    def find_by_sid_and_distributor(cls, env, sid, authenticated, distributor):
        return list(cls._find(env, sid=sid, authenticated=int(authenticated),
                              distributor=distributor, order='priority'))

    @classmethod
    def find_by_sids_and_class(cls, env, uids, klass):
        """uids should be a collection to tuples (sid, auth)"""
        subs = []
        for sid, authenticated in uids:
            subs.extend(cls._find(env, class_=klass, sid=sid,
                                  authenticated=int(authenticated),
                                  order='priority'))
        return subs

    @classmethod
    def find_by_class(cls, env, klass):
        return list(cls._find(env, class_=klass))

    def subscription_tuple(self):
        return (
            self.values['class'],
            self.values['distributor'],
            self.values['sid'],
            self.values['authenticated'],
            None,
            self.values['format'],
            int(self.values['priority']),
            self.values['adverb']
        )

    def _update_priority(self):
        with self.env.db_transaction as db:
            cursor = db.cursor()
            now = to_utimestamp(datetime.now(utc))
            cursor.execute("""
                UPDATE notify_subscription
                   SET changetime=%s, priority=%s
                 WHERE id=%s
            """, (now, int(self.values['priority']), self.values['id']))
