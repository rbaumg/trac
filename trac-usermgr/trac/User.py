# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2004 Edgewall Software
# Copyright (C) 2004 Jonas Borgström <jonas@edgewall.com>
# Copyright (C) 2004 Daniel Lundin <daniel@edgewall.com>
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
# Author: Jonas Borgström <jonas@edgewall.com>

import util
import perm
import Href
from Module import Module
from WikiFormatter import wiki_to_html
import neo_cgi
import neo_cs

class User (Module):
    template_name = ''

    about_cs = """
<?cs include "header.cs"?>
<div id="ctxtnav" class="nav">
 <ul>
 <li>Modify</li>
 <li class="last">Delete</li>
 </ul>
</div>
    
<br/>
<h1>About <?cs var:user.name ?></h1>
<p>
<strong>Email</strong> : <a href="<?cs var:user.email ?>"><?cs var:user.email ?></a><br/>
<strong>Username</strong>  : <?cs var:user.username ?><br/>
<strong>Team</strong>  : <?cs var:user.team ?><br/>
<strong>Role</strong>  : <?cs var:user.role ?><br/>
</p>
<p>
<?cs var:user.desc ?>
</p>
<h2>Assigned tickets</h2>
 <?cs each:ticket = user.tickets ?>
 <a href="<?cs var:ticket.href ?>"><?cs var:ticket.id ?> </a> )
 <?cs var:ticket.summary ?> 
 <br/>
 <?cs /each ?>
 <br/>
<?cs include "footer.cs"?>
""" # about_cs
    
    
    def render (self):	

	cursor = self.db.cursor ()
	user = self.args.get('user', '')	  
	
	cursor.execute ('SELECT username, name, email, role, desc, team FROM user '
	                'WHERE username = %s', user) 
	row = cursor.fetchone()
	
	self.req.hdf.setValue('user.username', row[0])	 
	self.req.hdf.setValue('user.name', row[1])
	self.req.hdf.setValue('user.email', row[2] or "")
	self.req.hdf.setValue('user.role', row[3] or "")	
	self.req.hdf.setValue('user.desc', wiki_to_html(row[4] or "",self.req.hdf, self.env,self.db) )
	self.req.hdf.setValue('user.team', row[5] or "")	

        self.req.hdf.setValue('title', 'About ' + row[1] +  ' (' + user + ')')
	
	cursor = self.db.cursor ()
	cursor.execute ('select id,summary,status,severity,priority from ticket where owner = %s and status = %s', user, 'assigned')
	i = 0
	info = []
	while 1:
	    row = cursor.fetchone()
	    if not row: break
	    item = {'id': row[0],
	            'summary': row[1],
		    'href': self.env.href.ticket(row[0])
		    }
	    info.append(item)
	    i = i + 1
	    
	util.add_dictlist_to_hdf(info, self.req.hdf, 'user.tickets')     


    def display (self):
        cs = neo_cs.CS(self.req.hdf)
        cs.parseStr(self.about_cs)
        self.req.display(cs)
	
class UserList (Module):
    template_name = ''

    about_cs = """
<?cs include "header.cs"?>
<div id="ctxtnav" class="nav">
 <ul>
  <li class="last">Add New User</li>
 </ul>
</div>
<br/>
<h1>Users list</h1>
<?cs each:team = userlist.team ?>
<h2><?cs var:team.name ?></h2>
   <TABLE width="100%" border=0>
     <TBODY>
     <TR>
      <TD class=sectionTitleBk width="16%" bgColor=#e2e2c5><B><FONT color=#666633>Id</FONT></B></TD>	  
      <TD class=sectionTitleBk width="25%" bgColor=#e2e2c5><B><FONT color=#666633>Name</FONT></B></TD>
      <TD class=sectionTitleBk width="30%" bgColor=#e2e2c5><B><FONT color=#666633>Email</FONT></B></TD>
      <TD class=sectionTitleBk width="29%" bgColor=#e2e2c5><B><FONT color=#666633>Role</FONT></B></TD>
     </TR>
<?cs each:user = userlist[team.name].user ?>
      <TR>
       <TD class=normalText width="16%"><a href="<?cs var:user.href ?>"><?cs var:user.username ?></a></TD>
       <TD class=normalText width="25%"><?cs var:user.name ?></TD>	 
       <TD class=normalText width="30%"><?cs var:user.email ?></TD>
       <TD class=normalText width="29%"><?cs var:user.role ?></TD>
      </TR>
<?cs /each ?>
</TBODY>
</TABLE>
 <br/>
<?cs /each ?>
<?cs include "footer.cs"?>
""" # about_cs
    
    
    def render (self):	

	cursort = self.db.cursor ()
	cursort.execute ('SELECT team FROM user GROUP BY team')

	infot = []	
	
	while 1:
	    rowt = cursort.fetchone()
	    if not rowt: break
	    itemt = {'name': rowt[0]}
	    infot.append(itemt)
	    
	    cursor = self.db.cursor ()	
	    cursor.execute ('SELECT username, name, email, role, desc, team FROM user where team=%s', rowt[0]) 
	    
	    info = []
	    while 1:
		row = cursor.fetchone()
		if not row: break
		item = {'username': row[0],
		'name': row[1],
		'email': row[2],
		'role': row[3],
		'href': self.env.href.user(row[0])
		}
		info.append(item)
		
	    util.add_dictlist_to_hdf(info, self.req.hdf, 'userlist.' + rowt[0] + '.user')
		 
	self.req.hdf.setValue('title', 'Users list')	
	util.add_dictlist_to_hdf(infot, self.req.hdf, 'userlist.team')

    def display (self):
        cs = neo_cs.CS(self.req.hdf)
        cs.parseStr(self.about_cs)
        self.req.display(cs)
