import unittest

from Query import Query
from environment import EnvironmentTestBase

class QueryTestCase(EnvironmentTestBase, unittest.TestCase):

    def test_all_ordered_by_id(self):
        query = Query(self.env, order='id')
        sql = query.to_sql()
        self.assertEqual(sql,
"""SELECT id,summary,status,owner,priority,milestone,component
FROM ticket
ORDER BY IFNULL(id,'')='',id""")

    def test_all_ordered_by_id_desc(self):
        query = Query(self.env, order='id', desc=1)
        sql = query.to_sql()
        self.assertEqual(sql,
"""SELECT id,summary,status,owner,priority,milestone,component
FROM ticket
ORDER BY IFNULL(id,'')='' DESC,id DESC""")

    def test_all_ordered_by_priority(self):
        query = Query(self.env) # priority is default order
        sql = query.to_sql()
        self.assertEqual(sql,
"""SELECT id,summary,priority,status,owner,milestone,component
FROM ticket
  LEFT OUTER JOIN (SELECT name AS priority_name, value AS priority_value FROM enum WHERE type='priority') ON priority_name=priority
ORDER BY IFNULL(priority,'')='',priority_value,id""")

    def test_all_ordered_by_priority_desc(self):
        query = Query(self.env, desc=1) # priority is default order
        sql = query.to_sql()
        self.assertEqual(sql,
"""SELECT id,summary,priority,status,owner,milestone,component
FROM ticket
  LEFT OUTER JOIN (SELECT name AS priority_name, value AS priority_value FROM enum WHERE type='priority') ON priority_name=priority
ORDER BY IFNULL(priority,'')='' DESC,priority_value DESC,id""")

    def test_all_ordered_by_version(self):
        query = Query(self.env, order='version')
        sql = query.to_sql()
        self.assertEqual(sql,
"""SELECT id,summary,version,status,owner,priority,milestone
FROM ticket
  LEFT OUTER JOIN (SELECT name AS version_name, time AS version_time FROM version) ON version_name=version
ORDER BY IFNULL(version,'')='',IFNULL(version_time,0)=0,version_time,version,id""")

    def test_all_ordered_by_version_desc(self):
        query = Query(self.env, order='version', desc=1)
        sql = query.to_sql()
        self.assertEqual(sql,
"""SELECT id,summary,version,status,owner,priority,milestone
FROM ticket
  LEFT OUTER JOIN (SELECT name AS version_name, time AS version_time FROM version) ON version_name=version
ORDER BY IFNULL(version,'')='' DESC,IFNULL(version_time,0)=0 DESC,version_time DESC,version DESC,id""")

    def test_constrained_by_milestone(self):
        query = Query(self.env, order='id')
        query.constraints['milestone'] = ['milestone1']
        sql = query.to_sql()
        self.assertEqual(sql,
"""SELECT id,summary,status,owner,priority,component,version
FROM ticket
WHERE IFNULL(milestone,'')='milestone1'
ORDER BY IFNULL(id,'')='',id""")

    def test_constrained_by_status(self):
        query = Query(self.env, order='id')
        query.constraints['status'] = ['new', 'assigned', 'reopened']
        sql = query.to_sql()
        self.assertEqual(sql,
"""SELECT id,summary,status,owner,priority,milestone,component
FROM ticket
WHERE status IN ('new','assigned','reopened')
ORDER BY IFNULL(id,'')='',id""")

def suite():
    return unittest.makeSuite(QueryTestCase, 'test')
