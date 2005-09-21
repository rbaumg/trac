<?cs include "header.cs" ?>
<?cs include "macros.cs" ?>

<div id="ctxtnav" class="nav">
 <h2>Xref Navigation</h2>
 <ul>
 </ul>
 <hr />
</div>


<div id="content" class="wiki">

 <?cs def:anchor(obj) ?>
  <a href="<?cs var:obj.href ?>"><em><?cs var:obj.displayname ?></em></a><?cs 
 /def ?>

 <?cs set:n_backlinks = len(xref.backlinks) ?>
 <?cs set:n_relations_in = len(xref.relations.in) ?>
 <?cs set:n_relations_out = len(xref.relations.out) ?>

 <h1>Cross-references for <a href="<?cs var:xref.me.href ?>"><?cs var:xref.me.displayname ?></a></h1>

 <h2 id='backlinks'>Backlinks (<?cs var:n_backlinks ?>)</h2>
  <dl><?cs 
   set:previous_name = "" ?><?cs
   each:item = xref.backlinks ?><?cs
    if item.fqname != previous_name ?><?cs
     set previous_name = item.fqname ?>
     <dt class="<?cs var:item.htmlclass ?>"><?cs call:anchor(item) ?></dt><?cs
    /if ?>
    <dd><?cs var:item.context ?> 
     <em>(by <?cs var:item.author ?>, <?cs var:item.age ?> ago, from the <?cs var:item.facet?>)</em></dd><?cs
   /each ?>
  </dl>

 <h2 id='incoming-relations'>Incoming relations (<?cs var:n_relations_in ?>)</h2>
  <dl><?cs
   each:item = xref.relations.in ?>
    <dt class="<?cs var:item.htmlclass ?>">
     <a href="<?cs var:item.href ?>">
       <em><?cs var:item.name ?></em> <?cs call:relation(item.relation) ?> <?cs var:xref.base.name ?>
     </a>
    </dt>
    <dd><?cs var:item.context ?></dd><?cs
   /each ?>
  </dl>

 <h2 id='outgoing-relations'>Outgoing relations (<?cs var:n_relations_out ?>)</h2>
  <dl><?cs
   each:item = xref.relations.out ?>
    <dt class="<?cs var:item.htmlclass ?>">
     <a href="<?cs var:item.href ?>">
       <?cs var:xref.base.name ?> <?cs call:relation(item.relation) ?> <em><?cs var:item.name ?></em>
     </a>
    </dt>
    <dd><?cs var:item.context ?></dd><?cs
   /each ?>
  </dl>

</div>

<?cs include "footer.cs" ?>
