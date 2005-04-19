# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004 Edgewall Software
# Copyright (C) 2003, 2004 Jonas Borgstr�m <jonas@edgewall.com>
#
# Trac is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Trac is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Author: Jonas Borgstr�m <jonas@edgewall.com>

from trac import perm
from trac.core import *
from trac.util import TracError, escape, shorten_line
from trac.versioncontrol.svn_authz import SubversionAuthorizer
from trac.web.main import add_link

import re
import time
import string


class SearchModule(Component):

    extends('RequestDispatcher.handlers')

    RESULTS_PER_PAGE = 10

    def query_to_sql(self, q, name):
        self.log.debug("Query: %s" % q)
        if q[0] == q[-1] == "'" or q[0] == q[-1] == '"':
            sql_q = "%s LIKE '%%%s%%'" % (name, q[1:-1].replace("'''", "''"))
        else:
            q = q.replace('\'', '\'\'')
            keywords = q.split(' ')
            x = map(lambda x, name=name: name + ' LIKE \'%' + x + '%\'', keywords)
            sql_q = string.join(x, ' AND ')
        self.log.debug("SQL Condition: %s" % sql_q)
        return sql_q

    def shorten_result(self, text='', keywords=[], maxlen=240, fuzz=60):
        if not text: text = ''
        text_low = text.lower()
        beg = -1
        for k in keywords:
            i = text_low.find(k.lower())
            if (i > -1 and i < beg) or beg == -1:
                beg = i
        excerpt_beg = 0
        if beg > fuzz:
            for sep in ('.', ':', ';', '='):
                eb = text.find(sep, beg - fuzz, beg - 1)
                if eb > -1:
                    eb += 1
                    break
            else:
                eb = beg - fuzz
            excerpt_beg = eb
        if excerpt_beg < 0: excerpt_beg = 0
        msg = text[excerpt_beg:beg+maxlen]
        if beg > fuzz:
            msg = '... ' + msg
        if beg < len(text)-maxlen:
            msg = msg + ' ...'
        return msg
    
    def perform_query(self, req, query, changeset, tickets, wiki, page=0):
        if not query:
            return ([], 0)
        keywords = query.split(' ')

        if changeset:
            changeset = req.perm.has_permission(perm.CHANGESET_VIEW)
        if tickets:
            tickets = req.perm.has_permission(perm.TICKET_VIEW)
        if wiki:
            wiki = req.perm.has_permission(perm.WIKI_VIEW)

        if changeset == tickets == wiki == 0:
            return ([], 0)

        if len(keywords) == 1:
            kwd = keywords[0]
            redir = None
            # Prepending a '!' disables quickjump feature
            if kwd[0] == '!':
                keywords[0] = kwd[1:]
                query = query[1:]
                req.hdf['search.q'] = query
            # Ticket quickjump
            elif kwd[0] == '#' and kwd[1:].isdigit():
                redir = self.env.href.ticket(kwd[1:])
            elif kwd[0:len('ticket:')] == 'ticket:' and kwd[len('ticket:'):].isdigit():
                redir = self.env.href.ticket(kwd[len('ticket:'):])
            elif kwd[0:len('bug:')] == 'bug:' and kwd[len('bug:'):].isdigit():
                redir = self.env.href.ticket(kwd[len('bug:'):])
            # Changeset quickjump
            elif kwd[0] == '[' and kwd[-1] == ']' and kwd[1:-1].isdigit():
                redir = self.env.href.changeset(kwd[1:-1])
            elif kwd[0:len('changeset:')] == 'changeset:' and kwd[len('changeset:'):].isdigit():
                redir = self.env.href.changeset(kwd[len('changeset:'):])
            # Report quickjump
            elif kwd[0] == '{' and kwd[-1] == '}' and kwd[1:-1].isdigit():
                redir = self.env.href.report(kwd[1:-1])
            elif kwd[0:len('report:')] == 'report:' and kwd[len('report:'):].isdigit():
                redir = self.env.href.report(kwd[len('report:'):])
            # Milestone quickjump
            elif kwd[0:len('milestone:')] == 'milestone:':
                redir = self.env.href.milestone(kwd[len('milestone:'):])
            # Source quickjump
            elif kwd[0:len('source:')] == 'source:':
                redir = self.env.href.browser(kwd[len('source:'):])
            # Wiki quickjump
            elif kwd[0:len('wiki:')] == 'wiki:':
                r = "((^|(?<=[^A-Za-z]))[!]?[A-Z][a-z/]+(?:[A-Z][a-z/]+)+)"
                if re.match (r, kwd[len('wiki:'):]):
                    redir = self.env.href.wiki(kwd[len('wiki:'):])
            elif kwd[0].isupper() and kwd[1].islower():
                r = "((^|(?<=[^A-Za-z]))[!]?[A-Z][a-z/]+(?:[A-Z][a-z/]+)+)"
                if re.match (r, kwd):
                    redir = self.env.href.wiki(kwd)
            if redir:
                req.hdf['search.q'] = ''
                req.redirect(redir)
            elif len(query) < 3:
                raise TracError('Search query too short. '
                                'Query must be at least 3 characters long.',
                                'Search Error')

        db = self.env.get_db_cnx()
        cursor = db.cursor()

        q = []
        if changeset:
            q.append("SELECT 1 as type, message AS title, message, author, "
                     "'' AS keywords, rev AS data, time,0 AS ver "
                     "FROM revision WHERE %s OR %s" %
                     (self.query_to_sql(query, 'message'),
                      self.query_to_sql(query, 'author')))
        if tickets:
            q.append("SELECT DISTINCT 2 as type, a.summary AS title, "
                     "a.description AS message, a.reporter AS author, "
                     "a.keywords as keywords, a.id AS data, a.time as time, 0 AS ver "
                     "FROM ticket a LEFT JOIN ticket_change b ON a.id = b.ticket "
                     "WHERE (b.field='comment' AND %s ) OR "
                     "%s OR %s OR %s OR %s OR %s" %
                     (self.query_to_sql(query, 'b.newvalue'),
                      self.query_to_sql(query, 'summary'),
                      self.query_to_sql(query, 'keywords'),
                      self.query_to_sql(query, 'description'),
                      self.query_to_sql(query, 'reporter'),
                      self.query_to_sql(query, 'cc')))
        if wiki:
            q.append("SELECT 3 as type, text AS title, text AS message,"
                     "author, '' AS keywords, w1.name AS data, time,"
                     "w1.version as ver "
                     "FROM wiki w1,"
                     "(SELECT name,max(version) AS ver "
                     "FROM wiki GROUP BY name) w2 "
                     "WHERE w1.version = w2.ver AND w1.name = w2.name  AND "
                     "(%s OR %s OR %s)" %
                     (self.query_to_sql(query, 'w1.name'),
                      self.query_to_sql(query, 'w1.author'),
                      self.query_to_sql(query, 'w1.text')))

        if not q:
            return [], 0

        q_str = ' UNION ALL '.join(q) + ' ORDER BY 7 DESC LIMIT %d OFFSET %d' \
                % (self.RESULTS_PER_PAGE + 1, self.RESULTS_PER_PAGE * page)
        self.log.debug('SQL Query: %s' % q_str)
        cursor.execute(q_str)

        # Make the data more HDF-friendly
        info = []
        more = 0
        while 1:
            row = cursor.fetchone()
            if not row:
                break
            if len(info) == self.RESULTS_PER_PAGE:
                more = 1
                break
            msg = row['message']
            t = time.localtime(int(row['time']))
            item = {'type': int(row['type']),
                    'keywords': row['keywords'] or '',
                    'data': row['data'],
                    'title': escape(row['title'] or ''),
                    'datetime' : time.strftime('%c', t),
                    'author': escape(row['author'])}
            if item['type'] == 1:
                item['changeset_href'] = self.env.href.changeset(int(row['data']))
                if not self.authzperm.has_permission_for_changeset(int(row['data'])):
                    continue
            elif item['type'] == 2:
                item['ticket_href'] = self.env.href.ticket(int(row['data']))
            elif item['type'] == 3:
                item['wiki_href'] = self.env.href.wiki(row['data'])

            item['shortmsg'] = escape(shorten_line(msg))
            item['message'] = escape(self.shorten_result(msg, keywords))
            info.append(item)
        return info, more

    def match_request(self, req):
        return req.path_info == '/search'

    def process_request(self, req):
        req.perm.assert_permission(perm.SEARCH_VIEW)
        self.authzperm = SubversionAuthorizer(self.env, req.authname)

        req.hdf['title'] = 'Search'
        req.hdf['search'] = {
            'ticket': 'checked',
            'changeset': 'checked',
            'wiki': 'checked',
            'results_per_page': self.RESULTS_PER_PAGE
        }

        if req.args.has_key('q'):
            query = req.args.get('q')
            req.hdf['title'] = 'Search Results'
            req.hdf['search.q'] = query.replace('"', "&#34;")
            tickets = req.args.has_key('ticket')
            changesets = req.args.has_key('changeset')
            wiki = req.args.has_key('wiki')

            # If no search options chosen, choose all
            if not (tickets or changesets or wiki):
                tickets = changesets = wiki = 1
            if not tickets:
                req.hdf['search.ticket'] = ''
            if not changesets:
                req.hdf['search.changeset'] = ''
            if not wiki:
                req.hdf['search.wiki'] = ''

            page = int(req.args.get('page', '0'))
            req.hdf['search.result_page'] = page
            info, more = self.perform_query(req, query, changesets, tickets,
                                            wiki, page)
            req.hdf['search.result'] = info

            params = [('q', query)]
            if tickets: params.append(('ticket', 'on'))
            if changesets: params.append(('changeset', 'on'))
            if wiki: params.append(('wiki', 'on'))
            if page:
                add_link(req, 'first', self.env.href.search(params, page=0))
                add_link(req, 'prev', self.env.href.search(params, page=page - 1))
            if more:
                add_link(req, 'next', self.env.href.search(params, page=page + 1))

        req.display('search.cs')
