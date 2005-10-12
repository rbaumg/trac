# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Edgewall Software
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.com/license.html.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://projects.edgewall.com/trac/.
#
# Author: Christopher Lenz <cmlenz@gmx.de>

import inspect
import os
import shutil
import sys

from trac import ticket, util, __version__ as TRAC_VERSION
from trac.core import *
from webadmin.web_ui import IAdminPageProvider

try:
    import pkg_resources
except ImportError:
    pkg_resources = None

__all__ = []

def _find_base_path(path, module_name):
    base_path = os.path.splitext(path)[0]
    while base_path.replace(os.sep, '.').endswith(module_name):
        base_path = os.path.dirname(base_path)
        module_name = '.'.join(module_name.split('.')[:-1])
        if not module_name:
            break
    return base_path

TRAC_PATH = _find_base_path(sys.modules['trac.core'].__file__, 'trac.core')

# Ideally, this wouldn't be hard-coded like this
required_components = ('AboutModule', 'DefaultPermissionGroupProvider',
    'Environment', 'EnvironmentSetup', 'PermissionSystem', 'RequestDispatcher',
    'Mimeview', 'Chrome')


class PluginAdminPage(Component):

    implements(IAdminPageProvider)

    # IAdminPageProvider methods

    def get_admin_pages(self, req):
        if req.perm.has_permission('TRAC_ADMIN'):
            yield ('general', 'General', 'plugin', 'Plugins')

    def process_admin_request(self, req, cat, page, _):
        req.perm.assert_permission('TRAC_ADMIN')

        if req.method == 'POST':
            if req.args.has_key('update'):
                self._do_update(req)
            elif req.args.has_key('install'):
                self._do_install(req)
            elif req.args.has_key('uninstall'):
                self._do_uninstall(req)
            else:
                self.log.warning('Unknown POST request: %s', req.args)
            anchor = ''
            if req.args.has_key('plugin'):
                anchor = '#no' + req.args.get('plugin')
            req.redirect(self.env.href.admin(cat, page) + anchor)

        self._render_view(req)
        return 'admin_plugin.cs', None

    # Internal methods

    def _do_install(self, req):
        """Install a plugin."""
        if not req.args.has_key('egg_file'):
            raise TracError, 'No file uploaded'
        upload = req.args['egg_file']
        if not upload.filename:
            raise TracError, 'No file uploaded'
        egg_filename = upload.filename.replace('\\', '/').replace(':', '/')
        egg_filename = os.path.basename(egg_filename)
        if not egg_filename:
            raise TracError, 'No file uploaded'
        if not egg_filename.endswith('.egg'):
            raise TracError, 'Uploaded file is not a python egg'

        target_path = os.path.join(self.env.path, 'plugins', egg_filename)
        if os.path.isfile(target_path):
            raise TracError, 'Plugin %s already installed' % egg_filename

        self.log.info('Installing plugin %s', egg_filename)
        flags = os.O_CREAT + os.O_WRONLY + os.O_EXCL
        try:
            flags += os.O_BINARY
        except AttributeError:
            # OS_BINARY not available on every platform
            pass
        target_file = os.fdopen(os.open(target_path, flags), 'w')
        try:
            shutil.copyfileobj(upload.file, target_file)
            self.log.info('Plugin installed to %s', egg_filename, target_path)
        finally:
            target_file.close()

        # TODO: Validate that the uploaded file is actually a valid Trac plugin

    def _do_uninstall(self, req):
        """Uninstall a plugin."""
        egg_filename = req.args.get('egg_filename')
        if not egg_filename:
            return
        egg_path = os.path.join(self.env.path, 'plugins', egg_filename)
        if not os.path.isfile(egg_path):
            return
        self.log.info('Uninstalling plugin %s', egg_filename)
        os.remove(egg_path)

    def _do_update(self, req):
        """Update component enablement."""
        components = req.args.getlist('component')
        enabled = req.args.getlist('enable')
        changes = False

        # FIXME: this needs to be more intelligent and minimize multiple
        # component names to prefix rules

        for component in components:
            is_enabled = self.env.is_component_enabled(component)
            if is_enabled != (component in enabled):
                self.config.set('components', component,
                                is_enabled and 'disabled' or 'enabled')
                self.log.info('%sabling component %s',
                              is_enabled and 'Dis' or 'En', component)
                changes = True

        if changes:
            self.config.save()

    def _render_view(self, req):
        plugins = {}
        plugins_dir = os.path.join(self.env.path, 'plugins')

        from trac.core import ComponentMeta
        for component in ComponentMeta._components:
            module = sys.modules[component.__module__]

            # Determine the plugin that this component belongs to
            path = module.__file__
            if path.endswith('pyc') or path.endswith('pyo'):
                path = path[:-1]
            path = _find_base_path(path, module.__name__)
            egg_filename = None
            if path == TRAC_PATH:
                category = 'Trac'
                version = TRAC_VERSION
            else:
                category = None
                version = None
                if pkg_resources is not None:
                    dist = pkg_resources.Distribution.from_filename(path)
                    # FIXME: how to way to check for a valid Distribution object
                    if hasattr(dist, 'name'):
                        category = dist.name
                        version = dist.version
                        if os.path.dirname(path) == plugins_dir:
                            egg_filename = os.path.basename(path)
                if category is None:
                    category = os.path.basename(path)

            description = inspect.getdoc(component)
            if description:
                description = description.split('.', 1)[0] + '.'

            if not category in plugins:
                plugins[category] = {'name': category, 'version': version,
                                     'components': [], 'path': path,
                                     'egg_filename': egg_filename}
            plugins[category]['components'].append({
                'name': component.__name__, 'module': module.__name__,
                'description': util.escape(description, quotes=True),
                'enabled': self.env.is_component_enabled(component),
                'required': component.__name__ in required_components
            })

        def component_order(a, b):
            c = cmp(len(a['module'].split('.')), len(b['module'].split('.')))
            if c == 0:
                c = cmp(a['module'].lower(), b['module'].lower())
                if c == 0:
                    c = cmp(a['name'].lower(), b['name'].lower())
            return c
        for category in plugins:
            plugins[category]['components'].sort(component_order)

        req.hdf['title'] = 'Manage Plugins'
        req.hdf['admin.plugins.0'] = plugins['Trac']
        addons = [key for key in plugins.keys() if key != 'Trac']
        addons.sort()
        for idx, category in enumerate(addons):
            req.hdf['admin.plugins.%s' % (idx + 1)] = plugins[category]
