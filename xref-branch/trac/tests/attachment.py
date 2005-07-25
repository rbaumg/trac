from trac.object import TracObject
from trac.attachment import Attachment
from trac.config import Configuration
from trac.log import logger_factory
from trac.test import EnvironmentStub, Mock

import os
import os.path
import shutil
import tempfile
import unittest


class AttachmentTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        self.env.path = os.path.join(tempfile.gettempdir(), 'trac-tempenv')
        os.mkdir(self.env.path)
        self.attachments_dir = os.path.join(self.env.path, 'attachments')
        self.env.config.setdefault('attachment', 'max_size', 512)

        self.perm = Mock(assert_permission=lambda x: None,
                         has_permission=lambda x: True)

    def tearDown(self):
        shutil.rmtree(self.env.path)

    def test_get_path(self):
        attachment = Attachment(TracObject.factory(self.env, 'ticket', '42'))
        attachment.filename = 'foo.txt'
        self.assertEqual(os.path.join(self.attachments_dir, 'ticket', '42',
                                      'foo.txt'),
                         attachment.path)
        attachment = Attachment(TracObject.factory(self.env,
                                                   'wiki', 'SomePage'))
        attachment.filename = 'bar.jpg'
        self.assertEqual(os.path.join(self.attachments_dir, 'wiki', 'SomePage',
                                      'bar.jpg'),
                         attachment.path)

    def test_get_path_encoded(self):
        attachment = Attachment(TracObject.factory(self.env, 'ticket', '42'))
        attachment.filename = 'Teh foo.txt'
        self.assertEqual(os.path.join(self.attachments_dir, 'ticket', '42',
                                      'Teh%20foo.txt'),
                         attachment.path)
        attachment = Attachment(TracObject.factory(self.env,
                                                   'wiki', '\xdcberSicht'))
        attachment.filename = 'Teh bar.jpg'
        self.assertEqual(os.path.join(self.attachments_dir, 'wiki',
                                      '%DCberSicht', 'Teh%20bar.jpg'),
                         attachment.path)

    def test_select_empty(self):
        self.assertRaises(StopIteration,
                          Attachment.select(TracObject.factory(self.env,
                                                               'ticket', '42')).next)
        self.assertRaises(StopIteration,
                          Attachment.select(TracObject.factory(self.env,
                                                               'wiki', 'SomePage')).next)

    def test_insert(self):
        attachment = Attachment(TracObject.factory(self.env, 'ticket', '42'))
        attachment.insert('foo.txt', tempfile.TemporaryFile(), 0)
        attachment = Attachment(TracObject.factory(self.env, 'ticket', '42'))
        attachment.insert('bar.jpg', tempfile.TemporaryFile(), 0)

        attachments = Attachment.select(TracObject.factory(self.env,
                                                           'ticket', '42'))
        self.assertEqual('foo.txt', attachments.next().filename)
        self.assertEqual('bar.jpg', attachments.next().filename)
        self.assertRaises(StopIteration, attachments.next)

    def test_insert_unique(self):
        attachment = Attachment(TracObject.factory(self.env, 'ticket', '42'))
        attachment.insert('foo.txt', tempfile.TemporaryFile(), 0)
        self.assertEqual('foo.txt', attachment.filename)
        attachment = Attachment(TracObject.factory(self.env, 'ticket', '42'))
        attachment.insert('foo.txt', tempfile.TemporaryFile(), 0)
        self.assertEqual('foo.2.txt', attachment.filename)

    def test_insert_outside_attachments_dir(self):
        attachment = Attachment(TracObject.factory(self.env,
                                                   '../../../../../sth/private',
                                                   '42')) # still relevant?
        self.assertRaises(AssertionError, attachment.insert, 'foo.txt',
                          tempfile.TemporaryFile(), 0)

    def test_delete(self):
        attachment1 = Attachment(TracObject.factory(self.env,
                                                    'wiki', 'SomePage'))
        attachment1.insert('foo.txt', tempfile.TemporaryFile(), 0)
        attachment2 = Attachment(TracObject.factory(self.env,
                                                    'wiki', 'SomePage'))
        attachment2.insert('bar.jpg', tempfile.TemporaryFile(), 0)

        attachments = Attachment.select(TracObject.factory(self.env,
                                                           'wiki', 'SomePage'))
        self.assertEqual(2, len(list(attachments)))

        attachment1.delete()
        attachment2.delete()

        assert not os.path.exists(attachment1.path)
        assert not os.path.exists(attachment2.path)

        attachments = Attachment.select(TracObject.factory(self.env,
                                                           'wiki', 'SomePage'))
        self.assertEqual(0, len(list(attachments)))

    def test_delete_file_gone(self):
        """
        Verify that deleting an attachment works even if the referenced file
        doesn't exist for some reason.
        """
        attachment = Attachment(TracObject.factory(self.env,
                                                   'wiki', 'SomePage'))
        attachment.insert('foo.txt', tempfile.TemporaryFile(), 0)
        os.unlink(attachment.path)

        attachment.delete()


def suite():
    return unittest.makeSuite(AttachmentTestCase, 'test')

if __name__ == '__main__':
    unittest.main()
