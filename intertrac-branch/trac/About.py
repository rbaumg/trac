# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2004, 2005 Edgewall Software
# Copyright (C) 2004, 2005 Jonas Borgstr�m <jonas@edgewall.com>
# Copyright (C) 2004, 2005 Daniel Lundin <daniel@edgewall.com>
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
from trac.Module import Module

class About(Module):

    about_cs = """
<?cs include "header.cs"?>
<div id="ctxtnav" class="nav">
 <h2>About Navigation</h2>
 <ul>
  <li<?cs if:!trac.acl.CONFIG_VIEW ?> class="last"<?cs /if ?>><a href="<?cs
   var:trac.href.about ?>">About Trac</a></li>
  <?cs if:trac.acl.CONFIG_VIEW ?><li class="last"><a href="<?cs
   var:trac.href.about_config ?>">View Config</a></li>
  <?cs /if ?>
 </ul>
</div>
<div id="content" class="about">
 <?cs if about.page == "config"?>
  <h3>Configuration</h3>
  <table>
  <tr><th>Section</th><th>Name</th><th>Value</th></tr>
  <?cs each:item = about.config ?>
    <tr>
      <td><?cs var:item.section ?></td>
      <td><?cs var:item.name ?></td>
      <td><?cs var:item.value ?></td>
    </tr>
  <?cs /each ?>
  </table>
 <?cs else ?>
  <a href="http://trac.edgewall.com" style="border: none; float: right; margin-left: 2em">
   <img style="display: block" src="<?cs var:htdocs_location ?>trac_banner.png"
     alt="Trac: Integrated SCM &amp; Project Management"/>
  </a>
<h1>About Trac <?cs var:trac.version ?></h1>
<p>
Trac is a web-based software project management and bug/issue
tracking system emphasizing ease of use and low ceremony. 
It provides an interface to the Subversion revision control systems, integrated Wiki and convenient report facilities. 
</p>
  <p>
  Trac is distributed under the GNU General Public License (GPL).<br />
  The entire text of the license should be found in the COPYING file,
  included in the package.
    </p>
  <p>
  Please visit the Trac open source project: 
  <a href="http://projects.edgewall.com/trac/">http://projects.edgewall.com/trac/</a>
  </p>
  <p>
  Trac is a product of <a href="http://www.edgewall.com/">Edgewall Software</a>, provider of professional Linux and software development services.
  </p>
<p>
Copyright &copy; 2003,2004 <a href="http://www.edgewall.com/">Edgewall Software</a>
</p>
  <a href="http://www.edgewall.com/">
   <img style="display: block; margin: 30px" src="<?cs var:htdocs_location ?>edgewall.png"
     alt="Edgewall Software"/></a>
 <?cs /if ?>
</div>
<?cs include "footer.cs"?>
""" # about_cs

    def render(self, req):
        page = req.args.get('page', 'default')
        req.hdf['title'] = 'About Trac'
        if page[0:7] == 'config':
            self.perm.assert_permission(perm.CONFIG_VIEW)
            req.hdf['about.page'] = 'config'
            # Export the config table to hdf
            sections = []
            for section in self.env.cfg.sections():
                for name in self.env.cfg.options(section):
                    value = self.env.get_config(section, name)
                    sections.append({'section': section, 'name': name,
                                     'value': value})
            req.hdf['about.config'] = sections
            # TODO:
            # We should probably export more info here like:
            # permissions, components...

        template = req.hdf.parse(self.about_cs)
        req.display(template)
